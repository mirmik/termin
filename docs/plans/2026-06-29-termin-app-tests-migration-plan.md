# termin-app tests migration plan

Date: 2026-06-29
Status: implemented

## Goal Objective

Move domain-owned Python tests out of `termin-app/tests` into the packages that
own the code under test, remove test-only dependencies on editor internals, and
leave `termin-app/tests` focused on editor/app/launcher/UI integration.

Goal-mode objective:

```text
Finish the termin-app Python test migration described in
docs/plans/2026-06-29-termin-app-tests-migration-plan.md in one pass: move
domain tests from termin-app/tests to package-owned tests directories, replace
editor ResourceManager usage with domain/runtime test fixtures where needed,
keep only editor/app integration tests in termin-app, add boundary coverage, and
verify with the listed package test gates.
```

## Context

The production-code extraction from `termin-app` is mostly complete. As of this
plan, non-app packages no longer import `termin.editor_core`,
`termin.editor_tcgui` or `termin.launcher`.

The remaining visible debt is mostly in tests:

- many domain tests still live in `termin-app/tests`;
- some domain tests still use `termin.editor_core.resource_manager.ResourceManager`;
- several tests are mixed: they assert domain behavior but rely on editor
  composition helpers or app fixtures;
- boundary tests already protect many removed app facades, but they do not yet
  fully protect the new package-owned test layout.

This work is intentionally about test ownership and test fixtures. It should
not reopen the package extraction decisions unless a test exposes a real
production dependency leak.

## Non-Goals

- Do not move editor, editor UI, launcher, MCP editor service, or app
  integration tests out of `termin-app`.
- Do not reintroduce compatibility shims for removed `termin-app` modules.
- Do not pull `termin.editor_core` into domain packages just to make old tests
  pass.
- Do not redesign `AssetRuntimeManager`, `DefaultResourceManager`, project
  build, GLB, or material architecture in this goal.
- Do not broaden test scope while moving files unless the move exposes a real
  boundary bug.

## Target State

After the migration:

- `termin-app/tests` contains only editor/app/launcher/UI integration tests and
  architecture/import-side-effect tests;
- domain packages own their domain tests under their own `tests` directories;
- package tests for `termin-glb`, `termin-default-assets`, `termin-assets`,
  `termin-project-build`, `termin-project`, `termin-navmesh`, `termin-base`,
  `termin-components/termin-components-kinematic`, `termin-collision`,
  `termin-render`, `termin-components/termin-components-render`,
  `termin-materials`, `termin-csg`, and `termin-animation` do not import
  `termin.editor_core` or `termin.editor_tcgui`;
- tests that need asset-runtime behavior use `termin_assets.AssetRuntimeManager`,
  `termin.default_assets.resource_manager.DefaultResourceManager`, or narrow
  local fakes instead of the editor `ResourceManager`;
- architecture boundary tests catch obvious regressions back into app-owned
  test placement or editor-private imports.

## Execution Order

### 1. Refresh The Audit

Start with a clean working-tree check and a fresh classification of
`termin-app/tests`:

```bash
git status --short
find termin-app/tests -maxdepth 2 -type f -name '*.py' | sort
rg -n "termin\\.editor_core|termin\\.editor_tcgui|termin\\.launcher" termin-* --glob '*.py' --glob '!termin-app/**' --glob '!build/**' --glob '!sdk/**'
rg -l "termin\\.project_build" termin-app/tests --glob '*.py' | sort
rg -l "termin\\.project\\.settings|from termin\\.project import" termin-app/tests --glob '*.py' | sort
rg -l "termin\\.glb|termin\\.default_assets|termin\\.stdlib|termin_assets" termin-app/tests --glob '*.py' | sort
rg -l "termin\\.navmesh|termin\\.geombase|termin\\.kinematic|termin\\.colliders|termin\\.render_framework|termin\\.materials|termin\\.mesh|termin\\.csg|termin\\.animation" termin-app/tests --glob '*.py' | sort
```

If the first `rg` finds non-app production/test imports of editor/app packages,
fix or record them before closing the goal.

### 2. Move Clean Domain Tests First

Move tests that do not import `termin.editor_core` or `termin.editor_tcgui`
before touching mixed fixture tests.

Expected first batch:

- `termin-project-build/tests`:
  - `test_project_build_capabilities.py`;
  - `test_project_build_context.py`;
  - `test_project_build_diagnostics.py`;
  - `test_project_build_pipeline.py`;
  - `test_project_build_profile_backend.py`;
  - `test_project_build_target_common.py`;
  - `test_project_build_target_preflight.py`;
  - `test_runtime_package_exporter.py`;
  - `test_runtime_package_exporter_android.py`;
  - `test_runtime_package_validator.py`.
- `termin-project/tests`:
  - `test_project_settings.py`.
- `termin-glb/tests`:
  - `test_gltf_loader.py`, after confirming it no longer needs editor
    `ResourceManager`.
- `termin-navmesh/tests`:
  - `pathfinding_test.py`;
  - `test_edge_flipping.py`;
  - `test_funnel_algorithm.py`;
  - `test_navmesh_package_facade.py`.
- `termin-base/tests` or the currently owning geometry package:
  - `pose_test.py`;
  - `pose2_test.py`;
  - `test_general_pose3.py`;
  - `test_general_transform3.py`;
  - `util_test.py`;
  - `aabb_test.py`, if `termin.geombase` is the owner.
- `termin-kinematic/tests`:
  - `tests/kinematics/*`.
- `termin-colliders/tests`:
  - `collider_test.py`;
  - `test_collision_teleport_component.py`.
- `termin-render-framework/tests` or the current render-framework owner:
  - `framegraph_test.py`;
  - `test_framegraph_internal_points.py`.
