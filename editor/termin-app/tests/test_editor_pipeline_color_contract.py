from __future__ import annotations

import os
import subprocess
import sys


def test_editor_pipeline_publishes_display_linear_color() -> None:
    script = """
from termin.bootstrap import bootstrap_editor, shutdown_editor

bootstrap_editor()
from termin.editor_core.editor_pipeline import make_editor_pipeline
from termin.geombase import SrgbColor

pipeline = make_editor_pipeline()
environment = pipeline.get_pass_by_name("EnvironmentLighting").to_python()
assert environment.output_res == "environment_lighting"
pass_names = [frame_pass.pass_name for frame_pass in pipeline.passes]
assert pass_names.index("EnvironmentLighting") < pass_names.index("Color")
tonemap = pipeline.get_pass_by_name("Tonemap").to_python()
assert tonemap.method == 0
ui_widgets = pipeline.get_pass_by_name("UIWidgets").to_python()
assert ui_widgets.include_scene_entities is False
assert ui_widgets.include_internal_entities is True
assert "OutputTransform" not in pass_names
hover_highlight = pipeline.get_pass_by_name("HoverHighlight").to_python()
assert isinstance(hover_highlight.color, SrgbColor)
assert all(abs(actual - expected) < 1.0e-6 for actual, expected in zip(hover_highlight.color, (0.3, 0.8, 1.0, 1.0), strict=True))
assert all(spec.format == "rgba16f" for spec in pipeline.pipeline_specs)
# All in-place scene-color passes share the initial HDR attachment. Their
# clear declarations must agree with the pipeline's allocation specs.
scene_color_resources = {
    "empty", "skybox", "color_scene", "color_transparent", "color_world2d",
    "color_editor", "color_editor_debug", "color_editor_debug_transparent",
    "color_debug_geometry", "color_immediate_depth", "color",
}
clear_colors = []
for spec in pipeline.pipeline_specs:
    if spec.resource in scene_color_resources and spec.clear_color is not None:
        clear_colors.append(tuple(spec.clear_color))
for name in ("Skybox", "Color", "Transparent", "EditorColor", "EditorDebug", "EditorDebugTransparent"):
    frame_pass = pipeline.get_pass_by_name(name).to_python()
    for spec in frame_pass.get_resource_specs():
        if spec.resource in scene_color_resources and spec.clear_color is not None:
            clear_colors.append(tuple(spec.clear_color))
    del frame_pass
assert clear_colors, "Scene color attachment must have an initialization clear"
assert len(set(clear_colors)) == 1, f"Conflicting aliased scene-color clears: {clear_colors}"
assert pipeline.color_exports == [{"resource": "color+widgets", "viewport_name": "", "color_content": "display_linear"}]

del hover_highlight
del environment
del tonemap
del ui_widgets
pipeline.destroy()
del pipeline
shutdown_editor()
"""
    result = subprocess.run(
        [sys.executable, "--termin-overlay", os.environ["TERMIN_PYTHON_OVERLAY"], "-c", script],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
