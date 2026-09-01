"""Build the first standalone Python distribution of the Graphics profile."""

from __future__ import annotations

import argparse
import base64
from email.parser import Parser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
import zipfile

from .artifact_manifest import ArtifactManifest, SDK_MANIFEST_NAME
from .local_wheel_artifacts import (
    build_local_wheel_artifact_set,
    validate_local_wheel_artifact_set,
    write_local_wheel_manifest,
)
from .package_manifest import load_manifest
from .sdk import (
    _clear_python_package_build_caches,
    _resolve_bindings_dir,
    _run,
    prepare_locked_runtime_wheels,
    prepare_python_build_environment,
    prepare_pinned_python_build_environment,
)
from .sdk_profiles import load_sdk_profiles, select_python_packages
from .slang_toolchain import SlangToolchainError, prepare_slang_toolchain
from .versioning import public_version
from .wheelhouse import inspect_wheel


PRODUCT_DISTRIBUTION = "termin-graphics"
RESOURCE_DISTRIBUTION = "termin-graphics-profile"
PRODUCT_IMPORT = "termin_graphics_profile"
PRODUCT_VERSION = public_version()
PRODUCT_MANIFEST = "termin-graphics-python-product.json"
PRODUCT_MANIFEST_KIND = "termin-graphics-python-product"
PRODUCT_MANIFEST_SCHEMA = 3
INTERNAL_PRODUCT_MANIFEST_SCHEMA = 2
SUPPORTED_PYTHON_ABIS = ("cp314", "cp314t")
BUILD_ONLY_DISTRIBUTIONS = frozenset({"termin-build-tools"})
WINDOW_EXTENSIONS = (
    "termin.window._window_native",
    "termin.gui_native._gui_native_window",
)
LINUX_BUNDLED_RUNTIME_LIBRARIES = ("libSDL2-2.0.so.0",)
_DISTRIBUTION_NORMALIZE_RE = re.compile(r"[-_.]+")
_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


class GraphicsPythonProductError(RuntimeError):
    """The standalone Graphics Python product could not be assembled."""


def _record_digest(payload: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).decode("ascii")
    return digest.rstrip("=")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_product_build_args(build_args: list[str]) -> tuple[tuple[str, ...], list[str]]:
    """Separate the product ABI selector from arguments forwarded to CMake."""
    selected: str | None = None
    forwarded: list[str] = []
    index = 0
    while index < len(build_args):
        argument = build_args[index]
        if argument == "--python-abi":
            index += 1
            if index >= len(build_args):
                raise GraphicsPythonProductError("--python-abi requires cp314 or cp314t")
            value = build_args[index]
        elif argument.startswith("--python-abi="):
            value = argument.split("=", 1)[1]
        else:
            forwarded.append(argument)
            index += 1
            continue
        if selected is not None:
            raise GraphicsPythonProductError("--python-abi may be specified only once")
        if value not in SUPPORTED_PYTHON_ABIS:
            choices = ", ".join(SUPPORTED_PYTHON_ABIS)
            raise GraphicsPythonProductError(
                f"unsupported Graphics product Python ABI {value!r}; expected one of: {choices}"
            )
        selected = value
        index += 1
    return ((selected,) if selected is not None else SUPPORTED_PYTHON_ABIS), forwarded


def _merge_variant_wheels(
    variant_wheel_dirs: list[tuple[str, Path]],
    destination: Path,
) -> list[dict[str, object]]:
    """Merge ABI wheel sets, admitting a shared wheel only when bytes are identical."""
    destination.mkdir(parents=True, exist_ok=False)
    merged: dict[str, dict[str, object]] = {}
    for variant, wheel_dir in variant_wheel_dirs:
        wheels = sorted(wheel_dir.glob("*.whl"))
        if not wheels:
            raise GraphicsPythonProductError(
                f"Graphics product variant {variant} produced no wheels under {wheel_dir}"
            )
        for wheel in wheels:
            digest = _sha256_file(wheel)
            existing = merged.get(wheel.name)
            if existing is not None:
                if existing["sha256"] != digest:
                    raise GraphicsPythonProductError(
                        "same-named wheel differs between Python ABI variants: "
                        f"{wheel.name} ({', '.join(existing['python_abis'])} and {variant})"
                    )
                existing["python_abis"].append(variant)
                continue
            shutil.copy2(wheel, destination / wheel.name)
            merged[wheel.name] = {
                "filename": wheel.name,
                "sha256": digest,
                "python_abis": [variant],
            }
    return [merged[name] for name in sorted(merged)]


