"""Shared project build pipeline orchestration."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Generic, TypeVar

from termin.project_build.build_context import BuildContext
from termin.project_build.common import preload_project_resources
from termin.project_build.diagnostics import DiagnosticLike, format_diagnostics
from termin.project_build.runtime_package_exporter import (
    RuntimePackageExportResult,
    export_runtime_package,
)
from termin.project_build.runtime_package_validator import validate_runtime_package
from termin.project_build.target_preflight import (
    ProjectBuildContextPreflightResult,
    preflight_project_build_context,
)


PreflightPayloadT = TypeVar("PreflightPayloadT")
TargetPayloadT = TypeVar("TargetPayloadT")


@dataclass
class TargetPreflightStepResult(Generic[PreflightPayloadT]):
    payload: PreflightPayloadT
    diagnostics: list[DiagnosticLike] = field(default_factory=list)


@dataclass
class TargetPackageStepResult(Generic[TargetPayloadT]):
    payload: TargetPayloadT
    diagnostics: list[DiagnosticLike] = field(default_factory=list)


@dataclass
class ProjectBuildPipelineResult(Generic[PreflightPayloadT, TargetPayloadT]):
    context: BuildContext
    project_preflight_result: ProjectBuildContextPreflightResult
    target_preflight_result: TargetPreflightStepResult[PreflightPayloadT]
    package_result: RuntimePackageExportResult
    package_validation_diagnostics: list[DiagnosticLike]
    target_package_result: TargetPackageStepResult[TargetPayloadT]
    diagnostics: list[DiagnosticLike] = field(default_factory=list)


class ProjectBuildPipelineError(RuntimeError):
    def __init__(
        self,
        target_name: str,
        diagnostics: list[DiagnosticLike],
        *,
        package_result: RuntimePackageExportResult | None = None,
        package_validation_diagnostics: list[DiagnosticLike] | None = None,
    ) -> None:
        self.target_name = target_name
        self.diagnostics = diagnostics
        self.package_result = package_result
        self.package_validation_diagnostics = list(package_validation_diagnostics or [])
        super().__init__(format_diagnostics(f"{target_name} build failed:", diagnostics))


PrepareOutputStep = Callable[[BuildContext], None]
TargetPreflightStep = Callable[[], TargetPreflightStepResult[PreflightPayloadT]]
TargetPackageStep = Callable[
    [BuildContext, RuntimePackageExportResult, PreflightPayloadT],
    TargetPackageStepResult[TargetPayloadT],
]
RuntimePackageExporter = Callable[..., RuntimePackageExportResult]
RuntimePackageValidator = Callable[[Path], list[DiagnosticLike]]


def run_project_build_pipeline(
    context: BuildContext,
    target_name: str,
    preload_log_tag: str,
    prepare_output: PrepareOutputStep,
    run_target_preflight: TargetPreflightStep[PreflightPayloadT],
    package_target: TargetPackageStep[PreflightPayloadT, TargetPayloadT],
    shader_compiler: str | Path | None = None,
    default_shader_language: str = "slang",
    shader_targets: Iterable[str] | None = None,
    export_package: RuntimePackageExporter = export_runtime_package,
    validate_package: RuntimePackageValidator = validate_runtime_package,
) -> ProjectBuildPipelineResult[PreflightPayloadT, TargetPayloadT]:
    project_preflight_result = preflight_project_build_context(
        context=context,
        target_name=target_name,
    )
    target_preflight_result = run_target_preflight()
    prepare_output(context)

    preload_project_resources(context.project_root, preload_log_tag)

    package_result = export_package(
        project_root=context.project_root,
        entry_scene=context.entry_scene,
        output_dir=context.package_dir,
        shader_compiler=shader_compiler,
        default_shader_language=default_shader_language,
        shader_targets=shader_targets,
        resource_policy=context.resource_policy,
    )
    package_validation_diagnostics = validate_package(package_result.package_dir)
    pre_target_diagnostics = [
        *project_preflight_result.diagnostics,
        *target_preflight_result.diagnostics,
        *package_result.diagnostics,
        *package_validation_diagnostics,
    ]
    if _has_error_diagnostic(pre_target_diagnostics):
        raise ProjectBuildPipelineError(
            target_name,
            pre_target_diagnostics,
            package_result=package_result,
            package_validation_diagnostics=package_validation_diagnostics,
        )

    target_package_result = package_target(
        context,
        package_result,
        target_preflight_result.payload,
    )

    return ProjectBuildPipelineResult(
        context=context,
        project_preflight_result=project_preflight_result,
        target_preflight_result=target_preflight_result,
        package_result=package_result,
        package_validation_diagnostics=package_validation_diagnostics,
        target_package_result=target_package_result,
        diagnostics=[
            *pre_target_diagnostics,
            *target_package_result.diagnostics,
        ],
    )


def _has_error_diagnostic(diagnostics: list[DiagnosticLike]) -> bool:
    return any(diagnostic.level == "error" for diagnostic in diagnostics)
