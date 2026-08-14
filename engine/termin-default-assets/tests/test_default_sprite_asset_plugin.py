from __future__ import annotations

import json
from pathlib import Path

from termin.render_components import TcSpriteAsset
from termin.default_assets.render.sprite_plugin import (
    create_import_plugin,
    create_runtime_plugin,
)
from termin_assets import AssetCatalog, AssetContext, AssetIdentityPolicy, PreLoadResult


class _ResourceManager:
    def __init__(self) -> None:
        self.external_assets = AssetCatalog()


def _write_sprite(path: Path, *, pixels_per_unit: float = 100.0) -> None:
    path.write_text(
        json.dumps(
            {
                "format": "termin.sprite",
                "version": 1,
                "texture": {"uuid": "texture-uuid"},
                "region": [2, 4, 16, 8],
                "source_size": [64, 32],
                "pivot": [0.25, 0.75],
                "pixels_per_unit": pixels_per_unit,
                "sampling": "nearest",
            }
        ),
        encoding="utf-8",
    )


def test_sprite_runtime_plugin_keeps_handle_stable_across_reload_and_unload(
    tmp_path: Path,
) -> None:
    TcSpriteAsset.clear_registry_for_tests()
    path = tmp_path / "hero.sprite"
    _write_sprite(path)
    uuid = "sprite-uuid"
    manager = _ResourceManager()
    context = AssetContext(resource_manager=manager, name="hero", uuid=uuid)
    result = PreLoadResult(
        resource_type="sprite_asset",
        path=str(path),
        content=None,
        uuid=uuid,
    )
    plugin = create_runtime_plugin()

    plugin.register(context, result)
    first = TcSpriteAsset.from_uuid(uuid)
    assert first.is_valid
    assert first.is_loaded
    first_version = first.version
    assert manager.external_assets.get_by_uuid("sprite_asset", uuid) is not None

    _write_sprite(path, pixels_per_unit=32.0)
    plugin.reload(context, result)
    reloaded = TcSpriteAsset.from_uuid(uuid)
    assert reloaded.is_valid
    assert reloaded.is_loaded
    assert reloaded.version == first_version + 1

    plugin.unregister(context, result)
    unloaded = TcSpriteAsset.from_uuid(uuid)
    assert unloaded.is_valid
    assert not unloaded.is_loaded
    assert manager.external_assets.get_by_uuid("sprite_asset", uuid) is None
    TcSpriteAsset.clear_registry_for_tests()


def test_sprite_import_plugin_uses_sidecar_identity(tmp_path: Path) -> None:
    path = tmp_path / "hero.sprite"
    _write_sprite(path)

    result = create_import_plugin().preload(str(path))

    assert result.resource_type == "sprite_asset"
    assert result.identity_policy is AssetIdentityPolicy.GENERATE_SIDECAR
