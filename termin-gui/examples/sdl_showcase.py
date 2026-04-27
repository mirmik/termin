"""tcgui Widget Showcase — демонстрация всех базовых виджетов.

Запуск: python3 examples/sdl_showcase.py
"""

import ctypes
import sdl2
from sdl2 import video

from tcbase import Key, MouseButton

from tcgui.widgets.ui import UI
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.checkbox import Checkbox
from tcgui.widgets.icon_button import IconButton
from tcgui.widgets.separator import Separator
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.table_widget import TableWidget, TableColumn
from tcgui.widgets.tree import TreeWidget, TreeNode
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.slider import Slider
from tcgui.widgets.spin_box import SpinBox
from tcgui.widgets.slider_edit import SliderEdit
from tcgui.widgets.progress_bar import ProgressBar
from tcgui.widgets.panel import Panel
from tcgui.widgets.group_box import GroupBox
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.splitter import Splitter
from tcgui.widgets.tabs import TabView
from tcgui.widgets.menu import MenuItem, Menu
from tcgui.widgets.menu_bar import MenuBar
from tcgui.widgets.tool_bar import ToolBar
from tcgui.widgets.status_bar import StatusBar
from tcgui.widgets.message_box import MessageBox, Buttons
from tcgui.widgets.input_dialog import show_input_dialog
from tcgui.widgets.color_dialog import ColorDialog
from tcgui.widgets.file_dialog_overlay import (
    show_open_file_dialog,
    show_save_file_dialog,
    show_open_directory_dialog,
)
from tcgui.widgets.units import px, pct
from tcgui.widgets.theme import current_theme as _t
from tcgui.widgets.frame_time_graph import FrameTimeGraph

from termin.display import BackendWindow
from tgfx import Tgfx2Context


# ── SDL helpers ──────────────────────────────────────────────────────────

_KEY_MAP = {
    sdl2.SDL_SCANCODE_BACKSPACE: Key.BACKSPACE,
    sdl2.SDL_SCANCODE_DELETE: Key.DELETE,
    sdl2.SDL_SCANCODE_LEFT: Key.LEFT,
    sdl2.SDL_SCANCODE_RIGHT: Key.RIGHT,
    sdl2.SDL_SCANCODE_UP: Key.UP,
    sdl2.SDL_SCANCODE_DOWN: Key.DOWN,
    sdl2.SDL_SCANCODE_HOME: Key.HOME,
    sdl2.SDL_SCANCODE_END: Key.END,
    sdl2.SDL_SCANCODE_RETURN: Key.ENTER,
    sdl2.SDL_SCANCODE_ESCAPE: Key.ESCAPE,
    sdl2.SDL_SCANCODE_TAB: Key.TAB,
    sdl2.SDL_SCANCODE_SPACE: Key.SPACE,
}

_BTN_MAP = {1: MouseButton.LEFT, 2: MouseButton.MIDDLE, 3: MouseButton.RIGHT}


def _translate_key(scancode):
    if scancode in _KEY_MAP:
        return _KEY_MAP[scancode]
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            pass
    return Key.UNKNOWN


def _translate_mods(sdl_mods):
    from tcbase import Mods
    result = 0
    if sdl_mods & (sdl2.KMOD_LSHIFT | sdl2.KMOD_RSHIFT):
        result |= Mods.SHIFT.value
    if sdl_mods & (sdl2.KMOD_LCTRL | sdl2.KMOD_RCTRL):
        result |= Mods.CTRL.value
    if sdl_mods & (sdl2.KMOD_LALT | sdl2.KMOD_RALT):
        result |= Mods.ALT.value
    return result


def _translate_button(sdl_button):
    return _BTN_MAP.get(sdl_button, MouseButton.LEFT)


# ── Helpers ──────────────────────────────────────────────────────────────


def _section_label(text):
    lbl = Label()
    lbl.text = text
    lbl.font_size = 15
    lbl.color = (0.5, 0.7, 1.0, 1.0)
    return lbl


