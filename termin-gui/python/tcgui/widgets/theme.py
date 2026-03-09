"""Centralized theme system for tcgui widgets."""

from __future__ import annotations

from copy import copy


class Theme:
    """Centralized color palette and metrics.

    Widgets read from ``current_theme`` at construction time.
    To change the look globally, assign a new theme and recreate widgets
    or call ``Theme.apply_to(theme, root)`` on an existing tree.
    """

    def __init__(self):
        # --- Backgrounds ---
        self.bg_primary: tuple = (0.12, 0.12, 0.14, 1.0)
        self.bg_surface: tuple = (0.2, 0.2, 0.2, 1.0)
        self.bg_group: tuple = (0.15, 0.15, 0.17, 1.0)
        self.bg_input: tuple = (0.15, 0.15, 0.15, 1.0)
        self.bg_input_focus: tuple = (0.18, 0.18, 0.22, 1.0)

        # --- Interactive states ---
        self.hover: tuple = (0.4, 0.4, 0.4, 1.0)
        self.pressed: tuple = (0.2, 0.2, 0.2, 1.0)
        self.selected: tuple = (0.2, 0.35, 0.6, 0.9)
        self.hover_subtle: tuple = (0.22, 0.22, 0.28, 0.9)

        # --- Accent ---
        self.accent: tuple = (0.3, 0.6, 0.9, 1.0)
        self.accent_success: tuple = (0.3, 0.8, 0.4, 1.0)

        # --- Text ---
        self.text_primary: tuple = (1.0, 1.0, 1.0, 1.0)
        self.text_secondary: tuple = (0.7, 0.7, 0.7, 1.0)
        self.text_muted: tuple = (0.5, 0.5, 0.5, 1.0)

        # --- Borders ---
        self.border: tuple = (0.4, 0.4, 0.4, 1.0)
        self.border_focus: tuple = (0.3, 0.5, 0.9, 1.0)

        # --- Scrollbar ---
        self.scrollbar: tuple = (0.5, 0.5, 0.5, 0.5)
        self.scrollbar_hover: tuple = (0.7, 0.7, 0.7, 0.7)

        # --- Metrics ---
        self.font_size: float = 12.0
        self.font_size_small: float = 10.0
        self.border_radius: float = 3.0
        self.spacing: float = 5.0

    @classmethod
    def dark(cls) -> Theme:
        """Create the default dark theme (current defaults)."""
        return cls()

    def copy(self) -> Theme:
        """Return a shallow copy of this theme for customization."""
        return copy(self)

    def _with_alpha(self, color: tuple, alpha: float) -> tuple:
        """Return *color* with replaced alpha channel."""
        return (color[0], color[1], color[2], alpha)

    # --- Application to widget trees ---

    def apply_to(self, widget) -> None:
        """Recursively apply this theme to *widget* and all descendants."""
        self._apply_single(widget)
        for child in widget.children:
            self.apply_to(child)

    def _apply_single(self, widget) -> None:
        """Apply theme colors/metrics to a single widget based on its type."""
        # Avoid circular imports — use class names
        cls_name = type(widget).__name__

        if cls_name == "Label":
            widget.color = self.text_primary
            widget.font_size = self.font_size

        elif cls_name == "Button":
            widget.background_color = self.bg_surface
            widget.hover_color = self.hover
            widget.pressed_color = self.pressed
            widget.text_color = self.text_primary
            widget.border_radius = self.border_radius
            widget.font_size = self.font_size

        elif cls_name == "Checkbox":
            widget.box_color = self.bg_surface
            widget.check_color = self.accent_success
            widget.hover_color = self.hover
            widget.text_color = self.text_primary
            widget.border_radius = self.border_radius
            widget.font_size = self.font_size

        elif cls_name == "IconButton":
            widget.background_color = self._with_alpha(self.bg_surface, 0.9)
            widget.hover_color = self.hover
            widget.pressed_color = self.pressed
            widget.active_color = self.accent
            widget.icon_color = self.text_secondary
            widget.border_radius = self.border_radius + 1

        elif cls_name == "Separator":
            widget.color = self.text_muted

        elif cls_name == "TextInput":
            widget.background_color = self.bg_input
            widget.focused_background_color = self.bg_input_focus
            widget.border_color = self.border
            widget.focused_border_color = self.border_focus
            widget.text_color = self.text_primary
            widget.placeholder_color = self.text_muted
            widget.cursor_color = self.text_primary
            widget.font_size = self.font_size
            widget.border_radius = self.border_radius

        elif cls_name == "ListWidget":
            widget.item_background = self._with_alpha(self.bg_input_focus, 0.6)
            widget.selected_background = self.selected
            widget.hover_background = self.hover_subtle
            widget.text_color = self.text_primary
            widget.subtitle_color = self.text_muted
            widget.selected_text_color = self.text_primary
            widget.font_size = self.font_size
            widget.border_radius = self.border_radius + 1

        elif cls_name == "TableWidget":
            widget.header_background = self.bg_surface
            widget.header_text_color = self.text_muted
            widget.header_border_color = self._with_alpha(self.border, 0.5)
            widget.row_background = self._with_alpha(self.bg_input_focus, 0.3)
            widget.row_alt_background = self._with_alpha(self.bg_input_focus, 0.15)
            widget.selected_background = self.selected
            widget.hover_background = self.hover_subtle
            widget.text_color = self.text_primary
            widget.selected_text_color = self.text_primary

        elif cls_name == "ProgressBar":
            widget.background_color = self.bg_surface
            widget.fill_color = self.accent
            widget.text_color = self.text_primary
            widget.border_radius = self.border_radius

        elif cls_name == "Slider":
            widget.track_color = self.bg_surface
            widget.fill_color = self.accent
            widget.thumb_color = self.text_secondary
            widget.thumb_hover_color = self.text_primary

        elif cls_name == "Panel":
            widget.background_color = self._with_alpha(self.bg_surface, 0.9)

        elif cls_name == "ScrollArea":
            widget.scrollbar_color = self.scrollbar
            widget.scrollbar_hover_color = self.scrollbar_hover

        elif cls_name == "TreeWidget":
            widget.selected_background = self.selected
            widget.hover_background = self.hover_subtle
            widget.toggle_color = self.text_secondary

        elif cls_name == "TabBar":
            widget.tab_color = self.bg_surface
            widget.selected_tab_color = self.hover_subtle
            widget.hover_tab_color = (
                self.bg_surface[0] + 0.05,
                self.bg_surface[1] + 0.05,
                self.bg_surface[2] + 0.05,
                self.bg_surface[3],
            )
            widget.text_color = self.text_secondary
            widget.selected_text_color = self.text_primary
            widget.indicator_color = self.accent
            widget.border_radius = self.border_radius + 1

        elif cls_name == "SpinBox":
            widget.background_color = self.bg_input
            widget.focused_background_color = self.bg_input_focus
            widget.border_color = self.border
            widget.focused_border_color = self.border_focus
            widget.text_color = self.text_primary
            widget.cursor_color = self.text_primary
            widget.button_color = self.bg_surface
            widget.button_hover_color = self.hover
            widget.arrow_color = self.text_secondary
            widget.font_size = self.font_size
            widget.border_radius = self.border_radius

        elif cls_name == "SliderEdit":
            # SliderEdit delegates to child Slider and SpinBox
            pass

        elif cls_name == "TextArea":
            widget.background_color = self.bg_input
            widget.focused_background_color = self.bg_input_focus
            widget.border_color = self.border
            widget.focused_border_color = self.border_focus
            widget.text_color = self.text_primary
            widget.placeholder_color = self.text_muted
            widget.cursor_color = self.text_primary
            widget.scrollbar_color = self.scrollbar
            widget.scrollbar_hover_color = self.scrollbar_hover
            widget.font_size = self.font_size
            widget.border_radius = self.border_radius

        elif cls_name == "GroupBox":
            widget.background_color = self.bg_group
            widget.title_background_color = self.bg_surface
            widget.title_hover_color = self.hover_subtle
            widget.title_text_color = self.text_primary
            widget.arrow_color = self.text_secondary
            widget.border_color = self.border
            widget.font_size = self.font_size
            widget.border_radius = self.border_radius

        elif cls_name == "Menu":
            widget.item_hover_color = self.hover_subtle
            widget.text_color = self.text_primary
            widget.text_disabled_color = self.text_muted
            widget.shortcut_color = self.text_muted
            widget.icon_color = self.text_secondary
            widget.border_radius = self.border_radius + 1
            widget.font_size = self.font_size

        elif cls_name == "MenuBar":
            widget.background_color = self.bg_surface
            widget.text_color = self.text_secondary
            widget.hover_text_color = self.text_primary
            widget.active_text_color = self.text_primary
            widget.hover_color = self.hover_subtle
            widget.active_color = self.hover
            widget.font_size = self.font_size

        elif cls_name == "ToolBar":
            widget.background_color = self.bg_surface
            widget.item_hover_color = self.hover_subtle
            widget.item_pressed_color = self.pressed
            widget.icon_color = self.text_secondary
            widget.icon_hover_color = self.text_primary
            widget.icon_disabled_color = self.text_muted
            widget.separator_color = self.text_muted
            widget.border_radius = self.border_radius

        elif cls_name == "StatusBar":
            widget.background_color = self.bg_surface
            widget.text_color = self.text_muted
            widget.temp_text_color = self.text_secondary
            widget.font_size = self.font_size_small

        elif cls_name == "Dialog":
            widget.background_color = self.bg_surface
            widget.title_background_color = self._with_alpha(self.bg_surface, 1.0)
            widget.title_text_color = self.text_primary
            widget.title_font_size = self.font_size + 2
            widget.border_radius = self.border_radius + 2

        elif cls_name == "MessageBox":
            widget.background_color = self.bg_surface
            widget.title_background_color = self._with_alpha(self.bg_surface, 1.0)
            widget.title_text_color = self.text_primary
            widget.title_font_size = self.font_size + 2
            widget.border_radius = self.border_radius + 2
            widget.message_font_size = self.font_size

        elif cls_name == "Canvas":
            widget.background_color = self.bg_primary

        elif cls_name == "ColorDialog":
            widget.background_color = self.bg_surface
            widget.title_background_color = self._with_alpha(self.bg_surface, 1.0)
            widget.title_text_color = self.text_primary
            widget.title_font_size = self.font_size + 2
            widget.border_radius = self.border_radius + 2


# Module-level default theme.  Widgets read from this in __init__.
current_theme: Theme = Theme.dark()
