import json

import pytest

from termin.editor_core.pipeline_editor_model import PipelineEditorController
from termin.editor_core.pipeline_inspector_model import PipelineInspectorController


def test_pipeline_inspector_loads_summary_and_hands_off_to_editor(tmp_path):
    path = tmp_path / "main.pipeline"
    path.write_text(
        json.dumps(
            {
                "nodes": [
                    {"type": "ColorPass", "node_type": "pass", "name": "Color"},
                    {"type": "Present", "node_type": "pass", "name": "Present"},
                ],
                "connections": [],
            }
        ),
        encoding="utf-8",
    )
    editor = PipelineEditorController()
    opened = []
    inspector = PipelineInspectorController(editor, open_editor=lambda: opened.append(True))

    snapshot = inspector.set_target(None, file_path=str(path))
    assert snapshot.available
    assert snapshot.nodes == 2
    assert snapshot.connections == 0
    assert snapshot.path == str(path)
    assert editor.file_path == path

    inspector.edit()
    assert opened == [True]


def test_pipeline_inspector_rejects_edit_without_source():
    inspector = PipelineInspectorController(PipelineEditorController(), open_editor=lambda: None)
    inspector.set_target(None)
    with pytest.raises(ValueError, match="no editable source"):
        inspector.edit()