# ── Tab pages ────────────────────────────────────────────────────────────


def make_basic_page(status_bar):
    page = VStack()
    page.spacing = 10
    page.alignment = "left"

    page.add_child(_section_label("Label"))
    lbl = Label()
    lbl.text = "Simple text label"
    lbl.font_size = 14
    page.add_child(lbl)

    muted = Label()
    muted.text = "Muted text label"
    muted.font_size = 12
    muted.color = _t.text_muted
    page.add_child(muted)

    page.add_child(_section_label("Button"))
    btn_row = HStack()
    btn_row.spacing = 8
    btn_row.alignment = "center"
    btn1 = Button()
    btn1.text = "Normal"
    btn1.padding = 8
    btn1.on_click = lambda: status_bar.show_message("Normal clicked")
    btn_row.add_child(btn1)
    btn2 = Button()
    btn2.text = "Disabled"
    btn2.padding = 8
    btn2.enabled = False
    btn_row.add_child(btn2)
    page.add_child(btn_row)

    page.add_child(_section_label("Checkbox"))
    cb_row = HStack()
    cb_row.spacing = 16
    cb_row.alignment = "center"
    cb1 = Checkbox()
    cb1.label = "Option A"
    cb1.checked = True
    cb_row.add_child(cb1)
    cb2 = Checkbox()
    cb2.label = "Option B"
    cb_row.add_child(cb2)
    cb3 = Checkbox()
    cb3.label = "Disabled"
    cb3.enabled = False
    cb_row.add_child(cb3)

    cb_status = Label()
    cb_status.text = "Option A: on | Option B: off"
    cb_status.font_size = 12
    cb_status.color = _t.text_muted

    def on_cb(*_):
        cb_status.text = f"Option A: {'on' if cb1.checked else 'off'} | Option B: {'on' if cb2.checked else 'off'}"

    cb1.on_change = on_cb
    cb2.on_change = on_cb

    page.add_child(cb_row)
    page.add_child(cb_status)

    page.add_child(_section_label("IconButton"))
    ib_row = HStack()
    ib_row.spacing = 8
    ib_row.alignment = "center"
    for icon, tip in [("✂", "Cut"), ("⎘", "Open"), ("✔", "OK")]:
        ib = IconButton()
        ib.icon = icon
        ib.tooltip = tip
        ib.on_click = lambda t=tip: status_bar.show_message(f"{t} clicked")
        ib_row.add_child(ib)
    page.add_child(ib_row)

    page.add_child(_section_label("TextInput"))
    ti = TextInput()
    ti.placeholder = "Type something..."
    ti.preferred_width = px(300)
    ti_status = Label()
    ti_status.text = 'Text: ""'
    ti_status.font_size = 12
    ti_status.color = _t.text_muted
    ti.on_change = lambda v: setattr(ti_status, 'text', f'Text: "{v}"')
    page.add_child(ti)
    page.add_child(ti_status)

    page.add_child(_section_label("Separator"))
    page.add_child(Separator())
    s_lbl = Label()
    s_lbl.text = "Content above and below separator"
    page.add_child(s_lbl)
    page.add_child(Separator())

    return page


