# termin-gui-native porting checklist

## Purpose

This checklist tracks the migration from Python `termin-gui`/`tcgui` concepts to
the C++/C ABI `termin-gui-native` core.

Board anchor: Kanboard `#210 [ui/plot] Design C++ UI core and plot annotation layer`.

The goal is not pixel-perfect parity first. Until visual verification is
available, each item should close through headless contracts:

- layout produces deterministic bounds;
- paint emits stable draw-list command sequences;
- event routing changes widget state or calls callbacks as expected;
- destroy invalidates handles and releases owned children;
- Python bindings expose the same primitive where relevant;
- the SDL showcase compiles, even if runtime visual smoke is skipped by the
  current host display backend.

## Current State

Already started in `termin-gui-native`:

- `tc_ui_document` owns adopted `tc_widget` instances through handles.
- `tc_widget` has measure/layout/paint/pointer-event lifecycle hooks.
- `tc_ui_draw_list` supports rects, lines, clipping and text.
- `UiDrawListRenderer` renders draw-list commands through `Canvas2DRenderer`.
- First C++ widget layer exists: `NativeWidget`, `BoxLayout`, `Panel`,
  `Button`, `Checkbox`, `ProgressBar`, `Slider`, `Swatch`, `Label`, `Spacer`.
- Existing tests cover document ownership, recursive destroy, paint command
  output, simple layout and pointer event routing.

## Non-Goals For The Blind-Port Phase

- Pixel-perfect theme matching.
- Final editor UI migration.
- Final typography, spacing and color polish.
- Complex widgets with production data models before layout/event foundations
  are stable.
- Compatibility fallbacks that hide broken migration state.

## Phase 1 - Core Contracts

- [x] Define child layout policy per child: fixed, preferred, flex, stretch.
- [x] Add child metadata storage without making parent/child imply memory
  ownership.
- [ ] Add max-size constraints and overflow behavior.
- [ ] Add hit-test helper API for root and containers.
- [ ] Add pointer hover tracking in `tc_ui_document`.
- [ ] Add pointer capture for pressed/draggable widgets.
- [ ] Add focus handle and focusable flag.
- [ ] Add keyboard event ABI.
- [ ] Add text input event ABI.
- [ ] Add callback/signal storage pattern for C++ widgets.
- [ ] Add stable widget id/name/debug metadata.
- [ ] Add dirty flags: layout dirty, paint dirty, state dirty.
- [ ] Add theme/style structs and make built-in widgets consume them.
- [ ] Add font provider or measurement service so `Label` measure uses real
  font metrics.
- [ ] Add tests for stale child handles inside containers.
- [ ] Add tests for event propagation order and capture release.
- [ ] Add tests for focus handoff and keyboard routing.

Phase 1 notes:

- Child layout policy is implemented in
  `termin-gui-native/include/termin/gui_native/widgets.hpp` and
  `termin-gui-native/src/widgets.cpp` via `LayoutPolicy`, `LayoutItem` and
  typed `BoxLayout::add_*_child` helpers. Containers still store handles plus
  metadata only; document ownership remains centralized in `tc_ui_document`.
- Headless coverage: `termin_gui_native_widgets_test` checks default stretch
  layout compatibility and mixed fixed/preferred/flex distribution.
- Visual verification remains deferred until the SDL/offscreen renderer smoke
  is available on the host display backend.

## Phase 2 - Draw List And Renderer Parity

- [x] Fill rect command.
- [x] Stroke rect command.
- [x] Line command.
- [x] Clip push/pop commands.
- [x] Text command.
- [ ] Rounded rect command, or renderer-level radius support in command data.
- [ ] Texture/image command.
- [ ] Polyline command.
- [ ] Circle/arc command.
- [ ] Path command, if plot annotations need it.
- [ ] Nine-slice or border-image command for scalable panels.
- [ ] Per-command debug label for renderer diagnostics.
- [ ] Optional command bounds for test/debug inspection.
- [ ] Renderer smoke into offscreen target with pixel readback.
- [ ] Python binding tests for every command type.

