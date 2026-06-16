"""Pack project Python modules into a desktop runtime bundle."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from termin.project.settings import ProjectSettings, SERVICE_RESOURCE_IGNORE_PATHS
from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic


@dataclass
class PythonModuleBundle:
    name: str
    descriptor: str
    root: str
    packages: list[str]
    requirements: list[str]
    files: list[str]


@dataclass
class PythonModuleBundleResult:
    root_dir: Path
    manifest_path: Path
    modules: list[PythonModuleBundle] = field(default_factory=list)
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)


def package_python_modules(
    project_root: str | Path,
    output_dir: str | Path,
) -> PythonModuleBundleResult:
    project_root_path = Path(project_root).resolve()
    output_dir_path = Path(output_dir).resolve()
    if output_dir_path.exists():
        shutil.rmtree(output_dir_path)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    diagnostics: list[RuntimePackageExportDiagnostic] = []
    modules: list[PythonModuleBundle] = []
    ignored_roots = _ignored_roots(project_root_path)

    for descriptor in _iter_module_descriptors(project_root_path, ignored_roots):
        module = _package_module_descriptor(
            project_root_path,
            descriptor,
            output_dir_path,
            ignored_roots,
            diagnostics,
        )
        if module is not None:
            modules.append(module)

    modules.sort(key=lambda item: item.descriptor)
    manifest_path = output_dir_path / "modules.json"
    _write_json(
        manifest_path,
        {
            "version": 1,
            "modules": [
                {
                    "name": module.name,
                    "descriptor": module.descriptor,
                    "root": module.root,
                    "packages": module.packages,
                    "requirements": module.requirements,
                    "files": module.files,
                }
                for module in modules
            ],
            "diagnostics": [diagnostic.to_dict() for diagnostic in diagnostics],
        },
    )

    return PythonModuleBundleResult(
        root_dir=output_dir_path,
        manifest_path=manifest_path,
        modules=modules,
        diagnostics=diagnostics,
    )


def _package_module_descriptor(
    project_root: Path,
    descriptor: Path,
    output_dir: Path,
    ignored_roots: tuple[Path, ...],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> PythonModuleBundle | None:
    descriptor_rel = _relative_project_path(project_root, descriptor)
    data = _read_descriptor(project_root, descriptor, diagnostics)
    if data is None:
        return None

    name_value = data.get("name", descriptor.stem)
    name = name_value if isinstance(name_value, str) and name_value != "" else descriptor.stem
    root_text = data.get("root", ".")
    if not isinstance(root_text, str) or root_text == "":
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                descriptor_rel,
                "Python module root must be a non-empty string",
            )
        )
        return None

    packages = _string_list_field(data, "packages", descriptor_rel, diagnostics)
    requirements = _string_list_field(data, "requirements", descriptor_rel, diagnostics)
    root_path = (descriptor.parent / root_text).resolve()
    if not _is_under(root_path, project_root):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                descriptor_rel,
                "Python module root must stay inside the project",
            )
        )
        return None

    descriptor_out = output_dir / descriptor_rel
    _copy_file(descriptor, descriptor_out)

    copied_files = {descriptor_out.relative_to(output_dir).as_posix()}
    output_root = (descriptor_out.parent / root_text).resolve()
    for package in packages:
        for source_path in _collect_python_package_files(
            project_root,
            root_path,
            package,
            descriptor_rel,
            ignored_roots,
            diagnostics,
        ):
            rel_to_root = source_path.relative_to(root_path)
            target_path = output_root / rel_to_root
            _copy_file(source_path, target_path)
            copied_files.add(target_path.relative_to(output_dir).as_posix())

    return PythonModuleBundle(
        name=name,
        descriptor=descriptor_rel,
        root=root_text,
        packages=packages,
        requirements=requirements,
        files=sorted(copied_files),
    )


def _collect_python_package_files(
    project_root: Path,
    root_path: Path,
    package: str,
    descriptor_rel: str,
    ignored_roots: tuple[Path, ...],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> list[Path]:
    package_rel = Path(*package.split("."))
    package_dir = (root_path / package_rel).resolve()
    module_file = package_dir.with_suffix(".py")

    if module_file.exists() and module_file.is_file():
        if _is_ignored_path(module_file, ignored_roots):
            return []
        return [module_file]

    if not package_dir.exists() or not package_dir.is_dir():
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                descriptor_rel,
                f"Python package '{package}' was not found under module root",
            )
        )
        return []

    result: list[Path] = []
    for root_str, dirs, filenames in os.walk(package_dir):
        root = Path(root_str)
        dirs[:] = [
            dirname
            for dirname in dirs
            if _should_enter_dir(root / dirname, ignored_roots)
            and dirname != "__pycache__"
        ]
        for filename in filenames:
            if filename.startswith("."):
                continue
            path = root / filename
            if _is_ignored_path(path, ignored_roots):
                continue
            result.append(path.resolve())
    result.sort()
    return result


def _iter_module_descriptors(project_root: Path, ignored_roots: tuple[Path, ...]) -> list[Path]:
    descriptors: list[Path] = []
    for path in project_root.rglob("*.pymodule"):
        if _is_ignored_path(path, ignored_roots):
            continue
        descriptors.append(path.resolve())
    descriptors.sort()
    return descriptors


def _ignored_roots(project_root: Path) -> tuple[Path, ...]:
    settings = _load_project_settings(project_root)
    ignored: list[Path] = [
        (project_root / ignored_path).resolve()
        for ignored_path in SERVICE_RESOURCE_IGNORE_PATHS
    ]
    ignored.append((project_root / settings.build_output_dir).resolve())
    ignored.extend(
        (project_root / ignored_path).resolve()
        for ignored_path in settings.ignored_resource_paths
    )
    return tuple(ignored)


def _load_project_settings(project_root: Path) -> ProjectSettings:
    settings_path = project_root / "project_settings" / "project.json"
    if not settings_path.exists():
        return ProjectSettings()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return ProjectSettings()
    if not isinstance(data, dict):
        return ProjectSettings()
    return ProjectSettings.from_dict(data)


def _is_ignored_path(path: Path, ignored_roots: tuple[Path, ...]) -> bool:
    resolved = path.resolve()
    if any(resolved == root or root in resolved.parents for root in ignored_roots):
        return True
    return any(part == "__pycache__" for part in resolved.parts)


def _should_enter_dir(path: Path, ignored_roots: tuple[Path, ...]) -> bool:
    name = path.name
    if name.startswith(".") or name.startswith("__"):
        return False
    return not _is_ignored_path(path, ignored_roots)


def _read_descriptor(
    project_root: Path,
    descriptor: Path,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> dict[str, Any] | None:
    descriptor_rel = _relative_project_path(project_root, descriptor)
    try:
        data = json.loads(descriptor.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic("error", descriptor_rel, f"Invalid JSON: {exc}")
        )
        return None
    except Exception as exc:
        diagnostics.append(
            RuntimePackageExportDiagnostic("error", descriptor_rel, f"Failed to read JSON: {exc}")
        )
        return None
    if not isinstance(data, dict):
        diagnostics.append(
            RuntimePackageExportDiagnostic("error", descriptor_rel, "JSON root must be an object")
        )
        return None
    return data


def _string_list_field(
    data: dict[str, Any],
    field_name: str,
    descriptor_rel: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> list[str]:
    value = data.get(field_name, [])
    if not isinstance(value, list):
        diagnostics.append(
            RuntimePackageExportDiagnostic(
                "error",
                descriptor_rel,
                f"Python module {field_name} must be a list",
            )
        )
        return []
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or item == "":
            diagnostics.append(
                RuntimePackageExportDiagnostic(
                    "error",
                    descriptor_rel,
                    f"Python module {field_name} must contain only non-empty strings",
                )
            )
            continue
        result.append(item)
    return result


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _relative_project_path(project_root: Path, path: Path) -> str:
    return path.resolve().relative_to(project_root).as_posix()


def _is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    return resolved == root or root in resolved.parents


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
