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
- The C++ widget layer includes the basic controls, text editors, value/media
  widgets, core containers and a virtualized `ListWidget` over reusable
  collection/selection models, a virtualized `TreeWidget` over stable-ID
  hierarchy/expansion models and a virtualized `TableWidget` with independent
  stable row and column models.
- Native and Python tests cover ownership, recursive destroy, paint output,
  layout, input routing, mixed-language lifetime and large-model virtualization.

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
- [x] Add target-to-root pointer and keyboard bubbling with consumption.
- [x] Add direct hover enter/leave transitions and pressed lifecycle state.
- [x] Add focus handle and focusable flag.
- [x] Add focus enter/leave notification and Tab/reverse-Tab traversal.
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
- [x] Add theme/style structs and make built-in widgets consume them.
- [x] Add font provider or measurement service so `Label` measure uses real
  font metrics.
- [x] Add tests for stale child handles inside containers.
- [x] Add tests for event propagation order and capture release.
- [x] Add tests for focus handoff and keyboard routing.

Phase 1 notes:

- `tc_ui_document`, its generation slots, roots and interaction handles are
  implemented in C. Slots contain only `tc_widget*`, generation and transient
  destroy state; they are not a parallel widget record.
- The C core is split behind one private `tc_ui_document_internal.h` state
  definition: `tc_ui_document.c` owns lifecycle/storage/services,
  `tc_widget.c` owns common widget state and canonical-tree mutation, and
  `tc_ui_interaction.c` owns paint composition, overlays, hit testing, focus
  and event routing. Public headers and ABI remain unchanged, and internal
  cross-module helpers use hidden visibility.
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
- `tc_ui_document` owns hovered, pressed, pointer-capture and focused handles.
  Hit testing selects one canonical target; ordinary pointer events then bubble
  target-to-root until the first `Handled`. Capture takes priority over pressed
  routing, pressed takes priority over the current hit for move/up, and wheel
  remains routed from the current hit. Hover `Enter`/`Leave` notifications are
  direct and do not bubble.
- Each pointer/key/text route is snapshotted as generation handles before the
  first callback. Destruction or reparenting during a callback cannot expose a
  dangling `tc_widget*`; stale route members are skipped and the route order
  remains the order observed at dispatch start.
- `tc_widget` exposes `TC_WIDGET_FOCUSABLE`; `tc_ui_document` tracks focused
  widget handle, focuses the nearest focusable hit ancestor on pointer down,
  and bubbles keyboard/text input from focus to root. Focus transitions invoke
  the vtable `focus_event` hook. Unhandled `Tab`/`Shift+Tab` wraps through
  effectively visible/enabled focusables in canonical root/depth-first order.
- Common visibility/enabled/focusable setters invalidate interaction state
  immediately. Hiding or disabling an ancestor clears hover, capture, pressed
  and focus handles inside that subtree, so language-specific widget bodies do
  not need parallel cleanup rules.
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
- Headless coverage: `termin_gui_native_document_test` additionally fixes the
  exact enter/leave, target-to-root bubbling, pressed, keyboard bubbling and
  forward/reverse traversal order. It destroys a pointer target from its own
  callback and verifies that the frozen route safely continues at the live
  parent. `termin_gui_native_widgets_test` checks default stretch
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
- `tc_ui_document` exposes a C text-measure service callback with explicit UTF-8
  byte lengths. `UiDrawListRenderer` binds its `FontAtlas` as the production
  provider, while headless tests install deterministic proportional metrics.
- Python-defined widgets now dispatch measure, layout, paint, pointer, hit-test,
  key, text, focus and destroy callbacks through a complete `tc_widget_vtable`.
  `WidgetRef` exposes common state, canonical parent/children and mutation via
  document plus handle without copying widget fields or owning the document.
- Initial Python document factories construct native C++ `HStack`, `VStack`,
  `Panel`, `Label` and `Button` widgets and return the same `WidgetRef` used by
  Python-defined widgets.
- The document retains each adopted Python body until its C deleter runs under
  the GIL. Focused Python tests cover callback routing, canonical child
  traversal, pointer-target destruction during bubbling, focus transitions and
  Tab traversal, recursive destroy order, rejection of double adoption,
  re-adoption after destroy, stale handles and ref invalidation on document
  teardown.

## Phase 2 - Draw List And Renderer Parity

- [x] Fill rect command.
- [x] Stroke rect command.
- [x] Line command.
- [x] Clip push/pop commands.
- [x] Text command.
- [x] Rounded fill/stroke commands and renderer-level radius support.
- [x] Texture/image command.
- [x] Polyline command with draw-list-owned point storage.
- [x] Filled/stroked circle and arc commands.
- [x] Explicitly exclude arbitrary path commands from current UI parity. The
  legacy painter and current widget set do not require them; path verbs,
  winding/fill rules, joins/caps and tessellation ownership need a separate
  plot-driven contract rather than an underspecified command.
- [ ] Nine-slice or border-image command for scalable panels.
- [ ] Per-command debug label for renderer diagnostics.
- [ ] Optional command bounds for test/debug inspection.
- [x] Renderer smoke into offscreen target with pixel readback.
- [x] Python binding tests for every command type.

Phase 2 notes:

- Python coverage in `termin-gui-native/python/tests/test_gui_native.py` now
  exercises rect, rounded rect, circle, arc, polyline, clip, line and text
  commands through the bound `PaintContext` and validates the resulting
  command fields and copied point storage.
- Draw lists own text and polyline backing storage. Texture commands hold a
  non-owning backend-neutral `TextureHandle` id; the device resource must stay
  alive until `UiDrawListRenderer::render` returns.
- `termin_gui_native_renderer_pixel_smoke` renders through
  `UiDrawListRenderer` and `Canvas2DRenderer` into a Vulkan offscreen target.
  Pixel readback covers sampled texture output, text signal, rounded corners,
  circle fill and the intersection of nested clips.
- Packaging note: standalone `cmake --install` for `termin-gui-native` can
  install the fresh Python module under `sdk/lib/python`, while the active SDK
  import path resolves `termin.gui_native` from
  `sdk/lib/python3.14t/site-packages`. The full `./build-sdk.sh --no-wheels`
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
- [x] `TextArea` multiline editor.
- [x] `SpinBox`.
- [x] `SliderEdit`.
- [x] `ComboBox` with document overlay dropdown.
- [x] `IconButton` with text/texture icon.
- [x] `ImageWidget` with texture/image command dependency.
- [x] `Canvas` custom paint callback widget.

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
- `TextInput` is a focusable single-line control with text insertion,
  backspace/delete, selection, caret movement and submit signal. Font metrics
  drive preferred size, pointer-to-caret mapping, selection and caret paint.
  Long text remains inside an inner clip and scrolls horizontally to keep the
  caret visible.
