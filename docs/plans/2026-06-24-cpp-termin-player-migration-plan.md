# C++ termin_player migration plan

Date: 2026-06-24
Status: completed

## Goal

Move the packaged desktop player runtime from Python-owned lifecycle to a native
C++ host. The C++ `termin_player` executable should own engine, scene, window,
display, render, input and shutdown order. Python should remain available for
project scripting, component registration and explicit bootstrap hooks, but it
must not be the owner of the player runtime resources.

## Why

After the `InspectRegistryPythonExt` reference-counting fix, `termin build dev`
for `termin-chess` exits cleanly. The runtime path is still noisy:

- `termin run dev` exits with signal 139 during shutdown.
- The shutdown report still includes nanobind leaks: scene/entity wrappers,
  materials, render state, texture handles, vector/pose wrappers, profiler
  objects, leaked types and leaked functions.
- The current packaged player creates `EngineCore` in C++, initializes Python,
  delegates the whole runtime to `termin.player.__main__.main()`, then calls
  `Py_FinalizeEx()` while native engine resources are still alive.
- Python `PlayerRuntime` owns wrappers and callbacks for resources whose real
  lifetime is native: scene, rendering manager attachments, display, surface,
  window, input, resource managers and project module state.

This shape makes shutdown order hard to reason about. It also makes nanobind
leak reports ambiguous because Python module globals, Python-owned callbacks and
native scene lifetime all collapse at interpreter finalization.

## Current State

Final state as of 2026-06-24:

- `termin_player` now enters through `termin::player::PlayerRuntimeHost`.
- The host parses `app.json`, initializes embedded Python for project modules,
  calls `termin::runtime::RuntimePackageLoader`, registers the loaded scene in
  `SceneManager`, creates the native SDL/offscreen display path, attaches
  rendering through `RenderingManager`, runs the frame loop in C++, and owns the
  shutdown order.
- Packaged `termin-chess` smoke passes with
  `./Chess --exit-after-frames 3`: exit code 0, no nanobind leak report, no
  signal 139, and no missing component/pass registry warnings.
- `termin build dev` in `termin-chess` exits cleanly without nanobind leak
  reports.
- Desktop `UIWidgetPass` has a native pass implementation in
  `termin-render-passes`, so the default runtime pipeline no longer depends on a
  Python-authored frame pass.
- Python `PlayerRuntime` is no longer created by the packaged desktop player
  path; a small facade remains for script-facing `request_quit()`.
- `termin-components-voxels` no longer installs modules into the core
  `termin.voxels` namespace. The component package now lives under
  `termin_voxel_components`, and both `termin.voxels` and
  `termin_voxel_components` expose component classes lazily so simple imports do
  not create native render/material resources.

Historical state before this migration:

Native player entrypoint:

- `termin-app/cpp/app/termin_player.cpp` resolves the bundle paths and embedded
  Python paths.
- It creates `termin::EngineCore engine`.
- It starts the Python interpreter.
- It runs:

```python
from termin.player.__main__ import main
main()
```

- It calls `Py_FinalizeEx()`.
- `EngineCore` is destroyed after Python finalization because it is a stack
  object in `main()`.

Python player runtime:

- `termin-app/termin/player/runtime.py` owns `PlayerRuntime`.
- `PlayerRuntime.initialize()` performs bootstrap, component registration,
  module loading, manifest/resource loading, scene deserialization, display
  creation, render attach, input setup and optional MCP setup.
- `PlayerRuntime.run()` owns the frame loop.
- `PlayerRuntime.shutdown()` tries to detach scene rendering and clear Python
  references.

Existing useful native foundation:

- `termin-runtime/include/termin/runtime/runtime_package.hpp`
- `termin-runtime/src/runtime_package.cpp`

The C++ `RuntimePackageLoader` already knows how to load packaged runtime
resources and return a `TcSceneRef`. The C++ migration should build on this
instead of porting the Python package loader mechanically.

## Target Ownership

The packaged player should have a native host with this high-level flow:

1. Resolve app bundle, `app.json`, package root and package manifest.
2. Create `EngineCore` and native player services.
3. Run player bootstrap through C++ APIs, with Python hooks only where needed.
4. Load the runtime package through `termin::runtime::RuntimePackageLoader`.
5. Create the native window, surface/display and render targets.
6. Attach the loaded scene to `RenderingManager`.
7. Initialize embedded Python only for project modules and script execution.
8. Run the frame loop in C++.
9. Shut down in deterministic native order.

