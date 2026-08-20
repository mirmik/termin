"""Desktop project build wrapper."""

from __future__ import annotations

from collections.abc import Iterable
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from termin.project.settings import ProjectSettings
from termin.project.world_controller_selection import ProjectWorldControllerSelection
from termin.project_build.build_context import BuildContext, create_build_context
from termin.project_build.capabilities import load_sdk_capabilities
from termin.project_build.common import initialize_project_build_player_runtime_state
from termin.project_build.diagnostics import BuildDiagnostic, DiagnosticLike, build_error
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
from termin.project_build.project_module_packager import (
    ProjectModuleBundleResult,
    package_project_modules,
)
from termin.project_build.runtime_package_exporter import RuntimePackageExportResult
from termin.project_build.runtime_package_resource_validator import (
    SceneComponentFactoryPolicy,
)
from termin.project_build.runtime_package_validator import validate_runtime_package
from termin.project_build.target_preflight import DesktopPreflightResult, preflight_desktop_build


DESKTOP_PLAYER_PYTHON_COMPONENT_OWNERS = frozenset(
    {
        "termin-builtin-python",
        "termin-scene-python",
    }
)


@dataclass
class DesktopBuildResult:
    dist_dir: Path
    package_result: RuntimePackageExportResult
    module_result: ProjectModuleBundleResult
    runtime_result: DesktopRuntimeBundleResult
    app_manifest_path: Path
    diagnostics: list[DiagnosticLike] = field(default_factory=list)


@dataclass
class _DesktopTargetPackagePayload:
    module_result: ProjectModuleBundleResult
    runtime_result: DesktopRuntimeBundleResult
    app_manifest_path: Path


def build_desktop_project(
    project_root: str | Path,
    entry_scene: str | Path,
    scenes: Iterable[str | Path] | None = None,
    output_dir: str | Path | None = None,
    shader_compiler: str | Path | None = None,
    fxc: str | Path | None = None,
    default_shader_language: str = "slang",
    shader_targets: Iterable[str] | None = None,
    sdk_root: str | Path | None = None,
    target_os: str | None = None,
    target_arch: str | None = None,
    configuration: str = "dev",
    resource_policy: str = "strict",
    python_package_policy: str = MINIMAL_PYTHON_PACKAGE_POLICY,
    python_requirements: Iterable[str] | None = None,
    modules: Iterable[str] | None = None,
) -> DesktopBuildResult:
    selected_modules = tuple(modules or ())
    sdk_capabilities = load_sdk_capabilities(sdk_root=sdk_root)
    resolved_target_os = target_os or sdk_capabilities.desktop.os
    resolved_target_arch = target_arch or sdk_capabilities.desktop.arch
    runtime_backends = tuple(shader_targets) if shader_targets is not None else (
        ("d3d11",) if resolved_target_os == "windows" else ("vulkan", "opengl")
    )
    context = create_build_context(
        project_root=project_root,
        entry_scene=entry_scene,
        scenes=scenes,
        target="desktop",
        output_dir=output_dir,
        configuration=configuration,
        resource_policy=resource_policy,
        target_options={
            "desktop": {
                "os": resolved_target_os,
                "arch": resolved_target_arch,
            }
        },
    )
    module_preparation = _DesktopModuleClosurePreparation(context, selected_modules)
    pipeline_result = run_project_build_pipeline(
        context=context,
        target_name="Desktop",
        preload_log_tag="[DesktopBuild]",
        prepare_output=lambda build_context: _prepare_dist_dir(
            build_context.project_root,
            build_context.dist_dir,
        ),
        run_target_preflight=lambda: _desktop_target_preflight(
            sdk_root,
            resolved_target_os,
            resolved_target_arch,
        ),
        package_target=lambda build_context, package_result, preflight_result: _package_desktop_target(
            build_context,
            package_result,
            preflight_result,
            python_package_policy,
            tuple(python_requirements or ()),
            module_preparation.require_result(),
        ),
        shader_compiler=shader_compiler,
        fxc=fxc,
        default_shader_language=default_shader_language,
        shader_targets=runtime_backends,
        target_platform=(resolved_target_os, resolved_target_arch),
        validate_package=module_preparation.validate_package,
        initialize_runtime_state=initialize_project_build_player_runtime_state,
    )
    target_payload = pipeline_result.target_package_result.payload

    return DesktopBuildResult(
        dist_dir=context.dist_dir,
        package_result=pipeline_result.package_result,
        module_result=target_payload.module_result,
        runtime_result=target_payload.runtime_result,
        app_manifest_path=target_payload.app_manifest_path,
        diagnostics=pipeline_result.diagnostics,
    )


