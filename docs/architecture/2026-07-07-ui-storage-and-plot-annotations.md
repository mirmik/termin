# UI Storage and Plot Annotation Architecture

This note fixes the target direction for the C++ migration of `termin-gui`
and for upcoming plot markers, labels and callouts in `tcplot`.

## Problem

`termin-gui` currently keeps the retained widget tree, layout, event routing,
focus state and overlays in Python. Primitive drawing is already moving in the
right direction: reusable rendering code such as `tgfx::Canvas2DRenderer`,
`Text2DRenderer` and `Text3DRenderer` lives in `termin-graphics`, and `tcplot`
already uses those C++ renderers directly for plot chrome and labels.

The remaining issue is ownership and domain boundaries:

- C++ runtimes must be able to use UI without Python.
- Widget lifetime should be explicit and inspectable, not Qt-style implicit
  parent-owned object deletion hidden behind ordinary object references.
- Plot markers, labels, legends, callouts and interactive handles need a C++
  model, but they are not ordinary UI widgets. They live in plot coordinate
  spaces, need data transforms, clipping, picking and snapping, and should not
  make `tcplot` depend on `termin-gui`.

## Decision

Use an explicit intrusive widget model for retained UI. This is a specialization
of the common multilingual lifetime model described in
[Multilanguage component lifetime model](2026-07-09-multilanguage-component-lifetime-model.md):
`tc_widget`, `tc_component` and `tc_pass` embed their neutral C structure into
the language-specific implementation and are adopted by one owning container.

The core concept is a per-document storage owner:

```text
UiStorage / UiDocument
    adopts tc_widget instances through their language-specific deleters
    owns handle slots and generations
    returns WidgetHandle values

tc_widget
    is embedded into a C++, Python or other language implementation
    stores common widget state and tree links
    dispatches language-specific behavior through a vtable

WidgetHandle
    index + generation
    invalidates predictably after destroy/reuse

Ui systems
    layout, input routing, rendering and debugging operate over storage
```

There is no separate `WidgetRecord` carrying a second copy of widget state.
The document handle slot resolves directly to the adopted `tc_widget`. The
document is a lifetime and indexing domain, not a closed application framework.
It must not own windows, render devices, framegraph passes, plot data or
application state. Hosts provide input events, render contexts and presentation.

Expected split:

```text
termin-graphics
    backend-neutral renderers: Canvas2DRenderer, Text2DRenderer, Text3DRenderer,
    line renderers, texture and GPU utilities

termin-gui
    UiDocument, intrusive tc_widget tree, layout, input routing, focus/capture,
    overlays, theme/style state, multilingual factories and bindings

tcplot
    plot data, axes, transforms, plot annotation layers, markers, labels,
    legends, callouts and picking in plot coordinate spaces

termin-display / host application
    windows, surfaces, input sources, frame/pass lifecycle and presentation
```

## UI Storage Model

The preferred ownership model combines an intrusive C object with handle-based
references:

- A language-specific implementation embeds one `tc_widget` C structure.
- A UI document adopts that `tc_widget` and registers its pointer in a
  generation-checked handle slot.
- The slot is an index and lifetime guard, not another widget state object.
- External and cross-widget references use `WidgetHandle`, not owning pointers.
- A handle contains at least slot index and generation.
- Destroying a widget invalidates existing handles through generation mismatch.
- Parent-child links live in `tc_widget` and describe structure, but do not hide
  lifetime rules or imply recursive destruction.
- Subtree destruction is an explicit API operation.
- The creator supplies the deleter used when the document releases the widget:
  C++ heap widgets use `delete`, Python widgets retain the Python object and use
  `Py_DECREF`, and borrowed/static widgets use an explicitly non-owning policy.
- A Python-defined widget embeds `tc_widget` just as a C++ widget does. A Python
  wrapper around an already-native widget may instead hold a document reference
  plus a handle.

The Python bridge implements this without a second widget record. Its adopted
shim contains the single `tc_widget` plus a retained Python body and releases
that body from the C deleter under the GIL. Python-facing `WidgetRef` values
contain a shared invalidation state and a generation-checked handle; the state
does not own `tc_ui_document`. Widget and document destruction therefore make
all outstanding refs stale without extending container lifetime. Python
callback failures are logged at the C boundary, retained for the duration of
the traversal, and rethrown by the calling Python `Document`/`WidgetRef` API.

The common state required by language-neutral systems belongs in `tc_widget`:

```text
identity/lifetime    vtable, deleter, body, language, document, handle
tree                 direct tc_widget parent and ordered child pointers
layout               computed bounds, common min/preferred/max constraints
state                visible, enabled, mouse-transparent, focusable, dirty flags
diagnostics          stable id, name, debug name
```

The physical C structure may group these fields into embedded substructures,
but they remain one allocation and one widget object. Widget-specific state such
as text, scroll offset, selected tab, padding or a collection model stays in the
language-specific implementation. Layout metadata that describes a relation
between a container and a child (grow/shrink, grid cell, tab title) stays in the
container and may refer to the child by handle; the generic `tc_widget` child
pointer list remains the canonical structural tree. Direct pointers are safe
inside the tree because adopted widget addresses are stable and tree mutation
is validated against the shared document. Handles remain the external and
cross-subsystem reference format.

Behavior can still be divided into internal systems without introducing a
second widget record:

```text
UiDocument (C)  adoption, handles, generations, create/destroy
tc_widget       common state and canonical parent/children/order
UiLayoutEngine  measure/layout passes
UiInputRouter   hit-test, focus, capture, hover
UiRenderer      traversal through Canvas2DRenderer
UiTheme         style tokens and inherited style state
```

These systems operate on `tc_widget` resolved from a handle. They must not keep
parallel copies of bounds, flags or tree links. The important constraints are
explicit lifetime, a single source of widget state and inspectability.

## Multilanguage Lifecycle And Factories

`tc_widget` should converge with `tc_component` and `tc_pass` on shared
infrastructure where practical:

- one adopting container and one creator-supplied deleter;
- composition-based inheritance through an embedded C structure and vtable;
- language runtime factories capable of creating registered widget types;
- neutral inspect metadata and serialization hooks;
- deterministic invalidation during destroy and hot reload.

Moving widgets between documents is not a required operation. A widget has no
meaning outside its owning document, and document transfer would complicate
handles, tree consistency and language lifetime without a current use case.

The C ABI is expected to evolve during active development. Before supporting
independently versioned binary plugins, the embedded structure must gain an
explicit compatibility contract such as ABI version/structure size, or plugins
must be required to rebuild against exactly the same SDK.

## Debugging Contract

The storage model should make UI state easy to inspect:

- list all live widgets in a document;
- show type, name, flags, parent, children, z/order, computed rect and dirty
  state;
- show focus, hover, pressed/captured widget handles and overlay stack;
- validate parent-child consistency;
- detect stale wrappers through generation mismatch;
- dump a UI document snapshot for tests and regression reports.

There should not be a single global `UiStorage` for the whole process. Use one
storage per UI document, surface, window or tool. A separate debug registry may
track live storages so tooling can enumerate all UI documents without merging
their lifetimes.

## Plot Annotations Are Not Widgets

Plot annotations should be retained data in `tcplot`, not `termin-gui`
widgets. Examples:

- data point markers;
- crosshairs;
- selected range spans;
- callout labels;
- legends;
- draggable plot handles;
- hover labels snapped to nearest series point.

These objects need plot-domain anchors:

```text
Data2D
Data3D
SeriesPointRef
AxesFraction
ViewportPixel
ScreenPixel
```

Rendering can use `tgfx::Canvas2DRenderer`, `Text2DRenderer`, `Text3DRenderer`
and specialized plot shaders, but the retained model belongs to `tcplot`.

`termin-gui` may provide a `PlotWidget` adapter that embeds a plot view in a UI
tree and forwards input, but `tcplot` must remain usable without Python and
without `termin-gui`.

## Migration Direction

1. Keep `termin-graphics` as the reusable GPU/rendering substrate.
2. Complete `tc_ui_document` as the owning container and move all common tree,
   layout and state fields into the embedded `tc_widget` contract.
3. Port basic widgets as C++ implementations embedding `tc_widget`.
4. Add Python-defined widgets that embed the same `tc_widget`, plus thin handle
   wrappers for already-native widgets.
5. Build plot annotation storage and APIs in `tcplot`.
6. Add optional `termin-gui` plot embedding after `tcplot` annotations are
   independent.

The older `termin-gui/docs/c-core-migration-analysis.md` remains useful as an
inventory of current Python widget responsibilities. Its embedded C
structure/body/vtable direction is retained, while ownership is clarified:
`tc_ui_document` adopts the complete multilingual widget through a single
deleter and handles refer directly to that object. There is no separate native
widget record that would make Python widgets second-class implementations.
