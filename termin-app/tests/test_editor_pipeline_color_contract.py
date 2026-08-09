from __future__ import annotations

import subprocess
import sys


def test_editor_pipeline_uses_linear_hdr_until_output_transform() -> None:
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
output_transform = pipeline.get_pass_by_name("OutputTransform").to_python()
assert output_transform.input_res == "color+widgets"
hover_highlight = pipeline.get_pass_by_name("HoverHighlight").to_python()
assert isinstance(hover_highlight.color, SrgbColor)
assert all(abs(actual - expected) < 1.0e-6 for actual, expected in zip(hover_highlight.color, (0.3, 0.8, 1.0, 1.0), strict=True))
assert all(spec.format == "rgba16f" for spec in pipeline.pipeline_specs)

del output_transform
del hover_highlight
del environment
del tonemap
del ui_widgets
pipeline.destroy()
del pipeline
shutdown_editor()
"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
