from __future__ import annotations

import json
from pathlib import Path

from termin.default_assets.render.pipeline_asset import PipelineAsset, _PipelineCandidate
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

        _write_graph_pipeline(pipeline_path, "pipeline-uuid")
        reload_result = plugin.preload(str(pipeline_path))
        assert reload_result is not None
        assert manager.reload_file(reload_result)

        assert asset.uuid == "pipeline-uuid"
        assert asset.version == 1
        assert asset.cached_data is not initial_pipeline
    finally:
        manager.clear_runtime_state()


def test_pipeline_reload_keeps_live_state_on_failure_and_commits_atomically(
    tmp_path: Path,
    monkeypatch,
) -> None:
    pipeline_path = tmp_path / "post.pipeline"
    _write_graph_pipeline(pipeline_path, "pipeline-uuid")
    live_pipeline = object()
    replacement_pipeline = object()
    asset = PipelineAsset(
        data=live_pipeline,
        name="post",
        source_path=pipeline_path,
        uuid="pipeline-uuid",
    )

    pipeline_path.write_text("not json", encoding="utf-8")
    assert not asset.reload()
    assert asset.cached_data is live_pipeline
    assert asset.is_loaded
    assert asset.version == 0

    pipeline_path.write_text("valid", encoding="utf-8")
    monkeypatch.setattr(
        asset,
        "_prepare_candidate",
        lambda content: _PipelineCandidate(replacement_pipeline, {"nodes": []}),
    )
    assert asset.reload()
    assert asset.cached_data is replacement_pipeline
    assert asset.graph_data == {"nodes": []}
    assert asset.version == 1
