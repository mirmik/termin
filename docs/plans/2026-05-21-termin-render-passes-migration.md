# termin-render-passes migration

Дата: 2026-05-21

Статус: план миграции. Не считать текущее состояние кода соответствующим этому документу, пока пункты не отмечены как выполненные в рабочей документации или changelog.

## Цель

Вынести concrete render passes из `termin-app` в отдельный SDK-модуль `termin-render-passes`.

`termin-app` должен остаться потребителем pass API, а не владельцем стандартного рендера. Android, standalone runtime и editor должны линковаться с `termin-render-passes`, а не компилировать `.cpp` из `termin-app/cpp/termin/render`.

## Текущая проблема

Concrete passes сейчас живут в app-слое:

- `termin-app/cpp/termin/render/color_pass.*`
- `termin-app/cpp/termin/render/id_pass.*`
- `termin-app/cpp/termin/render/shadow_pass.*`
- `termin-app/cpp/termin/render/present_pass.*`
- `termin-app/cpp/termin/render/bloom_pass.*`
- `termin-app/cpp/termin/render/grayscale_pass.*`
- `termin-app/cpp/termin/render/tonemap_pass.*`
- `termin-app/cpp/termin/render/skybox_pass.*`
- `termin-app/cpp/termin/render/debug_triangle_pass.*`
- `termin-app/cpp/termin/render/ground_grid_pass.*`
- `termin-app/cpp/termin/render/collider_gizmo_pass.*`
- `termin-app/cpp/termin/render/immediate_renderer.*`
- `termin-app/cpp/termin/render/material_ubo_apply.*`
- `termin-app/cpp/termin/render/shadow_camera.*`
- `termin-app/cpp/termin/render/shader_skinning.*`

`termin-android/CMakeLists.txt` напрямую компилирует часть этих файлов из `../termin-app/cpp/termin/render`. Это делает Android-запуск зависимым от app source tree и закрепляет неправильное направление зависимости.

Python bindings для этих пассов тоже находятся в app-слое:

- `termin-app/cpp/termin/bindings/render/frame_pass.cpp`
- Python re-export modules under `termin-app/termin/visualization/render/framegraph/passes/`

## Целевая форма

```text
termin-render
  frame graph, render engine, pass interfaces, render resources

termin-render-passes
  concrete pass implementations over termin-render/tgfx2/materials/components
  Python bindings for concrete passes

termin-components-render
  render scene components: CameraComponent, LightComponent, MeshRenderer,
  GeometryPassBase/Depth/Normal/Material while they still belong there

termin-app
  editor/player composition, default editor pipeline, resource-manager helpers,
  compatibility imports during migration

termin-android
  platform bootstrap, links SDK modules, no source-level dependency on termin-app
```

`termin-render-passes` may depend on:

- `termin-base`
- `termin-graphics`
- `termin-inspect`
- `termin-scene`
- `termin-lighting`
- `termin-render`
- `termin-materials`
- `termin-components-render`
- `termin-components-mesh`

Dependencies on collision/editor should be treated as split triggers, not silently added to the base pass module.

## Known blockers

### Duplicate ExecuteContext

There are two headers with the same include path intent:

- canonical: `termin-render/include/termin/render/execute_context.hpp`
- app copy: `termin-app/cpp/termin/render/execute_context.hpp`

The app copy differs by field names:

- app: `ctx.rect`
- canonical: `ctx.render_rect`
- app: `ctx.viewport_name`
- canonical: `ctx.render_target_name`

`ColorPass` and `IdPass` currently use `ctx.rect`. This must be fixed before those passes can compile cleanly in a SDK module without relying on the app include path.

### App-owned lighting upload helpers

`ColorPass` depends on:

- `termin-app/cpp/termin/lighting/lighting_ubo.hpp`
- `termin-app/cpp/termin/lighting/lighting_upload.hpp`

These are not app concepts. They should move before or with `ColorPass`. Candidate owner: `termin-render-passes` first, with a later review whether the data packing belongs in `termin-lighting` or `termin-render`.

### App-owned picking helper

`IdPass` depends on:

- `termin-app/core_c/include/tc_picking.h`
- `termin-app/core_c/src/tc_picking.c`

This should move before or with `IdPass`. Candidate owner: `termin-render-passes` unless a broader picking module appears.

### Bindings currently live in termin-app

Concrete pass bindings are mixed into app `_native.render`. The new module should own a new native binding target, tentatively:

- `termin.render_passes._render_passes_native`

App-level Python re-exports may remain temporarily, but their source should switch to `termin.render_passes`.

### ColliderGizmoPass has a wider dependency footprint

`ColliderGizmoPass` depends on collision components and debug immediate rendering. It is useful in editor pipelines, but it is not a clean "standard render pass" in the same sense as postprocess/color/shadow/present passes.

Do not let `ColliderGizmoPass` force collision/editor dependencies into the initial base migration unless we explicitly accept that dependency.

## Migration phases

### Phase 0: document and freeze scope

Goal: make the migration boundaries explicit before code movement.

Tasks:

- Add this plan.
- Add an audit entry that standard render passes currently live in `termin-app`.
- Treat `termin-app/cpp/termin/render/execute_context.hpp` as deprecated duplicate and stop adding includes that depend on it.

Verification:

- Documentation only.

### Phase 1: create empty `termin-render-passes`

Goal: establish the module skeleton without moving behavior.

Create:

- `termin-render-passes/CMakeLists.txt`
- `termin-render-passes/cmake/termin_render_passesConfig.cmake.in`
- `termin-render-passes/include/termin/render_passes/termin_render_passes.h`
- `termin-render-passes/include/termin/render_passes/version.h`
- `termin-render-passes/src/termin_render_passes_version.c`
- `termin-render-passes/docs/index.md`
- `termin-render-passes/pyproject.toml`
- `termin-render-passes/setup.py`
- `termin-render-passes/python/termin/render_passes/__init__.py`

Wire:

- top-level `CMakeLists.txt`: add `add_subdirectory(termin-render-passes)` after `termin-components-render` or after its required dependencies.
- build/install scripts if they enumerate packages manually.
- docs module index if needed.

Initial dependencies:

- `termin-render`
- `termin-materials`
- `termin-components-render`
- `termin-graphics`
- `termin-inspect`

Verification:

- `cmake --build build/Release --target termin_render_passes -j2`
- `./build-sdk-android.sh` should still work because Android is not changed yet.

### Phase 2: move pure utility/postprocess passes

Goal: move the lowest-risk pass set first.

Move to `termin-render-passes/include/termin/render/...` and `termin-render-passes/src/`:

- `present_pass.hpp/cpp`
- `debug_triangle_pass.hpp/cpp`
- `grayscale_pass.hpp/cpp`
- `tonemap_pass.hpp/cpp`
- `bloom_pass.hpp/cpp`
- `material_ubo_apply.hpp/cpp` if required by moved or next-phase passes

Notes:

- Keep public include paths stable as `<termin/render/present_pass.hpp>` etc. during the migration. That avoids changing every existing include at once.
- Remove these sources from `RENDER_LIB_SOURCES` in `termin-app/cpp/CMakeLists.txt`.
- Link `render_lib` against `termin_render_passes::termin_render_passes`.
- Keep app pipeline code unchanged except for CMake/linking.

Python:

- Do not move Python imports yet unless the native binding target already exists.
- If bindings move in this phase, keep app re-export modules forwarding to the new package.

Verification:

- `cmake --build build/Release --target termin_render_passes render_lib -j2`
- import smoke after binding move: `from termin.visualization.render.framegraph.passes.tonemap import TonemapPass`

### Phase 3: add Python bindings owned by `termin-render-passes`

Goal: concrete pass Python API stops depending on app native bindings.

Create:

- `termin-render-passes/python/render_passes_bindings.cpp`
- native target `_render_passes_native`
- package `termin.render_passes`

Move or split binding code from:

- `termin-app/cpp/termin/bindings/render/frame_pass.cpp`

Initially bind only the Phase 2 pass classes:

- `PresentToScreenPass`
- `DebugTrianglePass`
- `GrayscalePass`
- `TonemapPass`
- `BloomPass`

Also export:

- `TONEMAP_ACES`
- `TONEMAP_REINHARD`
- `TONEMAP_NONE`

Compatibility:

- `termin-app/termin/visualization/render/framegraph/passes/*.py` should import these classes from `termin.render_passes` rather than `termin._native.render`.
- Do not add new wrapper classes; use re-exports only.

Verification:

- `./build-sdk-bindings.sh` or target-specific binding build if available.
- `bash run-tests-python.sh` for import and pipeline tests.

### Phase 4: remove Android source-level dependency on app pass files

Goal: Android links `termin-render-passes` instead of compiling `../termin-app/cpp/termin/render/*.cpp`.

Change:

- Remove app pass `.cpp` entries from `TERMIN_ANDROID_SOURCES`.
- Remove `set_source_files_properties(... INCLUDE_DIRECTORIES "../termin-app/cpp")` for pass files.
- Link `termin_android` against `termin_render_passes::termin_render_passes`.

Only do this after the Android-used pass set exists in `termin-render-passes`:

- `bloom_pass`
- `color_pass`
- `material_ubo_apply`
- `present_pass`
- `shadow_camera`
- `shadow_pass`
- `shader_skinning`
- `skybox_pass`
- `tonemap_pass`

If Color/Shadow/Skybox are not moved yet, this phase must wait or be split into "partial Android cleanup" and "complete Android cleanup".

Verification:

- `./build-sdk-android.sh`

### Phase 5: normalize `ExecuteContext`

Goal: remove reliance on app duplicate `execute_context.hpp`.

Change pass code to canonical fields:

- `ctx.rect` -> `ctx.render_rect`
- `ctx.viewport_name` -> `ctx.render_target_name`, only where the semantic is actually render target name.

Then:

- update any app code that included the app duplicate to use `<termin/render/execute_context.hpp>`.
- delete `termin-app/cpp/termin/render/execute_context.hpp` if no longer used.

Expected affected pass files:

- `color_pass.cpp`
- `id_pass.cpp`

Verification:

- `rg "ctx\\.rect|ctx\\.viewport_name" termin-app termin-render-passes termin-components`
- `cmake --build build/Release --target termin_render termin_components_render render_lib -j2`

### Phase 6: move lighting upload helpers

Goal: unblock `ColorPass` move.

Move:

- `termin-app/cpp/termin/lighting/lighting_ubo.hpp`
- `termin-app/cpp/termin/lighting/lighting_upload.hpp`

Candidate destination:

- `termin-render-passes/include/termin/lighting/lighting_ubo.hpp`
- `termin-render-passes/include/termin/lighting/lighting_upload.hpp`

Reasoning:

- These helpers describe render-pass-side std140 packing and texture binding conventions.
- They are not editor/app concerns.
- They can be revisited later if `termin-lighting` grows a render-facing packing submodule.

Verification:

- No include path to `termin-app/cpp` should be needed for `ColorPass`.

### Phase 7: move `ColorPass`, `ShadowPass`, `SkyBoxPass`, `shadow_camera`, `shader_skinning`

Goal: move the main scene render passes.

Move:

- `color_pass.hpp/cpp`
- `shadow_pass.hpp/cpp`
- `skybox_pass.hpp/cpp`
- `shadow_camera.hpp/cpp`
- `shader_skinning.hpp/cpp`

Update dependencies:

- `termin-render-passes` links `termin-lighting`, `termin-materials`, `termin-components-render`, `termin-components-mesh`.
- `render_lib` no longer compiles these sources.
- Android no longer compiles these sources from app.

Python bindings:

- Move binding definitions for `ColorPass`, `ShadowPass`, `SkyBoxPass`, `ShadowMapResult`, `ShadowMapArrayEntry`, `ShadowMapArrayResource` if those resource classes are owned together with the passes.
- App re-export modules point to `termin.render_passes`.

Verification:

- `cmake --build build/Release --target termin_render_passes render_lib -j2`
- editor pipeline import smoke
- profiler/smoke scene render if practical

### Phase 8: move picking helper and `IdPass`

Goal: move ID rendering and picking support out of app.

Move:

