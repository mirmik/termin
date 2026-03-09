"""Test that reproduces the full diffusion-editor UI layout.

Builds the exact widget tree from editor_window._build_ui() and verifies
that all panels, canvas, splitters, menu, toolbar, and statusbar are
positioned and sized correctly at various viewport sizes.
"""

from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.scroll_area import ScrollArea
from tcgui.widgets.group_box import GroupBox
from tcgui.widgets.splitter import Splitter
from tcgui.widgets.units import px, pct
from tcgui.widgets.events import MouseEvent
from tcbase import MouseButton
from tests.conftest import make_widget, assert_rect

# Theme defaults
FONT_SIZE = 14.0
FONT_SIZE_SMALL = 11.0
MENUBAR_H = FONT_SIZE + 6.0 * 2        # 26
TOOLBAR_H = 32.0 + 4.0 * 2             # 40
STATUSBAR_H = FONT_SIZE_SMALL + 4.0 * 2  # 19

# Panel widths from diffusion-editor
LEFT_CONTAINER_W = 260
LAYER_PANEL_W = 220
SPLITTER_W = 5
BRUSH_PANEL_W = 240
DIFFUSION_PANEL_W = 280
LAMA_PANEL_W = 250
INSTRUCT_PANEL_W = 280


def _build_editor_ui(viewport_w=1280, viewport_h=800):
    """Build the exact UI tree from diffusion-editor's editor_window._build_ui().

    Returns dict with named widgets for assertions.
    """
    root = VStack()
    root.preferred_width = pct(100)
    root.preferred_height = pct(100)
    root.spacing = 0

    # MenuBar stub
    menu_bar = make_widget(0, MENUBAR_H)

    # ToolBar stub
    toolbar = make_widget(0, TOOLBAR_H)

    # Main content area
    main_area = HStack()
    main_area.stretch = True
    main_area.spacing = 0

    # Left panel container (VStack with clip)
    left_container = VStack()
    left_container.preferred_width = px(LEFT_CONTAINER_W)
    left_container.clip = True

    # Panels: BrushPanel (GroupBox), DiffusionPanel (ScrollArea),
    #         LamaPanel (ScrollArea), InstructPanel (ScrollArea)
    brush_panel = GroupBox()
    brush_panel.preferred_width = px(BRUSH_PANEL_W)
    brush_panel.title = "Brush"
    brush_panel.visible = False
    brush_panel.stretch = True
    # Add some content to BrushPanel
    brush_content = VStack()
    brush_content.spacing = 4
    brush_content.add_child(make_widget(0, 30))  # color row
    brush_content.add_child(make_widget(0, 30))  # size slider
    brush_content.add_child(make_widget(0, 30))  # hardness slider
    brush_panel.add_child(brush_content)

    diffusion_panel = ScrollArea()
    diffusion_panel.preferred_width = px(DIFFUSION_PANEL_W)
    diffusion_panel.visible = False
    diffusion_panel.stretch = True
    # DiffusionPanel content: VStack with many GroupBoxes
    diff_content = VStack()
    diff_content.spacing = 8
    diff_content.preferred_width = pct(100)
    # Model group (~120px)
    model_gb = GroupBox()
    model_gb.title = "Model"
    model_content = VStack()
    model_content.add_child(make_widget(0, 30))  # combo
    model_content.add_child(make_widget(0, 30))  # prediction combo
    model_content.add_child(make_widget(0, 30))  # load button
    model_content.add_child(make_widget(0, 15))  # status label
    model_content.add_child(make_widget(0, 15))  # diagnostics
    model_gb.add_child(model_content)
    diff_content.add_child(model_gb)
    # Prompt group (~130px)
    prompt_gb = GroupBox()
    prompt_gb.title = "Prompt"
    prompt_content = VStack()
    prompt_content.add_child(make_widget(0, 15))  # label
    prompt_content.add_child(make_widget(0, 50))  # positive text area
    prompt_content.add_child(make_widget(0, 15))  # label
    prompt_content.add_child(make_widget(0, 40))  # negative text area
    prompt_gb.add_child(prompt_content)
    diff_content.add_child(prompt_gb)
    # Parameters group (~200px)
    params_gb = GroupBox()
    params_gb.title = "Parameters"
    params_content = VStack()
    params_content.add_child(make_widget(0, 15))   # mode label
    params_content.add_child(make_widget(0, 30))   # mode combo
    params_content.add_child(make_widget(0, 15))   # masked label
    params_content.add_child(make_widget(0, 30))   # masked combo
    params_content.add_child(make_widget(0, 30))   # strength
    params_content.add_child(make_widget(0, 30))   # steps
    params_content.add_child(make_widget(0, 30))   # cfg
    params_content.add_child(make_widget(0, 25))   # checkbox
    params_gb.add_child(params_content)
    diff_content.add_child(params_gb)
    # Seed group (~50px)
    seed_gb = GroupBox()
    seed_gb.title = "Seed"
    seed_gb.add_child(make_widget(0, 30))
    diff_content.add_child(seed_gb)
    # Mask Brush group (~140px)
    mask_gb = GroupBox()
    mask_gb.title = "Mask Brush"
    mask_content = VStack()
    mask_content.add_child(make_widget(0, 30))  # size
    mask_content.add_child(make_widget(0, 30))  # hardness
    mask_content.add_child(make_widget(0, 25))  # checkboxes
    mask_content.add_child(make_widget(0, 30))  # select bg
    mask_gb.add_child(mask_content)
    diff_content.add_child(mask_gb)
    # IP-Adapter group (~120px)
    ip_gb = GroupBox()
    ip_gb.title = "IP-Adapter"
    ip_content = VStack()
    ip_content.add_child(make_widget(0, 30))  # load
    ip_content.add_child(make_widget(0, 15))  # status
    ip_content.add_child(make_widget(0, 30))  # scale
    ip_content.add_child(make_widget(0, 25))  # buttons row
    ip_gb.add_child(ip_content)
    diff_content.add_child(ip_gb)
    # Diffusion Layer group (~100px)
    layer_gb = GroupBox()
    layer_gb.title = "Diffusion Layer"
    layer_content = VStack()
    layer_content.add_child(make_widget(0, 15))  # info
    layer_content.add_child(make_widget(0, 30))  # regen row
    layer_content.add_child(make_widget(0, 30))  # clear mask
    layer_content.add_child(make_widget(0, 25))  # patch row
    layer_gb.add_child(layer_content)
    diff_content.add_child(layer_gb)
    diffusion_panel.add_child(diff_content)

    lama_panel = ScrollArea()
    lama_panel.preferred_width = px(LAMA_PANEL_W)
    lama_panel.visible = False
    lama_panel.stretch = True
    lama_content = VStack()
    lama_content.spacing = 8
    lama_content.preferred_width = pct(100)
    # Mask Brush group
    lama_mask_gb = GroupBox()
    lama_mask_gb.title = "Mask Brush"
    lama_mask_c = VStack()
    lama_mask_c.add_child(make_widget(0, 30))
    lama_mask_c.add_child(make_widget(0, 30))
    lama_mask_c.add_child(make_widget(0, 25))
    lama_mask_c.add_child(make_widget(0, 30))
    lama_mask_gb.add_child(lama_mask_c)
    lama_content.add_child(lama_mask_gb)
    # LaMa Layer group
    lama_layer_gb = GroupBox()
    lama_layer_gb.title = "LaMa Layer"
    lama_layer_c = VStack()
    lama_layer_c.add_child(make_widget(0, 15))
    lama_layer_c.add_child(make_widget(0, 30))
    lama_layer_c.add_child(make_widget(0, 30))
    lama_layer_gb.add_child(lama_layer_c)
    lama_content.add_child(lama_layer_gb)
    lama_panel.add_child(lama_content)

    instruct_panel = ScrollArea()
    instruct_panel.preferred_width = px(INSTRUCT_PANEL_W)
    instruct_panel.visible = False
    instruct_panel.stretch = True
    instruct_content = VStack()
    instruct_content.spacing = 8
    instruct_content.preferred_width = pct(100)
    # Model group
    inst_model_gb = GroupBox()
    inst_model_gb.title = "Model"
    inst_model_c = VStack()
    inst_model_c.add_child(make_widget(0, 30))
    inst_model_c.add_child(make_widget(0, 15))
    inst_model_gb.add_child(inst_model_c)
    instruct_content.add_child(inst_model_gb)
    # Instruction group
    inst_text_gb = GroupBox()
    inst_text_gb.title = "Instruction"
    inst_text_gb.add_child(make_widget(0, 50))
    instruct_content.add_child(inst_text_gb)
    # Parameters group
    inst_params_gb = GroupBox()
    inst_params_gb.title = "Parameters"
    inst_params_c = VStack()
    inst_params_c.add_child(make_widget(0, 30))  # img guidance
    inst_params_c.add_child(make_widget(0, 30))  # cfg
    inst_params_c.add_child(make_widget(0, 30))  # steps
    inst_params_c.add_child(make_widget(0, 30))  # seed row
    inst_params_gb.add_child(inst_params_c)
    instruct_content.add_child(inst_params_gb)
    # Mask Brush group
    inst_mask_gb = GroupBox()
    inst_mask_gb.title = "Mask Brush"
    inst_mask_c = VStack()
    inst_mask_c.add_child(make_widget(0, 30))
    inst_mask_c.add_child(make_widget(0, 30))
    inst_mask_c.add_child(make_widget(0, 25))
    inst_mask_gb.add_child(inst_mask_c)
    instruct_content.add_child(inst_mask_gb)
    # Instruct Layer group
    inst_layer_gb = GroupBox()
    inst_layer_gb.title = "Instruct Layer"
    inst_layer_c = VStack()
    inst_layer_c.add_child(make_widget(0, 15))
    inst_layer_c.add_child(make_widget(0, 30))
    inst_layer_c.add_child(make_widget(0, 30))
    inst_layer_c.add_child(make_widget(0, 25))
    inst_layer_gb.add_child(inst_layer_c)
    instruct_content.add_child(inst_layer_gb)
    instruct_panel.add_child(instruct_content)

    left_container.add_child(brush_panel)
    left_container.add_child(diffusion_panel)
    left_container.add_child(lama_panel)
    left_container.add_child(instruct_panel)

    main_area.add_child(left_container)
    spl_left = Splitter(target=left_container, side="left")
    main_area.add_child(spl_left)

    # Canvas (center, stretch)
    canvas = make_widget(stretch=True)
    main_area.add_child(canvas)

    # Right panel: LayerPanel (VStack, w=220px)
    layer_panel = VStack()
    layer_panel.preferred_width = px(LAYER_PANEL_W)
    layer_panel.spacing = 6
    # Tree widget (stretch)
    tree = make_widget(stretch=True)
    layer_panel.add_child(tree)
    # Button rows
    btn_row1 = HStack()
    btn_row1.spacing = 4
    btn_row1.preferred_height = px(30)
    btn_row1.add_child(make_widget(30, 30))  # +
    btn_row1.add_child(make_widget(30, 30))  # -
    btn_row1.add_child(make_widget(60, 30))  # Flatten
    layer_panel.add_child(btn_row1)
    # Create-layer buttons
    layer_panel.add_child(make_widget(0, 30))  # Diffusion btn
    layer_panel.add_child(make_widget(0, 30))  # LaMa btn
    layer_panel.add_child(make_widget(0, 30))  # Instruct btn

    spl_right = Splitter(target=layer_panel, side="right")
    main_area.add_child(spl_right)
    main_area.add_child(layer_panel)

    root.add_child(menu_bar)
    root.add_child(toolbar)
    root.add_child(main_area)

    # StatusBar stub
    statusbar = make_widget(0, STATUSBAR_H)
    root.add_child(statusbar)

    # Run layout
    root.layout(0, 0, viewport_w, viewport_h, viewport_w, viewport_h)

    return {
        "root": root,
        "menu_bar": menu_bar,
        "toolbar": toolbar,
        "main_area": main_area,
        "left_container": left_container,
        "brush_panel": brush_panel,
        "diffusion_panel": diffusion_panel,
        "lama_panel": lama_panel,
        "instruct_panel": instruct_panel,
        "spl_left": spl_left,
        "canvas": canvas,
        "spl_right": spl_right,
        "layer_panel": layer_panel,
        "tree": tree,
        "statusbar": statusbar,
    }


