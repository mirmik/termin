# termin-gui-native porting checklist

## Purpose

This checklist tracks the migration from Python `termin-gui`/`tcgui` concepts to
the C++/C ABI `termin-gui-native` core.

Board anchor: Kanboard `#244 [ui/native] Add native UI manager parity layer` in
the `termin-gui-native` swimlane. The cross-cutting plot boundary remains in
`#210 [ui/plot] Design C++ UI core and plot annotation layer`.

The target lifetime and language model is defined by:

- `docs/architecture/2026-07-07-ui-storage-and-plot-annotations.md`;
- `docs/architecture/2026-07-09-multilanguage-component-lifetime-model.md`.

`tc_widget` is the single common widget object embedded into C++, Python or
another language implementation. `tc_ui_document` adopts it through a
creator-supplied deleter and maps handles directly to it. There is no parallel
`WidgetRecord`. Common bounds, size constraints, flags and canonical tree links
belong in `tc_widget`; widget-specific and parent-child layout metadata remains
in the implementation that interprets it.

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

## Board Work Breakdown

- `#244` umbrella: full native parity and legacy retirement.
- `#247`: common `tc_widget` state and canonical tree.
- `#248`: input routing and focus traversal.
- `#249`: overlays, modal routing and tooltips.
- `#250`: theme and style.
- `#251`: draw-list and renderer primitive parity.
- `#252`: embedded `tc_widget` Python bridge.
- `#246`, then `#253`: text measurement/clipping and complete text editing.
- `#254`: remaining basic input and media widgets.
- `#255`: collection widgets and shared models.
- `#256`: menus, menu bar, toolbar and status bar.
- `#257`: dialogs and pickers.
- `#258`: factories, inspect, serialization and hot reload.
- `#259`: rich and specialized widgets.
- `#260`: visual regression and showcase gates.
- `#261`: editor migration and retirement of `termin-gui`.

## Phase 1 - Core Contracts

- [x] Define child layout policy per child: fixed, preferred, flex, stretch.
- [x] Add child metadata storage without making parent/child imply memory
  ownership.
- [x] Add max-size constraints and overflow behavior.
- [x] Add hit-test helper API for root and containers.
- [x] Add pointer hover tracking in `tc_ui_document`.
- [x] Add pointer capture for pressed/draggable widgets.
- [x] Add focus handle and focusable flag.
- [x] Add keyboard event ABI.
- [x] Add text input event ABI.
- [x] Add callback/signal storage pattern for C++ widgets.
- [x] Add stable widget id/name/debug metadata.
- [x] Add dirty flags: layout dirty, paint dirty, state dirty.
- [x] Move common computed bounds and size constraints into `tc_widget`.
- [x] Add canonical parent/ordered-children links and mutation APIs to
  `tc_widget` without making tree links imply recursive ownership.
- [x] Add common visible, enabled and mouse-transparent flags.
- [x] Make layout, hit testing and event routing consume the
  common `tc_widget` state without parallel container-specific copies.
- [ ] Add theme/style structs and make built-in widgets consume them.
- [ ] Add font provider or measurement service so `Label` measure uses real
  font metrics.
- [x] Add tests for stale child handles inside containers.
- [x] Add tests for event propagation order and capture release.
- [x] Add tests for focus handoff and keyboard routing.

Phase 1 notes:

- `tc_ui_document`, its generation slots, roots and interaction handles are
  implemented in C. Slots contain only `tc_widget*`, generation and transient
  destroy state; they are not a parallel widget record.
- `tc_widget` now owns common geometry, size constraints, state flags, a direct
  parent pointer and an ordered child pointer array. Tree mutation validates
  adoption, document identity and cycles; attaching performs atomic reparenting
  and removes the child from explicit roots.
- Plain destroy detaches a widget and orphans its children. Explicit recursive
  destroy walks canonical children and no longer asks widget vtables for a
  competing recursive-destroy list. Common child storage is released by the C
  core before the optional language deleter runs; a null deleter represents a
  borrowed/static widget.
- Built-in containers register their children in the canonical tree. Box paint,
  layout, hit testing and events follow canonical order; grid relationship
  metadata is filtered by canonical membership; single-content, splitter and
  tab membership is derived from canonical children.

- Child layout policy is implemented in
  `termin-gui-native/include/termin/gui_native/widgets.hpp` and
  `termin-gui-native/src/widgets.cpp` via `LayoutPolicy`, `LayoutItem` and
  typed `BoxLayout::add_*_child` helpers. Containers still store handles plus
  metadata only; document ownership remains centralized in `tc_ui_document`.