- `TextArea` uses one canonical UTF-8 buffer with computed line spans. It
  supports multiline selection and replacement, horizontal/vertical
  navigation, Home/End, pointer drag selection, wheel scrolling and
  horizontal/vertical caret scrolling. The initial contract is deliberately
  unwrapped; word wrapping remains a separate layout feature rather than a
  second text representation.
- Editor carets and selection anchors are byte offsets at the C++ and Python
  boundaries, normalized to UTF-8 codepoint boundaries. Editing never splits
  a codepoint, and invalid UTF-8 initial/set/event/clipboard text is rejected
  and logged.
- Clipboard access is injected into `tc_ui_document` through non-owning C
  callbacks. C++ and Python-facing tests cover cross-codepoint and multiline
  copy/cut/paste through the same host service.
- `Slider` now supports finite min/max ranges and optional step quantization.
  `SpinBox` provides clamped stepping and fully parsed numeric editing;
  `SliderEdit` owns canonical Slider/SpinBox children and synchronizes changes
  in both directions without parallel child state.
- `ComboBox` owns one reusable, unparented overlay handle. The dropdown supports
  outside dismissal, keyboard selection, hover and wheel scrolling. Unlike the
  legacy widget it does not yet expose a draggable scrollbar thumb; wheel
  overflow behavior and overlay destruction are covered by native tests.
- `IconButton` supports UTF-8 text icons or a non-owning texture handle.
  `ImageWidget` preserves intrinsic aspect by default. `Canvas` supports a
  main/overlay texture pair, fit/zoom/pan transforms, image-coordinate pointer
  signals and a clipped custom paint callback. Fit is a persistent view mode
  that recomputes on layout resize; Python exposes fit state, zoom/pointer
  signals and explicit texture clearing for host-managed GPU lifetimes.
- Media widgets deliberately do not decode files, retain CPU arrays or
  create/update/destroy GPU resources. Hosts inject registered tgfx2 texture
  handles and keep them alive through rendering, matching draw-list ownership.
- All six widgets have typed Python references/factories. Python callbacks map
  changed/clicked/custom-paint behavior onto the same C++ widget instances.

## Phase 4 - Layout And Containers

- [x] `BoxLayout` primitive.
- [x] `HStack` convenience wrapper.
- [x] `VStack` convenience wrapper.
- [x] `GridLayout`.
- [x] `ScrollArea`.
- [x] `Splitter`.
- [x] `GroupBox`.
- [x] `TabView` / tabs.
- [x] Document overlay stack and modal policy.
- [x] Dialog root/container.
- [x] Menu popup container.
- [x] Toolbar layout.
- [x] Status bar layout.

Acceptance:

- [ ] Layout tests cover empty, one child, many children.
- [x] Layout tests cover padding, spacing, min/max, flex distribution.
- [ ] Paint tests cover clipping.
- [x] Event tests cover child order and overlay precedence.
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
- `tc_ui_document` owns an ordered overlay presentation stack without creating
  a second widget tree or ownership relationship. Overlay entries reference
  unparented, non-root widgets by generation handle and carry modal,
  dismiss-on-outside, pointer-transparent and tooltip policy flags.
- `tc_ui_document_paint` paints ordinary roots followed by overlays in stack
  order. Hit testing walks overlays top-down before roots; tooltip and other
  pointer-transparent entries paint but do not intercept input.
- Modal overlays form an input barrier. Pointer events outside the barrier are
  consumed, keyboard/text routing cannot escape the active modal scope, and
  focus traversal includes the modal plus any overlays stacked above it.
- Tooltip timing remains host-owned. The C core exposes only the pure
  `tc_ui_tooltip_rect` placement/clamping helper, so clocks and presentation
  scheduling stay deterministic in tests and appropriate to each host.

## Phase 5 - Input, Focus And Interaction

- [x] Pointer move/down/up/wheel event ABI and basic dispatch.
- [x] Host-supplied deterministic click-count ABI and double-click activation.
- [x] Hover enter/leave callbacks.
- [x] Pressed state lifecycle.
- [x] Pointer capture API.
- [x] Focusable flag and direct focus assignment.
- [x] Tab focus traversal.
- [x] Keyboard event ABI.
- [x] Text input ABI.
- [x] Host-injected clipboard ABI.
- [x] Parent-chain event bubbling.
- [ ] Shortcut routing.
- [x] Modal overlay input capture.
- [x] Dismiss-on-outside and Escape behavior.
- [x] Disabled state and event blocking.
- [ ] Cursor request API.

## Phase 6 - Theme And Style

Start with data structures and tests; postpone visual tuning.

- [x] `tc_ui_theme` with role-based colors, spacing, border widths, font sizes
  and minimum metrics, owned by `tc_ui_document` by value.
- [x] Semantic role and masked `tc_ui_style_override` stored directly in each
  `tc_widget`, without a second widget/style record.
- [x] Default theme matching the current native showcase palette.
- [x] Disabled/hover/pressed/focused/checked state layers.
- [x] Explicit inherited overrides along the canonical parent chain.
- [x] Runtime theme revision, full-widget invalidation and switch tests.
- [x] C++ and Python-facing theme/style APIs and inheritance/state tests.

## Phase 7 - Collection Widgets

Port only after layout, focus and events are reliable.

- [x] `ListWidget`.
- [x] `TreeWidget`.
- [x] `TableWidget`.
- [x] `FileGridWidget`.
- [x] Virtualized flat collection and table presentation.
- [x] Selection model: single, multi, range.
- [x] Expand/collapse model for tree.
- [x] Header/column resize model for table.
- [x] Keyboard navigation.
- [x] Scroll integration.

Phase 7 notes:

- `CollectionModel` owns UTF-8 item records and emits typed structural changes.
  `SelectionModel` shifts selected/current/anchor indices on insert and erase,
  so a shared model can mutate without silently retargeting selection.
- `ListWidget` is a scroll viewport rather than a container of one widget per
  row. Layout and paint compute a bounded visible range; native and Python
  tests exercise a 10,000-item model and assert bounded draw-command output.
- Selection supports ordinary, Ctrl-toggle, Shift-range and Ctrl+Shift-additive
  input, plus Home/End/arrow navigation, Ctrl+A and Enter activation. Disabled
  items reject direct selection and are skipped by keyboard navigation.
- The shared model is retained by the widget and released when the widget is
  destroyed. C++ and Python lifetime tests cover both sides of that contract.