def make_lists_page():
    page = VStack()
    page.spacing = 10
    page.alignment = "left"

    page.add_child(_section_label("ListWidget"))
    lst = ListWidget()
    lst.preferred_width = px(300)
    lst.preferred_height = px(160)
    lst.set_items([
        {"text": "Item Alpha", "subtitle": "First item"},
        {"text": "Item Beta", "subtitle": "Second item"},
        {"text": "Item Gamma", "subtitle": "Third item"},
        {"text": "Item Delta", "subtitle": "Fourth item"},
        {"text": "Item Epsilon", "subtitle": "Fifth item"},
        {"text": "Item Zeta", "subtitle": "Sixth item"},
    ])
    lst_status = Label()
    lst_status.text = "Selected: (none)"
    lst_status.font_size = 12
    lst_status.color = _t.text_muted
    lst.on_select = lambda i, d: setattr(lst_status, 'text', f"Selected: {d.get('text', '?')}")
    page.add_child(lst)
    page.add_child(lst_status)

    page.add_child(_section_label("ComboBox"))
    cb = ComboBox()
    cb.preferred_width = px(250)
    cb.items = ["Option 1", "Option 2", "Option 3", "Option 4"]
    cb.selected_index = 0
    cb_status = Label()
    cb_status.text = "ComboBox: Option 1"
    cb_status.font_size = 12
    cb_status.color = _t.text_muted
    cb.on_changed = lambda i, s: setattr(cb_status, 'text', f"ComboBox: {s}")
    page.add_child(cb)
    page.add_child(cb_status)

    page.add_child(_section_label("TableWidget"))
    tbl = TableWidget()
    tbl.preferred_width = px(400)
    tbl.preferred_height = px(160)
    tbl.set_columns([
        TableColumn("Name"),
        TableColumn("Type", 80),
        TableColumn("Size", 80),
    ])
    rows = []
    data = []
    for name, typ, size in [
        ("config.json", "JSON", "2.1 KB"),
        ("model.glb", "GLB", "4.3 MB"),
        ("texture.png", "PNG", "512 KB"),
        ("scene.termin", "Termin", "128 KB"),
        ("shader.glsl", "GLSL", "3.4 KB"),
    ]:
        rows.append([name, typ, size])
        data.append(name)
    tbl.set_rows(rows, data)
    page.add_child(tbl)

    page.add_child(_section_label("TreeWidget"))
    tree = TreeWidget()
    tree.preferred_width = px(400)
    tree.preferred_height = px(180)

    root = TreeNode()
    root.content = Label()
    root.content.text = "Project Root"
    root.content.font_size = 14
    root.expanded = True

    tex_dir = TreeNode()
    tex_dir.content = Label()
    tex_dir.content.text = "Textures/"
    tex_dir.content.font_size = 14
    tex_dir.expanded = True
    for name in ["albedo.png", "normal.png"]:
        n = TreeNode()
        n.content = Label()
        n.content.text = name
        n.content.font_size = 14
        tex_dir.add_node(n)
    root.add_node(tex_dir)

    mesh_dir = TreeNode()
    mesh_dir.content = Label()
    mesh_dir.content.text = "Meshes/"
    mesh_dir.content.font_size = 14
    mesh_dir.expanded = True
    for name in ["character.glb", "environment.glb"]:
        n = TreeNode()
        n.content = Label()
        n.content.text = name
        n.content.font_size = 14
        mesh_dir.add_node(n)
    root.add_node(mesh_dir)

    proj_node = TreeNode()
    proj_node.content = Label()
    proj_node.content.text = "project.terminproj"
    proj_node.content.font_size = 14
    root.add_node(proj_node)

    tree.add_root(root)
    page.add_child(tree)

    return page


