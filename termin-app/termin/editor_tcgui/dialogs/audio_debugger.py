"""Audio Debugger dialog — shows audio engine status and active channels."""

from __future__ import annotations

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.group_box import GroupBox
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.button import Button
from tcgui.widgets.units import px

from termin.editor_core.audio_debugger_model import create_audio_debugger_controller


def show_audio_debugger(ui) -> None:
    """Show audio debugger dialog."""
    controller = create_audio_debugger_controller()
    content = VStack()
    content.spacing = 8

    # --- Engine status ---
    status_group = GroupBox()
    status_group.title = "Audio Engine"

    def _make_status_row(label_text: str) -> tuple[HStack, Label]:
        row = HStack()
        row.spacing = 8
        lbl = Label()
        lbl.text = label_text
        row.add_child(lbl)
        val = Label()
        val.text = "—"
        row.add_child(val)
        return row, val

    engine_row, engine_status = _make_status_row("Status:")
    volume_row, volume_status = _make_status_row("Master Volume:")
    channels_row, channels_status = _make_status_row("Active Channels:")

    status_group.add_child(engine_row)
    status_group.add_child(volume_row)
    status_group.add_child(channels_row)
    content.add_child(status_group)

    # --- Active channels ---
    channels_group = GroupBox()
    channels_group.title = "Active Channels"

    channels_list = ListWidget()
    channels_list.item_height = 24
    channels_list.stretch = True
    channels_list.preferred_height = px(200)
    channels_list.empty_text = "No active channels"
    channels_group.add_child(channels_list)
    content.add_child(channels_group)

    def _refresh():
        snapshot = controller.snapshot()
        if not snapshot.initialized:
            engine_status.text = "Not initialized"
            volume_status.text = "—"
            channels_status.text = "—"
            channels_list.set_items([])
            return

        engine_status.text = "Initialized"

        volume_status.text = f"{snapshot.master_volume * 100:.0f}%"
        items = [
            {
                "text": (
                    f"Ch {channel.channel}  {'Paused' if channel.paused else 'Playing'}  "
                    f"Vol: {channel.volume * 100:.0f}%  Angle: {channel.angle}\u00b0  "
                    f"Dist: {channel.distance}"
                )
            }
            for channel in snapshot.channels
        ]

        channels_status.text = f"{len(snapshot.channels)} / {snapshot.total_channels}"
        channels_list.set_items(items)

    # Refresh button
    btn_row = HStack()
    btn_row.spacing = 4
    refresh_btn = Button()
    refresh_btn.text = "Refresh"
    refresh_btn.padding = 6
    refresh_btn.on_click = _refresh
    btn_row.add_child(refresh_btn)
    content.add_child(btn_row)

    _refresh()

    dlg = Dialog()
    dlg.title = "Audio Debugger"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 450

    dlg.show(ui, windowed=True)
