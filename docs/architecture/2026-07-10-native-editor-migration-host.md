# Native Editor Migration Host

## Decision

Editor UI migration starts with one native host/root, not by embedding isolated
native panels into the legacy `tcgui.UI` tree. A `tc_widget` may only belong to
one `tc_ui_document`, and native overlays, focus, pointer capture and embedded
viewport/SceneView children all depend on that single canonical document.
Running two UI trees in one production window would split input, lifetime and
modal ownership and turn the migration path into a permanent compatibility
layer.

`termin.editor_native.NativeUiHost` is the new host boundary. It owns:

- one `Document`, `DrawList`, `PaintContext` and `DrawListRenderer`;
- the host-owned color attachment resized to the SDL framebuffer;
- layout, paint, render, present and deterministic shutdown ordering;
- SDL pointer/key/text translation, including host click counts;
- document clipboard services and a typed file-drop callback boundary;
- owner-thread PNG readback of the composed color target for screenshots/MCP.

`EditorPythonExecutor`, `EditorMcpServer` and editor shader-runtime setup now
live in `termin.editor_core`; their old `termin.editor_tcgui` modules are
temporary compatibility imports for legacy consumers. MCP screenshot capture
is an injected callable in the executor namespace, not a hard-coded lookup of
`EditorWindowTcgui._fbo_surface`. The native host injects its composed target;
the legacy editor injects its viewport surface. Both frontends therefore share
one transport, owner-thread queue and tool schema without sharing UI objects.

The platform event key values and `tc_ui_key_code` now use the same
`tcbase.Key`/GLFW-compatible integer contract. The host does not maintain a
translation table that could silently lose editor shortcuts. Unsupported keys
remain explicit `Unknown` events. SDL button events preserve their native
click count through the event dictionary into `PointerEvent`.

The default DroidSans font is installed in `sdk/share/termin/fonts`. Production
layout no longer depends on running from a source checkout; an explicit broken
`TERMIN_UI_FONT` is an error rather than a silent fallback.

## Migration order

1. Stabilize the native host and minimal menu/toolbar/central/status shell.
2. Move one low-coupling utility/profiler slice onto the native root.
3. Port registry/project collection views and the scene tree.
4. Port inspector fields and component extension panels.
5. Attach production `Viewport3D` and the `tcnodegraph` SceneView adapter to
   the same document.
6. Port remaining dialogs/launcher chrome, make native the only production
   entrypoint and remove `tcgui`/`termin.editor_tcgui` dependencies.

`termin_editor` now exercises the host through the normal
C++ embedded-Python `EngineCore` entrypoint. `TERMIN_EDITOR_NATIVE_SMOKE_FRAMES`
is a deterministic test-only frame limit used to prove graceful startup,
render/present and shutdown. The default is `native`; the temporary
`--ui=tcgui` compatibility path is an entrypoint choice during legacy
retirement, not a mixed-tree fallback.

The production MCP gate starts this entrypoint with an ephemeral loopback port,
captures the composed native UI through `capture_editor_screenshot`, then uses
`execute_python_script` to request window close on the editor thread. This
proves startup, transport, queued execution, GPU readback and shutdown as one
flow rather than as unrelated unit tests.

## First utility slice: profiler

The first production panel on the native root is the Profiler. Sampling and
presentation policy live in `termin.editor_core.profiler_model`, independently
of either widget toolkit. `ProfilerController` owns enable/detailed/include-UI
boundaries, selects the last complete frame and suppresses duplicate frames;
`ProfilerPresentationModel` owns smoothing, decay and flattened typed rows.
The temporary `tcgui` profiler view now consumes this same controller instead
of reading private C history and maintaining a second EMA implementation.

`termin.editor_native.profiler_panel` composes native `ToolBar`, `StatusBar`,
`FrameTimeGraph` and `TableWidget` instances. The shell exposes a checkable
Debug/Profiler command and F7 shortcut; function-key descriptors are supported
by the native menu shortcut parser. Python BoxLayout bindings expose explicit
fixed/preferred/flex/stretch policies, padding, spacing and extent limits so
production panels do not infer layout from preferred sizes.

The end-to-end gate enabled the panel and UI profiling through the editor MCP,
observed 13 live section rows, captured a 1280x720 composed screenshot and then
closed the window on the editor owner thread. The same work fixed an ABI bug
where policy-aware `append_child` attempted a C++ cast on Python widget bodies;
the bridge now branches on `native_language`, with registry lifecycle coverage.

## Registry and project collection slice