Python remains responsible for:

- project module imports,
- Python component classes,
- Python script callbacks,
- explicit player-facing APIs such as `request_quit()`,
- optional development services such as MCP, if kept for player.

Python should not own:

- `EngineCore`,
- `TcSceneRef` lifetime,
- display/window/surface lifetime,
- render pipeline attachment lifetime,
- runtime package resource ownership,
- shutdown ordering.

## Non-goals

- Do not rewrite the editor runtime in this migration.
- Do not remove Python components or Python gameplay scripting.
- Do not port editor-only debug and inspection flows into the packaged player.
- Do not keep broad legacy fallbacks for old package formats unless a current
  project still depends on them.
- Do not treat the old Python `PlayerRuntime` as the long-term runtime owner.

## Phase 0: Baseline And Gates

Record the current behavior before moving code:

- `termin build dev` in `termin-chess` must stay clean.
- `timeout 30 termin run dev` in `termin-chess` is the runtime regression gate.
- Capture the current leak signature and exit code in task context.

Keep a temporary escape hatch while the migration is active:

- Either an environment switch such as `TERMIN_PLAYER_IMPL=python`, or
- a separate internal command path for the old Python player.

Acceptance:

- The failing runtime behavior is reproducible.
- The build path remains clean.
- The old player can be invoked only as a temporary diagnostic path.

## Phase 1: Native Bundle And Package Load

Introduce a native player package startup path:

- Parse `app.json`.
- Locate the package directory and `manifest.json`.
- Link `termin_player` against `termin_runtime::termin_runtime`.
- Call `termin::runtime::RuntimePackageLoader::load(package_root)`.
- Surface loader diagnostics through normal logging.

Implementation notes:

- Keep this layer independent from SDL/window creation.
- Prefer small C++ structs for app/package manifests instead of ad hoc JSON
  lookup spread through `main()`.
- Fail loudly on missing manifest fields during active migration.

Acceptance:

- A packaged `termin-chess` bundle can be loaded to a valid `TcSceneRef` from
  the C++ player path.
- No Python `PlayerRuntime` object is created for package loading.

## Phase 2: Native Window, Display And Render Attach

Move visible player runtime ownership to C++:

- Create the desktop window through the native backend path used by the current
  player.
- Create the surface/display/render target objects in C++.
- Configure the default render pipeline from package or bootstrap state.
- Attach the loaded scene to `RenderingManager`.
- Render at least one frame from the native path.

Acceptance:

- `termin run dev` opens the packaged project and renders through the C++
  player host.
- Python still does not own scene/window/display resources.

## Phase 3: Native Frame Loop, Input And Shutdown

Move the player loop out of `PlayerRuntime._tick()`:

- Poll window events in C++.
- Route viewport/input events through native input APIs.
- Update scene/runtime state.
- Render and present.
- Honor quit requests from both native input and Python script facade.

Define shutdown order explicitly:

1. Stop optional MCP/development services.
2. Stop Python script callbacks and module-owned runtime hooks.
3. Detach the scene from `RenderingManager`.
4. Destroy display, surface and window objects.
5. Release runtime package resources and scene references.
6. Unregister Python component/pass/kind/inspect records owned by this player
   session.
7. Destroy `EngineCore`.
8. Finalize Python only if no remaining native destructors can touch Python.
   Otherwise follow the editor model and intentionally let process teardown
   reclaim the embedded interpreter.

Acceptance:

- A packaged smoke run using `./Chess --exit-after-frames 3` exits with status 0.
- No nanobind leak report is printed on normal player shutdown.
- Shutdown logs show the expected owner order.

## Phase 4: Python Scripting Bridge

Reintroduce only the Python pieces that the game actually needs:

- Initialize embedded Python from the C++ player host.
- Import project modules from the package manifest.
- Register Python component classes under an explicit player session owner.
- Execute Python script callbacks without exposing ownership of native scene
  resources to Python.
- Provide a small Python facade for `termin.player` APIs that game scripts may
  already call, for example `request_quit()` and active-runtime lookup.

