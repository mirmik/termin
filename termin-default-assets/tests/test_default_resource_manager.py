from termin.default_assets.resource_manager import DefaultResourceManager
from termin.default_assets.handle_accessors import HandleAccessors
from termin.materials import TcMaterial
from tgfx import TcTexture
import pytest


def test_default_resource_manager_owns_default_runtime_registries() -> None:
    manager = DefaultResourceManager()

    assert "prefab" in manager._runtime_asset_registries
    assert "glb" in manager._runtime_asset_registries
    assert "animation_clip" in manager._runtime_asset_registries
    assert "skeleton" in manager._runtime_asset_registries
    assert "pipeline" in manager._runtime_asset_registries
    missing_material = manager.get_material("__missing__")
    assert isinstance(missing_material, TcMaterial)
    assert missing_material.is_valid
    assert "Missing material: __missing__" in missing_material.name
    missing_uuid_material = manager.get_material_by_uuid("__missing_uuid__")
    assert isinstance(missing_uuid_material, TcMaterial)
    assert missing_uuid_material.is_valid
    assert "Missing material: uuid:__missing_uuid__" in missing_uuid_material.name
    assert isinstance(manager.get_handle_accessors("tc_material"), HandleAccessors)


def test_default_resource_manager_has_no_parallel_tc_handle_caches() -> None:
    manager = DefaultResourceManager()

    instance_fields = vars(manager)
    assert "materials" not in instance_fields
    assert "voxel_grids" not in instance_fields
    assert "navmeshes" not in instance_fields
    assert "animation_clips" not in instance_fields
    assert "skeletons" not in instance_fields
    assert "shaders" not in instance_fields


def test_material_lookup_uses_unique_asset_name_and_canonical_uuid() -> None:
    from termin.default_assets.render.material_asset import MaterialAsset

    manager = DefaultResourceManager()
    first = TcMaterial.create("first", "resource-manager-material-first")
    second = TcMaterial.create("second", "resource-manager-material-second")
    manager.register_material("shared", first)

    by_name = manager.get_material("shared")
    by_uuid = manager.get_material_by_uuid(first.uuid)
    assert by_name.uuid == first.uuid
    assert by_uuid.uuid == first.uuid
    assert by_uuid.uuid == TcMaterial.from_uuid(first.uuid).uuid
    assert manager.find_material_name(TcMaterial.from_uuid(first.uuid)) == "shared"
    assert manager.find_material_uuid(TcMaterial.from_uuid(first.uuid)) == first.uuid

    manager.register_material_asset(
        "shared",
        MaterialAsset.from_material(second, name="shared"),
    )

    ambiguous = manager.get_material("shared")
    assert ambiguous.uuid not in {first.uuid, second.uuid}
    assert "Missing material: shared" in ambiguous.name
    assert manager.get_material_by_uuid(first.uuid).uuid == first.uuid
    assert manager.get_material_by_uuid(second.uuid).uuid == second.uuid


def test_shader_lookup_rejects_duplicate_names_but_keeps_uuid_identity() -> None:
    from termin.materials import parse_shader_text

    manager = DefaultResourceManager()
    source = """@program Shared
@language slang
@phase opaque
@stage vertex
void main() {}
@endstage
@stage fragment
void main() {}
@endstage
@endphase
"""
    manager.register_shader("shared", parse_shader_text(source), uuid="shader-duplicate-one")
    manager.register_shader("shared", parse_shader_text(source), uuid="shader-duplicate-two")

    assert manager.get_shader("shared") is None
    assert manager.get_shader_by_uuid("shader-duplicate-one").uuid == "shader-duplicate-one"
    assert manager.get_shader_by_uuid("shader-duplicate-two").uuid == "shader-duplicate-two"


def test_tc_resource_lookups_resolve_asset_uuid_through_native_registries() -> None:
    from termin.animation import TcAnimationClip
    from termin.navmesh._navmesh_native import TcNavMesh
    from termin.navmesh.types import NavMesh
    from termin.skeleton import TcSkeleton
    from termin.voxels._voxels_native import TcVoxelGrid
    from termin.voxels.grid import VoxelGrid

    manager = DefaultResourceManager()

    manager.register_voxel_grid("grid", VoxelGrid(name="grid"))
    voxel_asset = manager.get_voxel_grid_asset("grid")
    assert voxel_asset is not None
    assert manager.get_voxel_grid("grid").uuid == voxel_asset.uuid
    assert manager.get_voxel_grid_by_uuid(voxel_asset.uuid).uuid == voxel_asset.uuid
    assert TcVoxelGrid.from_uuid(voxel_asset.uuid).is_valid

    manager.register_navmesh("navmesh", NavMesh(name="navmesh"))
    navmesh_asset = manager.get_navmesh_asset("navmesh")
    assert navmesh_asset is not None
    assert manager.get_navmesh("navmesh").uuid == navmesh_asset.uuid
    assert manager.get_navmesh_by_uuid(navmesh_asset.uuid).uuid == navmesh_asset.uuid
    assert TcNavMesh.from_uuid(navmesh_asset.uuid).is_valid

    clip = TcAnimationClip.create("clip", "resource-manager-animation-clip")
    manager.register_animation_clip("clip", clip)
    assert manager.get_animation_clip("clip").uuid == clip.uuid
    assert manager.get_animation_clip_by_uuid(clip.uuid).uuid == clip.uuid
    assert manager.get_animation_clip_asset_by_uuid(clip.uuid).uuid == clip.uuid
    assert manager.find_animation_clip_name(TcAnimationClip.from_uuid(clip.uuid)) == "clip"

    skeleton = TcSkeleton.create("skeleton", "resource-manager-skeleton")
    manager.register_skeleton("skeleton", skeleton)
    assert manager.get_skeleton("skeleton").uuid == skeleton.uuid
    assert manager.get_skeleton_by_uuid(skeleton.uuid).uuid == skeleton.uuid
    assert manager.get_skeleton_asset_by_uuid(skeleton.uuid).uuid == skeleton.uuid
    assert manager.find_skeleton_name(TcSkeleton.from_uuid(skeleton.uuid)) == "skeleton"
    assert manager.find_skeleton_uuid(TcSkeleton.from_uuid(skeleton.uuid)) == skeleton.uuid


