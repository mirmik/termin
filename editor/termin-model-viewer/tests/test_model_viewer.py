from __future__ import annotations

import json
from pathlib import Path
import struct

import pytest

from termin.model_viewer.application import _OrbitInteraction, _create_view, parse_options
from termin.model_viewer.model import load_visual_model


def _padded(data: bytes, fill: bytes) -> bytes:
    padding = (-len(data)) % 4
    return data + fill * padding


def _write_triangle_glb(path: Path, *, include_material: bool = True) -> Path:
    positions = struct.pack(
        "<9f",
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
    )
    indices = struct.pack("<3H", 0, 1, 2)
    binary = positions + indices
    binary = _padded(binary, b"\0")
    document = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(positions)},
            {
                "buffer": 0,
                "byteOffset": len(positions),
                "byteLength": len(indices),
            },
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [0.0, 0.0, 0.0],
                "max": [1.0, 1.0, 0.0],
            },
            {
                "bufferView": 1,
                "componentType": 5123,
                "count": 3,
                "type": "SCALAR",
            },
        ],
        "meshes": [
            {
                "name": "Triangle",
                "primitives": [
                    {
                        "attributes": {"POSITION": 0},
                        "indices": 1,
                    }
                ],
            }
        ],
        "nodes": [
            {
                "name": "Translated",
                "mesh": 0,
                "translation": [2.0, 3.0, 4.0],
            }
        ],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    if include_material:
        document["materials"] = [
            {
                "name": "Blue",
                "pbrMetallicRoughness": {"baseColorFactor": [0.1, 0.3, 0.9, 1.0]},
            }
        ]
        document["meshes"][0]["primitives"][0]["material"] = 0
    json_chunk = _padded(
        json.dumps(document, separators=(",", ":")).encode("utf-8"),
        b" ",
    )
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary)
    glb = b"".join(
        [
            struct.pack("<4sII", b"glTF", 2, total_length),
            struct.pack("<II", len(json_chunk), 0x4E4F534A),
            json_chunk,
            struct.pack("<II", len(binary), 0x004E4942),
            binary,
        ]
    )
    path.write_bytes(glb)
    return path


def test_load_visual_model_preserves_hierarchy_and_converts_to_z_up(tmp_path):
    model_path = _write_triangle_glb(tmp_path / "triangle.glb")
    before = {path.name for path in tmp_path.iterdir()}
    model = load_visual_model(model_path)
    try:
        assert len(model.items) == 1
        assert model.bounds.minimum == pytest.approx((2.0, -4.0, 3.0))
        assert model.bounds.maximum == pytest.approx((3.0, -4.0, 4.0))
        assert not model.items[0].hit_test_enabled
        assert model.items[0].flat_lighting_enabled
        assert {path.name for path in tmp_path.iterdir()} == before
        assert model.statistics.mesh_count == 1
        assert model.statistics.primitive_count == 1
        assert model.statistics.vertex_count == 3
        assert model.statistics.triangle_count == 1
    finally:
        model.close()


def test_load_visual_model_uses_default_material_when_glb_has_no_materials(tmp_path):
    model_path = _write_triangle_glb(
        tmp_path / "material-less.glb",
        include_material=False,
    )

    model = load_visual_model(model_path)
    try:
        assert len(model.items) == 1
        assert model.bounds.minimum == pytest.approx((2.0, -4.0, 3.0))
        assert model.bounds.maximum == pytest.approx((3.0, -4.0, 4.0))
        item = model.items[0]
        assert not item.hit_test_enabled
        assert item.flat_lighting_enabled
        assert tuple(item.flat_light_direction) == pytest.approx(
            (0.6123724356957945, -0.6123724356957946, 0.5)
        )
        assert item.flat_light_ambient == pytest.approx(0.28)
        assert item.flat_light_diffuse == pytest.approx(0.72)
        assert (item.tint.r, item.tint.g, item.tint.b, item.tint.a) == pytest.approx(
            (0.34, 0.72, 0.95, 1.0)
        )
    finally:
        model.close()


