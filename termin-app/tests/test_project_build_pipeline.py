from pathlib import Path

import pytest

from termin.project_build.build_context import create_build_context
from termin.project_build.diagnostics import build_error, build_warning
from termin.project_build.pipeline import (
    ProjectBuildPipelineError,
    TargetPackageStepResult,
    TargetPreflightStepResult,
    run_project_build_pipeline,
)
from termin.project_build.runtime_package_exporter import RuntimePackageExportResult
from termin.project_build.target_preflight import TargetPreflightError


def _write_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "PipelineGame"
    project.mkdir()
    (project / "PipelineGame.terminproj").write_text(
        '{"version": 1, "name": "PipelineGame"}\n',
        encoding="utf-8",
    )
    scene = project / "Scenes" / "Main.scene"
    scene.parent.mkdir()
    scene.write_text('{"uuid": "pipeline-scene", "entities": []}\n', encoding="utf-8")
    return project, scene


def test_project_build_pipeline_orders_export_validation_and_target_packaging(tmp_path: Path) -> None:
    project, scene = _write_project(tmp_path)
    context = create_build_context(
        project_root=project,
        entry_scene=scene,
        target="desktop",
        output_dir=project / "dist" / "pipeline",
    )
    events: list[str] = []
    target_preflight_diagnostic = build_warning("target", "target preflight warning")
    export_diagnostic = build_warning("package", "export warning")
    validation_diagnostic = build_warning("manifest.json", "validation warning")
    target_package_diagnostic = build_warning("artifact", "target package warning")

    def prepare_output(_context):
        events.append("prepare")

    def run_target_preflight():
        events.append("target_preflight")
        return TargetPreflightStepResult(
            payload="target-env",
            diagnostics=[target_preflight_diagnostic],
        )

    def export_package(
        project_root,
        entry_scene,
        output_dir,
        shader_compiler,
        default_shader_language,
        shader_targets,
        resource_policy,
    ):
        events.append("export")
        assert project_root == context.project_root
        assert entry_scene == context.entry_scene
        assert output_dir == context.package_dir
        assert shader_compiler == tmp_path / "shaderc"
        assert default_shader_language == "slang"
        assert shader_targets == ("vulkan", "opengl", "d3d11")
        assert resource_policy == "strict"
        output_dir.mkdir(parents=True)
        manifest_path = output_dir / "manifest.json"
        scene_path = output_dir / "scene.json"
        manifest_path.write_text("{}\n", encoding="utf-8")
        scene_path.write_text("{}\n", encoding="utf-8")
        return RuntimePackageExportResult(
            package_dir=output_dir,
            manifest_path=manifest_path,
            scene_path=scene_path,
            diagnostics=[export_diagnostic],
        )

    def validate_package(package_dir):
        events.append("validate")
        assert package_dir == context.package_dir
        return [validation_diagnostic]

    def package_target(package_context, package_result, preflight_payload):
        events.append("package")
        assert package_context is context
        assert package_result.package_dir == context.package_dir
        assert preflight_payload == "target-env"
        return TargetPackageStepResult(
            payload="target-artifact",
            diagnostics=[target_package_diagnostic],
        )

    result = run_project_build_pipeline(
        context=context,
        target_name="Desktop",
        preload_log_tag="[PipelineTest]",
        prepare_output=prepare_output,
        run_target_preflight=run_target_preflight,
        package_target=package_target,
        shader_compiler=tmp_path / "shaderc",
        default_shader_language="slang",
        shader_targets=("vulkan", "opengl", "d3d11"),
        export_package=export_package,
        validate_package=validate_package,
    )

    assert events == ["target_preflight", "prepare", "export", "validate", "package"]
    assert result.target_preflight_result.payload == "target-env"
    assert result.target_package_result.payload == "target-artifact"
    assert result.diagnostics == [
        target_preflight_diagnostic,
        export_diagnostic,
        validation_diagnostic,
        target_package_diagnostic,
    ]


def test_project_build_pipeline_cleans_runtime_state_after_target_packaging(tmp_path: Path) -> None:
    project, scene = _write_project(tmp_path)
    context = create_build_context(
        project_root=project,
        entry_scene=scene,
        target="desktop",
        output_dir=project / "dist" / "pipeline",
    )
    events: list[str] = []

    def export_package(
        project_root,
        entry_scene,
        output_dir,
        shader_compiler,
        default_shader_language,
        shader_targets,
        resource_policy,
    ):
        events.append("export")
        output_dir.mkdir(parents=True)
        manifest_path = output_dir / "manifest.json"
        scene_path = output_dir / "scene.json"
        manifest_path.write_text("{}\n", encoding="utf-8")
        scene_path.write_text("{}\n", encoding="utf-8")
        return RuntimePackageExportResult(
            package_dir=output_dir,
            manifest_path=manifest_path,
            scene_path=scene_path,
        )

    def package_target(_context, _package_result, _payload):
        events.append("package")
        return TargetPackageStepResult(payload="target-artifact")

    run_project_build_pipeline(
        context=context,
        target_name="Desktop",
        preload_log_tag="[PipelineTest]",
        prepare_output=lambda _context: events.append("prepare"),
        run_target_preflight=lambda: TargetPreflightStepResult(payload="target-env"),
        package_target=package_target,
        export_package=export_package,
        validate_package=lambda _package_dir: [],
        cleanup_runtime_state=lambda log_tag: events.append(f"cleanup:{log_tag}"),
    )

    assert events == ["prepare", "export", "package", "cleanup:[PipelineTest]"]


