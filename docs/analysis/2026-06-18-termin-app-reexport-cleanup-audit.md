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
- Breaking cleanup on 2026-06-19 removed the remaining test-only app asset
  shim modules and the GLB loader compatibility modules after moving tests to
  canonical package paths.
- A second breaking cleanup on 2026-06-19 removed small editor/project-build
  and visualization shims after internal consumers were redirected to canonical
  packages.
- Kept editor CLI entrypoint compatibility paths because they may be used
  outside normal Python import scans.

There are enough leftovers to justify a dedicated cleanup pass, but they should not all be removed in one sweep. `termin.assets.resources` is still an active app-owned runtime implementation, and `termin.visualization.*` is still used as a shared runtime facade by app code and external component packages.

## Cleanup Order

1. Remove or redirect unused pure shims.
2. Convert test-only compatibility imports to canonical paths, then remove those shims if they have no external compatibility commitment.
3. Clean small, low-risk package facades such as `termin.loaders.*`.
4. Handle `termin.assets.*` together with the asset-runtime boundary in `#40`.
5. Handle `termin.visualization.*` only after choosing the canonical visualization/runtime package boundary.

## Asset Compatibility Layer

Largest cluster at the start of the audit:
- `termin.assets`: `43` explicit compatibility modules.
- `40` were pure re-export shims.

Current status after the 2026-06-19 breaking cleanup:
- `termin-app/termin/assets` contains only the package facade, the
  app-specific `project_file_watcher` wrapper, and the active
  `termin.assets.resources` runtime facade.
- App-side `termin.assets.<asset/plugin/handle>` submodule compatibility paths
  for default/domain asset types were removed. Internal tests now import
  canonical paths directly.

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

Removed app asset shims:
- `termin.assets.animation_clip_asset`
- `termin.assets.animation_clip_handle`
- `termin.assets.asset`
- `termin.assets.asset_plugin`
- `termin.assets.asset_registry`
- `termin.assets.audio_clip_asset`
- `termin.assets.audio_clip_handle`
- `termin.assets.audio_clip_plugin`
- `termin.assets.builtin_resources`
- `termin.assets.builtin_uuids`
- `termin.assets.data_asset`
- `termin.assets.default_plugins`
- `termin.assets.glb_asset`
- `termin.assets.glb_plugin`
- `termin.assets.glsl_asset`
- `termin.assets.glsl_plugin`
- `termin.assets.material_asset`
- `termin.assets.material_plugin`
- `termin.assets.mesh_asset`
- `termin.assets.mesh_plugin`
- `termin.assets.navmesh_asset`
- `termin.assets.navmesh_handle`
- `termin.assets.navmesh_plugin`
- `termin.assets.pipeline_asset`
- `termin.assets.pipeline_dependencies`
- `termin.assets.pipeline_plugin`
- `termin.assets.plugin_preloader`
- `termin.assets.prefab_asset`
- `termin.assets.prefab_plugin`
- `termin.assets.resource_handle`
- `termin.assets.resources._registration`
- `termin.assets.scene_pipeline_asset`
- `termin.assets.scene_pipeline_plugin`
- `termin.assets.skeleton_asset`
- `termin.assets.skeleton_handle`
- `termin.assets.shader_asset`
- `termin.assets.shader_interface`
- `termin.assets.shader_plugin`
- `termin.assets.texture_asset`
- `termin.assets.texture_handle`
- `termin.assets.texture_plugin`
- `termin.assets.ui_asset`
- `termin.assets.ui_handle`
- `termin.assets.ui_plugin`
- `termin.assets.voxel_grid_asset`
- `termin.assets.voxel_grid_handle`
- `termin.assets.voxel_grid_plugin`

Still retained app asset compatibility/runtime surface:
- `termin.assets` package facade
- `termin.assets.project_file_watcher`
- `termin.assets.resources`

`project_file_watcher` has local wrapper behavior and should be reviewed separately from pure asset class shims. `termin.assets.resources` remains active runtime glue and should move only with the asset-runtime boundary.