def make_sliders_page():
    page = VStack()
    page.spacing = 10
    page.alignment = "left"

    page.add_child(_section_label("Slider"))
    s1 = Slider()
    s1.preferred_width = px(350)
    s1.value = 0.65
    s1_lbl = Label()
    s1_lbl.text = "Continuous: 0.65"
    s1_lbl.font_size = 13
    s1.on_change = lambda v: setattr(s1_lbl, 'text', f"Continuous: {v:.2f}")
    page.add_child(s1_lbl)
    page.add_child(s1)

    s2 = Slider()
    s2.preferred_width = px(350)
    s2.min_value = 0
    s2.max_value = 100
    s2.step = 10
    s2.value = 50
    s2.fill_color = (0.9, 0.5, 0.2, 1.0)
    s2_lbl = Label()
    s2_lbl.text = "Stepped (0-100, step 10): 50"
    s2_lbl.font_size = 13
    s2.on_change = lambda v: setattr(s2_lbl, 'text', f"Stepped (0-100, step 10): {int(v)}")
    page.add_child(s2_lbl)
    page.add_child(s2)

    page.add_child(_section_label("SpinBox"))
    sb = SpinBox()
    sb.value = 42
    sb.min_value = 0
    sb.max_value = 100
    sb.step = 1
    sb.decimals = 0
    sb.preferred_width = px(150)
    sb_lbl = Label()
    sb_lbl.text = "SpinBox: 42"
    sb_lbl.font_size = 13
    sb.on_change = lambda v: setattr(sb_lbl, 'text', f"SpinBox: {int(v)}")
    page.add_child(sb_lbl)
    page.add_child(sb)

    page.add_child(_section_label("SliderEdit"))
    se = SliderEdit()
    se.value = 42
    se.min_value = 0
    se.max_value = 100
    se.step = 1
    se.decimals = 0
    se.preferred_width = px(380)
    se_lbl = Label()
    se_lbl.text = "SliderEdit: 42"
    se_lbl.font_size = 13
    se.on_change = lambda v: setattr(se_lbl, 'text', f"SliderEdit: {int(v)}")
    page.add_child(se_lbl)
    page.add_child(se)

    page.add_child(_section_label("ProgressBar"))
    pb1 = ProgressBar()
    pb1.value = 0.75
    pb1.preferred_width = px(350)
    pb1.preferred_height = px(20)
    page.add_child(pb1)

    pb2 = ProgressBar()
    pb2.value = 0.42
    pb2.show_text = True
    pb2.preferred_width = px(350)
    pb2.preferred_height = px(24)
    pb2.fill_color = (0.2, 0.8, 0.4, 1.0)
    page.add_child(pb2)

    # FrameTimeGraph — connects to Profiler automatically
    page.add_child(_section_label("FrameTimeGraph"))
    ftg = FrameTimeGraph()
    ftg.preferred_width = px(350)
    ftg.preferred_height = px(60)
    page.add_child(ftg)

    return page


def make_text_page():
    page = VStack()
    page.spacing = 10
    page.alignment = "left"

    page.add_child(_section_label("TextArea"))
    ta = TextArea()
    ta.preferred_width = px(450)
    ta.preferred_height = px(220)
    ta.placeholder = "Type here..."
    ta.text = (
        "Line 1: Hello, TextArea!\n"
        "Line 2: Multi-line editing.\n"
        "Line 3: Arrow keys, Enter, Backspace.\n"
        "Line 4: Scroll with mouse wheel.\n"
        "Line 5: Word wrap when lines are long."
    )
    ta_status = Label()
    ta_status.text = f"Lines: {len(ta._lines)} | Chars: {len(ta.text)}"
    ta_status.font_size = 12
    ta_status.color = _t.text_muted
    ta.on_change = lambda v: setattr(ta_status, 'text', f"Lines: {len(ta._lines)} | Chars: {len(v)}")
    page.add_child(ta)
    page.add_child(ta_status)

    return page


