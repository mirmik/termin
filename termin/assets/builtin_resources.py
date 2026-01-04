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

    from termin.visualization.render.materials.default_material import (
        DEFAULT_VERT,
        DEFAULT_FRAG,
    )
    from termin.visualization.render.shader_parser import (
        ShaderMultyPhaseProgramm,
        ShaderPhase,
        ShasderStage,
        MaterialProperty,
    )

    vertex_stage = ShasderStage("vertex", DEFAULT_VERT)
    fragment_stage = ShasderStage("fragment", DEFAULT_FRAG)

    phase = ShaderPhase(
        phase_mark="opaque",
        priority=0,
        gl_depth_mask=True,
        gl_depth_test=True,
        gl_blend=False,
        gl_cull=True,
        stages={"vertex": vertex_stage, "fragment": fragment_stage},
        uniforms=[
            MaterialProperty("u_color", "Color", (1.0, 1.0, 1.0, 1.0)),
            MaterialProperty("u_albedo_texture", "Texture", None),
            MaterialProperty("u_shininess", "Float", 32.0, 1.0, 2048.0),
        ],
    )

    program = ShaderMultyPhaseProgramm(program="DefaultShader", phases=[phase])
    rm.register_shader("DefaultShader", program, uuid=BUILTIN_UUIDS["DefaultShader"])


def register_pbr_shader(rm: "ResourceManager") -> None:
    """Register built-in PBR shader."""
    if "PBRShader" in rm.shaders:
        return

    from termin.visualization.render.materials.pbr_material import (
        PBR_VERT,
        PBR_FRAG,
    )
    from termin.visualization.render.shader_parser import (
        ShaderMultyPhaseProgramm,
        ShaderPhase,
        ShasderStage,
        MaterialProperty,
    )

    vertex_stage = ShasderStage("vertex", PBR_VERT)
    fragment_stage = ShasderStage("fragment", PBR_FRAG)

    phase = ShaderPhase(
        phase_mark="opaque",
        priority=0,
        gl_depth_mask=True,
        gl_depth_test=True,
        gl_blend=False,
        gl_cull=True,
        stages={"vertex": vertex_stage, "fragment": fragment_stage},
        uniforms=[
            MaterialProperty("u_color", "Color", (1.0, 1.0, 1.0, 1.0)),
            MaterialProperty("u_albedo_texture", "Texture", None),
            MaterialProperty("u_metallic", "Float", 0.0, 0.0, 1.0),
            MaterialProperty("u_roughness", "Float", 0.5, 0.0, 1.0),
        ],
    )

    program = ShaderMultyPhaseProgramm(program="PBRShader", phases=[phase])
    rm.register_shader("PBRShader", program, uuid=BUILTIN_UUIDS["PBRShader"])


def register_advanced_pbr_shader(rm: "ResourceManager") -> None:
    """Register built-in Advanced PBR shader with SSS and ACES."""
    if "AdvancedPBRShader" in rm.shaders:
        return

    from termin.visualization.render.materials.advanced_pbr_material import (
        ADVANCED_PBR_VERT,
        ADVANCED_PBR_FRAG,
    )
    from termin.visualization.render.shader_parser import (
        ShaderMultyPhaseProgramm,
        ShaderPhase,
        ShasderStage,
        MaterialProperty,
    )

    vertex_stage = ShasderStage("vertex", ADVANCED_PBR_VERT)
    fragment_stage = ShasderStage("fragment", ADVANCED_PBR_FRAG)

    phase = ShaderPhase(
        phase_mark="opaque",
        priority=0,
        gl_depth_mask=True,
        gl_depth_test=True,
        gl_blend=False,
        gl_cull=True,
        stages={"vertex": vertex_stage, "fragment": fragment_stage},
        uniforms=[
            MaterialProperty("u_color", "Color", (1.0, 1.0, 1.0, 1.0)),
            MaterialProperty("u_albedo_texture", "Texture", None),
            MaterialProperty("u_metallic", "Float", 0.0, 0.0, 1.0),
            MaterialProperty("u_roughness", "Float", 0.5, 0.0, 1.0),
            MaterialProperty("u_subsurface", "Float", 0.0, 0.0, 1.0),
        ],
    )

    program = ShaderMultyPhaseProgramm(program="AdvancedPBRShader", phases=[phase])
    rm.register_shader("AdvancedPBRShader", program, uuid=BUILTIN_UUIDS["AdvancedPBRShader"])


