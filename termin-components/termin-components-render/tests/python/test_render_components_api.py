from pathlib import Path
from uuid import uuid4

import pytest

from termin.bootstrap import bootstrap_player

bootstrap_player()

from termin.geombase import Vec3
from termin.materials import TcMaterial
from termin.render_components import (
    Camera,
    CameraController,
    CameraProjection,
    DepthOnlyPass,
    DepthPass,
    LineRenderer,
    LineRenderMode,
    MaterialPass,
    MeshRenderer,
    NormalPass,
    OrbitCameraController,
    SkinnedMeshRenderer,
    WorldTextAnchor,
    WorldTextComponent,
    WorldTextOrientation,
    get_texture_inputs_for_material,
)
from termin.render_framework import RenderContext
from termin.render import (
    RENDER_PHASE_DEPTH,
    RENDER_PHASE_ID,
    RENDER_PHASE_OPAQUE,
    RENDER_PHASE_SHADOW,
    RENDER_PHASE_TRANSPARENT,
    configure_project_render_phases,
    find_render_phase,
)


VERTEX = """
#version 450
layout(location=0) in vec3 in_position;
void main() { gl_Position = vec4(in_position, 1.0); }
"""


FRAGMENT = """
#version 450
layout(location=0) out vec4 out_color;
void main() { out_color = vec4(1.0); }
"""


def _render_context() -> RenderContext:
    return RenderContext()


def _line_points() -> list[Vec3]:
    return [Vec3(0, 0, 0), Vec3(1, 0, 0)]


def create_line_test_material(extra_phase_marks: tuple[str, ...] = ()) -> TcMaterial:
    material = TcMaterial.create("LineRendererShadowPhaseTest", "")
    assert material.is_valid
    assert material.add_phase_from_sources(
        VERTEX,
        FRAGMENT,
        "",
        "LineRendererShadowPhaseTestShader",
        "opaque",
        0,
    ) is not None
    assert material.add_phase_from_sources(
        VERTEX,
        FRAGMENT,
        "",
        "LineRendererShadowPhaseTestShadowShader",
        "shadow",
        0,
    ) is not None
    for phase_mark in extra_phase_marks:
        assert material.add_phase_from_sources(
            VERTEX,
            FRAGMENT,
            "",
            f"LineRendererShadowPhaseTest{phase_mark.title()}Shader",
            phase_mark,
            0,
        ) is not None
    return material


def create_unique_test_material(label: str) -> TcMaterial:
    material = TcMaterial.create(f"{label}-{uuid4()}", str(uuid4()))
    assert material.is_valid
    return material


def test_render_components_exports_camera_controller_and_material_pass_helpers():
    camera = Camera.perspective_deg(60.0, 16.0 / 9.0)

    assert camera.projection_type == CameraProjection.Perspective
    assert CameraController.__name__ == "CameraController"
    assert SkinnedMeshRenderer.__name__ == "SkinnedMeshRenderer"
    assert MaterialPass.inspect_fields["material"].kind == "tc_material"
    assert MaterialPass.get_texture_inputs_for_material is not None
    assert get_texture_inputs_for_material("(None)") == []


def test_orbit_camera_controller_exposes_target_as_vec3():
    controller = OrbitCameraController()

    assert isinstance(controller.target, Vec3)

    controller.center_on(Vec3(1.0, 2.0, 3.0))
    assert controller.target == Vec3(1.0, 2.0, 3.0)

    controller._target = Vec3(4.0, 5.0, 6.0)
    assert controller._target == Vec3(4.0, 5.0, 6.0)