def make_containers_page():
    page = VStack()
    page.spacing = 10
    page.alignment = "left"

    page.add_child(_section_label("Panel"))
    p = Panel()
    p.preferred_width = px(300)
    p.preferred_height = px(80)
    p.padding = 12
    p.background_color = (0.2, 0.2, 0.25, 1.0)
    p_lbl = Label()
    p_lbl.text = "Content inside a Panel"
    p_lbl.color = (0.9, 0.9, 0.9, 1.0)
    p.add_child(p_lbl)
    page.add_child(p)

    page.add_child(_section_label("GroupBox"))
    gb1 = GroupBox()
    gb1.title = "Settings"
    gb1.preferred_width = px(350)
    gb1_content = VStack()
    gb1_content.spacing = 4
    for k, v in [("Resolution", "1920x1080"), ("FPS", "60"), ("VSync", "On")]:
        row = HStack()
        row.spacing = 6
        kl = Label()
        kl.text = f"{k}:"
        kl.color = (0.8, 0.8, 0.8, 1.0)
        row.add_child(kl)
        vl = Label()
        vl.text = v
        vl.color = (0.5, 0.8, 1.0, 1.0)
        row.add_child(vl)
        gb1_content.add_child(row)
    gb1.add_child(gb1_content)
    page.add_child(gb1)

    gb2 = GroupBox()
    gb2.title = "Advanced (collapsed by default)"
    gb2.expanded = False
    gb2.preferred_width = px(350)
    adv = Label()
    adv.text = "Hidden advanced content."
    adv.color = (0.7, 0.7, 0.7, 1.0)
    gb2.add_child(adv)
    page.add_child(gb2)

    page.add_child(_section_label("ScrollArea"))
    sa = ScrollArea()
    sa.preferred_width = px(380)
    sa.preferred_height = px(130)
    sa_content = VStack()
    sa_content.spacing = 4
    for i in range(20):
        sl = Label()
        sl.text = f"Scrollable line {i + 1}"
        sl.font_size = 13
        sl.color = (0.8, 0.8, 0.85, 1.0)
        sa_content.add_child(sl)
    sa.add_child(sa_content)
    page.add_child(sa)

    page.add_child(_section_label("Splitter (in HStack)"))
    split_row = HStack()
    split_row.preferred_width = px(400)
    split_row.preferred_height = px(100)

    left_panel = Panel()
    left_panel.padding = 8
    left_panel.preferred_width = px(180)
    left_lbl = Label()
    left_lbl.text = "Left panel"
    left_lbl.color = (0.9, 0.9, 0.9, 1.0)
    left_panel.add_child(left_lbl)
    split_row.add_child(left_panel)

    spl = Splitter(target=left_panel, side="right")
    split_row.add_child(spl)

    right_panel = Panel()
    right_panel.padding = 8
    right_panel.stretch = True
    right_lbl = Label()
    right_lbl.text = "Right panel (drag splitter)"
    right_lbl.color = (0.9, 0.9, 0.9, 1.0)
    right_panel.add_child(right_lbl)
    split_row.add_child(right_panel)

    page.add_child(split_row)

    return page


def make_dialogs_page(ui_ref):
    page = VStack()
    page.spacing = 10
    page.alignment = "left"

    status = Label()
    status.text = "Result: (none)"
    status.font_size = 13
    status.color = (0.5, 0.8, 1.0, 1.0)

    def show_result(kind, val):
        status.text = f"Result [{kind}]: {val}"

    page.add_child(_section_label("MessageBox"))
    mb_row = HStack()
    mb_row.spacing = 8
    mb_row.alignment = "center"

    for label, factory in [
        ("Info", lambda: MessageBox.info(ui_ref[0], "Info", "Operation completed.", on_result=lambda b: show_result("Info", b))),
        ("Warning", lambda: MessageBox.warning(ui_ref[0], "Warning", "Disk space low.", on_result=lambda b: show_result("Warning", b))),
        ("Error", lambda: MessageBox.error(ui_ref[0], "Error", "File not found.", on_result=lambda b: show_result("Error", b))),
        ("Question", lambda: MessageBox.question(ui_ref[0], "Confirm", "Delete items?", on_result=lambda b: show_result("Question", b))),
        ("Yes/No/Cancel", lambda: MessageBox.question(
            ui_ref[0], "Save", "Save changes?", buttons=Buttons.YES_NO_CANCEL,
            on_result=lambda b: show_result("YN", b))),
    ]:
        b = Button()
        b.text = label
        b.padding = 6
        b.on_click = factory
        mb_row.add_child(b)
    page.add_child(mb_row)

    page.add_child(_section_label("InputDialog"))
    inp_btn = Button()
    inp_btn.text = "Input Dialog"
    inp_btn.padding = 6
    inp_btn.on_click = lambda: show_input_dialog(
        ui_ref[0], "Enter name", "Name:",
        on_result=lambda v: show_result("Input", v) if v else None)
    page.add_child(inp_btn)

    page.add_child(_section_label("ColorDialog"))
    clr_btn = Button()
    clr_btn.text = "Color Picker"
    clr_btn.padding = 6
    clr_btn.on_click = lambda: ColorDialog.pick_color(
        ui_ref[0], initial=(128, 128, 255, 255),
        on_result=lambda c: show_result("Color", f"RGBA({c[0]}, {c[1]}, {c[2]}, {c[3]})") if c else None)
    page.add_child(clr_btn)

    page.add_child(_section_label("FileDialog"))
    fd_row = HStack()
    fd_row.spacing = 8
    fd_row.alignment = "center"

    for label, cb in [
        ("Open File", lambda: show_open_file_dialog(
            ui_ref[0], lambda p: show_result("Open", p) if p else show_result("Open", "(cancelled)"))),
        ("Save File", lambda: show_save_file_dialog(
            ui_ref[0], lambda p: show_result("Save", p) if p else show_result("Save", "(cancelled)"))),
        ("Open Dir", lambda: show_open_directory_dialog(
            ui_ref[0], lambda p: show_result("Dir", p) if p else show_result("Dir", "(cancelled)"))),
    ]:
        b = Button()
        b.text = label
        b.padding = 6
        b.on_click = cb
        fd_row.add_child(b)
    page.add_child(fd_row)

    page.add_child(status)
    return page