def test_project_build_pipeline_stops_before_output_prepare_when_project_preflight_fails(
    tmp_path: Path,
) -> None:
    project, _scene = _write_project(tmp_path)
    context = create_build_context(
        project_root=project,
        entry_scene="Scenes/Missing.scene",
        target="desktop",
        output_dir=project / "dist" / "pipeline",
    )
    events: list[str] = []

    with pytest.raises(TargetPreflightError, match="Entry scene does not exist"):
        run_project_build_pipeline(
            context=context,
            target_name="Desktop",
            preload_log_tag="[PipelineTest]",
            prepare_output=lambda _context: events.append("prepare"),
            run_target_preflight=lambda: TargetPreflightStepResult(payload=None),
            package_target=lambda _context, _package_result, _payload: TargetPackageStepResult(
                payload=None
            ),
        )

    assert events == []


def test_project_build_pipeline_cleans_runtime_state_when_validation_fails(tmp_path: Path) -> None:
    project, scene = _write_project(tmp_path)
    context = create_build_context(
        project_root=project,
        entry_scene=scene,
        target="desktop",
        output_dir=project / "dist" / "pipeline",
    )
    events: list[str] = []
    validation_diagnostic = build_error("manifest.json", "validation error")

    def export_package(
        project_root,
        entry_scene,
        output_dir,
        shader_compiler,
        default_shader_language,
        shader_targets,
        resource_policy,
    ):
        events.append("export")
        output_dir.mkdir(parents=True)
        manifest_path = output_dir / "manifest.json"
        scene_path = output_dir / "scene.json"
        manifest_path.write_text("{}\n", encoding="utf-8")
        scene_path.write_text("{}\n", encoding="utf-8")
        return RuntimePackageExportResult(
            package_dir=output_dir,
            manifest_path=manifest_path,
            scene_path=scene_path,
        )

    with pytest.raises(ProjectBuildPipelineError):
        run_project_build_pipeline(
            context=context,
            target_name="Desktop",
            preload_log_tag="[PipelineTest]",
            prepare_output=lambda _context: events.append("prepare"),
            run_target_preflight=lambda: TargetPreflightStepResult(payload="target-env"),
            package_target=lambda _context, _package_result, _payload: TargetPackageStepResult(
                payload="target-artifact"
            ),
            export_package=export_package,
            validate_package=lambda _package_dir: [validation_diagnostic],
            cleanup_runtime_state=lambda log_tag: events.append(f"cleanup:{log_tag}"),
        )

    assert events == ["prepare", "export", "cleanup:[PipelineTest]"]


def test_project_build_pipeline_stops_before_target_packaging_when_validation_fails(
    tmp_path: Path,
) -> None:
    project, scene = _write_project(tmp_path)
    context = create_build_context(
        project_root=project,
        entry_scene=scene,
        target="desktop",
        output_dir=project / "dist" / "pipeline",
    )
    events: list[str] = []
    validation_diagnostic = build_error("manifest.json", "validation error")

    def export_package(
        project_root,
        entry_scene,
        output_dir,
        shader_compiler,
        default_shader_language,
        shader_targets,
        resource_policy,
    ):
        events.append("export")
        assert shader_targets is None
        output_dir.mkdir(parents=True)
        manifest_path = output_dir / "manifest.json"
        scene_path = output_dir / "scene.json"
        manifest_path.write_text("{}\n", encoding="utf-8")
        scene_path.write_text("{}\n", encoding="utf-8")
        return RuntimePackageExportResult(
            package_dir=output_dir,
            manifest_path=manifest_path,
            scene_path=scene_path,
        )

    with pytest.raises(ProjectBuildPipelineError) as exc_info:
        run_project_build_pipeline(
            context=context,
            target_name="Desktop",
            preload_log_tag="[PipelineTest]",
            prepare_output=lambda _context: events.append("prepare"),
            run_target_preflight=lambda: TargetPreflightStepResult(payload="target-env"),
            package_target=lambda _context, _package_result, _payload: TargetPackageStepResult(
                payload="target-artifact"
            ),
            export_package=export_package,
            validate_package=lambda _package_dir: [validation_diagnostic],
        )

    assert events == ["prepare", "export"]
    assert exc_info.value.package_result is not None
    assert exc_info.value.diagnostics == [validation_diagnostic]
