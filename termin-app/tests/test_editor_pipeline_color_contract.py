from __future__ import annotations

import subprocess
import sys


def test_editor_pipeline_uses_linear_hdr_until_output_transform() -> None:
    script = """
from termin.bootstrap import bootstrap_editor, shutdown_editor

bootstrap_editor()
from termin.editor_core.editor_pipeline import make_editor_pipeline

pipeline = make_editor_pipeline()
tonemap = pipeline.get_pass_by_name("Tonemap").to_python()
assert tonemap.method == 0
output_transform = pipeline.get_pass_by_name("OutputTransform").to_python()
assert output_transform.input_res == "color+widgets"
assert all(spec.format == "rgba16f" for spec in pipeline.pipeline_specs)

del output_transform
del tonemap
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
