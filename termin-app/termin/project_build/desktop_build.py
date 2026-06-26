"""Desktop project build wrapper."""

from __future__ import annotations

from collections.abc import Iterable
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from termin.project.settings import ProjectSettings
from termin.project_build.build_context import BuildContext, create_build_context
from termin.project_build.diagnostics import DiagnosticLike
from termin.project_build.desktop_runtime_packager import (
    DesktopRuntimeBundleResult,
    MINIMAL_PYTHON_PACKAGE_POLICY,
    package_desktop_runtime,
)
from termin.project_build.pipeline import (
    TargetPackageStepResult,
    TargetPreflightStepResult,
    run_project_build_pipeline,
)
from termin.project_build.python_module_packager import PythonModuleBundleResult, package_python_modules
from termin.project_build.runtime_package_exporter import RuntimePackageExportResult
from termin.project_build.target_preflight import DesktopPreflightResult, preflight_desktop_build


@dataclass
class DesktopBuildResult:
    dist_dir: Path
    package_result: RuntimePackageExportResult
    python_result: PythonModuleBundleResult
    runtime_result: DesktopRuntimeBundleResult
    app_manifest_path: Path
    diagnostics: list[DiagnosticLike] = field(default_factory=list)


@dataclass
class _DesktopTargetPackagePayload:
    python_result: PythonModuleBundleResult
    runtime_result: DesktopRuntimeBundleResult
    app_manifest_path: Path


def build_desktop_project(
    project_root: str | Path,
    entry_scene: str | Path,
    output_dir: str | Path | None = None,
    shader_compiler: str | Path | None = None,
    default_shader_language: str = "slang",
    shader_targets: Iterable[str] | None = None,
    sdk_root: str | Path | None = None,
    configuration: str = "dev",
    resource_policy: str = "strict",
    python_package_policy: str = MINIMAL_PYTHON_PACKAGE_POLICY,
    python_requirements: Iterable[str] | None = None,
) -> DesktopBuildResult:
    context = create_build_context(
        project_root=project_root,
        entry_scene=entry_scene,
        target="desktop",
        output_dir=output_dir,
        configuration=configuration,
        resource_policy=resource_policy,
    )
    pipeline_result = run_project_build_pipeline(
        context=context,
        target_name="Desktop",
        preload_log_tag="[DesktopBuild]",
        prepare_output=lambda build_context: _prepare_dist_dir(
            build_context.project_root,
            build_context.dist_dir,
        ),
        run_target_preflight=lambda: _desktop_target_preflight(sdk_root),
        package_target=lambda build_context, package_result, preflight_result: _package_desktop_target(
            build_context,
            package_result,
            preflight_result,
            python_package_policy,
            tuple(python_requirements or ()),
        ),
        shader_compiler=shader_compiler,
        default_shader_language=default_shader_language,
        shader_targets=shader_targets,
    )
    target_payload = pipeline_result.target_package_result.payload

    return DesktopBuildResult(
        dist_dir=context.dist_dir,
        package_result=pipeline_result.package_result,
        python_result=target_payload.python_result,
        runtime_result=target_payload.runtime_result,
        app_manifest_path=target_payload.app_manifest_path,
        diagnostics=pipeline_result.diagnostics,
    )


def _desktop_target_preflight(
    sdk_root: str | Path | None,
) -> TargetPreflightStepResult[DesktopPreflightResult]:
    preflight_result = preflight_desktop_build(sdk_root=sdk_root)
    return TargetPreflightStepResult(
        payload=preflight_result,
        diagnostics=preflight_result.diagnostics,
    )


