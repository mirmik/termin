"""Compose the deterministic Windows Termin Graphics NuGet candidate."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr
import zipfile

from .versioning import public_version


LOCK_RELATIVE_PATH = Path("build-system/graphics-nuget-lock.json")
README_RELATIVE_PATH = Path("termin-csharp/NUGET_README.md")
PRODUCT_MANIFEST = "termin-graphics-nuget-product.json"
PRODUCT_MANIFEST_KIND = "termin-graphics-nuget-product"
PRODUCT_MANIFEST_SCHEMA = 1
PACKAGE_REPOSITORY_URL = "https://github.com/mirmik/termin.git"
PACKAGE_PROJECT_URL = "https://github.com/mirmik/termin"
PACKAGE_AUTHORS = "Termin contributors"
FIXED_ZIP_TIME = (2000, 1, 1, 0, 0, 0)


class GraphicsNugetProductError(RuntimeError):
    """The installed SDK cannot produce the declared NuGet product."""


@dataclass(frozen=True)
class ReleaseLicense:
    name: str
    path: Path


@dataclass(frozen=True)
class GraphicsNugetLock:
    product: str
    platform: str
    runtime_identifier: str
    target_framework: str
    csharp_profile: str
    runtime_package: str
    wpf_package: str
    runtime_assembly: Path
    wpf_assembly: Path
    native_runtime_root: Path
    resource_root: Path
    required_native_libraries: tuple[str, ...]
    forbidden_native_libraries: tuple[str, ...]
    required_resources: tuple[Path, ...]
    release_licenses: tuple[ReleaseLicense, ...]


@dataclass(frozen=True)
class PackageDefinition:
    package_id: str
    description: str
    dependencies: tuple[tuple[str, str], ...]
    payloads: dict[str, bytes]


def _require_object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise GraphicsNugetProductError(f"{context} must be an object")
    return value


def _require_string(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise GraphicsNugetProductError(f"{context} must be a non-empty string")
    return value


def _require_string_tuple(value: object, context: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise GraphicsNugetProductError(f"{context} must be a string array")
    result = tuple(value)
    if len(set(item.casefold() for item in result)) != len(result):
        raise GraphicsNugetProductError(f"{context} contains duplicate names")
    return result


def _relative_path(value: object, context: str) -> Path:
    text = _require_string(value, context)
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise GraphicsNugetProductError(f"{context} must be a safe relative path")
    return Path(*candidate.parts)


def load_lock(repo_root: Path) -> GraphicsNugetLock:
    path = repo_root / LOCK_RELATIVE_PATH
    try:
        root = _require_object(json.loads(path.read_text(encoding="utf-8")), str(path))
    except FileNotFoundError as error:
        raise GraphicsNugetProductError(f"NuGet product lock does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise GraphicsNugetProductError(f"invalid NuGet product lock {path}: {error}") from error
    if root.get("schema") != 1:
        raise GraphicsNugetProductError(
            f"unsupported NuGet product lock schema {root.get('schema')!r}"
        )
    packages = _require_object(root.get("packages"), f"{path}: packages")
    assemblies = _require_object(
        root.get("managed_assemblies"), f"{path}: managed_assemblies"
    )
    raw_licenses = root.get("release_licenses")
    if not isinstance(raw_licenses, list) or not raw_licenses:
        raise GraphicsNugetProductError(f"{path}: release_licenses must be a non-empty array")
    licenses: list[ReleaseLicense] = []
    for index, value in enumerate(raw_licenses):
        context = f"{path}: release_licenses[{index}]"
        entry = _require_object(value, context)
        licenses.append(
            ReleaseLicense(
                name=_require_string(entry.get("name"), f"{context}.name"),
                path=_relative_path(entry.get("path"), f"{context}.path"),
            )
        )
    if len({license.name.casefold() for license in licenses}) != len(licenses):
        raise GraphicsNugetProductError(f"{path}: release license names must be unique")
    required_resources = tuple(
        _relative_path(value, f"{path}: required_resources[{index}]")
        for index, value in enumerate(
            _require_string_tuple(root.get("required_resources"), f"{path}: required_resources")
        )
    )
    lock = GraphicsNugetLock(
        product=_require_string(root.get("product"), f"{path}: product"),
        platform=_require_string(root.get("platform"), f"{path}: platform"),
        runtime_identifier=_require_string(
            root.get("runtime_identifier"), f"{path}: runtime_identifier"
        ),
        target_framework=_require_string(
            root.get("target_framework"), f"{path}: target_framework"
        ),
        csharp_profile=_require_string(
            root.get("csharp_profile"), f"{path}: csharp_profile"
        ),
        runtime_package=_require_string(packages.get("runtime"), f"{path}: packages.runtime"),
        wpf_package=_require_string(packages.get("wpf"), f"{path}: packages.wpf"),
        runtime_assembly=_relative_path(
            assemblies.get("runtime"), f"{path}: managed_assemblies.runtime"
        ),
        wpf_assembly=_relative_path(
            assemblies.get("wpf"), f"{path}: managed_assemblies.wpf"
        ),
        native_runtime_root=_relative_path(
            root.get("native_runtime_root"), f"{path}: native_runtime_root"
        ),
        resource_root=_relative_path(root.get("resource_root"), f"{path}: resource_root"),
        required_native_libraries=_require_string_tuple(
            root.get("required_native_libraries"), f"{path}: required_native_libraries"
        ),
        forbidden_native_libraries=_require_string_tuple(
            root.get("forbidden_native_libraries"), f"{path}: forbidden_native_libraries"
        ),
        required_resources=required_resources,
        release_licenses=tuple(licenses),
    )
    if lock.platform != "windows-x64" or lock.runtime_identifier != "win-x64":
        raise GraphicsNugetProductError(
            "the initial Graphics NuGet contract must be Windows x64 / win-x64"
        )
    if lock.csharp_profile != "plot-d3d11":
        raise GraphicsNugetProductError(
            "the initial Graphics NuGet contract must use the plot-d3d11 profile"
        )
    required_names = {name.casefold() for name in lock.required_native_libraries}
    forbidden_names = {name.casefold() for name in lock.forbidden_native_libraries}
    overlap = sorted(required_names & forbidden_names)
    if overlap:
        raise GraphicsNugetProductError(
            "NuGet product lock lists native libraries as both required and forbidden: "
            + ", ".join(overlap)
        )
    return lock


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_regular_file(path: Path, context: str) -> bytes:
    if path.is_symlink():
        raise GraphicsNugetProductError(f"{context} must not be a symlink: {path}")
    if not path.is_file():
        raise GraphicsNugetProductError(f"{context} does not exist as a regular file: {path}")
    return path.read_bytes()


def _tree_files(root: Path, context: str) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise GraphicsNugetProductError(f"{context} is not a regular directory: {root}")
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise GraphicsNugetProductError(f"{context} contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise GraphicsNugetProductError(f"{context} contains a non-file entry: {path}")
        files.append(path)
    if not files:
        raise GraphicsNugetProductError(f"{context} contains no files: {root}")
    return files


def _collect_sdk_inputs(
    sdk_prefix: Path,
    lock: GraphicsNugetLock,
) -> tuple[dict[str, bytes], dict[str, bytes], list[dict[str, object]]]:
    input_records: list[dict[str, object]] = []

    def read_input(relative: Path, context: str) -> bytes:
        payload = _read_regular_file(sdk_prefix / relative, context)
        input_records.append(
            {
                "path": relative.as_posix(),
                "sha256": _sha256_bytes(payload),
                "size": len(payload),
            }
        )
        return payload

    runtime_payloads = {
        f"lib/{lock.target_framework}/Termin.Native.dll": read_input(
            lock.runtime_assembly, "runtime managed assembly"
        )
    }
    wpf_payloads = {
        f"lib/{lock.target_framework}/Termin.Wpf.dll": read_input(
            lock.wpf_assembly, "WPF managed assembly"
        )
    }

    native_root = sdk_prefix / lock.native_runtime_root
    native_files = _tree_files(native_root, "native runtime")
    nested = [path for path in native_files if len(path.relative_to(native_root).parts) != 1]
    if nested:
        raise GraphicsNugetProductError(
            "native runtime must contain only flat DLL files: "
            + ", ".join(str(path) for path in nested)
        )
    non_dll = [path.name for path in native_files if path.suffix.casefold() != ".dll"]
    if non_dll:
        raise GraphicsNugetProductError(
            "native runtime contains non-DLL files: " + ", ".join(non_dll)
        )
    by_name: dict[str, Path] = {}
    for path in native_files:
        key = path.name.casefold()
        if key in by_name:
            raise GraphicsNugetProductError(
                f"native runtime contains case-insensitive duplicate {path.name}"
            )
        by_name[key] = path
    missing = sorted(
        name for name in lock.required_native_libraries if name.casefold() not in by_name
    )
    forbidden = sorted(
        name for name in lock.forbidden_native_libraries if name.casefold() in by_name
    )
    if missing:
        raise GraphicsNugetProductError(
            "native runtime is missing required libraries: " + ", ".join(missing)
        )
    if forbidden:
        raise GraphicsNugetProductError(
            "native runtime contains libraries from the full C# profile: "
            + ", ".join(forbidden)
        )
    for path in native_files:
        relative = lock.native_runtime_root / path.name
        runtime_payloads[
            f"runtimes/{lock.runtime_identifier}/native/{path.name}"
        ] = read_input(relative, "native runtime library")

    resource_root = sdk_prefix / lock.resource_root
    resource_files = _tree_files(resource_root, "Termin shader resources")
    resource_relatives = {path.relative_to(resource_root).as_posix() for path in resource_files}
    missing_resources = sorted(
        path.as_posix()
        for path in lock.required_resources
        if path.as_posix() not in resource_relatives
    )
    if missing_resources:
        raise GraphicsNugetProductError(
            "shader resource tree is missing required files: "
            + ", ".join(missing_resources)
        )
    for path in resource_files:
        tree_relative = path.relative_to(resource_root)
        sdk_relative = lock.resource_root / tree_relative
        runtime_payloads[f"share/termin/{tree_relative.as_posix()}"] = read_input(
            sdk_relative, "shader resource"
        )
    return runtime_payloads, wpf_payloads, sorted(input_records, key=lambda item: item["path"])


def _license_payloads(
    repo_root: Path,
    lock: GraphicsNugetLock,
) -> tuple[dict[str, bytes], list[dict[str, object]]]:
    payloads: dict[str, bytes] = {}
    records: list[dict[str, object]] = []
    for license in lock.release_licenses:
        source = repo_root / license.path
        payload = _read_regular_file(source, f"release license {license.name}")
        target = f"licenses/{license.name}/{source.name}"
        if target in payloads:
            raise GraphicsNugetProductError(f"release license target collision: {target}")
        payloads[target] = payload
        records.append(
            {
                "name": license.name,
                "source": license.path.as_posix(),
                "package_path": target,
                "sha256": _sha256_bytes(payload),
            }
        )
    return payloads, records


def _targets_payload(package_id: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Project xmlns="http://schemas.microsoft.com/developer/msbuild/2003">\n'
        "  <ItemGroup>\n"
        f'    <_{package_id.replace(".", "")}ShaderResource '
        'Include="$(MSBuildThisFileDirectory)..\\..\\share\\termin\\**\\*" />\n'
        "  </ItemGroup>\n"
        f'  <Target Name="{package_id.replace(".", "")}CopyShaderResources" '
        'AfterTargets="Build">\n'
        "    <Copy\n"
        f'      SourceFiles="@(_{package_id.replace(".", "")}ShaderResource)"\n'
        f'      DestinationFiles="@(_{package_id.replace(".", "")}ShaderResource->'
        "'$(OutDir)share\\termin\\%(RecursiveDir)%(Filename)%(Extension)')\"\n"
        '      SkipUnchangedFiles="true" />\n'
        "  </Target>\n"
        "</Project>\n"
    ).encode("utf-8")


def _nuspec(
    definition: PackageDefinition,
    *,
    version: str,
    target_framework: str,
    source_revision: str,
    license_path: str,
) -> bytes:
    dependencies = ""
    if definition.dependencies:
        dependency_lines = "\n".join(
            "        <dependency id={} version={} include=\"All\" exclude=\"None\" />".format(
                quoteattr(package_id), quoteattr(version_range)
            )
            for package_id, version_range in definition.dependencies
        )
        dependencies = (
            "\n    <dependencies>\n"
            f"      <group targetFramework={quoteattr(target_framework)}>\n"
            f"{dependency_lines}\n"
            "      </group>\n"
            "    </dependencies>"
        )
    else:
        dependencies = (
            "\n    <dependencies>\n"
            f"      <group targetFramework={quoteattr(target_framework)} />\n"
            "    </dependencies>"
        )
    package_id = escape(definition.package_id)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">\n'
        "  <metadata>\n"
        f"    <id>{package_id}</id>\n"
        f"    <version>{escape(version)}</version>\n"
        f"    <title>{package_id}</title>\n"
        f"    <authors>{escape(PACKAGE_AUTHORS)}</authors>\n"
        "    <requireLicenseAcceptance>false</requireLicenseAcceptance>\n"
        f"    <license type=\"file\">{escape(license_path)}</license>\n"
        "    <readme>README.md</readme>\n"
        f"    <projectUrl>{escape(PACKAGE_PROJECT_URL)}</projectUrl>\n"
        f"    <description>{escape(definition.description)}</description>\n"
        "    <tags>termin graphics native d3d11 wpf windows</tags>\n"
        f"    <repository type=\"git\" url={quoteattr(PACKAGE_REPOSITORY_URL)} "
        f"commit={quoteattr(source_revision)} />"
        f"{dependencies}\n"
        "  </metadata>\n"
        "</package>\n"
    ).encode("utf-8")


def _core_properties(definition: PackageDefinition, version: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<coreProperties xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns="http://schemas.openxmlformats.org/package/2006/metadata/core-properties">\n'
        f"  <dc:creator>{escape(PACKAGE_AUTHORS)}</dc:creator>\n"
        f"  <dc:description>{escape(definition.description)}</dc:description>\n"
        f"  <dc:identifier>{escape(definition.package_id)}</dc:identifier>\n"
        f"  <version>{escape(version)}</version>\n"
        "  <keywords>termin graphics native d3d11 wpf windows</keywords>\n"
        "  <lastModifiedBy>termin-build-tools</lastModifiedBy>\n"
        "</coreProperties>\n"
    ).encode("utf-8")


def _relationships(package_id: str, properties_path: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        "  <Relationship "
        'Type="http://schemas.microsoft.com/packaging/2010/07/manifest" '
        f'Target={quoteattr("/" + package_id + ".nuspec")} Id="RManifest" />\n'
        "  <Relationship "
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        f'Target={quoteattr("/" + properties_path)} Id="RProperties" />\n'
        "</Relationships>\n"
    ).encode("utf-8")


def _content_types(names: set[str]) -> bytes:
    extensions = sorted(
        {
            PurePosixPath(name).suffix.removeprefix(".").casefold()
            for name in names
            if PurePosixPath(name).suffix
        }
        - {"rels", "psmdcp"}
    )
    defaults = [
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml" />',
        '  <Default Extension="psmdcp" ContentType="application/vnd.openxmlformats-package.core-properties+xml" />',
    ]
    defaults.extend(
        f"  <Default Extension={quoteattr(extension)} ContentType=\"application/octet\" />"
        for extension in extensions
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        + "\n".join(defaults)
        + "\n</Types>\n"
    ).encode("utf-8")


def _safe_archive_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name
        or "\\" in name
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise GraphicsNugetProductError(f"unsafe NuGet archive path: {name!r}")


def compose_package(
    definition: PackageDefinition,
    destination: Path,
    *,
    version: str,
    target_framework: str,
    source_revision: str,
    license_path: str,
) -> Path:
    package_name = f"{definition.package_id}.{version}.nupkg"
    output = destination / package_name
    properties_id = uuid.uuid5(
        uuid.NAMESPACE_URL, f"{PACKAGE_REPOSITORY_URL}/{definition.package_id}/{version}"
    ).hex
    properties_path = f"package/services/metadata/core-properties/{properties_id}.psmdcp"
    payloads = dict(definition.payloads)
    payloads[f"{definition.package_id}.nuspec"] = _nuspec(
        definition,
        version=version,
        target_framework=target_framework,
        source_revision=source_revision,
        license_path=license_path,
    )
    payloads[properties_path] = _core_properties(definition, version)
    payloads["_rels/.rels"] = _relationships(definition.package_id, properties_path)
    payloads["[Content_Types].xml"] = _content_types(set(payloads))
    for name in payloads:
        _safe_archive_name(name)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(payloads.items()):
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, payload)
    return output


def _archive_records(package: Path) -> list[dict[str, object]]:
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise GraphicsNugetProductError(f"NuGet package has duplicate entries: {package}")
        records: list[dict[str, object]] = []
        for name in names:
            _safe_archive_name(name)
            payload = archive.read(name)
            records.append(
                {
                    "path": name,
                    "sha256": _sha256_bytes(payload),
                    "size": len(payload),
                }
            )
    return sorted(records, key=lambda item: item["path"])


def _validate_nuspec(
    package: Path,
    *,
    package_id: str,
    version: str,
    dependency: tuple[str, str] | None,
) -> None:
    with zipfile.ZipFile(package) as archive:
        archive_names = set(archive.namelist())
        nuspec_name = f"{package_id}.nuspec"
        if nuspec_name not in archive_names:
            raise GraphicsNugetProductError(f"{package.name} has no {nuspec_name}")
        try:
            root = ElementTree.fromstring(archive.read(nuspec_name))
        except ElementTree.ParseError as error:
            raise GraphicsNugetProductError(f"invalid nuspec in {package.name}: {error}") from error
    namespace = {"n": root.tag.partition("}")[0].removeprefix("{")}
    metadata = root.find("n:metadata", namespace)
    if metadata is None:
        raise GraphicsNugetProductError(f"{package.name} nuspec has no metadata")

    def metadata_text(name: str) -> str | None:
        element = metadata.find(f"n:{name}", namespace)
        return element.text if element is not None else None

    if metadata_text("id") != package_id or metadata_text("version") != version:
        raise GraphicsNugetProductError(f"{package.name} nuspec identity mismatch")
    if not metadata_text("description") or not metadata_text("readme"):
        raise GraphicsNugetProductError(f"{package.name} has incomplete public metadata")
    license_element = metadata.find("n:license", namespace)
    if license_element is None or license_element.get("type") != "file":
        raise GraphicsNugetProductError(f"{package.name} has no file license")
    if license_element.text not in archive_names or metadata_text("readme") not in archive_names:
        raise GraphicsNugetProductError(
            f"{package.name} public metadata refers to missing package files"
        )
    dependency_elements = metadata.findall("n:dependencies/n:group/n:dependency", namespace)
    actual_dependencies = [
        (element.get("id"), element.get("version")) for element in dependency_elements
    ]
    expected_dependencies = [dependency] if dependency is not None else []
    if actual_dependencies != expected_dependencies:
        raise GraphicsNugetProductError(
            f"{package.name} dependencies mismatch: {actual_dependencies}"
        )


def _publish_candidate(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.new-{uuid.uuid4().hex}"
    backup = destination.parent / f".{destination.name}.old-{uuid.uuid4().hex}"
    shutil.copytree(source, temporary)
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


def _git_state(repo_root: Path) -> tuple[str, bool]:
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    )
    return revision, dirty


def build_product(
    repo_root: Path,
    sdk_prefix: Path,
    destination: Path,
    *,
    source_revision: str | None = None,
    source_dirty: bool | None = None,
) -> Path:
    repo_root = repo_root.resolve()
    sdk_prefix = sdk_prefix.resolve()
    destination = destination.resolve()
    lock = load_lock(repo_root)
    version = public_version()
    if source_revision is None or source_dirty is None:
        detected_revision, detected_dirty = _git_state(repo_root)
        source_revision = source_revision or detected_revision
        source_dirty = detected_dirty if source_dirty is None else source_dirty
    if not source_revision:
        raise GraphicsNugetProductError("source revision must not be empty")

    runtime_payloads, wpf_payloads, input_records = _collect_sdk_inputs(
        sdk_prefix, lock
    )
    licenses, license_records = _license_payloads(repo_root, lock)
    readme = _read_regular_file(
        repo_root / README_RELATIVE_PATH, "NuGet package README"
    ).replace(b"{{TERMIN_VERSION}}", version.encode("ascii"))
    common_payloads = {**licenses, "README.md": readme}
    runtime_payloads.update(common_payloads)
    wpf_payloads.update(common_payloads)
    runtime_payloads[
        f"buildTransitive/{lock.target_framework}/{lock.runtime_package}.targets"
    ] = _targets_payload(lock.runtime_package)
    termin_license = next(
        record["package_path"]
        for record in license_records
        if record["name"] == "Termin"
    )
    definitions = (
        PackageDefinition(
            package_id=lock.runtime_package,
            description="Windows x64 D3D11 runtime and C# bindings for Termin Graphics.",
            dependencies=(),
            payloads=runtime_payloads,
        ),
        PackageDefinition(
            package_id=lock.wpf_package,
            description="WPF hosts for the Termin Graphics Windows D3D11 runtime.",
            dependencies=((lock.runtime_package, f"[{version}]"),),
            payloads=wpf_payloads,
        ),
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="termin-graphics-nuget.", dir=destination.parent
    ) as temporary:
        candidate = Path(temporary) / "candidate"
        candidate.mkdir()
        package_records: list[dict[str, object]] = []
        for definition in definitions:
            package = compose_package(
                definition,
                candidate,
                version=version,
                target_framework=lock.target_framework,
                source_revision=source_revision,
                license_path=termin_license,
            )
            dependency = definition.dependencies[0] if definition.dependencies else None
            _validate_nuspec(
                package,
                package_id=definition.package_id,
                version=version,
                dependency=dependency,
            )
            package_records.append(
                {
                    "id": definition.package_id,
                    "filename": package.name,
                    "sha256": _sha256_file(package),
                    "size": package.stat().st_size,
                    "dependencies": [
                        {"id": package_id, "version": version_range}
                        for package_id, version_range in definition.dependencies
                    ],
                    "archive_files": _archive_records(package),
                }
            )
        manifest = {
            "schema": PRODUCT_MANIFEST_SCHEMA,
            "manifest_kind": PRODUCT_MANIFEST_KIND,
            "product": lock.product,
            "version": version,
            "platform": lock.platform,
            "runtime_identifier": lock.runtime_identifier,
            "target_framework": lock.target_framework,
            "csharp_profile": lock.csharp_profile,
            "source": {
                "repository": PACKAGE_REPOSITORY_URL,
                "revision": source_revision,
                "dirty": source_dirty,
            },
            "inputs": input_records,
            "release_licenses": license_records,
            "packages": package_records,
            "package_count": len(package_records),
        }
        (candidate / PRODUCT_MANIFEST).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        validate_candidate(repo_root, candidate)
        _publish_candidate(candidate, destination)
    print(f"Termin Graphics NuGet candidate published to {destination}")
    return destination


def validate_candidate(repo_root: Path, candidate: Path) -> dict[str, object]:
    lock = load_lock(repo_root.resolve())
    version = public_version()
    manifest_path = candidate / PRODUCT_MANIFEST
    try:
        manifest = _require_object(
            json.loads(manifest_path.read_text(encoding="utf-8")), str(manifest_path)
        )
    except FileNotFoundError as error:
        raise GraphicsNugetProductError(
            f"NuGet candidate manifest does not exist: {manifest_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise GraphicsNugetProductError(
            f"invalid NuGet candidate manifest {manifest_path}: {error}"
        ) from error
    if manifest.get("schema") != PRODUCT_MANIFEST_SCHEMA:
        raise GraphicsNugetProductError("NuGet candidate manifest schema mismatch")
    if manifest.get("manifest_kind") != PRODUCT_MANIFEST_KIND:
        raise GraphicsNugetProductError("NuGet candidate manifest kind mismatch")
    expected_contract = {
        "product": lock.product,
        "version": version,
        "platform": lock.platform,
        "runtime_identifier": lock.runtime_identifier,
        "target_framework": lock.target_framework,
        "csharp_profile": lock.csharp_profile,
    }
    actual_contract = {name: manifest.get(name) for name in expected_contract}
    if actual_contract != expected_contract:
        raise GraphicsNugetProductError(
            "NuGet candidate product contract mismatch: "
            f"expected={expected_contract}, actual={actual_contract}"
        )
    packages = manifest.get("packages")
    if not isinstance(packages, list) or manifest.get("package_count") != len(packages):
        raise GraphicsNugetProductError("NuGet candidate package count mismatch")
    expected_packages = {
        lock.runtime_package: [],
        lock.wpf_package: [
            {"id": lock.runtime_package, "version": f"[{version}]"}
        ],
    }
    actual_package_ids = [
        _require_string(
            _require_object(package, f"packages[{index}]").get("id"),
            f"packages[{index}].id",
        )
        for index, package in enumerate(packages)
    ]
    if len(packages) != len(expected_packages) or set(actual_package_ids) != set(
        expected_packages
    ):
        raise GraphicsNugetProductError(
            "NuGet candidate package identity set mismatch: "
            f"expected={sorted(expected_packages)}, actual={sorted(actual_package_ids)}"
        )
    expected_names: set[str] = set()
    for index, raw_package in enumerate(packages):
        package = _require_object(raw_package, f"packages[{index}]")
        package_id = _require_string(package.get("id"), f"packages[{index}].id")
        filename = _require_string(package.get("filename"), f"packages[{index}].filename")
        expected_filename = f"{package_id}.{version}.nupkg"
        if PurePosixPath(filename).name != filename or filename != expected_filename:
            raise GraphicsNugetProductError(
                f"unexpected NuGet package filename in manifest: {filename!r}"
            )
        dependencies = package.get("dependencies")
        if dependencies != expected_packages[package_id]:
            raise GraphicsNugetProductError(
                f"NuGet candidate dependency mismatch for {package_id}: {dependencies!r}"
            )
        if filename in expected_names:
            raise GraphicsNugetProductError(f"duplicate package filename in manifest: {filename}")
        expected_names.add(filename)
        path = candidate / filename
        if path.is_symlink() or not path.is_file():
            raise GraphicsNugetProductError(f"manifest-declared package is missing: {path}")
        if package.get("sha256") != _sha256_file(path):
            raise GraphicsNugetProductError(f"NuGet package hash mismatch: {filename}")
        if package.get("archive_files") != _archive_records(path):
            raise GraphicsNugetProductError(
                f"NuGet package archive manifest mismatch: {filename}"
            )
        expected_dependency = (
            (lock.runtime_package, f"[{version}]")
            if package_id == lock.wpf_package
            else None
        )
        _validate_nuspec(
            path,
            package_id=package_id,
            version=version,
            dependency=expected_dependency,
        )
    candidate_entries = [
        path for path in candidate.iterdir() if path.name != PRODUCT_MANIFEST
    ]
    invalid_entries = [
        path.name for path in candidate_entries if path.is_symlink() or not path.is_file()
    ]
    if invalid_entries:
        raise GraphicsNugetProductError(
            "NuGet candidate contains non-file entries: " + ", ".join(invalid_entries)
        )
    actual_names = {path.name for path in candidate_entries}
    if actual_names != expected_names:
        raise GraphicsNugetProductError(
            "NuGet candidate file set mismatch; "
            f"missing={sorted(expected_names - actual_names)}, "
            f"undeclared={sorted(actual_names - expected_names)}"
        )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--sdk-prefix", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_product(args.repo_root, args.sdk_prefix, args.destination)
        return 0
    except (GraphicsNugetProductError, OSError, subprocess.SubprocessError) as error:
        print(f"ERROR: failed to build Termin Graphics NuGet product: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
