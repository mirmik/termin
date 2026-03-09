"""TreeWidget example with SDL2 + OpenGL.

Displays a file-tree-like structure with expand/collapse,
keyboard navigation, and rich content nodes.

Requirements: tcbase, tgfx, tcgui, PySDL2
Run: python3 examples/sdl_tree.py
"""

import ctypes
import sdl2
from sdl2 import video

from tgfx import OpenGLGraphicsBackend
from tcbase import Key, MouseButton, Mods

from tcgui.widgets.ui import UI
from tcgui.widgets.basic import Label
from tcgui.widgets.containers import VStack, HStack, Panel
from tcgui.widgets.tree import TreeNode, TreeWidget
from tcgui.widgets.units import px, pct


# --- SDL helpers (same as sdl_hello.py) ---

def create_window(title: str, width: int, height: int):
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
        raise RuntimeError(f"SDL_Init failed: {sdl2.SDL_GetError()}")

    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
    video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
    video.SDL_GL_SetAttribute(
        video.SDL_GL_CONTEXT_PROFILE_MASK,
        video.SDL_GL_CONTEXT_PROFILE_CORE,
    )
    video.SDL_GL_SetAttribute(video.SDL_GL_DOUBLEBUFFER, 1)
    video.SDL_GL_SetAttribute(video.SDL_GL_DEPTH_SIZE, 24)

    flags = video.SDL_WINDOW_OPENGL | video.SDL_WINDOW_RESIZABLE | video.SDL_WINDOW_SHOWN
    window = video.SDL_CreateWindow(
        title.encode("utf-8"),
        video.SDL_WINDOWPOS_CENTERED,
        video.SDL_WINDOWPOS_CENTERED,
        width, height, flags,
    )
    if not window:
        raise RuntimeError(f"SDL_CreateWindow failed: {sdl2.SDL_GetError()}")

    gl_ctx = video.SDL_GL_CreateContext(window)
    if not gl_ctx:
        video.SDL_DestroyWindow(window)
        raise RuntimeError(f"SDL_GL_CreateContext failed: {sdl2.SDL_GetError()}")

    video.SDL_GL_MakeCurrent(window, gl_ctx)
    video.SDL_GL_SetSwapInterval(1)
    return window, gl_ctx


def get_drawable_size(window):
    w, h = ctypes.c_int(), ctypes.c_int()
    video.SDL_GL_GetDrawableSize(window, ctypes.byref(w), ctypes.byref(h))
    return w.value, h.value


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


def translate_key(scancode: int) -> int:
    if scancode in _KEY_MAP:
        return _KEY_MAP[scancode]
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            pass
    return Key.UNKNOWN


def translate_mods(sdl_mods: int) -> int:
    result = 0
    if sdl_mods & (sdl2.KMOD_LSHIFT | sdl2.KMOD_RSHIFT):
        result |= Mods.SHIFT.value
    if sdl_mods & (sdl2.KMOD_LCTRL | sdl2.KMOD_RCTRL):
        result |= Mods.CTRL.value
    if sdl_mods & (sdl2.KMOD_LALT | sdl2.KMOD_RALT):
        result |= Mods.ALT.value
    return result


_SDL_BUTTON_MAP = {
    1: MouseButton.LEFT,
    2: MouseButton.MIDDLE,
    3: MouseButton.RIGHT,
}


def translate_button(sdl_button: int) -> MouseButton:
    return _SDL_BUTTON_MAP.get(sdl_button, MouseButton.LEFT)


# --- Helpers to build tree nodes ---

def make_label_node(text, color=(0.9, 0.9, 0.9, 1.0), font_size=14):
    """Create a TreeNode with a simple text label."""
    lbl = Label()
    lbl.text = text
    lbl.color = color
    lbl.font_size = font_size
    return TreeNode(content=lbl)


def make_icon_node(icon, icon_color, text, text_color=(0.9, 0.9, 0.9, 1.0)):
    """Create a TreeNode with icon + text (HStack)."""
    row = HStack()
    row.spacing = 6

    icon_lbl = Label()
    icon_lbl.text = icon
    icon_lbl.color = icon_color
    icon_lbl.font_size = 14
    row.add_child(icon_lbl)

    text_lbl = Label()
    text_lbl.text = text
    text_lbl.color = text_color
    text_lbl.font_size = 14
    row.add_child(text_lbl)

    return TreeNode(content=row)


# --- UI ---

