# Termin App Re-Export Cleanup Audit

Date: 2026-06-18

Scope:
- Python re-export and compatibility modules under `termin-app/termin`.
- Direct Python import usage across the repository, excluding build/sdk/venv/cache outputs.
- C++ inline imports that anchor legacy Python module paths.

Related Kanboard tasks:
- `#36 [architecture] Наметить следующий вынос из termin-app`
- `#40 [assets] Завершить вынос asset runtime из termin-app`

## Summary

`termin-app` still contains a broad compatibility layer left by package extractions and API migrations.

Audit counts:
- `336` Python files under `termin-app/termin`.
- `74` modules have explicit compatibility/re-export wording in module docs.
- `68` of those are pure or near-pure import shims.
- `37` explicit compatibility modules have no direct Python imports in the repository.
- `18` explicit compatibility modules are referenced only by tests.
- `19` explicit compatibility modules are still referenced by production code.

Cleanup status:
- First unused cleanup batch started on 2026-06-18.
- Removed `31` unused app compatibility modules with no live direct code imports.
- Follow-up cleanup removed `termin.loaders.mesh_spec` and
  `termin.assets.texture_handle` after redirecting their remaining consumers.
- Kept CLI/entrypoint compatibility paths because they may be used outside normal Python import scans.

There are enough leftovers to justify a dedicated cleanup pass, but they should not all be removed in one sweep. `termin.assets.resources` is still an active app-owned runtime implementation, and `termin.visualization.*` is still used as a shared runtime facade by app code and external component packages.

## Cleanup Order

1. Remove or redirect unused pure shims.
2. Convert test-only compatibility imports to canonical paths, then remove those shims if they have no external compatibility commitment.
3. Clean small, low-risk package facades such as `termin.loaders.*`.
4. Handle `termin.assets.*` together with the asset-runtime boundary in `#40`.
5. Handle `termin.visualization.*` only after choosing the canonical visualization/runtime package boundary.

## Asset Compatibility Layer

Largest cluster:
- `termin.assets`: `43` explicit compatibility modules.
- `40` are pure re-export shims.

Keep for now:
- `termin.assets.resources`

Reason:
- This is not a passive shim. It still owns `ResourceManager` and registers the app resource-manager factory:
  - `termin-app/termin/assets/resources/__init__.py`
  - `termin-app/termin/assets/resources/_manager.py`
  - `termin-app/termin/assets/resources/_base.py`
  - `termin-app/termin/assets/resources/_assets.py`
  - `termin-app/termin/assets/resources/_accessors.py`
  - `termin-app/termin/assets/resources/_components.py`
  - `termin-app/termin/assets/resources/_pipelines.py`
  - `termin-app/termin/assets/resources/_scene_pipelines.py`
  - `termin-app/termin/assets/resources/_serialization.py`
  - `termin-app/termin/assets/resources/_builtins.py`
  - `termin-app/termin/assets/resources/_handle_accessors.py`

Native anchors:
- `termin-app/cpp/termin/assets/handles_inline.hpp`
- `termin-app/cpp/termin/assets/voxel_grid_handle_inline.hpp`

These C++ inline handle helpers import `termin.assets.resources` directly. They need a stable bridge or canonical resource-runtime package before the old app path can be removed.

C++ texture handle cleanup:
- `termin-app/cpp/termin/assets/handles_inline.hpp` now imports
  `termin.default_assets.render.texture_asset` for `TextureAsset`.
- `get_white_texture_handle()` now imports `termin.render.texture_handle`.
- `termin.assets.texture_handle` was removed after the string import was
  redirected.

Clean after tests-only usage is redirected:
- `termin.assets.animation_clip_asset` -> `termin.animation.asset`
- `termin.assets.audio_clip_asset` -> `termin.default_assets.audio.asset`
- `termin.assets.audio_clip_handle` -> `termin.default_assets.audio.handle`
- `termin.assets.mesh_asset` -> `termin.default_assets.mesh.asset`
- `termin.assets.navmesh_asset` -> `termin.default_assets.navmesh.asset`
- `termin.assets.navmesh_handle` -> `termin.default_assets.navmesh.handle`
- `termin.assets.pipeline_asset` -> `termin.default_assets.render.pipeline_asset`
- `termin.assets.pipeline_plugin` -> `termin.default_assets.render.pipeline_plugin`
- `termin.assets.prefab_asset` -> `termin.prefab.asset`
- `termin.assets.prefab_plugin` -> `termin.prefab.asset_plugin`
- `termin.assets.scene_pipeline_asset` -> `termin.default_assets.render.scene_pipeline_asset`
- `termin.assets.scene_pipeline_plugin` -> `termin.default_assets.render.scene_pipeline_plugin`
- `termin.assets.skeleton_asset` -> `termin.skeleton.asset`
- `termin.assets.ui_asset` -> `termin.default_assets.ui.asset`
- `termin.assets.ui_handle` -> `termin.default_assets.ui.handle`
- `termin.assets.ui_plugin` -> `termin.default_assets.ui.asset_plugin`
- `termin.assets.voxel_grid_asset` -> `termin.default_assets.voxels.asset`