def test_skinned_mesh_renderer_computes_bones_in_renderer_space():
    from termin.scene import TcScene
    from termin.geombase import Vec3
    from termin.skeleton import TcSkeleton
    from termin.skeleton_components import SkeletonController

    skeleton = TcSkeleton.create("Renderer Space Skeleton", f"renderer-space-skeleton-{uuid4()}")
    skeleton.alloc_bones(1)
    bone = skeleton.get_bone(0)
    bone.name = "root"
    bone.index = 0
    bone.parent_index = -1
    bone.inverse_bind_matrix = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    skeleton.rebuild_roots()

    scene = TcScene.create("skinned-renderer-space")
    try:
        armature = scene.create_entity("Armature")
        armature.transform.set_local_position(Vec3(10.0, 0.0, 0.0))

        bone_entity = scene.create_entity("root")
        bone_entity.transform.set_local_position(Vec3(5.0, 0.0, 0.0))
        bone_entity.set_parent(armature)

        mesh_entity = scene.create_entity("Body")
        mesh_entity.transform.set_local_position(Vec3(2.0, 0.0, 0.0))
        mesh_entity.set_parent(armature)

        controller = SkeletonController(skeleton, [bone_entity])
        armature.add_component(controller)
        renderer = SkinnedMeshRenderer(None, controller, True)
        mesh_entity.add_component(renderer)

        renderer.update_bone_matrices()

        matrix = renderer.get_bone_matrices_flat().reshape(-1)
        assert renderer._bone_count == 1
        assert matrix[12] == pytest.approx(3.0)
        assert matrix[13] == pytest.approx(0.0)
        assert matrix[14] == pytest.approx(0.0)
    finally:
        scene.destroy()


def test_skinned_mesh_renderer_resolves_skeleton_controller_from_ancestor():
    from termin.scene import TcScene
    from termin.geombase import Vec3
    from termin.skeleton import TcSkeleton
    from termin.skeleton_components import SkeletonController

    skeleton = TcSkeleton.create("Ancestor Skeleton", f"ancestor-skeleton-{uuid4()}")
    skeleton.alloc_bones(1)
    bone = skeleton.get_bone(0)
    bone.name = "root"
    bone.index = 0
    bone.parent_index = -1
    bone.inverse_bind_matrix = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    skeleton.rebuild_roots()

    scene = TcScene.create("skinned-renderer-ancestor-controller")
    try:
        model = scene.create_entity("Model")
        armature = scene.create_entity("Armature")
        armature.set_parent(model)

        bone_entity = scene.create_entity("root")
        bone_entity.transform.set_local_position(Vec3(5.0, 0.0, 0.0))
        bone_entity.set_parent(armature)

        mesh_entity = scene.create_entity("Body")
        mesh_entity.transform.set_local_position(Vec3(2.0, 0.0, 0.0))
        mesh_entity.set_parent(armature)

        controller = SkeletonController(skeleton, [bone_entity])
        model.add_component(controller)
        renderer = SkinnedMeshRenderer()
        mesh_entity.add_component(renderer)

        renderer.update_bone_matrices()

        matrix = renderer.get_bone_matrices_flat().reshape(-1)
        assert renderer.skeleton_controller is controller
        assert renderer._bone_count == 1
        assert matrix[12] == pytest.approx(3.0)
    finally:
        scene.destroy()


def test_depth_and_normal_passes_expose_explicit_phase_mark():
    from termin.inspect import InspectRegistry

    depth = DepthPass()
    depth_only = DepthOnlyPass()
    normal = NormalPass()

    assert depth.phase_mark == "depth"
    assert depth_only.phase_mark == "depth"
    assert normal.phase_mark == "normal"

    depth.phase_mark = "custom_depth"
    depth_only.phase_mark = "custom_depth_only"
    normal.phase_mark = "custom_normals"

    assert depth.phase_mark == "custom_depth"
    assert depth_only.phase_mark == "custom_depth_only"
    assert normal.phase_mark == "custom_normals"

    registry = InspectRegistry.instance()
    for type_name in ("DepthPass", "DepthOnlyPass", "NormalPass"):
        fields = {field.path: field for field in registry.all_fields(type_name)}
        assert fields["phase_mark"].label == "Phase Mark"
        assert fields["phase_mark"].kind == "string"


def test_depth_and_normal_passes_deserialize_phase_mark():
    default_depth = DepthPass._deserialize_instance({"pass_name": "Depth", "data": {}}, None)
    default_depth_only = DepthOnlyPass._deserialize_instance(
        {"pass_name": "DepthOnly", "data": {}},
        None,
    )
    default_normal = NormalPass._deserialize_instance({"pass_name": "Normal", "data": {}}, None)

    assert default_depth.phase_mark == "depth"
    assert default_depth_only.phase_mark == "depth"
    assert default_normal.phase_mark == "normal"

    depth = DepthPass._deserialize_instance(
        {"pass_name": "Depth", "data": {"phase_mark": "custom_depth"}},
        None,
    )
    depth_only = DepthOnlyPass._deserialize_instance(
        {"pass_name": "DepthOnly", "data": {"phase_mark": "custom_depth_only"}},
        None,
    )
    normal = NormalPass._deserialize_instance(
        {"pass_name": "Normal", "data": {"phase_mark": "custom_normals"}},
        None,
    )

    assert depth.phase_mark == "custom_depth"
    assert depth_only.phase_mark == "custom_depth_only"
    assert normal.phase_mark == "custom_normals"