# ── UI construction ──────────────────────────────────────────────────────


def build_ui(graphics):
    ui_ref = [None]

    root = VStack()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.spacing = 0
    root.alignment = "left"

    status_bar = StatusBar()
    status_bar.set_text("Ready | tcgui Widget Showcase")

    # MenuBar
    menu_bar = MenuBar()
    file_menu = Menu()
    file_menu.items = [
        MenuItem("New", shortcut="Ctrl+N", on_click=lambda: status_bar.show_message("New")),
        MenuItem("Open", shortcut="Ctrl+O", on_click=lambda: status_bar.show_message("Open...")),
        MenuItem.sep(),
        MenuItem("Quit", shortcut="Ctrl+Q", on_click=lambda: status_bar.show_message("Quit")),
    ]
    menu_bar.add_menu("File", file_menu)

    edit_menu = Menu()
    edit_menu.items = [
        MenuItem("Undo", shortcut="Ctrl+Z", on_click=lambda: status_bar.show_message("Undo")),
        MenuItem("Redo", shortcut="Ctrl+Shift+Z", on_click=lambda: status_bar.show_message("Redo")),
        MenuItem.sep(),
        MenuItem("Cut", shortcut="Ctrl+X"),
        MenuItem("Copy", shortcut="Ctrl+C"),
        MenuItem("Paste", shortcut="Ctrl+V"),
    ]
    menu_bar.add_menu("Edit", edit_menu)

    root.add_child(menu_bar)

    # ToolBar
    toolbar = ToolBar()
    toolbar.add_action(icon="✂", tooltip="Cut", on_click=lambda: status_bar.show_message("Cut"))
    toolbar.add_action(icon="⎘", tooltip="Open", on_click=lambda: status_bar.show_message("Open..."))
    toolbar.add_separator()
    toolbar.add_action(text="Fit", tooltip="Fit to window", on_click=lambda: status_bar.show_message("Fit"))
    toolbar.add_action(text="Reset", tooltip="Reset view", on_click=lambda: status_bar.show_message("Reset"))
    root.add_child(toolbar)

    # Tabs
    content = Panel()
    content.preferred_width = pct(100)
    content.preferred_height = px(530)
    content.background_color = (0.12, 0.12, 0.14, 1.0)
    content.padding = 16

    layout = VStack()
    layout.spacing = 10
    layout.alignment = "left"

    title = Label()
    title.text = "tcgui Widget Showcase"
    title.font_size = 22
    title.color = (1, 1, 1, 1)
    layout.add_child(title)

    tabs = TabView()
    tabs.preferred_width = px(720)
    tabs.preferred_height = px(470)

    tabs.add_tab("Basic", make_basic_page(status_bar))
    tabs.add_tab("Lists", make_lists_page())
    tabs.add_tab("Sliders", make_sliders_page())
    tabs.add_tab("Text", make_text_page())
    tabs.add_tab("Containers", make_containers_page())
    tabs.add_tab("Dialogs", make_dialogs_page(ui_ref))

    layout.add_child(tabs)
    content.add_child(layout)
    root.add_child(content)

    root.add_child(status_bar)

    ui = UI(graphics=graphics)
    ui.root = root
    ui_ref[0] = ui

    # Global shortcuts
    ui.add_shortcut_from_string("Ctrl+N", lambda: status_bar.show_message("New"))
    ui.add_shortcut_from_string("Ctrl+O", lambda: status_bar.show_message("Open..."))
    ui.add_shortcut_from_string("Ctrl+Z", lambda: status_bar.show_message("Undo"))
    ui.add_shortcut_from_string("Ctrl+Shift+Z", lambda: status_bar.show_message("Redo"))

    return ui