def _normalized_distribution(name: str) -> str:
    return _DISTRIBUTION_NORMALIZE_RE.sub("-", name).lower()


def _wheel_metadata(archive: zipfile.ZipFile, wheel: Path) -> tuple[str, str]:
    names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
    if len(names) != 1:
        raise GraphicsPythonProductError(
            f"input wheel has {len(names)} METADATA files: {wheel.name}"
        )
    try:
        return names[0], archive.read(names[0]).decode("utf-8")
    except (KeyError, UnicodeDecodeError) as error:
        raise GraphicsPythonProductError(
            f"cannot read input wheel metadata from {wheel.name}: {error}"
        ) from error


def compose_product_wheel(
    input_wheels: list[Path],
    destination: Path,
    *,
    abi: str,
    platform_tag: str,
    licenses: list[tuple[str, Path]] | None = None,
) -> Path:
    """Fuse one ABI's internal wheels into the single public Graphics wheel."""
    if abi not in SUPPORTED_PYTHON_ABIS:
        raise GraphicsPythonProductError(f"unsupported product wheel ABI: {abi}")
    if not input_wheels:
        raise GraphicsPythonProductError("cannot compose a product wheel from an empty wheel set")

    destination.mkdir(parents=True, exist_ok=True)
    interpreter = abi.removesuffix("t")
    dist_info = f"termin_graphics-{PRODUCT_VERSION}.dist-info"
    output = destination / (
        f"termin_graphics-{PRODUCT_VERSION}-{interpreter}-{abi}-{platform_tag}.whl"
    )
    payloads: dict[str, tuple[bytes, int]] = {}
    input_metadata: list[tuple[str, str, str]] = []

    for wheel in sorted(input_wheels):
        try:
            with zipfile.ZipFile(wheel) as archive:
                metadata_name, metadata_text = _wheel_metadata(archive, wheel)
                metadata = Parser().parsestr(metadata_text)
                distribution = metadata.get("Name")
                version = metadata.get("Version")
                if not distribution or not version:
                    raise GraphicsPythonProductError(
                        f"input wheel metadata has no Name/Version: {wheel.name}"
                    )
                if version != PRODUCT_VERSION:
                    raise GraphicsPythonProductError(
                        f"input wheel {wheel.name} has version {version}, "
                        f"expected {PRODUCT_VERSION}"
                    )
                input_metadata.append((distribution, metadata_name, metadata_text))
                dist_info_root = metadata_name.rsplit("/", 1)[0] + "/"
                license_root = dist_info_root + "licenses/"
                normalized = _normalized_distribution(distribution)
                for info in archive.infolist():
                    name = info.filename
                    if info.is_dir():
                        continue
                    if name.startswith(dist_info_root):
                        if not name.startswith(license_root):
                            continue
                        relative = name.removeprefix(license_root)
                        if not relative or ".." in Path(relative).parts:
                            raise GraphicsPythonProductError(
                                f"unsafe bundled license path {name!r} in {wheel.name}"
                            )
                        name = f"{dist_info}/licenses/{normalized}/{relative}"
                    elif ".dist-info/" in name or ".data/" in name:
                        raise GraphicsPythonProductError(
                            f"unsupported wheel layout entry {name!r} in {wheel.name}"
                        )
                    if name.startswith("/") or ".." in Path(name).parts:
                        raise GraphicsPythonProductError(
                            f"unsafe payload path {name!r} in {wheel.name}"
                        )
                    payload = archive.read(info)
                    mode = (info.external_attr >> 16) & 0o777 or 0o644
                    previous = payloads.get(name)
                    if previous is not None and previous[0] != payload:
                        raise GraphicsPythonProductError(
                            f"product payload collision at {name}: {wheel.name} differs"
                        )
                    if previous is None:
                        payloads[name] = (payload, mode)
        except (OSError, zipfile.BadZipFile) as error:
            raise GraphicsPythonProductError(
                f"cannot read input wheel {wheel.name}: {error}"
            ) from error

    internal_distributions = {
        _normalized_distribution(distribution)
        for distribution, _metadata_name, _text in input_metadata
    }
    requirements: set[str] = set()
    requires_python: set[str] = set()
    for _distribution, _metadata_name, metadata_text in input_metadata:
        metadata = Parser().parsestr(metadata_text)
        python_constraint = metadata.get("Requires-Python")
        if python_constraint:
            requires_python.add(python_constraint)
        for requirement in metadata.get_all("Requires-Dist", []):
            match = _REQUIREMENT_NAME_RE.match(requirement)
            if match is None:
                raise GraphicsPythonProductError(
                    f"cannot parse input Requires-Dist value: {requirement!r}"
                )
            if _normalized_distribution(match.group(1)) not in internal_distributions:
                requirements.add(requirement)
    if len(requires_python) > 1:
        raise GraphicsPythonProductError(
            "input wheels disagree on Requires-Python: " + ", ".join(sorted(requires_python))
        )

    for license_name, license_path in licenses or []:
        if Path(license_name).name != license_name or not license_path.is_file():
            raise GraphicsPythonProductError(
                f"invalid release license {license_name!r}: {license_path}"
            )
        archive_name = f"{dist_info}/licenses/{license_name}/{license_path.name}"
        payload = license_path.read_bytes()
        previous = payloads.get(archive_name)
        if previous is not None and previous[0] != payload:
            raise GraphicsPythonProductError(
                f"release license collision at {archive_name}"
            )
        payloads[archive_name] = (payload, 0o644)

    license_fields = "".join(
        f"License-File: {name.removeprefix(dist_info + '/') }\n"
        for name in sorted(payloads)
        if name.startswith(f"{dist_info}/licenses/")
    )
    requirement_fields = "".join(
        f"Requires-Dist: {requirement}\n" for requirement in sorted(requirements)
    )
    payloads[f"{dist_info}/METADATA"] = (
        (
            "Metadata-Version: 2.4\n"
            f"Name: {PRODUCT_DISTRIBUTION}\n"
            f"Version: {PRODUCT_VERSION}\n"
            "Summary: Standalone Python runtime for Termin Graphics\n"
            "Requires-Python: >=3.14\n"
            "License-Expression: Apache-2.0\n"
            "Description-Content-Type: text/markdown\n"
            "Project-URL: Source, https://github.com/termin-dev/termin\n"
            f"{license_fields}"
            f"{requirement_fields}\n"
            "# Termin Graphics\n\n"
            "The standalone Python runtime for Termin's modular graphics stack.\n"
        ).encode("utf-8"),
        0o644,
    )
    payloads[f"{dist_info}/WHEEL"] = (
        (
            "Wheel-Version: 1.0\n"
            "Generator: termin-build-tools\n"
            "Root-Is-Purelib: false\n"
            f"Tag: {interpreter}-{abi}-{platform_tag}\n"
        ).encode("utf-8"),
        0o644,
    )
    record_name = f"{dist_info}/RECORD"
    record_lines = [
        f"{name},sha256={_record_digest(payload)},{len(payload)}"
        for name, (payload, _mode) in sorted(payloads.items())
    ]
    record_lines.append(f"{record_name},,")
    payloads[record_name] = (("\n".join(record_lines) + "\n").encode("utf-8"), 0o644)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, (payload, mode) in sorted(payloads.items()):
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, payload)
    return output


