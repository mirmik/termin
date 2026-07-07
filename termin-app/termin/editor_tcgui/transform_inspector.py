"""TransformInspector for tcgui editor."""

from __future__ import annotations

import math
from typing import Callable, Optional

from tcgui.widgets.vstack import VStack
from tcgui.widgets.label import Label
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.units import px

from termin.kinematic.general_transform import GeneralTransform3
from termin.scene import Entity
from termin.geombase import GeneralPose3, Quat, Vec3
from termin.editor_core.undo_stack import UndoCommand
from termin.editor_core.editor_commands import TransformEditCommand


class TransformInspector(VStack):
    """tcgui widget for editing transform (position/rotation/scale)."""

    def __init__(self) -> None:
        super().__init__()
        self.spacing = 4

        self._transform: Optional[GeneralTransform3] = None
        self._updating_from_model: bool = False
        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None
        self.on_transform_changed: Optional[Callable[[], None]] = None
        self._row_labels: list[Label] = []
        self._compact_mode: bool = False
        self._labels_hide_threshold: float = 320.0

        self._grid = GridLayout(columns=4)
        self._grid.column_spacing = 4
        self._grid.row_spacing = 4
        self._grid.set_column_stretch(1, 1.0)
        self._grid.set_column_stretch(2, 1.0)
        self._grid.set_column_stretch(3, 1.0)
        self.add_child(self._grid)

        self._pos = self._add_vec3_row(0, "Position")
        self._rot = self._add_vec3_row(1, "Rotation (deg)")
        self._scale = self._add_vec3_row(2, "Scale")

        for sb in (*self._pos, *self._rot, *self._scale):
            sb.on_changed = self._on_value_changed

        self._set_enabled(False)

    def _add_vec3_row(self, row: int, label_text: str) -> tuple[SpinBox, SpinBox, SpinBox]:
        lbl = Label()
        lbl.text = label_text
        lbl.preferred_width = px(92)
        self._grid.add(lbl, row, 0)
        self._row_labels.append(lbl)

        spinboxes: list[SpinBox] = []
        for col in range(3):
            sb = SpinBox()
            sb.decimals = 3
            sb.step = 0.1
            sb.min_value = -1e6
            sb.max_value = 1e6
            sb.preferred_width = px(74)
            self._grid.add(sb, row, col + 1)
            spinboxes.append(sb)
        return (spinboxes[0], spinboxes[1], spinboxes[2])

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float) -> None:
        compact = width < self._labels_hide_threshold
        if compact != self._compact_mode:
            self._compact_mode = compact
            for lbl in self._row_labels:
                lbl.visible = not compact
        super().layout(x, y, width, height, viewport_w, viewport_h)

    def set_undo_command_handler(self, handler: Optional[Callable[[UndoCommand, bool], None]]) -> None:
        self._push_undo_command = handler

    def set_target(self, obj: Optional[object]) -> None:
        if isinstance(obj, Entity):
            transform = obj.transform
        elif isinstance(obj, GeneralTransform3):
            transform = obj
        else:
            transform = None

        self._transform = transform
        self._update_from_transform()

    def refresh_transform(self) -> None:
        self._update_from_transform()

    def _set_enabled(self, flag: bool) -> None:
        for sb in (*self._pos, *self._rot, *self._scale):
            sb.enabled = flag

    def _update_from_transform(self) -> None:
        self._updating_from_model = True
        try:
            if self._transform is None:
                self._set_enabled(False)
                for sb in (*self._pos, *self._rot, *self._scale):
                    sb.value = 0.0
                for sb in self._scale:
                    sb.value = 1.0
                return

            self._set_enabled(True)
            pose: GeneralPose3 = self._transform.local_pose()

            px, py, pz = pose.lin
            az, ay, ax = self._quat_to_euler_zyx(pose.ang)

            self._pos[0].value = float(px)
            self._pos[1].value = float(py)
            self._pos[2].value = float(pz)

            self._rot[0].value = float(ax)
            self._rot[1].value = float(ay)
            self._rot[2].value = float(az)

            s = pose.scale
            self._scale[0].value = float(s[0])
            self._scale[1].value = float(s[1])
            self._scale[2].value = float(s[2])
        finally:
            self._updating_from_model = False

    def _on_value_changed(self, _value: float) -> None:
        if self._updating_from_model or self._transform is None:
            return

        old_pose: GeneralPose3 = self._transform.local_pose()

        new_lin = Vec3(
            self._pos[0].value, self._pos[1].value, self._pos[2].value,
        )

        ax, ay, az = self._rot[0].value, self._rot[1].value, self._rot[2].value
        new_ang = self._euler_zyx_to_quat(az, ay, ax)

        new_scale = Vec3(
            self._scale[0].value, self._scale[1].value, self._scale[2].value,
        )

        new_pose = GeneralPose3(lin=new_lin, ang=new_ang, scale=new_scale)

        if self._push_undo_command is not None:
            cmd = TransformEditCommand(
                transform=self._transform,
                old_pose=old_pose,
                new_pose=new_pose,
            )
            self._push_undo_command(cmd, True)
        else:
            self._transform.relocate(new_pose)

        if self.on_transform_changed is not None:
            self.on_transform_changed()

    # ------------------------------------------------------------------
    # Math helpers
    # ------------------------------------------------------------------

    def _euler_zyx_to_quat(self, z_degrees: float, y_degrees: float, x_degrees: float) -> Quat:
        qz = Quat.from_axis_angle(Vec3.unit_z(), math.radians(z_degrees))
        qy = Quat.from_axis_angle(Vec3.unit_y(), math.radians(y_degrees))
        qx = Quat.from_axis_angle(Vec3.unit_x(), math.radians(x_degrees))
        return (qz * qy * qx).normalized()

    def _quat_to_euler_zyx(self, quat: Quat) -> tuple[float, float, float]:
        x, y, z, w = quat.x, quat.y, quat.z, quat.w

        t0 = 2.0 * (w * z + x * y)
        t1 = 1.0 - 2.0 * (y * y + z * z)
        Z = math.degrees(math.atan2(t0, t1))

        t2 = 2.0 * (w * y - z * x)
        t2 = max(-1.0, min(1.0, t2))
        Y = math.degrees(math.asin(t2))

        t3 = 2.0 * (w * x + y * z)
        t4 = 1.0 - 2.0 * (x * x + y * y)
        X = math.degrees(math.atan2(t3, t4))

        return (Z, Y, X)