- `NativeWidget` now separates hard minimum, preferred and maximum size.
  Built-in widgets use preferred size for natural layout so flexible children
  can shrink before overflowing.
- `BoxLayout` resolves each child to basis/preferred size, then distributes
  extra space by grow weights or deficit by shrink weights. Fixed/preferred
  children with zero shrink may intentionally overflow; clamped children stop
  at max extent and remaining extra is redistributed.
- `tc_ui_document_hit_test` and `NativeWidget::hit_test` provide root and
  container hit-test helpers. `BoxLayout` returns the deepest visible native
  child by reverse child order and falls back to its own handle when a point is
  inside the container but no live child is hit.
- `tc_ui_document` now tracks the hovered widget handle from pointer events and
  supports pointer capture through `tc_ui_document_set_pointer_capture`,
  `tc_ui_document_pointer_capture` and `tc_ui_document_release_pointer_capture`.
  Captured widgets receive pointer events directly until release or destroy.
- `tc_widget` exposes `TC_WIDGET_FOCUSABLE`; `tc_ui_document` tracks focused
  widget handle, focuses a focusable hit target on pointer down, clears focus
  on non-focusable hits, and dispatches keyboard/text input events to the
  focused widget through C ABI vtable hooks.
- C++ widgets expose a typed `Signal<Args...>` storage pattern with connection
  ids and disconnect support. `Button::clicked`, `Checkbox::changed` and
  `Slider::changed` are wired to pointer/state changes; the C++ showcase uses
  `Slider::changed` to update its progress bar.
- `tc_widget` exposes stable id/name/debug metadata pointers through C ABI
  accessors. C++ `Widget` owns the backing strings for `set_stable_id`,
  `set_name` and `set_debug_name`, so debug metadata remains stable after
  temporary construction strings go out of scope.
- `tc_widget` exposes dirty flags for layout, paint and state. C++ widgets mark
  layout/paint on sizing and layout-affecting container changes, paint on visual
  changes, state/paint on value changes, and clear layout dirty after applying
  `layout()`.
- Headless coverage: `termin_gui_native_widgets_test` checks default stretch
  layout compatibility, mixed fixed/preferred/flex distribution, flexible
  shrink, max extent clamping, preferred overflow, topmost-root hit order,
  deepest child hit order, stale child handle skipping, hover updates, capture
  routing outside bounds, hover/capture cleanup on destroy, focus routing,
  focus rejection for non-focusable widgets, focused key/text dispatch, signal
  emit/disconnect behavior and signal emission from button/checkbox/slider
  interactions, plus owned widget metadata stability and C ABI metadata
  accessors, dirty flag marking/clearing and separation from focusable flags.
- Visual verification remains deferred until the SDL/offscreen renderer smoke
  is available on the host display backend.
- C++ test executables now undefine `NDEBUG`, so `assert`-based headless
  contracts run in Release as well as Debug builds.
- Python-defined widgets now dispatch measure, layout, paint, pointer, hit-test,
  key, text and destroy callbacks through a complete `tc_widget_vtable`.
  `WidgetRef` exposes common state, canonical parent/children and mutation via
  document plus handle without copying widget fields or owning the document.
- Initial Python document factories construct native C++ `HStack`, `VStack`,
  `Panel`, `Label` and `Button` widgets and return the same `WidgetRef` used by
  Python-defined widgets.
- The document retains each adopted Python body until its C deleter runs under
  the GIL. Focused Python tests cover callback routing, canonical child
  traversal, recursive destroy order, rejection of double adoption, re-adoption
  after destroy, stale handles and ref invalidation on document teardown.

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
- [x] Python binding tests for every command type.

Phase 2 notes:

- Python coverage in `termin-gui-native/python/tests/test_gui_native.py` now
  exercises `PushClip`, `FillRect`, `StrokeRect`, `Line`, `Text` and `PopClip`
  through the bound `PaintContext` and validates the resulting command fields.
- Packaging note: standalone `cmake --install` for `termin-gui-native` can
  install the fresh Python module under `sdk/lib/python`, while the active SDK
  import path resolves `termin.gui_native` from
  `sdk/lib/python3.10/site-packages`. The full `./build-sdk.sh --no-wheels`
  flow removes the legacy `sdk/lib/python` staging tree and the Python binding
  test passes through the normal `site-packages` import path.

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
- [x] `Separator`.
- [x] `TextInput` single-line skeleton.
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

Phase 3 notes:

- `Separator` emits a deterministic fill command and participates in
  preferred-size layout.
