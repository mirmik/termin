# termin-app native re-export cleanup plan

Дата: 2026-06-23

Статус: план поэтапной миграции после удаления `entity_lib`.

## Цель

`termin-app` должен быть владельцем editor/player/tool composition, но не
каноничным владельцем доменных Python/C++ API.

Внешние SDK-пакеты не должны зависеть от `termin._native` или C++ headers из
`termin-app`, если нужный API уже принадлежит доменному модулю (`termin-scene`,
`termin-materials`, `termin-render-passes`, `termin-inspect`, `tcbase`, etc.).

## Текущее состояние

После удаления `entity_lib` в `termin-app` остаются:

- `libtermin_core.so`: маленький C init/util ABI (`tc_init`, `tc_shutdown`,
  version/uuid/runtime-id), но с широким public link surface.
- `termin._native`: app-level Python compatibility/glue module.
- CLI/runtime/editor executables: `termin`, `termin_builder`, `termin_runner`,
  `termin_stdlib`, `termin_player`, `termin_editor`, `termin_launcher`.

`termin._native` сейчас смешивает:

- compatibility re-export'ы scene/entity/input/render/material/inspect/kind API;
- app/editor-specific native bindings;
- scene render extension helpers;
- asset handle bindings;
- picking/render utility wrappers.

## Boundary Rules

- Новый код не должен импортировать `termin._native.*`, если есть canonical
  package path.
- Сначала переписываем внутренних пользователей на canonical imports, потом
  удаляем compatibility re-export из `termin._native`.
- Не добавлять новые fallback wrappers в `termin._native`.
- `termin-base` должен получать только generic utilities. Render settings,
  scene render extensions, material handles, asset handles и editor interaction
  не являются base API.

## Mechanical Migration Batches

### Batch 1: `termin._native.render` imports

Status: done, 2026-06-23.

Goal: убрать прямые зависимости доменных пакетов от app-level render submodule.

Known users:

- `termin-navmesh/python/termin/navmesh/material_component.py`
- `termin-default-assets/python/termin/default_assets/render/glsl_asset.py`
- `termin-render/python/termin/render/texture_handle.py`
- `termin-scene/cpp/bindings/component_registry_python.cpp`
- examples/tests that still import `termin._native.render`

Canonical owners:

- material/shader parser/preprocessor API -> `termin.materials`
- frame graph/render framework API -> `termin.render_framework`
- concrete passes and picking helpers -> `termin.render_passes`
- draw call types -> `termin.render`
- render components -> `termin.render_components`
- skeleton binding re-export -> `termin.skeleton`

Work:

1. Replace Python imports from `termin._native.render` with canonical packages.
2. Replace C++ binding imports in non-app modules with canonical native modules.
3. Add focused import tests where a domain package previously required
   `termin._native`.
4. After all users are migrated, remove corresponding re-export assignments from
   `termin-app/cpp/termin/bindings/render/render_module.cpp`.

Verification:

- `./run-tests.sh`: passed, 585 Python tests passed, 1 skipped; C/C++ tests
  and editor smoke tests passed.
- import smoke for affected packages: passed for
  `termin.navmesh`, `termin.default_assets`, `termin.render`,
  `termin.scene`
- `rg "termin\\._native\\.render|_native\\.render"` outside build/sdk/docs:
  no matches.

### Batch 2: inspect/kind compatibility imports

Status: done, 2026-06-23.

Goal: internal code stops depending on `termin._native.inspect` and
`termin._native.kind`.

Canonical owners:

- inspect registry/types -> `termin.inspect`
- low-level inspect binding, if absolutely needed -> `termin.inspect._inspect_native`
- kind registry wrapper -> `termin.inspect.kind`
- legacy app/domain builtin registration -> `termin.serialization.kind`, now a
  thin wrapper over `termin.inspect.kind`.

Work:

1. Replace app/editor imports of `termin._native.inspect`.
2. Replace `termin_modules` ownership recording import of
   `termin._native.kind` with the canonical kind owner.
3. Keep singleton topology tests, but point them at canonical modules.
4. Remove `termin._native.inspect/kind` re-export once no internal users remain.