def _resource_module() -> bytes:
    source = '''"""Wheel-owned runtime resources for the Termin Graphics profile."""

from __future__ import annotations

import os
from pathlib import Path


def root() -> Path:
    return Path(__file__).resolve().parent


def _required(path: Path, description: str) -> Path:
    if not path.is_file():
        raise RuntimeError(f"termin-graphics-profile is missing {description}: {path}")
    return path


def font_path() -> Path:
    return _required(
        root() / "share" / "termin" / "fonts" / "DroidSans.ttf",
        "DroidSans.ttf",
    )


def shader_artifact_root() -> Path:
    path = root() / "share" / "termin"
    if not (path / "shaders").is_dir():
        raise RuntimeError(f"termin-graphics-profile is missing compiled shaders: {path}")
    return path


def activate() -> None:
    os.environ.setdefault("TERMIN_UI_FONT", str(font_path()))
    os.environ.setdefault(
        "TERMIN_BUILTIN_SHADER_ROOT",
        str(root() / "share" / "termin" / "builtin_shaders"),
    )
    os.environ.setdefault("TERMIN_SHADER_ARTIFACT_ROOT", str(shader_artifact_root()))
    os.environ.setdefault("TERMIN_SHADER_DEV_COMPILE", "0")
'''
    return source.encode("utf-8")