- `TextInput` is a focusable single-line skeleton with text insertion,
  backspace/delete, caret movement and submit signal. It uses approximate
  glyph advance until the font measurement service lands.

## Phase 4 - Layout And Containers

- [x] `BoxLayout` primitive.
- [x] `HStack` convenience wrapper.
- [x] `VStack` convenience wrapper.
- [x] `GridLayout`.
- [x] `ScrollArea`.
- [x] `Splitter`.
- [x] `GroupBox`.
- [x] `TabView` / tabs.
- [ ] Overlay container.
- [ ] Dialog root/container.
- [ ] Menu popup container.
- [ ] Toolbar layout.
- [ ] Status bar layout.

Acceptance:

- [ ] Layout tests cover empty, one child, many children.
- [x] Layout tests cover padding, spacing, min/max, flex distribution.
- [ ] Paint tests cover clipping.
- [ ] Event tests cover child order, clipping and overlay precedence.
- [ ] Destroy tests prove containers do not leak child widgets.

Phase 4 notes:

- `HStack` and `VStack` are thin `BoxLayout` wrappers for source-porting
  ergonomics. The showcase uses them instead of raw orientation arguments.
- `GridLayout` supports explicit fixed/preferred/flex/stretch rows and columns,
  padding, row/column spacing, child row/column spans, recursive destroy,
  reverse-order hit-testing and pointer routing. The showcase palette now uses
  it, and `termin_gui_native_widgets_test` covers track distribution and spans.
- `GroupBox` supports a titled header, one content handle, content padding,
  clipped child paint, content hit-testing/event routing and recursive destroy.
  The showcase wraps its control row in a group box.
- `Splitter` supports horizontal/vertical two-pane layout, split fraction,
  divider thickness, min extents, divider hit-testing, pointer-capture dragging
  and recursive destroy. The showcase preview area now uses it.
- `ScrollArea` supports one content handle, viewport clipping, wheel scrolling,
  clamped offsets, clipped hit-testing and recursive destroy of content.
- `TabView` supports simple tab headers, selected page layout, body clipping,
  header click switching, selected-page hit-testing and recursive destroy of
  pages.

## Phase 5 - Input, Focus And Interaction

- [x] Pointer move/down/up/wheel event ABI and basic dispatch.
- [ ] Hover enter/leave callbacks.
- [ ] Pressed state lifecycle.
- [x] Pointer capture API.
- [x] Focusable flag and direct focus assignment.
- [ ] Tab focus traversal.
- [x] Keyboard event ABI.
- [x] Text input ABI.
- [ ] Parent-chain event bubbling.
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
- [ ] Implement Python-defined widgets with an embedded `tc_widget`, Python
  vtable dispatch and an adoption retain/deleter pair.
- [ ] Implement handle wrappers for already-native widgets without creating a
  second widget state object.
- [ ] Add Python tests for stale handles and document-destroy behavior.
- [ ] Add Python showcase that uses native layouts/widgets instead of custom
  Python paint-only widgets.
- [ ] Decide migration path for existing `tcgui.widgets.Widget`.
- [ ] Define multilingual widget factory registration and creation.
- [ ] Expose common inspect metadata and document/tree snapshots.
- [ ] Define serialization identity and state hooks for registered widgets.
- [ ] Define widget hot-reload invalidation/recreation behavior.

## Phase 11 - Showcase And Smoke Gates

- [x] C++ showcase compiles with basic widgets.
- [x] C++ showcase uses text, panels, buttons, checkbox, slider, progress,
  splitter, group box, grid palette, scroll area and tabs.
- [ ] Python showcase mirrors the C++ showcase.
- [x] Headless draw-list snapshot test for showcase structure.
- [ ] Offscreen renderer pixel smoke for text + rect + clip.
- [ ] Manual SDL smoke once visual verification is available.
- [ ] Screenshot capture path for future visual regression checks.

Phase 11 notes:

- The C++ showcase now uses text, panels, buttons, checkbox, slider, progress,
  `Splitter`, `GroupBox`, grid palette, `Separator`, `TextInput`, `ScrollArea`
  and `TabView`.
- The showcase tree is built by shared `build_showcase(Document&)` code used by
  both the SDL examples and `termin_gui_native_showcase_test`. The dedicated
  `termin_gui_native_showcase` example is the primary manual visual smoke entry
  point; `termin_gui_native_rect_window` remains as a compatibility wrapper.
  The snapshot test fixes draw-list command totals by type after an 800x600
  layout.

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