def _activate_panel(ui, panel_name):
    """Simulate _on_layer_changed: hide all, show one, re-layout."""
    for name in ("brush_panel", "diffusion_panel", "lama_panel", "instruct_panel"):
        ui[name].visible = False
    if panel_name:
        ui[panel_name].visible = True
    # Re-layout (simulates ui.request_layout + next render)
    vw = ui["root"].width
    vh = ui["root"].height
    ui["root"].layout(0, 0, vw, vh, vw, vh)


# =========================================================================
# Tests: initial layout (no panel visible)
# =========================================================================

class TestInitialLayout:
    """All panels hidden — initial state."""

    def test_root_fills_viewport(self):
        ui = _build_editor_ui(1280, 800)
        assert_rect(ui["root"], 0, 0, 1280, 800)

    def test_menu_bar_position(self):
        ui = _build_editor_ui(1280, 800)
        assert_rect(ui["menu_bar"], 0, 0, 1280, MENUBAR_H)

    def test_toolbar_below_menu(self):
        ui = _build_editor_ui(1280, 800)
        assert abs(ui["toolbar"].y - MENUBAR_H) <= 0.5
        assert abs(ui["toolbar"].height - TOOLBAR_H) <= 0.5

    def test_statusbar_at_bottom(self):
        ui = _build_editor_ui(1280, 800)
        sb = ui["statusbar"]
        assert abs(sb.y - (800 - STATUSBAR_H)) <= 0.5
        assert abs(sb.height - STATUSBAR_H) <= 0.5

    def test_main_area_between_bars(self):
        ui = _build_editor_ui(1280, 800)
        ma = ui["main_area"]
        expected_y = MENUBAR_H + TOOLBAR_H
        expected_h = 800 - MENUBAR_H - TOOLBAR_H - STATUSBAR_H
        assert abs(ma.y - expected_y) <= 0.5
        assert abs(ma.height - expected_h) <= 0.5
        assert abs(ma.width - 1280) <= 0.5

    def test_left_container_width(self):
        ui = _build_editor_ui(1280, 800)
        lc = ui["left_container"]
        assert abs(lc.width - LEFT_CONTAINER_W) <= 0.5

    def test_layer_panel_width(self):
        ui = _build_editor_ui(1280, 800)
        lp = ui["layer_panel"]
        assert abs(lp.width - LAYER_PANEL_W) <= 0.5

    def test_canvas_fills_remaining(self):
        ui = _build_editor_ui(1280, 800)
        expected_w = 1280 - LEFT_CONTAINER_W - SPLITTER_W * 2 - LAYER_PANEL_W
        assert abs(ui["canvas"].width - expected_w) <= 0.5

    def test_splitters_positioned(self):
        ui = _build_editor_ui(1280, 800)
        spl_l = ui["spl_left"]
        spl_r = ui["spl_right"]
        # Left splitter: right after left_container
        assert abs(spl_l.x - LEFT_CONTAINER_W) <= 0.5
        assert abs(spl_l.width - SPLITTER_W) <= 0.5
        # Right splitter: before layer panel
        expected_x = 1280 - LAYER_PANEL_W - SPLITTER_W
        assert abs(spl_r.x - expected_x) <= 0.5

    def test_canvas_x_position(self):
        ui = _build_editor_ui(1280, 800)
        expected_x = LEFT_CONTAINER_W + SPLITTER_W
        assert abs(ui["canvas"].x - expected_x) <= 0.5

    def test_all_elements_full_height(self):
        """Main area children all get the same height."""
        ui = _build_editor_ui(1280, 800)
        ma_h = ui["main_area"].height
        for name in ("left_container", "spl_left", "canvas", "spl_right", "layer_panel"):
            assert abs(ui[name].height - ma_h) <= 0.5, f"{name}.height = {ui[name].height}"


