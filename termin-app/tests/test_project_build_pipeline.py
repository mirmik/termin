from pathlib import Path

import pytest

from termin.project_build.build_context import create_build_context
from termin.project_build.diagnostics import build_error, build_warning
from termin.project_build.pipeline import (
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
    validation_diagnostic = build_error("manifest.json", "validation error")
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
    ):
        events.append("export")
        assert project_root == context.project_root
        assert entry_scene == context.entry_scene
        assert output_dir == context.package_dir
        assert shader_compiler == tmp_path / "shaderc"
        assert default_shader_language == "slang"
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