## Visualization Facades

Remaining production-used visualization-owned paths:
- `termin.visualization.core.scene`
- `termin.visualization.core.camera`
- `termin.visualization.core.viewport`
- `termin.visualization.render.glsl_preprocessor`
- `termin.visualization.render.framegraph.*`
- `termin.visualization.render.materials.*`
- `termin.visualization.platform.*`
- `termin.visualization.ui.widgets.component`

These are imported by:
- `termin-app/termin/editor_core/*`
- `termin-app/termin/editor_tcgui/*`
- `termin-app/termin/player/*`
- `termin-navmesh`
- `termin-physics`
- examples

These are no longer treated as canonical facade APIs. Move consumers to domain
packages where a canonical owner exists, and move real app/runtime logic only
after choosing the new owner.

Likely canonical replacements:
- `termin.visualization.core.entity` -> `termin.scene.Entity`
- `termin.visualization.core.component` -> `termin.scene.Component`, `termin.input.InputComponent`, `termin.inspect.InspectField`
- `termin.visualization.core.python_component` -> `termin.scene.PythonComponent`, `termin.input.InputComponent`, `termin.render.DrawableComponent`
- `termin.visualization.core.input_events` -> `termin.input` (`MouseButtonEvent`, `MouseMoveEvent`, `ScrollEvent`, `KeyEvent`)
- `termin.visualization.render.immediate` -> `termin.render.ImmediateRenderer`
- `termin.visualization.render.manager` -> `termin.engine.RenderingManager`
- `termin.visualization.core.voxel_grid_handle` -> `termin.voxels._voxels_native.VoxelGridHandle`
- `termin.visualization.core.picking` -> `termin.render_passes`
- `termin.visualization.render.shader` -> `tgfx.TcShader`, `termin.materials.GlslPreprocessor`
- `termin.visualization.core.display` -> `termin.display.Display`
- `termin.visualization.render.render_context` -> `termin.render_framework.RenderContext`
- `termin.visualization.render.drawable` -> `termin.render.drawable`
- `termin.visualization.render.framegraph.resource_spec` -> `termin.render_framework.ResourceSpec`
- `termin.visualization.platform.backends.fbo_backend` -> `termin.display.FBOSurface`

Removed after internal consumers were redirected:
- `termin.visualization.core.entity_registry`
- `termin.visualization.core.plugin_loader`
- `termin.visualization.core.prefab_instance_marker`
- `termin.visualization.core.prefab_registry`
- `termin.visualization.core.property_path`
- `termin.visualization.core.component`
- `termin.visualization.core.display`
- `termin.visualization.core.entity`
- `termin.visualization.core.picking`
- `termin.visualization.core.python_component`
- `termin.visualization.core.serialization`
- `termin.visualization.core.voxel_grid_handle`
- `termin.visualization.render.drawable`
- `termin.visualization.render.framegraph.pipeline`
- `termin.visualization.render.framegraph.resource_spec`
- `termin.visualization.render.manager`
- `termin.visualization.render.render_context`
- `termin.visualization.render.shader`
- `termin.visualization.render.shader_parser`
- `termin.visualization.render.solid_primitives`
- `termin.visualization.render.texture`
- `termin.visualization.render.view`
- `termin.visualization.platform.backends.fbo_backend`
- `termin.visualization.ui.widgets.basic`
- `termin.visualization.ui.widgets.containers`
- `termin.visualization.ui.widgets.units`

Package-level `termin.visualization.__init__` and `termin.visualization.render.__init__`
were stripped to namespace-only modules on 2026-06-19. Do not add new
package-level domain re-exports there.

Resolved in this cleanup pass:
- `termin.visualization.core.input_events` was removed. Python consumers import
  event classes from `termin.input`; native registration lives in
  `termin-display` because event instances carry `TcViewport` handles.
- `termin.visualization.render.immediate` was removed. The singleton wrapper
  moved to `termin.render.ImmediateRenderer`; native immediate rendering remains
  in `tgfx.ImmediateRenderer`.

