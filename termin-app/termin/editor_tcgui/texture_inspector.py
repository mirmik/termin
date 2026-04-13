"""Texture inspector for tcgui."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional, Any

import numpy as np

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.separator import Separator
from tcgui.widgets.widget import Widget
from tcgui.widgets.units import px

from termin.loaders.texture_spec import TextureSpec


class _TexturePreview(Widget):
    def __init__(self) -> None:
        super().__init__()
        self.preferred_width = px(180)
        self.preferred_height = px(120)
        self._image_data: np.ndarray | None = None
        self._gpu_texture = None
        self._dirty = False

    def set_image(self, data: Any) -> None:
        self._image_data = None
        self._dirty = True
        if data is None:
            return
        try:
            arr = np.asarray(data)
            if arr.ndim != 3:
                return
            if arr.shape[2] == 4:
                self._image_data = np.ascontiguousarray(arr.astype(np.uint8))
            elif arr.shape[2] == 3:
                alpha = np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)
                self._image_data = np.ascontiguousarray(np.concatenate([arr.astype(np.uint8), alpha], axis=2))
        except Exception as e:
            log.error(f"[TextureInspectorTcgui] preview conversion failed: {e}")

    def _sync(self, renderer) -> None:
        if not self._dirty:
            return
        self._dirty = False
        if self._gpu_texture is not None:
            try:
                self._gpu_texture.delete()
            except Exception as e:
                log.error(f"[TextureInspectorTcgui] preview texture delete failed: {e}")
            self._gpu_texture = None
        if self._image_data is not None:
            try:
                self._gpu_texture = renderer.upload_texture(self._image_data)
            except Exception as e:
                log.error(f"[TextureInspectorTcgui] preview texture upload failed: {e}")

    def render(self, renderer) -> None:
        self._sync(renderer)
        renderer.draw_rect(self.x, self.y, self.width, self.height, (0.16, 0.17, 0.20, 1.0))
        renderer.draw_rect_outline(self.x, self.y, self.width, self.height, (0.34, 0.36, 0.42, 1.0), 1.0)
        if self._gpu_texture is None:
            renderer.draw_text_centered(self.x + self.width * 0.5, self.y + self.height * 0.5,
                                        "No Preview", (0.58, 0.60, 0.66, 1.0), 11.0)
            return
        renderer.draw_image(self.x + 2, self.y + 2, self.width - 4, self.height - 4, self._gpu_texture)


class TextureInspectorTcgui(VStack):
    """Inspector for texture properties and import settings."""

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4

        self._rm = resource_manager
        self._texture = None
        self._name = ""
        self._file_path = ""
        self._updating = False
        self.on_changed: Optional[Callable[[], None]] = None

        title = Label()
        title.text = "Texture Inspector"
        self.add_child(title)

        self._subtitle = Label()
        self._subtitle.color = (0.62, 0.66, 0.74, 1.0)
        self.add_child(self._subtitle)
        self.add_child(Separator())

        self._preview = _TexturePreview()
        self.add_child(self._preview)

        grid = GridLayout(columns=2)
        grid.column_spacing = 4
        grid.row_spacing = 4
        grid.set_column_stretch(1, 1.0)
        self.add_child(grid)

        def add_info_row(row: int, label: str):
            lbl = Label(); lbl.text = label; lbl.preferred_width = px(96)
            val = Label(); val.color = (0.70, 0.72, 0.76, 1.0)
            grid.add(lbl, row, 0); grid.add(val, row, 1)
            return val

        self._name_v = add_info_row(0, "Name:")
        self._uuid_v = add_info_row(1, "UUID:")
        self._res_v = add_info_row(2, "Resolution:")
        self._channels_v = add_info_row(3, "Channels:")
        self._size_v = add_info_row(4, "File size:")
        self._path_v = add_info_row(5, "Path:")

        self.add_child(Separator())

        self._flip_x = Checkbox(); self._flip_x.on_changed = lambda _v: self._save_spec_and_reload()
        self._flip_y = Checkbox(); self._flip_y.on_changed = lambda _v: self._save_spec_and_reload()
        self._transpose = Checkbox(); self._transpose.on_changed = lambda _v: self._save_spec_and_reload()

        fx = HStack(); fx.spacing = 6; l = Label(); l.text = "Flip X:"; l.preferred_width = px(96); fx.add_child(l); fx.add_child(self._flip_x); fx.add_child(Label()); fx.children[-1].stretch = True
        fy = HStack(); fy.spacing = 6; l = Label(); l.text = "Flip Y:"; l.preferred_width = px(96); fy.add_child(l); fy.add_child(self._flip_y); fy.add_child(Label()); fy.children[-1].stretch = True
        tr = HStack(); tr.spacing = 6; l = Label(); l.text = "Transpose:"; l.preferred_width = px(96); tr.add_child(l); tr.add_child(self._transpose); tr.add_child(Label()); tr.children[-1].stretch = True
        self.add_child(fx); self.add_child(fy); self.add_child(tr)

        self._empty = Label()
        self._empty.text = "No texture selected."
        self._empty.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty)

        self._set_visible_state(False)

    def set_texture(self, texture, name: str = "") -> None:
        self._texture = texture
        self._name = name

        self._updating = True
        try:
            if texture is None:
                self._set_visible_state(False)
                self._subtitle.text = "No texture selected."
                self._preview.set_image(None)
                return

            self._set_visible_state(True)
            self._subtitle.text = f"Texture: {name}" if name else "Texture"
            self._name_v.text = name or "-"

            asset = self._rm.get_texture_asset(name) if name else None
            self._uuid_v.text = asset.uuid if asset is not None else "-"

            if texture._size is not None:
                self._res_v.text = f"{texture._size[0]} x {texture._size[1]}"
            else:
                self._res_v.text = "-"

            if texture._image_data is not None and len(texture._image_data.shape) == 3:
                self._channels_v.text = str(texture._image_data.shape[2])
            else:
                self._channels_v.text = "-"

            src = texture.source_path
            self._file_path = src or ""
            if src and os.path.exists(src):
                self._size_v.text = self._format_size(os.path.getsize(src))
                self._path_v.text = src
            else:
                self._size_v.text = "-"
                self._path_v.text = src or "-"

            self._flip_x.checked = bool(texture.flip_x)
            self._flip_y.checked = bool(texture.flip_y)
            self._transpose.checked = bool(texture.transpose)

            self._preview.set_image(texture._image_data)
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def set_texture_by_path(self, file_path: str) -> None:
        name = Path(file_path).stem
        texture = self._rm.get_texture(name)
        if texture is None:
            try:
                from termin.visualization.render.texture import Texture
                texture = Texture.from_file(file_path)
            except Exception as e:
                log.error(f"[TextureInspectorTcgui] set_texture_by_path failed: {e}")
                texture = None
        self.set_texture(texture, name)

    def _set_visible_state(self, has_texture: bool) -> None:
        self._preview.visible = has_texture
        self._name_v.visible = has_texture
        self._uuid_v.visible = has_texture
        self._res_v.visible = has_texture
        self._channels_v.visible = has_texture
        self._size_v.visible = has_texture
        self._path_v.visible = has_texture
        self._flip_x.visible = has_texture
        self._flip_y.visible = has_texture
        self._transpose.visible = has_texture
        self._empty.visible = not has_texture

    def _save_spec_and_reload(self) -> None:
        if self._updating or not self._file_path:
            return
        spec = TextureSpec(
            flip_x=self._flip_x.checked,
            flip_y=self._flip_y.checked,
            transpose=self._transpose.checked,
        )
        spec.save_for_texture(self._file_path)
        if self.on_changed is not None:
            self.on_changed()

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024.0:.1f} KB"
        return f"{size / (1024.0 * 1024.0):.2f} MB"