- `termin-app/core_c/include/tc_picking.h`
- `termin-app/core_c/src/tc_picking.c`
- `id_pass.hpp/cpp`

Candidate destination:

- `termin-render-passes/include/tc_picking.h`
- `termin-render-passes/src/tc_picking.c`
- `termin-render-passes/include/termin/render/id_pass.hpp`
- `termin-render-passes/src/id_pass.cpp`

Open question:

- If picking becomes a broader SDK capability, this may later move into `termin-render` or a dedicated interaction/picking module. Do not block the pass migration on that split.

Verification:

- picking import smoke
- `rg "tc_picking" termin-app/core_c termin-app/cpp`

### Phase 9: decide debug/editor pass ownership

Goal: handle `GroundGridPass`, `ColliderGizmoPass`, and `ImmediateRenderer` intentionally.

Options:

1. Put them into `termin-render-passes-debug`.
2. Put them into `termin-render-passes` with optional collision dependency.
3. Keep them in `termin-app` as editor/debug app passes for now.

Recommended first decision:

- Move `GroundGridPass` with standard passes if it only needs camera/render/tgfx.
- Keep `ColliderGizmoPass` and `ImmediateRenderer` out of the first module until we decide whether collision debug rendering belongs in an optional debug package.

Reason:

- `ColliderGizmoPass` pulls `termin-components-collision` and is editor/debug-specific.
- Pulling collision into the base pass package would make every render-pass consumer depend on collision for one editor visualization pass.

Verification:

- If kept in app, document it as remaining app-owned debug pass, not forgotten debt.

### Phase 10: cleanup old app surfaces

Goal: remove compatibility ownership once consumers are migrated.

Remove from `termin-app/cpp/CMakeLists.txt`:

- moved pass sources from `RENDER_LIB_SOURCES`
- app include requirements that only existed for pass sources

Remove or shrink:

- concrete pass bindings from `termin-app/cpp/termin/bindings/render/frame_pass.cpp`
- app duplicate `termin/render/execute_context.hpp`
- app `core_c` leftovers used only by moved passes

Python cleanup:

- Long term, replace `termin.visualization.render.framegraph.passes.*` imports in app code with canonical `termin.render_passes`.
- Re-export modules may remain temporarily for compatibility, but they should contain no logic.

Verification:

- `rg "../termin-app/cpp/termin/render" termin-android termin-* CMakeLists.txt`
- `rg "termin/render/execute_context.hpp" termin-app/cpp`
- `rg "from termin\\._native\\.render import (ColorPass|ShadowPass|BloomPass|GrayscalePass|TonemapPass|SkyBoxPass|PresentToScreenPass|IdPass)" termin-app`

## Suggested first implementation batch

First batch should be intentionally small:

1. Create empty `termin-render-passes`.
2. Move `PresentToScreenPass`, `GrayscalePass`, `TonemapPass`, `BloomPass`, `DebugTrianglePass`.
3. Add bindings for only those moved classes.
4. Update app re-export modules for those classes.
5. Leave Android unchanged until `ColorPass`/`ShadowPass` are moved.

This gives a real module and verifies the path without touching the hardest scene-render passes immediately.

## Do not do in the first batch

- Do not move `ColorPass` before `ExecuteContext` duplicate is resolved.
- Do not move `IdPass` before `tc_picking` ownership is decided.
- Do not move `ColliderGizmoPass` if it forces collision into the base module by accident.
- Do not keep using `termin-app/cpp` include paths to make the new module compile.
- Do not add compatibility wrappers around C++ pass classes. Python modules should re-export native classes.

## Build checks

Host:

```bash
cmake --build build/Release --target termin_render_passes render_lib -j2
```

Bindings:

```bash
./build-sdk-bindings.sh
bash run-tests-python.sh
```

Android after Android source cleanup:

```bash
./build-sdk-android.sh
```

## Documentation follow-up

When the migration starts, update:

- `docs/architecture_boundary_violations_audit.md`
- `docs/modules.md`
- `docs/library-dependencies.md`
- `docs/library-dependencies.dot`
- `docs/plans/index.md`

When the migration finishes, move the final module contract into live module documentation and mark this plan as historical.