def test_parse_options_validates_path_size_and_frame_limit(tmp_path):
    model_path = _write_triangle_glb(tmp_path / "triangle.glb")
    options = parse_options(
        [
            str(model_path),
            "--width",
            "900",
            "--height",
            "600",
            "--backend",
            "opengl",
            "--frames",
            "2",
        ]
    )
    assert options.model == model_path.resolve()
    assert (options.width, options.height, options.frame_limit) == (900, 600, 2)
    assert options.backend == "opengl"

    with pytest.raises(SystemExit):
        parse_options([str(model_path), "--width", "100"])
    with pytest.raises(SystemExit):
        parse_options([str(model_path), "--frames", "-1"])


def test_orbit_interaction_uses_shared_orbit_camera():
    from tcbase import MouseButton
    from termin.geombase import AABB, OrbitCamera, Vec3
    from termin.gui_native import PointerEvent, PointerEventType

    camera = OrbitCamera()
    camera.fit_bounds(AABB(Vec3(-1.0, -1.0, -1.0), Vec3(1.0, 1.0, 1.0)))
    invalidations = []
    interaction = _OrbitInteraction(camera, lambda: invalidations.append(True))
    initial_azimuth = camera.azimuth
    initial_distance = camera.distance

    event = PointerEvent()
    event.type = PointerEventType.Down
    event.button = MouseButton.LEFT.value
    event.x = 100.0
    event.y = 100.0
    assert interaction.handle(event, None)

    event.type = PointerEventType.Move
    event.x = 180.0
    event.y = 130.0
    assert interaction.handle(event, None)
    assert camera.azimuth != initial_azimuth

    event.type = PointerEventType.Up
    assert interaction.handle(event, None)

    event.type = PointerEventType.Wheel
    event.wheel_y = 1.0
    assert interaction.handle(event, None)
    assert camera.distance < initial_distance
    assert len(invalidations) == 2


def test_model_viewer_native_toolbar_controls_scene_view_and_light(tmp_path):
    from termin.gui_native import (
        EventResult,
        PointerEvent,
        PointerEventType,
        Rect,
        SceneView3DShadingMode,
        tc_ui_document_create,
        tc_ui_document_destroy,
    )

    model = load_visual_model(_write_triangle_glb(tmp_path / "toolbar.glb"))
    document = tc_ui_document_create()
    repaint_requests = []
    ui = None
    try:
        ui = _create_view(document, model, lambda: repaint_requests.append(True))
        assert ui.root.widget.stable_id == "termin.model-viewer.root"
        assert ui.view.widget.stable_id == "termin.model-viewer.scene"
        assert ui.view.shading_mode == SceneView3DShadingMode.Flat
        assert ui.statistics_label.widget.stable_id == "termin.model-viewer.statistics"
        assert ui.statistics_label.text == "Vertices: 3  ·  Triangles: 1"
        assert ui.flat_button.active
        assert not ui.smooth_button.active
        assert not ui.view.wireframe_enabled
        initial_direction = (ui.camera.eye - ui.camera.target).normalized()
        assert tuple(model.items[0].flat_light_direction) == pytest.approx(
            (initial_direction.x, initial_direction.y, initial_direction.z)
        )

        def click(button) -> None:
            button.widget.bounds = Rect(0.0, 0.0, 36.0, 36.0)
            event = PointerEvent()
            event.x = 10.0
            event.y = 10.0
            event.type = PointerEventType.Down
            assert button.widget.dispatch_pointer_event(event) == EventResult.Handled
            event.type = PointerEventType.Up
            assert button.widget.dispatch_pointer_event(event) == EventResult.Handled

        click(ui.smooth_button)
        assert ui.view.shading_mode == SceneView3DShadingMode.Smooth
        assert not ui.flat_button.active
        assert ui.smooth_button.active

        click(ui.wireframe_button)
        assert ui.view.wireframe_enabled
        assert ui.wireframe_button.active

        ui.camera.orbit(0.37, -0.18)
        eye = ui.camera.eye
        target = ui.camera.target
        expected = (eye - target).normalized()
        click(ui.light_button)
        assert tuple(model.items[0].flat_light_direction) == pytest.approx(
            (expected.x, expected.y, expected.z)
        )
        assert len(repaint_requests) >= 4
    finally:
        if ui is not None:
            ui.view.set_fallback_pointer_handler(None)
            ui.view.set_camera_provider(None)
            ui.view.detach_scene()
        model.close()
        tc_ui_document_destroy(document)
