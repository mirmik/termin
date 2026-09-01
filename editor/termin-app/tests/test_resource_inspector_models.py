import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from termin.editor_core.resource_inspector_models import (
    GlbInspectorController,
    MeshInspectorController,
    TextureInspectorController,
    format_file_size,
    prepare_texture_preview_pixels,
)


class _ResourceManager:
    def __init__(self, mesh=None):
        self.mesh = mesh

    def get_mesh_asset(self, _name):
        return self.mesh


class _MeshAsset:
    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.name = source_path.stem
        self.uuid = "mesh-uuid"

    def get_vertex_count(self):
        return 12

    def get_triangle_count(self):
        return 4


def test_format_file_size_uses_compact_units():
    assert format_file_size(512) == "512 B"
    assert format_file_size(2048) == "2.0 KB"
    assert format_file_size(2 * 1024 * 1024) == "2.00 MB"


def test_linear_texture_preview_is_encoded_for_sdr_without_changing_alpha():
    pixels = np.array([[[0, 128, 255, 64]]], dtype=np.uint8)

    preview = prepare_texture_preview_pixels(pixels, "linear")

    np.testing.assert_array_equal(preview, np.array([[[0, 188, 255, 64]]], dtype=np.uint8))
    np.testing.assert_array_equal(pixels, np.array([[[0, 128, 255, 64]]], dtype=np.uint8))
    assert prepare_texture_preview_pixels(pixels, "srgb") is pixels


def test_texture_inspector_round_trips_full_spec_and_recreates_native_texture(
    tmp_path,
):
    from termin.image import write_png_rgba8_file
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin_assets import set_resource_manager_factory
    from termin.graphics import TextureEncoding

    texture_path = tmp_path / "albedo.png"
    pixels = np.array([[[128, 128, 128, 64]]], dtype=np.uint8)
    write_png_rgba8_file(texture_path, pixels)
    meta_path = Path(f"{texture_path}.meta")
    meta_path.write_text(
        json.dumps(
            {
                "uuid": "inspector-texture-uuid",
                "filter": "nearest",
                "mipmaps": True,
                "wrap": "repeat",
                "encoding": "srgb",
                "alpha_mode": "opaque",
            }
        ),
        encoding="utf-8",
    )
    manager = DefaultResourceManager()
    set_resource_manager_factory(lambda: manager)
    try:
        plugin = manager.asset_type_plugins.get_import("texture")
        assert plugin is not None
        result = plugin.preload(str(texture_path))
        assert result is not None
        manager.register_file(result)
        asset = manager.get_texture_asset_by_uuid("inspector-texture-uuid")
        assert asset is not None
        native = asset.texture_data
        assert native is not None
        previous_asset_version = asset.version
        previous_native_version = native.version
        changed = []
        controller = TextureInspectorController(
            manager,
            changed=lambda: changed.append(True),
        )
        snapshot = controller.set_target(manager.get_texture("albedo"), name="albedo")

        assert snapshot.encoding == "srgb"
        np.testing.assert_array_equal(snapshot.preview_pixels, pixels)
        updated = controller.save_import_settings(
            encoding="linear",
            flip_x=True,
            flip_y=False,
            transpose=True,
        )

        assert updated.error == ""
        assert updated.encoding == "linear"
        np.testing.assert_array_equal(
            updated.preview_pixels,
            np.array([[[188, 188, 188, 64]]], dtype=np.uint8),
        )
        persisted = json.loads(meta_path.read_text(encoding="utf-8"))
        assert persisted == {
            "uuid": "inspector-texture-uuid",
            "filter": "nearest",
            "mipmaps": True,
            "wrap": "repeat",
            "encoding": "linear",
            "alpha_mode": "opaque",
            "flip_x": True,
            "flip_y": False,
            "transpose": True,
        }
        assert asset.encoding == "linear"
        assert asset.filter == "nearest"
        assert asset.mipmaps is True
        assert asset.wrap == "repeat"
        assert asset.alpha_mode == "opaque"
        assert asset.version > previous_asset_version
        recreated = asset.texture_data
        assert recreated is not None
        assert recreated.uuid == native.uuid
        assert recreated.encoding == TextureEncoding.LINEAR
        assert recreated.version > previous_native_version
        assert changed == [True]
    finally:
        set_resource_manager_factory(None)
        manager.clear_runtime_state()