def _add_payload(
    payloads: dict[str, tuple[bytes, int]],
    archive_name: str,
    source: Path,
) -> None:
    data = source.read_bytes()
    mode = stat.S_IMODE(source.stat().st_mode)
    previous = payloads.get(archive_name)
    if previous is not None and previous[0] != data:
        raise GraphicsPythonProductError(
            f"resource collision at {archive_name}: {source} differs from another payload"
        )
    payloads[archive_name] = (data, mode)


def _add_tree(
    payloads: dict[str, tuple[bytes, int]],
    source_root: Path,
    archive_root: str,
) -> None:
    if not source_root.is_dir():
        raise GraphicsPythonProductError(f"required resource directory is missing: {source_root}")
    for source in sorted(path for path in source_root.rglob("*") if path.is_file()):
        relative = source.relative_to(source_root).as_posix()
        _add_payload(payloads, f"{archive_root}/{relative}", source)


def _add_named_libraries(
    payloads: dict[str, tuple[bytes, int]],
    source_root: Path,
    archive_root: str,
    names: list[str],
) -> None:
    for name in names:
        if Path(name).name != name:
            raise GraphicsPythonProductError(f"unsafe native library name: {name!r}")
        source = source_root / name
        if not source.is_file():
            raise GraphicsPythonProductError(f"manifest-declared native library is missing: {source}")
        _add_payload(payloads, f"{archive_root}/{name}", source)