# =========================================================================
# Tests: panel switching
# =========================================================================

class TestPanelSwitching:
    """Simulate _on_layer_changed for different layer types."""

    def test_brush_panel_active(self):
        ui = _build_editor_ui(1280, 800)
        _activate_panel(ui, "brush_panel")
        bp = ui["brush_panel"]
        assert bp.visible
        assert abs(bp.x - 0) <= 0.5
        # brush panel y = left_container.y (main_area.y = menu+toolbar)
        expected_y = MENUBAR_H + TOOLBAR_H
        assert abs(bp.y - expected_y) <= 0.5
        # stretch: fills left_container height
        lc_h = ui["left_container"].height
        assert abs(bp.height - lc_h) <= 0.5
        # Other panels hidden
        assert not ui["diffusion_panel"].visible
        assert not ui["lama_panel"].visible
        assert not ui["instruct_panel"].visible

    def test_diffusion_panel_active(self):
        ui = _build_editor_ui(1280, 800)
        _activate_panel(ui, "diffusion_panel")
        dp = ui["diffusion_panel"]
        assert dp.visible
        lc_h = ui["left_container"].height
        # ScrollArea stretch: gets full container height
        assert abs(dp.height - lc_h) <= 0.5

    def test_lama_panel_active(self):
        ui = _build_editor_ui(1280, 800)
        _activate_panel(ui, "lama_panel")
        lp = ui["lama_panel"]
        assert lp.visible
        lc_h = ui["left_container"].height
        assert abs(lp.height - lc_h) <= 0.5

    def test_instruct_panel_active(self):
        ui = _build_editor_ui(1280, 800)
        _activate_panel(ui, "instruct_panel")
        ip = ui["instruct_panel"]
        assert ip.visible
        lc_h = ui["left_container"].height
        assert abs(ip.height - lc_h) <= 0.5

    def test_no_panel_active(self):
        ui = _build_editor_ui(1280, 800)
        _activate_panel(ui, None)
        for name in ("brush_panel", "diffusion_panel", "lama_panel", "instruct_panel"):
            assert not ui[name].visible

    def test_switch_between_panels(self):
        """Switch from diffusion to lama — layout stays consistent."""
        ui = _build_editor_ui(1280, 800)
        _activate_panel(ui, "diffusion_panel")
        canvas_w_1 = ui["canvas"].width
        _activate_panel(ui, "lama_panel")
        canvas_w_2 = ui["canvas"].width
        # Canvas width should not change when switching left panels
        assert abs(canvas_w_1 - canvas_w_2) <= 0.5