## Phase 3 - Basic Widgets

These should be ported before complex editor widgets.

- [x] `Label`.
- [x] `Button` skeleton.
- [x] `Checkbox` skeleton.
- [x] `Slider` skeleton.
- [x] `ProgressBar` skeleton.
- [x] `Panel`.
- [x] `Spacer`.
- [x] `Swatch`.
- [ ] `Separator`.
- [ ] `TextInput` single-line skeleton.
- [ ] `TextArea` skeleton.
- [ ] `SpinBox`.
- [ ] `SliderEdit`.
- [ ] `ComboBox` closed-state skeleton.
- [ ] `IconButton` with image/icon command dependency.
- [ ] `ImageWidget` with texture/image command dependency.
- [ ] `Canvas` custom paint callback widget.

Acceptance per widget:

- [ ] Construction through C++ `DocumentBuilder`.
- [ ] Deterministic min/preferred size.
- [ ] Layout bounds test.
- [ ] Paint command test.
- [ ] Pointer/keyboard behavior test where applicable.
- [ ] Recursive destroy test if it owns child handles.
- [ ] Python binding decision recorded: bind now, defer, or not needed.

## Phase 4 - Layout And Containers

- [x] `BoxLayout` primitive.
- [ ] `HStack` convenience wrapper.
- [ ] `VStack` convenience wrapper.
- [ ] `GridLayout`.
- [ ] `ScrollArea`.
- [ ] `Splitter`.
- [ ] `GroupBox`.
- [ ] `TabView` / tabs.
- [ ] Overlay container.
- [ ] Dialog root/container.
- [ ] Menu popup container.
- [ ] Toolbar layout.
- [ ] Status bar layout.

Acceptance:

- [ ] Layout tests cover empty, one child, many children.
- [ ] Layout tests cover padding, spacing, min/max, flex distribution.
- [ ] Paint tests cover clipping.
- [ ] Event tests cover child order, clipping and overlay precedence.
- [ ] Destroy tests prove containers do not leak child widgets.

## Phase 5 - Input, Focus And Interaction

- [ ] Pointer move/down/up/wheel event model.
- [ ] Hover enter/leave callbacks.
- [ ] Pressed state lifecycle.
- [ ] Pointer capture API.
- [ ] Focusable flag and focus traversal.
- [ ] Keyboard event ABI.
- [ ] Text input ABI.
- [ ] Shortcut routing.
- [ ] Modal overlay input capture.
- [ ] Dismiss-on-outside behavior.
- [ ] Disabled state and event blocking.
- [ ] Cursor request API.

## Phase 6 - Theme And Style

Start with data structures and tests; postpone visual tuning.

- [ ] `Theme` object with colors, spacing, border widths and font sizes.
- [ ] Per-widget style refs or style classes.
- [ ] Default theme matching current native showcase.
- [ ] Disabled/hover/pressed/focused state colors.
- [ ] Theme propagation from document/root.
- [ ] Runtime theme switch test.
- [ ] Python-facing theme API.

## Phase 7 - Collection Widgets

Port only after layout, focus and events are reliable.

- [ ] `ListWidget`.
- [ ] `TreeWidget`.
- [ ] `TableWidget`.
- [ ] `FileGridWidget`.
- [ ] Virtualized list/table model.
- [ ] Selection model: single, multi, range.
- [ ] Expand/collapse model for tree.
- [ ] Header/column resize model for table.
- [ ] Keyboard navigation.
- [ ] Scroll integration.

## Phase 8 - Menus, Dialogs And Overlays

- [ ] `Menu`.
- [ ] `MenuBar`.
- [ ] `ToolBar`.
- [ ] `Dialog`.
- [ ] `MessageBox`.
- [ ] `InputDialog`.
- [ ] `FileDialogOverlay`.
- [ ] `ColorDialog`.
- [ ] Popup placement.
- [ ] Modal stack.
- [ ] Escape/enter/default-button behavior.

## Phase 9 - Rich And Specialized Widgets

