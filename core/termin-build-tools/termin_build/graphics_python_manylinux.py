"""Build and audit the dual-ABI Graphics product on a pinned manylinux baseline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from .graphics_python_product import (
    PRODUCT_DISTRIBUTION,
    PRODUCT_MANIFEST,
    PRODUCT_MANIFEST_KIND,
    RESOURCE_DISTRIBUTION,
    SUPPORTED_PYTHON_ABIS,
    GraphicsPythonProductError,
    _publish,
    build_product,
    compose_product_wheel,
    verify_product,
)
from .wheelhouse import inspect_wheel


LOCK_RELATIVE_PATH = Path("build-system/graphics-python-manylinux-lock.json")
DOCKERFILE_RELATIVE_PATH = Path("build-system/manylinux/graphics-python/Dockerfile")
LAVAPIPE_REQUIREMENTS_RELATIVE_PATH = Path(
    "build-system/manylinux/graphics-python/lavapipe-python-requirements.txt"
)
SLANG_PATCH_RELATIVE_PATH = Path(
    "build-system/manylinux/graphics-python/patch-slang.py"
)
SLANG_VERSION_SCRIPT_RELATIVE_PATH = Path(
    "build-system/manylinux/graphics-python/slang-libstdcxx.map"
)
MANYLINUX_PRODUCT_SCHEMA = 4
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SAFE_LICENSE_NAME_RE = re.compile(r"^[A-Za-z0-9_.+-]+$")


class GraphicsPythonManylinuxError(RuntimeError):
    """The manylinux Graphics release candidate could not be produced."""


@dataclass(frozen=True)
class ReleaseLicense:
    name: str
    path: str
    source_url: str | None = None
    source_sha256: str | None = None


@dataclass(frozen=True)
class ManylinuxLock:
    policy: str
    architecture: str
    base_image: str
    auditwheel_version: str
    software_vulkan: dict[str, str]
    python_interpreters: dict[str, tuple[Path, str]]
    release_licenses: tuple[ReleaseLicense, ...]

    @classmethod
    def load(cls, path: Path) -> "ManylinuxLock":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise GraphicsPythonManylinuxError(
                f"failed to read manylinux lock {path}: {error}"
            ) from error
        if not isinstance(value, dict) or value.get("schema") != 1:
            raise GraphicsPythonManylinuxError(
                f"unsupported Graphics manylinux lock schema in {path}"
            )
        policy = value.get("policy")
        architecture = value.get("architecture")
        base_image = value.get("base_image")
        auditwheel_version = value.get("auditwheel_version")
        software_vulkan = value.get("software_vulkan")
        if policy != "manylinux_2_28_x86_64" or architecture != "x86_64":
            raise GraphicsPythonManylinuxError(
                "the initial Graphics manylinux contract must be manylinux_2_28_x86_64"
            )
        if not isinstance(base_image, str) or "@" not in base_image:
            raise GraphicsPythonManylinuxError("manylinux base_image must be digest-pinned")
        _repository, digest = base_image.rsplit("@", 1)
        if _DIGEST_RE.fullmatch(digest) is None:
            raise GraphicsPythonManylinuxError(
                f"manylinux base image has an invalid digest: {base_image}"
            )
        if not isinstance(auditwheel_version, str) or not auditwheel_version:
            raise GraphicsPythonManylinuxError("auditwheel_version must be a string")
        required_software_vulkan = {
            "implementation",
            "version",
            "source_url",
            "source_sha256",
            "icd_manifest",
        }
        if (
            not isinstance(software_vulkan, dict)
            or set(software_vulkan) != required_software_vulkan
            or not all(
                isinstance(key, str) and isinstance(item, str) and item
                for key, item in software_vulkan.items()
            )
            or _DIGEST_RE.fullmatch(f"sha256:{software_vulkan.get('source_sha256', '')}")
            is None
            or not software_vulkan.get("source_url", "").startswith("https://")
            or not software_vulkan.get("icd_manifest", "").startswith("/")
        ):
            raise GraphicsPythonManylinuxError(
                "software_vulkan must completely pin the release-smoke ICD"
            )

        raw_interpreters = value.get("python_interpreters")
        if not isinstance(raw_interpreters, dict) or set(raw_interpreters) != set(
            SUPPORTED_PYTHON_ABIS
        ):
            raise GraphicsPythonManylinuxError(
                "manylinux lock must define exactly cp314 and cp314t interpreters"
            )
        interpreters: dict[str, tuple[Path, str]] = {}
        for abi in SUPPORTED_PYTHON_ABIS:
            entry = raw_interpreters[abi]
            if not isinstance(entry, dict):
                raise GraphicsPythonManylinuxError(
                    f"manylinux interpreter {abi} must be an object"
                )
            executable = entry.get("path")
            version = entry.get("version")
            if (
                not isinstance(executable, str)
                or not executable.startswith("/opt/python/")
                or not isinstance(version, str)
                or not version.startswith("3.14.")
            ):
                raise GraphicsPythonManylinuxError(
                    f"manylinux interpreter {abi} has an invalid path or version"
                )
            interpreters[abi] = (Path(executable), version)

        raw_licenses = value.get("release_licenses")
        if not isinstance(raw_licenses, list) or not raw_licenses:
            raise GraphicsPythonManylinuxError("release_licenses must be a non-empty array")
        licenses: list[ReleaseLicense] = []
        seen_names: set[str] = set()
        for entry in raw_licenses:
            if not isinstance(entry, dict):
                raise GraphicsPythonManylinuxError("release license entry must be an object")
            if not set(entry) <= {"name", "path", "source_url", "source_sha256"}:
                raise GraphicsPythonManylinuxError(
                    f"release license entry has unknown fields: {entry!r}"
                )
            name = entry.get("name")
            license_path = entry.get("path")
            source_url = entry.get("source_url")
            source_sha256 = entry.get("source_sha256")
            if (
                not isinstance(name, str)
                or _SAFE_LICENSE_NAME_RE.fullmatch(name) is None
                or not isinstance(license_path, str)
                or not license_path
                or name in seen_names
            ):
                raise GraphicsPythonManylinuxError(
                    f"invalid or duplicate release license entry: {entry!r}"
                )
            if (source_url is None) != (source_sha256 is None) or (
                source_url is not None
                and (
                    not isinstance(source_url, str)
                    or not source_url.startswith("https://")
                    or not isinstance(source_sha256, str)
                    or _DIGEST_RE.fullmatch(f"sha256:{source_sha256}") is None
                )
            ):
                raise GraphicsPythonManylinuxError(
                    f"release license source must be completely pinned: {entry!r}"
                )
            seen_names.add(name)
            licenses.append(
                ReleaseLicense(
                    name=name,
                    path=license_path,
                    source_url=source_url,
                    source_sha256=source_sha256,
                )
            )
        return cls(
            policy=policy,
            architecture=architecture,
            base_image=base_image,
            auditwheel_version=auditwheel_version,
            software_vulkan=software_vulkan,
            python_interpreters=interpreters,
            release_licenses=tuple(licenses),
        )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_checked(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    print("+ " + " ".join(command), flush=True)
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=False,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
        )
    except OSError as error:
        raise GraphicsPythonManylinuxError(
            f"failed to execute {command[0]}: {error}"
        ) from error
    if result.returncode != 0:
        if capture:
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise GraphicsPythonManylinuxError(
            f"command failed with exit code {result.returncode}: {' '.join(command)}"
        )
    return result


def _docker_image_tag(repo_root: Path, lock_path: Path) -> str:
    dockerfile = repo_root / DOCKERFILE_RELATIVE_PATH
    requirements = repo_root / LAVAPIPE_REQUIREMENTS_RELATIVE_PATH
    payload = (
        lock_path.read_bytes()
        + b"\0"
        + dockerfile.read_bytes()
        + b"\0"
        + requirements.read_bytes()
    )
    return f"termin-graphics-manylinux:{_sha256_bytes(payload)[:16]}"


def _verify_dockerfile(repo_root: Path, lock: ManylinuxLock) -> Path:
    dockerfile = repo_root / DOCKERFILE_RELATIVE_PATH
    try:
        source = dockerfile.read_text(encoding="utf-8")
    except OSError as error:
        raise GraphicsPythonManylinuxError(f"cannot read {dockerfile}: {error}") from error
    from_images = [
        line.split()[1]
        for line in source.splitlines()
        if line.strip().upper().startswith("FROM ") and len(line.split()) >= 2
    ]
    if not from_images or any(image != lock.base_image for image in from_images):
        raise GraphicsPythonManylinuxError(
            "every manylinux Dockerfile stage must use the digest-pinned base image"
        )
    for key in ("source_url", "source_sha256", "icd_manifest"):
        if lock.software_vulkan[key] not in source:
            raise GraphicsPythonManylinuxError(
                f"manylinux Dockerfile disagrees with software_vulkan.{key}"
            )
    for license_entry in lock.release_licenses:
        if license_entry.source_url is None:
            continue
        if (
            license_entry.source_url not in source
            or license_entry.source_sha256 not in source
        ):
            raise GraphicsPythonManylinuxError(
                f"manylinux Dockerfile disagrees with the pinned {license_entry.name} "
                "license source"
            )
    return dockerfile


def _run_container_build(repo_root: Path, build_args: list[str]) -> int:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise GraphicsPythonManylinuxError(
            "Graphics manylinux packaging currently requires a Linux x86_64 Docker host"
        )
    if any(argument.startswith("--python-abi") for argument in build_args):
        raise GraphicsPythonManylinuxError(
            "the manylinux release gate always builds both cp314 and cp314t"
        )
    lock_path = repo_root / LOCK_RELATIVE_PATH
    lock = ManylinuxLock.load(lock_path)
    dockerfile = _verify_dockerfile(repo_root, lock)
    image_tag = _docker_image_tag(repo_root, lock_path)
    _run_checked(
        [
            "docker",
            "build",
            "--file",
            str(dockerfile),
            "--tag",
            image_tag,
            str(dockerfile.parent),
        ],
        cwd=repo_root,
    )
    image_id = _run_checked(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image_tag],
        cwd=repo_root,
        capture=True,
    ).stdout.strip()
    if _DIGEST_RE.fullmatch(image_id) is None:
        raise GraphicsPythonManylinuxError(
            f"Docker returned an invalid builder image id: {image_id!r}"
        )

    container_root = repo_root / "build" / "products" / "graphics-python-manylinux"
    home = container_root / "container-home"
    cache = container_root / "container-cache"
    home.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    command = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--volume",
        f"{repo_root}:/io",
        "--workdir",
        "/io",
        "--env",
        "HOME=/io/build/products/graphics-python-manylinux/container-home",
        "--env",
        "XDG_CACHE_HOME=/io/build/products/graphics-python-manylinux/container-cache",
        "--env",
        "PIP_DISABLE_PIP_VERSION_CHECK=1",
        "--env",
        "TERMIN_USE_BUNDLED_IMAGE_CODECS=ON",
        "--env",
        "TERMIN_ENABLE_SHADERC=OFF",
        "--env",
        f"TERMIN_MANYLINUX_BUILDER_IMAGE_ID={image_id}",
    ]
    build_jobs = os.environ.get("BUILD_JOBS")
    if build_jobs:
        command.extend(["--env", f"BUILD_JOBS={build_jobs}"])
    command.extend(
        [
            image_tag,
            str(lock.python_interpreters["cp314"][0]),
            "-m",
            "termin_build.graphics_python_manylinux",
            "--repo-root",
            "/io",
            "--inside-container",
            "--",
            *build_args,
        ]
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "core" / "termin-build-tools")
    # The module is imported inside the container through its own explicit path.
    command[command.index(image_tag) + 1 : command.index(image_tag) + 1] = [
        "env",
        "PYTHONPATH=/io/core/termin-build-tools",
    ]
    _run_checked(command, cwd=repo_root, env=env)
    return 0


def _probe_python(executable: Path) -> dict[str, object]:
    script = (
        "import json, platform, sys, sysconfig; "
        "print(json.dumps({'version': platform.python_version(), "
        "'soabi': sysconfig.get_config_var('SOABI'), "
        "'py_gil_disabled': bool(sysconfig.get_config_var('Py_GIL_DISABLED') or 0), "
        "'gil_enabled': sys._is_gil_enabled()}))"
    )
    result = _run_checked(
        [str(executable), "-I", "-c", script],
        cwd=Path.cwd(),
        capture=True,
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise GraphicsPythonManylinuxError(
            f"invalid Python identity from {executable}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise GraphicsPythonManylinuxError(f"invalid Python identity from {executable}")
    return value


def _license_sources(
    repo_root: Path,
    lock: ManylinuxLock,
    raw_build_root: Path,
) -> tuple[list[tuple[str, Path]], list[dict[str, str]]]:
    sources: list[tuple[str, Path]] = []
    provenance: list[dict[str, str]] = []
    for license_entry in lock.release_licenses:
        configured = Path(license_entry.path)
        source = configured if configured.is_absolute() else repo_root / configured
        if not source.is_file():
            raise GraphicsPythonManylinuxError(
                f"release license source is missing: {license_entry.name}: {source}"
            )
        sources.append((license_entry.name, source))
        provenance.append(
            {
                "name": license_entry.name,
                "source": license_entry.path,
                "sha256": _sha256_file(source),
                **(
                    {
                        "source_url": license_entry.source_url,
                        "source_sha256": license_entry.source_sha256,
                    }
                    if license_entry.source_url is not None
                    else {}
                ),
            }
        )

    nanobind_licenses = sorted(
        (raw_build_root / "cp314" / "python-build-env").glob(
            "lib/python*/site-packages/nanobind-*.dist-info/licenses/LICENSE"
        )
    )
    if len(nanobind_licenses) != 1:
        raise GraphicsPythonManylinuxError(
            "expected exactly one nanobind license in the cp314 build environment"
        )
    nanobind_license = nanobind_licenses[0]
    sources.append(("nanobind", nanobind_license))
    provenance.append(
        {
            "name": "nanobind",
            "source": "pinned nanobind build requirement",
            "sha256": _sha256_file(nanobind_license),
        }
    )
    return sources, provenance


def _resource_library_names(wheel: Path) -> list[str]:
    try:
        with zipfile.ZipFile(wheel) as archive:
            value = json.loads(
                archive.read("termin_graphics_profile/native-libraries.json")
            )
    except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        raise GraphicsPythonManylinuxError(
            f"cannot read runtime library inventory from {wheel.name}: {error}"
        ) from error
    if not isinstance(value, list) or not all(
        isinstance(name, str) and Path(name).name == name for name in value
    ):
        raise GraphicsPythonManylinuxError(
            f"invalid runtime library inventory in {wheel.name}"
        )
    return sorted(value)


def _is_auditwheel_alias(soname: str, candidate: str) -> bool:
    """Return whether candidate is auditwheel's hash-renamed copy of soname."""
    marker = soname.find(".so")
    if marker == -1:
        return candidate == soname
    prefix = soname[:marker]
    suffix = soname[marker:]
    return candidate == soname or (
        candidate.startswith(f"{prefix}-") and candidate.endswith(suffix)
    )