# =========================================================================
# Tests: scroll area content inside left panel
# =========================================================================

class TestScrollAreaInLeftPanel:
    """DiffusionPanel (ScrollArea) has content taller than viewport."""

    def test_diffusion_content_scrollable(self):
        ui = _build_editor_ui(1280, 800)
        _activate_panel(ui, "diffusion_panel")
        dp = ui["diffusion_panel"]
        # Content is taller than the panel
        assert dp._content_h > dp.height
        assert dp._max_scroll_y > 0

    def test_diffusion_scroll_clamps(self):
        ui = _build_editor_ui(1280, 800)
        _activate_panel(ui, "diffusion_panel")
        dp = ui["diffusion_panel"]
        dp.scroll_y = 99999
        dp._relayout_content()
        # Cannot scroll past max
        # (relayout_content doesn't clamp, but layout does)
        vw = ui["root"].width
        vh = ui["root"].height
        ui["root"].layout(0, 0, vw, vh, vw, vh)
        assert dp.scroll_y <= dp._max_scroll_y + 0.5

    def test_lama_content_may_fit(self):
        """LamaPanel has less content — may or may not need scrolling."""
        ui = _build_editor_ui(1280, 800)
        _activate_panel(ui, "lama_panel")
        lp = ui["lama_panel"]
        # Just verify no crash and valid geometry
        assert lp.height > 0
        assert lp._content_h >= 0


