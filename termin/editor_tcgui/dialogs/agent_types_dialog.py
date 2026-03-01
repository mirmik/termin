"""Agent Types dialog — configure navigation agent types."""

from __future__ import annotations

from typing import Callable

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.group_box import GroupBox
from tcgui.widgets.units import px


def show_agent_types_dialog(
    ui,
    on_changed: Callable[[], None] | None = None,
) -> None:
    """Show agent types configuration dialog."""
    from termin.navmesh.settings import AgentType, NavigationSettingsManager

    manager = NavigationSettingsManager.instance()
    current_index = [-1]
    updating = [False]

    content = HStack()
    content.spacing = 8
    content.preferred_height = px(300)

    # --- Left panel: list + add/remove ---
    left = VStack()
    left.spacing = 4
    left.preferred_width = px(150)

    agent_list = ListWidget()
    agent_list.item_height = 24
    agent_list.stretch = True
    left.add_child(agent_list)

    btn_row = HStack()
    btn_row.spacing = 4
    add_btn = Button()
    add_btn.text = "+"
    add_btn.preferred_width = px(30)
    add_btn.padding = 4

    remove_btn = Button()
    remove_btn.text = "-"
    remove_btn.preferred_width = px(30)
    remove_btn.padding = 4
    btn_row.add_child(add_btn)
    btn_row.add_child(remove_btn)
    left.add_child(btn_row)

    content.add_child(left)

    # --- Right panel: properties ---
    props_group = GroupBox()
    props_group.title = "Agent Properties"
    props_group.stretch = True

    name_row = HStack()
    name_row.spacing = 8
    name_lbl = Label()
    name_lbl.text = "Name:"
    name_row.add_child(name_lbl)
    name_input = TextInput()
    name_input.placeholder = "Agent name"
    name_input.stretch = True
    name_row.add_child(name_input)
    props_group.add_child(name_row)

    def _make_spin_row(label_text: str, min_val: float, max_val: float,
                       step: float, decimals: int) -> tuple[HStack, SpinBox]:
        row = HStack()
        row.spacing = 8
        lbl = Label()
        lbl.text = label_text
        row.add_child(lbl)
        spin = SpinBox()
        spin.min_value = min_val
        spin.max_value = max_val
        spin.step = step
        spin.decimals = decimals
        spin.stretch = True
        row.add_child(spin)
        return row, spin

    radius_row, radius_spin = _make_spin_row("Radius:", 0.1, 10.0, 0.1, 2)
    height_row, height_spin = _make_spin_row("Height:", 0.1, 20.0, 0.1, 2)
    slope_row, slope_spin = _make_spin_row("Max Slope:", 0.0, 90.0, 1.0, 1)
    step_row, step_spin = _make_spin_row("Step Height:", 0.0, 5.0, 0.05, 2)

    props_group.add_child(radius_row)
    props_group.add_child(height_row)
    props_group.add_child(slope_row)
    props_group.add_child(step_row)

    content.add_child(props_group)

    # --- Logic ---
    def _load_list():
        items = []
        for agent in manager.settings.agent_types:
            items.append({"text": agent.name})
        agent_list.set_items(items)
        if agent_list.items and current_index[0] < 0:
            current_index[0] = 0
            agent_list.selected_index = 0
            _load_agent(0)

    def _load_agent(idx: int):
        if idx < 0 or idx >= len(manager.settings.agent_types):
            current_index[0] = -1
            return
        current_index[0] = idx
        agent = manager.settings.agent_types[idx]
        updating[0] = True
        name_input.text = agent.name
        radius_spin.value = agent.radius
        height_spin.value = agent.height
        slope_spin.value = agent.max_slope
        step_spin.value = agent.step_height
        updating[0] = False

    def _on_select(idx, item):
        _load_agent(idx)

    agent_list.on_select = _on_select

    def _on_property_changed(_=None):
        if updating[0] or current_index[0] < 0:
            return
        agent = AgentType(
            name=name_input.text,
            radius=radius_spin.value,
            height=height_spin.value,
            max_slope=slope_spin.value,
            step_height=step_spin.value,
        )
        manager.update_agent_type(current_index[0], agent)
        # Update list item text
        items = agent_list.items
        if 0 <= current_index[0] < len(items):
            items[current_index[0]]["text"] = agent.name
            agent_list.set_items(items)
            agent_list.selected_index = current_index[0]

    name_input.on_text_changed = _on_property_changed
    radius_spin.on_value_changed = _on_property_changed
    height_spin.on_value_changed = _on_property_changed
    slope_spin.on_value_changed = _on_property_changed
    step_spin.on_value_changed = _on_property_changed

    def _on_add():
        base_name = "New Agent"
        name = base_name
        counter = 1
        existing = manager.settings.get_agent_type_names()
        while name in existing:
            name = f"{base_name} {counter}"
            counter += 1
        agent = AgentType(name=name)
        manager.add_agent_type(agent)
        _load_list()
        new_idx = len(manager.settings.agent_types) - 1
        agent_list.selected_index = new_idx
        _load_agent(new_idx)

    add_btn.on_click = _on_add

    def _on_remove():
        if current_index[0] < 0:
            return
        if len(manager.settings.agent_types) <= 1:
            from tcgui.widgets.message_box import MessageBox
            MessageBox.show_info(ui, "Cannot Remove",
                                 "At least one agent type must exist.")
            return
        manager.remove_agent_type(current_index[0])
        new_idx = min(current_index[0], len(manager.settings.agent_types) - 1)
        current_index[0] = new_idx
        _load_list()
        if new_idx >= 0:
            agent_list.selected_index = new_idx
            _load_agent(new_idx)

    remove_btn.on_click = _on_remove

    _load_list()

    # --- Dialog ---
    dlg = Dialog()
    dlg.title = "Agent Types"
    dlg.content = content
    dlg.buttons = ["OK", "Cancel"]
    dlg.default_button = "OK"
    dlg.cancel_button = "Cancel"
    dlg.min_width = 500

    def _on_result(btn):
        if btn == "OK":
            manager.save()
            if on_changed is not None:
                on_changed()

    dlg.on_result = _on_result
    dlg.show(ui)