def register_skinned_shader(rm: "ResourceManager") -> None:
    """Register built-in SkinnedShader for skeletal animation."""
    if "SkinnedShader" in rm.shaders:
        return

    from termin.visualization.render.materials.skinned_material import (
        SKINNED_VERT,
        SKINNED_FRAG,
    )
    from termin.visualization.render.shader_parser import (
        ShaderMultyPhaseProgramm,
        ShaderPhase,
        ShasderStage,
        MaterialProperty,
    )

    vertex_stage = ShasderStage("vertex", SKINNED_VERT)
    fragment_stage = ShasderStage("fragment", SKINNED_FRAG)

    phase = ShaderPhase(
        phase_mark="opaque",
        priority=0,
        gl_depth_mask=True,
        gl_depth_test=True,
        gl_blend=False,
        gl_cull=True,
        stages={"vertex": vertex_stage, "fragment": fragment_stage},
        uniforms=[
            MaterialProperty("u_color", "Color", (1.0, 1.0, 1.0, 1.0)),
            MaterialProperty("u_albedo_texture", "Texture", None),
            MaterialProperty("u_shininess", "Float", 32.0, 1.0, 2048.0),
        ],
    )

    program = ShaderMultyPhaseProgramm(program="SkinnedShader", phases=[phase])
    rm.register_shader("SkinnedShader", program, uuid=BUILTIN_UUIDS["SkinnedShader"])


def register_builtin_shaders(rm: "ResourceManager") -> None:
    """Register all built-in shaders."""
    register_default_shader(rm)
    register_pbr_shader(rm)
    register_advanced_pbr_shader(rm)
    register_skinned_shader(rm)


def register_builtin_materials(rm: "ResourceManager") -> None:
    """Register built-in materials."""
    from termin.visualization.core.material import Material
    from termin.visualization.core.texture_handle import get_white_texture_handle

    # Ensure shaders are registered
    register_builtin_shaders(rm)

    white_tex = get_white_texture_handle()

    # DefaultMaterial (Blinn-Phong)
    if "DefaultMaterial" not in rm.materials:
        shader = rm.shaders.get("DefaultShader")
        if shader is not None:
            mat = Material.from_parsed(shader, textures={"u_albedo_texture": white_tex})
            mat.name = "DefaultMaterial"
            mat.color = (0.3, 0.85, 0.9, 1.0)
            rm.register_material("DefaultMaterial", mat, uuid=BUILTIN_UUIDS["DefaultMaterial"])

    # PBRMaterial
    if "PBRMaterial" not in rm.materials:
        shader = rm.shaders.get("PBRShader")
        if shader is not None:
            mat = Material.from_parsed(shader, textures={"u_albedo_texture": white_tex})
            mat.name = "PBRMaterial"
            mat.color = (0.8, 0.8, 0.8, 1.0)
            rm.register_material("PBRMaterial", mat, uuid=BUILTIN_UUIDS["PBRMaterial"])

    # AdvancedPBRMaterial (SSS + ACES)
    if "AdvancedPBRMaterial" not in rm.materials:
        shader = rm.shaders.get("AdvancedPBRShader")
        if shader is not None:
            mat = Material.from_parsed(shader, textures={"u_albedo_texture": white_tex})
            mat.name = "AdvancedPBRMaterial"
            mat.color = (0.8, 0.8, 0.8, 1.0)
            rm.register_material("AdvancedPBRMaterial", mat, uuid=BUILTIN_UUIDS["AdvancedPBRMaterial"])

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
            mat = Material.from_parsed(shader, textures={"u_albedo_texture": white_tex})
            mat.name = "SkinnedMaterial"
            mat.color = (0.8, 0.8, 0.8, 1.0)
            rm.register_material("SkinnedMaterial", mat, uuid=BUILTIN_UUIDS["SkinnedMaterial"])


def register_builtin_meshes(rm: "ResourceManager") -> List[str]:
    """
    Register built-in primitive meshes.

    Returns:
        List of registered mesh names.
    """
    from termin.visualization.core.mesh_asset import MeshAsset
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
            PlaneMesh(width=1.0, depth=1.0), name="Plane", uuid=BUILTIN_UUIDS["Plane"]
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
    """Register built-in default render pipeline."""
    if rm.get_pipeline("Default") is not None:
        return

    from termin.visualization.core.viewport import make_default_pipeline

    pipeline = make_default_pipeline()
    rm.register_pipeline("Default", pipeline, uuid=BUILTIN_UUIDS.get("DefaultPipeline"))


def register_all_builtins(rm: "ResourceManager") -> None:
    """Register all built-in resources (shaders, materials, meshes, pipelines)."""
    register_builtin_shaders(rm)
    register_builtin_materials(rm)
    register_builtin_meshes(rm)
    register_default_pipeline(rm)
