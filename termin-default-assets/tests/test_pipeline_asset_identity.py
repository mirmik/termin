from __future__ import annotations

import json
from pathlib import Path

from termin.default_assets.render.pipeline_plugin import PipelineImportPlugin
from termin.default_assets.resource_manager import DefaultResourceManager


def _write_graph_pipeline(path: Path, uuid: str) -> None:
    path.write_text(
        json.dumps({"uuid": uuid, "nodes": [], "connections": []}),
        encoding="utf-8",
    )


def test_pipeline_preload_uses_embedded_uuid_before_lazy_registration(tmp_path: Path) -> None:
    pipeline_path = tmp_path / "post.pipeline"
    _write_graph_pipeline(pipeline_path, "pipeline-uuid")

    result = PipelineImportPlugin().preload(str(pipeline_path))

    assert result is not None
    assert result.uuid == "pipeline-uuid"

    manager = DefaultResourceManager()
    try:
        manager.register_file(result)
        asset = manager.get_pipeline_asset("post")
        assert asset is not None
        assert asset.uuid == "pipeline-uuid"
        assert manager.get_runtime_asset_by_uuid("pipeline", "pipeline-uuid") is asset
        assert not asset.is_loaded
    finally:
        manager.clear_runtime_state()


def test_pipeline_preload_rejects_mismatched_or_missing_identity(tmp_path: Path) -> None:
    pipeline_path = tmp_path / "post.pipeline"
    plugin = PipelineImportPlugin()

    _write_graph_pipeline(pipeline_path, "embedded-uuid")
    pipeline_path.with_suffix(".pipeline.meta").write_text(
        '{"uuid": "sidecar-uuid"}',
        encoding="utf-8",
    )
    assert plugin.preload(str(pipeline_path)) is None

    pipeline_path.with_suffix(".pipeline.meta").unlink()
    pipeline_path.write_text('{"nodes": [], "connections": []}', encoding="utf-8")
    assert plugin.preload(str(pipeline_path)) is None


def test_pipeline_graph_reload_compiles_new_pipeline_with_stable_uuid(tmp_path: Path) -> None:
    pipeline_path = tmp_path / "post.pipeline"
    _write_graph_pipeline(pipeline_path, "pipeline-uuid")
    plugin = PipelineImportPlugin()
    initial_result = plugin.preload(str(pipeline_path))
    assert initial_result is not None

    manager = DefaultResourceManager()
    try:
        manager.register_file(initial_result)
        asset = manager.get_pipeline_asset("post")
        assert asset is not None
        initial_pipeline = asset.pipeline
        assert initial_pipeline is not None
        initial_resource = asset.canonical_resource
        assert initial_resource is not None
        assert initial_resource.uuid == "pipeline-uuid"
        initial_resource_version = initial_resource.version

        _write_graph_pipeline(pipeline_path, "pipeline-uuid")
        reload_result = plugin.preload(str(pipeline_path))
        assert reload_result is not None
        assert manager.reload_file(reload_result)

        assert asset.uuid == "pipeline-uuid"
        assert asset.version == 1
        assert asset.cached_data.uuid == "pipeline-uuid"
        assert asset.cached_data.version > initial_resource_version
        replacement_instance = asset.pipeline
        assert replacement_instance is not initial_pipeline
        assert replacement_instance.pipeline_template.uuid == "pipeline-uuid"
        assert replacement_instance.pipeline_template.version == asset.cached_data.version
        initial_pipeline.destroy()
        replacement_instance.destroy()
    finally:
        manager.clear_runtime_state()


def test_pipeline_reload_keeps_live_resource_on_failure_and_commits_atomically(tmp_path: Path) -> None:
    pipeline_path = tmp_path / "post.pipeline"
    _write_graph_pipeline(pipeline_path, "pipeline-uuid")
    plugin = PipelineImportPlugin()
    result = plugin.preload(str(pipeline_path))
    assert result is not None
    manager = DefaultResourceManager()
    try:
        manager.register_file(result)
        asset = manager.get_pipeline_asset("post")
        assert asset is not None
        assert asset.ensure_loaded()
        resource = asset.cached_data
        live_version = resource.version

        pipeline_path.write_text("not json", encoding="utf-8")
        assert not asset.reload()
        assert asset.cached_data is resource
        assert resource.version == live_version
        assert asset.version == 0

        pipeline_path.write_text(
            json.dumps({"uuid": "pipeline-uuid", "passes": []}),
            encoding="utf-8",
        )
        assert asset.reload()
        assert asset.cached_data is resource
        assert resource.version > live_version
        assert asset.source_format == "pass-list"
        assert asset.version == 1
    finally:
        manager.clear_runtime_state()


def test_pipeline_rejects_mixed_or_unknown_authored_format(tmp_path: Path) -> None:
    pipeline_path = tmp_path / "post.pipeline"
    _write_graph_pipeline(pipeline_path, "pipeline-uuid")
    plugin = PipelineImportPlugin()
    result = plugin.preload(str(pipeline_path))
    assert result is not None
    manager = DefaultResourceManager()
    try:
        manager.register_file(result)
        asset = manager.get_pipeline_asset("post")
        assert asset is not None
        assert asset.ensure_loaded()
        version = asset.cached_data.version

        pipeline_path.write_text(
            json.dumps({"uuid": "pipeline-uuid", "passes": [], "nodes": []}),
            encoding="utf-8",
        )
        assert not asset.reload()
        assert asset.cached_data.version == version

        pipeline_path.write_text(json.dumps({"uuid": "pipeline-uuid"}), encoding="utf-8")
        assert not asset.reload()
        assert asset.cached_data.version == version
    finally:
        manager.clear_runtime_state()