def test_depth_and_normal_passes_deserialize_legacy_material_phase_mark():
    depth = DepthPass._deserialize_instance(
        {"pass_name": "Depth", "data": {"material_phase_mark": "custom_depth"}},
        None,
    )
    depth_only = DepthOnlyPass._deserialize_instance(
        {"pass_name": "DepthOnly", "data": {"material_phase_mark": "custom_depth_only"}},
        None,
    )
    normal = NormalPass._deserialize_instance(
        {"pass_name": "Normal", "data": {"material_phase_mark": "custom_normals"}},
        None,
    )

    assert depth.phase_mark == "custom_depth"
    assert depth_only.phase_mark == "custom_depth_only"
    assert normal.phase_mark == "custom_normals"


def test_line_renderer_defaults_to_world_billboard_mode():
    renderer = LineRenderer(points=_line_points())

    assert renderer.render_mode == LineRenderMode.WorldBillboard
    assert renderer.raw_lines is False
    assert renderer.phase_mask == RENDER_PHASE_OPAQUE | RENDER_PHASE_DEPTH | RENDER_PHASE_ID


def test_line_renderer_world_mesh_fallback_builds_cpu_mesh():
    renderer = LineRenderer(points=_line_points(), render_mode=LineRenderMode.WorldMesh)

    assert renderer.render_mode == LineRenderMode.WorldMesh
    assert bool(renderer.get_mesh()) is True


def test_pipeline_shader_usage_collection_uses_pass_phase_mark():
    from tgfx import ShaderVariantOp
    from termin.render_framework import RenderPipeline, collect_shader_usages_for_pipeline
    from termin.render_passes import ColorPass
    from termin.scene import TcScene

    scene = TcScene.create("pipeline-shader-usage-test")
    pipeline = RenderPipeline("pipeline-shader-usage-test")
    empty_phase_pipeline = RenderPipeline("pipeline-shader-usage-empty-phase-test")
    try:
        entity = scene.create_entity("line")
        entity.add_component(
            LineRenderer(
                points=_line_points(),
                render_mode=LineRenderMode.WorldTube,
            )
        )

        pipeline.add_pass(ColorPass(phase_mark="opaque"))
        shaders = collect_shader_usages_for_pipeline(scene.scene_handle(), pipeline)
        shader_uuids = {shader.uuid for shader in shaders}

        assert "termin-engine-line-default" in shader_uuids
        assert len(shader_uuids) == len(shaders)
        variant_ops = {shader.variant_op for shader in shaders}
        assert ShaderVariantOp.LINE_TUBE_BODY in variant_ops
        assert ShaderVariantOp.LINE_TUBE_CAP in variant_ops

        empty_phase_pipeline.add_pass(ColorPass(phase_mark=""))
        assert len(collect_shader_usages_for_pipeline(scene.scene_handle(), empty_phase_pipeline)) == 0
    finally:
        empty_phase_pipeline.destroy()
        pipeline.destroy()
        scene.destroy()


def test_line_renderer_direct_modes_skip_shadow_material_phase():
    material = create_line_test_material()

    renderer = LineRenderer(points=_line_points(), material=material)

    assert renderer.phase_mask == RENDER_PHASE_OPAQUE | RENDER_PHASE_DEPTH | RENDER_PHASE_ID


def test_line_renderer_includes_builtin_id_phase():
    material = create_line_test_material(extra_phase_marks=("id",))

    renderer = LineRenderer(
        points=_line_points(),
        material=material,
        render_mode=LineRenderMode.WorldTube,
    )

    assert renderer.phase_mask == RENDER_PHASE_OPAQUE | RENDER_PHASE_DEPTH | RENDER_PHASE_ID