def test_texture_inspector_rolls_back_metadata_and_ui_after_reimport_failure(
    tmp_path,
):
    from termin.image import write_png_rgba8_file
    from termin.default_assets.resource_manager import DefaultResourceManager
    from termin_assets import set_resource_manager_factory

    texture_path = tmp_path / "broken.png"
    write_png_rgba8_file(
        texture_path,
        np.array([[[64, 96, 128, 255]]], dtype=np.uint8),
    )
    meta_path = Path(f"{texture_path}.meta")
    original_metadata = {
        "uuid": "broken-inspector-texture",
        "filter": "nearest",
        "mipmaps": True,
        "wrap": "repeat",
        "encoding": "srgb",
        "alpha_mode": "straight",
    }
    meta_path.write_text(json.dumps(original_metadata), encoding="utf-8")
    manager = DefaultResourceManager()
    set_resource_manager_factory(lambda: manager)
    try:
        plugin = manager.asset_type_plugins.get_import("texture")
        assert plugin is not None
        result = plugin.preload(str(texture_path))
        assert result is not None
        manager.register_file(result)
        asset = manager.get_texture_asset_by_uuid("broken-inspector-texture")
        assert asset is not None
        assert asset.texture_data is not None
        previous_version = asset.version
        controller = TextureInspectorController(manager)
        controller.set_target(manager.get_texture("broken"), name="broken")
        texture_path.write_bytes(b"not an image")

        updated = controller.save_import_settings(
            encoding="linear",
            flip_x=True,
            flip_y=False,
            transpose=True,
        )

        assert "runtime recreation failed" in updated.error
        assert updated.encoding == "srgb"
        assert asset.encoding == "srgb"
        assert asset.version == previous_version
        restored = json.loads(meta_path.read_text(encoding="utf-8"))
        assert {key: restored[key] for key in original_metadata} == original_metadata
        assert restored["flip_x"] is False
        assert restored["flip_y"] is True
        assert restored["transpose"] is False
    finally:
        set_resource_manager_factory(None)
        manager.clear_runtime_state()
def test_mesh_inspector_reads_and_persists_import_settings(tmp_path):
    mesh_path = tmp_path / "crate.obj"
    mesh_path.write_text("mesh", encoding="utf-8")
    meta_path = Path(f"{mesh_path}.meta")
    meta_path.write_text(json.dumps({"uuid": "preserve-me", "scale": 2.0}), encoding="utf-8")
    changed = []
    controller = MeshInspectorController(
        _ResourceManager(_MeshAsset(mesh_path)),
        changed=lambda: changed.append(True),
    )

    snapshot = controller.set_target(None, file_path=str(mesh_path))
    assert snapshot.available
    assert snapshot.vertices == "12"
    assert snapshot.triangles == "4"
    assert snapshot.scale == 2.0

    updated = controller.save_import_settings(
        scale=0.5,
        axis_x="-x",
        axis_y="z",
        axis_z="y",
        flip_uv_v=True,
    )
    assert updated.scale == 0.5
    assert changed == [True]
    persisted = json.loads(meta_path.read_text(encoding="utf-8"))
    assert persisted["uuid"] == "preserve-me"
    assert persisted["flip_uv_v"] is True


def test_mesh_inspector_rejects_invalid_axis(tmp_path):
    mesh_path = tmp_path / "crate.obj"
    mesh_path.write_text("mesh", encoding="utf-8")
    controller = MeshInspectorController(_ResourceManager(_MeshAsset(mesh_path)))
    controller.set_target(None, file_path=str(mesh_path))
    with pytest.raises(ValueError, match="invalid mesh import axis"):
        controller.save_import_settings(
            scale=1.0,
            axis_x="sideways",
            axis_y="y",
            axis_z="z",
            flip_uv_v=False,
        )


def test_glb_inspector_persists_reimport_settings(tmp_path, monkeypatch):
    glb_path = tmp_path / "actor.glb"
    glb_path.write_bytes(b"glb")
    fake_data = SimpleNamespace(meshes=(1, 2), textures=(1,), animations=(1, 2, 3))
    monkeypatch.setattr("termin.glb.loader.load_glb_file", lambda _path: fake_data)
    changed = []
    controller = GlbInspectorController(changed=lambda: changed.append(True))

    snapshot = controller.set_target(None, file_path=str(glb_path))
    assert snapshot.available
    assert (snapshot.meshes, snapshot.textures, snapshot.animations) == ("2", "1", "3")
    updated = controller.save_import_settings(
        convert_to_z_up=False,
        normalize_scale=True,
        blender_z_up_fix=True,
    )
    assert updated.normalize_scale
    assert changed == [True]
