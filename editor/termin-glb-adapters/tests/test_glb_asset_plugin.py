from pathlib import Path

from termin_assets import AssetContext, AssetRuntimeManager, PreLoadResult
from termin.glb_adapters import asset as glb_asset_module
from termin.glb_adapters.asset import GLBAsset
from termin.glb_adapters.asset_plugin import GLBImportPlugin, GLBRuntimePlugin


def test_glb_asset_stage_logs_begin_and_end(monkeypatch):
    messages = []
    monkeypatch.setattr(glb_asset_module.log, "info", messages.append)
    asset = GLBAsset(name="robot", source_path="/tmp/robot.glb")

    with asset._load_stage("publish-mesh", child="Body"):
        pass

    assert "[GLBAsset] stage-begin stage=publish-mesh child='Body'" in messages[0]
    assert "[GLBAsset] stage-end stage=publish-mesh child='Body'" in messages[1]
    assert "duration_ms=" in messages[1]
    assert "thread=" in messages[1]


def test_glb_import_plugin_preloads_meta_uuid(tmp_path):
    path = tmp_path / "robot.glb"
    path.write_bytes(b"glb")
    path.with_name(path.name + ".meta").write_text('{"uuid": "glb-test-uuid"}', encoding="utf-8")

    result = GLBImportPlugin().preload(str(path))

    assert result is not None
    assert result.resource_type == "glb"
    assert result.path == str(path)
    assert result.content is None
    assert result.uuid == "glb-test-uuid"
    assert result.spec_data == {"uuid": "glb-test-uuid"}


def test_glb_runtime_plugin_registers_through_resource_manager_api():
    rm = AssetRuntimeManager()
    result = PreLoadResult(
        resource_type="glb",
        path="/tmp/robot.glb",
        content=None,
        uuid="glb-test-uuid",
        spec_data={"uuid": "glb-test-uuid"},
    )
    context = AssetContext(resource_manager=rm, name="robot", uuid="glb-test-uuid")

    GLBRuntimePlugin().register(context, result)

    asset = rm.get_runtime_asset("glb", "robot")
    assert isinstance(asset, GLBAsset)
    assert asset.uuid == "glb-test-uuid"
    assert asset.source_path == Path("/tmp/robot.glb")
    assert rm.get_runtime_asset_by_uuid("glb", "glb-test-uuid") is asset