def build_resource_wheel(
    *,
    sdk_prefix: Path,
    wheel_dir: Path,
    requirements: list[tuple[str, str]],
) -> Path:
    """Build the binary resource/metapackage wheel for one native build."""
    manifest = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
    abi = manifest.python_abi.wheel_abi_tag
    interpreter = abi.removesuffix("t")
    if sys.platform != "linux":
        raise GraphicsPythonProductError("the initial Graphics Python product supports Linux only")
    platform_tag = "linux_x86_64"
    version = PRODUCT_VERSION
    dist_info = f"termin_graphics_profile-{version}.dist-info"
    filename = f"termin_graphics_profile-{version}-{interpreter}-{abi}-{platform_tag}.whl"
    output = wheel_dir / filename

    payloads: dict[str, tuple[bytes, int]] = {
        f"{PRODUCT_IMPORT}/__init__.py": (_resource_module(), 0o644),
    }
    _add_payload(
        payloads,
        f"{dist_info}/licenses/SDL2/LICENSE.txt",
        sdk_prefix / "share" / "licenses" / "SDL2" / "LICENSE.txt",
    )
    native_library_names = sorted(
        {
            dependency["name"]
            for artifact in manifest.data["artifacts"]
            for dependency in artifact.get("runtime_dependencies", [])
            if isinstance(dependency, dict) and isinstance(dependency.get("name"), str)
        }
        | set(LINUX_BUNDLED_RUNTIME_LIBRARIES)
    )
    payloads[f"{PRODUCT_IMPORT}/native-libraries.json"] = (
        (json.dumps(native_library_names, indent=2) + "\n").encode("utf-8"),
        0o644,
    )
    _add_named_libraries(
        payloads,
        sdk_prefix / "lib",
        f"{PRODUCT_IMPORT}/lib",
        native_library_names,
    )
    _add_tree(payloads, sdk_prefix / "share" / "termin", f"{PRODUCT_IMPORT}/share/termin")

    requirement_lines = "".join(
        f"Requires-Dist: {name}=={required_version}\n"
        for name, required_version in sorted(requirements)
    )
    payloads[f"{dist_info}/METADATA"] = (
        (
            "Metadata-Version: 2.3\n"
            f"Name: {RESOURCE_DISTRIBUTION}\n"
            f"Version: {version}\n"
            "Summary: Standalone runtime resources for the Termin Graphics profile\n"
            "Requires-Python: >=3.14\n"
            "License-File: licenses/SDL2/LICENSE.txt\n"
            f"{requirement_lines}\n"
        ).encode("utf-8"),
        0o644,
    )
    payloads[f"{dist_info}/WHEEL"] = (
        (
            "Wheel-Version: 1.0\nGenerator: termin-build-tools\nRoot-Is-Purelib: false\n"
            f"Tag: {interpreter}-{abi}-{platform_tag}\n"
        ).encode("utf-8"),
        0o644,
    )

    records = [
        f"{name},sha256={_record_digest(data)},{len(data)}"
        for name, (data, _mode) in sorted(payloads.items())
    ]
    record_name = f"{dist_info}/RECORD"
    records.append(f"{record_name},,")
    payloads[record_name] = (("\n".join(records) + "\n").encode("utf-8"), 0o644)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, (data, mode) in sorted(payloads.items()):
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(info, data)
    return output