def _auditwheel(
    command: list[str],
    *,
    repo_root: Path,
    library_path: Path,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AUDITWHEEL_LD_LIBRARY_PATH"] = str(library_path)
    return _run_checked(command, cwd=repo_root, env=env, capture=True)


def _repair_wheelhouse(
    *,
    repo_root: Path,
    lock: ManylinuxLock,
    raw_wheelhouse: Path,
    raw_manifest: dict[str, object],
    raw_build_root: Path,
    destination: Path,
    licenses: list[tuple[str, Path]],
) -> tuple[list[dict[str, object]], dict[str, str]]:
    raw_variants = raw_manifest.get("variants")
    if not isinstance(raw_variants, list) or len(raw_variants) != len(
        SUPPORTED_PYTHON_ABIS
    ):
        raise GraphicsPythonManylinuxError(
            "raw wheel manifest does not contain the complete ABI matrix"
        )
    destination.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, object]] = []
    wheels_by_abi: dict[str, str] = {}
    for raw_variant in raw_variants:
        if not isinstance(raw_variant, dict):
            raise GraphicsPythonManylinuxError("raw ABI variant must be an object")
        abi = raw_variant.get("id")
        raw_names = raw_variant.get("wheels")
        if (
            abi not in SUPPORTED_PYTHON_ABIS
            or abi in wheels_by_abi
            or not isinstance(raw_names, list)
            or not raw_names
            or not all(isinstance(name, str) for name in raw_names)
        ):
            raise GraphicsPythonManylinuxError(
                f"invalid raw Graphics ABI variant: {raw_variant!r}"
            )
        raw_wheels = [raw_wheelhouse / name for name in raw_names]
        missing = [wheel.name for wheel in raw_wheels if not wheel.is_file()]
        if missing:
            raise GraphicsPythonManylinuxError(
                f"raw {abi} variant is missing wheels: {', '.join(missing)}"
            )
        resource_wheels = [
            wheel
            for wheel in raw_wheels
            if inspect_wheel(wheel).name == RESOURCE_DISTRIBUTION
        ]
        if len(resource_wheels) != 1:
            raise GraphicsPythonManylinuxError(
                f"raw {abi} variant has {len(resource_wheels)} resource wheels"
            )
        excludes = _resource_library_names(resource_wheels[0])
        library_path = raw_build_root / abi / "native-prefix" / "lib"
        with tempfile.TemporaryDirectory(prefix="termin-manylinux-wheel-") as temporary:
            temporary_root = Path(temporary)
            audit_input = compose_product_wheel(
                raw_wheels,
                temporary_root / "composed",
                abi=abi,
                platform_tag="linux_x86_64",
                licenses=licenses,
            )
            before = _auditwheel(
                ["auditwheel", "show", str(audit_input)],
                repo_root=repo_root,
                library_path=library_path,
            )
            repaired_dir = temporary_root / "repaired"
            repaired_dir.mkdir()
            repair_command = [
                "auditwheel",
                "repair",
                "--plat",
                lock.policy,
                "--only-plat",
                "--wheel-dir",
                str(repaired_dir),
            ]
            for soname in excludes:
                repair_command.extend(["--exclude", soname])
            repair_command.append(str(audit_input))
            repair = _auditwheel(
                repair_command,
                repo_root=repo_root,
                library_path=library_path,
            )
            repaired = sorted(repaired_dir.glob("*.whl"))
            if len(repaired) != 1:
                raise GraphicsPythonManylinuxError(
                    f"auditwheel produced {len(repaired)} wheels for {abi}"
                )
            repaired_artifact = inspect_wheel(repaired[0])
            if repaired_artifact.name != PRODUCT_DISTRIBUTION:
                raise GraphicsPythonManylinuxError(
                    f"repaired wheel has unexpected distribution {repaired_artifact.name}"
                )
            platforms = {tag.rsplit("-", 1)[-1] for tag in repaired_artifact.tags}
            if platforms != {lock.policy}:
                raise GraphicsPythonManylinuxError(
                    f"repaired wheel has unexpected platform tags {sorted(platforms)}: "
                    f"{repaired[0].name}"
                )
            after = _auditwheel(
                ["auditwheel", "show", str(repaired[0])],
                repo_root=repo_root,
                library_path=library_path,
            )
            target = destination / repaired[0].name
            shutil.copy2(repaired[0], target)
            wheels_by_abi[abi] = target.name
            records.append(
                {
                    "filename": target.name,
                    "sha256": _sha256_file(target),
                    "python_abis": [abi],
                    "auditwheel": {
                        "excluded_runtime_sonames": excludes,
                        "show_before_sha256": _sha256_bytes(
                            (before.stdout + before.stderr).encode("utf-8")
                        ),
                        "repair_log_sha256": _sha256_bytes(
                            (repair.stdout + repair.stderr).encode("utf-8")
                        ),
                        "show_after_sha256": _sha256_bytes(
                            (after.stdout + after.stderr).encode("utf-8")
                        ),
                    },
                }
            )

        with zipfile.ZipFile(target) as archive:
            names = set(archive.namelist())
        missing = [
            soname
            for soname in excludes
            if f"termin_graphics_profile/lib/{soname}" not in names
        ]
        if missing:
            raise GraphicsPythonManylinuxError(
                f"repaired {abi} runtime owner lost excluded libraries: {', '.join(missing)}"
            )
        auditwheel_libraries = [
            Path(name).name
            for name in names
            if name.startswith(f"{PRODUCT_DISTRIBUTION.replace('-', '_')}.libs/")
        ]
        duplicates = sorted(
            candidate
            for candidate in auditwheel_libraries
            if any(
                _is_auditwheel_alias(soname, candidate)
                for soname in excludes
            )
        )
        if duplicates:
            raise GraphicsPythonManylinuxError(
                f"repaired {abi} runtime owner contains duplicated internal libraries: "
                + ", ".join(duplicates)
            )
    if set(wheels_by_abi) != set(SUPPORTED_PYTHON_ABIS):
        raise GraphicsPythonManylinuxError(
            "manylinux composition did not produce both public ABI wheels"
        )
    return sorted(records, key=lambda entry: str(entry["filename"])), wheels_by_abi