- `termin-materials/tests`:
  - `test_material_registry_copy.py`;
  - material-only cases split out of shader/material serialization tests.
- `termin-csg/tests` or procedural mesh owner:
  - `test_procedural_mesh_component.py`.
- `termin-animation/tests`:
  - `test_canonical_animation_imports.py`, if component imports fit that
    package boundary.

After each package batch, run that package's tests before moving on.

### 3. Untangle Asset Runtime Tests

Handle tests that still import editor `ResourceManager` as a separate pass.

Do not move these by carrying editor imports into domain packages:

- `asset_plugin_test.py`;
- `shader_parser_test.py`;
- `test_gltf_loader.py`;
- `test_material_asset_texture_persistence.py`;
- `test_material_pass_serialization.py`;
- `test_texture_lazy_registration.py`.

Preferred replacements:

- use `AssetRuntimeManager` plus explicit `AssetRegistry` instances for narrow
  embedded-asset contracts;
- use `DefaultResourceManager` when the test is explicitly about
  `termin-default-assets` composition;
- use local fakes when the production code accepts a small protocol surface;
- use `termin_assets.set_resource_manager_factory()` only around code paths
  that intentionally exercise the global access point, and always reset it in
  `finally`.

Package placement guidance:

- GLB loader/repair tests go to `termin-glb/tests`;
- generic asset plugin/preloader behavior goes to `termin-assets/tests`;
- default mesh/texture/material/audio/ui/prefab integration goes to
  `termin-default-assets/tests`;
- material serialization tests go to `termin-materials/tests` unless they
  specifically test default asset composition.

### 4. Keep App-Owned Tests In App

Leave these categories in `termin-app/tests`:

- editor command/undo/project operation tests;
- `editor_core` and `editor_tcgui` model/controller/widget tests;
- launcher tests;
- editor MCP tests;
- project browser/dialog/controller tests;
- app import-side-effect tests;
- architecture boundary tests;
- tests that intentionally validate editor composition with
  `termin.editor_core.resource_manager.ResourceManager`.

Examples that should normally stay:

- `editor_commands_test.py`;
- `undo_stack_test.py`;
- `test_editor_builtin_resources.py`;
- `test_editor_mcp_server.py`;
- `test_editor_python_executor.py`;
- `test_editor_shader_runtime.py`;
- `test_framegraph_debugger_model_disconnect.py`;
- `test_game_mode_model.py`;
- `test_game_mode_ui_controller.py`;
- `test_gltf_drag_drop.py`;
- `test_launcher_process_mode.py`;
- `test_material_inspector_texture.py`;
- `test_project_build_controller.py`;
- `test_project_file_action_controller.py`;
- `test_project_file_watcher.py`, unless split later into asset watcher domain
  tests and editor policy tests;
- `test_project_operations.py`;
- `test_project_settings_dialog.py`;
- `test_scene_file_model.py`;
- `test_scene_manager_viewer.py`;
- `test_tcgui_*`;
- `test_texture_inspector.py`;
- `test_vec3_list_field_widget.py`.

If one of these contains a pure domain subsection, split the subsection into
the owning package instead of moving the whole mixed test file.

### 5. Add Boundary Coverage

Extend `termin-app/tests/test_architecture_boundaries.py` after the moves.

Suggested assertions:

- domain package tests do not import `termin.editor_core` or
  `termin.editor_tcgui`;
- `termin-glb/tests` does not import editor internals;
- `termin-project-build` tests live in `termin-project-build/tests`, not in
  `termin-app/tests`;
- `termin-project` settings tests live in `termin-project/tests`;
- obvious geometry/navmesh/render-framework/materials test files no longer live
  directly under `termin-app/tests`.

Keep the boundary test pragmatic. It should prevent old ownership from creeping
back, not encode every possible filename forever.

### 6. Clean Test Config And Imports

For each moved package:

- check its `pyproject.toml`/pytest config and package path assumptions;
- fix relative imports between moved tests;
- avoid importing sibling tests through `termin-app/tests`;
- remove stale references to old file paths from docs if found;
- keep `__pycache__` and `.pytest_cache` out of the diff.

If moving a test changes pytest rootdir behavior, prefer adjusting the package
test to use robust project-relative fixtures over relying on `termin-app`
pytest configuration.

## Verification Gates

Run package-local tests as batches:

```bash
./run-tests-python.sh termin-project-build/tests
./run-tests-python.sh termin-project/tests
./run-tests-python.sh termin-glb/tests
./run-tests-python.sh termin-assets/tests
./run-tests-python.sh termin-default-assets/tests
./run-tests-python.sh termin-navmesh/tests
./run-tests-python.sh termin-base/tests
./run-tests-python.sh termin-components/termin-components-kinematic/tests
./run-tests-python.sh termin-collision/tests
./run-tests-python.sh termin-render/tests
./run-tests-python.sh termin-components/termin-components-render/tests
./run-tests-python.sh termin-materials/tests
./run-tests-python.sh termin-csg/tests
./run-tests-python.sh termin-animation/tests
./run-tests-python.sh termin-app/tests/test_architecture_boundaries.py
```

If a package has no tests directory or no matching moved tests, skip that gate
and say so in the goal summary.

Final broad gate when time allows:

```bash
./run-tests-python.sh
```

## Completion Checklist

- `termin-app/tests` no longer contains obvious domain-only tests.
- Moved tests pass from their owning packages.
- Domain package tests do not import `termin.editor_core` or
  `termin.editor_tcgui`.
- Asset-runtime tests use domain/default-assets fixtures instead of editor
  `ResourceManager`.
- Boundary tests cover the new ownership rule.
- Any test that remains in `termin-app/tests` has a clear editor/app
  integration reason.
- `git status --short` contains only intentional source/test/doc changes.
