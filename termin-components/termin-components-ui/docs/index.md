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

## Input contract

Display input is routed to the selected viewport in viewport-local pixel
coordinates and then through the scene input-capability priority order.
`UIComponent` defaults to priority `1000`, propagates the native document's
handled result, and therefore stops lower-priority camera/game handlers when a
widget consumes the event.

The native path supports mouse button/move, wheel, key, committed UTF-8 text,
device-neutral pointer down/move/up/cancel, focus loss, cursor intent,
clipboard access, and platform text-input activation. Platform callbacks are
borrowed from the attached display endpoint; hosts cancel focus and detach the
services before destroying their window. The component does not own an SDL,
Android, or window object.

The document model currently owns one pointer interaction. For touch input,
`UIComponent` claims the first contact whose DOWN is handled, keeps that
pointer identity through UP/CANCEL, and ignores additional contacts until the
claimed stream ends. Focus/capture loss and component teardown cancel the
interaction and clear document focus deterministically.

World-space UI uses the same document interaction path. A
`WorldUiSurfaceComponent` describes a local XY rectangle, projects normalized
world-pointer rays onto it, and forwards the resulting UV coordinates to a
referenced `UIComponent`. The UI component converts UV through its published
physical presentation extent and density before dispatching ordinary native
MOVE/DOWN/UP/LEAVE/CANCEL events. It owns one world pointer at a time, matching
the document's single-pointer contract.

The surface publishes the renderer-independent `world_pointer_surface`
capability from `termin-input`. It does not depend on OpenXR, controller types,
render targets, materials, or collision geometry; XR and future gaze/mouse
interactors consume the same capability.

Committed UTF-8 text is part of the common input ABI. IME preedit/composition,
selection ranges, grapheme-aware editing, and simultaneous multi-touch widget
gestures remain outside this contract and are tracked by #863.