def _desktop_target_preflight(
    sdk_root: str | Path | None,
    target_os: str | None,
    target_arch: str | None,
) -> TargetPreflightStepResult[DesktopPreflightResult]:
    preflight_result = preflight_desktop_build(
        sdk_root=sdk_root,
        target_os=target_os,
        target_arch=target_arch,
    )
    return TargetPreflightStepResult(
        payload=preflight_result,
        diagnostics=preflight_result.diagnostics,
    )


def _package_desktop_target(
    context: BuildContext,
    package_result: RuntimePackageExportResult,
    preflight_result: DesktopPreflightResult,
    python_package_policy: str,
    python_requirements: tuple[str, ...],
    module_result: ProjectModuleBundleResult,
) -> TargetPackageStepResult[_DesktopTargetPackagePayload]:
    resolved_python_requirements = list(dict.fromkeys((
        *python_requirements,
        *module_result.requirements,
    )))
    runtime_result = package_desktop_runtime(
        dist_dir=context.dist_dir,
        requirements=resolved_python_requirements,
        app_name=context.project_name,
        sdk_root=preflight_result.sdk_root,
        requirement_search_paths=_project_requirement_search_paths(context.project_root),
        python_package_policy=python_package_policy,
    )
    app_manifest_path = context.dist_dir / "app.json"
    module_descriptors = [f"package/modules/{module.descriptor}" for module in module_result.modules]
    project_settings = _load_project_settings(context.project_root)
    desktop_options = context.target_options["desktop"]
    if not isinstance(desktop_options, dict):
        raise TypeError("Desktop build target options must be an object")
    target_os = desktop_options.get("os") or preflight_result.capabilities.desktop.os
    target_arch = desktop_options.get("arch") or preflight_result.capabilities.desktop.arch
    runtime_backends = package_result.runtime_backends
    entry_scene_identity = context.entry_scene.relative_to(context.project_root).as_posix()
    packaged_scenes = [
        {
            "identity": identity,
            "path": f"package/{path.relative_to(package_result.package_dir).as_posix()}",
        }
        for identity, path in package_result.scene_paths.items()
    ]

    _write_app_manifest(
        app_manifest_path,
        {
            "version": 2,
            "format": "termin.desktop_bundle",
            "target": {
                "kind": "desktop",
                "os": target_os,
                "arch": target_arch,
            },
            "project_name": context.project_name,
            "package": {
                "root": "package",
                "manifest": "package/manifest.json",
                "entry_scene": entry_scene_identity,
                "scenes": packaged_scenes,
            },
            "runtime": {
                "backends": list(runtime_backends),
                "launcher": _relative_runtime_path(context.dist_dir, runtime_result.launcher_path),
                "modules": {
                    "enabled": bool(module_result.modules),
                    "root": "package/modules",
                    "manifest": "package/modules/modules.json",
                    "roots": list(module_result.roots),
                    "closure": [module.name for module in module_result.modules],
                    "descriptors": module_descriptors,
                },
                "python": {
                    "enabled": True,
                    "home": _relative_runtime_path(context.dist_dir, runtime_result.python_home),
                    "package_policy": runtime_result.python_package_policy,
                    "runtime_manifest": _relative_runtime_path(
                        context.dist_dir,
                        runtime_result.python_runtime_manifest_path,
                    ),
                },
                "native_library_dirs": _runtime_native_library_dirs(context.dist_dir, runtime_result),
                "window": project_settings.player_window.to_dict(),
                "render_phase_names": list(project_settings.render_phase_names),
                "world_controller": (
                    context.world_controller.to_dict()
                    if context.world_controller is not None
                    else None
                ),
                "mcp": {
                    "enabled": False,
                    "host": "127.0.0.1",
                    "port": 8766,
                    "session_file": "/tmp/termin-player-mcp.json",
                },
            },
            "entry": {
                "scene_identity": entry_scene_identity,
            },
        },
    )

    return TargetPackageStepResult(
        payload=_DesktopTargetPackagePayload(
            module_result=module_result,
            runtime_result=runtime_result,
            app_manifest_path=app_manifest_path,
        ),
        diagnostics=[*runtime_result.diagnostics],
    )


