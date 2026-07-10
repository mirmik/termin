"""Native navigation agent and NavMesh area settings dialogs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import weakref

from termin.editor_core.navigation_settings_model import (
    NavigationAgentSnapshot,
    NavigationSettingsController,
    NavigationSettingsSnapshot,
)
from termin.gui_native import DialogAction, Document, EdgeInsets, Rect, Size, WidgetRef

from .dialog_service import NativeDialogService


def _ref(document: Document, widget) -> WidgetRef:
    return widget if isinstance(widget, WidgetRef) else document.ref(widget.handle)


def _row(document: Document, label: str, control) -> WidgetRef:
    row = document.create_hstack(f"navigation-{label.lower().replace(' ', '-')}")
    row.set_layout_spacing(6.0)
    row.add_fixed_child(document.create_label(label), 110.0)
    row.add_stretch_child(_ref(document, control))
    return row


def _set_agents(combo, snapshot: NavigationSettingsSnapshot) -> None:
    combo.clear()
    for agent in snapshot.agents:
        combo.add_item(agent.name)


@dataclass
class NativeAgentTypesDialog:
    document: Document
    controller: NavigationSettingsController
    dialog_service: NativeDialogService
    dialog: object
    agents: object
    name: object
    radius: object
    height: object
    max_slope: object
    step_height: object
    remove_button: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    _updating: bool = False
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native agent types dialog is closed")
        if self.dialog.open:
            return False
        self.apply_snapshot(self.controller.revert(), 0)
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def apply_snapshot(self, snapshot: NavigationSettingsSnapshot, index: int) -> None:
        index = min(max(index, 0), len(snapshot.agents) - 1)
        agent = snapshot.agents[index]
        self._updating = True
        try:
            _set_agents(self.agents, snapshot)
            self.agents.selected_index = index
            self.name.text = agent.name
            self.radius.value = agent.radius
            self.height.value = agent.height
            self.max_slope.value = agent.max_slope
            self.step_height.value = agent.step_height
            self.remove_button.widget.enabled = len(snapshot.agents) > 1
        finally:
            self._updating = False
        self.request_render()

    def select(self, index: int) -> None:
        if not self._updating and 0 <= index < len(self.controller.snapshot.agents):
            self.apply_snapshot(self.controller.snapshot, index)

    def update_selected(self, *, strict: bool = False) -> None:
        if self._updating:
            return
        index = self.agents.selected_index
        if index < 0:
            return
        try:
            snapshot = self.controller.update_agent(
                index,
                NavigationAgentSnapshot(
                    self.name.text,
                    self.radius.value,
                    self.height.value,
                    self.max_slope.value,
                    self.step_height.value,
                ),
            )
        except ValueError:
            if strict:
                raise
            return
        self.apply_snapshot(snapshot, index)

    def add(self) -> None:
        index, snapshot = self.controller.add_agent()
        self.apply_snapshot(snapshot, index)

    def remove(self) -> None:
        index = self.agents.selected_index
        try:
            snapshot = self.controller.remove_agent(index)
        except (IndexError, ValueError) as error:
            self.dialog_service.show_error("Agent Types", str(error))
            return
        self.apply_snapshot(snapshot, min(index, len(snapshot.agents) - 1))

    def save(self) -> None:
        try:
            self.update_selected(strict=True)
            self.controller.save()
        except (RuntimeError, ValueError) as error:
            self.dialog_service.show_error("Agent Types", f"Save failed: {error}")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


@dataclass
class NativeNavMeshAreasDialog:
    document: Document
    controller: NavigationSettingsController
    dialog_service: NativeDialogService
    dialog: object
    names: object
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    _closed: bool = False

    def show(self) -> bool:
        if self._closed:
            raise RuntimeError("native NavMesh areas dialog is closed")
        if self.dialog.open:
            return False
        self.names.text = "\n".join(self.controller.revert().area_names)
        shown = self.dialog.show(self.viewport())
        if shown:
            self.request_render()
        return shown

    def save(self) -> None:
        values = self.names.text.split("\n")[:64]
        values.extend("" for _ in range(64 - len(values)))
        try:
            self.controller.set_area_names(tuple(values))
            self.controller.save()
        except (RuntimeError, ValueError) as error:
            self.dialog_service.show_error("NavMesh Areas", f"Save failed: {error}")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.dialog.open:
            self.dialog.close()
        if self.document.is_alive(self.dialog.handle):
            self.document.destroy_widget_recursive(self.dialog.handle)


def build_native_agent_types_dialog(document, controller, *, dialog_service, viewport, request_render):
    root = document.create_vstack("native-agent-types")
    root.stable_id = "editor.agent-types"
    root.preferred_size = Size(520.0, 360.0)
    root.set_layout_padding(EdgeInsets(8.0, 8.0, 8.0, 8.0))
    root.set_layout_spacing(6.0)
    agents = document.create_combo_box()
    root.add_fixed_child(_row(document, "Agent", agents), 30.0)
    action_row = document.create_hstack("agent-actions")
    action_row.set_layout_spacing(4.0)
    add_button = document.create_button("Add")
    remove_button = document.create_button("Remove")
    action_row.add_fixed_child(_ref(document, add_button), 80.0)
    action_row.add_fixed_child(_ref(document, remove_button), 80.0)
    root.add_fixed_child(action_row, 30.0)
    name = document.create_text_input()
    radius = document.create_spin_box()
    height = document.create_spin_box()
    max_slope = document.create_spin_box()
    step_height = document.create_spin_box()
    for control, minimum, maximum, step, decimals in (
        (radius, 0.1, 10.0, 0.1, 2),
        (height, 0.1, 20.0, 0.1, 2),
        (max_slope, 0.0, 90.0, 1.0, 1),
        (step_height, 0.0, 5.0, 0.05, 2),
    ):
        control.set_range(minimum, maximum)
        control.step = step
        control.decimals = decimals
    for label, control in (
        ("Name", name), ("Radius", radius), ("Height", height),
        ("Max Slope", max_slope), ("Step Height", step_height),
    ):
        root.add_fixed_child(_row(document, label, control), 30.0)
    dialog = document.create_dialog("Agent Types")
    dialog.actions = [
        DialogAction("ok", "OK", is_default=True),
        DialogAction("cancel", "Cancel", is_cancel=True),
    ]
    dialog.set_content(root)
    result = NativeAgentTypesDialog(
        document, controller, dialog_service, dialog, agents, name, radius, height,
        max_slope, step_height, remove_button, viewport, request_render,
    )
    owner = weakref.ref(result)
    agents.connect_changed(lambda index, _text: owner().select(index) if owner() is not None else None)
    for control in (name, radius, height, max_slope, step_height):
        control.connect_changed(lambda *_args: owner().update_selected() if owner() is not None else None)
    add_button.connect_clicked(lambda: owner().add() if owner() is not None else None)
    remove_button.connect_clicked(lambda: owner().remove() if owner() is not None else None)
    dialog.connect_finished(
        lambda value: owner().save()
        if owner() is not None and value.action_id == "ok"
        else None
    )
    return result


def build_native_navmesh_areas_dialog(document, controller, *, dialog_service, viewport, request_render):
    root = document.create_vstack("native-navmesh-areas")
    root.stable_id = "editor.navmesh-areas"
    root.preferred_size = Size(520.0, 620.0)
    root.set_layout_padding(EdgeInsets(8.0, 8.0, 8.0, 8.0))
    root.set_layout_spacing(4.0)
    root.add_fixed_child(document.create_label("Area names, one per line (indices 0-63)"), 24.0)
    names = document.create_text_area()
    root.add_stretch_child(_ref(document, names))
    dialog = document.create_dialog("NavMesh Areas")
    dialog.actions = [
        DialogAction("ok", "OK", is_default=True),
        DialogAction("cancel", "Cancel", is_cancel=True),
    ]
    dialog.set_content(root)
    result = NativeNavMeshAreasDialog(
        document, controller, dialog_service, dialog, names, viewport, request_render
    )
    owner = weakref.ref(result)
    dialog.connect_finished(
        lambda value: owner().save()
        if owner() is not None and value.action_id == "ok"
        else None
    )
    return result


def connect_navigation_settings_command(menu_bar, command_id: int, dialog) -> None:
    owner = weakref.ref(dialog)

    def activated(_menu_index: int, activated_id: int, _command) -> None:
        current = owner()
        if activated_id == command_id and current is not None:
            current.show()

    menu_bar.connect_activated(activated)


__all__ = [
    "NativeAgentTypesDialog", "NativeNavMeshAreasDialog",
    "build_native_agent_types_dialog", "build_native_navmesh_areas_dialog",
    "connect_navigation_settings_command",
]
