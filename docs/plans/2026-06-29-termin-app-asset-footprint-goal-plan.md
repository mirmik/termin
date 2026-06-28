# termin-app asset footprint cleanup goal plan

Дата: 2026-06-29

Статус: implemented and verified in current working tree.

## Goal Objective

Reduce or remove the remaining asset-system footprint in `termin-app` after
the asset runtime migration, without re-opening broad asset architecture work.

Goal-mode objective:

```text
Finish the termin-app asset footprint cleanup described in
docs/plans/2026-06-29-termin-app-asset-footprint-goal-plan.md in one pass:
remove non-editor dependencies on termin.assets.resources, collapse app
ResourceManager implementation to canonical default-assets behavior, move the
app ProjectFileWatcher policy wrapper out of termin.assets, delete the stale
termin-app assets namespace when imports are gone, update docs/tests/Kanboard,
and verify with the listed gates.
```

## Context

The large migration from `termin-app` asset ownership is mostly done:

- neutral asset infrastructure lives in `termin-assets`;
- standard SDK asset adapters and `DefaultResourceManager` live in
  `termin-default-assets`;
- prefab and GLB ownership live in `termin-prefab` and `termin-glb`;
- missing material fallback policy now lives in `termin-materials` and
  `termin-default-assets`, not in `termin-app`;
- `termin-app` no longer publishes asset plugin entry points.

The remaining app footprint is now mostly naming and composition glue:

- `termin.assets.resources` is still the app-facing `ResourceManager` import;
- `termin.assets.project_file_watcher` is an app ignored-root policy wrapper
  over `termin_assets.project_file_watcher`;
- editor code imports these app asset namespaces heavily;
- `termin-modules` still imports `termin.assets.resources`, which makes the app
  namespace leak outside editor/app code;
- ignored `__pycache__` files below `termin-app/termin/assets` can make audits
  noisy but are not source files.

## Non-Goals

- Do not move concrete default asset implementations out of
  `termin-default-assets`.
- Do not remove typed convenience APIs such as `get_mesh()`, `get_material()`,
  `get_prefab_asset()`, etc.
- Do not redesign `AssetRuntimeManager`, `AssetRegistry`, plugin entry points,
  or project build manifests.
- Do not add compatibility fallbacks for removed app paths unless an existing
  live consumer cannot be migrated in this pass.
- Do not fix unrelated import-side-effect or nanobind cleanup debt unless it
  blocks the listed verification gates.

## Target State

After this pass:

- non-editor packages do not import `termin.assets.resources`;
- runtime-ish app helpers use `termin_assets.get_resource_manager()` or
  `termin.default_assets.resource_manager.DefaultResourceManager`, not the app
  namespace;
- the app `ResourceManager` implementation no longer duplicates
  `DefaultResourceManager` component/frame-pass behavior;
- editor-specific watcher policy is named as editor code, not as asset runtime;
- `termin-app/termin/assets` is either deleted or reduced to a short,
  intentionally documented compatibility shim with no implementation modules;
- tests assert the old implementation paths are gone or inert;
- docs and Kanboard #40 describe the final boundary.

## Execution Order

### 1. Refresh The Local Audit

Before editing, rerun a focused audit so the goal pass starts from current code:

```bash
git status --short
git ls-files termin-app/termin/assets termin-app/termin/editor_core termin-app/termin/editor_tcgui | rg 'asset|resource|resources|preload|loader'
rg -n "from termin\\.assets\\.resources import ResourceManager|termin\\.assets\\.resources" --glob '*.py' --glob '!termin-app/tests/**' --glob '!docs/**'
rg -n "from termin\\.assets\\.project_file_watcher|termin\\.assets\\.project_file_watcher" --glob '*.py' --glob '!termin-app/tests/**' --glob '!docs/**'
```

Expected important hits before the cleanup:

- `termin-modules/python/termin_modules/module_context.py`;
- `termin-app/termin/shader_runtime.py`;
- `termin-app/termin/scene_animation_repair.py`;
- `termin-app/termin/mcp/python_executor.py`;
- editor/editor_core/editor_tcgui imports of `termin.assets.resources`;
- editor file processors importing `termin.assets.project_file_watcher`.

If the audit finds new non-editor users of `termin.assets.*`, migrate them in
this same pass or document a blocker before closing the goal.

### 2. Remove Non-Editor `termin.assets.resources` Dependencies

Migrate `termin-modules/python/termin_modules/module_context.py` first.

Current problem:

- `_unregister_app_resource_classes()` imports
  `termin.assets.resources.ResourceManager`;
- this makes module hot-reload cleanup depend on the app asset namespace.

Preferred shape:

