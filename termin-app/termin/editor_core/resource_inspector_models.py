"""Toolkit-neutral models for texture, mesh and GLB asset inspectors."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import logging
import os
from pathlib import Path
from typing import Any, Callable


_logger = logging.getLogger(__name__)
ChangedHandler = Callable[[], None]


def format_file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024.0:.1f} KB"
    return f"{size / (1024.0 * 1024.0):.2f} MB"


@dataclass(frozen=True)
class TextureInspectorSnapshot:
    available: bool
    name: str = ""
    uuid: str = ""
    resolution: str = "—"
    channels: str = "—"
    file_size: str = "—"
    path: str = ""
    flip_x: bool = False
    flip_y: bool = True
    transpose: bool = False
    preview_pixels: Any = field(default=None, compare=False, repr=False)
    message: str = "No texture selected."


class TextureInspectorController:
    def __init__(self, resource_manager, *, changed: ChangedHandler | None = None) -> None:
        self._resource_manager = resource_manager
        self._changed = changed
        self._snapshot = TextureInspectorSnapshot(False)

    @property
    def snapshot(self) -> TextureInspectorSnapshot:
        return self._snapshot

    def set_target(
        self,
        texture,
        *,
        name: str = "",
        file_path: str | None = None,
    ) -> TextureInspectorSnapshot:
        if file_path:
            name = Path(file_path).stem
            texture = self._resource_manager.get_texture(name)
            if texture is None:
                try:
                    from termin.render.texture import Texture

                    texture = Texture.from_file(file_path)
                except Exception as exc:
                    _logger.error("Texture inspector failed to load '%s': %s", file_path, exc)
        if texture is None:
            self._snapshot = TextureInspectorSnapshot(
                False,
                name=name,
                path=file_path or "",
                message=f"Texture is not loaded: {file_path}" if file_path else "No texture selected.",
            )
            return self._snapshot

        from tgfx import TcTexture
        from termin.render.texture import Texture

        asset = self._resource_manager.get_texture_asset(name) if name else None
        if asset is None and isinstance(texture, Texture):
            asset = texture.asset
        source = str(asset.source_path) if asset is not None and asset.source_path is not None else ""
        flip_x = bool(asset.flip_x) if asset is not None else False
        flip_y = bool(asset.flip_y) if asset is not None else True
        transpose = bool(asset.transpose) if asset is not None else False
        width = height = channels = 0
        pixels = None
        if isinstance(texture, Texture):
            if texture._size is not None:
                width, height = texture._size
            pixels = texture._image_data
            source = source or str(texture.source_path or "")
            if asset is None:
                flip_x, flip_y, transpose = texture.flip_x, texture.flip_y, texture.transpose
        elif isinstance(texture, TcTexture):
            width, height, channels = texture.width, texture.height, texture.channels
            pixels = texture.data
            source = source or str(texture.source_path or "")
            if asset is None:
                flip_x, flip_y, transpose = texture.flip_x, texture.flip_y, texture.transpose
        if pixels is not None and len(pixels.shape) == 3:
            channels = int(pixels.shape[2])
        if asset is None and source:
            from termin.default_assets.render.texture_spec import TextureSpec

            spec = TextureSpec.for_texture_file(source)
            flip_x, flip_y, transpose = spec.flip_x, spec.flip_y, spec.transpose
        self._snapshot = TextureInspectorSnapshot(
            True,
            name=name,
            uuid=str(asset.uuid) if asset is not None else "",
            resolution=f"{width} × {height}" if width > 0 and height > 0 else "—",
            channels=str(channels) if channels > 0 else "—",
            file_size=format_file_size(os.path.getsize(source)) if source and os.path.exists(source) else "—",
            path=source,
            flip_x=bool(flip_x),
            flip_y=bool(flip_y),
            transpose=bool(transpose),
            preview_pixels=pixels,
            message="",
        )
        return self._snapshot

    def save_import_settings(self, *, flip_x: bool, flip_y: bool, transpose: bool) -> TextureInspectorSnapshot:
        if not self._snapshot.path:
            raise ValueError("texture import settings require a source path")
        from termin.default_assets.render.texture_spec import TextureSpec

        TextureSpec(flip_x=flip_x, flip_y=flip_y, transpose=transpose).save_for_texture(
            self._snapshot.path
        )
        self._snapshot = replace(
            self._snapshot,
            flip_x=flip_x,
            flip_y=flip_y,
            transpose=transpose,
        )
        if self._changed is not None:
            self._changed()
        return self._snapshot


@dataclass(frozen=True)
class MeshInspectorSnapshot:
    available: bool
    name: str = ""
    uuid: str = ""
    vertices: str = "—"
    triangles: str = "—"
    file_size: str = "—"
    path: str = ""
    scale: float = 1.0
    axis_x: str = "x"
    axis_y: str = "y"
    axis_z: str = "z"
    flip_uv_v: bool = False
    message: str = "No mesh selected."


class MeshInspectorController:
    AXIS_CHOICES = ("x", "y", "z", "-x", "-y", "-z")

    def __init__(self, resource_manager, *, changed: ChangedHandler | None = None) -> None:
        self._resource_manager = resource_manager
        self._changed = changed
        self._snapshot = MeshInspectorSnapshot(False)

    @property
    def snapshot(self) -> MeshInspectorSnapshot:
        return self._snapshot

    def set_target(self, mesh_asset, *, name: str = "", file_path: str | None = None) -> MeshInspectorSnapshot:
        if file_path:
            name = Path(file_path).stem
            mesh_asset = self._resource_manager.get_mesh_asset(name)
        if mesh_asset is None:
            self._snapshot = MeshInspectorSnapshot(
                False,
                name=name,
                path=file_path or "",
                message=f"Mesh is not loaded: {file_path}" if file_path else "No mesh selected.",
            )
            return self._snapshot
        from termin.default_assets.mesh.mesh_spec import MeshSpec

        source = str(mesh_asset.source_path) if mesh_asset.source_path is not None else ""
        spec = MeshSpec.for_mesh_file(source) if source else MeshSpec()
        self._snapshot = MeshInspectorSnapshot(
            True,
            name=name or str(mesh_asset.name or ""),
            uuid=str(mesh_asset.uuid or ""),
            vertices=f"{mesh_asset.get_vertex_count():,}",
            triangles=f"{mesh_asset.get_triangle_count():,}",
            file_size=format_file_size(os.path.getsize(source)) if source and os.path.exists(source) else "—",
            path=source,
            scale=float(spec.scale),
            axis_x=spec.axis_x,
            axis_y=spec.axis_y,
            axis_z=spec.axis_z,
            flip_uv_v=bool(spec.flip_uv_v),
            message="",
        )
        return self._snapshot

    def save_import_settings(
        self,
        *,
        scale: float,
        axis_x: str,
        axis_y: str,
        axis_z: str,
        flip_uv_v: bool,
    ) -> MeshInspectorSnapshot:
        if not self._snapshot.path:
            raise ValueError("mesh import settings require a source path")
        if any(axis not in self.AXIS_CHOICES for axis in (axis_x, axis_y, axis_z)):
            raise ValueError("invalid mesh import axis")
        from termin.default_assets.mesh.mesh_spec import MeshSpec

        MeshSpec(
            scale=float(scale),
            axis_x=axis_x,
            axis_y=axis_y,
            axis_z=axis_z,
            flip_uv_v=bool(flip_uv_v),
        ).save_for_mesh(self._snapshot.path)
        self._snapshot = replace(
            self._snapshot,
            scale=float(scale),
            axis_x=axis_x,
            axis_y=axis_y,
            axis_z=axis_z,
            flip_uv_v=bool(flip_uv_v),
        )
        if self._changed is not None:
            self._changed()
        return self._snapshot


@dataclass(frozen=True)
class GlbInspectorSnapshot:
    available: bool
    name: str = ""
    file_size: str = "—"
    path: str = ""
    meshes: str = "—"
    textures: str = "—"
    animations: str = "—"
    convert_to_z_up: bool = True
    normalize_scale: bool = False
    blender_z_up_fix: bool = False
    message: str = "No GLB selected."


class GlbInspectorController:
    def __init__(self, *, changed: ChangedHandler | None = None) -> None:
        self._changed = changed
        self._snapshot = GlbInspectorSnapshot(False)

    @property
    def snapshot(self) -> GlbInspectorSnapshot:
        return self._snapshot

    def set_target(self, glb_asset, *, name: str = "", file_path: str | None = None) -> GlbInspectorSnapshot:
        source = file_path or (
            str(glb_asset.source_path)
            if glb_asset is not None and glb_asset.source_path is not None
            else ""
        )
        if not source:
            self._snapshot = GlbInspectorSnapshot(False)
            return self._snapshot
        meshes = textures = animations = "—"
        try:
            from termin.glb.loader import load_glb_file

            data = load_glb_file(source)
            meshes, textures, animations = str(len(data.meshes)), str(len(data.textures)), str(len(data.animations))
        except Exception as exc:
            _logger.error("GLB inspector failed to load '%s': %s", source, exc)
        from termin.editor_core.project_file_watcher import FilePreLoader

        spec = FilePreLoader.read_spec_file(source) or {}
        self._snapshot = GlbInspectorSnapshot(
            True,
            name=name or Path(source).stem,
            file_size=format_file_size(os.path.getsize(source)) if os.path.exists(source) else "—",
            path=source,
            meshes=meshes,
            textures=textures,
            animations=animations,
            convert_to_z_up=bool(spec.get("convert_to_z_up", True)),
            normalize_scale=bool(spec.get("normalize_scale", False)),
            blender_z_up_fix=bool(spec.get("blender_z_up_fix", False)),
            message="",
        )
        return self._snapshot

    def save_import_settings(
        self,
        *,
        convert_to_z_up: bool,
        normalize_scale: bool,
        blender_z_up_fix: bool,
    ) -> GlbInspectorSnapshot:
        if not self._snapshot.path:
            raise ValueError("GLB import settings require a source path")
        from termin.editor_core.project_file_watcher import FilePreLoader

        spec = FilePreLoader.read_spec_file(self._snapshot.path) or {}
        spec.update(
            convert_to_z_up=bool(convert_to_z_up),
            normalize_scale=bool(normalize_scale),
            blender_z_up_fix=bool(blender_z_up_fix),
        )
        if not FilePreLoader.write_spec_file(self._snapshot.path, spec):
            raise OSError(f"failed to save GLB import settings for {self._snapshot.path}")
        self._snapshot = replace(
            self._snapshot,
            convert_to_z_up=bool(convert_to_z_up),
            normalize_scale=bool(normalize_scale),
            blender_z_up_fix=bool(blender_z_up_fix),
        )
        if self._changed is not None:
            self._changed()
        return self._snapshot


__all__ = [
    "GlbInspectorController",
    "GlbInspectorSnapshot",
    "MeshInspectorController",
    "MeshInspectorSnapshot",
    "TextureInspectorController",
    "TextureInspectorSnapshot",
    "format_file_size",
]
