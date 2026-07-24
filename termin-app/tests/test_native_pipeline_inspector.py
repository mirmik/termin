from termin.gui_native import tc_ui_document_create, tc_ui_document_destroy
import gc
import json

from termin.editor_core.pipeline_editor_model import PipelineEditorController
from termin.editor_core.pipeline_inspector_model import PipelineInspectorController
from termin.editor_native.pipeline_inspector import build_native_pipeline_inspector


def test_native_pipeline_inspector_projects_summary(tmp_path):
    path = tmp_path / "main.pipeline"
    path.write_text(json.dumps({"nodes": [], "connections": []}), encoding="utf-8")
    document = tc_ui_document_create()
    renders = []
    inspector = build_native_pipeline_inspector(
        document,
        PipelineInspectorController(PipelineEditorController(), open_editor=lambda: None),
        request_render=lambda: renders.append(True),
    )
    assert document.add_root(inspector.root.handle)

    inspector.set_target(None, file_path=str(path))
    assert "nodes" in inspector.controls
    assert "connections" in inspector.controls
    assert "edit" in inspector.controls
    assert renders

    assert document.destroy_widget_recursive(inspector.root.handle)
    tc_ui_document_destroy(document)
    del inspector, document
    gc.collect()