def test_line_renderer_cast_shadow_enables_shadow_material_phase():
    material = create_line_test_material()

    billboard = LineRenderer(
        points=_line_points(),
        material=material,
        cast_shadow=True,
    )
    expected = RENDER_PHASE_OPAQUE | RENDER_PHASE_DEPTH | RENDER_PHASE_ID | RENDER_PHASE_SHADOW
    assert billboard.phase_mask == expected

    renderer = LineRenderer(
        points=_line_points(),
        material=material,
        render_mode=LineRenderMode.WorldMesh,
        cast_shadow=True,
    )
    assert renderer.phase_mask == expected


def test_line_renderer_cast_shadow_uses_default_shadow_phase_when_material_lacks_one():
    renderer = LineRenderer(points=_line_points(), cast_shadow=True)

    assert renderer.phase_mask == (
        RENDER_PHASE_OPAQUE | RENDER_PHASE_DEPTH | RENDER_PHASE_ID | RENDER_PHASE_SHADOW
    )


def test_mesh_renderer_get_phases_for_mark_returns_non_owning_phase_refs():
    material = create_line_test_material()
    renderer = MeshRenderer(material=material)

    opaque = renderer.get_phases_for_mark("opaque")
    shadow = renderer.get_phases_for_mark("shadow")

    assert [phase.phase_mark for phase in opaque] == ["opaque"]
    assert [phase.phase_mark for phase in shadow] == ["shadow"]
    assert material.phases[0].phase_mark == "opaque"


def test_mesh_renderer_rejects_legacy_mesh_constructor_argument():
    with pytest.raises(TypeError):
        MeshRenderer(mesh="Cube")


def test_mesh_renderer_no_longer_exposes_mesh_mutators():
    renderer = MeshRenderer()

    with pytest.raises(AttributeError):
        _ = renderer.set_mesh
    with pytest.raises(AttributeError):
        _ = renderer.set_mesh_by_name
    with pytest.raises(AttributeError):
        _ = renderer.mesh


def test_mesh_renderer_material_slots_serialize_data_roundtrip():
    legacy_material = create_unique_test_material("MeshRendererSlotLegacy")
    slot0_material = create_unique_test_material("MeshRendererSlot0")
    slot2_material = create_unique_test_material("MeshRendererSlot2")

    renderer = MeshRenderer(material=legacy_material)
    renderer.set_material_slot(0, slot0_material)
    renderer.set_material_slot(2, slot2_material)

    data = renderer.serialize_data()

    assert data["material"]["uuid"] == legacy_material.uuid
    assert [slot["type"] for slot in data["materials"]] == ["uuid", "none", "uuid"]
    assert data["materials"][0]["uuid"] == slot0_material.uuid
    assert data["materials"][2]["uuid"] == slot2_material.uuid

    restored = MeshRenderer()
    restored.deserialize_data(data)

    assert restored.material.uuid == legacy_material.uuid
    assert restored.material_slot_count == 3
    assert restored.materials[0].uuid == slot0_material.uuid
    assert restored.materials[1].is_valid is False
    assert restored.materials[2].uuid == slot2_material.uuid


def test_mesh_renderer_material_slots_survive_entity_hierarchy_roundtrip():
    from termin.scene import Entity, TcScene

    legacy_material = create_unique_test_material("MeshRendererHierarchyLegacy")
    slot0_material = create_unique_test_material("MeshRendererHierarchySlot0")
    slot2_material = create_unique_test_material("MeshRendererHierarchySlot2")

    source_scene = TcScene.create("mesh-renderer-material-slots-source")
    restored_scene = TcScene.create("mesh-renderer-material-slots-restored")
    try:
        entity = source_scene.create_entity("mesh")
        renderer = entity.add_component_by_name("MeshRenderer").to_python()
        renderer.set_material(legacy_material)
        renderer.set_material_slot(0, slot0_material)
        renderer.set_material_slot(2, slot2_material)

        restored_entity = Entity.deserialize_hierarchy(
            entity.serialize_hierarchy(),
            restored_scene,
            None,
        )
        restored = restored_entity.get_component(MeshRenderer)

        assert restored.material.uuid == legacy_material.uuid
        assert restored.material_slot_count == 3
        assert restored.materials[0].uuid == slot0_material.uuid
        assert restored.materials[1].is_valid is False
        assert restored.materials[2].uuid == slot2_material.uuid
    finally:
        source_scene.destroy()
        restored_scene.destroy()


