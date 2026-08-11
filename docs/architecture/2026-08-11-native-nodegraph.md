# Native nodegraph architecture

Status: accepted migration design.

## Context

`termin-nodegraph` is currently a Python package containing four concerns:

- mutable authoring data (`Graph`, `Node`, `Socket`, `Edge`, `Group`);
- graph mutation and connection validation;
- generic graph JSON serialization;
- a `termin-gui-native`/`termin-visual-scene` projection with editing interaction.

The pipeline editor is its production consumer. C# cannot reuse this implementation
without hosting Python, and the public mutable dataclasses let consumers bypass graph
invariants. The target is one native implementation shared by C++, Python and C#.
Nodegraph remains an authoring subsystem; graph execution and domain compilation stay
in their owning modules such as `termin-render`.

## Target modules

### `termin_nodegraph_core`

A headless C++ shared library depending only on public foundation APIs, initially
`termin-base` for logging, binding handles and `tc_value`.

It owns:

- graph, node, socket, edge and visual-group storage;
- stable persisted string IDs and generation-checked runtime handles;
- all structural mutations and revisions;
- connection cardinality and validator dispatch;
- owned `tc_value` parameter and metadata trees;
- generic nodegraph serialization and strict deserialization.

It does not own rendering, widgets, pipeline semantics, graph execution or WPF.

### `termin_nodegraph_ui`

A C++ shared library depending on `termin_nodegraph_core`,
`termin-visual-scene` and `termin-gui-native`.

It owns:

- the retained `TcVisualScene` projection;
- node/group/edge geometry and semantic hit testing;
- selection, dragging, connection gestures and deletion;
- native parameter editors embedded through `SceneView` widget portals;
- graph-revision synchronization and presentation callbacks.

The view is created inside a caller-owned `tc_ui_document` and returns a native root
widget handle. C# embeds the complete native document/view; individual parameter
editors are not WPF controls.

## Data and ownership contract

- A graph is an explicit owner. Destroying it invalidates all node, edge and group
  handles issued by it.
- Runtime handles are generation checked. Persisted identity remains a non-empty,
  graph-unique UTF-8 string.
- Sockets have unique names within one node direction and are addressed by node
  handle plus direction/name. They do not need independent pooled handles initially.
- Parameters and extension metadata use deeply owned `tc_value` trees. Borrowed
  pointers never survive a call.
- Reads use copied snapshots or size-query/copy functions across C ABI. Internal C++
  pointers never cross the ABI.
- Graphs are thread-confined. The owning UI/application thread performs mutations;
  the implementation does not use `thread_local` state.

## Mutation contract

The native controller is the only mutation path. It provides focused operations and
transactional descriptor-based node creation/configuration. Direct mutation of node
containers is not reproduced in new bindings.

Every successful logical mutation increments a graph revision exactly once and emits
one change record after invariants hold. Failed operations log a diagnostic, return a
structured error and leave the graph unchanged.

Core invariants are:

- edges reference existing, distinct nodes and existing output/input sockets;
- socket names are non-empty and unique within their direction;
- IDs are non-empty and unique within their entity kind;
- a non-multi endpoint has at most one edge;
- reconnecting a non-multi endpoint atomically replaces affected edges;
- the configured type validator accepts every connection.

Cycles are not a core error. DAG policy belongs to domains that require it.

Validators are synchronous C-compatible callbacks with explicit userdata/lifetime.
They may inspect the proposed endpoints but may not mutate the graph recursively.
Built-in exact/`any` validation is the default. The render pipeline adapter continues
to delegate assignability to the canonical renderer socket contract.

## ABI and bindings

The C ABI is the language-neutral source of truth and follows existing Termin handle
conventions. Its surface is grouped around:

- graph create/destroy/validity/revision;
- descriptor-based node/group creation;
- explicit socket, parameter, metadata and position mutation;
- connect/remove operations returning error codes and copied diagnostics;
- snapshot enumeration and generic serialization;
- native view create/destroy/root-widget and change callbacks.

C++ provides RAII/facade types above the same ownership model. Python nanobind and the
C# `Termin.Native` facade are thin adapters. They do not implement independent graph
rules.

Python compatibility is behavioral rather than structural: existing imports may be
preserved during migration, but publicly mutable dataclass containers are replaced by
snapshots and controller methods. Repository consumers must migrate in the same series.
No permanent fallback to the Python model remains.

## Presentation policy

The generic native view must not hard-code render-pipeline node kinds or socket types.
Colors, labels, parameter editor specifications and optional node roles are supplied
as presentation metadata/descriptors. The current `fbo`, texture and shadow palette is
moved into the pipeline editor adapter or an explicit reusable theme.

Full rebuild remains permitted for initial parity, but the graph revision contract must
allow later incremental synchronization. Node dragging and edge geometry should update
incrementally from the beginning.

## WPF integration

The nodegraph does not create WPF portals. A generic Termin WPF document host renders a
borrowed `tc_ui_document` through the D3D11 presentation path and forwards pointer,
wheel, keyboard, text-input, cursor and clipboard services. The same native nodegraph
widget can therefore run in the editor and in a C# WPF shell.

This host is reusable infrastructure and is kept separate from nodegraph bindings.

## Migration order

1. Add native core storage, handles, mutations and contract tests.
2. Add `tc_value` snapshots/serialization and the stable C ABI.
3. Bind the core to Python and migrate generic nodegraph tests.
4. Port retained scene projection and interaction to C++.
5. Add native parameter widgets and remove pipeline-specific presentation from the
   generic view.
6. Migrate the Python pipeline editor and examples to the native implementation.
7. Add C# facade and generic WPF native-document host.
8. Add a Windows interactive nodegraph smoke.
9. Remove the Python implementation and obsolete packaging paths.

During the migration there is one authoritative implementation per concern. New native
tests precede consumer cutover; old Python code is deleted immediately after its final
consumer moves.

## Completion criteria

- C++, Python and C# exercise the same native graph/controller implementation.
- The pipeline editor has parity for load/save, typed connections, parameters, groups
  and interactive editing.
- A WPF sample hosts the complete native nodegraph without per-parameter WPF portals.
- Linux SDK build and central tests pass; the D3D11 C# SDK and Windows interactive smoke
  pass.
- The old Python model/controller/io/native-view implementation and its GUI dependency
  declaration are removed.
