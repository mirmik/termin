"""Transform gizmo orientation toolbar state for EditorWindowTcgui."""

from __future__ import annotations

from typing import Callable, Literal

from tcbase import log

GizmoOrientationMode = Literal["local", "world"]


class GizmoModeUiController:
    def __init__(
        self,
        *,
        get_interaction_system: Callable[[], object | None],
        request_viewport_update: Callable[[], None],
    ) -> None:
        self._get_interaction_system = get_interaction_system
        self._request_viewport_update = request_viewport_update
        self._orientation_button = None
        self._orientation_mode: GizmoOrientationMode = "local"

    @property
    def orientation_mode(self) -> GizmoOrientationMode:
        return self._orientation_mode

    def set_widgets(self, *, orientation_button) -> None:
        self._orientation_button = orientation_button
        self._apply_button_state()
        self._apply_gizmo_state()

    def toggle_orientation_mode(self) -> None:
        mode: GizmoOrientationMode = (
            "world" if self._orientation_mode == "local" else "local"
        )
        self.set_orientation_mode(mode)

    def set_orientation_mode(self, mode: GizmoOrientationMode) -> None:
        if mode not in ("local", "world"):
            log.error(f"[GizmoModeUi] invalid orientation mode: {mode!r}")
            raise ValueError("Transform gizmo orientation mode must be 'local' or 'world'")

        if self._orientation_mode == mode:
            return

        self._orientation_mode = mode
        self._apply_button_state()
        self._apply_gizmo_state()
        self._request_viewport_update()

    def sync_to_interaction_system(self) -> None:
        self._apply_gizmo_state()

    def _apply_button_state(self) -> None:
        if self._orientation_button is None:
            return

        from tcgui.widgets.theme import current_theme as theme

        if self._orientation_mode == "world":
            self._orientation_button.text = "World"
            self._orientation_button.background_color = theme.accent
        else:
            self._orientation_button.text = "Local"
            self._orientation_button.background_color = theme.bg_surface

    def _apply_gizmo_state(self) -> None:
        interaction_system = self._get_interaction_system()
        if interaction_system is None:
            return
        transform_gizmo = interaction_system.transform_gizmo
        if transform_gizmo is None:
            return
        transform_gizmo.set_orientation_mode(self._orientation_mode)