def test_mesh_renderer_preconfigured_component_survives_entity_add_component():
    from termin.scene import Entity, TcScene

    legacy_material = create_unique_test_material("MeshRendererPreconfiguredLegacy")
    slot0_material = create_unique_test_material("MeshRendererPreconfiguredSlot0")
    slot2_material = create_unique_test_material("MeshRendererPreconfiguredSlot2")

    source_scene = TcScene.create("mesh-renderer-preconfigured-source")
    restored_scene = TcScene.create("mesh-renderer-preconfigured-restored")
    try:
        entity = source_scene.create_entity("mesh")
        renderer = MeshRenderer(material=legacy_material, cast_shadow=False)
        renderer.set_material_slot(0, slot0_material)
        renderer.set_material_slot(2, slot2_material)

        entity.add_component(renderer)
        hierarchy = entity.serialize_hierarchy()
        component_data = next(
            item["data"] for item in hierarchy["components"] if item["type"] == "MeshRenderer"
        )

        assert component_data["material"]["uuid"] == legacy_material.uuid
        assert component_data["cast_shadow"] is False
        assert [slot["type"] for slot in component_data["materials"]] == ["uuid", "none", "uuid"]
        assert component_data["materials"][0]["uuid"] == slot0_material.uuid
        assert component_data["materials"][2]["uuid"] == slot2_material.uuid

        restored_entity = Entity.deserialize_hierarchy(
            hierarchy,
            restored_scene,
            None,
        )
        restored = restored_entity.get_component(MeshRenderer)

        assert restored.material.uuid == legacy_material.uuid
        assert restored.cast_shadow is False
        assert restored.material_slot_count == 3
        assert restored.materials[0].uuid == slot0_material.uuid
        assert restored.materials[1].is_valid is False
        assert restored.materials[2].uuid == slot2_material.uuid
    finally:
        source_scene.destroy()
        restored_scene.destroy()


def test_mesh_renderer_legacy_single_material_data_clears_material_slots():
    legacy_material = create_unique_test_material("MeshRendererLegacySingleMaterial")
    stale_slot_material = create_unique_test_material("MeshRendererStaleSlot")

    renderer = MeshRenderer()
    renderer.set_material_slot(0, stale_slot_material)
    renderer.deserialize_data(
        {
            "material": {
                "uuid": legacy_material.uuid,
                "name": legacy_material.name,
                "type": "uuid",
            },
            "cast_shadow": True,
        }
    )

    assert renderer.material.uuid == legacy_material.uuid
    assert renderer.material_slot_count == 0
    assert renderer.get_material_for_slot(0).uuid == legacy_material.uuid


def test_line_renderer_mesh_mode_skips_shadow_when_cast_shadow_is_disabled():
    material = create_line_test_material()

    renderer = LineRenderer(
        points=_line_points(),
        material=material,
        render_mode=LineRenderMode.WorldMesh,
    )

    assert renderer.phase_mask == RENDER_PHASE_OPAQUE | RENDER_PHASE_DEPTH | RENDER_PHASE_ID


def test_line_renderer_world_tube_is_gpu_direct_mode():
    renderer = LineRenderer(
        points=_line_points(),
        render_mode=LineRenderMode.WorldTube,
        tube_sides=6,
    )

    assert renderer.render_mode == LineRenderMode.WorldTube
    assert renderer.tube_sides == 6
    assert renderer.get_mesh().is_valid is False


def test_line_renderer_keeps_legacy_raw_lines_constructor_position():
    renderer = LineRenderer(_line_points(), 0.25, True)

    assert renderer.raw_lines is True
    assert bool(renderer.get_mesh()) is True