def test_tc_resource_rename_and_unregister_need_no_parallel_state() -> None:
    manager = DefaultResourceManager()
    material = TcMaterial.create("rename", "resource-manager-material-rename")
    manager.register_material("before", material)

    assert manager.rename_runtime_asset("material", material.uuid, "after")
    assert "Missing material: before" in manager.get_material("before").name
    assert manager.get_material("after").uuid == material.uuid

    removed = manager.unregister_runtime_asset_by_uuid("material", material.uuid)
    assert removed is not None
    assert manager.get_material_by_uuid(material.uuid).uuid != material.uuid


def test_tc_resource_registration_rejects_split_asset_and_handle_uuids() -> None:
    from termin.animation import TcAnimationClip
    from termin.skeleton import TcSkeleton

    manager = DefaultResourceManager()

    material = TcMaterial.create("material", "resource-manager-material-aligned")
    with pytest.raises(ValueError, match="UUIDs must match"):
        manager.register_material("material", material, uuid="different-material-uuid")

    clip = TcAnimationClip.create("clip", "resource-manager-animation-aligned")
    with pytest.raises(ValueError, match="UUIDs must match"):
        manager.register_animation_clip("clip", clip, uuid="different-animation-uuid")

    skeleton = TcSkeleton.create("skeleton", "resource-manager-skeleton-aligned")
    with pytest.raises(ValueError, match="UUIDs must match"):
        manager.register_skeleton("skeleton", skeleton, uuid="different-skeleton-uuid")


def test_default_resource_manager_does_not_register_removed_scene_pipeline_assets() -> None:
    manager = DefaultResourceManager()

    assert "scene_pipeline" not in manager._runtime_asset_registries
    assert manager.asset_type_plugins.get_for_extension(".scene_pipeline") == []


def test_default_resource_manager_exposes_handle_accessor_contracts() -> None:
    manager = DefaultResourceManager()

    assert isinstance(manager.get_handle_accessors("mesh_handle"), HandleAccessors)
    assert isinstance(manager.get_handle_accessors("tc_texture"), HandleAccessors)
    assert isinstance(manager.get_handle_accessors("texture_handle"), HandleAccessors)


def test_handle_accessors_enumerate_duplicate_names_by_uuid() -> None:
    from termin.default_assets.render.texture_asset import TextureAsset

    manager = DefaultResourceManager()
    manager.register_texture_asset(
        "shared",
        TextureAsset(name="shared", source_path="Assets/One/shared.png", uuid="texture-one"),
    )
    manager.register_texture_asset(
        "shared",
        TextureAsset(name="shared", source_path="Assets/Two/shared.png", uuid="texture-two"),
    )

    assert manager.get_handle_accessors("tc_texture").list_items() == [
        ("shared", "texture-one"),
        ("shared", "texture-two"),
    ]


def test_default_resource_manager_exposes_builtin_asset_registration() -> None:
    manager = DefaultResourceManager()

    manager.register_builtin_textures()
    manager.register_builtin_materials()
    registered_meshes = manager.register_builtin_meshes()

    assert manager.get_texture_asset("__white_1x1__") is not None
    assert manager.get_texture_asset("__normal_1x1__") is not None
    white_texture = manager.get_texture_handle("__white_1x1__")
    normal_texture = manager.get_texture_handle("__normal_1x1__")
    assert isinstance(white_texture, TcTexture)
    assert isinstance(normal_texture, TcTexture)
    assert white_texture.is_valid
    assert normal_texture.is_valid
    assert white_texture.uuid == "__white_1x1__"
    assert normal_texture.uuid == "__normal_1x1__"
    assert manager.get_handle_by_uuid("tc_texture", "__white_1x1__").uuid == "__white_1x1__"
    assert not TcTexture.from_uuid("5fb7972ad02ddfad").is_valid
    assert not TcTexture.from_uuid("07151644d3bb92c7").is_valid
    assert manager.get_texture_asset_by_uuid("5fb7972ad02ddfad") is None
    assert manager.get_texture_asset_by_uuid("07151644d3bb92c7") is None
    assert set(registered_meshes) == {"Cube", "Sphere", "Plane", "Cylinder"}
    assert manager.get_mesh_asset("Cube") is not None


def test_builtin_pipeline_registration_is_idempotent_without_cached_instance() -> None:
    from termin.render_framework import tc_pipeline_registry_count

    manager = DefaultResourceManager()
    baseline = tc_pipeline_registry_count()

    try:
        manager.register_builtin_pipelines()
        after_first = tc_pipeline_registry_count()
        manager.register_builtin_pipelines()

        assert manager.get_pipeline_asset("Triangle") is not None
        assert after_first == baseline
        assert tc_pipeline_registry_count() == after_first
    finally:
        manager.clear_runtime_state()
        assert tc_pipeline_registry_count() == baseline