def build_ui(graphics):
    root = Panel()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.background_color = (0.12, 0.12, 0.14, 1.0)
    root.padding = 20

    layout = VStack()
    layout.spacing = 12
    layout.alignment = "left"

    # Title
    title = Label()
    title.text = "TreeWidget Demo"
    title.font_size = 24
    title.color = (1.0, 1.0, 1.0, 1.0)
    layout.add_child(title)

    # Status label
    status = Label()
    status.text = "Click a node, use arrow keys, or drag to reorder"
    status.font_size = 13
    status.color = (0.5, 0.5, 0.55, 1.0)
    layout.add_child(status)

    # Tree
    tree = TreeWidget()
    tree.preferred_width = px(500)
    tree.preferred_height = px(380)
    tree.row_height = 26
    tree.row_spacing = 1

    # -- Build file tree --
    project = make_icon_node("\u25A0", (0.9, 0.7, 0.3, 1.0), "my-project")
    project.expanded = True

    # src/
    src = make_icon_node("\u25A3", (0.5, 0.8, 1.0, 1.0), "src")
    src.expanded = True
    src.add_node(make_icon_node("\u25C8", (0.4, 0.75, 0.4, 1.0), "main.py"))
    src.add_node(make_icon_node("\u25C8", (0.4, 0.75, 0.4, 1.0), "utils.py"))
    src.add_node(make_icon_node("\u25C8", (0.4, 0.75, 0.4, 1.0), "config.py"))

    # src/widgets/
    widgets = make_icon_node("\u25A3", (0.5, 0.8, 1.0, 1.0), "widgets")
    widgets.add_node(make_icon_node("\u25C8", (0.4, 0.75, 0.4, 1.0), "button.py"))
    widgets.add_node(make_icon_node("\u25C8", (0.4, 0.75, 0.4, 1.0), "label.py"))
    widgets.add_node(make_icon_node("\u25C8", (0.4, 0.75, 0.4, 1.0), "tree.py"))
    src.add_node(widgets)

    # tests/
    tests = make_icon_node("\u25A3", (0.5, 0.8, 1.0, 1.0), "tests")
    tests.add_node(make_icon_node("\u25C8", (0.7, 0.7, 0.4, 1.0), "test_main.py"))
    tests.add_node(make_icon_node("\u25C8", (0.7, 0.7, 0.4, 1.0), "test_utils.py"))

    # docs/
    docs = make_icon_node("\u25A3", (0.5, 0.8, 1.0, 1.0), "docs")
    docs.add_node(make_icon_node("\u25AB", (0.8, 0.8, 0.8, 1.0), "README.md"))
    docs.add_node(make_icon_node("\u25AB", (0.8, 0.8, 0.8, 1.0), "CHANGELOG.md"))
    docs.add_node(make_icon_node("\u25AB", (0.8, 0.8, 0.8, 1.0), "API.md"))

    # Root files
    gitignore = make_icon_node("\u25CB", (0.6, 0.6, 0.6, 1.0), ".gitignore")
    setup_py = make_icon_node("\u25C8", (0.4, 0.75, 0.4, 1.0), "setup.py")
    license_f = make_icon_node("\u25AB", (0.8, 0.8, 0.8, 1.0), "LICENSE")

    project.add_node(src)
    project.add_node(tests)
    project.add_node(docs)
    project.add_node(gitignore)
    project.add_node(setup_py)
    project.add_node(license_f)

    tree.add_root(project)

    # Callbacks
    def on_select(node):
        # Extract text from content
        c = node.content
        if isinstance(c, Label):
            status.text = f"Selected: {c.text}"
        elif isinstance(c, HStack) and len(c.children) >= 2:
            lbl = c.children[1]
            if isinstance(lbl, Label):
                status.text = f"Selected: {lbl.text}"
            else:
                status.text = "Selected: <node>"
        else:
            status.text = "Selected: <node>"

    def on_activate(node):
        c = node.content
        name = ""
        if isinstance(c, Label):
            name = c.text
        elif isinstance(c, HStack) and len(c.children) >= 2:
            lbl = c.children[1]
            if isinstance(lbl, Label):
                name = lbl.text
        status.text = f"Activated: {name}" if name else "Activated: <node>"

    tree.on_select = on_select
    tree.on_activate = on_activate

    # --- Drag & drop ---
    tree.draggable = True

    def _get_node_name(node):
        c = node.content
        if isinstance(c, Label):
            return c.text
        if isinstance(c, HStack) and len(c.children) >= 2:
            lbl = c.children[1]
            if isinstance(lbl, Label):
                return lbl.text
        return "<node>"

    def _detach_node(node):
        """Remove node from its current parent (root list or subnode list)."""
        for rn in tree.root_nodes:
            if node in rn.subnodes:
                rn.remove_node(node)
                return
            if _detach_from(rn, node):
                return
        if node in tree.root_nodes:
            tree.remove_root(node)

    def _detach_from(parent, target):
        for child in parent.subnodes:
            if target in child.subnodes:
                child.remove_node(target)
                return True
            if _detach_from(child, target):
                return True
        return False

    def _find_parent_and_index(target):
        """Find (parent_subnodes_list, index) for target node."""
        for i, rn in enumerate(tree.root_nodes):
            if rn is target:
                return tree.root_nodes, i
        def _search(node):
            for i, child in enumerate(node.subnodes):
                if child is target:
                    return node.subnodes, i
                result = _search(child)
                if result:
                    return result
            return None
        for rn in tree.root_nodes:
            result = _search(rn)
            if result:
                return result
        return None

    def _is_descendant_of(node, ancestor):
        """Check if node is a descendant of ancestor."""
        def _check(parent):
            for child in parent.subnodes:
                if child is node:
                    return True
                if _check(child):
                    return True
            return False
        return _check(ancestor)

    def on_drop(dragged, target, position):
        name = _get_node_name(dragged)

        # Prevent dropping onto self or own descendant
        if target is dragged:
            status.text = f"Cannot drop '{name}' onto itself"
            return
        if target is not None and _is_descendant_of(target, dragged):
            status.text = f"Cannot drop '{name}' into its own subtree"
            return

        _detach_node(dragged)
        dragged._set_tree_recursive(tree)

        if position == "root" or target is None:
            tree.root_nodes.append(dragged)
            status.text = f"Moved '{name}' to root"
        elif position == "inside":
            target.subnodes.append(dragged)
            target.expanded = True
            status.text = f"Moved '{name}' inside '{_get_node_name(target)}'"
        elif position in ("above", "below"):
            loc = _find_parent_and_index(target)
            if loc:
                lst, idx = loc
                insert_idx = idx if position == "above" else idx + 1
                lst.insert(insert_idx, dragged)
                status.text = f"Moved '{name}' {position} '{_get_node_name(target)}'"
            else:
                tree.root_nodes.append(dragged)
                status.text = f"Moved '{name}' to root (fallback)"

        tree._dirty = True

    tree.on_drop = on_drop

    layout.add_child(tree)
    root.add_child(layout)

    ui = UI(graphics)
    ui.root = root
    return ui


