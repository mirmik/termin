"""Validate runtime package manifests before target packaging."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic


RUNTIME_PACKAGE_SCHEMA_VERSION = 1


def validate_runtime_package(package_dir: str | Path) -> list[RuntimePackageExportDiagnostic]:
    package_root = Path(package_dir).resolve()
    manifest_path = package_root / "manifest.json"
    diagnostics: list[RuntimePackageExportDiagnostic] = []

    manifest = _read_manifest(manifest_path, diagnostics)
    if manifest is None:
        return diagnostics

    _validate_version(manifest, diagnostics)
    _validate_scene(package_root, manifest, diagnostics)
    _validate_resources(package_root, manifest, diagnostics)
    return diagnostics


def _read_manifest(
    manifest_path: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except OSError as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                f"Runtime package manifest cannot be read: {exc}",
            )
        )
        return None
    except json.JSONDecodeError as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                f"Runtime package manifest is not valid JSON: {exc}",
            )
        )
        return None

    if not isinstance(data, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                "Runtime package manifest root must be a JSON object",
            )
        )
        return None
    return data


def _validate_version(
    manifest: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    value = manifest.get("version")
    if value is None:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                f"Runtime package manifest must contain integer field 'version' with value {RUNTIME_PACKAGE_SCHEMA_VERSION}",
            )
        )
        return
    if not isinstance(value, int):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                "Runtime package manifest field 'version' must be an integer",
            )
        )
        return
    if value != RUNTIME_PACKAGE_SCHEMA_VERSION:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                f"Unsupported runtime package schema version {value}; supported version is {RUNTIME_PACKAGE_SCHEMA_VERSION}",
            )
        )


def _validate_scene(
    package_root: Path,
    manifest: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    scene = manifest.get("scene")
    if not isinstance(scene, str) or scene == "":
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                "Runtime package manifest must contain non-empty string field 'scene'",
            )
        )
        return

    scene_path = _validate_relative_existing_path(package_root, scene, "scene", diagnostics)
    if scene_path is not None and scene_path.suffix.lower() != ".json":
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "warning",
                scene,
                "Runtime package scene path does not use .json extension",
            )
        )


def _validate_resources(
    package_root: Path,
    manifest: dict[str, Any],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> None:
    resources = manifest.get("resources")
    if not isinstance(resources, list):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                "manifest.json",
                "Runtime package manifest field 'resources' must be a list",
            )
        )
        return

    seen_uuids: dict[str, str] = {}
    for index, resource in enumerate(resources):
        context = f"resources[{index}]"
        if not isinstance(resource, dict):
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    "Runtime package resource entry must be a JSON object",
                )
            )
            continue

        path = resource.get("path")
        if not isinstance(path, str) or path == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    "Runtime package resource entry must contain non-empty string field 'path'",
                )
            )
        else:
            _validate_relative_existing_path(package_root, path, context, diagnostics)

        uuid = resource.get("uuid")
        if uuid is None:
            continue
        if not isinstance(uuid, str) or uuid == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    "Runtime package resource field 'uuid' must be a non-empty string when present",
                )
            )
            continue

        previous_context = seen_uuids.get(uuid)
        if previous_context is not None:
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    context,
                    f"Duplicate runtime package resource uuid '{uuid}' also declared at {previous_context}",
                )
            )
        else:
            seen_uuids[uuid] = context


def _validate_relative_existing_path(
    package_root: Path,
    relative_path: str,
    context: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> Path | None:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                f"Runtime package path must be relative: {relative_path}",
            )
        )
        return None
    resolved = (package_root / candidate).resolve()
    try:
        resolved.relative_to(package_root)
    except ValueError:
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                context,
                f"Runtime package path escapes package root: {relative_path}",
            )
        )
        return None
    if not resolved.exists():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                relative_path,
                f"Runtime package path does not exist: {relative_path}",
            )
        )
        return None
    return resolved

