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

Use an explicit UI storage model for retained widgets.

The core concept is a per-document storage owner:

```text
UiStorage / UiDocument
    owns widget slots and generations
    returns WidgetHandle values
    stores common widget state and tree links

WidgetHandle
    index + generation
    invalidates predictably after destroy/reuse

Ui systems
    layout, input routing, rendering and debugging operate over storage
```

`UiStorage` is a lifetime/storage domain, not a closed application framework.
It must not own windows, render devices, framegraph passes, plot data or
application state. Hosts provide input events, render contexts and presentation.

Expected split:

```text
termin-graphics
    backend-neutral renderers: Canvas2DRenderer, Text2DRenderer, Text3DRenderer,
    line renderers, texture and GPU utilities

termin-gui
    UiStorage / UiDocument, widget tree, layout, input routing, focus/capture,
    overlays, theme/style state, Python wrappers for widget handles

tcplot
    plot data, axes, transforms, plot annotation layers, markers, labels,
    legends, callouts and picking in plot coordinate spaces

termin-display / host application
    windows, surfaces, input sources, frame/pass lifecycle and presentation
```

## UI Storage Model

The preferred ownership model is handle-based:

- A UI document owns all widget records in a slot storage.
- Public references are `WidgetHandle` values, not raw owning pointers.
- A handle contains at least slot index and generation.
- Destroying a widget invalidates existing handles through generation mismatch.
- Parent-child links describe tree structure, but do not hide lifetime rules.
- Subtree destruction is an explicit API operation.
- Python/C#/other language wrappers hold a document reference plus a handle.
  They observe or command C++ storage; they do not become the primary owners of
  native widget lifetime.

The storage can be implemented as one owner object with internal subsystems or
as separate components:

```text
UiStorage       handles, generations, create/destroy
UiTree          parent/children/order
UiLayoutEngine  measure/layout passes
UiInputRouter   hit-test, focus, capture, hover
UiRenderer      traversal through Canvas2DRenderer
UiTheme         style tokens and inherited style state
```

The important constraint is explicit lifetime and inspectability. The exact
class names can change during implementation.

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
2. Introduce a C++ UI storage/document layer in `termin-gui`.
3. Port basic widgets to native C++ records/classes behind `WidgetHandle`.
4. Add Python wrappers as thin handle references over the C++ storage.
5. Build plot annotation storage and APIs in `tcplot`.
6. Add optional `termin-gui` plot embedding after `tcplot` annotations are
   independent.

The older `termin-gui/docs/c-core-migration-analysis.md` remains useful as an
inventory of current Python widget responsibilities, but its language-owned
`body`/vtable sketch is not the preferred final ownership model. Native C++
widget storage should be the primary path; language callbacks and custom
widgets are extension points.