Verification:

- inspect singleton topology test: passed.
- component/frame-pass registry tests: covered by focused tcgui/widget tests and
  full `./run-tests.sh`.
- `./run-tests.sh`: passed, 585 Python tests passed, 1 skipped; C/C++ tests
  and editor smoke tests passed.
- `rg "termin\\._native\\.(inspect|kind)|_native\\.(inspect|kind)"`
  outside build/sdk/docs: no matches.

### Batch 3: `termin.graphics` facade

Status: done, 2026-06-23.

Goal: remove app-owned graphics facade from non-app code.

Canonical owners:

- `Color4`, `RenderState` -> `tgfx`
- `RenderSyncMode`, `get_render_sync_mode`, `set_render_sync_mode` ->
  `termin.render`.

Work:

1. Replace `from termin.graphics import Color4/RenderState` with `tgfx`.
2. Keep render sync mode under `termin.project.settings` for now. It is a
   project/app settings API, not a graphics facade API; moving the underlying C
   binding out of `_native` is done: runtime sync binding now belongs to
   `termin.render`.
3. Remove `termin-app/termin/graphics` after downstream users are gone: done.
4. Move render sync runtime binding from root `termin._native` to
   `termin.render`.

Verification:

- `rg "termin\\.graphics|from termin\\.graphics"` outside build/sdk/docs:
  no matches.
- stale package check in source/sdk/venv: no `termin/graphics` paths.
- render sync owner test: `termin.render` exposes `RenderSyncMode`,
  `get_render_sync_mode`, and `set_render_sync_mode`; root `termin._native`
  does not.
- `./run-tests.sh`: passed, 596 Python tests passed, 1 skipped; C/C++ tests
  and editor smoke tests passed.

### Batch 4: picking helpers

Status: done, 2026-06-23.

Goal: picking utility imports use `termin.render_passes`, not `termin._native`.

Canonical owner:

- `termin.render_passes`

Work:

1. Replace `tc_picking_*` imports/calls from `termin._native`.
2. Remove wrappers from `termin-app/cpp/termin/bindings.cpp`.

Verification:

- picking helper smoke: `termin.render_passes.tc_picking_*` roundtrips pick id
  12345, while `termin._native` no longer exposes these names.
- focused pytest: `termin-render-passes/tests` and
  `termin-app/tests/test_tcgui_framegraph_debugger_handle.py` passed.
- `./build-sdk.sh --no-wheels`: passed.
- `./setup-test-venv.sh --force`: passed.
- `./run-tests.sh`: passed, 585 Python tests passed, 1 skipped; C/C++ tests
  and editor smoke tests passed.
- `rg "termin\\._native.*tc_picking|_native\\.tc_picking|from termin\\._native import .*tc_picking|m\\.def\\(\"tc_picking"`
  outside build/sdk/docs: no legacy app `_native` exports/imports remain.
  Remaining `tc_picking.h` users are canonical render-passes code and app C++
  editor interaction using the C API directly.

### Batch 5: scene/entity compatibility re-export

Status: done, 2026-06-23.

Goal: `termin._native` no longer acts as the public scene/entity module.

Canonical owners:

- scene/entity/component API -> `termin.scene`
- input events -> `termin.input` or the display/input canonical owner selected
  by current package boundaries
- `OrbitCameraController` -> `termin.render_components`

Work:

1. Replace internal imports of scene/entity symbols from `termin._native`.
2. Move remaining tests/examples to `termin.scene` and domain packages.
3. Remove re-export assignments from
   `termin-app/cpp/termin/bindings/entity/entity_native_to_native.cpp`.

Verification:

- scene/entity root re-export smoke: canonical imports from `termin.scene`,
  `termin.input`, and `termin.render_components` work; `termin._native` no
  longer exposes root aliases for `TcScene`, `Entity`, `Component`,
  `TcComponentRef`, input event classes, or `OrbitCameraController`.
- focused pytest: scene/editor/component registry coverage passed.
- `./build-sdk.sh --no-wheels`: passed.
- `./setup-test-venv.sh --force`: passed.
- `./run-tests.sh`: passed, 585 Python tests passed, 1 skipped; C/C++ tests
  and editor smoke tests passed.