- [ ] `RichTextView`.
- [ ] `FrameTimeGraph`.
- [ ] `Viewport3D`.
- [ ] `SceneView` / graphics item bridge decision.
- [ ] Plot annotation widgets or shared plot overlay primitives.
- [ ] Texture preview widget.
- [ ] Profiler panel primitives.
- [ ] Registry/table inspector primitives.

## Phase 10 - Python Bridge And Mixed-Language Use

- [ ] Bind native widget handles and core document APIs.
- [ ] Bind layout APIs.
- [ ] Bind event structs.
- [ ] Bind draw text/image commands.
- [ ] Decide Python ownership policy for native widgets: wrapper observes handle
  or creates/adopts owned widget.
- [ ] Add Python tests for stale handles and document-destroy behavior.
- [ ] Add Python showcase that uses native layouts/widgets instead of custom
  Python paint-only widgets.
- [ ] Decide migration path for existing `tcgui.widgets.Widget`.

## Phase 11 - Showcase And Smoke Gates

- [x] C++ showcase compiles with basic widgets.
- [ ] C++ showcase uses text, panels, buttons, checkbox, slider, progress,
  palette, scroll area and tabs.
- [ ] Python showcase mirrors the C++ showcase.
- [ ] Headless draw-list snapshot test for showcase structure.
- [ ] Offscreen renderer pixel smoke for text + rect + clip.
- [ ] Manual SDL smoke once visual verification is available.
- [ ] Screenshot capture path for future visual regression checks.

## Phase 12 - Editor Migration Slices

Do not start these until basic containers, text, focus and scrolling are
stable.

- [ ] Replace a small editor utility panel with native UI.
- [ ] Port registry viewer table skeleton.
- [ ] Port scene tree skeleton.
- [ ] Port inspector field widgets.
- [ ] Port viewport list.
- [ ] Port build profiles window.
- [ ] Port framegraph debugger shell.
- [ ] Decide old `termin.editor_tcgui` coexistence boundary.

## Source Widget Inventory From termin-gui

Files under `termin-gui/python/tcgui/widgets` to audit or port:

- [ ] `basic.py`
- [ ] `button.py`
- [ ] `canvas.py`
- [ ] `checkbox.py`
- [ ] `color_dialog.py`
- [ ] `combo_box.py`
- [ ] `containers.py`
- [ ] `dialog.py`
- [ ] `events.py`
- [ ] `file_dialog_overlay.py`
- [ ] `file_grid_widget.py`
- [ ] `frame_time_graph.py`
- [ ] `grid_layout.py`
- [ ] `group_box.py`
- [ ] `hstack.py`
- [ ] `icon_button.py`
- [ ] `icon_theme.py`
- [ ] `image_widget.py`
- [ ] `input_dialog.py`
- [ ] `label.py`
- [ ] `list_widget.py`
- [ ] `loader.py`
- [ ] `menu.py`
- [ ] `menu_bar.py`
- [ ] `message_box.py`
- [ ] `panel.py`
- [ ] `progress_bar.py`
- [ ] `renderer.py`
- [ ] `rich_text_view.py`
- [ ] `scroll_area.py`
- [ ] `separator.py`
- [ ] `shortcuts.py`
- [ ] `slider.py`
- [ ] `slider_edit.py`
- [ ] `spin_box.py`
- [ ] `splitter.py`
- [ ] `status_bar.py`
- [ ] `table_widget.py`
- [ ] `tabs.py`
- [ ] `text_area.py`
- [ ] `text_input.py`
- [ ] `theme.py`
- [ ] `tool_bar.py`
- [ ] `tree.py`
- [ ] `ui.py`
- [ ] `units.py`
- [ ] `viewport3d.py`
- [ ] `vstack.py`
- [ ] `widget.py`

## Completion Rules

For each checked item, update either this plan or live module docs with:

- implemented files/API;
- tests or smoke command;
- known missing visual verification;
- follow-up card if the item exposed a larger design problem.

When a phase is substantially complete, move the durable state into
`termin-gui-native/README.md` or an architecture note. This file is a working
plan, not the final source of truth.