# --- Main ---

def main():
    window, gl_ctx = create_window("tcgui — Tree Demo", 700, 520)

    graphics = OpenGLGraphicsBackend.get_instance()
    graphics.ensure_ready()

    ui = build_ui(graphics)

    sdl2.SDL_StartTextInput()
    event = sdl2.SDL_Event()
    running = True

    def dispatch(ev):
        nonlocal running
        t = ev.type
        if t == sdl2.SDL_QUIT:
            running = False
        elif t == sdl2.SDL_WINDOWEVENT:
            if ev.window.event == video.SDL_WINDOWEVENT_CLOSE:
                running = False
        elif t == sdl2.SDL_MOUSEMOTION:
            ui.mouse_move(float(ev.motion.x), float(ev.motion.y))
        elif t == sdl2.SDL_MOUSEBUTTONDOWN:
            ui.mouse_down(float(ev.button.x), float(ev.button.y), translate_button(ev.button.button))
        elif t == sdl2.SDL_MOUSEBUTTONUP:
            ui.mouse_up(float(ev.button.x), float(ev.button.y))
        elif t == sdl2.SDL_MOUSEWHEEL:
            mx, my = ctypes.c_int(), ctypes.c_int()
            sdl2.SDL_GetMouseState(ctypes.byref(mx), ctypes.byref(my))
            ui.mouse_wheel(float(ev.wheel.x), float(ev.wheel.y), float(mx.value), float(my.value))
        elif t == sdl2.SDL_KEYDOWN:
            key = translate_key(ev.key.keysym.scancode)
            mods = translate_mods(sdl2.SDL_GetModState())
            ui.key_down(key, mods)
        elif t == sdl2.SDL_TEXTINPUT:
            ui.text_input(ev.text.text.decode("utf-8"))

    while running:
        if sdl2.SDL_WaitEventTimeout(ctypes.byref(event), 500):
            dispatch(event)
            while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
                dispatch(event)

        if not running:
            break

        vw, vh = get_drawable_size(window)
        graphics.bind_framebuffer(None)
        graphics.set_viewport(0, 0, vw, vh)
        graphics.clear_color_depth(0.12, 0.12, 0.14, 1.0)

        ui.render(vw, vh)

        video.SDL_GL_SwapWindow(window)

    video.SDL_GL_DeleteContext(gl_ctx)
    video.SDL_DestroyWindow(window)
    sdl2.SDL_Quit()


if __name__ == "__main__":
    main()
