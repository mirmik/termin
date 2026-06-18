"""Builtin resources registration.

This module only registers resources that are truly embedded runtime defaults.
Resources under ``termin/resources/stdlib`` are assets and must be loaded
through the asset pipeline so their source files stay authoritative.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from termin.assets.resources import ResourceManager

from termin.assets.builtin_uuids import BUILTIN_UUIDS


def register_builtin_shaders(rm: "ResourceManager") -> None:
    """Register all built-in shaders.

    Material shaders are loaded from stdlib assets, not synthesized here.
    """
    return


def register_builtin_textures(rm: "ResourceManager") -> None:
    """Register built-in placeholder textures."""
    from termin.render.texture_asset import TextureAsset
    from termin.render.texture import get_normal_texture, get_white_texture

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
    """Register dependencies for builtin materials.

    Builtin material registration intentionally does not synthesize material
    assets. Standard materials live in ``resources/stdlib/materials`` and must
    be registered by the asset pipeline from their ``.material`` files.
    """
    register_builtin_shaders(rm)
    register_builtin_textures(rm)


def register_builtin_meshes(rm: "ResourceManager") -> List[str]:
    """
    Register built-in primitive meshes.

    Returns:
        List of registered mesh names.
    """
    from termin.default_assets.mesh.asset import MeshAsset
    from tmesh import (
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
    """Register all built-in resources (runtime shaders, textures, meshes, pipelines)."""
    register_builtin_shaders(rm)
    register_builtin_textures(rm)
    register_builtin_materials(rm)
    register_builtin_meshes(rm)
    register_default_pipeline(rm)
    register_triangle_pipeline(rm)
