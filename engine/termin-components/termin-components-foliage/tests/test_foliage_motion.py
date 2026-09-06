from __future__ import annotations

from termin.foliage import FoliageInstance, FoliageLayerComponent, TcFoliageData
from termin.scene import TcScene
from termin.bootstrap import bootstrap_player, shutdown_runtime


def test_bulk_instances_initialize_unsaved_asset_and_reject_invalid_replacement(tmp_path):
    path = tmp_path / "new.tfoliage"
    handle = TcFoliageData.declare("foliage-bulk-motion-test", "bulk", str(path))
    instance = FoliageInstance()
    instance.px = 2.0
    instance.scale = 0.65
    instance.seed = 13
    assert handle.set_instances([instance])
    assert handle.is_loaded
    assert handle.instance_count == 1
    version = handle.version
    invalid = FoliageInstance()
    invalid.px = float("nan")
    assert not handle.set_instances([invalid])
    assert handle.version == version
    assert handle.instances[0].px == 2.0
    assert handle.save()
    assert handle.reload()
    assert abs(handle.instances[0].scale - 0.65) < 1e-6
    assert handle.instances[0].seed == 13


def test_motion_controls_survive_scene_roundtrip():
    bootstrap_player()
    source = TcScene.create("foliage-motion-source")
    restored = TcScene.create("foliage-motion-restored")
    try:
        entity = source.create_entity("moving foliage")
        layer = FoliageLayerComponent()
        layer.motion_time = -12.5
        layer.prototype_height = 0.7
        layer.wind_strength = 0.2
        layer.wind_speed = 1.8
        layer.wind_wavelength = 6.0
        layer.wind_direction_degrees = 37.0
        layer.interaction_x = 4.0
        layer.interaction_y = -2.0
        layer.interaction_z = 0.5
        layer.interaction_radius = 1.4
        layer.interaction_strength = 0.35
        entity.add_component(layer)
        assert restored.load_from_data(source.serialize()) > 0
        copied = restored.get_entity(entity.uuid).get_component(FoliageLayerComponent)
        assert copied.motion_time == -12.5
        assert copied.prototype_height == 0.7
        assert copied.wind_strength == 0.2
        assert copied.wind_speed == 1.8
        assert copied.wind_wavelength == 6.0
        assert copied.wind_direction_degrees == 37.0
        assert copied.interaction_x == 4.0
        assert copied.interaction_y == -2.0
        assert copied.interaction_z == 0.5
        assert copied.interaction_radius == 1.4
        assert copied.interaction_strength == 0.35
    finally:
        restored.destroy()
        source.destroy()
        shutdown_runtime()