def _package_desktop_target(
    context: BuildContext,
    _package_result: RuntimePackageExportResult,
    preflight_result: DesktopPreflightResult,
    python_package_policy: str,
    python_requirements: tuple[str, ...],
) -> TargetPackageStepResult[_DesktopTargetPackagePayload]:
    python_result = package_python_modules(
        project_root=context.project_root,
        output_dir=context.package_dir / "python",
    )
    resolved_python_requirements = [
        *python_requirements,
        *[
            requirement
            for module in python_result.modules
            for requirement in module.requirements
        ],
    ]
    runtime_result = package_desktop_runtime(
        dist_dir=context.dist_dir,
        requirements=resolved_python_requirements,
        app_name=context.project_name,
        sdk_root=preflight_result.sdk_root,
        requirement_search_paths=_project_requirement_search_paths(context.project_root),
        python_package_policy=python_package_policy,
    )

    app_manifest_path = context.dist_dir / "app.json"
    python_descriptors = [
        f"package/python/{module.descriptor}"
        for module in python_result.modules
    ]
    project_settings = _load_project_settings(context.project_root)

    _write_app_manifest(
        app_manifest_path,
        {
            "version": 1,
            "format": "termin.desktop_bundle",
            "target": "desktop",
            "project_name": context.project_name,
            "package": {
                "root": "package",
                "manifest": "package/manifest.json",
                "scene": "package/scene.json",
            },
            "runtime": {
                "launcher": _relative_runtime_path(context.dist_dir, runtime_result.launcher_path),
                "python": {
                    "enabled": bool(python_result.modules),
                    "home": _relative_runtime_path(context.dist_dir, runtime_result.python_home),
                    "package_policy": runtime_result.python_package_policy,
                    "runtime_manifest": _relative_runtime_path(
                        context.dist_dir,
                        runtime_result.python_runtime_manifest_path,
                    ),
                    "project_modules": "package/python",
                    "module_manifest": "package/python/modules.json",
                    "descriptors": python_descriptors,
                },
                "native_library_dirs": _runtime_native_library_dirs(context.dist_dir, runtime_result),
                "window": project_settings.player_window.to_dict(),
                "mcp": {
                    "enabled": False,
                    "host": "127.0.0.1",
                    "port": 8766,
                    "session_file": "/tmp/termin-player-mcp.json",
                },
            },
            "entry": {
                "scene": "package/scene.json",
            },
        },
    )

    return TargetPackageStepResult(
        payload=_DesktopTargetPackagePayload(
            python_result=python_result,
            runtime_result=runtime_result,
            app_manifest_path=app_manifest_path,
        ),
        diagnostics=[
            *python_result.diagnostics,
            *runtime_result.diagnostics,
        ],
    )


def _relative_runtime_path(dist_dir: Path, path: Path | None) -> str:
    if path is None:
        return ""
    return path.relative_to(dist_dir).as_posix()


def _runtime_native_library_dirs(
    dist_dir: Path,
    runtime_result: DesktopRuntimeBundleResult,
) -> list[str]:
    result: list[str] = []
    paths = [runtime_result.lib_dir, runtime_result.bin_dir]
    if runtime_result.launcher_path is not None:
        paths.insert(0, runtime_result.launcher_path.parent)
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        if _contains_native_library(path):
            result.append(path.relative_to(dist_dir).as_posix())
    return result or ["lib"]


def _contains_native_library(path: Path) -> bool:
    if not path.is_dir():
        return False
    for child in path.iterdir():
        if not child.is_file():
            continue
        name = child.name.lower()
        if name.endswith(".dll") or name.endswith(".dylib") or ".so" in name:
            return True
    return False


def _project_requirement_search_paths(project_root: Path) -> list[Path]:
    venv = project_root / ".venv"
    candidates = [
        venv / "Lib" / "site-packages",
    ]
    unix_lib = venv / "lib"
    if unix_lib.is_dir():
        candidates.extend(sorted(unix_lib.glob("python*/site-packages")))
    return [
        path
        for path in candidates
        if path.is_dir()
    ]


def _prepare_dist_dir(project_root: Path, dist_dir: Path) -> None:
    if dist_dir == project_root:
        raise ValueError(f"Refusing to use project root as desktop build output: {dist_dir}")
    if project_root in dist_dir.parents:
        rel = dist_dir.relative_to(project_root)
        if rel.parts and rel.parts[0] == "dist":
            _replace_dir(dist_dir)
            return

    if not dist_dir.exists():
        dist_dir.mkdir(parents=True, exist_ok=True)
        return

    if (dist_dir / "app.json").exists() or (dist_dir / "package").exists():
        _replace_dir(dist_dir)
        return

    if any(dist_dir.iterdir()):
        raise ValueError(
            "Refusing to clean non-generated desktop build output directory: "
            f"{dist_dir}. Use a project dist/... path or an empty directory."
        )
    _replace_dir(dist_dir)


def _replace_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _write_app_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _load_project_settings(project_root: Path) -> ProjectSettings:
    settings_path = project_root / "project_settings" / "project.json"
    if not settings_path.exists():
        return ProjectSettings()

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        from tcbase import log

        log.error(f"[DesktopBuild] Failed to read project settings: {exc}")
        return ProjectSettings()

    if not isinstance(data, dict):
        from tcbase import log

        log.error("[DesktopBuild] Project settings root must be an object")
        return ProjectSettings()
    return ProjectSettings.from_dict(data)