Registry and project views follow the same split as the profiler. The
toolkit-neutral `RegistryCollectionController` owns refresh, filtering,
selection, activation and context actions; `InspectRegistrySource` is a public
InspectRegistry adapter rather than a closure embedded in a dialog. The native
dialog composes `TextInput`, virtualized `TableWidget`, `RichTextView`, toolbar,
status and reusable context menu. Debug/Inspect Registry and F8 open the same
production dialog.

`ProjectBrowserController` owns filesystem scanning, ignored project paths,
breadcrumbs, navigation, selection/activation, drag payload data and action
dispatch. `NativeProjectBrowser` projects it into a lazy `TreeWidget` and
virtualized `FileGridWidget`; the native entrypoint now consumes launcher
project handoff and falls back to the saved project file. Session/module
loading remains a separate editor-core migration boundary rather than being
hidden inside the view.

The Python bridge gained TextInput changed/submitted signals and explicit
TableWidget/TreeWidget context-menu signals. Signal wiring in both new views
uses weak owner references, preventing `Document → callback → view → Document`
cycles; isolated nanobind lifetime gates remain clean. MCP QA used a real
project, observed 52 InspectRegistry rows, filtered component details and
captured both composed surfaces. Screenshot capture now forces one synchronous
owner-thread compose before readback, preventing a just-enqueued UI mutation
from racing the previous render target contents.

Core Registry and Resource Manager now use `RegistryCatalogController`, which
owns an ordered set of `RegistryPage` descriptors. Each page declares stable
toolkit-neutral columns, a `RegistrySource`, independent collection state and
an optional activation boundary. `NativeRegistryViewer` projects that catalog
through one ComboBox and replaces the native `TableColumnModel` on page change;
the single-page Inspect Registry remains the same view composition.

Core registry adapters live in `editor_core.registry_sources` and call the
public C/Python inspection APIs. `RegistryRow.parent_id` represents hierarchy;
filtered snapshots retain matching nodes and their ancestors, and the native
viewer swaps between virtualized TableWidget and TreeWidget projections.
Scene/entity and NavMesh scene/agent/source trees use this contract. Resource pages enumerate assets through
`AssetRuntimeManager.list_runtime_asset_names()` and `get_runtime_asset()`;
double activation calls `ensure_loaded()` and reloads the snapshot. This
removes the new frontend's dependency on legacy private asset-cache fields.
The native Debug menu exposes Core Registry on F9 and Resource Manager on F10.

`create_editor_project_file_watcher()` is now the shared production composition
boundary for module, component and default-asset processors. Both frontends use
it; native watches the selected project, polls on the owner thread and disables
the observer during shutdown. Resource Manager adds a hierarchical Watched
Files page for extension counts, directories, processors and tracked resource
names. `NavMeshRegistry.instances()` exposes an immutable sorted snapshot so
diagnostics no longer read its private class dictionary.

The migrated tcgui Core Registry, Inspect Registry, NavMesh Registry, Resource
Manager and shared RegistryViewerDialog modules were deleted together with
their launcher and menu paths. `ProjectBrowserTcgui` remains until the native
frontend becomes the default, because project navigation is still required by
the legacy production shell during staged migration.

## Scene hierarchy slice

`SceneHierarchyController` owns a UUID-keyed preorder projection, selection
and expansion state, context actions and file-drop policy without importing a
widget toolkit. Entity mutations continue through the shared
`EntityOperations` and `UndoStack` command boundary. The native dialog service
implements asynchronous input, choice and error contracts using document
overlays, while retaining dialogs until their callbacks finish without
creating document/view callback cycles.

`NativeSceneTree` projects controller snapshots into `TreeModel` and
`TreeExpansionModel`. Its toolbar, status and context menu live on the same
production native root as the project browser. `TreeWidget` provides typed
before/inside/after/root drag results in C++ and Python, pointer-capture-based
drag lifetime and visual drop feedback. OS file drops are accepted only over
the tree and routed to the hierarchy controller for `.glb`, `.gltf` and
`.prefab` imports. Widget-originated selection and expansion are applied
in-place so a model rebuild cannot invalidate native node IDs midway through a
signal callback.

Sibling ordering is owned by `tc_entity_pool`: roots and child arrays retain
stable order, `Entity.sibling_index` moves an entity within its current sibling
set, and `sibling_order_changed` is published through the scene structure
event. Scene serialization walks ordered roots and ordered children, so native
before/after drops survive save/load; `ReparentEntityCommand` restores both the
parent and prior index on undo. The legacy scene-tree frontend remains only
while tcgui is an explicit compatibility entrypoint during staged retirement.
Its controller is now a thin `SceneHierarchyController` projection and no longer
owns a second `EntityOperations` or hierarchy policy implementation.
