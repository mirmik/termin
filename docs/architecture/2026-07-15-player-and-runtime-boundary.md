# Player Host and Embeddable Runtime Boundary

## Decision

`termin-player` and `termin-runtime` have similar names because both participate
in project execution, but they are different architectural layers:

- **`termin-player` is a host application and command-line development tool.**
  It runs a Termin project outside the editor and should behave approximately
  like entering Play Mode in the editor.
- **`termin-runtime` is an embeddable native library.** It loads and runs the
  already-built runtime representation of a project inside another host
  application.

The short mnemonic is:

```text
player  = a program that runs a project
runtime = a library used to embed a built project
```

This document is the canonical current boundary. Historical extraction and
build plans explain how the repository reached it but do not redefine it.

## `termin-player`: editor-adjacent project host

`termin-player` owns the `termin_player` executable, `python -m termin.player`
and related source/headless/automation entrypoints. Its primary use is running
a project from the command line without opening the editor UI.

The player is allowed the same broad execution capabilities as editor Play
Mode, including:

- embedded Python and Python project modules;
- source-project discovery and `.terminproj` settings;
- source asset adapters and development-time asset loading;
- native and Python component factories;
- module discovery, loading and development hot reload;
- windowed, offscreen and headless execution;
- input, rendering, audio and normal scene lifecycle;
- MCP, screenshots, diagnostics and deterministic test controls;
- loading a built runtime package when that is the requested run mode.

Python is not an accidental dependency of the player. The player is an
editor-adjacent SDK tool, so linking and packaging Python is allowed.

### Play Mode parity

For the same project and run configuration, editor Play Mode and
`termin_player` should agree on:

- project settings and entry scene selection;
- module and component discovery;
- asset identity and resource resolution;
- scene construction and component lifecycle;
- update, fixed-update, render and shutdown ordering;
- input semantics and runtime error reporting.

The player does not reproduce editor UI state, selection, undo history,
inspector behavior or authoring overlays. It owns a process/window/CLI boundary
instead. Headless and automation modes may replace display/input services
explicitly, but they should not invent a second project runtime model.

Parity must come from shared neutral composition code and engine services. It
must not come from `termin-player` importing editor-private implementations.
If Play Mode behavior currently exists only inside `termin-app`, reusable
behavior is extracted into an appropriate neutral module and consumed by both.

## `termin-runtime`: embeddable native project runtime

`termin-runtime` is a C/C++ library for hosts that already own their
application shell. Its primary input is a validated runtime package produced by
the project build pipeline, not a source project checkout.

Typical consumers include:

- a desktop application embedding a Termin scene;
- an Android activity;
- an OpenXR application;
- a game-specific native executable;
- `termin_player` when it is asked to run a built package;
- focused native tests and tools.

`termin-runtime` owns domain-level packaged execution facilities such as:

- runtime-package manifest and resource loading;
- construction of runtime scenes and native resources;
- resource keepalive for loaded package data;
- target-independent runtime bootstrap required by package loading;
- stable native APIs needed by platform/application hosts.

It does not own:

- command-line parsing or a process entrypoint;
- window, event-loop or platform application lifecycle;
- source-project discovery, file watching or build orchestration;
- editor UI, selection, undo/redo, inspectors or authoring state;
- MCP and editor automation policy;
- Python module discovery or a required Python interpreter;
- source asset import plugins or assumptions about a repository checkout.

Bindings may expose `termin-runtime` APIs to Python or other languages, but the
library implementation and its required dependency graph remain native. A host
may add language-specific component factories above this boundary.

## Dependency direction

The intended dependency graph is:

```text
termin-app (editor) -----> shared Play Mode/project services
        |                              |
        v                              v
termin-player -----------------> termin-runtime
        |                              |
        v                              v
 host/tool policy             engine/scene/render/runtime assets

custom desktop / Android / OpenXR host -> termin-runtime
```

Allowed:

```text
termin-app     -> termin-player
termin-player  -> termin-runtime
termin-player  -> Python/modules/MCP/source asset tooling
custom host    -> termin-runtime
bindings       -> termin-runtime
```

Forbidden:

```text
termin-runtime -> termin-player
termin-runtime -> termin-app or editor modules
termin-runtime -> Python/nanobind as a required implementation dependency
termin-runtime -> source-project watchers/import/build tooling
termin-player  -> termin-app private modules
```

`termin-app -> termin-player` means the editor may invoke or compose the player
tool. It does not permit the reverse dependency. Capabilities shared by editor
Play Mode and the player belong below both consumers, not in either private
package.

## Scenario matrix

| Scenario | Entry layer | Input | Python allowed | Editor dependencies |
| --- | --- | --- | --- | --- |
| Editor Play Mode | `termin-app` | source project | yes | yes |
| Command-line project run | `termin-player` | source project | yes | no editor-private imports |
| Player package run | `termin-player` | runtime package | yes | no editor-private imports |
| Embedded desktop/game host | host + `termin-runtime` | runtime package | host choice | forbidden in runtime |
| Android/OpenXR host | platform host + `termin-runtime` | runtime package | host choice | forbidden in runtime |
| Native runtime test | `termin-runtime` | fixture package | not required | forbidden |

“Python allowed” describes host policy. It does not move canonical engine or
asset behavior out of native runtime libraries. Conversely, a custom host may
embed Python above `termin-runtime` without changing the library boundary.

## Runtime package ownership

A runtime package is a build artifact and a contract of `termin-runtime`.
`termin-player` may consume it, but the player must not define a competing
package schema or canonical loader.

Python-side player loaders can be development adapters or bindings around the
native loader. Format validation, native resource construction and scene
loading required by embedded hosts belong to `termin-runtime` and domain
runtime libraries.

Source project handling is the opposite: `.terminproj` discovery, development
module loading, source asset watching and editor-like run policy belong to the
player/shared project-tooling side, not `termin-runtime`.

## Review questions

When adding execution-related code, use these questions:

1. Is this a reusable operation needed by an embedded built project? Put it in
   `termin-runtime` or a lower native domain library.
2. Is this process, CLI, window, source-project, Python, hot-reload or
   automation policy? Put it in `termin-player` or shared development tooling.
3. Is it needed equally by editor Play Mode and the command-line player?
   Extract a neutral service consumed by both; do not create an editor import.
4. Does a runtime library require a Python/editor object to perform the
   operation? The boundary is wrong; move policy upward or introduce a native
   domain API.
5. Does the player duplicate a native runtime-package implementation? Keep one
   canonical native implementation and expose it through bindings/adapters.

## Verification gates

- `termin-runtime` configures, builds and runs focused package-loader tests
  without Python or editor targets.
- dependency tests reject imports/links from `termin-runtime` to player,
  editor, Python or source-tooling implementations.
- player tests compare source-project startup and lifecycle behavior with the
  shared services used by editor Play Mode.
- runtime-package fixtures are accepted consistently by native embedded hosts
  and by `termin_player` package mode.
- adding Python support to a host does not change the serialized runtime
  package contract or introduce a second loader.

