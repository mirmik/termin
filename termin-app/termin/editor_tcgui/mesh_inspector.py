"""Mesh inspector for tcgui."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.label import Label
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.button import Button
from tcgui.widgets.separator import Separator
from tcgui.widgets.units import px

from termin.loaders.mesh_spec import MeshSpec


class MeshInspectorTcgui(VStack):
    """Inspector for mesh assets and mesh import settings."""

    _AXIS_ITEMS = ["x", "y", "z", "-x", "-y", "-z"]

    def __init__(self, resource_manager) -> None:
        super().__init__()
        self.spacing = 4
        self._rm = resource_manager

        self._mesh_asset = None
        self._file_path = ""
        self._updating = False
        self.on_changed: Optional[Callable[[], None]] = None

        title = Label(); title.text = "Mesh Inspector"; self.add_child(title)
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
        self._uuid_v = add_info(1, "UUID:")
        self._verts_v = add_info(2, "Vertices:")
        self._tris_v = add_info(3, "Triangles:")
        self._size_v = add_info(4, "File size:")
        self._path_v = add_info(5, "Path:")

        self.add_child(Separator())

        self._scale = SpinBox()
        self._scale.decimals = 4
        self._scale.step = 0.1
        self._scale.min_value = 0.0001
        self._scale.max_value = 10000.0

        self._axis_x = ComboBox(); self._axis_y = ComboBox(); self._axis_z = ComboBox()
        for item in self._AXIS_ITEMS:
            self._axis_x.add_item(item)
            self._axis_y.add_item(item)
            self._axis_z.add_item(item)

        self._flip_uv_v = Checkbox()
        self._apply = Button(); self._apply.text = "Apply && Save"; self._apply.on_click = self._on_apply

        def row(label_text: str, widget):
            line = HStack(); line.spacing = 6
            lbl = Label(); lbl.text = label_text; lbl.preferred_width = px(110)
            line.add_child(lbl); line.add_child(widget)
            spacer = Label(); spacer.stretch = True; line.add_child(spacer)
            self.add_child(line)

        row("Scale:", self._scale)
        row("Axis X:", self._axis_x)
        row("Axis Y:", self._axis_y)
        row("Axis Z:", self._axis_z)
        row("Flip UV V:", self._flip_uv_v)
        self.add_child(self._apply)

        self._empty = Label(); self._empty.text = "No mesh selected."; self._empty.color = (0.52, 0.56, 0.62, 1.0)
        self.add_child(self._empty)
        self._set_visible_state(False)

    def set_mesh(self, mesh_asset, name: str = "") -> None:
        self._mesh_asset = mesh_asset

        self._updating = True
        try:
            if mesh_asset is None:
                self._set_visible_state(False)
                self._subtitle.text = "No mesh selected."
                self._file_path = ""
                return

            self._set_visible_state(True)
            self._subtitle.text = f"Mesh: {name}" if name else "Mesh"
            self._name_v.text = name or mesh_asset.name or "-"
            self._uuid_v.text = mesh_asset.uuid or "-"
            self._verts_v.text = f"{mesh_asset.get_vertex_count():,}"
            self._tris_v.text = f"{mesh_asset.get_triangle_count():,}"

            src = str(mesh_asset.source_path) if mesh_asset.source_path is not None else ""
            self._file_path = src
            if src and os.path.exists(src):
                self._size_v.text = self._format_size(os.path.getsize(src))
                self._path_v.text = src
                self._load_spec(src)
            else:
                self._size_v.text = "-"
                self._path_v.text = src or "-"
                self._reset_spec()
        finally:
            self._updating = False
            if self._ui is not None:
                self._ui.request_layout()

    def set_mesh_by_path(self, file_path: str) -> None:
        name = Path(file_path).stem
        asset = self._rm.get_mesh_asset(name)
        if asset is None:
            self._set_visible_state(False)
            self._subtitle.text = f"File: {file_path}"
            return
        self.set_mesh(asset, name)

    def _set_visible_state(self, has_mesh: bool) -> None:
        self._name_v.visible = has_mesh
        self._uuid_v.visible = has_mesh
        self._verts_v.visible = has_mesh
        self._tris_v.visible = has_mesh
        self._size_v.visible = has_mesh
        self._path_v.visible = has_mesh
        self._scale.visible = has_mesh
        self._axis_x.visible = has_mesh
        self._axis_y.visible = has_mesh
        self._axis_z.visible = has_mesh
        self._flip_uv_v.visible = has_mesh
        self._apply.visible = has_mesh
        self._empty.visible = not has_mesh

    def _load_spec(self, mesh_path: str) -> None:
        spec = MeshSpec.for_mesh_file(mesh_path)
        self._scale.value = float(spec.scale)
        self._select_axis(self._axis_x, spec.axis_x)
        self._select_axis(self._axis_y, spec.axis_y)
        self._select_axis(self._axis_z, spec.axis_z)
        self._flip_uv_v.checked = bool(spec.flip_uv_v)

    def _reset_spec(self) -> None:
        self._scale.value = 1.0
        self._select_axis(self._axis_x, "x")
        self._select_axis(self._axis_y, "y")
        self._select_axis(self._axis_z, "z")
        self._flip_uv_v.checked = False

    def _select_axis(self, combo: ComboBox, value: str) -> None:
        combo.selected_index = -1
        for i in range(combo.item_count):
            if combo.item_text(i) == value:
                combo.selected_index = i
                return

    def _on_apply(self) -> None:
        if self._updating or not self._file_path:
            return
        spec = MeshSpec(
            scale=float(self._scale.value),
            axis_x=self._axis_x.selected_text or "x",
            axis_y=self._axis_y.selected_text or "y",
            axis_z=self._axis_z.selected_text or "z",
            flip_uv_v=bool(self._flip_uv_v.checked),
        )
        try:
            spec.save_for_mesh(self._file_path)
        except Exception as e:
            log.error(f"[MeshInspectorTcgui] save spec failed: {e}")
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