def test_line_renderer_points_are_inspectable():
    from termin.inspect import InspectRegistry
    from termin.scene import Entity

    registry = InspectRegistry.instance()
    fields = {field.path: field for field in registry.all_fields("LineRenderer")}

    assert fields["points"].label == "Positions"
    assert fields["points"].kind == "list[vec3]"
    assert fields["cast_shadow"].label == "Cast Shadow"
    assert fields["cast_shadow"].kind == "bool"
    assert fields["tube_sides"].label == "Tube Sides"
    assert fields["tube_sides"].kind == "int"
    assert fields["render_mode"].label == "Render Mode"
    assert fields["render_mode"].kind == "enum"
    assert [(choice.value, choice.label) for choice in fields["render_mode"].choices] == [
        ("0", "World Billboard"),
        ("1", "Screen Space"),
        ("2", "World Mesh"),
        ("3", "Raw Lines"),
        ("4", "World Tube"),
    ]

    entity = Entity(name="line")
    component = entity.add_component_by_name("LineRenderer")
    component.set_field("points", [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    component.set_field("render_mode", "4")

    assert component.get_field("points") == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    assert component.get_field("render_mode") == 4
    points = component.to_python().points
    assert [(p.x, p.y, p.z) for p in points] == [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
    assert component.to_python().render_mode == LineRenderMode.WorldTube


def test_world_text_component_defaults_to_transparent_direct_draw():
    text = WorldTextComponent("e4", size=0.5)

    assert text.text == "e4"
    assert text.size == 0.5
    assert text.anchor == WorldTextAnchor.Center
    assert text.anchor_name == "center"
    assert text.orientation == WorldTextOrientation.Billboard
    assert text.orientation_name == "billboard"
    assert (text.plane_normal.x, text.plane_normal.y, text.plane_normal.z) == (0.0, 0.0, 1.0)
    assert (text.text_up.x, text.text_up.y, text.text_up.z) == (0.0, 1.0, 0.0)
    assert text.depth_test is True
    assert text.depth_write is False
    assert text.blend is True
    assert text.phase_mask == RENDER_PHASE_TRANSPARENT | RENDER_PHASE_ID


def test_world_text_component_hides_empty_text_from_draw_contract():
    text = WorldTextComponent()

    assert text.phase_mask == 0

    names = [""] * 48
    names[0] = "overlay"
    configure_project_render_phases(names)
    try:
        text.text = "A"
        text.phase_mark = "overlay"
        assert text.phase_mask == find_render_phase("overlay") | RENDER_PHASE_ID
    finally:
        configure_project_render_phases([""] * 48)


def test_world_text_component_is_inspectable():
    from termin.inspect import InspectRegistry
    from termin.scene import Entity

    registry = InspectRegistry.instance()
    fields = {field.path: field for field in registry.all_fields("WorldTextComponent")}

    assert fields["text"].label == "Text"
    assert fields["text"].kind == "string"
    assert fields["local_offset"].label == "Local Offset"
    assert fields["local_offset"].kind == "vec3"
    assert fields["color"].label == "Color"
    assert fields["color"].kind == "color"
    assert fields["anchor"].label == "Anchor"
    assert fields["anchor"].kind == "enum"
    assert [(choice.value, choice.label) for choice in fields["anchor"].choices] == [
        ("0", "Left"),
        ("1", "Center"),
        ("2", "Right"),
    ]
    assert fields["orientation"].label == "Orientation"
    assert fields["orientation"].kind == "enum"
    assert [(choice.value, choice.label) for choice in fields["orientation"].choices] == [
        ("0", "Billboard"),
        ("1", "Fixed"),
    ]
    assert fields["plane_normal"].label == "Plane Normal"
    assert fields["plane_normal"].kind == "vec3"
    assert fields["text_up"].label == "Text Up"
    assert fields["text_up"].kind == "vec3"

    entity = Entity(name="world text")
    component = entity.add_component_by_name("WorldTextComponent")
    component.set_field("text", "Nf3")
    component.set_field("anchor", "2")
    component.set_field("orientation", "1")
    component.set_field("plane_normal", [0.0, 0.0, 1.0])
    component.set_field("text_up", [0.0, 1.0, 0.0])
    component.set_field("size", 0.75)

    assert component.get_field("text") == "Nf3"
    assert component.get_field("anchor") == 2
    assert component.get_field("orientation") == 1
    assert component.get_field("plane_normal") == [0.0, 0.0, 1.0]
    assert component.get_field("text_up") == [0.0, 1.0, 0.0]
    assert component.get_field("size") == 0.75
    assert component.to_python().anchor == WorldTextAnchor.Right
    assert component.to_python().anchor_name == "right"
    assert component.to_python().orientation == WorldTextOrientation.Fixed
    assert component.to_python().orientation_name == "fixed"


def test_depth_conversion_passes_bind_textures_by_reflected_name():
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "depth_pass.cpp"
    ).read_text(encoding="utf-8")

    assert 'bind_texture("u_depth_tex", depth_tex)' in source
    assert 'bind_texture("u_color_tex", color_tex)' in source
    assert "bind_sampled_texture(9" not in source