Removed app asset shims:
- `termin.assets.audio_clip_plugin`
- `termin.assets.default_plugins`
- `termin.assets.glsl_asset`
- `termin.assets.glsl_plugin`
- `termin.assets.material_asset`
- `termin.assets.material_plugin`
- `termin.assets.mesh_plugin`
- `termin.assets.navmesh_plugin`
- `termin.assets.pipeline_dependencies`
- `termin.assets.plugin_preloader`
- `termin.assets.resources._registration`
- `termin.assets.shader_asset`
- `termin.assets.shader_interface`
- `termin.assets.shader_plugin`
- `termin.assets.texture_asset`
- `termin.assets.texture_handle`
- `termin.assets.texture_plugin`
- `termin.assets.voxel_grid_plugin`

Still production-used app asset shims:
- `termin.assets.asset`
- `termin.assets.asset_plugin`
- `termin.assets.asset_registry`
- `termin.assets.data_asset`
- `termin.assets.project_file_watcher`
- `termin.assets.resource_handle`
- `termin.assets.skeleton_handle`
- `termin.assets.voxel_grid_handle`

These should be redirected internally before deletion. `project_file_watcher` has local wrapper behavior and should be reviewed separately from pure asset class shims.

## Visualization Facades

Production-used facade paths:
- `termin.visualization.core.entity`
- `termin.visualization.core.component`
- `termin.visualization.core.display`
- `termin.visualization.render.render_context`
- `termin.visualization.render.drawable`
- `termin.visualization.render.framegraph.resource_spec`
- `termin.visualization.platform.backends.fbo_backend`

These are imported by:
- `termin-app/termin/editor_core/*`
- `termin-app/termin/editor_tcgui/*`
- `termin-app/termin/player/*`
- `termin-navmesh`
- `termin-components-render`
- `termin-components-voxels`
- `termin-physics`
- examples

Do not delete these one-by-one unless their consumers are first moved to canonical packages.

Likely canonical replacements:
- `termin.visualization.core.entity` -> `termin.scene.Entity`
- `termin.visualization.core.component` -> `termin.scene.Component`, `termin.scene.InputComponent`, `termin.inspect.InspectField`
- `termin.visualization.core.display` -> `termin.display.Display`
- `termin.visualization.render.render_context` -> `termin.render_framework.RenderContext`
- `termin.visualization.render.drawable` -> `termin.render.drawable`
- `termin.visualization.render.framegraph.resource_spec` -> `termin.render_framework.ResourceSpec`
- `termin.visualization.platform.backends.fbo_backend` -> `termin.display.FBOSurface`

Removed in the first unused cleanup batch:
- `termin.visualization.core.entity_registry`
- `termin.visualization.core.plugin_loader`
- `termin.visualization.core.prefab_instance_marker`
- `termin.visualization.core.prefab_registry`
- `termin.visualization.core.property_path`
- `termin.visualization.render.shader_parser`
- `termin.visualization.render.solid_primitives`
- `termin.visualization.render.texture`
- `termin.visualization.ui.widgets.basic`
- `termin.visualization.ui.widgets.containers`
- `termin.visualization.ui.widgets.units`

Unused direct-import visualization shims still deferred:
- `termin.visualization.render.shader` contains local wrapper code and should be reviewed separately.

Note: `termin.visualization.__init__`, `termin.visualization.core.__init__`, `termin.visualization.render.__init__`, and `termin.visualization.render.framegraph.__init__` are broader package facades. They were not counted as explicit migration shims in the same way, but they should be reviewed when the visualization boundary is redesigned.

## Loader Shims

Explicit compatibility modules:
- `termin.loaders.mesh_spec` -> `termin.default_assets.mesh.mesh_spec`
- `termin.loaders.obj_loader` -> `termin.default_assets.mesh.obj_loader`
- `termin.loaders.stl_loader` -> `termin.default_assets.mesh.stl_loader`
- `termin.loaders.texture_spec` -> `termin.default_assets.render.texture_spec`

Current status:
- `termin.loaders.mesh_spec` was removed after tests moved to
  `termin.default_assets.mesh.mesh_spec`.
