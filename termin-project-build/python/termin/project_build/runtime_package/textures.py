"""Runtime texture asset export."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from termin.project_build.runtime_package.models import RuntimePackageExportDiagnostic
from termin.project_build.runtime_package.package_files import project_relative_path, write_json


SUPPORTED_TEXTURE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tga"}
_IGNORED_PATH_PARTS = {".git", "__pycache__", "build", "dist"}
_IMPORT_SETTING_NAMES = ("flip_x", "flip_y", "transpose")


def write_textures(
    project_root: Path,
    package_dir: Path,
    textures: dict[str, str],
    resources: list[dict[str, str]],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    if not textures:
        return

    texture_sources, rejected_uuids = index_project_texture_sources(project_root, set(textures), diagnostics)
    texture_dir = package_dir / "textures"
    texture_dir.mkdir(parents=True, exist_ok=True)

    for uuid_value, name in sorted(textures.items()):
        source_path = texture_sources.get(uuid_value)
        if source_path is None:
            if uuid_value in rejected_uuids:
                continue
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=f"textures/{uuid_value}.texture.json",
                    message=(
                        "Runtime exporter could not export texture because no project texture source "
                        f"with UUID '{uuid_value}' was found"
                    ),
                )
            )
            continue

        import_settings = read_texture_import_settings(project_root, source_path, diagnostics)
        if import_settings is None:
            continue

        source_rel_path = f"textures/{uuid_value}{source_path.suffix.lower()}"
        source_output_path = package_dir / source_rel_path
        spec_rel_path = f"textures/{uuid_value}.texture.json"
        try:
            shutil.copyfile(source_path, source_output_path)
        except OSError as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, source_path),
                    message=f"Runtime exporter failed to copy texture source: {exc}",
                )
            )
            continue

        write_json(
            package_dir / spec_rel_path,
            {
                "uuid": uuid_value,
                "name": name or uuid_value,
                "source_path": source_rel_path,
                "import_settings": import_settings,
            },
        )
        resources.append(
            {
                "type": "texture",
                "uuid": uuid_value,
                "path": spec_rel_path,
            }
        )


def collect_material_texture_refs(
    material_spec: dict[str, object],
    textures: dict[str, str],
    diagnostics: list[RuntimePackageExportDiagnostic],
    material_path: str,
) -> None:
    values = material_spec.get("textures")
    if values is None:
        return
    if not isinstance(values, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="error",
                path=material_path,
                message="Runtime material textures must be an object",
            )
        )
        return

    for slot_name, value in values.items():
        context = f"{material_path}:textures.{slot_name}"
        if not isinstance(slot_name, str) or slot_name == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=material_path,
                    message="Runtime material texture slot name must be a non-empty string",
                )
            )
            continue
        if not isinstance(value, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=context,
                    message="Runtime material texture reference must be an object",
                )
            )
            continue
        kind = value.get("kind")
        if kind == "builtin":
            continue
        if kind != "asset":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=context,
                    message="Runtime material texture reference kind must be 'asset' or 'builtin'",
                )
            )
            continue
        uuid_value = value.get("uuid")
        if not isinstance(uuid_value, str) or uuid_value == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=context,
                    message="Runtime material asset texture reference must contain a non-empty UUID",
                )
            )
            continue
        name = value.get("name")
        textures[uuid_value] = name if isinstance(name, str) and name != "" else uuid_value


def index_project_texture_sources(
    project_root: Path,
    required_uuids: set[str],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> tuple[dict[str, Path], set[str]]:
    result: dict[str, Path] = {}
    rejected_uuids: set[str] = set()
    for source_path in iter_project_asset_paths(project_root):
        metadata_path = Path(f"{source_path}.meta")
        if not metadata_path.is_file():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=project_relative_path(project_root, metadata_path),
                    message=f"Runtime exporter failed to inspect asset metadata: {exc}",
                )
            )
            continue
        if not isinstance(metadata, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="warning",
                    path=project_relative_path(project_root, metadata_path),
                    message="Runtime exporter skipped asset metadata because JSON root is not an object",
                )
            )
            continue
        uuid_value = metadata.get("uuid")
        if not isinstance(uuid_value, str) or uuid_value not in required_uuids:
            continue
        if source_path.suffix.lower() not in SUPPORTED_TEXTURE_SUFFIXES:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, source_path),
                    message=(
                        "Runtime exporter does not support texture source format "
                        f"'{source_path.suffix.lower()}' for UUID '{uuid_value}'"
                    ),
                )
            )
            rejected_uuids.add(uuid_value)
            continue
        previous = result.get(uuid_value)
        if previous is not None:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, source_path),
                    message=(
                        f"Runtime exporter found duplicate project texture UUID '{uuid_value}' "
                        f"also used by {project_relative_path(project_root, previous)}"
                    ),
                )
            )
            result.pop(uuid_value, None)
            rejected_uuids.add(uuid_value)
            continue
        result[uuid_value] = source_path
    return result, rejected_uuids


def iter_project_asset_paths(project_root: Path):
    for path in sorted(project_root.rglob("*")):
        relative_path = path.relative_to(project_root)
        if any(part in _IGNORED_PATH_PARTS for part in relative_path.parts):
            continue
        if path.is_file() and path.suffix.lower() != ".meta":
            yield path


def read_texture_import_settings(
    project_root: Path,
    source_path: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, bool] | None:
    metadata_path = Path(f"{source_path}.meta")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="error",
                path=project_relative_path(project_root, metadata_path),
                message=f"Runtime exporter failed to read texture import settings: {exc}",
            )
        )
        return None
    if not isinstance(metadata, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                level="error",
                path=project_relative_path(project_root, metadata_path),
                message="Runtime exporter texture metadata root must be an object",
            )
        )
        return None

    defaults = {"flip_x": False, "flip_y": True, "transpose": False}
    settings: dict[str, bool] = {}
    for key in _IMPORT_SETTING_NAMES:
        value = metadata.get(key, defaults[key])
        if not isinstance(value, bool):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    level="error",
                    path=project_relative_path(project_root, metadata_path),
                    message=f"Runtime exporter texture import setting '{key}' must be boolean",
                )
            )
            return None
        settings[key] = value
    return settings