Still deferred:
- `termin.visualization.core.scene` owns app-specific scene extension helpers
  such as `create_scene`, `scene_render_mount`, and `default_scene_extensions`;
  these need a canonical owner before removal.
- Real editor/debug/framegraph/material/platform modules under
  `termin.visualization.*` still need ownership decisions or extraction.

## Loader Shims

Explicit compatibility modules:
- `termin.loaders.mesh_spec` -> `termin.default_assets.mesh.mesh_spec`
- `termin.loaders.obj_loader` -> `termin.default_assets.mesh.obj_loader`
- `termin.loaders.stl_loader` -> `termin.default_assets.mesh.stl_loader`
- `termin.loaders.texture_spec` -> `termin.default_assets.render.texture_spec`
- `termin.loaders.glb_loader` -> `termin.glb.loader`
- `termin.loaders.glb_extractor` -> `termin.glb.extractor`
- `termin.loaders.glb_instantiator` -> `termin.glb.instantiator`

Current status:
- `termin.loaders.mesh_spec` was removed after tests moved to
  `termin.default_assets.mesh.mesh_spec`.
- `termin.loaders.obj_loader` was removed in the first unused cleanup batch.
- `termin.loaders.stl_loader` was removed in the first unused cleanup batch.
- `termin.loaders.texture_spec` was removed in the first unused cleanup batch.
- `termin.loaders.glb_loader`, `termin.loaders.glb_extractor`, and
  `termin.loaders.glb_instantiator` were removed on 2026-06-19 after GLB
  runtime moved to the canonical `termin.glb.*` package and internal scans
  showed no direct repository imports of the app loader paths.

## Editor And Project Build Entry Points

Compatibility entry points:
- `termin.editor`
- `termin.editor.run_editor`

Current status:
- `termin.editor` / `termin.editor.run_editor` are legacy editor entry points around `termin.editor_tcgui`.
- `termin.project_builder.profile_build` was removed on 2026-06-19 after the
  C++ `termin_builder`, tests, and docs were already using
  `termin.project_build.profile_build`.

Recommended cleanup:
- Keep editor command-line entry points until launcher/build scripts and docs are checked.
- Prefer warning/deprecation before removal if these paths are part of user-visible CLI compatibility.
- Check `setup.py`, script entry points, C++ launcher calls, docs, and user-facing examples before deleting.

## Core And Profiler Facades

Removed after internal consumers were redirected:
- `termin.core.profiler` -> `tcbase.profiler`
- `termin.core.identifiable` -> `termin_assets.identifiable`

Current status:
- App imports now use canonical paths directly.
- Package-level `from termin.core import Identifiable` still works through
  `termin.core.__init__`, but the removed `termin.core.identifiable` submodule
  no longer exists.

## Test-Only Compatibility Contracts

Several tests used to assert that old app paths re-export canonical classes.
Those assertions were removed on 2026-06-19 for the app-owned
`termin.assets.<asset/plugin/handle>` compatibility modules. Tests now import
canonical package paths directly. Domain-level legacy paths such as
`termin.mesh.mesh_asset` or `termin.audio.audio_clip_asset` were intentionally
left out of this app cleanup.

## Suggested First Pass

Low-risk cleanup batch:
- Converted tests away from `termin.loaders.mesh_spec` and removed the shim.
- Removed unused `termin.loaders.obj_loader`, `termin.loaders.stl_loader`, and `termin.loaders.texture_spec`.
- Redirected `termin.core.profiler` production imports to `tcbase.profiler`
  and removed the shim.
- Redirected `termin.core.identifiable` package import to
  `termin_assets.identifiable` and removed the submodule shim.
- Fixed the C++ `termin.visualization.render.texture_asset` import to
  `termin.default_assets.render.texture_asset`.

Asset cleanup batch:
- Converted test-only `termin.assets.<domain asset/plugin>` imports to canonical packages.
- Removed pure app asset shims once test coverage no longer referenced them.
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
