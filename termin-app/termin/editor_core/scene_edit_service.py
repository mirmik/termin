"""Public, undo-aware local transform editing for editor automation."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from tcbase import log

from termin.editor_core.editor_commands import TransformEditCommand
from termin.geombase import GeneralPose3, Quat, Vec3
from termin.scene import Entity


class EditorSceneEditService:
    """Edits entity local transforms through the active editor undo handler.

    This is deliberately a narrow editor-automation surface. It keeps scripts
    out of editor implementation details while preserving exactly the same
    undo/redo command contract used by the transform inspector.
    """

    def __init__(
        self,
        *,
        get_selected_entity: Callable[[], Entity | None],
        push_undo_command: Callable[[TransformEditCommand, bool], None],
        request_viewport_update: Callable[[], None],
    ) -> None:
        self._get_selected_entity = get_selected_entity
        self._push_undo_command = push_undo_command
        self._request_viewport_update = request_viewport_update

    def set_selected_local_transform(
        self,
        *,
        position: Vec3 | Sequence[float] | None = None,
        rotation: Quat | Sequence[float] | None = None,
        scale: Vec3 | Sequence[float] | None = None,
        merge: bool = False,
    ) -> dict[str, object]:
        """Set selected entity's local pose and return its resulting state.

        ``position`` and ``scale`` are ``Vec3`` or three finite numeric values.
        ``rotation`` is ``Quat`` or four finite numeric values in ``x, y, z, w``
        order. Omitted fields retain their current local values.
        """
        return self._set_local_transform(
            self._get_selected_entity(),
            position=position,
            rotation=rotation,
            scale=scale,
            merge=merge,
            target_label="selected entity",
        )

    def set_entity_local_transform(
        self,
        entity: Entity | None,
        *,
        position: Vec3 | Sequence[float] | None = None,
        rotation: Quat | Sequence[float] | None = None,
        scale: Vec3 | Sequence[float] | None = None,
        merge: bool = False,
    ) -> dict[str, object]:
        """Set an explicit entity's local pose and return its resulting state."""
        return self._set_local_transform(
            entity,
            position=position,
            rotation=rotation,
            scale=scale,
            merge=merge,
            target_label="entity",
        )

    def _set_local_transform(
        self,
        entity: Entity | None,
        *,
        position: Vec3 | Sequence[float] | None,
        rotation: Quat | Sequence[float] | None,
        scale: Vec3 | Sequence[float] | None,
        merge: bool,
        target_label: str,
    ) -> dict[str, object]:
        if not isinstance(merge, bool):
            self._fail("merge must be a boolean")
        if entity is None or not entity.valid():
            self._fail(f"Cannot edit local transform: {target_label} is unavailable")
        if entity.transform is None:
            self._fail(f"Cannot edit local transform: {target_label} has no transform")

        old_pose = entity.transform.local_pose()
        new_pose = GeneralPose3(
            lin=_coerce_vec3(position, "position", old_pose.lin),
            ang=_coerce_quat(rotation, old_pose.ang),
            scale=_coerce_vec3(scale, "scale", old_pose.scale),
        )
        changed = _pose_changed(old_pose, new_pose)
        if changed:
            command = TransformEditCommand(entity.transform, old_pose, new_pose)
            try:
                self._push_undo_command(command, merge)
            except Exception as exc:
                log.error(
                    "[EditorSceneEditService] failed to push local transform edit for %s: %s",
                    target_label,
                    exc,
                    exc_info=True,
                )
                raise RuntimeError("Unable to record local transform edit in editor undo history") from exc
            try:
                self._request_viewport_update()
            except Exception as exc:
                log.error(
                    "[EditorSceneEditService] failed to request viewport update after local transform edit: %s",
                    exc,
                    exc_info=True,
                )
                raise RuntimeError("Local transform edit applied but viewport refresh failed") from exc

        result_pose = entity.transform.local_pose()
        return {
            "entity_uuid": entity.uuid,
            "local_space": True,
            "changed": changed,
            "position": _vec3_tuple(result_pose.lin),
            "rotation": _quat_tuple(result_pose.ang),
            "scale": _vec3_tuple(result_pose.scale),
        }

    @staticmethod
    def _fail(message: str) -> None:
        log.error("[EditorSceneEditService] %s", message)
        raise RuntimeError(message)


def _coerce_vec3(
    value: Vec3 | Sequence[float] | None,
    name: str,
    current: Vec3,
) -> Vec3:
    if value is None:
        components = _vec3_tuple(current)
    elif isinstance(value, Vec3):
        components = _vec3_tuple(value)
    elif isinstance(value, (list, tuple)) and len(value) == 3:
        components = tuple(float(component) for component in value)
    else:
        EditorSceneEditService._fail(
            f"{name} must be Vec3 or a list/tuple of three finite numbers"
        )
    if not all(math.isfinite(component) for component in components):
        EditorSceneEditService._fail(f"{name} must contain only finite numbers")
    return Vec3(*components)


def _coerce_quat(value: Quat | Sequence[float] | None, current: Quat) -> Quat:
    if value is None:
        components = _quat_tuple(current)
    elif isinstance(value, Quat):
        components = _quat_tuple(value)
    elif isinstance(value, (list, tuple)) and len(value) == 4:
        components = tuple(float(component) for component in value)
    else:
        EditorSceneEditService._fail(
            "rotation must be Quat or a list/tuple of four finite x, y, z, w values"
        )
    if not all(math.isfinite(component) for component in components):
        EditorSceneEditService._fail("rotation must contain only finite numbers")
    if math.isclose(sum(component * component for component in components), 0.0):
        EditorSceneEditService._fail("rotation must not be the zero quaternion")
    return Quat(*components).normalized()


def _pose_changed(old_pose: GeneralPose3, new_pose: GeneralPose3) -> bool:
    return (
        _vec3_tuple(old_pose.lin) != _vec3_tuple(new_pose.lin)
        or _quat_tuple(old_pose.ang) != _quat_tuple(new_pose.ang)
        or _vec3_tuple(old_pose.scale) != _vec3_tuple(new_pose.scale)
    )


def _vec3_tuple(value: Vec3) -> tuple[float, float, float]:
    return (float(value[0]), float(value[1]), float(value[2]))


def _quat_tuple(value: Quat) -> tuple[float, float, float, float]:
    return (float(value.x), float(value.y), float(value.z), float(value.w))


__all__ = ["EditorSceneEditService"]
