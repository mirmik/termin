"""Default built-in runtime resource registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.default_assets.builtin_uuids import BUILTIN_TEXTURE_LEGACY_UUIDS, BUILTIN_UUIDS

if TYPE_CHECKING:
    from termin.default_assets.resource_api import DefaultAssetsResourceApiMixin


def register_builtin_shaders(rm: DefaultAssetsResourceApiMixin) -> None:
    """Register all built-in shaders.

    Material shaders are loaded from stdlib assets, not synthesized here.
    """
    return


def register_builtin_textures(rm: DefaultAssetsResourceApiMixin) -> None:
    """Register built-in placeholder textures."""
    from termin.default_assets.render.texture_asset import TextureAsset
    from termin.render.texture import get_normal_texture, get_white_texture
    from tgfx import TcTexture

    def register_legacy_texture_uuids(name: str, asset: TextureAsset) -> None:
        texture = asset.texture_data
        if texture is None or not texture.is_valid:
            return

        data = texture.data
        if data is None:
            return

        for legacy_uuid in BUILTIN_TEXTURE_LEGACY_UUIDS.get(name, ()):
            rm._assets_by_uuid[legacy_uuid] = asset
            if TcTexture.from_uuid(legacy_uuid).is_valid:
                continue

            TcTexture.from_data(
                data=data,
                width=texture.width,
                height=texture.height,
                channels=texture.channels,
                flip_x=texture.flip_x,
                flip_y=texture.flip_y,
                transpose=texture.transpose,
                name=name,
                source_path=texture.source_path or name,
                uuid=legacy_uuid,
            )

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
    white_asset = rm.get_texture_asset("__white_1x1__")
    if white_asset is not None:
        register_legacy_texture_uuids("__white_1x1__", white_asset)

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
    normal_asset = rm.get_texture_asset("__normal_1x1__")
    if normal_asset is not None:
        register_legacy_texture_uuids("__normal_1x1__", normal_asset)


def register_builtin_materials(rm: DefaultAssetsResourceApiMixin) -> None:
    """Register dependencies for built-in materials.

    Built-in material registration intentionally does not synthesize material
    assets. Standard materials live in ``resources/stdlib/materials`` and must
    be registered by the asset pipeline from their ``.material`` files.
    """
    register_builtin_shaders(rm)
    register_builtin_textures(rm)


def register_builtin_meshes(rm: DefaultAssetsResourceApiMixin) -> list[str]:
    """Register built-in primitive meshes."""
    from termin.default_assets.mesh.asset import MeshAsset
    from tmesh import CylinderMesh, PlaneMesh, TexturedCubeMesh, UVSphereMesh

    registered: list[str] = []

    if "Cube" not in rm._mesh_assets:
        cube = MeshAsset.from_mesh3(
            TexturedCubeMesh(size=1.0), name="Cube", uuid=BUILTIN_UUIDS["Cube"]
        )
        rm.register_mesh_asset("Cube", cube, uuid=BUILTIN_UUIDS["Cube"])
        registered.append("Cube")

    if "Sphere" not in rm._mesh_assets:
        sphere = MeshAsset.from_mesh3(
            UVSphereMesh(radius=0.5, n_meridians=32, n_parallels=16),
            name="Sphere",
            uuid=BUILTIN_UUIDS["Sphere"],
        )
        rm.register_mesh_asset("Sphere", sphere, uuid=BUILTIN_UUIDS["Sphere"])
        registered.append("Sphere")

    if "Plane" not in rm._mesh_assets:
        plane = MeshAsset.from_mesh3(
            PlaneMesh(width=1.0, height=1.0), name="Plane", uuid=BUILTIN_UUIDS["Plane"]
        )
        rm.register_mesh_asset("Plane", plane, uuid=BUILTIN_UUIDS["Plane"])
        registered.append("Plane")

    if "Cylinder" not in rm._mesh_assets:
        cylinder = MeshAsset.from_mesh3(
            CylinderMesh(radius=0.5, height=1.0), name="Cylinder", uuid=BUILTIN_UUIDS["Cylinder"]
        )
        rm.register_mesh_asset("Cylinder", cylinder, uuid=BUILTIN_UUIDS["Cylinder"])
        registered.append("Cylinder")

    return registered


def register_default_pipeline(rm: DefaultAssetsResourceApiMixin) -> None:
    """Default pipeline is created by native RenderingManager on demand."""
    return


def register_triangle_pipeline(rm: DefaultAssetsResourceApiMixin) -> None:
    """Register built-in diagnostic triangle render pipeline."""
    if rm.get_pipeline_asset("Triangle") is not None:
        return

    from termin.render_framework import RenderPipeline
    from termin.render_passes import DebugTrianglePass

    pipeline = RenderPipeline(
        name="Triangle",
        _init_passes=[
            DebugTrianglePass(output_res="OUTPUT", pass_name="DebugTriangle"),
        ],
    )
    rm.register_pipeline("Triangle", pipeline, uuid=BUILTIN_UUIDS.get("TrianglePipeline"))


def register_all_builtins(rm: DefaultAssetsResourceApiMixin) -> None:
    """Register all built-in resources."""
    register_builtin_shaders(rm)
    register_builtin_textures(rm)
    register_builtin_materials(rm)
    register_builtin_meshes(rm)
    register_default_pipeline(rm)
    register_triangle_pipeline(rm)


__all__ = [
    "register_all_builtins",
    "register_builtin_materials",
    "register_builtin_meshes",
    "register_builtin_shaders",
    "register_builtin_textures",
    "register_default_pipeline",
    "register_triangle_pipeline",
]