- `TreeModel` owns stable numeric node IDs, validated parent/ordered-child
  relationships and cycle-safe move/reorder operations. `TreeExpansionModel`
  keeps presentation state separate from hierarchy data and reconciles erased
  IDs.
- `TreeWidget` caches a flattened visible-row projection only when hierarchy
  or expansion revisions change. Layout and paint operate on a bounded viewport
  range without creating one widget per node; 10,100-node C++ and Python tests
  fix that contract. Pointer toggles/selection, scrolling, disabled-node skip,
  Up/Down/Home/End/Left/Right navigation, activation and delete requests share
  the same C++/Python implementation.
- Tree reparent/reorder semantics are available through `TreeModel::move`.
  External OS/editor drag payload transport remains an explicit future host
  input boundary rather than a tree-specific fallback event API.
- `TableModel` gives each row an internal stable numeric ID and emits typed
  reset/insert/update/erase changes. `TableColumnModel` owns unique stable
  column IDs, fixed/stretch sizing, min/max constraints and explicit resize
  mutations; header clicks are signals so sorting remains a host/model concern.
- `TableWidget` reuses `SelectionModel`, paints only its bounded visible row
  range, skips disabled rows and supports Home/End/arrow navigation and Enter
  activation. Resize uses document pointer capture and remains active outside
  widget bounds. C++ and Python tests cover 10,000 rows, sizing, mutation,
  callbacks and shared-model lifetime.
- SDL button sequence counts propagate through `tc_input_manager`,
  `tc_mouse_button_event`, `tc_ui_pointer_event` and both Python bridges.
  List/tree/table/file-grid widgets activate exactly on count 2. The editor's
  former `high_resolution_clock` double-click detector was removed, so every
  consumer now shares the host-defined sequence with no local timing fallback.
- `FileGridWidget` shares `CollectionModel` and `SelectionModel` with the list;
  `CollectionItem` carries an optional backend-neutral texture ID for grid/icon
  presentation without embedding asset loading in the widget. Responsive
  column/row layout, bounded visible-range paint, disabled-item navigation,
  wheel scrolling, scrollbar pointer capture, context-menu requests,
  activation and delete requests use the same C++/Python implementation.
- Native and Python tests cover a 10,000-item responsive grid, bounded draw
  output, texture commands, model mutation/lifetime, callback errors,
  scrollbar dragging outside the widget and deterministic double-click
  activation. External drag payload transport stays a host input boundary.

## Phase 8 - Menus, Dialogs And Overlays

- [x] `Menu`.
- [x] `MenuBar`.
- [x] `ToolBar`.
- [x] `StatusBar`.
- [x] `Dialog`.
- [x] `MessageBox`.
- [x] `InputDialog`.
- [x] `FileDialogOverlay`.
- [x] `ColorDialog`.
- [x] Popup placement for menu and submenu overlays.
- [x] Modal stack.
- [x] Escape/enter/default-button behavior.

Phase 8 chrome notes:

- `CommandModel` owns stable command IDs and validated UTF-8 action/separator
  descriptors, including enabled/checkable/checked state, icon text or texture,
  shortcut/tooltip metadata and an optional nested command model. Typed model
  changes keep toolbar, future menus and shortcut consumers on one state source.
- `ToolBar` computes deterministic action/separator geometry directly from the
  shared model, paints without per-action widgets, uses pointer capture for
  press/release semantics and updates checkable state before emitting activation.
  Tooltip scheduling remains a host concern exposed through hovered metadata.
- `StatusBar` has persistent and temporary message state with explicit
  `clear_message`. Timeout scheduling belongs to the host event loop instead of
  a nondeterministic widget-local monotonic clock.
- `Menu` is a document overlay backed by `CommandModel`: it clamps root and
  fallback-left submenu placement to an explicit viewport, bounds tall content
  with wheel/keyboard scrolling, skips disabled/separator entries, toggles
  checkable commands before activation and owns teardown of its entire submenu
  overlay chain. Ancestor-model tracking rejects cyclic submenu expansion.
- `MenuBar` owns exactly one root popup, keeps its title strip inside the popup
  hit scope for adjacent hover switching, and exposes cycle-safe shortcut
  dispatch over the same command graph. Outside/Escape dismissal, nested
  keyboard navigation, switching, shortcut activation and Python callback
  parity are covered by C++ and bundled-Python tests.
- `Dialog` owns one canonical content subtree plus validated stable-ID actions,
  centers and clamps itself inside an explicit viewport, uses the document
  modal stack for pointer/focus containment, restores the previous modal/root
  focus on dismissal and emits one typed result per show cycle. Escape maps to
  the declared cancel action; Enter activates the focused button or bubbles to
  the declared default action. `MessageBox` and `InputDialog` build their
  content on this same core, including text-submit acceptance and optional
  input results. C++ tests cover nested modal focus/lifecycle and the showcase
  draw snapshot paints an open message box; Python exercises the same APIs.
- `FileDialogModel` separates path/filter/history/confirmation policy from UI
  and filesystem access. Its injected `FileDialogFileSystem` makes failure and
  navigation behavior deterministic in tests, while
  `NativeFileDialogFileSystem` is the production `std::filesystem` provider.
  `FileDialogOverlay` composes navigation, list, filter and save-name controls
  on `Dialog`; the dialog's pre-action validation hook keeps invalid accepts
  open and emits exactly one optional path per show cycle. Open-file,
  save-file and open-directory modes have C++ and bundled-Python coverage.
  `FileDialogService` separately defines the asynchronous host/platform picker
  boundary: a host chooses it or the overlay explicitly, with no implicit
  fallback between them.
- `ColorPickerModel` owns validated RGB/HSV/alpha conversion and revisioned
  change flags. `ColorPicker` owns renderer-neutral 64x64/1x64 RGBA CPU
  surfaces and invalidation signals, while GPU texture allocation/update/free
  remains a host responsibility represented by explicit texture IDs. Without
  those IDs it paints bounded draw-list gradients, so headless and non-GPU
  hosts retain the complete picker. SV, hue and optional alpha drag paths use
  document pointer capture; old/new checkerboard previews and hex text share
  the same paint path. `ColorDialog` composes the picker on `Dialog` and emits
  exactly one optional typed color per show cycle. C++/Python tests cover HSV
  conversion, surface revisions, both paint paths, capture outside bounds and
  accept/cancel delivery.

## Phase 9 - Rich And Specialized Widgets