def _copy_install_index(
    destination: Path,
    sources: list[Path],
) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    digests: dict[str, str] = {}
    for source_dir in sources:
        for wheel in sorted(source_dir.glob("*.whl")):
            digest = _sha256_file(wheel)
            previous = digests.get(wheel.name)
            if previous is not None:
                if previous != digest:
                    raise GraphicsPythonManylinuxError(
                        f"candidate install index has conflicting wheel {wheel.name}"
                    )
                continue
            shutil.copy2(wheel, destination / wheel.name)
            digests[wheel.name] = digest


def _inside_container(repo_root: Path, build_args: list[str]) -> int:
    lock_path = repo_root / LOCK_RELATIVE_PATH
    lock = ManylinuxLock.load(lock_path)
    dockerfile = _verify_dockerfile(repo_root, lock)
    auditwheel_version = _run_checked(
        ["auditwheel", "--version"], cwd=repo_root, capture=True
    ).stdout
    if f"auditwheel {lock.auditwheel_version}" not in auditwheel_version:
        raise GraphicsPythonManylinuxError(
            "auditwheel version disagrees with the manylinux lock: "
            + auditwheel_version.strip()
        )

    python_paths = {
        abi: executable
        for abi, (executable, _version) in lock.python_interpreters.items()
    }
    python_probes: dict[str, dict[str, object]] = {}
    for abi in SUPPORTED_PYTHON_ABIS:
        executable, expected_version = lock.python_interpreters[abi]
        probe = _probe_python(executable)
        expected_soabi_fragment = "cpython-314t-" if abi == "cp314t" else "cpython-314-"
        expected_gil_enabled = abi == "cp314"
        if (
            probe.get("version") != expected_version
            or expected_soabi_fragment not in str(probe.get("soabi"))
            or probe.get("gil_enabled") is not expected_gil_enabled
        ):
            raise GraphicsPythonManylinuxError(
                f"manylinux interpreter {abi} disagrees with its lock: {probe}"
            )
        python_probes[abi] = probe

    root = repo_root / "build" / "products" / "graphics-python-manylinux"
    raw_build_root = root / "raw-build"
    raw_wheelhouse = root / "raw-wheelhouse"
    slang_root = root / "slang-toolchain"
    slang_patch = repo_root / SLANG_PATCH_RELATIVE_PATH
    if build_product(
        repo_root,
        build_args,
        product_root=raw_build_root,
        destination=raw_wheelhouse,
        python_executables=python_paths,
        slang_install_root=slang_root,
        slang_post_extract_script=slang_patch,
        public_projection=False,
    ) != 0:
        return 1
    try:
        raw_manifest = json.loads(
            (raw_wheelhouse / PRODUCT_MANIFEST).read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as error:
        raise GraphicsPythonManylinuxError(
            f"cannot read raw Graphics product manifest: {error}"
        ) from error
    if raw_manifest.get("python_abi_variants") != list(SUPPORTED_PYTHON_ABIS):
        raise GraphicsPythonManylinuxError(
            "raw Graphics product did not build the complete dual-ABI matrix"
        )

    licenses, license_provenance = _license_sources(repo_root, lock, raw_build_root)
    with tempfile.TemporaryDirectory(prefix="graphics-manylinux-publish.", dir=root) as temporary:
        temporary_root = Path(temporary)
        prepared = temporary_root / "wheels"
        wheel_records, wheels_by_abi = _repair_wheelhouse(
            repo_root=repo_root,
            lock=lock,
            raw_wheelhouse=raw_wheelhouse,
            raw_manifest=raw_manifest,
            raw_build_root=raw_build_root,
            destination=prepared,
            licenses=licenses,
        )
        install_index = temporary_root / "install-index"
        external_sources = [
            raw_build_root / abi / "external-wheels" for abi in SUPPORTED_PYTHON_ABIS
        ]
        _copy_install_index(install_index, [prepared, *external_sources])
        for abi in SUPPORTED_PYTHON_ABIS:
            build_python = raw_build_root / abi / "python-build-env" / "bin" / "python"
            verify_product(
                repo_root,
                install_index,
                build_python,
                external_wheels=install_index,
            )

        variants: list[dict[str, object]] = []
        for raw_variant in raw_manifest["variants"]:
            abi = raw_variant["id"]
            variants.append(
                {
                    "id": abi,
                    "version": raw_variant["version"],
                    "python_abi": raw_variant["python_abi"],
                    "native_build_id": raw_variant["native_build_id"],
                    "python_runtime": python_probes[abi],
                    "wheel": wheels_by_abi[abi],
                    "wheel_count": 1,
                }
            )
        product_data = {
            "schema": MANYLINUX_PRODUCT_SCHEMA,
            "manifest_kind": PRODUCT_MANIFEST_KIND,
            "product": raw_manifest["product"],
            "version": raw_manifest["version"],
            "profile": raw_manifest["profile"],
            "platform": lock.policy,
            "python_abi_variants": list(SUPPORTED_PYTHON_ABIS),
            "projection": "public-monolith",
            "variants": variants,
            "shared_wheels": [],
            "wheels": wheel_records,
            "wheel_count": len(wheel_records),
            "manylinux": {
                "policy": lock.policy,
                "architecture": lock.architecture,
                "base_image": lock.base_image,
                "lock_sha256": _sha256_file(lock_path),
                "builder_image_id": os.environ.get(
                    "TERMIN_MANYLINUX_BUILDER_IMAGE_ID", "unknown"
                ),
                "dockerfile_sha256": _sha256_file(dockerfile),
                "lavapipe_python_requirements_sha256": _sha256_file(
                    repo_root / LAVAPIPE_REQUIREMENTS_RELATIVE_PATH
                ),
                "slang_compatibility": {
                    "patch_sha256": _sha256_file(slang_patch),
                    "version_script_sha256": _sha256_file(
                        repo_root / SLANG_VERSION_SCRIPT_RELATIVE_PATH
                    ),
                },
                "auditwheel_version": lock.auditwheel_version,
                "software_vulkan": lock.software_vulkan,
                "release_licenses": license_provenance,
                "raw_manifest_sha256": _sha256_file(raw_wheelhouse / PRODUCT_MANIFEST),
            },
        }
        destination = repo_root / "dist" / "graphics-python-manylinux"
        _publish(prepared, destination, product_data)
    print(f"Graphics manylinux product published to {destination}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--inside-container", action="store_true")
    parser.add_argument("build_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    build_args = list(args.build_args)
    if build_args[:1] == ["--"]:
        build_args = build_args[1:]
    try:
        if args.inside_container:
            return _inside_container(args.repo_root.resolve(), build_args)
        return _run_container_build(args.repo_root.resolve(), build_args)
    except (
        GraphicsPythonManylinuxError,
        GraphicsPythonProductError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"ERROR: failed to build Graphics manylinux product: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