Important cleanup work:

- Builtin and project Python registrations need explicit unregister paths.
- Python frame-pass registration currently needs the same ownership audit as
  component registration if it is used in player.
- Direct `import termin.inspect` preload behavior is tracked separately as
  Kanboard task #123 and should be fixed before relying on import smoke tests.

Acceptance:

- `termin-chess` project modules load in the C++ player.
- Gameplay scripts run.
- Player shutdown unregisters session-owned Python records.
- Leak checks remain clean after Python module import and script execution.

## Phase 5: Retire Python PlayerRuntime From Packaged Run Path

Once the native host owns the runtime:

- Keep `termin.player.__main__` only as a compatibility path; the packaged
  desktop executable should enter through `PlayerRuntimeHost`.
- Remove duplicated Python package loading logic that is covered by
  `RuntimePackageLoader`.
- Keep Python APIs only where scripts import them directly.
- Update `termin-app/docs/termin-cli.md` and any bundle/runtime docs.
- Add migration notes for removed Python player internals.

Acceptance:

- `termin run PROFILE` uses the native C++ player path by default.
- The old Python `PlayerRuntime` is not used for packaged desktop runtime.
- Documentation describes the native player ownership model.

## Proposed C++ Structure

Create a small player subsystem instead of growing `app/termin_player.cpp`:

- `termin::player::PlayerAppManifest`
- `termin::player::PlayerPackageManifest`
- `termin::player::PlayerRuntimeHost`
- `termin::player::PlayerPythonSession`
- `termin::player::PlayerWindowHost`

`app/termin_player.cpp` should become a thin entrypoint:

```cpp
int main(int argc, char** argv) {
    termin::player::PlayerRuntimeHost host;
    return host.run(argc, argv);
}
```

The host should own objects in the same order in which shutdown must happen.
That keeps the destructor order visible in the class layout and avoids relying
on scattered cleanup code in Python `finally` blocks.

## RuntimePackageLoader Gaps To Audit

Before replacing Python loading completely, compare native and Python loaders
for these resource types:

- shader programs,
- materials and render states,
- meshes,
- textures,
- foliage,
- scene pipeline templates,
- project module manifests,
- asset aliases and package-relative paths,
- fallback scene behavior.

The migration should close real gaps in `termin-runtime`, not reintroduce a
second player-specific resource loader.

## Risks

- Python scripts may rely on `termin.player.runtime.active_runtime()`.
- MCP support may currently assume a Python `PlayerRuntime` instance.
- Some resource kinds may still be loaded only by the Python path.
- Cleaning nanobind leaks may expose a deeper native lifetime bug rather than
  fully solving shutdown on the first pass.
- Calling `Py_FinalizeEx()` too early can reproduce the same class of crash seen
  in the old player path.

## Verification

Final verification completed on 2026-06-24:

- `./build-sdk.sh --no-wheels`: passed, including SDK verification.
- `./setup-test-venv.sh --force`: passed after the final SDK build.
- `./run-tests.sh`: passed.
  - C/C++: 28/28 tests passed.
  - Python: 614 passed, 1 skipped.
  - Editor smoke: Python module hot reload PASS, C++ module cascade hot reload
    PASS.
- `.venv/bin/python -m pytest termin-voxels/tests -q`: 45 passed.
- Import leak sanity:
  - `import termin_voxel_components`: no nanobind leak report.
  - `import termin.voxels; from termin.voxels import TcVoxelGrid`: no nanobind
    leak report.
- `/home/mirmik/project/termin-chess`: `termin build dev` passed without
  nanobind leak reports.
- `/home/mirmik/project/termin-chess/dist/Chess/Chess --exit-after-frames 3`:
  passed with exit code 0, no nanobind leak report, no shutdown signal 139.

Build and Python test environment:

```bash
./build-sdk.sh --no-wheels
./setup-test-venv.sh --force
```

Package smoke:

```bash
cd /home/mirmik/project/termin-chess
termin build dev
```

Runtime smoke:

```bash
cd /home/mirmik/project/termin-chess/dist/Chess
./Chess --exit-after-frames 3
```

Expected final gate:

- build exits cleanly,
- packaged runtime smoke exits with status 0,
- no `nanobind: leaked ...` report appears,
- no signal 139 at shutdown.
