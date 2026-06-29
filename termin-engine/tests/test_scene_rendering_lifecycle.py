from termin.engine import (
    deserialize_scene as engine_deserialize_scene,
    destroy_scene as engine_destroy_scene,
    scene_ext_attached_names,
)
from termin.render import TcSceneLighting, scene_render_state


def test_engine_deserialize_scene_registers_defaults_and_migrates_legacy_render_state():
    scene = engine_deserialize_scene(
        {
            "uuid": "legacy-render-scene",
            "background_color": [0.25, 0.5, 0.75, 1.0],
            "ambient_color": [0.1, 0.2, 0.3],
            "ambient_intensity": 2.0,
            "entities": [],
        },
        "legacy-render-smoke",
    )
    try:
        render_state = scene_render_state(scene)
        lighting = render_state.lighting()

        assert scene.uuid == "legacy-render-scene"
        assert scene_ext_attached_names(scene) == [
            "render_mount",
            "render_state",
            "collision_world",
        ]
        assert tuple(round(value, 3) for value in render_state.get_background_color()) == (
            0.25,
            0.5,
            0.75,
            1.0,
        )
        assert tuple(round(value, 3) for value in render_state.ambient_color) == (
            0.1,
            0.2,
            0.3,
        )
        assert round(render_state.ambient_intensity, 3) == 2.0
        assert isinstance(lighting, TcSceneLighting)
        assert lighting.valid()
        assert tuple(round(value, 3) for value in lighting.ambient_color) == (
            0.1,
            0.2,
            0.3,
        )
    finally:
        engine_destroy_scene(scene)
