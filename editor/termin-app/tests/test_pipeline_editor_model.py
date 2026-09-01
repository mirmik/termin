import json
from pathlib import Path

import pytest

from termin.nodegraph.model import Graph
import termin.editor_core.pipeline_editor_model as pipeline_editor_model
from termin.editor_core.pipeline_editor_model import (
    PipelineConnectionValidator,
    PipelineEditorController,
)


def test_pipeline_connection_validator_uses_one_way_xr_assignability():
    validator = PipelineConnectionValidator()
    context = {
        "src_node_id": "source",
        "src_socket": "fbo",
        "dst_node_id": "target",
        "dst_socket": "fbo",
    }

    assert validator.validate(
        "external_xr_multiview_fbo",
        "multiview_fbo",
        **context,
    )
    assert not validator.validate(
        "multiview_fbo",
        "external_xr_multiview_fbo",
        **context,
    )


def test_pipeline_editor_controller_load_save_and_signals_are_consistent(tmp_path: Path):
    source = tmp_path / "source.pipeline"
    source.write_text(
        json.dumps(
            {
                "uuid": "pipeline-uuid",
                "execution_model": "xr_multiview",
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
    assert graph.data["execution_model"] == "xr_multiview"
    assert graph.nodes["node_1"].params["color_content"] == "display_linear"
    assert graph_events == [graph]
    assert status_events == [f"Loaded: {source}"]

    output = controller.create_node("output", "RenderTarget", 30.0, 40.0)
    assert graph_events[-1] is graph
    assert output.id in graph.nodes
    assert controller.rename_node(output.id, "Final")
    assert graph.nodes[output.id].title == "Final"

    saved = tmp_path / "saved.pipeline"
    assert controller.save(saved) == saved
    payload = json.loads(saved.read_text(encoding="utf-8"))
    assert payload["uuid"] == "pipeline-uuid"
    assert payload["execution_model"] == "xr_multiview"
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


@pytest.mark.parametrize(
    ("document_update", "message"),
    [
        ({"nodes": {}}, "nodes must be a list"),
        ({"connections": {}}, "connections must be a list"),
        ({"viewport_frames": {}}, "viewport_frames must be a list"),
        ({"connections": [None]}, "connection 0 must be an object"),
        ({"connections": [{"from_node": True}]}, "from_node must be an integer"),
        (
            {
                "connections": [
                    {
                        "from_node": 0,
                        "from_socket": "color",
                        "to_node": "1",
                        "to_socket": "color",
                    }
                ]
            },
            "to_node must be an integer",
        ),
        (
            {
                "connections": [
                    {
                        "from_node": 2,
                        "from_socket": "color",
                        "to_node": 1,
                        "to_socket": "color",
                    }
                ]
            },
            "from_node is out of range",
        ),
        (
            {
                "connections": [
                    {
                        "from_node": 0,
                        "from_socket": "color",
                        "to_node": -1,
                        "to_socket": "color",
                    }
                ]
            },
            "to_node is out of range",
        ),
        (
            {
                "connections": [
                    {
                        "from_node": 0,
                        "from_socket": "",
                        "to_node": 1,
                        "to_socket": "color",
                    }
                ]
            },
            "from_socket must be a nonempty string",
        ),
        (
            {
                "connections": [
                    {
                        "from_node": 0,
                        "from_socket": "color",
                        "to_node": 1,
                        "to_socket": 7,
                    }
                ]
            },
            "to_socket must be a nonempty string",
        ),
        (
            {
                "connections": [
                    {
                        "from_node": 0,
                        "from_socket": "missing",
                        "to_node": 1,
                        "to_socket": "color",
                    }
                ]
            },
            "connection 0 rejected.*socket not found",
        ),
    ],
)
def test_pipeline_editor_rejects_malformed_graph_connections_atomically(
    tmp_path: Path,
    document_update: dict,
    message: str,
):
    controller = PipelineEditorController()
    previous = tmp_path / "previous.pipeline"
    previous.write_text(
        json.dumps({"uuid": "previous-uuid", "passes": []}),
        encoding="utf-8",
    )
    previous_graph = controller.load(previous)
    previous_graph_controller = controller.graph_controller
    previous_source_format = controller.source_format
    graph_events = []
    controller.graph_changed.connect(graph_events.append)

    document = {
        "uuid": "replacement-uuid",
        "nodes": [
            {"type": "RenderTargetInput", "node_type": "render_target_input"},
            {"type": "PipelineOutput", "node_type": "pipeline_output"},
        ],
        "connections": [],
        "viewport_frames": [],
    }
    document.update(document_update)
    broken = tmp_path / "broken.pipeline"
    broken.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        controller.load(broken)

    assert controller.graph is previous_graph
    assert controller.graph_controller is previous_graph_controller
    assert controller.graph_controller.graph is previous_graph
    assert controller.file_path == previous
    assert controller.file_uuid == "previous-uuid"
    assert controller.source_format == previous_source_format
    assert controller.status == f"Load failed: {broken}"
    assert graph_events == []


def test_pipeline_editor_graph_load_uses_pipeline_connection_validator(tmp_path: Path):
    source = tmp_path / "xr.pipeline"
    source.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "type": "ExternalXrMultiviewFbo",
                        "node_type": "external_xr_multiview_fbo",
                    },
                    {
                        "type": "MultiviewFboSplit",
                        "node_type": "multiview_fbo_split",
                    },
                ],
                "connections": [
                    {
                        "from_node": 0,
                        "from_socket": "fbo",
                        "to_node": 1,
                        "to_socket": "fbo",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    graph = PipelineEditorController().load(source)

    assert len(graph.edges) == 1


def test_pipeline_editor_graph_replacement_preserves_controller_and_validator():
    controller = PipelineEditorController()
    graph_controller = controller.graph_controller
    validator = graph_controller.validator
    replacement = Graph()

    controller.set_graph(replacement)

    assert controller.graph_controller is graph_controller
    assert graph_controller.graph is replacement
    assert graph_controller.validator is validator


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


def test_pipeline_editor_pass_list_save_merges_supported_edits_without_losing_metadata(
    tmp_path: Path,
):
    source = tmp_path / "rich.pipeline"
    original = {
        "uuid": "rich-pipeline-uuid",
        "name": "Rich",
        "execution_model": "xr_multiview",
        "custom_root": {"future": [1, 2, 3]},
        "pipeline_specs": [
            {"resource": "scene", "resource_type": "external", "future_spec": True}
        ],
        "targets": [
            {
                "viewport_name": "main",
                "export_name": "display",
                "color_content": "display_linear",
                "width": 1920,
                "height": 1080,
                "future_target": "preserve",
            }
        ],
        "resource_views": {
            "scene.color": {
                "parent": "scene",
                "attachment": "color",
                "future_view": 9,
            }
        },
        "fbo_compositions": {
            "scene-composed": {
                "color": "scene.color",
                "future_composition": "preserve",
            }
        },
        "passes": [
            {
                "type": "UIWidgetPass",
                "pass_name": "UI",
                "viewport_name": "main",
                "enabled": False,
                "future_pass": {"opaque": True},
                "data": {
                    "include_internal_entities": True,
                    "future_parameter": {"opaque": "value"},
                },
            },
            {
                "type": "UIWidgetPass",
                "pass_name": "Removed",
                "data": {"include_internal_entities": False},
            },
        ],
    }
    source.write_text(json.dumps(original), encoding="utf-8")
    controller = PipelineEditorController()
    graph = controller.load(source)
    ui_node = graph.nodes["node_0"]

    assert controller.rename_node(ui_node.id, "Renamed UI")
    controller.set_param(ui_node, "include_internal_entities", False)
    assert controller.remove_node("node_1")
    added = controller.create_node("pass", "UIWidgetPass", 20.0, 30.0)
    assert controller.rename_node(added.id, "Added UI")
    controller.set_param(added, "include_internal_entities", True)

    saved = tmp_path / "saved-rich.pipeline"
    controller.save(saved)
    payload = json.loads(saved.read_text(encoding="utf-8"))

    for field in (
        "uuid",
        "name",
        "execution_model",
        "custom_root",
        "pipeline_specs",
        "targets",
        "resource_views",
        "fbo_compositions",
    ):
        assert payload[field] == original[field]
    assert len(payload["passes"]) == 2
    preserved = payload["passes"][0]
    assert preserved["pass_name"] == "Renamed UI"
    assert preserved["viewport_name"] == "main"
    assert preserved["enabled"] is False
    assert preserved["future_pass"] == {"opaque": True}
    assert preserved["data"] == {
        "include_internal_entities": False,
        "future_parameter": {"opaque": "value"},
    }
    assert payload["passes"][1]["type"] == "UIWidgetPass"
    assert payload["passes"][1]["pass_name"] == "Added UI"
    assert payload["passes"][1]["data"]["include_internal_entities"] is True
    assert json.loads(source.read_text(encoding="utf-8")) == original

    controller.set_param(ui_node, "include_internal_entities", True)
    controller.save()
    second_payload = json.loads(saved.read_text(encoding="utf-8"))
    assert second_payload["passes"][0]["future_pass"] == {"opaque": True}
    assert second_payload["passes"][0]["data"]["future_parameter"] == {
        "opaque": "value"
    }
    assert second_payload["passes"][0]["data"]["include_internal_entities"] is True


@pytest.mark.parametrize("unsupported", ["edge", "group", "non-pass"])
def test_pipeline_editor_rejects_unsupported_pass_list_graph_before_writing(
    tmp_path: Path,
    unsupported: str,
):
    source = tmp_path / "source.pipeline"
    source.write_text(
        json.dumps(
            {
                "uuid": "pipeline-uuid",
                "passes": [{"type": "UIWidgetPass", "pass_name": "UI", "data": {}}],
            }
        ),
        encoding="utf-8",
    )
    controller = PipelineEditorController()
    controller.load(source)
    if unsupported == "edge":
        source_node = controller.graph.nodes["node_0"]
        target_node = controller.graph_controller.create_node("pass", title="Target")
        controller.graph_controller.add_output_socket(source_node.id, "out")
        controller.graph_controller.add_input_socket(target_node.id, "in")
        assert controller.graph_controller.connect(
            source_node.id, "out", target_node.id, "in", edge_id="edge"
        ).ok
        message = "graph connections"
    elif unsupported == "group":
        controller.graph_controller.add_group("Viewport", 0.0, 0.0, 100.0, 100.0)
        message = "viewport groups"
    else:
        controller.create_node("resource", "FBO", 0.0, 0.0)
        message = "non-pass node"
    before = source.read_bytes()

    with pytest.raises(ValueError, match=message):
        controller.save()

    assert source.read_bytes() == before
    assert controller.status == f"Save failed: {source}"


@pytest.mark.parametrize("failure", ["validation", "write", "reload"])
def test_pipeline_editor_failed_pass_list_save_preserves_original_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
):
    source = tmp_path / "source.pipeline"
    source.write_text(
        json.dumps(
            {
                "uuid": "pipeline-uuid",
                "future_root": "preserve",
                "passes": [
                    {
                        "type": "UIWidgetPass",
                        "pass_name": "UI",
                        "data": {"include_internal_entities": True},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    controller = PipelineEditorController()
    graph = controller.load(source)
    controller.set_param(graph.nodes["node_0"], "include_internal_entities", False)
    before = source.read_bytes()

    if failure == "validation":
        def fail_validation(_data):
            raise ValueError("candidate rejected")

        monkeypatch.setattr(controller, "_validate_save_candidate", fail_validation)
        message = "candidate rejected"
    elif failure == "write":
        def fail_write(_path, _content):
            raise OSError("write rejected")

        monkeypatch.setattr(pipeline_editor_model, "_replace_file_bytes", fail_write)
        message = "write rejected"
    else:
        monkeypatch.setattr(pipeline_editor_model, "reload_pipeline_asset", lambda _path: False)
        message = "reload failed"

    with pytest.raises((OSError, RuntimeError, ValueError), match=message):
        controller.save()

    assert source.read_bytes() == before
    assert controller.file_path == source
    assert controller.status == f"Save failed: {source}"


def test_pipeline_editor_controller_mutations_emit_only_for_changes():
    controller = PipelineEditorController()
    events = []
    controller.graph_changed.connect(events.append)
    source = controller.create_node("render_target_input", "RenderTargetInput", 0.0, 0.0)
    target = controller.create_node("pipeline_output", "PipelineOutput", 300.0, 0.0)
    assert target.params["color_content"] == "display_linear"
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
