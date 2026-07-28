from __future__ import annotations

import subprocess
import sys


def test_editor_pipeline_keeps_tonemap_as_identity() -> None:
    script = """
from termin.bootstrap import bootstrap_editor, shutdown_editor

bootstrap_editor()
from termin.editor_core.editor_pipeline import make_editor_pipeline

pipeline = make_editor_pipeline()
tonemap = pipeline.get_pass_by_name("Tonemap").to_python()
assert tonemap.method == 2

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