# =========================================================================
# Tests: layer panel (right) internal layout
# =========================================================================

class TestLayerPanelLayout:
    """Right panel: tree(stretch) + button rows."""

    def test_tree_stretches(self):
        ui = _build_editor_ui(1280, 800)
        tree = ui["tree"]
        lp = ui["layer_panel"]
        # Tree should take most of the space
        # Buttons: btn_row1(30) + 3 buttons(30 each) = 120 + spacing
        # spacing = 6 * 4 = 24, total fixed = 120 + 24 = 144
        # tree.height = lp.height - 144
        expected_tree_h = lp.height - (30 * 4) - (6 * 4)
        assert abs(tree.height - expected_tree_h) <= 1.0

    def test_buttons_below_tree(self):
        ui = _build_editor_ui(1280, 800)
        tree = ui["tree"]
        lp = ui["layer_panel"]
        # First button row starts after tree + spacing
        btn_row_y = tree.y + tree.height + lp.spacing
        # Check that it's within the layer panel bounds
        assert btn_row_y < lp.y + lp.height


# =========================================================================
# Tests: splitter drag
# =========================================================================

class TestSplitterDrag:
    """Drag splitters and verify layout recalculates correctly."""

    def test_drag_left_splitter_wider(self):
        ui = _build_editor_ui(1280, 800)
        spl = ui["spl_left"]
        old_canvas_w = ui["canvas"].width

        # Drag left splitter right by 50px (shrink left panel for side="left")
        ev_down = MouseEvent(x=spl.x + 2, y=spl.y + 100, button=MouseButton.LEFT)
        spl.on_mouse_down(ev_down)
        ev_move = MouseEvent(x=spl.x + 52, y=spl.y + 100)
        spl.on_mouse_move(ev_move)
        spl.on_mouse_up(MouseEvent(x=spl.x + 52, y=spl.y + 100))

        # Re-layout
        ui["root"].layout(0, 0, 1280, 800, 1280, 800)
        new_lc_w = ui["left_container"].width
        assert abs(new_lc_w - (LEFT_CONTAINER_W - 50)) <= 1.0
        # Canvas grows by 50
        assert abs(ui["canvas"].width - (old_canvas_w + 50)) <= 1.0

    def test_drag_right_splitter_wider(self):
        ui = _build_editor_ui(1280, 800)
        spl = ui["spl_right"]
        old_canvas_w = ui["canvas"].width

        # Drag right splitter left by 30px (shrink right panel for side="right")
        ev_down = MouseEvent(x=spl.x + 2, y=spl.y + 100, button=MouseButton.LEFT)
        spl.on_mouse_down(ev_down)
        ev_move = MouseEvent(x=spl.x - 28, y=spl.y + 100)
        spl.on_mouse_move(ev_move)
        spl.on_mouse_up(MouseEvent(x=spl.x - 28, y=spl.y + 100))

        ui["root"].layout(0, 0, 1280, 800, 1280, 800)
        new_lp_w = ui["layer_panel"].width
        assert abs(new_lp_w - (LAYER_PANEL_W - 30)) <= 1.0
        assert abs(ui["canvas"].width - (old_canvas_w + 30)) <= 1.0

    def test_splitter_min_width(self):
        ui = _build_editor_ui(1280, 800)
        spl = ui["spl_left"]

        ev_down = MouseEvent(x=spl.x + 2, y=spl.y + 100, button=MouseButton.LEFT)
        spl.on_mouse_down(ev_down)
        # Drag far right — side="left" shrinks target when moving right.
        ev_move = MouseEvent(x=9999, y=spl.y + 100)
        spl.on_mouse_move(ev_move)
        spl.on_mouse_up(MouseEvent(x=9999, y=spl.y + 100))

        ui["root"].layout(0, 0, 1280, 800, 1280, 800)
        assert ui["left_container"].width >= spl._min_size - 0.5