- [x] `RichTextView`.
- [x] `FrameTimeGraph`.
- [x] `Viewport3D`.
- [x] `SceneView` / graphics item bridge decision.
- [ ] Plot annotation widgets or shared plot overlay primitives.
- [ ] Texture preview widget.
- [x] Profiler panel primitives.
- [x] Registry/table inspector primitives.

Phase 9 rich-text notes:

- `RichTextModel` owns validated UTF-8 lines and styled segments independently
  of the widget. Optional color plus bold/italic flags are explicit native
  values; the small HTML adapter recognizes `br`, `pre`/`p`, `b`/`strong`,
  `i`/`em`, span color/font-weight/font-style and common/numeric entities.
- `RichTextView` wraps through the document text-measurement service, clips and
  virtualizes visible rows, scrolls by wheel or captured scrollbar drag, and
  uses the document clipboard service for read-only selection/copy. Selection
  offsets refer to source UTF-8 bytes, so visual wrapping never inserts false
  newlines into copied text. C++ and Python share the same model lifetime.
- `FrameTimeModel` is an explicitly host-fed, bounded sample history; it has no
  profiler singleton or clock dependency. `FrameTimeGraph` owns only native
  draw-list presentation, configurable ordered target/warning thresholds and
  empty-state rendering. Its right-aligned history, 60/30 FPS guides and
  green/yellow/red ranges have matching C++/Python model-lifetime tests.
- `termin.editor_core.ProfilerController` is the UI-neutral sampling boundary:
  it selects only closed frames, deduplicates revisions, owns smoothing and
  exposes typed section rows. Both native and temporary `tcgui` profiler views
  consume it, so the migration does not maintain two profiler policies.
- Registry/collection production paths use native table/tree/grid models with
  stable IDs, live filtering, activation and right-click context signals.
  `TextInput` exposes changed/submitted signals to Python; `TableWidget` and
  `TreeWidget` expose context-menu requests without toolkit callbacks in core.
  Tests cover 10,000 registry rows and 2,000 project files while bounding the
  painted range to visible rows/tiles.
- `Viewport3D` depends only on the backend-neutral `ViewportSurfaceHost`
  contract: validity, texture identity, framebuffer size/resize and typed
  pointer/wheel/key/text dispatch. It retains the host explicitly, paints a
  placeholder for detached/stale surfaces, and releases the host on detach or
  document destruction. Resize ordering is deterministic (`before_resize`,
  then host resize), including late surface attachment after layout.
  `termin.display.Display` supplies both the owned texture surface and typed
  input dispatch; the path never transports a native pointer as a Python
  integer. External drag enter/move/leave/drop uses a separate
  MIME/payload/local-coordinate host contract. Headless C++ and Python tests
  cover compositing, ordering, complete input routing, drag/drop, stale
  surfaces, detach and destruction lifetime.
- `GraphicsScene` is a retained 2D tool-scene, not a plot annotation or render
  scene model. It exclusively owns shared item roots; items exclusively own
  children through strong child/weak parent links, reject cycles and expose
  stable z-order, custom local hit tests and draw-list paint callbacks.
  `SceneView` owns only camera/interaction state and a shared scene: anchored
  zoom, captured pan/drag, selection, hover and explicit pointer/key/text
  adapter handlers. Embedded widgets remain generation-checked document
  handles and are attached as canonical `tc_widget` children; removal/view
  destruction detaches without silently destroying caller-owned widgets.
  `tcnodegraph.native_view` is now the production projection in the native
  pipeline editor. Its toolbar, dialogs, context menu, graph and embedded
  controls switch as one tree because a native child cannot live inside the
  legacy `tcgui` tree. The old projection remains isolated to the temporary
  tcgui entrypoint until that frontend retires.

## Phase 10 - Python Bridge And Mixed-Language Use

- [x] Bind native widget handles and core document APIs.
- [x] Bind layout APIs.
- [x] Bind event structs.
- [x] Bind draw text/image commands.
- [x] Implement Python-defined widgets with an embedded `tc_widget`, Python
  vtable dispatch and an adoption retain/deleter pair.
- [x] Implement handle wrappers for already-native widgets without creating a
  second widget state object.
- [x] Add Python tests for stale handles and document-destroy behavior.
- [x] Add Python showcase that uses native layouts/widgets instead of custom
  Python paint-only widgets.
- [ ] Decide migration path for existing `tcgui.widgets.Widget`.
- [x] Define multilingual widget factory registration and creation.
- [x] Expose common inspect metadata and document/tree snapshots.
- [x] Define serialization identity and state hooks for registered widgets.
- [x] Define widget hot-reload invalidation/recreation behavior.

Phase 10 factory notes:

- Registered widget factories are a lifecycle facet of the shared
  `tc_runtime_type_registry`. They carry ABI version, implementation language,
  module owner and parent type; created widgets link into the same runtime
  instance lists used by other polyglot types.
- Factory results choose exactly one explicit lifetime policy: owned widgets
  provide a deleter, while borrowed widgets do not. The document remains the
  sole handle-slot owner in both cases.
- Unregistering a widget type recursively destroys all of its live widget trees
  across documents before factory userdata is released. Existing handles become
  stale and a later registration creates instances with fresh generations.
- Python registration retains the callable in factory userdata, binds the
  returned high-level object to the adopted native handle, and propagates
  constructor/bind failures after rolling back adoption.
- The document inspect snapshot is an owned neutral C value: widget records are
  in stable slot order, while child, root and overlay order are represented
  explicitly with generation handles. It includes copied identity strings,
  language/ownership, geometry, flags, dirty/style state, theme revision and
  hover/press/capture/focus handles.
- C++ owns snapshots through move-only `DocumentSnapshot`; Python converts the
  same data to detached dict/list/value structures through
  `Document.inspect_snapshot()`. Snapshot tests mutate and destroy the live tree
  afterward to prove there are no borrowed widget or string references.
- Widget factory ABI v2 owns optional paired state hooks in the same runtime
  facet and exchanges strict `tc_value` dictionaries. Common stable id/name/
  debug identity moved into `tc_widget`-owned copied storage, removing the
  previous C++/Python string-lifetime split.
- Versioned `termin.gui.document` schema v2 stores registered type names,
  common geometry/constraints/behavior/style/cursor state, per-type state and
  record-index child/root/overlay topology. Runtime handles, dirty flags and
  interaction state are not persisted.
- Restore requires an empty document, creates instances through registered
  factories, restores state before topology, and rolls every created instance
  back on malformed relations or hook failure. C++ uses owning `tc::trent`;
  Python uses detached strict primitive/list/dict values and explicit hook
  callables without reflection fallbacks.