def test_pass_list_resource_instantiates_independent_execution_passes(tmp_path: Path) -> None:
    from termin.bootstrap import bootstrap_player, shutdown_player

    bootstrap_player()
    pipeline_path = tmp_path / "debug.pipeline"
    pipeline_path.write_text(
        json.dumps(
            {
                "uuid": "debug-pipeline-uuid",
                "passes": [
                    {
                        "type": "MissingDebugPass",
                        "pass_name": "debug",
                        "data": {"value": 7},
                    }
                ],
                "pipeline_specs": [],
            }
        ),
        encoding="utf-8",
    )
    plugin = PipelineImportPlugin()
    result = plugin.preload(str(pipeline_path))
    assert result is not None
    manager = DefaultResourceManager()
    try:
        manager.register_file(result)
        asset = manager.get_pipeline_asset("debug")
        assert asset is not None
        first = asset.pipeline
        second = asset.pipeline
        assert first is not None and second is not None
        assert first is not second
        assert first.pass_count == second.pass_count == 1
        assert first.pipeline_template.uuid == "debug-pipeline-uuid"
        assert second.pipeline_template.uuid == "debug-pipeline-uuid"
        first.destroy()
        second.destroy()
    finally:
        manager.clear_runtime_state()
        shutdown_player()


def test_graph_and_its_lowered_pass_list_publish_equivalent_descriptors(tmp_path: Path) -> None:
    from termin.bootstrap import bootstrap_player, shutdown_player
    from termin.render_framework import compile_graph_from_json

    bootstrap_player()
    graph_data = {
        "uuid": "graph-equivalence-uuid",
        "name": "Equivalent",
        "nodes": [
            {"type": "RenderTargetInput", "node_type": "render_target_input", "x": 10, "y": 10},
            {"type": "FBO Split", "node_type": "fbo_split", "x": 160, "y": 10},
            {"type": "FBO Join", "node_type": "fbo_join", "name": "Joined", "x": 310, "y": 10},
            {"type": "PipelineOutput", "node_type": "pipeline_output", "x": 460, "y": 10},
        ],
        "connections": [
            {"from_node": 0, "from_socket": "color", "to_node": 1, "to_socket": "fbo"},
            {"from_node": 1, "from_socket": "color", "to_node": 2, "to_socket": "color"},
            {"from_node": 1, "from_socket": "depth", "to_node": 2, "to_socket": "depth"},
            {"from_node": 2, "from_socket": "fbo", "to_node": 3, "to_socket": "color"},
        ],
        "viewport_frames": [
            {
                "viewport_name": "main",
                "x": 0,
                "y": 0,
                "width": 600,
                "height": 300,
                "target_width": 1920,
                "target_height": 1080,
            }
        ],
    }
    graph_path = tmp_path / "graph.pipeline"
    graph_path.write_text(json.dumps(graph_data), encoding="utf-8")

    lowered_pipeline = compile_graph_from_json(json.dumps(graph_data))
    try:
        pass_list_data = lowered_pipeline.serialize()
    finally:
        lowered_pipeline.destroy()
    pass_list_data["uuid"] = "pass-list-equivalence-uuid"
    pass_list_data["targets"] = [
        {"viewport_name": "main", "export_name": "", "width": 1920, "height": 1080}
    ]
    pass_list_path = tmp_path / "pass-list.pipeline"
    pass_list_path.write_text(json.dumps(pass_list_data), encoding="utf-8")

    plugin = PipelineImportPlugin()
    manager = DefaultResourceManager()
    try:
        for path in (graph_path, pass_list_path):
            result = plugin.preload(str(path))
            assert result is not None
            manager.register_file(result)
        graph_resource = manager.get_pipeline_asset("graph").canonical_resource
        pass_list_resource = manager.get_pipeline_asset("pass-list").canonical_resource
        assert graph_resource.passes == pass_list_resource.passes
        assert graph_resource.resources == pass_list_resource.resources
        def dependency_key(item):
            return item["pass_index"], item["resource"], item["access"]

        assert sorted(map(dependency_key, graph_resource.dependencies)) == sorted(
            map(dependency_key, pass_list_resource.dependencies)
        )
        assert graph_resource.targets == pass_list_resource.targets
        graph_instance = manager.get_pipeline("graph")
        pass_list_instance = manager.get_pipeline("pass-list")
        try:
            graph_recipe = graph_instance.serialize()
            pass_list_recipe = pass_list_instance.serialize()
            assert graph_recipe["resource_views"] == pass_list_recipe["resource_views"]
            assert graph_recipe["fbo_compositions"] == pass_list_recipe["fbo_compositions"]
            assert graph_recipe["fbo_compositions"]["Joined"] == {
                "color": "RT_COLOR.color",
                "depth": "RT_COLOR.depth",
            }
        finally:
            graph_instance.destroy()
            pass_list_instance.destroy()
    finally:
        manager.clear_runtime_state()
        shutdown_player()
