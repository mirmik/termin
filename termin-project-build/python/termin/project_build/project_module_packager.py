"""Package an explicit mixed Python/C++ project-module closure."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from termin.project.settings import ProjectSettings, SERVICE_RESOURCE_IGNORE_PATHS
from termin.project_build.runtime_package_exporter import RuntimePackageExportDiagnostic
from termin_modules import ModuleKind, ModuleRuntime


@dataclass(frozen=True)
class ProjectModuleBundle:
    name: str
    kind: str
    dependencies: tuple[str, ...]
    descriptor: str
    files: tuple[str, ...]
    requirements: tuple[str, ...] = ()
    packages: tuple[str, ...] = ()
    native_artifact: str | None = None


@dataclass
class ProjectModuleBundleResult:
    root_dir: Path
    manifest_path: Path
    roots: tuple[str, ...]
    modules: list[ProjectModuleBundle] = field(default_factory=list)
    diagnostics: list[RuntimePackageExportDiagnostic] = field(default_factory=list)

    @property
    def requirements(self) -> tuple[str, ...]:
        return tuple(
            requirement
            for module in self.modules
            for requirement in module.requirements
        )


def package_project_modules(
    project_root: str | Path,
    output_dir: str | Path,
    selected_modules: tuple[str, ...] | list[str],
) -> ProjectModuleBundleResult:
    project_root_path = Path(project_root).resolve()
    output_dir_path = Path(output_dir).resolve()
    if output_dir_path.exists():
        shutil.rmtree(output_dir_path)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    roots = tuple(sorted(set(selected_modules)))
    result = ProjectModuleBundleResult(
        root_dir=output_dir_path,
        manifest_path=output_dir_path / "modules.json",
        roots=roots,
    )
    if not roots:
        _write_manifest(result)
        return result

    runtime = ModuleRuntime()
    runtime.set_discovery_ignored_roots([str(path) for path in _ignored_roots(project_root_path)])
    if not runtime.discover(str(project_root_path)):
        result.diagnostics.append(_error("modules", runtime.last_error))
        _write_manifest(result)
        return result

    try:
        closure = runtime.resolve_closure(list(roots))
    except RuntimeError as exc:
        result.diagnostics.append(_error("modules", str(exc)))
        _write_manifest(result)
        return result

    claimed_targets: dict[Path, str] = {}
    for record in closure:
        if record.ignored:
            result.diagnostics.append(
                _error(_descriptor_identity(project_root_path, record.descriptor_path),
                       f"Selected closure contains ignored module '{record.id}'")
            )
            continue
        module = _package_record(
            project_root_path,
            output_dir_path,
            record,
            claimed_targets,
            result.diagnostics,
        )
        if module is not None:
            result.modules.append(module)

    _write_manifest(result)
    return result


def _package_record(
    project_root: Path,
    output_dir: Path,
    record: object,
    claimed_targets: dict[Path, str],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> ProjectModuleBundle | None:
    descriptor_source = Path(record.descriptor_path).resolve()
    descriptor_identity = _descriptor_identity(project_root, descriptor_source)
    if "/" in record.id or "\\" in record.id or record.id in (".", ".."):
        diagnostics.append(
            _error(descriptor_identity, f"Module id '{record.id}' is not safe for packaging")
        )
        return None
    dependencies = tuple(sorted(set(record.dependencies)))
    descriptor_suffix = ".module" if record.kind == ModuleKind.Cpp else ".pymodule"
    descriptor_target = output_dir / "descriptors" / f"{record.id}{descriptor_suffix}"

    if record.kind == ModuleKind.Cpp:
        artifact_source = Path(record.native_artifact_path).resolve()
        if not _is_under(artifact_source, project_root):
            diagnostics.append(
                _error(descriptor_identity,
                       f"Native artifact for module '{record.id}' must stay inside the project")
            )
            return None
        if not artifact_source.is_file():
            diagnostics.append(
                _error(descriptor_identity,
                       f"Native artifact for module '{record.id}' does not exist: {artifact_source}")
            )
            return None
        artifact_target = output_dir / "native" / artifact_source.name
        if not _claim_target(artifact_target, record.id, claimed_targets, diagnostics):
            return None
        _copy_file(artifact_source, artifact_target)
        descriptor_data = {
            "name": record.id,
            "type": "cpp",
            "dependencies": list(dependencies),
            "build": {
                "command": "",
                "clean_command": "",
                "output": f"../native/{artifact_source.name}",
            },
        }
        _write_json(descriptor_target, descriptor_data)
        files = (
            descriptor_target.relative_to(output_dir).as_posix(),
            artifact_target.relative_to(output_dir).as_posix(),
        )
        return ProjectModuleBundle(
            name=record.id,
            kind="cpp",
            dependencies=dependencies,
            descriptor=files[0],
            files=tuple(sorted(files)),
            native_artifact=files[1],
        )

    python_root = Path(record.python_root).resolve()
    if not _is_under(python_root, project_root):
        diagnostics.append(
            _error(descriptor_identity,
                   f"Python root for module '{record.id}' must stay inside the project")
        )
        return None
    packages = tuple(sorted(set(record.python_packages)))
    requirements = tuple(record.python_requirements)
    copied_files = {descriptor_target.relative_to(output_dir).as_posix()}
    for package in packages:
        sources = _collect_python_package_files(
            python_root, package, descriptor_identity, diagnostics
        )
        for source in sources:
            target = output_dir / "python" / source.relative_to(python_root)
            if not _claim_target(target, record.id, claimed_targets, diagnostics):
                continue
            _copy_file(source, target)
            copied_files.add(target.relative_to(output_dir).as_posix())

    descriptor_data = {
        "name": record.id,
        "type": "python",
        "dependencies": list(dependencies),
        "root": "../python",
        "packages": list(packages),
        "requirements": list(requirements),
    }
    _write_json(descriptor_target, descriptor_data)
    return ProjectModuleBundle(
        name=record.id,
        kind="python",
        dependencies=dependencies,
        descriptor=descriptor_target.relative_to(output_dir).as_posix(),
        files=tuple(sorted(copied_files)),
        requirements=requirements,
        packages=packages,
    )


def _collect_python_package_files(
    root: Path,
    package: str,
    descriptor_identity: str,
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> list[Path]:
    package_path = root / Path(*package.split("."))
    module_file = package_path.with_suffix(".py")
    if module_file.is_file():
        return [module_file.resolve()]
    if not package_path.is_dir():
        diagnostics.append(
            _error(descriptor_identity, f"Python package '{package}' was not found under module root")
        )
        return []
    result: list[Path] = []
    for root_text, dirs, filenames in os.walk(package_path):
        current = Path(root_text)
        dirs[:] = sorted(name for name in dirs if not name.startswith(".") and name != "__pycache__")
        for filename in sorted(filenames):
            if not filename.startswith("."):
                result.append((current / filename).resolve())
    return result


def _claim_target(
    target: Path,
    module_id: str,
    claimed_targets: dict[Path, str],
    diagnostics: list[RuntimePackageExportDiagnostic],
) -> bool:
    owner = claimed_targets.get(target)
    if owner is None:
        claimed_targets[target] = module_id
        return True
    if owner == module_id:
        return True
    diagnostics.append(
        _error("modules", f"Packaged file collision between modules '{owner}' and '{module_id}': {target.name}")
    )
    return False


def _ignored_roots(project_root: Path) -> tuple[Path, ...]:
    settings_path = project_root / "project_settings" / "project.json"
    settings = ProjectSettings()
    if settings_path.is_file():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                settings = ProjectSettings.from_dict(data)
        except Exception:
            pass
    roots = [(project_root / path).resolve() for path in SERVICE_RESOURCE_IGNORE_PATHS]
    roots.append((project_root / settings.build_output_dir).resolve())
    roots.extend((project_root / path).resolve() for path in settings.ignored_resource_paths)
    return tuple(roots)


def _descriptor_identity(project_root: Path, descriptor: str | Path) -> str:
    path = Path(descriptor).resolve()
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _error(path: str, message: str) -> RuntimePackageExportDiagnostic:
    return RuntimePackageExportDiagnostic("error", path, message)


def _write_manifest(result: ProjectModuleBundleResult) -> None:
    _write_json(
        result.manifest_path,
        {
            "version": 2,
            "format": "termin.project_modules",
            "roots": list(result.roots),
            "closure": [module.name for module in result.modules],
            "modules": [
                {
                    "name": module.name,
                    "kind": module.kind,
                    "dependencies": list(module.dependencies),
                    "descriptor": module.descriptor,
                    "files": list(module.files),
                    "packages": list(module.packages),
                    "requirements": list(module.requirements),
                    "native_artifact": module.native_artifact,
                }
                for module in result.modules
            ],
            "diagnostics": [diagnostic.to_dict() for diagnostic in result.diagnostics],
        },
    )


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