- Owner hot reload deliberately uses explicit invalidation instead of trying to
  recreate widgets while replacement factories are unavailable. Unregistering
  an owner invalidates all matching live instances across documents, releases
  factory userdata only afterward and leaves every stale Python/native handle
  generation-safe. Recursive document topology takes precedence over module
  ownership: a foreign-owner descendant is destroyed with an unloaded parent,
  while its still-registered factory can create a fresh instance.

## Phase 11 - Showcase And Smoke Gates

- [x] C++ showcase compiles with basic widgets.
- [x] C++ showcase uses text, panels, buttons, checkbox, slider, progress,
  text input/area, virtualized list, splitter, group box, grid palette, scroll
  area and tabs.
- [x] Python showcase exercises equivalent native layout, text, command,
  collection, status and profiling controls without paint-only stand-ins.
- [x] Headless draw-list snapshot test for showcase structure.
- [x] Offscreen renderer pixel smoke for text + texture + rounded geometry +
  nested clip intersection.
- [x] Manual SDL offscreen OpenGL showcase smoke.
- [x] Deterministic one-frame desktop screenshot capture path.

Phase 11 notes:

- The C++ showcase now uses text, panels, buttons, checkbox, slider, progress,
  `Splitter`, `GroupBox`, grid palette, `Separator`, `TextInput`, `TextArea`,
  `ScrollArea` and `TabView`.
- The showcase tree is built by shared `build_showcase(Document&)` code used by
  both the SDL examples and `termin_gui_native_showcase_test`. The dedicated
  `termin_gui_native_showcase` example is the primary manual visual smoke entry
  point; `termin_gui_native_rect_window` remains as a compatibility wrapper.
  The snapshot test fixes draw-list command totals by type after an 800x600
  layout.
- `termin.gui_native.build_python_showcase` builds a separate Python-authored
  native tree with shared command/collection/tree/table/frame-time models. Its
  installed-SDK test fixes the 800x600 draw-list totals, verifies balanced
  clipping, long UTF-8 content, selection/model state and focus reachability.
  `examples/showcase.py` presents the same tree through `SDLBackendWindow`.
- The C++ SDL showcase accepts `TERMIN_GUI_NATIVE_SCREENSHOT`. It freezes the
  time-dependent controls, reads back one frame to binary PPM and exits. Two
  SDL offscreen OpenGL runs produced byte-identical 800x600 captures during
  implementation; Vulkan continues to use the context-free renderer pixel
  smoke when the SDL offscreen driver cannot create Vulkan windows.

## Phase 12 - Editor Migration Slices

Do not start these until basic containers, text, focus and scrolling are
stable.

- [x] Establish one native editor host/root boundary with SDL event routing,
  clipboard, SDK font, draw-list rendering and graceful engine-loop shutdown.
- [x] Replace a small editor utility panel with native UI (Profiler).
- [x] Port registry viewer table skeleton (Inspect Registry).
- [x] Port Core Registry and Resource Manager multi-page catalog skeletons.
- [x] Port project browser collection/tree skeleton.
- [x] Port scene tree skeleton.
- [x] Port scalar, boolean, string, enum, vec3, color and action inspector
  fields plus the production native Entity Inspector shell.
- [x] Port list and asset/handle inspector fields.
- [x] Port component catalog plus add/remove actions with undo.
- [x] Port clip, agent-type and navmesh-area selectors.
- [x] Port remaining specialized inspector fields.
- [x] Port the Foliage brush extension model and native panel projection.
- [x] Port the ProceduralMesh shared command model and native command panel.
- [x] Port the ProceduralMesh native document tree and primitive parameter
  editors from the shared declarative schemas.
- [x] Port ProceduralMesh extrude, wall and operation-transform parameters.
- [x] Port wall-corner, sketch-plane, contour and path point parameters.
- [x] Replace the native workspace placeholder with the production editor
  viewport chain: `Viewport3D` + display-owned offscreen surface, scene
  attachment, input router, picking/selection callbacks and explicit shutdown.
- [x] Port ProceduralMesh viewport interaction through the shared core model,
  native viewport geometry and extension callback boundary.
- [x] Port viewport list.
- [x] Port the pipeline editor and `tcnodegraph` projection to native
  `SceneView`.
- [ ] Port build profiles window.
- [x] Port framegraph debugger shell.
- [x] Port editor chrome utility dialogs: Python Console, Settings and About.
- [x] Port Undo Stack Viewer and Audio Debugger diagnostics.
- [x] Port Scene Properties, Layers & Flags and Shadow Settings dialogs.
- [x] Port Project Settings dialog.
- [x] Port Agent Types and NavMesh Areas dialogs.
- [x] Port SpaceMouse runtime integration and settings dialog.
- [x] Complete Scene Manager native editor-attachment workflow.
- [x] Complete Scene Manager native render-attachment workflow.
- [x] Decide old `termin.editor_tcgui` coexistence boundary.

Agent Types and NavMesh Areas share a toolkit-neutral staged controller. The
native Scene-menu dialogs persist the agent list and all 64 area names only on
OK; Cancel now discards the draft instead of leaking the legacy dialog's live
singleton mutations.

The native editor now owns the SpaceMouse lifecycle end to end: it opens the
device against the native editor attachment, polls it from the editor loop and
closes it during shutdown. Settings project through a toolkit-neutral model to
the native View-menu dialog and apply live. The controller also uses the public
`EditorSceneAttachment.camera_manager` boundary rather than its former private
field access.

Scene Manager has a toolkit-neutral snapshot/action controller and a native
Debug-menu projection. Scene inspection, selection, mode changes, duplication,
confirmed unload and lifecycle cleanup are native. The initial projection kept
all attachment actions capability-disabled until their owner graphs could be
switched atomically.

Editor Attach/Detach now routes through `EditorSceneSession`: the viewport
attachment, scene hierarchy, entity inspector and all three scene-settings
controllers switch as one operation, selection/extensions are cleared, open
scene dialogs are dismissed and a failed switch rolls back to the previous
scene. Dynamic editor commands and Python executor context resolve the active
scene rather than retaining the startup scene.

Render Attach/Detach now routes through `RenderSceneSession`. It uses the native
display workspace as the rendering manager's display factory, restores viewport
input routing after attach, synchronizes viewport and render-target configs
before detach, and removes native tabs/displays left empty by the operation. A
failed attach rolls the partial rendering attachment back. Live editor MCP
smoke covered attaching a scene into a newly created native display, detaching
it and switching the editor attachment to another scene and back.

