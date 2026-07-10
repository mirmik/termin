# Native Framegraph Debugger

Status: production native migration slice implemented; the temporary tcgui
projection remains until the default editor frontend changes.

## Ownership

`FramegraphDebuggerModel` remains the single owner of target selection,
debugger-pass connection, internal-symbol capture, preview parameters and
derived diagnostic text. `EditorFramegraphDebuggerService` lives in
`editor_core` and exposes that same model to MCP inspection and capture export;
it has no widget-toolkit dependency.

The native dialog is a projection over that owner. Opening binds model signals
and connects the selected capture path. Dismissing unbinds signals, removes all
debugger passes from known pipelines, clears captures and releases preview GPU
targets. The persistent dialog object may then be reopened; editor shutdown
permanently unregisters its host callback and destroys the document subtree.

## Preview Composition

Captured textures cannot be handed directly to `ImageWidget`: depth display,
channel selection and HDR highlighting require `FrameGraphPresenter`. Each
preview therefore owns a sampled color target and renders the current capture
through the presenter before native UI composition. Targets are recreated on
capture-size changes and destroyed on dialog dismissal or shutdown.

`NativeUiHost` runs registered pre-render callbacks inside the active tgfx2
frame and before `Document.paint()` records texture identities into the draw
list. This ordering is essential: recreating a preview target after recording
the draw list could otherwise destroy a handle still referenced by the current
Vulkan frame. The callback boundary is explicit and removable; failure is
logged and propagated instead of silently dropping a preview update.

## Production Wiring

The native Debug menu opens the debugger with F12. The editor polls its model
once per frame while the dialog is open, exposes the shared automation service
to the owner-thread MCP executor, and honors `--debug-resource` by opening in
resource mode. `RenderingModel` supplies viewport and standalone-target
descriptors without duplicating managed targets already owned by a viewport.
