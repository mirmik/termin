import gc
from termin.editor_core.resource_inspector_models import (
    GlbInspectorSnapshot,
    MeshInspectorSnapshot,
    TextureInspectorSnapshot,
)
from termin.editor_native.resource_inspectors import build_native_resource_inspectors
from termin.gui_native import Document


class _ResourceManager:
    def get_texture(self, _name):
        return None

    def get_mesh_asset(self, _name):
        return None


def test_native_resource_inspectors_project_snapshots():
    document = Document()
    renders = []
    texture, mesh, glb = build_native_resource_inspectors(
        document,
        resource_manager=_ResourceManager(),
        request_render=lambda: renders.append(True),
    )
    for inspector in (texture, mesh, glb):
        assert document.add_root(inspector.root.handle)

    texture.rebuild(
        TextureInspectorSnapshot(
            True,
            name="albedo",
            uuid="texture-uuid",
            resolution="256 × 128",
            channels="4",
            path="/project/albedo.png",
        )
    )
    assert "resolution" in texture.controls
    assert texture.controls["flip-y"].checked

    mesh.rebuild(
        MeshInspectorSnapshot(
            True,
            name="crate",
            vertices="24",
            triangles="12",
            path="/project/crate.obj",
            axis_y="z",
            axis_z="y",
        )
    )
    assert "vertices" in mesh.controls
    assert mesh.controls["axis-y"].selected_text == "z"

    glb.rebuild(
        GlbInspectorSnapshot(
            True,
            name="actor",
            path="/project/actor.glb",
            meshes="3",
            textures="2",
            animations="7",
        )
    )
    assert "animations" in glb.controls
    assert "apply" in glb.controls
    assert renders

    for inspector in (texture, mesh, glb):
        assert document.destroy_widget_recursive(inspector.root.handle)
    del texture, mesh, glb, document
    gc.collect()