# =========================================================================
# Tests: different viewport sizes
# =========================================================================

class TestViewportSizes:
    """Verify layout adapts to different viewport sizes."""

    def test_small_viewport(self):
        ui = _build_editor_ui(800, 600)
        expected_canvas_w = 800 - LEFT_CONTAINER_W - SPLITTER_W * 2 - LAYER_PANEL_W
        assert abs(ui["canvas"].width - expected_canvas_w) <= 0.5
        # All elements still positioned correctly
        assert ui["statusbar"].y > 0
        assert ui["canvas"].height > 0

    def test_large_viewport(self):
        ui = _build_editor_ui(1920, 1080)
        expected_canvas_w = 1920 - LEFT_CONTAINER_W - SPLITTER_W * 2 - LAYER_PANEL_W
        assert abs(ui["canvas"].width - expected_canvas_w) <= 0.5
        # Canvas gets more space
        main_h = 1080 - MENUBAR_H - TOOLBAR_H - STATUSBAR_H
        assert abs(ui["canvas"].height - main_h) <= 0.5

    def test_wide_viewport(self):
        ui = _build_editor_ui(2560, 800)
        expected_canvas_w = 2560 - LEFT_CONTAINER_W - SPLITTER_W * 2 - LAYER_PANEL_W
        assert abs(ui["canvas"].width - expected_canvas_w) <= 0.5

    def test_narrow_viewport(self):
        """Even when viewport is barely larger than fixed panels, no crash."""
        min_w = LEFT_CONTAINER_W + SPLITTER_W * 2 + LAYER_PANEL_W + 10
        ui = _build_editor_ui(min_w, 600)
        # Canvas should get approximately 10px
        assert ui["canvas"].width >= 0


