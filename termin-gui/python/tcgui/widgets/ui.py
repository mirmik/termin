"""Main UI class that manages the widget tree."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from tcbase import Key, MouseButton, Mods
from tgfx import GraphicsBackend
from tcgui.font import FontTextureAtlas
from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, MouseWheelEvent, KeyEvent, TextEvent
from tcgui.widgets.renderer import UIRenderer
from tcgui.widgets.loader import UILoader
from tcgui.widgets.shortcuts import ShortcutRegistry


@dataclass
class _OverlayEntry:
    """Internal record for an overlay shown on top of the UI."""
    widget: Widget
    modal: bool = False
    dismiss_on_outside: bool = True
    on_dismiss: Callable[[], None] | None = None


class UI:
    """
    Main UI manager class.

    Manages a widget tree, handles input, renders the UI,
    and provides an overlay stack for popups / tooltips / menus.
    """

    def __init__(self, graphics: GraphicsBackend, font: FontTextureAtlas | None = None):
        self._graphics = graphics
        self._renderer = UIRenderer(graphics, font)
        self._loader = UILoader()

        self._root: Widget | None = None
        self._hovered_widget: Widget | None = None
        self._pressed_widget: Widget | None = None
        self._focused_widget: Widget | None = None

        # Viewport dimensions
        self._viewport_w: int = 0
        self._viewport_h: int = 0
        self._needs_layout: bool = True

        # Overlay stack (rendered on top of root, receives events first)
        self._overlays: list[_OverlayEntry] = []

        # Tooltip state
        self._tooltip_widget: Widget | None = None
        self._tooltip_target: Widget | None = None
        self._hover_start_time: float = 0.0
        self._last_mouse_x: float = 0.0
        self._last_mouse_y: float = 0.0
        self.tooltip_delay: float = 0.5  # seconds

        # Global keyboard shortcuts
        self._shortcuts = ShortcutRegistry()

        # Deferred actions (run after event dispatch completes)
        self._deferred_actions: list[Callable[[], None]] = []

        # Cursor tracking
        self._current_cursor: str = ""
        self.on_cursor_changed: Callable[[str], None] | None = None

        # Window management callbacks (set by application)
        self.create_window: Callable[[str, int, int], UI | None] | None = None
        self.close_window: Callable[[], None] | None = None
        self.on_empty: Callable[[], None] | None = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def root(self) -> Widget | None:
        return self._root

    @root.setter
    def root(self, widget: Widget | None):
        self._root = widget
        # Force re-layout on next render
        self._viewport_w = 0
        self._viewport_h = 0
        # Propagate _ui reference
        if widget is not None:
            self._set_ui_recursive(widget)
        else:
            self._check_empty()

    @property
    def font(self) -> FontTextureAtlas | None:
        return self._renderer.font

    @font.setter
    def font(self, value: FontTextureAtlas | None):
        self._renderer.font = value

    @property
    def loader(self) -> UILoader:
        """Access to the loader for registering custom widget types."""
        return self._loader

    # ------------------------------------------------------------------
    # Global shortcuts
    # ------------------------------------------------------------------

    def add_shortcut(self, key: Key, mods: int,
                     callback: Callable[[], None]) -> None:
        """Register a global keyboard shortcut."""
        self._shortcuts.add(key, mods, callback)

    def remove_shortcut(self, key: Key, mods: int) -> None:
        """Unregister a global keyboard shortcut."""
        self._shortcuts.remove(key, mods)

    def add_shortcut_from_string(self, shortcut_str: str,
                                 callback: Callable[[], None]) -> None:
        """Register a shortcut from a string like ``'Ctrl+S'``."""
        k, m = ShortcutRegistry.parse_shortcut_string(shortcut_str)
        self._shortcuts.add(k, m, callback)

    # ------------------------------------------------------------------
    # _ui propagation
    # ------------------------------------------------------------------

    def _set_ui_recursive(self, widget: Widget):
        """Set back-reference to this UI on *widget* and all descendants."""
        widget._ui = self
        for child in widget.children:
            self._set_ui_recursive(child)

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    def load(self, path: str) -> Widget:
        """Load UI from a YAML file and set as root."""
        self.root = self._loader.load(path)
        return self._root

    def load_string(self, yaml_str: str) -> Widget:
        """Load UI from a YAML string and set as root."""
        self.root = self._loader.load_string(yaml_str)
        return self._root

    def find(self, name: str) -> Widget | None:
        """Find a widget by name."""
        if self._root:
            return self._root.find(name)
        return None

    def find_all(self, name: str) -> list[Widget]:
        """Find all widgets with the given name."""
        if self._root:
            return self._root.find_all(name)
        return []

    # ------------------------------------------------------------------
    # Layout & rendering
    # ------------------------------------------------------------------

    def defer(self, callback: 'Callable[[], None]'):
        """Schedule *callback* to run after current event dispatch completes.

        Use this when a widget callback may block the event loop (e.g.
        opening a native file dialog).  The deferred action runs outside
        event dispatch so SDL mouse state stays consistent.
        """
        self._deferred_actions.append(callback)

    def process_deferred(self):
        """Execute and clear all deferred actions."""
        while self._deferred_actions:
            action = self._deferred_actions.pop(0)
            action()

    def request_layout(self):
        """Mark layout as needing recalculation."""
        self._needs_layout = True

    def layout(self, viewport_w: int, viewport_h: int):
        """Perform layout calculation."""
        self._viewport_w = viewport_w
        self._viewport_h = viewport_h

        if self._root:
            w, h = self._root.compute_size(viewport_w, viewport_h)

            anchor = self._root.anchor
            x, y = 0.0, 0.0

            if anchor == "absolute":
                if self._root.position_x is not None:
                    x = self._root.position_x.to_pixels(viewport_w)
                if self._root.position_y is not None:
                    y = self._root.position_y.to_pixels(viewport_h)
            else:
                if "left" in anchor:
                    x = 0
                elif "right" in anchor:
                    x = viewport_w - w
                else:
                    x = (viewport_w - w) / 2

                if "top" in anchor:
                    y = 0
                elif "bottom" in anchor:
                    y = viewport_h - h
                else:
                    y = (viewport_h - h) / 2

                x += self._root.offset_x
                y += self._root.offset_y

            self._root.layout(x, y, w, h, viewport_w, viewport_h)

    def render(self, viewport_w: int, viewport_h: int):
        """Render the UI and all overlays."""
        if not self._root and not self._overlays:
            return

        # Re-layout if viewport changed or layout invalidated
        if (viewport_w != self._viewport_w or viewport_h != self._viewport_h
                or self._needs_layout):
            self._needs_layout = False
            self.layout(viewport_w, viewport_h)

        # Check tooltip timer
        self._update_tooltip()

        self._renderer.begin(viewport_w, viewport_h)
        if self._root:
            self._root.render(self._renderer)

        # Render overlays on top (re-center modal dialogs if viewport changed)
        for entry in self._overlays:
            if entry.modal:
                w, h = entry.widget.compute_size(viewport_w, viewport_h)
                x = (viewport_w - w) / 2
                y = (viewport_h - h) / 2
                entry.widget.layout(x, y, w, h, viewport_w, viewport_h)
                self._renderer.draw_rect(0, 0, viewport_w, viewport_h,
                                         (0, 0, 0, 0.3))
            entry.widget.render(self._renderer)

        self._renderer.end()

    # ------------------------------------------------------------------
    # Overlay management
    # ------------------------------------------------------------------

    def show_overlay(self, widget: Widget, *, modal: bool = False,
                     dismiss_on_outside: bool = True,
                     on_dismiss: Callable[[], None] | None = None):
        """Show *widget* as an overlay on top of everything.

        The caller must set widget.x/y/width/height before calling this,
        or call compute_size + layout on the widget.
        """
        entry = _OverlayEntry(widget, modal, dismiss_on_outside, on_dismiss)
        self._overlays.append(entry)
        self._set_ui_recursive(widget)

    def hide_overlay(self, widget: Widget):
        """Remove an overlay by its widget reference."""
        for entry in self._overlays:
            if entry.widget is widget:
                self._overlays.remove(entry)
                if entry.on_dismiss:
                    entry.on_dismiss()
                self._check_empty()
                return

    def _hide_top_overlay(self):
        """Close the topmost overlay (e.g. on Escape)."""
        if self._overlays:
            entry = self._overlays.pop()
            if entry.on_dismiss:
                entry.on_dismiss()
            self._check_empty()

    def _check_empty(self):
        """If root is None and no overlays remain, fire on_empty callback."""
        if self._root is None and not self._overlays and self.on_empty is not None:
            self.on_empty()

    # ------------------------------------------------------------------
    # Focus management
    # ------------------------------------------------------------------

    def set_focus(self, widget: Widget | None):
        """Set the focused widget. Pass None to clear focus."""
        if self._focused_widget is widget:
            return
        if self._focused_widget is not None:
            self._focused_widget.on_blur()
        self._focused_widget = widget
        if self._focused_widget is not None:
            self._focused_widget.on_focus()

    def _collect_focusables(self) -> list[Widget]:
        """Collect all focusable widgets in depth-first tree order."""
        result: list[Widget] = []

        def walk(w: Widget):
            if w.visible and w.enabled:
                if w.focusable:
                    result.append(w)
                for child in w.children:
                    walk(child)

        if self._root:
            walk(self._root)
        return result

    def _focus_next(self, focusables: list[Widget]):
        if self._focused_widget in focusables:
            idx = focusables.index(self._focused_widget)
            self.set_focus(focusables[(idx + 1) % len(focusables)])
        else:
            self.set_focus(focusables[0])

    def _focus_prev(self, focusables: list[Widget]):
        if self._focused_widget in focusables:
            idx = focusables.index(self._focused_widget)
            self.set_focus(focusables[(idx - 1) % len(focusables)])
        else:
            self.set_focus(focusables[-1])

    # ------------------------------------------------------------------
    # Tooltip
    # ------------------------------------------------------------------

    def _update_tooltip(self):
        """Check hover timer and show/hide tooltip as needed."""
        if self._tooltip_target is not None and self._tooltip_widget is None:
            if time.monotonic() - self._hover_start_time >= self.tooltip_delay:
                self._show_tooltip(
                    self._tooltip_target.tooltip,
                    self._last_mouse_x,
                    self._last_mouse_y,
                )

    def _show_tooltip(self, text: str, x: float, y: float):
        from tcgui.widgets.containers import Panel
        from tcgui.widgets.basic import Label

        panel = Panel()
        panel.background_color = (0.15, 0.15, 0.18, 0.95)
        panel.border_radius = 4
        panel.padding = 6

        label = Label()
        label.text = text
        label.font_size = 12
        label.color = (0.9, 0.9, 0.9, 1.0)
        panel.add_child(label)

        vw, vh = self._viewport_w, self._viewport_h
        w, h = panel.compute_size(vw, vh)

        # Position: below and right of cursor, clamped to viewport
        tx = min(x + 12, vw - w - 4)
        ty = min(y + 18, vh - h - 4)
        tx = max(4, tx)
        ty = max(4, ty)
        panel.layout(tx, ty, w, h, vw, vh)

        self._tooltip_widget = panel
        self.show_overlay(panel, modal=False, dismiss_on_outside=False)

    def _hide_tooltip(self):
        if self._tooltip_widget is not None:
            self.hide_overlay(self._tooltip_widget)
            self._tooltip_widget = None
        self._tooltip_target = None

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mouse_move(self, x: float, y: float) -> bool:
        """Handle mouse move event."""
        if not self._root and not self._overlays:
            return False

        self._last_mouse_x = x
        self._last_mouse_y = y

        event = MouseEvent(x, y)

        # If we're dragging, send move to pressed widget
        if self._pressed_widget:
            self._pressed_widget.on_mouse_move(event)
            return True

        # Check overlays first (ignore tooltip overlays for hover)
        for entry in reversed(self._overlays):
            if entry.widget is self._tooltip_widget:
                continue
            hit = entry.widget.hit_test(x, y)
            if hit:
                self._update_hover(hit, event)
                return True

        # Normal hover
        if self._root:
            hit = self._root.hit_test(x, y)
            self._update_hover(hit, event)

            # Tooltip tracking
            if hit != self._tooltip_target or hit is None:
                self._hide_tooltip()
                if hit is not None and hit.tooltip:
                    self._tooltip_target = hit
                    self._hover_start_time = time.monotonic()

        return False

    def _update_hover(self, hit: Widget | None, event: MouseEvent):
        """Update hover state, firing enter/leave as needed."""
        if hit != self._hovered_widget:
            if self._hovered_widget:
                self._hovered_widget.on_mouse_leave()
            if hit:
                hit.on_mouse_enter()
            self._hovered_widget = hit

        # Update cursor based on hovered widget hierarchy
        self._update_cursor(hit)

        if self._hovered_widget:
            self._hovered_widget.on_mouse_move(event)

    def _update_cursor(self, widget: Widget | None):
        """Walk up widget tree to find cursor, notify if changed."""
        new_cursor = ""
        w = widget
        while w is not None:
            if w.cursor:
                new_cursor = w.cursor
                break
            w = w.parent
        if new_cursor != self._current_cursor:
            self._current_cursor = new_cursor
            if self.on_cursor_changed:
                self.on_cursor_changed(new_cursor)

    def mouse_down(self, x: float, y: float,
                   button: MouseButton = MouseButton.LEFT,
                   mods: int = 0) -> bool:
        """Handle mouse down event."""
        if not self._root and not self._overlays:
            return False

        event = MouseEvent(x, y, button, mods)

        # --- Overlays first (top to bottom) ---
        for entry in reversed(self._overlays):
            if entry.widget is self._tooltip_widget:
                continue  # tooltip doesn't capture clicks
            hit = entry.widget.hit_test(x, y)
            if hit:
                # Click inside overlay — dispatch to it
                if hit.focusable:
                    self.set_focus(hit)
                if hit.on_mouse_down(event):
                    self._pressed_widget = hit
                return True
            # Click outside overlay
            if entry.dismiss_on_outside:
                self.hide_overlay(entry.widget)
                return True
            if entry.modal:
                return True  # modal blocks everything below

        # --- Hide tooltip on any click ---
        self._hide_tooltip()

        if not self._root:
            return False

        # --- Context menu (right click) ---
        if button == MouseButton.RIGHT:
            hit = self._root.hit_test(x, y)
            widget = hit
            while widget is not None:
                if widget.context_menu is not None:
                    widget.context_menu.show(self, x, y)
                    return True
                widget = widget.parent

        # --- Normal dispatch ---
        hit = self._root.hit_test(x, y)

        # Focus management
        if hit is not None and hit.focusable:
            self.set_focus(hit)
        else:
            self.set_focus(None)

        if hit:
            if hit.on_mouse_down(event):
                self._pressed_widget = hit
                return True

        return False

    def mouse_up(self, x: float, y: float,
                 button: MouseButton = MouseButton.LEFT,
                 mods: int = 0) -> bool:
        """Handle mouse up event."""
        if self._pressed_widget:
            event = MouseEvent(x, y, button, mods)
            self._pressed_widget.on_mouse_up(event)
            self._pressed_widget = None
            return True
        return False

    def mouse_wheel(self, dx: float, dy: float, x: float, y: float) -> bool:
        """Handle mouse wheel event. Bubbles up through parents."""
        if not self._root and not self._overlays:
            return False

        event = MouseWheelEvent(dx, dy, x, y)

        # Check overlays first
        for entry in reversed(self._overlays):
            if entry.widget is self._tooltip_widget:
                continue
            hit = entry.widget.hit_test(x, y)
            if hit:
                widget = hit
                while widget is not None:
                    if widget.on_mouse_wheel(event):
                        return True
                    widget = widget.parent
                return entry.modal

        if not self._root:
            return False

        # Normal bubble
        widget = self._root.hit_test(x, y)
        while widget is not None:
            if widget.on_mouse_wheel(event):
                return True
            widget = widget.parent

        return False

    # ------------------------------------------------------------------
    # Keyboard events
    # ------------------------------------------------------------------

    def key_down(self, key: Key, mods: int = 0) -> bool:
        """Dispatch key down to focused widget, then handle UI-level keys."""
        event = KeyEvent(key, mods)

        def _is_descendant(child: Widget | None, root: Widget) -> bool:
            while child is not None:
                if child is root:
                    return True
                child = child.parent
            return False

        # Escape closes top overlay
        if key == Key.ESCAPE and self._overlays:
            self._hide_top_overlay()
            return True

        # If top overlay is modal, route keys to it exclusively
        if self._overlays:
            top = self._overlays[-1]
            if top.modal and top.widget is not self._tooltip_widget:
                if (self._focused_widget is not None
                        and _is_descendant(self._focused_widget, top.widget)):
                    if self._focused_widget.on_key_down(event):
                        return True
                if top.widget.on_key_down(event):
                    return True
                return False  # modal blocks further dispatch

        # Global shortcuts
        if self._shortcuts.try_dispatch(key, mods):
            return True

        # Let focused widget handle
        if self._focused_widget is not None:
            if self._focused_widget.on_key_down(event):
                return True

        # UI-level: Tab navigation
        if key == Key.TAB:
            focusables = self._collect_focusables()
            if not focusables:
                return False
            if event.shift:
                self._focus_prev(focusables)
            else:
                self._focus_next(focusables)
            return True

        return False

    def text_input(self, text: str) -> bool:
        """Dispatch text input to the focused widget."""
        if self._focused_widget is not None:
            event = TextEvent(text)
            return self._focused_widget.on_text_input(event)
        return False