The offscreen OpenGL editor process smoke also exposed and fixed three startup
and shutdown gaps: native startup now registers Python builtin component specs
before creating editor entities, nullable SceneManager callbacks are accepted
by their nanobind contract, and the attachment-owned render target is unlocked
after viewport removal before it is freed. The process now reaches and exits
its main loop cleanly. Missing packaged editor shader sources remain tracked
separately as Kanboard #310.

Phase 12 host notes:

- The coexistence boundary is entrypoint-level, never two widget trees inside
  one window. `termin_editor` owns one `tc_ui_document`; production backend
  selection has been removed.
- `termin.editor_native.NativeUiHost` owns render target resize, layout/paint,
  SDL pointer/key/text/click-count routing, clipboard, PNG/MCP capture and
  shutdown. The native Profiler panel is attached to the same root as a fixed
  right-side slice and is toggled by the Debug/Profiler F7 command. Its toolbar,
  status, `FrameTimeGraph` and virtualized `TableWidget` are native widgets;
  a production MCP run verified real `Include UI` section rows and screenshot
  capture. The key ABI is aligned directly with `tcbase.Key`, and the default
  font is installed in the SDK.
- The native minimal shell has stable menu, toolbar, project, workspace,
  inspector and status roots.
  Its headless snapshot and event-router tests are complemented by an actual
  two-frame `sdk/bin/termin_editor` SDL offscreen OpenGL smoke.
- The workspace now owns a real editor viewport rather than a label
  placeholder. `NativeEditorViewport` composes the native texture surface,
  editor-only display, `EditorSceneAttachment`, per-viewport editor input
  manager and display router; the native entrypoint registers the edited scene
  with `SceneManager`, routes picking selection back into the scene tree and
  inspector, synchronizes the transform gizmo and pumps extension overlays from
  the after-render hook. Its idempotent shutdown detaches the surface, releases
  the attachment-owned render target/pipeline, unregisters and destroys the
  display, closes the FBO and clears all interaction callbacks atomically.
  The current automated session cannot repeat the visual production smoke:
  SDL's offscreen driver has no Vulkan window support and the local X server
  rejects `DISPLAY=:0` without authorization. Headless lifecycle/input tests
  and the SDK-backed binding gate cover this slice until an authorized display
  is available.
- Executor, MCP server and shader-runtime services moved to `editor_core`.
  Screenshot capture is provider-injected, so native composed UI and legacy
  viewport capture use the same explicit MCP executor flow. The end-to-end native
  gate captured a 1280x720 PNG through the stock MCP client and then stopped
  the editor through `execute_python_script` with clean server/engine shutdown.
- `RegistryCollectionController` and `ProjectBrowserController` own filtering,
  selection/activation, filesystem navigation, ignored paths, breadcrumbs,
  drag payload data and context actions without importing a widget toolkit.
- Native screenshot capture synchronously composes the current document and
  waits for the backend-neutral `Tgfx2Device.wait_idle()` boundary before GPU
  readback. Live MCP QA caught the OpenGL target still exposing a partially
  completed frame immediately after a dynamic inspector rebuild; explicit GPU
  completion makes that first capture deterministic instead of relying on a
  later presentation frame.
- `RegistryCatalogController` extends the same collection contract to dynamic
  multi-page catalogs with per-page filters, selection state, hierarchical
  parent links and column schemas. Debug/F9 opens eleven public core registry
  sources: nine flat registries plus virtualized Scene/Entity and
  Scene/Agent/NavMesh trees. Debug/F10 opens nine public runtime asset
  registries, project component classes and a hierarchical watched-file page.
  Resource activation calls the public asset
  `ensure_loaded()` boundary and refreshes the page instead of reading the
  legacy viewer's private `_mesh_assets`/`_texture_assets` caches. A bundled
  runtime bootstrap observed 23 component types, 26 pass types and 65 interned
  strings; the headless native gate covers page switching, dynamic columns,
  independent filters and 10,000-row virtualization. Live visual QA for this
  first catalog increment was unavailable because the active X11 display rejected the
  process authorization cookie; the earlier Inspect/Project MCP gate remains
  valid.
- The native entrypoint now owns the same production `ProjectFileWatcher`
  composition as tcgui, including 17 module/component/default-asset
  processors, editor-loop polling and deterministic disable on shutdown. The
  processor factory moved into `editor_core`; a real project bootstrap produced
  31 watcher nodes. `NavMeshRegistry.instances()` replaces the legacy viewer's
  direct access to `_instances`.
- `SceneHierarchyController` is the toolkit-neutral scene projection and
  action boundary. The native shell now hosts the production scene tree with
  stable UUID selection/expansion state, undo-backed create/rename/duplicate/
  visibility/delete actions, deterministic reparent/reorder projection and
  `.glb`/`.gltf`/`.prefab` OS drops. `TreeWidget` exposes typed
  before/inside/after/root drag positions through C++ and Python, retains
  pointer capture until drop, and paints the active drop target. Widget-originated
  selection and expansion update controller state without rebuilding the tree
  from inside the active signal dispatch. The temporary tcgui scene tree now
  projects the same controller and contains no separate `EntityOperations` or
  hierarchy action implementation. Root and child order is stored by
  `tc_entity_pool`, exposed as `Entity.sibling_index`, published as a scene
  structure event and preserved by scene serialization plus undo/redo.