# ── Event loop ───────────────────────────────────────────────────────────


def _get_event_window_id(event):
    etype = event.type
    if etype == sdl2.SDL_MOUSEMOTION:
        return event.motion.windowID
    if etype in (sdl2.SDL_MOUSEBUTTONDOWN, sdl2.SDL_MOUSEBUTTONUP):
        return event.button.windowID
    if etype == sdl2.SDL_MOUSEWHEEL:
        return event.wheel.windowID
    if etype in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
        return event.key.windowID
    if etype == sdl2.SDL_TEXTINPUT:
        return event.text.windowID
    return None


def main():
    window = BackendWindow("tcgui — Widget Showcase", 900, 680)

    graphics = Tgfx2Context.from_window(window.device_ptr(), window.context_ptr())

    ui = build_ui(graphics)
    main_id = window.window_id()

    sdl2.SDL_StartTextInput()
    event = sdl2.SDL_Event()
    running = True

    while running:
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            etype = event.type

            if etype == sdl2.SDL_QUIT:
                running = False
                break

            if etype == sdl2.SDL_WINDOWEVENT:
                if event.window.event == video.SDL_WINDOWEVENT_CLOSE:
                    if event.window.windowID == main_id:
                        running = False
                        break
                continue

            wid = _get_event_window_id(event)
            if wid is not None and wid != main_id:
                continue

            if etype == sdl2.SDL_MOUSEMOTION:
                ui.mouse_move(float(event.motion.x), float(event.motion.y))
            elif etype == sdl2.SDL_MOUSEBUTTONDOWN:
                btn = _translate_button(event.button.button)
                mods = _translate_mods(sdl2.SDL_GetModState())
                ui.mouse_down(float(event.button.x), float(event.button.y), btn, mods)
            elif etype == sdl2.SDL_MOUSEBUTTONUP:
                btn = _translate_button(event.button.button)
                mods = _translate_mods(sdl2.SDL_GetModState())
                ui.mouse_up(float(event.button.x), float(event.button.y), btn, mods)
            elif etype == sdl2.SDL_MOUSEWHEEL:
                mx = ctypes.c_int()
                my = ctypes.c_int()
                sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
                ui.mouse_wheel(float(event.wheel.x), float(event.wheel.y),
                               float(mx.value), float(my.value))
            elif etype == sdl2.SDL_KEYDOWN:
                key = _translate_key(event.key.keysym.scancode)
                mods = _translate_mods(event.key.keysym.mod)
                if key == Key.ESCAPE:
                    running = False
                    break
                ui.key_down(key, mods)
            elif etype == sdl2.SDL_TEXTINPUT:
                ui.text_input(event.text.text.decode("utf-8", errors="replace"))

        if not running:
            break

        vw, vh = window.framebuffer_size()
        tex = ui.render_compose(vw, vh, background_color=(0.12, 0.12, 0.14, 1.0))
        if tex is not None:
            window.present(tex)

    sdl2.SDL_Quit()


if __name__ == "__main__":
    main()