def _publish(source: Path, destination: Path, product_data: dict[str, object]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.new-{uuid.uuid4().hex}"
    backup = destination.parent / f".{destination.name}.old-{uuid.uuid4().hex}"
    shutil.copytree(source, temporary)
    (temporary / PRODUCT_MANIFEST).write_text(
        json.dumps(product_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    had_destination = destination.exists()
    if had_destination:
        destination.replace(backup)
    try:
        temporary.replace(destination)
    except Exception:
        if had_destination:
            backup.replace(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _verify_relative_elf_rpaths(site_packages: Path) -> None:
    readelf = shutil.which("readelf")
    if readelf is None:
        raise GraphicsPythonProductError("readelf is required to verify Linux wheel RPATHs")
    for path in sorted(candidate for candidate in site_packages.rglob("*") if candidate.is_file()):
        try:
            with path.open("rb") as stream:
                if stream.read(4) != b"\x7fELF":
                    continue
        except OSError as error:
            raise GraphicsPythonProductError(f"cannot inspect installed wheel file {path}: {error}") from error
        result = subprocess.run(
            [readelf, "-d", str(path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if result.returncode != 0:
            raise GraphicsPythonProductError(
                f"readelf failed for installed wheel file {path}: {result.stderr.strip()}"
            )
        for line in result.stdout.splitlines():
            if "RPATH" not in line and "RUNPATH" not in line:
                continue
            value = line.rsplit("[", 1)[-1].split("]", 1)[0]
            absolute = [entry for entry in value.split(":") if entry.startswith("/")]
            if absolute:
                raise GraphicsPythonProductError(
                    f"installed wheel ELF has absolute RPATH entries {absolute}: {path}"
                )


def verify_product(
    repo_root: Path,
    wheel_dir: Path,
    build_python: Path,
    *,
    external_wheels: Path,
    distribution: str = PRODUCT_DISTRIBUTION,
) -> None:
    """Install and render the product without any SDK or checkout Python overlay."""
    with tempfile.TemporaryDirectory(prefix="termin-graphics-python-verify-") as temporary:
        root = Path(temporary)
        venv = root / "venv"
        if _run([str(build_python), "-m", "venv", str(venv)], cwd=root) != 0:
            raise GraphicsPythonProductError("failed to create clean product verification venv")
        python = venv / "bin" / "python"
        if _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(wheel_dir),
                "--find-links",
                str(external_wheels),
                distribution,
            ],
            cwd=root,
        ) != 0:
            raise GraphicsPythonProductError("clean pip install of the product failed")
        clean_env = os.environ.copy()
        for name in (
            "TERMIN_SDK",
            "PYTHONPATH",
            "PYTHONHOME",
            "LD_LIBRARY_PATH",
            "TERMIN_SHADERC",
            "TERMIN_SLANGC",
            "TERMIN_SHADER_DEV_COMPILE",
            "TERMIN_SHADER_ARTIFACT_ROOT",
            "TERMIN_BUILTIN_SHADER_ROOT",
            "TERMIN_UI_FONT",
        ):
            clean_env.pop(name, None)
        clean_env["XDG_CACHE_HOME"] = str(root / "cache")
        if _run([str(python), "-m", "pip", "check"], cwd=root, env=clean_env) != 0:
            raise GraphicsPythonProductError("pip check failed for the installed product")

        site_packages = next((venv / "lib").glob("python*/site-packages"), None)
        if site_packages is None:
            raise GraphicsPythonProductError("verification venv has no site-packages")
        _verify_relative_elf_rpaths(site_packages)
        profile_root = site_packages / PRODUCT_IMPORT
        forbidden_runtime_tools = (
            profile_root / "bin" / "termin_shaderc",
            profile_root / "bin" / "slangc",
        )
        if any(path.exists() for path in forbidden_runtime_tools) or any(
            profile_root.joinpath("lib").glob("libslang*")
        ):
            raise GraphicsPythonProductError(
                "runtime product unexpectedly contains the shader compiler toolchain"
            )

        showcase = root / "graphics-showcase"
        shutil.copytree(repo_root / "examples" / "graphics-showcase", showcase)
        output = root / "graphics-showcase.png"
        report = root / "graphics-showcase.json"
        showcase_env = clean_env.copy()
        showcase_env["PATH"] = ""
        if _run(
            [
                str(python),
                "-I",
                str(showcase / "main.py"),
                "--headless",
                "--output",
                str(output),
                "--report",
                str(report),
            ],
            cwd=root,
            env=showcase_env,
        ) != 0:
            raise GraphicsPythonProductError("clean installed graphics showcase failed")
        if not output.is_file() or output.stat().st_size == 0 or not report.is_file():
            raise GraphicsPythonProductError("graphics showcase did not produce its PNG and report")

        window_env = showcase_env.copy()
        window_env["SDL_VIDEODRIVER"] = "offscreen"
        window_env["TERMIN_BACKEND"] = "opengl"
        if _run(
            [
                str(python),
                "-I",
                str(showcase / "main.py"),
                "--windowed",
                "--width",
                "640",
                "--height",
                "480",
                "--frames",
                "1",
            ],
            cwd=root,
            env=window_env,
        ) != 0:
            raise GraphicsPythonProductError("clean installed windowed graphics showcase failed")


def build_product(
    repo_root: Path,
    build_args: list[str],
    *,
    product_root: Path | None = None,
    destination: Path | None = None,
    python_executables: dict[str, Path] | None = None,
    slang_install_root: Path | None = None,
    slang_post_extract_script: Path | None = None,
    public_projection: bool = True,
) -> int:
    variants, forwarded_build_args = _parse_product_build_args(build_args)
    if "--no-sdl" in forwarded_build_args:
        raise GraphicsPythonProductError(
            "the Graphics Python product always includes window support; "
            "--no-sdl is not a supported product option"
        )
    profile = load_sdk_profiles(repo_root).profile("graphics")
    profile_packages = select_python_packages(
        profile, load_manifest(repo_root), repo_root=repo_root
    )
    packages = [
        package
        for package in profile_packages
        if package.distribution not in BUILD_ONLY_DISTRIBUTIONS
    ]
    unsupported = [package.path for package in packages if package.source != "repository"]
    if unsupported:
        raise GraphicsPythonProductError(
            "graphics profile contains non-repository packages: " + ", ".join(unsupported)
        )

    product_root = product_root or repo_root / "build" / "products" / "graphics-python"
    product_root.mkdir(parents=True, exist_ok=True)
    variant_results: list[dict[str, object]] = []
    variant_wheel_dirs: list[tuple[str, Path]] = []
    variant_verifications: list[tuple[Path, Path]] = []
    for variant in variants:
        variant_root = product_root / variant
        sdk_prefix = variant_root / "native-prefix"
        build_dir = variant_root / "cmake-build"
        staging_dir = variant_root / "cmake-install-staging"
        wheel_dir = variant_root / "wheels"
        external_wheels = variant_root / "external-wheels"
        build_environment = variant_root / "python-build-env"
        explicit_python = (
            python_executables.get(variant)
            if python_executables is not None
            else None
        )
        if python_executables is not None and explicit_python is None:
            raise GraphicsPythonProductError(
                f"explicit Graphics Python matrix has no interpreter for {variant}"
            )
        if explicit_python is None:
            build_python = prepare_pinned_python_build_environment(
                repo_root,
                variant=variant,
                environment_root=build_environment,
            )
        else:
            build_python = prepare_python_build_environment(
                repo_root,
                base_python=explicit_python,
                variant=variant,
                environment_root=build_environment,
            )
        prepare_locked_runtime_wheels(
            repo_root,
            build_python,
            wheel_dir=external_wheels,
        )
        try:
            if slang_install_root is None:
                slangc = prepare_slang_toolchain(
                    repo_root,
                    build_python,
                    post_extract_script=slang_post_extract_script,
                )
            else:
                slangc = prepare_slang_toolchain(
                    repo_root,
                    build_python,
                    install_root=slang_install_root,
                    post_extract_script=slang_post_extract_script,
                )
        except SlangToolchainError as error:
            raise GraphicsPythonProductError(str(error)) from error
        env = os.environ.copy()
        env.update(
            {
                "SDK_PREFIX": str(sdk_prefix),
                "BUILD_DIR": str(build_dir),
                "TERMIN_SDK_INSTALL_STAGING_DIR": str(staging_dir),
                "TERMIN_RELOCATABLE_PYTHON_WHEELS": "ON",
                "TERMIN_USE_BUNDLED_SDL2": "ON",
                "TERMIN_PYTHON_ABI": variant,
                "PYTHON_BIN": str(build_python),
                "PYTHON_EXECUTABLE": str(build_python),
                "TERMIN_SLANGC": str(slangc),
            }
        )
        command = [
            str(repo_root / "scripts" / "build" / "bindings.sh"),
            "--profile=graphics",
            "--sdl",
            *forwarded_build_args,
        ]
        if _run(command, cwd=repo_root, env=env) != 0:
            return 1

        bindings_dir = _resolve_bindings_dir(repo_root, build_dir)
        result = build_local_wheel_artifact_set(
            repo_root=repo_root,
            sdk_prefix=sdk_prefix,
            bindings_dir=bindings_dir,
            wheel_dir=wheel_dir,
            build_python=build_python,
            packages=packages,
            run=_run,
            clear_build_caches=_clear_python_package_build_caches,
            bundle_runtime_libraries=False,
            package_version=PRODUCT_VERSION,
        )
        if result != 0:
            return result

        requirements = [
            (artifact.name, artifact.version)
            for artifact in (
                inspect_wheel(path) for path in sorted(wheel_dir.glob("*.whl"))
            )
        ]
        resource_wheel = build_resource_wheel(
            sdk_prefix=sdk_prefix,
            wheel_dir=wheel_dir,
            requirements=requirements,
        )
        wheel_count = len(packages) + 1
        write_local_wheel_manifest(
            wheel_dir,
            sdk_prefix=sdk_prefix,
            expected_wheel_count=wheel_count,
        )
        validate_local_wheel_artifact_set(
            wheel_dir,
            sdk_prefix=sdk_prefix,
            expected_wheel_count=wheel_count,
        )
        native_manifest = ArtifactManifest.load(sdk_prefix / SDK_MANIFEST_NAME)
        actual_abi = native_manifest.python_abi.wheel_abi_tag
        if actual_abi != variant:
            raise GraphicsPythonProductError(
                f"Graphics product variant {variant} produced {actual_abi} native artifacts"
            )
        missing_window_extensions = [
            extension
            for extension in WINDOW_EXTENSIONS
            if not native_manifest.has_extension(extension)
        ]
        if missing_window_extensions:
            raise GraphicsPythonProductError(
                "window-capable Graphics product is missing native extensions: "
                + ", ".join(missing_window_extensions)
            )
        variant_wheel_dirs.append((variant, wheel_dir))
        variant_verifications.append((build_python, external_wheels))
        variant_results.append(
            {
                "id": variant,
                "version": PRODUCT_VERSION,
                "python_abi": native_manifest.python_abi.to_dict(),
                "native_build_id": native_manifest.native_build_id,
                "resource_wheel": resource_wheel.name,
                "wheel_count": wheel_count,
                "wheels": sorted(path.name for path in wheel_dir.glob("*.whl")),
            }
        )

    native_build_ids = {result["native_build_id"] for result in variant_results}
    if len(native_build_ids) != len(variant_results):
        raise GraphicsPythonProductError(
            "Graphics product Python ABI variants unexpectedly share a native_build_id"
        )
    destination = destination or repo_root / "dist" / "graphics-python"
    with tempfile.TemporaryDirectory(
        prefix="graphics-python-publish.",
        dir=product_root,
    ) as temporary_root:
        aggregate = Path(temporary_root) / "wheels"
        if public_projection:
            merged_wheels: list[dict[str, object]] = []
            public_variants: list[dict[str, object]] = []
            for raw_variant, (variant, wheel_dir) in zip(
                variant_results, variant_wheel_dirs, strict=True
            ):
                wheel = compose_product_wheel(
                    sorted(wheel_dir.glob("*.whl")),
                    aggregate,
                    abi=variant,
                    platform_tag="linux_x86_64",
                )
                merged_wheels.append(
                    {
                        "filename": wheel.name,
                        "sha256": _sha256_file(wheel),
                        "python_abis": [variant],
                    }
                )
                public_variants.append(
                    {
                        "id": variant,
                        "version": PRODUCT_VERSION,
                        "python_abi": raw_variant["python_abi"],
                        "native_build_id": raw_variant["native_build_id"],
                        "wheel": wheel.name,
                        "wheel_count": 1,
                    }
                )
            verification_distribution = PRODUCT_DISTRIBUTION
            published_variants = public_variants
            manifest_schema = PRODUCT_MANIFEST_SCHEMA
        else:
            merged_wheels = _merge_variant_wheels(variant_wheel_dirs, aggregate)
            verification_distribution = RESOURCE_DISTRIBUTION
            published_variants = variant_results
            manifest_schema = INTERNAL_PRODUCT_MANIFEST_SCHEMA
        for build_python, external_wheels in variant_verifications:
            verify_product(
                repo_root,
                aggregate,
                build_python,
                external_wheels=external_wheels,
                distribution=verification_distribution,
            )
        _publish(
            aggregate,
            destination,
            {
                "schema": manifest_schema,
                "manifest_kind": PRODUCT_MANIFEST_KIND,
                "product": PRODUCT_DISTRIBUTION,
                "version": PRODUCT_VERSION,
                "profile": "graphics",
                "platform": "linux_x86_64",
                "python_abi_variants": list(variants),
                "projection": "public-monolith" if public_projection else "internal-split",
                "variants": published_variants,
                "shared_wheels": [
                    wheel["filename"]
                    for wheel in merged_wheels
                    if len(wheel["python_abis"]) > 1
                ],
                "wheels": merged_wheels,
                "wheel_count": len(merged_wheels),
            },
        )
    print(f"Graphics Python product published to {destination}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("build_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    build_args = list(args.build_args)
    if build_args[:1] == ["--"]:
        build_args = build_args[1:]
    try:
        return build_product(args.repo_root.resolve(), build_args)
    except (GraphicsPythonProductError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: failed to build Graphics Python product: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