- `InspectorFieldsController` is now the single inspect discovery, inherited
  field, layout metadata, conditional visibility and mixed-value contract used
  by both frontends. Native typed projections cover scalar spin boxes, bool,
  string, enum, vec3, color and action fields; `Button` and `Checkbox` now have
  typed Python refs/signals. `EntityInspectorController` owns entity name/layer,
  descendant layer application, component selection and undo-backed component
  field writes. The production native shell attaches this panel to its stable
  right-side inspector host and scene-tree selection drives it directly.
  Rebuilding dynamic field rows recursively destroys the old native subtree,
  with a headless lifetime test preventing retained widget trees. The next
  increment added a Python `ScrollArea` bridge and fixed `BoxLayout.measure()`
  to honor preferred/min/max constraints, so dynamically sized inspector
  content scrolls rather than being compressed into the viewport. Native
  fields now cover 64-bit `layer_mask` through a lifetime-safe modal selector,
  generic typed lists with selection/reorder/remove and undo, and resource
  handle kinds through the UI-neutral `InspectorResourceCatalog` with none,
  select and create workflows. Production `slider` and `interval_slider`
  fields now use native slider/edit composites; interval bounds remain
  editable and clamp the current value through the same mergeable undo path.
  The specialized `list[vec3]` projection adds point selection, direct XYZ
  editing, insertion, reorder and removal instead of stringifying coordinates.
  Inline material metadata now projects a native material editor backed by the
  shared `MaterialInspectorController`; tcgui consumes the same immutable
  shader-property snapshots and mutation/persistence path. Scalar, vector,
  color and texture properties are typed, and the UI-neutral
  `MaterialTextureSourceCatalog` supplies default, asset and live render-target
  color/depth choices to both frontends. The final stray `AudioSource.clip`
  schema was migrated from the unsupported `audio_clip` kind to serialized
  `audio_clip_handle` values, so selecting a clip cannot store a dictionary in
  the runtime component.
  `EntityInspectorController` now also projects
  the component catalog and owns undo-backed add/remove operations; the native
  inspector presents the categorized submenu and reconciles selection after
  external undo so stale `TcComponentRef` values cannot survive into shutdown.
  `ComponentEditorExtensionRegistry` and `ComponentEditorExtensionSession`
  moved out of tcgui into editor-core. They enforce one active extension,
  detach-before-destroy cleanup and rollback after attach/projector failures.
  The native entrypoint owns an independent projector registry and a recursively
  destroyed extension host, while tcgui is an adapter to the same lifecycle.
  Dynamic clip, navigation-agent and 64-area navmesh choices now come from the
  UI-neutral `InspectorSpecialChoices` provider and reuse the same typed combo
  projection plus undo-backed field writes. Clip discovery uses the public
  component/inspect boundary, while navigation dependencies remain lazy and
  injected so importing the inspector model cannot bootstrap hidden native
  registries. The Foliage brush behavior is now a single toolkit-neutral
  extension model shared by tcgui and native projectors instead of two paint
  implementations. Its native panel exposes mode, radius, stamp count and
  asset/instance state; `NativeComponentExtensionContext` owns balanced tool
  lifetime plus ordered click/key/overlay callback registration, now connected
  to the native editor viewport's picking and after-render paths. Domain imports
  stay lazy until post-bootstrap extension registration. ProceduralMesh
  document ownership, command results, dirty/regenerate behavior and
  presentation snapshots now live in
  `ProceduralMeshExtensionModel`; the tcgui extension delegates to that owner.
  Its native panel exposes draw/close/finish/stop, primitive, boolean,
  extrude/wall/clear commands and live document/selection/status state. The
  existing tcgui contour and wall-height drag tests pass through the shared
  mutation boundary. The native document tree recursively projects the shared
  `DocumentTreeNode` graph, preserves collapsed state by structural stable IDs
  and routes selection back through the shared controller. Primitive parameter
  rows are generated from `PrimitiveSpec.param_schema`; vec3, scalar, integer
  and boolean edits use native typed controls and the same dirty/regenerate
  path. A pointer-driven test selects a nested boolean input and increments a
  native spin box. Extrude vector, wall height/thickness/alignment and shared
  operation center/rotation now use the same typed controls and controller
  commands; pointer tests cover each mutation path. Concrete projectors were
  split into `foliage_extension` and `procedural_mesh_extension`, reducing the
  lifecycle/context registry module from 568 to 151 lines while preserving
  post-bootstrap lazy imports. The parameter host now has its own native
  `ScrollArea`; variable wall-corner offsets, plane origin/x/y axes and
  contour/path points use the same controller mutation path and survive
  recursive parameter-subtree replacement. ProceduralMesh ray picking,
  draw-click fallback, contour/path point dragging, variable wall-height drag
  and debug overlay rendering now live in
  `ProceduralMeshViewportInteraction` under `editor_core`; tcgui is a thin
  presentation adapter to that owner. `ViewportGeometryController` likewise
  moved to `editor_core`, and `NativeEditorViewport` injects its camera,
  display, interaction system and native widget bounds through the same
  geometry contract. Native tests exercise OXY-plane draw fallback and a full
  pointer down/up contour drag, including balanced viewport-tool lifetime,
  component regeneration and native status/parameter subtree refresh.
  Pointer-driven tests cover all parameter families. Headless/full gates
  passed; live visual QA was attempted but the available X11 `:0` rejected
  authorization and SDL's fallback offscreen driver cannot create a Vulkan
  window.
- Viewport-list migration now has one `ViewportListController` in editor-core
  for display/viewport/internal-entity/render-target snapshots, selection,
  rename and action requests. Both tcgui and native tree projections consume
  that contract. The production native shell shows the editor display and
  managed targets, synchronizes entity selection with the scene tree, and
  wires display, viewport and render-target add/remove/rename actions.
  `NativeDisplayWorkspace` owns one native `TabView`, the editor page and every
  secondary `Display` page. Each secondary page has one surface-owning `Display`,
  `Viewport3D`, `BasicDisplayInputManager` and rendering-manager registration;
  removal detaches the tab, releases per-viewport input managers,
  unregisters and destroys the display and recursively destroys
  the page. `TabView` now exposes dynamic page removal/title/handle APIs and a
  typed selection signal through C++ and Python, so list selection and workspace
  tabs stay synchronized without tcgui ownership. The central gate covers the
  C++ mutation contract, Python bridge, workspace lifetime and both frontend
  projections. Live QA was attempted again on 2026-07-10; X11 `:0` rejected the
  process authorization cookie and SDL's fallback offscreen driver cannot create
  a Vulkan window, while the backend-neutral renderer pixel smoke remains green.
- Pipeline editing now has one toolkit-neutral `PipelineEditorController` for
  graph construction, pass/resource schemas, dynamic material sockets,
  load/save identity and mutations. Both the temporary tcgui window and the
  native editor consume that owner; the former no longer carries a duplicate
  serializer or node factory. `tcnodegraph.native_view` projects the shared
  graph into native `GraphicsScene` items with socket connection, Bezier edge
  hit testing, node/group dragging, selection deletion and embedded typed
  parameter widgets. The production native shell opens the complete editor on
  F11 with native file/input dialogs and context commands. Explicit close
  destroys the dialog, graph parameter subtree and separately owned context
  overlay. Controller, projection, F11 wiring, file roundtrip and lifetime are
  covered by bundled-Python tests. The legacy tcgui `NodeGraphView` remains only
  because tcgui remains an explicit compatibility frontend; it can now be
  deleted together with that frontend.