class _DesktopModuleClosurePreparation:
    def __init__(self, context: BuildContext, selected_modules: tuple[str, ...]) -> None:
        self._context = context
        module_roots = list(selected_modules)
        if (
            context.world_controller is not None
            and context.world_controller.module not in module_roots
        ):
            module_roots.append(context.world_controller.module)
        self._selected_modules = tuple(module_roots)
        self._result: ProjectModuleBundleResult | None = None

    def validate_package(self, package_dir: Path) -> list[DiagnosticLike]:
        module_result = package_project_modules(
            project_root=self._context.project_root,
            output_dir=self._context.package_dir / "modules",
            selected_modules=self._selected_modules,
        )
        self._result = module_result
        module_owners = frozenset(module.name for module in module_result.modules)
        preparer = _DesktopRuntimeTypePreparer(
            project_root=self._context.project_root,
            selected_modules=self._selected_modules,
            world_controller=self._context.world_controller,
        )
        diagnostics: list[DiagnosticLike] = [*module_result.diagnostics]
        if (
            self._context.world_controller is not None
            and self._context.world_controller.module not in module_owners
        ):
            diagnostics.append(
                _world_controller_error(
                    f"owner '{self._context.world_controller.module}' is absent from "
                    "the packaged module closure"
                )
            )
        try:
            diagnostics.extend(
                validate_runtime_package(
                    package_dir,
                    component_factory_policy=SceneComponentFactoryPolicy(
                        allowed_kinds=frozenset({"cxx", "python"}),
                        allowed_python_owners=(
                            DESKTOP_PLAYER_PYTHON_COMPONENT_OWNERS | module_owners
                        ),
                    ),
                    prepare_component_factories=preparer.prepare,
                )
            )
        finally:
            cleanup_diagnostic = preparer.close()
            if cleanup_diagnostic is not None:
                diagnostics.append(cleanup_diagnostic)
        return diagnostics

    def require_result(self) -> ProjectModuleBundleResult:
        if self._result is None:
            raise RuntimeError("Desktop module closure was not prepared before target packaging")
        return self._result


class _DesktopRuntimeTypePreparer:
    def __init__(
        self,
        *,
        project_root: Path,
        selected_modules: tuple[str, ...],
        world_controller: ProjectWorldControllerSelection | None,
    ) -> None:
        self._project_root = project_root
        self._selected_modules = selected_modules
        self._world_controller = world_controller
        self._runtime = None

    def prepare(self, _required_types: frozenset[str]):
        if not self._selected_modules:
            return []

        try:
            from termin.project_modules.runtime import ProjectModulesRuntime

            self._runtime = ProjectModulesRuntime(use_project_venv=True)
            if not self._runtime.discover_project(self._project_root):
                return [self._error(self._runtime.last_error)]
            for module_id in self._selected_modules:
                if not self._runtime.load_module(module_id):
                    return [self._error(self._runtime.last_error, module_id)]
            controller_diagnostic = self._validate_world_controller()
            if controller_diagnostic is not None:
                return [controller_diagnostic]
        except Exception as exc:
            return [self._error(str(exc))]
        return []

    def _validate_world_controller(self) -> BuildDiagnostic | None:
        selection = self._world_controller
        if selection is None:
            return None
        from termin.engine._engine_native import _world_controller_type_info

        info = _world_controller_type_info(selection.type_name)
        if info is None:
            return _world_controller_error(
                f"type '{selection.type_name}' was not published by module '{selection.module}'"
            )
        if info["owner"] != selection.module:
            return _world_controller_error(
                f"type '{selection.type_name}' is owned by {info['owner']!r}, not '{selection.module}'"
            )
        if info["abstract"]:
            return _world_controller_error(
                f"type '{selection.type_name}' is abstract and cannot be created"
            )
        return None

    def close(self):
        if self._runtime is None:
            return None
        try:
            if self._runtime.close():
                return None
            return self._error(self._runtime.last_error or "module runtime shutdown failed")
        except Exception as exc:
            return self._error(f"module runtime shutdown raised: {exc}")

    @staticmethod
    def _error(message: str, module_id: str | None = None) -> BuildDiagnostic:
        context = f"modules[{module_id}]" if module_id is not None else "modules"
        return build_error(
            context,
            f"Failed to prepare selected project component factories: {message}",
        )


def _world_controller_error(message: str) -> BuildDiagnostic:
    return build_error(
        "world_controller",
        f"Cannot package selected WorldController: {message}",
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
