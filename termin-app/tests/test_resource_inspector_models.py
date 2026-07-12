import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from termin.editor_core.resource_inspector_models import (
    GlbInspectorController,
    MeshInspectorController,
    format_file_size,
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