- fetch the active process manager through `termin_assets.get_resource_manager()`;
- if no manager is configured, log and return;
- operate only when the manager exposes `component_registry` and
  `frame_pass_registry`;
- log failures explicitly, preserving current cleanup behavior.

Do not instantiate `DefaultResourceManager` as a side effect here. Module
cleanup should use the active composition root, not create a new global manager.

Then migrate runtime-ish app helpers:

- `termin-app/termin/shader_runtime.py`: `_glsl_fallback_loader()` should use
  `termin_assets.get_resource_manager()` first. If no manager is configured,
  log an error and return `False`. Avoid importing `termin.assets.resources`.
- `termin-app/termin/scene_animation_repair.py`: remove the fallback import of
  `termin.assets.resources.ResourceManager`. The function already accepts an
  injected manager and already tries `termin_assets.get_resource_manager()`.
  If neither exists, log and return `0`.
- `termin-app/termin/mcp/python_executor.py`: this is editor tooling, so it may
  use the editor resource manager after the editor namespace exists. Do not
  leave it on `termin.assets.resources`.

Add or update tests around these behaviors:

- no import of `termin_modules.module_context` should require `termin-app`
  asset namespace;
- shader fallback with no configured manager logs/returns `False`;
- scene animation repair with no configured manager returns `0` without app
  import;
- MCP console still exposes `rm` / `resource_manager` when editor manager is
  configured.

### 3. Introduce An Editor Resource Manager Namespace

Create a clear editor-facing namespace before removing the old app asset path.

Recommended module:

- `termin-app/termin/editor_core/resource_manager.py`

Recommended API:

```python
from termin.default_assets.resource_manager import DefaultResourceManager

EditorResourceManager = DefaultResourceManager
ResourceManager = EditorResourceManager

def configure_editor_resource_manager_factory() -> None:
    from termin.bootstrap import configure_resource_manager_factory

    configure_resource_manager_factory(EditorResourceManager.instance)
```

Rationale:

- there is no remaining app-specific `ResourceManager` behavior after
  `UnknownMaterial` moved below app;
- `DefaultResourceManager` already owns default components/frame passes through
  `DefaultComponentsMixin`;
- if future editor-only additions are needed, this module is the right
  composition point.

Update editor imports from `termin.assets.resources` to this editor namespace:

- `termin-app/termin/editor_tcgui/run_editor.py`;
- `termin-app/termin/editor_tcgui/editor_window.py`;
- `termin-app/termin/editor_tcgui/pipeline_editor_window.py`;
- `termin-app/termin/editor_tcgui/rendering_controller.py`;
- `termin-app/termin/editor_tcgui/widgets/field_widgets.py`;
- `termin-app/termin/editor_tcgui/dialogs/resource_manager_viewer.py`;
- `termin-app/termin/editor_tcgui/dialogs/scene_inspector.py`;
- `termin-app/termin/editor_core/default_preloaders.py`;
- `termin-app/termin/editor_core/resource_loader.py`;
- `termin-app/termin/editor_core/entity_operations.py`;
- `termin-app/termin/editor_core/project_operations.py`;
- `termin-app/termin/editor_core/prefab_*`;
- `termin-app/termin/editor_core/rendering_model.py`;
- `termin-app/termin/editor_core/editor_camera.py`;
- `termin-app/termin/editor_core/pipeline_operations.py`;
- `termin-app/termin/mcp/python_executor.py`.

Tests that still need a full editor resource manager should import from
`termin.editor_core.resource_manager` after this step.

### 4. Collapse Or Remove `termin.assets.resources`

After editor imports move, shrink the old path aggressively.

Preferred end state:

- delete `termin-app/termin/assets/resources/_manager.py`;
- delete `termin-app/termin/assets/resources/_components.py`;
- delete `termin-app/termin/assets/resources/_builtins.py`;
- either delete `termin-app/termin/assets/resources/__init__.py` entirely, or
  keep it as a short temporary shim that imports from
  `termin.editor_core.resource_manager`.

Use the more aggressive deletion if all source and test imports are migrated.
If a short shim is kept for one pass, it must be documented as deprecated and
must not contain implementation logic.

Add/update import-side-effect coverage:

- importing `termin.default_assets.resource_manager` must not import
  `termin-app`;
- importing editor resource manager must not create a manager instance;
- removed implementation submodules under `termin.assets.resources._*` should
  raise `ModuleNotFoundError`.

### 5. Move `ProjectFileWatcher` App Policy Out Of `termin.assets`

Create an editor namespace for the app ignored-root watcher policy.

Recommended module:

- `termin-app/termin/editor_core/project_file_watcher.py`

Move the wrapper currently in
`termin-app/termin/assets/project_file_watcher.py`:

- keep using `termin_assets.project_file_watcher.ProjectFileWatcher`;
- keep `_termin_app_ignored_roots()` wired to
  `termin.project.ignored_paths.project_ignored_roots`;
- export `ProjectFileWatcher`, `FilePreLoader`, `PreLoadResult`, and
  `DEBOUNCE_DELAY_S` if editor processors still need those names.

Update imports in:

- editor file processors below `termin-app/termin/editor_core/file_processors`;
- `termin-app/termin/editor_tcgui/editor_window.py`;
- `termin-app/termin/editor_tcgui/glb_inspector.py`;
- `termin-app/tests/test_project_file_watcher.py`.

Then delete `termin-app/termin/assets/project_file_watcher.py` unless a
temporary shim is explicitly required. Prefer no shim during active migration.

### 6. Delete Or Empty `termin-app/termin/assets`

After `resources` and `project_file_watcher` are gone:

- remove `termin-app/termin/assets/README.md` or move useful architecture text
  into `termin-assets/README.md` / `termin-default-assets/docs/index.md`;
- remove `termin-app/termin/assets/__init__.py`;
- remove any now-empty `termin-app/termin/assets` directories.

Ignored `__pycache__` directories may need manual cleanup to keep import audits
honest:

```bash
find termin-app/termin/assets -type d -name __pycache__ -print
```

Remove only ignored/generated directories after checking they are not tracked.

### 7. Update Documentation

Update living docs, not only this plan:

- `termin-assets/README.md`: remove stale wording that concrete asset
  implementations still live in `termin-app`;
- `termin-default-assets/docs/index.md`: describe `DefaultResourceManager` as
  the canonical standard SDK resource manager and remove references to
  app-owned `AppResourceManager` if the shim is deleted;
- `docs/plans/2026-05-13-plugin-asset-system.md`: add a final status note that
  `termin.assets.resources` and `termin.assets.project_file_watcher` were
  removed or reduced to compatibility shims;
- `docs/plans/index.md`: keep this plan listed.

If editor resource manager remains as a named alias, document it in a small
editor-facing doc or module docstring as composition policy, not asset runtime.

### 8. Update Kanboard #40

Add a Kanboard comment to task `#40` with:

- files/namespaces removed;
- whether `termin.assets` was deleted or left as a deprecated shim;
- verification commands and results;
- any remaining explicitly accepted editor-only asset references.

Do not close #40 unless the final audit shows no non-editor `termin.assets.*`
imports and the only remaining app references are deliberate editor naming or
no references at all.

## Verification Gate

Run these checks before declaring the goal complete:

```bash
git diff --check
PYTHONPATH=termin-build-tools .venv/bin/python -m termin_build.package_manifest --check
./run-tests-python.sh \
  termin-assets/tests/test_asset_contracts.py \
  termin-default-assets/tests/test_default_resource_manager.py \
  termin-app/tests/test_import_side_effects.py \
  termin-app/tests/asset_plugin_test.py \
  termin-app/tests/test_project_file_watcher.py \
  termin-app/tests/test_editor_builtin_resources.py \
  termin-app/tests/test_scene_animation_repair.py
```

Also run focused import audits:

```bash
rg -n "termin\\.assets\\." --glob '*.py' --glob '!docs/**'
.venv/bin/python -c 'from termin.default_assets.resource_manager import DefaultResourceManager; print(DefaultResourceManager.__name__)'
.venv/bin/python -c 'from termin.editor_core.resource_manager import ResourceManager; print(ResourceManager.__name__)'
```

If the code changes touch package metadata, native bindings, setup helpers, or
test environment behavior, also run:

```bash
./build-sdk.sh --no-wheels
./setup-test-venv.sh --force
```

Full-suite target when time is acceptable:

```bash
./run-tests.sh
```

## Completion Criteria

The goal is complete when all of these are true:

- `rg -n "termin\\.assets\\." --glob '*.py' --glob '!docs/**'` has no
  non-editor/runtime hits; ideally it has no hits at all;
- `termin-modules` no longer imports app asset namespaces;
- `termin-app/termin/assets` has no implementation source files, or the whole
  directory is removed;
- `DefaultResourceManager` remains the canonical standard SDK manager;
- editor startup still explicitly configures the process resource-manager
  factory;
- listed verification gates pass;
- docs and Kanboard #40 are updated.

## Rollback Notes

If editor startup breaks after removing `termin.assets.resources`, do not bring
back the old implementation. Restore only a minimal temporary shim:

```python
from termin.editor_core.resource_manager import (
    ResourceManager,
    configure_editor_resource_manager_factory as configure_app_resource_manager_factory,
)
```

Then keep migrating callers to the editor namespace and delete the shim before
closing #40.