- Framegraph debugging now uses one C++ `FrameGraphDebugger`, attached directly
  to `RenderingManager`, for native UI, MCP inspection and capture export.
  `EditorFramegraphDebuggerService` is an editor-core automation/export adapter;
  both frontends project the same native owner. The native F12 dialog covers
  target/mode/pass/symbol/resource selection, stable duplicate-pass indices,
  pause, channel/HDR controls, schedule/pass JSON/timing/stats, main and depth
  previews, and startup `--debug-resource` selection. Preview composition uses
  `FrameGraphPresenter` to render capture textures into explicitly owned color
  targets before the document draw-list is recorded. `NativeUiHost` exposes a
  removable pre-render callback boundary so changed targets can never leave a
  stale texture handle in the current Vulkan draw list. Closing the dialog
  cancels frame-local capture requests and releases preview targets; shutdown also
  unregisters the callback and destroys the dialog tree. Headless tests cover
  F12, reopen/close, presenter options, resize/release, host ordering, MCP
  compatibility and render-target deduplication. The former Python model and
  injected `FrameDebugCapturePass` have been removed.
- Editor chrome utilities now share toolkit-neutral owners instead of copying
  policy between frontends. `PythonConsoleController` owns the transcript,
  prompt and execution state for the native F6 dialog and the temporary tcgui
  panel; the canonical executor now accepts the blank line that completes a
  buffered interactive `for`/`def`/`if` statement. `EditorSettingsController`
  validates, normalizes and persists editor paths, font sizes and MCP state;
  the native Settings dialog uses the native file-dialog service and can apply
  the font size live across every theme role. About data is assembled by one
  immutable editor-core model and escaped by the native rich-text projection.
  The Edit, Debug and Help menu commands, reopen/close teardown, callback
  disconnection and garbage-collection boundaries have bundled-Python tests.
- Undo/redo and audio diagnostics now likewise use toolkit-neutral immutable
  snapshots. The native Debug menu opens explicitly owned dialogs for both;
  undo pushes publish refreshes to an open history view, while the audio model
  receives a narrow engine diagnostics protocol and lists only active channels.
  The temporary tcgui dialogs consume the same controllers instead of directly
  interrogating the undo stack or audio singleton. Headless tests cover active,
  paused and uninitialized audio states plus undo/redo branches, reopen and
  recursive teardown.
- Scene-level settings now have one `ScenePropertiesController`,
  `SceneNamesController` and `ShadowSettingsController` shared by native and
  temporary tcgui projections. The controller separates the scene render mount
  from the resource catalog, fixing the legacy pipeline picker aliasing both as
  `rm`; add/remove now call the canonical mount API. Fresh scenes explicitly
  materialize their render-state extension before reading shadow settings, so
  the dialog no longer receives `None` before the first rendering mutation.
  Native Scene menu commands cover undoable background/ambient/skybox edits,
  pipeline membership, all 64 layer/flag names, live shadow method/softness/bias
  and mirror-scene propagation. Tests cover validation, undo, mirroring,
  reopen and recursive teardown.
- Project settings now use one `ProjectSettingsController` for render sync,
  generated output, standalone window defaults and resource-ignore paths.
  Resource and render invalidations are distinct: player-window changes do not
  rescan assets, while output/ignore changes do. The native Edit menu dialog
  preserves pending text fields while applying live render/window controls and
  persists through the canonical `ProjectSettingsManager`; tcgui consumes the
  same owner. Repository audit found no legacy Build Profiles window to port:
  that unchecked item is new UI over the existing
  `termin.project_build.profile_build` backend, not a frontend migration.
- Project build and scene-file orchestration now live in `editor_core` rather
  than `editor_tcgui`. The native File menu supports new/load/save/save-as and
  restores the project's last scene; its Game menu exposes desktop and Android
  builds plus built/standalone launch through the same controller as tcgui.
  Quest/OpenXR build/install/launch now likewise uses one asynchronous
  `QuestOpenXRBuildController`; native drains its worker notifications from the
  editor loop, while tcgui projects the same snapshots through `ui.defer`.
  A live native MCP screenshot verified all five actions, status/log output and
  dialog teardown without invoking Gradle or adb. The process smoke also fixed nullable
  `RenderingManager` callback bindings and now shuts the rendering manager down
  before destroying the native window/context; the three-frame offscreen
  OpenGL run exits cleanly.
- Native Play/Stop now projects the shared `GameModeModel` through explicit
  editor/render session adapters. F5 and the toolbar copy the editor scene,
  transfer the editor attachment and render configuration to the game scene,
  update their labels/status, then delete the game copy and restore the editor
  scene and tree expansion state on Stop. The model retains the original editor
  scene name across the temporary attachment switch instead of asking the
  active game scene for it. A live MCP run observed `untitled(game)` in PLAY,
  refreshed executor context to that scene, and restored `untitled` in STOP;
  shutdown remained clean.
- The canonical `termin_editor` entrypoint now has only the native UI route.
  Launcher project activation invokes the same path; backend override and the
  production tcgui import were removed. An SDK-backed three-frame offscreen
  OpenGL smoke passed through the production command.
- Launcher project/session behavior now lives in the toolkit-neutral
  `LauncherController`: recent selection, screen/form state, validation,
  create/open/remove actions and launch outcomes have headless coverage.
  Filesystem pickers and process dispatch are explicit injected services;
  the remaining tcgui `LauncherApp` only builds widgets and projects controller
  state, so a native launcher frontend no longer needs to duplicate behavior.
- The migrated tcgui Core/Inspect/NavMesh/Resource viewer modules, their shared
  `RegistryViewerDialog`, launcher methods and menu callbacks were deleted.
  An architecture test fixes their absence. Card #302 remains open only for
  retiring `ProjectBrowserTcgui` with the explicit legacy frontend.

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
- [x] `file_grid_widget.py`
- [x] `frame_time_graph.py`
- [ ] `grid_layout.py`
- [ ] `group_box.py`
- [ ] `hstack.py`
- [ ] `icon_button.py`
- [ ] `icon_theme.py`
- [ ] `image_widget.py`
- [ ] `input_dialog.py`
- [ ] `label.py`
- [x] `list_widget.py`
- [ ] `loader.py`
- [ ] `menu.py`
- [ ] `menu_bar.py`
- [ ] `message_box.py`
- [ ] `panel.py`
- [ ] `progress_bar.py`
- [ ] `renderer.py`
- [x] `rich_text_view.py`
- [ ] `scroll_area.py`
- [ ] `separator.py`
- [ ] `shortcuts.py`
- [ ] `slider.py`
- [ ] `slider_edit.py`
- [ ] `spin_box.py`
- [ ] `splitter.py`
- [x] `status_bar.py`
- [x] `table_widget.py`
- [ ] `tabs.py`
- [ ] `text_area.py`
- [ ] `text_input.py`
- [ ] `theme.py`
- [x] `tool_bar.py`
- [x] `tree.py`
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