- `rg` for removed root aliases outside build/sdk/docs: no matches.
  Remaining `termin._native` users are app-owned/editor-specific surfaces:
  scene render extensions, project render sync settings, editor submodule,
  inspect singleton smoke, and skeleton callback hook.

## Non-mechanical / Needs Design

### Scene render extensions

Status: done, 2026-06-23.

Canonical ownership split now starts outside app:

- `termin.render` owns `SceneRenderState`, `SceneRenderMount`,
  `scene_render_state`, `scene_render_mount` and render extension type names.
- `termin.engine` owns default scene extension registration and scene creation
  helpers because that layer composes render, collision and scene lifecycle.
- `termin.engine` also owns render-enabled `deserialize_scene`/`destroy_scene`:
  deserialize creates a default render scene and applies the render legacy
  adapter before `TcSceneRef::load_from_data`; destroy notifies components,
  clears render pipelines, then destroys the core scene.
- `termin.render` also owns `TcSceneLighting`, because
  `SceneRenderState.lighting()` returns the scene lighting handle and no longer
  reaches through app-native lighting bindings.
- `termin-app/termin/scene_rendering.py` remains a transitional facade for
  app/editor compatibility.

App-native cleanup:

- `termin-app/cpp/termin/tc_scene_bindings.cpp` removed from `_native` and
  deleted.
- `termin-app/cpp/termin/tc_scene_lighting_bindings.cpp` removed from
  `_native` and deleted.
- `termin-app/cpp/termin/scene_bindings.hpp` deleted.
- root `termin._native` no longer exports scene render extension symbols or
  render-enabled scene lifecycle helpers.

Verification:

- app-native scene render smoke: removed names are absent from `termin._native`;
  `termin.engine.deserialize_scene` creates render-enabled scenes; migrated
  legacy lighting returns `termin.render.TcSceneLighting`.
- focused pytest: `termin-app/tests/test_scene_rendering_lifecycle.py`,
  `termin-app/tests/test_headless_runtime.py`,
  `termin-app/tests/editor_commands_test.py`,
  `termin-app/tests/test_game_mode_model.py`, and
  `termin-app/tests/test_rendering_model_render_target_restore.py` passed.
- `./build-sdk.sh --no-wheels`: passed.
- `./setup-test-venv.sh --force`: passed.

### TextureHandle

The app-native `TextureHandle` wrapper was removed. Runtime texture APIs now
traffic in `tgfx.TcTexture`, backed by the C `tc_texture` pool. The remaining
`termin.render.texture_handle` module is a compatibility home for default white
and normal texture helpers only; it no longer exports a `TextureHandle` class.

`termin-default-assets` owns the asset lookup integration:

- lazy texture registration declares pool entries with `tc_texture_declare`;
- `ResourceManager.get_texture_handle()` returns `TcTexture`;
- the legacy selector kind name `texture_handle` remains as a UI/serialization
  alias while internal data uses `TcTexture`.

### Editor native bindings

`termin._native.editor` should become editor-private or a dedicated editor
native module. It should not be presented as a general SDK native surface.

### `termin.log`

The exception-formatting wrapper around `tcbase.log` is generic enough to move
to `tcbase` eventually, but it should be handled separately from native binding
ownership.

## Current Smells To Track

- `termin-app/core_c/src/tc_scene_registry.c` is not built; the public header is
  already a legacy inline delegate to `tc_scene_pool`.
- The old `termin._native` target and compatibility re-export surface were
  removed on 2026-06-24. Component base inspect metadata now belongs to
  `termin-scene` and is registered through explicit bootstrap init.
- C++ binding modules in non-app packages still import app native submodules for
  type lookup in a few places.

## First Working Step

Start with Batch 1. It has the best ratio of mechanical import changes to
architecture cleanup:

1. Rewrite `termin._native.render` users to canonical modules.
2. Run focused import tests for affected packages.
3. Run `./run-tests.sh`.
4. Only then remove migrated re-export entries from `render_module.cpp`.
