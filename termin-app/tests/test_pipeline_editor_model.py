import json
from pathlib import Path

import pytest

from termin.editor_core.pipeline_editor_model import PipelineEditorController


def test_pipeline_editor_controller_load_save_and_signals_are_consistent(tmp_path: Path):
    source = tmp_path / "source.pipeline"
    source.write_text(
        json.dumps(
            {
                "uuid": "pipeline-uuid",
                "nodes": [
                    {"type": "RenderTargetInput", "node_type": "render_target_input"},
                    {"type": "PipelineOutput", "node_type": "pipeline_output"},
                ],
                "connections": [
                    {
                        "from_node": 0,
                        "from_socket": "color",
                        "to_node": 1,
                        "to_socket": "color",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    controller = PipelineEditorController()
    graph_events = []
    status_events = []
    controller.graph_changed.connect(graph_events.append)
    controller.status_changed.connect(status_events.append)

    graph = controller.load(source)

    assert controller.graph is graph
    assert controller.file_path == source
    assert controller.file_uuid == "pipeline-uuid"
    assert graph_events == [graph]
    assert status_events == [f"Loaded: {source}"]

    output = controller.create_node("output", "RenderTarget", 30.0, 40.0)
    assert graph_events[-1] is graph
    assert output.id in graph.nodes
    assert controller.rename_node(output.id, "Final")
    assert output.title == "Final"

    saved = tmp_path / "saved.pipeline"
    assert controller.save(saved) == saved
    payload = json.loads(saved.read_text(encoding="utf-8"))
    assert payload["uuid"] == "pipeline-uuid"
    assert payload["nodes"][-1]["name"] == "Final"
    assert status_events[-1] == f"Saved: {saved}"


def test_pipeline_editor_controller_failed_load_preserves_current_document(tmp_path: Path):
    controller = PipelineEditorController()
    original_graph = controller.graph
    original = tmp_path / "original.pipeline"
    controller.save(original)
    broken = tmp_path / "broken.pipeline"
    broken.write_text('{"uuid": 42, "nodes": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="uuid must be a string"):
        controller.load(broken)

    assert controller.graph is original_graph
    assert controller.file_path == original
    assert controller.file_uuid is None
    assert controller.status == f"Load failed: {broken}"


def test_pipeline_editor_preserves_pass_list_authored_format(tmp_path: Path):
    source = tmp_path / "debug.pipeline"
    source.write_text(
        json.dumps(
            {
                "uuid": "debug-pipeline-uuid",
                "name": "Debug",
                "passes": [
                    {
                        "type": "UIWidgetPass",
                        "pass_name": "UI",
                        "data": {"include_internal_entities": True},
                    }
                ],
                "pipeline_specs": [],
            }
        ),
        encoding="utf-8",
    )
    controller = PipelineEditorController()

    graph = controller.load(source)
    assert controller.source_format == "pass-list"
    assert graph.nodes["node_0"].params["include_internal_entities"] is True

    saved = tmp_path / "saved-debug.pipeline"
    controller.save(saved)
    payload = json.loads(saved.read_text(encoding="utf-8"))
    assert "passes" in payload
    assert "nodes" not in payload
    assert payload["uuid"] == "debug-pipeline-uuid"


def test_pipeline_editor_controller_mutations_emit_only_for_changes():
    controller = PipelineEditorController()
    events = []
    controller.graph_changed.connect(events.append)
    source = controller.create_node("render_target_input", "RenderTargetInput", 0.0, 0.0)
    target = controller.create_node("pipeline_output", "PipelineOutput", 300.0, 0.0)
    edge = controller.graph_controller.connect(source.id, "color", target.id, "color")
    assert edge.ok

    controller.notify_graph_changed()
    event_count = len(events)
    assert not controller.remove_node("missing")
    assert not controller.remove_edge("missing")
    assert len(events) == event_count

    edge_id = next(iter(controller.graph.edges))
    assert controller.remove_edge(edge_id)
    assert len(events) == event_count + 1
    assert controller.remove_node(target.id)
    assert len(events) == event_count + 2