# =========================================================================
# Tests: consistency after multiple relayouts
# =========================================================================

class TestRelayoutConsistency:
    """Repeated layout produces same results."""

    def test_double_layout_same_result(self):
        ui = _build_editor_ui(1280, 800)
        _activate_panel(ui, "diffusion_panel")

        # Record positions
        positions_1 = {
            name: (ui[name].x, ui[name].y, ui[name].width, ui[name].height)
            for name in ("canvas", "left_container", "layer_panel", "diffusion_panel")
        }

        # Layout again
        ui["root"].layout(0, 0, 1280, 800, 1280, 800)

        for name in positions_1:
            w = ui[name]
            p = positions_1[name]
            assert abs(w.x - p[0]) <= 0.1, f"{name}.x changed"
            assert abs(w.y - p[1]) <= 0.1, f"{name}.y changed"
            assert abs(w.width - p[2]) <= 0.1, f"{name}.width changed"
            assert abs(w.height - p[3]) <= 0.1, f"{name}.height changed"

    def test_panel_switch_preserves_structure(self):
        """Switching panels doesn't affect canvas or right panel."""
        ui = _build_editor_ui(1280, 800)

        _activate_panel(ui, "brush_panel")
        canvas_rect_1 = (ui["canvas"].x, ui["canvas"].y,
                         ui["canvas"].width, ui["canvas"].height)
        lp_rect_1 = (ui["layer_panel"].x, ui["layer_panel"].y,
                      ui["layer_panel"].width, ui["layer_panel"].height)

        _activate_panel(ui, "diffusion_panel")
        canvas_rect_2 = (ui["canvas"].x, ui["canvas"].y,
                         ui["canvas"].width, ui["canvas"].height)
        lp_rect_2 = (ui["layer_panel"].x, ui["layer_panel"].y,
                      ui["layer_panel"].width, ui["layer_panel"].height)

        _activate_panel(ui, "instruct_panel")
        canvas_rect_3 = (ui["canvas"].x, ui["canvas"].y,
                         ui["canvas"].width, ui["canvas"].height)

        for i in range(4):
            assert abs(canvas_rect_1[i] - canvas_rect_2[i]) <= 0.5
            assert abs(canvas_rect_2[i] - canvas_rect_3[i]) <= 0.5
            assert abs(lp_rect_1[i] - lp_rect_2[i]) <= 0.5