- `termin.loaders.obj_loader` was removed in the first unused cleanup batch.
- `termin.loaders.stl_loader` was removed in the first unused cleanup batch.
- `termin.loaders.texture_spec` was removed in the first unused cleanup batch.

Recommended cleanup:
- Change tests to canonical `termin.default_assets.*` imports.
- Remove the unused loader shims once external compatibility policy allows it.

Do not include non-shim GLB loader/instantiator files in this small cleanup:
- `termin.loaders.glb_loader`
- `termin.loaders.glb_extractor`
- `termin.loaders.glb_instantiator`

Those still contain real loader/runtime logic.

## Editor And Project Build Entry Points

Compatibility entry points:
- `termin.editor`
- `termin.editor.run_editor`
- `termin.project_builder.profile_build`

Current status:
- `termin.editor` / `termin.editor.run_editor` are legacy editor entry points around `termin.editor_tcgui`.
- `termin.project_builder.profile_build` delegates to the canonical `termin.project_build.profile_build`.

Recommended cleanup:
- Keep command-line entry points until launcher/build scripts and docs are checked.
- Prefer warning/deprecation before removal if these paths are part of user-visible CLI compatibility.
- Check `setup.py`, script entry points, C++ launcher calls, docs, and user-facing examples before deleting.

## Core And Profiler Facades

Production-used shims:
- `termin.core.profiler` -> `tcbase.profiler`
- `termin.core.identifiable` -> `termin_assets.identifiable`

Recommended cleanup:
- Redirect app imports to canonical paths.
- Keep or remove package-level `termin.core` facade based on public API policy after internal consumers are gone.

## Test-Only Compatibility Contracts

Several tests intentionally assert that old app paths re-export canonical classes. These tests preserve compatibility, but they also keep migration shims alive.

Review and either update or delete compatibility assertions in:
- `termin-app/tests/test_asset_default_plugins.py`
- `termin-app/tests/test_canonical_animation_imports.py`
- `termin-animation/tests/test_animation_asset.py`
- `termin-audio/tests/test_audio_asset_plugin.py`
- `termin-default-assets/tests/test_default_prefab_asset_plugin.py`
- `termin-default-assets/tests/test_default_ui_asset_plugin.py`
- `termin-mesh/tests/python/test_mesh_asset_plugin.py`
- `termin-navmesh/tests/test_navmesh_asset_plugin.py`
- `termin-prefab/tests/test_prefab_asset_plugin.py`
- `termin-skeleton/tests/test_skeleton_asset.py`
- `termin-voxels/tests/test_voxel_asset_plugin.py`

Policy decision needed:
- If old `termin.assets.*` paths are no longer a supported external API, remove these compatibility assertions and convert tests to canonical package imports.
- If old paths remain supported temporarily, add an explicit deprecation policy and target removal milestone.

## Suggested First Pass

Low-risk cleanup batch:
- Converted tests away from `termin.loaders.mesh_spec` and removed the shim.
- Removed unused `termin.loaders.obj_loader`, `termin.loaders.stl_loader`, and `termin.loaders.texture_spec`.
- Redirect `termin.core.profiler` production imports to `tcbase.profiler`.
- Redirect `termin.core.identifiable` production imports to `termin_assets.identifiable`.
- Fixed the C++ `termin.visualization.render.texture_asset` import to
  `termin.default_assets.render.texture_asset`.

Asset cleanup batch:
- Convert test-only `termin.assets.<domain asset/plugin>` imports to canonical domain packages.
- Remove pure unused app asset shims once test coverage no longer references them.
- Keep `termin.assets.resources` until `#40` moves or bridges `ResourceManager`.

Visualization cleanup batch:
- Choose the package boundary first.
- Move internal app imports from `termin.visualization.core.*` and `termin.visualization.render.*` to canonical runtime packages.
- Update external package imports in the same pass or leave temporary shims with explicit deprecation.

## Verification Commands

Useful local checks after each cleanup batch:

```bash
rg -n "from termin\.assets\.|import termin\.assets\." -g '*.py' -g '*.hpp' -g '*.cpp' .
rg -n "from termin\.loaders\.|import termin\.loaders\." -g '*.py' .
rg -n "from termin\.visualization\.(core|render|ui\.widgets)|import termin\.visualization\." -g '*.py' .
rg -n "termin\.visualization\.render\.texture_asset|termin\.assets\.resources" termin-app/cpp termin-app/termin -g '*.hpp' -g '*.cpp' -g '*.py'
./run-tests.sh
```

Use the central `./run-tests.sh` for final validation. For narrowly scoped import cleanup, start with the touched package tests, then run the full suite before deleting compatibility paths.
