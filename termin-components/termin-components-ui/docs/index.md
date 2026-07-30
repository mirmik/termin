# Native scene UI component

`termin-components-ui` owns the native `UIComponent` runtime type. The
component contains only scene-facing CPU state:

- a generation-checked `UiDocumentAsset` handle;
- one independently materialized `tc_ui_document`;
- render/input priority and the accepted input-source mask.

It publishes the `scene_ui_document` component capability. Render and input
systems consume a snapshot containing the borrowed document handle, asset
generation, priority and input-source policy. The component never owns a
graphics context, painter, texture, font atlas, framebuffer or render target.

The serialized `ui_layout` field is a typed UUID reference with
`kind: ui_document`. Runtime packages register all referenced compiled UI
documents before native scene deserialization, so creating `UIComponent`
requires no Python bootstrap.

Asset and instance reload are replacement-first. A failed parse,
materialization or stale asset resolution leaves the component's live document
untouched. Engine-wide hot reload will publish coordinated replacements while
rendering is paused between frames; this component does not introduce its own
frame synchronization.

`termin.ui_components.UIComponent` is a thin nanobind projection of the same
C++ component and native document/asset handles. It does not import or expose
`tcgui` objects.
