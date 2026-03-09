"""Test nested clip (scissor) stacking in rendering."""

from tcgui.widgets.vstack import VStack
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.units import px
from tests.conftest import make_widget


class MockGraphics:
    """Fake GraphicsBackend that records scissor calls."""

    def __init__(self):
        self.scissor_log: list[tuple[str, tuple]] = []
        self.scissor_active: bool = False
        self.scissor_rect: tuple[int, int, int, int] | None = None

    def enable_scissor(self, x, y, w, h):
        self.scissor_active = True
        self.scissor_rect = (x, y, w, h)
        self.scissor_log.append(("enable", (x, y, w, h)))

    def disable_scissor(self):
        self.scissor_active = False
        self.scissor_rect = None
        self.scissor_log.append(("disable", ()))


class MockRenderer:
    """Minimal UIRenderer using MockGraphics for testing clip stack."""

    def __init__(self, viewport_w=1280, viewport_h=800):
        self._graphics = MockGraphics()
        self._viewport_h = viewport_h
        self._viewport_w = viewport_w
        self._clip_stack: list[tuple[int, int, int, int]] = []

    def begin_clip(self, x, y, w, h):
        ix, iy, iw, ih = int(x), int(self._viewport_h - (y + h)), int(w), int(h)
        if self._clip_stack:
            px, py, pw, ph = self._clip_stack[-1]
            x1 = max(ix, px)
            y1 = max(iy, py)
            x2 = min(ix + iw, px + pw)
            y2 = min(iy + ih, py + ph)
            iw = max(0, x2 - x1)
            ih = max(0, y2 - y1)
            ix, iy = x1, y1
        self._clip_stack.append((ix, iy, iw, ih))
        self._graphics.enable_scissor(ix, iy, iw, ih)

    def end_clip(self):
        if self._clip_stack:
            self._clip_stack.pop()
        if self._clip_stack:
            px, py, pw, ph = self._clip_stack[-1]
            self._graphics.enable_scissor(px, py, pw, ph)
        else:
            self._graphics.disable_scissor()

    # Stubs for render methods that widgets might call
    def draw_rect(self, *args, **kwargs):
        pass

    def draw_text(self, *args, **kwargs):
        pass

    def draw_text_centered(self, *args, **kwargs):
        pass


# --- Tests ---

def test_single_clip():
    r = MockRenderer()
    r.begin_clip(10, 20, 100, 200)
    assert r._graphics.scissor_active
    r.end_clip()
    assert not r._graphics.scissor_active


def test_nested_clip_restores_parent():
    """Inner end_clip restores outer scissor, not disables."""
    r = MockRenderer(viewport_h=800)
    r.begin_clip(0, 0, 400, 800)
    outer_rect = r._graphics.scissor_rect

    r.begin_clip(0, 0, 400, 600)
    r.end_clip()

    # After inner end_clip, outer scissor should be restored
    assert r._graphics.scissor_active
    assert r._graphics.scissor_rect == outer_rect

    r.end_clip()
    assert not r._graphics.scissor_active


def test_nested_clip_intersects():
    """Inner clip should be intersection of outer and inner rects."""
    r = MockRenderer(viewport_h=800)
    # Outer: x=0..200, y_screen=0..400  (GL: y=400..800)
    r.begin_clip(0, 0, 200, 400)

    # Inner: x=50..250, y_screen=100..500 — should be clipped to outer
    r.begin_clip(50, 100, 200, 400)

    # Intersection in screen coords: x=50..200, y_screen=100..400
    # GL coords: x=50, y=800-(400)=400, w=150, h=300
    rect = r._graphics.scissor_rect
    # x should start at 50 (max of 0, 50)
    assert rect[0] == 50
    # w should be 150 (min of 200, 250) - 50 = 150)
    assert rect[2] == 150

    r.end_clip()
    r.end_clip()
    assert not r._graphics.scissor_active


def test_left_container_with_scroll_area():
    """Reproduce the diffusion-editor clip chain:
    left_container(clip=True) > DiffusionPanel(ScrollArea)

    After ScrollArea's end_clip, left_container's scissor must still be active.
    """
    VW, VH = 1280, 800

    # Build: left_container (VStack, clip) > scroll_area (stretch)
    left = VStack()
    left.preferred_width = px(260)
    left.clip = True

    sa = ScrollArea()
    sa.stretch = True
    content = make_widget(260, 1200)  # tall content
    sa.add_child(content)

    left.add_child(sa)
    left.layout(0, 66, 260, 715, VW, VH)

    # Render
    r = MockRenderer(viewport_h=VH)
    left.render(r)

    log = r._graphics.scissor_log

    # left_container begin_clip → enable
    # ScrollArea begin_clip → enable (intersected)
    # ScrollArea end_clip → enable (restores left_container)
    # ScrollArea scrollbar render (if any)
    # left_container end_clip → disable

    # Final state: scissor disabled
    assert not r._graphics.scissor_active

    # Count enables and disables
    enables = [e for e in log if e[0] == "enable"]
    disables = [e for e in log if e[0] == "disable"]

    # At least: outer enable, inner enable, inner restore, outer disable
    assert len(enables) >= 3  # outer, inner, restore
    assert len(disables) >= 1  # final

    # After inner end_clip (3rd entry), scissor must still be enabled
    # log: [enable(outer), enable(inner), enable(restore-outer), disable]
    # The 3rd entry should be enable (restoring outer)
    assert log[2][0] == "enable", f"Expected restore-enable, got {log[2]}"


def test_triple_nesting():
    """Three levels of clip: each end_clip restores the correct parent."""
    r = MockRenderer(viewport_h=800)

    r.begin_clip(0, 0, 800, 800)
    rect1 = r._graphics.scissor_rect

    r.begin_clip(10, 10, 400, 400)
    rect2 = r._graphics.scissor_rect

    r.begin_clip(20, 20, 200, 200)

    r.end_clip()
    assert r._graphics.scissor_active
    assert r._graphics.scissor_rect == rect2

    r.end_clip()
    assert r._graphics.scissor_active
    assert r._graphics.scissor_rect == rect1

    r.end_clip()
    assert not r._graphics.scissor_active
