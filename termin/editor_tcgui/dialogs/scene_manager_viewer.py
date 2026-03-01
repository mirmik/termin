"""Scene Manager Viewer — shows all scenes, modes, entity counts, and actions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tcgui.widgets.dialog import Dialog
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.button import Button
from tcgui.widgets.units import px

from termin.editor.scene_manager import SceneMode

if TYPE_CHECKING:
    from termin.editor.scene_manager import SceneManager


def show_scene_manager_viewer(
    ui,
    scene_manager: "SceneManager",
    get_rendering_controller=None,
    get_editor_attachment=None,
    on_scene_edited=None,
) -> None:
    """Show scene manager viewer dialog.

    Parameters
    ----------
    ui : UI
    scene_manager : SceneManager
    get_rendering_controller : callable returning RenderingControllerTcgui or None
    get_editor_attachment : callable returning EditorSceneAttachment or None
    on_scene_edited : callable(scene_name) called after editor is attached to a new scene
    """
    from tcbase import log

    selected_name: list[str | None] = [None]

    content = VStack()
    content.spacing = 4

    # Main area: list + details
    main_row = HStack()
    main_row.spacing = 8
    main_row.preferred_height = px(350)

    # Left: scene list
    left = VStack()
    left.spacing = 4
    left.preferred_width = px(300)
    left.stretch = True

    left_lbl = Label()
    left_lbl.text = "Scenes"
    left_lbl.font_size = 14
    left.add_child(left_lbl)

    scene_list = ListWidget()
    scene_list.item_height = 28
    scene_list.stretch = True
    left.add_child(scene_list)
    main_row.add_child(left)

    # Right: details
    right = VStack()
    right.spacing = 4
    right.stretch = True

    right_lbl = Label()
    right_lbl.text = "Scene Details"
    right_lbl.font_size = 14
    right.add_child(right_lbl)

    details = TextArea()
    details.read_only = True
    details.word_wrap = False
    details.stretch = True
    details.placeholder = "Select a scene to view details"
    right.add_child(details)
    main_row.add_child(right)

    content.add_child(main_row)

    # Status
    status_lbl = Label()
    status_lbl.text = ""
    content.add_child(status_lbl)

    # --- Action buttons ---
    actions_row = HStack()
    actions_row.spacing = 4

    def _make_action_btn(text: str) -> Button:
        btn = Button()
        btn.text = text
        btn.padding = 6
        btn.enabled = False
        return btn

    unload_btn = _make_action_btn("Unload")
    duplicate_btn = _make_action_btn("Duplicate")
    inactive_btn = _make_action_btn("Inactive")
    stop_btn = _make_action_btn("Stop")
    play_btn = _make_action_btn("Play")
    attach_btn = _make_action_btn("Attach")
    detach_btn = _make_action_btn("Detach")
    edit_btn = _make_action_btn("Edit")

    actions_row.add_child(unload_btn)
    actions_row.add_child(duplicate_btn)

    sep1 = Label()
    sep1.text = "|"
    actions_row.add_child(sep1)

    actions_row.add_child(inactive_btn)
    actions_row.add_child(stop_btn)
    actions_row.add_child(play_btn)

    sep2 = Label()
    sep2.text = "|"
    actions_row.add_child(sep2)

    actions_row.add_child(attach_btn)
    actions_row.add_child(detach_btn)

    sep3 = Label()
    sep3.text = "|"
    actions_row.add_child(sep3)

    actions_row.add_child(edit_btn)

    content.add_child(actions_row)

    # Refresh button
    btn_row = HStack()
    btn_row.spacing = 4
    refresh_btn = Button()
    refresh_btn.text = "Refresh"
    refresh_btn.padding = 6
    btn_row.add_child(refresh_btn)
    content.add_child(btn_row)

    # --- Logic ---

    def _update_action_buttons():
        has_sel = selected_name[0] is not None
        unload_btn.enabled = has_sel
        duplicate_btn.enabled = has_sel
        inactive_btn.enabled = has_sel
        stop_btn.enabled = has_sel
        play_btn.enabled = has_sel
        attach_btn.enabled = has_sel
        detach_btn.enabled = has_sel
        edit_btn.enabled = has_sel

    def _refresh():
        scene_list.set_items([])
        details.text = ""

        items = []
        for name in sorted(scene_manager.scene_names()):
            scene = scene_manager.get_scene(name)
            if scene is None:
                continue
            mode = scene_manager.get_mode(name)
            path = scene_manager.get_scene_path(name)
            entity_count = len(list(scene.entities))

            if path:
                import os
                display = f"{os.path.splitext(os.path.basename(path))[0]} [{name}]"
            else:
                display = f"{name} (unsaved)"

            mode_str = mode.name if mode else "?"
            items.append({
                "text": f"{display}  mode={mode_str}  entities={entity_count}",
                "data": name,
            })

        scene_list.set_items(items)

        # Update status
        total = len(items)
        total_entities = 0
        play_count = 0
        for name in scene_manager.scene_names():
            scene = scene_manager.get_scene(name)
            if scene:
                total_entities += len(list(scene.entities))
            mode = scene_manager.get_mode(name)
            if mode == SceneMode.PLAY:
                play_count += 1

        status_lbl.text = f"Scenes: {total} | Entities: {total_entities} | Playing: {play_count}"

        if selected_name[0] is not None:
            _update_details(selected_name[0])

    def _update_details(name: str):
        scene = scene_manager.get_scene(name)
        if scene is None:
            details.text = f"Scene '{name}' not found"
            return

        mode = scene_manager.get_mode(name)
        path = scene_manager.get_scene_path(name)
        handle = scene.scene_handle()

        # Check editing
        is_editing = False
        if get_editor_attachment is not None:
            attachment = get_editor_attachment()
            if attachment is not None and attachment.scene is scene:
                is_editing = True

        lines = [
            f"Name: {name}",
            f"Handle: {handle[0]}:{handle[1]} (index:generation)",
            f"Mode: {mode.name if mode else '?'}",
            f"Path: {path or '(unsaved)'}",
            f"Editing: {'YES' if is_editing else 'no'}",
            "",
            "=== Entities ===",
        ]

        entity_count = 0
        root_entities = []
        for entity in scene.entities:
            entity_count += 1
            if entity.transform.parent is None:
                root_entities.append(entity)

        lines.append(f"Total: {entity_count}")
        lines.append(f"Root entities: {len(root_entities)}")
        lines.append("")

        for entity in root_entities[:20]:
            serializable = "S" if entity.serializable else "-"
            enabled = "E" if entity.enabled else "-"
            lines.append(f"  [{serializable}{enabled}] {entity.name}")

        if len(root_entities) > 20:
            lines.append(f"  ... and {len(root_entities) - 20} more")

        details.text = "\n".join(lines)

    def _on_select(idx, item):
        name = item.get("data")
        selected_name[0] = name
        _update_action_buttons()
        if name is not None:
            _update_details(name)

    scene_list.on_select = _on_select

    def _on_unload():
        if selected_name[0] is None:
            return
        from tcgui.widgets.message_box import MessageBox
        MessageBox.show_confirm(
            ui,
            "Confirm Unload",
            f"Close scene '{selected_name[0]}'?\nUnsaved changes will be lost.",
            on_result=lambda yes: _do_unload() if yes else None,
        )

    def _do_unload():
        try:
            scene_manager.close_scene(selected_name[0])
            selected_name[0] = None
            _update_action_buttons()
            _refresh()
        except Exception as e:
            log.error(f"Failed to close scene: {e}")

    unload_btn.on_click = _on_unload

    def _on_duplicate():
        if selected_name[0] is None:
            return
        from tcgui.widgets.input_dialog import show_input_dialog
        show_input_dialog(
            ui,
            title="Duplicate Scene",
            label=f"Enter name for copy of '{selected_name[0]}':",
            initial_text=f"{selected_name[0]}_copy",
            on_result=_do_duplicate,
        )

    def _do_duplicate(new_name: str | None):
        if new_name is None or not new_name.strip():
            return
        new_name = new_name.strip()
        if scene_manager.has_scene(new_name):
            log.error(f"Scene '{new_name}' already exists")
            return
        try:
            scene_manager.copy_scene(selected_name[0], new_name)
            _refresh()
        except Exception as e:
            log.error(f"Failed to duplicate scene: {e}")

    duplicate_btn.on_click = _on_duplicate

    def _set_mode(mode: SceneMode):
        if selected_name[0] is None:
            return
        try:
            scene_manager.set_mode(selected_name[0], mode)
            _refresh()
        except Exception as e:
            log.error(f"Failed to set mode: {e}")

    inactive_btn.on_click = lambda: _set_mode(SceneMode.INACTIVE)
    stop_btn.on_click = lambda: _set_mode(SceneMode.STOP)
    play_btn.on_click = lambda: _set_mode(SceneMode.PLAY)

    def _on_attach():
        if selected_name[0] is None:
            return
        rc = get_rendering_controller() if get_rendering_controller else None
        if rc is None:
            log.error("RenderingController not available")
            return
        scene = scene_manager.get_scene(selected_name[0])
        if scene is None:
            return
        try:
            rc.attach_scene(scene)
            _refresh()
        except Exception as e:
            log.error(f"Failed to attach scene: {e}")

    attach_btn.on_click = _on_attach

    def _on_detach():
        if selected_name[0] is None:
            return
        rc = get_rendering_controller() if get_rendering_controller else None
        if rc is None:
            log.error("RenderingController not available")
            return
        scene = scene_manager.get_scene(selected_name[0])
        if scene is None:
            return
        try:
            rc.detach_scene(scene)
            _refresh()
        except Exception as e:
            log.error(f"Failed to detach scene: {e}")

    detach_btn.on_click = _on_detach

    def _on_edit():
        if selected_name[0] is None:
            return
        attachment = get_editor_attachment() if get_editor_attachment else None
        if attachment is None:
            log.error("EditorSceneAttachment not available")
            return
        scene = scene_manager.get_scene(selected_name[0])
        if scene is None:
            return
        if attachment.scene is scene:
            return
        try:
            attachment.attach(scene, transfer_camera_state=True)
            scene_manager.set_mode(selected_name[0], SceneMode.STOP)
            if on_scene_edited is not None:
                on_scene_edited(selected_name[0])
            _refresh()
        except Exception as e:
            log.error(f"Failed to attach editor: {e}")

    edit_btn.on_click = _on_edit
    refresh_btn.on_click = _refresh

    _refresh()

    dlg = Dialog()
    dlg.title = "Scene Manager"
    dlg.content = content
    dlg.buttons = ["Close"]
    dlg.default_button = "Close"
    dlg.cancel_button = "Close"
    dlg.min_width = 700

    dlg.show(ui)
