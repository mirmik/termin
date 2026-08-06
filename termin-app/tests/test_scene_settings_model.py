import pytest

from termin.bootstrap import bootstrap_player, shutdown_player
from termin.editor_core.scene_settings_model import (
    SKYBOX_TYPES,
    SceneNamesController,
    SceneNamesSnapshot,
    ScenePropertiesController,
    ShadowSettingsController,
    ShadowSettingsSnapshot,
)
from termin.editor_core.undo_stack import UndoStack
from termin.render import DebugGeometryTypeRegistration, scene_render_state
from termin.scene import TcScene


@pytest.fixture(scope="module", autouse=True)
def _bootstrap():
    bootstrap_player()
    yield
    shutdown_player()


@pytest.fixture
def scene():
    value = TcScene.create("scene-settings-test")
    yield value
    value.destroy()


def test_scene_names_controller_normalizes_and_persists_64_names(scene):
    controller = SceneNamesController(scene)
    layers = [""] * 64
    flags = [""] * 64
    layers[3] = "  Gameplay "
    flags[7] = " Selected "

    saved = controller.save(SceneNamesSnapshot(tuple(layers), tuple(flags)))

    assert saved.layers[3] == "Gameplay"
    assert controller.load().flags[7] == "Selected"
    with pytest.raises(ValueError):
        controller.save(SceneNamesSnapshot(("short",), tuple(flags)))


def test_shadow_settings_controller_validates_applies_and_mirrors(scene):
    mirror = TcScene.create("shadow-settings-mirror")
    changed = []
    try:
        controller = ShadowSettingsController(
            scene,
            mirror_scenes=(scene, mirror),
            on_changed=lambda: changed.append(True),
        )
        saved = controller.apply(ShadowSettingsSnapshot(2, 1.25, 0.003))

        loaded = controller.load()
        mirrored = ShadowSettingsController(mirror).load()
        assert loaded.method == saved.method
        assert loaded.softness == pytest.approx(saved.softness)
        assert loaded.bias == pytest.approx(saved.bias)
        assert mirrored.method == saved.method
        assert mirrored.softness == pytest.approx(saved.softness)
        assert mirrored.bias == pytest.approx(saved.bias)
        assert changed == [True]
        with pytest.raises(ValueError):
            controller.apply(ShadowSettingsSnapshot(3, 1.0, 0.0))
    finally:
        mirror.destroy()


def test_scene_properties_controller_owns_undoable_render_mutations(scene):
    stack = UndoStack()
    changed = []
    controller = ScenePropertiesController(
        scene,
        push_undo_command=stack.push,
        on_changed=lambda: changed.append(True),
    )
    initial = controller.load()
    next_type = next(item for item in SKYBOX_TYPES if item != initial.skybox_type)

    updated = controller.set_ambient_intensity(0.625)
    updated = controller.set_skybox_type(next_type)
    updated = controller.set_background_color((0.1, 0.2, 0.3, 1.0))
    updated = controller.set_fixed_update_frequency(200.0)
    updated = controller.set_time_scale(0.4)

    assert updated.fixed_update_frequency == pytest.approx(200.0)
    assert updated.time_scale == pytest.approx(0.4)
    assert scene.fixed_timestep == pytest.approx(0.005)
    assert scene.time_scale == pytest.approx(0.4)
    assert updated.ambient_intensity == pytest.approx(0.625)
    assert updated.skybox_type == next_type
    assert updated.background_color == pytest.approx((0.1, 0.2, 0.3, 1.0))
    assert len(stack) == 5
    stack.undo()
    assert scene.time_scale == pytest.approx(initial.time_scale)
    stack.undo()
    assert scene.fixed_timestep == pytest.approx(initial.fixed_update_frequency**-1)
    stack.undo()
    assert tuple(scene_render_state(scene).background_color) == pytest.approx(initial.background_color)
    assert len(changed) == 5
    with pytest.raises(ValueError):
        controller.set_ambient_intensity(12.0)
    with pytest.raises(ValueError):
        controller.set_fixed_update_frequency(0.0)
    with pytest.raises(ValueError):
        controller.set_time_scale(-0.1)


def test_scene_properties_controller_discovers_and_toggles_debug_geometry(scene):
    registration = DebugGeometryTypeRegistration(
        "tests.scene-settings.debug-geometry",
        "Scene Settings Probe",
        "Tests",
        True,
    )
    assert registration
    changed = []
    controller = ScenePropertiesController(
        scene,
        on_changed=lambda: changed.append(True),
    )

    setting = next(
        item
        for item in controller.load().debug_geometry
        if item.stable_id == "tests.scene-settings.debug-geometry"
    )
    assert setting.display_name == "Scene Settings Probe"
    assert setting.category == "Tests"
    assert setting.enabled is True

    updated = controller.set_debug_geometry_enabled(setting.stable_id, False)
    toggled = next(
        item for item in updated.debug_geometry if item.stable_id == setting.stable_id
    )
    assert toggled.enabled is False
    assert changed == [True]
