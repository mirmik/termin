"""GLB inspector for tcgui."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.label import Label
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.button import Button
from tcgui.widgets.separator import Separator
from tcgui.widgets.units import px

from termin.editor.project_file_watcher import FilePreLoader


class GLBInspectorTcgui(VStack):
    """Inspector for GLB files."""

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4
        self._rm = resource_manager

        self._file_path = ""
        self._updating = False
        self.on_changed: Optional[Callable[[], None]] = None

        title = Label(); title.text = "GLB Inspector"; self.add_child(title)
        self._subtitle = Label(); self._subtitle.color = (0.62, 0.66, 0.74, 1.0); self.add_child(self._subtitle)
        self.add_child(Separator())

        grid = GridLayout(columns=2)
        grid.column_spacing = 4
        grid.row_spacing = 4
        grid.set_column_stretch(1, 1.0)
        self.add_child(grid)

        def add_info(row: int, text: str):
            k = Label(); k.text = text; k.preferred_width = px(110)
            v = Label(); v.color = (0.70, 0.72, 0.76, 1.0)
            grid.add(k, row, 0); grid.add(v, row, 1)
            return v

        self._name_v = add_info(0, "Name:")
        self._size_v = add_info(1, "File size:")
        self._path_v = add_info(2, "Path:")
        self._meshes_v = add_info(3, "Meshes:")
        self._textures_v = add_info(4, "Textures:")
        self._anims_v = add_info(5, "Animations:")

        self.add_child(Separator())

        self._convert_z_up = Checkbox()
        self._normalize_scale = Checkbox()
        self._blender_fix = Checkbox()

        self.add_child(self._check_row("Convert to Z-Up:", self._convert_z_up))
        self.add_child(self._check_row("Normalize Scale:", self._normalize_scale))
        self.add_child(self._check_row("Blender Z-Up Fix:", self._blender_fix))

        self._apply = Button(); self._apply.text = "Apply && Reimport"; self._apply.on_click = self._on_apply
        self.add_child(self._apply)

        self._empty = Label(); self._empty.text = "No GLB selected."; self._empty.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty)
        self._set_visible_state(False)

    def _check_row(self, label_text: str, cb: Checkbox) -> HStack:
        row = HStack(); row.spacing = 6
        lbl = Label(); lbl.text = label_text; lbl.preferred_width = px(110)
        row.add_child(lbl); row.add_child(cb)
        spacer = Label(); spacer.stretch = True; row.add_child(spacer)
        return row

    def set_glb_by_path(self, file_path: str) -> None:
        self._updating = True
        try:
            self._set_visible_state(True)
            self._file_path = file_path
            self._subtitle.text = f"File: {file_path}"

            p = Path(file_path)
            self._name_v.text = p.stem
            if p.exists():
                self._size_v.text = self._format_size(p.stat().st_size)
            else:
                self._size_v.text = "-"
            self._path_v.text = file_path

            try:
                from termin.loaders.glb_loader import load_glb_file
                data = load_glb_file(file_path)
                self._meshes_v.text = str(len(data.meshes))
                self._textures_v.text = str(len(data.textures))
                self._anims_v.text = str(len(data.animations))
            except Exception as e:
                log.error(f"[GLBInspectorTcgui] load_glb_file failed: {e}")
                self._meshes_v.text = "-"
                self._textures_v.text = "-"
                self._anims_v.text = "-"

            spec_data = FilePreLoader.read_spec_file(file_path) or {}
            self._convert_z_up.checked = bool(spec_data.get("convert_to_z_up", True))
            self._normalize_scale.checked = bool(spec_data.get("normalize_scale", False))
            self._blender_fix.checked = bool(spec_data.get("blender_z_up_fix", False))
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def set_glb_asset(self, glb_asset, name: str = "") -> None:
        if glb_asset is None or glb_asset.source_path is None:
            self._set_visible_state(False)
            return
        self.set_glb_by_path(str(glb_asset.source_path))
        if name:
            self._subtitle.text = f"GLB: {name}"

    def _set_visible_state(self, has_glb: bool) -> None:
        self._name_v.visible = has_glb
        self._size_v.visible = has_glb
        self._path_v.visible = has_glb
        self._meshes_v.visible = has_glb
        self._textures_v.visible = has_glb
        self._anims_v.visible = has_glb
        self._convert_z_up.visible = has_glb
        self._normalize_scale.visible = has_glb
        self._blender_fix.visible = has_glb
        self._apply.visible = has_glb
        self._empty.visible = not has_glb

    def _on_apply(self) -> None:
        if self._updating or not self._file_path:
            return
        spec_data = FilePreLoader.read_spec_file(self._file_path) or {}
        spec_data["convert_to_z_up"] = bool(self._convert_z_up.checked)
        spec_data["normalize_scale"] = bool(self._normalize_scale.checked)
        spec_data["blender_z_up_fix"] = bool(self._blender_fix.checked)
        ok = FilePreLoader.write_spec_file(self._file_path, spec_data)
        if not ok:
            log.error(f"[GLBInspectorTcgui] failed to save spec for {self._file_path}")
            return
        if self.on_changed is not None:
            self.on_changed()

    @staticmethod
    def _format_size(size: int) -> str:
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024.0:.1f} KB"
        return f"{size / (1024.0 * 1024.0):.2f} MB"
