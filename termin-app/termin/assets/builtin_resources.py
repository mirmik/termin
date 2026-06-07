"""
Builtin resources registration.

Contains functions to register built-in shaders, materials, meshes, and pipelines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from termin.assets.resources import ResourceManager

from termin.assets.builtin_uuids import BUILTIN_UUIDS


def register_default_shader(rm: "ResourceManager") -> None:
    """Register built-in DefaultShader (Blinn-Phong)."""
    if "DefaultShader" in rm.shaders:
        return

    from termin.visualization.render.materials.default_material import DEFAULT_SHADER_TEXT
    from termin.materials import parse_shader_text

    program = parse_shader_text(DEFAULT_SHADER_TEXT)
    rm.register_shader("DefaultShader", program, uuid=BUILTIN_UUIDS["DefaultShader"])


def register_pbr_shader(rm: "ResourceManager") -> None:
    """Register built-in PBR shader."""
    if "PBRShader" in rm.shaders:
        return

    from termin.visualization.render.materials.pbr_material import PBR_SHADER_TEXT
    from termin.materials import parse_shader_text

    program = parse_shader_text(PBR_SHADER_TEXT)
    rm.register_shader("PBRShader", program, uuid=BUILTIN_UUIDS["PBRShader"])


def register_skinned_shader(rm: "ResourceManager") -> None:
    """Register built-in SkinnedShader for skeletal animation."""
    if "SkinnedShader" in rm.shaders:
        return

    from termin.visualization.render.materials.skinned_material import (
        SKINNED_VERT,
        SKINNED_FRAG,
    )
    from termin.materials import (
        ShaderMultyPhaseProgramm,
        ShaderPhase,
        ShasderStage,
        MaterialProperty,
    )

    vertex_stage = ShasderStage("vertex", SKINNED_VERT)
    fragment_stage = ShasderStage("fragment", SKINNED_FRAG)
    properties = [
        MaterialProperty("u_color", "Color", (1.0, 1.0, 1.0, 1.0)),
        MaterialProperty("u_albedo_texture", "Texture", None),
        MaterialProperty("u_shininess", "Float", 32.0, 1.0, 2048.0),
        MaterialProperty("u_emission_color", "Color", (0.0, 0.0, 0.0, 1.0)),
        MaterialProperty("u_emission_intensity", "Float", 0.0, 0.0, 100.0),
    ]

    phase = ShaderPhase(
        phase_mark="opaque",
        priority=0,
        gl_depth_mask=True,
        gl_depth_test=True,
        gl_blend=False,
        gl_cull=True,
        stages={"vertex": vertex_stage, "fragment": fragment_stage},
        uniforms=properties,
    )

    program = ShaderMultyPhaseProgramm(
        program="SkinnedShader",
        phases=[phase],
        material_properties=properties,
    )
    rm.register_shader("SkinnedShader", program, uuid=BUILTIN_UUIDS["SkinnedShader"])


def register_builtin_shaders(rm: "ResourceManager") -> None:
    """Register all built-in shaders."""
    register_default_shader(rm)
    register_pbr_shader(rm)
    register_skinned_shader(rm)


def register_builtin_textures(rm: "ResourceManager") -> None:
    """Register built-in placeholder textures."""
    from termin.assets.texture_asset import TextureAsset
    from termin.visualization.render.texture import get_normal_texture, get_white_texture

    if "__white_1x1__" not in rm._texture_registry.assets:
        white_texture = get_white_texture().texture_data
        if white_texture is not None and white_texture.is_valid:
            white_asset = TextureAsset(
                texture_data=white_texture,
                name="__white_1x1__",
                source_path="__white_1x1__",
                uuid=white_texture.uuid,
            )
            rm.register_texture_asset("__white_1x1__", white_asset, uuid=white_texture.uuid)

    if "__normal_1x1__" not in rm._texture_registry.assets:
        normal_texture = get_normal_texture().texture_data
        if normal_texture is not None and normal_texture.is_valid:
            normal_asset = TextureAsset(
                texture_data=normal_texture,
                name="__normal_1x1__",
                source_path="__normal_1x1__",
                uuid=normal_texture.uuid,
            )
            rm.register_texture_asset("__normal_1x1__", normal_asset, uuid=normal_texture.uuid)


def register_builtin_materials(rm: "ResourceManager") -> None:
    """Register built-in materials."""
    from termin.materials import create_material_from_parsed
    from termin.assets.texture_handle import (
        get_normal_texture_handle,
        get_white_texture_handle,
    )

    # Ensure shaders are registered
    register_builtin_shaders(rm)
    register_builtin_textures(rm)

    white_tex = get_white_texture_handle().get()
    normal_tex = get_normal_texture_handle().get()

    # DefaultMaterial (Blinn-Phong)
    if "DefaultMaterial" not in rm.materials:
        shader = rm.shaders.get("DefaultShader")
        if shader is not None:
            mat = create_material_from_parsed(
                shader,
                textures={
                    "u_albedo_texture": white_tex,
                    "u_metallic_roughness_texture": white_tex,
                    "u_occlusion_texture": white_tex,
                    "u_emissive_texture": white_tex,
                },
                default_white_texture=white_tex,
                default_normal_texture=normal_tex,
            )
            mat.name = "DefaultMaterial"
            mat.color = (0.3, 0.85, 0.9, 1.0)
            rm.register_material("DefaultMaterial", mat, uuid=BUILTIN_UUIDS["DefaultMaterial"])

    # PBRMaterial
    if "PBRMaterial" not in rm.materials:
        shader = rm.shaders.get("PBRShader")
        if shader is not None:
            mat = create_material_from_parsed(
                shader,
                textures={"u_albedo_texture": white_tex},
                default_white_texture=white_tex,
                default_normal_texture=normal_tex,
            )
            mat.name = "PBRMaterial"
            mat.color = (0.8, 0.8, 0.8, 1.0)
            rm.register_material("PBRMaterial", mat, uuid=BUILTIN_UUIDS["PBRMaterial"])

    # NormalizedPBR is the material contract used by default scenes and GLB
    # instantiation. Keep it registered as a first-class builtin, not as a
    # lazy missing-material fallback.
    if "NormalizedPBR" not in rm.materials:
        shader = rm.shaders.get("PBRShader")
        if shader is not None:
            mat = create_material_from_parsed(
                shader,
                textures={"u_albedo_texture": white_tex},
                default_white_texture=white_tex,
                default_normal_texture=normal_tex,
            )
            mat.name = "NormalizedPBR"
            mat.color = (0.8, 0.8, 0.8, 1.0)
            rm.register_material("NormalizedPBR", mat, uuid=BUILTIN_UUIDS["NormalizedPBR"])

    # GridMaterial (calibration grid)
    if "GridMaterial" not in rm.materials:
        from termin.visualization.render.materials.grid_material import GridMaterial
        mat = GridMaterial(color=(0.8, 0.8, 0.8, 1.0), grid_spacing=1.0, line_width=0.02)
        mat.name = "GridMaterial"
        rm.register_material("GridMaterial", mat, uuid=BUILTIN_UUIDS["GridMaterial"])

    # SkinnedMaterial (skeletal animation)
    if "SkinnedMaterial" not in rm.materials:
        shader = rm.shaders.get("SkinnedShader")
        if shader is not None:
            mat = create_material_from_parsed(
                shader,
                textures={"u_albedo_texture": white_tex},
                default_white_texture=white_tex,
                default_normal_texture=normal_tex,
            )
            mat.name = "SkinnedMaterial"
            mat.color = (0.8, 0.8, 0.8, 1.0)
            rm.register_material("SkinnedMaterial", mat, uuid=BUILTIN_UUIDS["SkinnedMaterial"])


def register_builtin_meshes(rm: "ResourceManager") -> List[str]:
    """
    Register built-in primitive meshes.

    Returns:
        List of registered mesh names.
    """
    from termin.assets.mesh_asset import MeshAsset
    from termin.mesh.mesh import (
        TexturedCubeMesh,
        UVSphereMesh,
        PlaneMesh,
        CylinderMesh,
    )

    registered = []

    # Cube with correct UVs (texture on each face)
    if "Cube" not in rm._mesh_assets:
        cube = MeshAsset.from_mesh3(
            TexturedCubeMesh(size=1.0), name="Cube", uuid=BUILTIN_UUIDS["Cube"]
        )
        rm.register_mesh_asset("Cube", cube, uuid=BUILTIN_UUIDS["Cube"])
        registered.append("Cube")

    # Sphere
    if "Sphere" not in rm._mesh_assets:
        sphere = MeshAsset.from_mesh3(
            UVSphereMesh(radius=0.5, n_meridians=32, n_parallels=16),
            name="Sphere", uuid=BUILTIN_UUIDS["Sphere"]
        )
        rm.register_mesh_asset("Sphere", sphere, uuid=BUILTIN_UUIDS["Sphere"])
        registered.append("Sphere")

    # Plane
    if "Plane" not in rm._mesh_assets:
        plane = MeshAsset.from_mesh3(
            PlaneMesh(width=1.0, height=1.0), name="Plane", uuid=BUILTIN_UUIDS["Plane"]
        )
        rm.register_mesh_asset("Plane", plane, uuid=BUILTIN_UUIDS["Plane"])
        registered.append("Plane")

    # Cylinder
    if "Cylinder" not in rm._mesh_assets:
        cylinder = MeshAsset.from_mesh3(
            CylinderMesh(radius=0.5, height=1.0), name="Cylinder", uuid=BUILTIN_UUIDS["Cylinder"]
        )
        rm.register_mesh_asset("Cylinder", cylinder, uuid=BUILTIN_UUIDS["Cylinder"])
        registered.append("Cylinder")

    return registered


def register_default_pipeline(rm: "ResourceManager") -> None:
    """Default pipeline is created by native RenderingManager on demand."""
    return


def register_triangle_pipeline(rm: "ResourceManager") -> None:
    """Register built-in diagnostic triangle render pipeline."""
    if rm.get_pipeline("Triangle") is not None:
        return

    from termin.visualization.render.framegraph import RenderPipeline
    from termin.visualization.render.framegraph.passes.debug_triangle import DebugTrianglePass

    pipeline = RenderPipeline(
        name="Triangle",
        _init_passes=[
            DebugTrianglePass(output_res="OUTPUT", pass_name="DebugTriangle"),
        ],
    )
    rm.register_pipeline("Triangle", pipeline, uuid=BUILTIN_UUIDS.get("TrianglePipeline"))


def register_all_builtins(rm: "ResourceManager") -> None:
    """Register all built-in resources (shaders, materials, meshes, pipelines)."""
    register_builtin_shaders(rm)
    register_builtin_textures(rm)
    register_builtin_materials(rm)
    register_builtin_meshes(rm)
    register_default_pipeline(rm)
    register_triangle_pipeline(rm)
