# Plugin Asset System Migration

## Context

`termin-app` currently owns too much of the asset pipeline:

- `termin.assets` lives under `termin-app`.
- `termin.loaders` lives under `termin-app`.
- `ProjectFileWatcher`, `FilePreLoader`, `PreLoadResult`, and concrete file processors live under `termin.editor_core`.
- `ResourceManager.register_file()` and `reload_file()` know every concrete `resource_type` through a long `if/elif` dispatch.
- Player, editor, project builder, and future build/publish tooling all need asset processing, but should not depend on editor/app modules.

The target direction is to move asset infrastructure out of `termin-app` and make concrete file/asset support pluggable.

## Goals

- Create a base `termin-assets` package that does not depend on `termin-app`.
- Move file watching, preloading, metadata/spec helpers, asset registries, and asset build-manifest primitives out of editor code.
- Make the asset hub/resource manager unaware of concrete file types such as material, shader, mesh, GLB, navmesh, audio, or UI.
- Put concrete asset plugins near the domain module that owns the actual runtime type.
- Let `termin-app` compose editor/player/runtime behavior by registering available asset plugins, not by implementing file processing.

## Non-Goals For The First Migration

- Do not remove all typed convenience APIs such as `get_mesh()` or `get_material()` in the first pass.
- Do not move all asset classes to their final domain modules in one PR.
- Do not solve Qt/tcgui editor orchestration duplication here.
- Do not make `termin-assets` independent of the engine ecosystem entirely. It should be independent of `termin-app`, not necessarily independent of `termin-base` or other runtime packages.

## Proposed Module Boundaries

### `termin-assets`

Base infrastructure:

- `Asset`
- `DataAsset`
- `AssetRegistry`
- `AssetHub` or core `ResourceManager`
- `AssetTypePlugin` protocol/base class
- `AssetTypeRegistry`
- `PreLoadResult`
- watcher/scanner primitives
- `.meta`/spec helpers
- plugin registration/discovery API
- build manifest data structures and generic scanner/writer pieces, if they remain format-agnostic

`termin-assets` should not import `termin-app`, `termin.editor`, or `termin.editor_core`.

Status 2026-05-27: `Identifiable`, `Asset`, `DataAsset`, `AssetRegistry`, and
`ResourceHandle` were moved into `termin-assets`. The old
`termin.assets.asset`, `termin.assets.data_asset`, `termin.assets.asset_registry`,
and `termin.assets.resource_handle` modules are now compatibility re-exports so
existing imports keep working during the migration. The
`termin.core.identifiable` submodule shim was removed on 2026-06-18; use
`termin_assets.identifiable` directly. `from termin.core import Identifiable`
still works through the package facade.

Status 2026-06-17: `FilePreLoader`, `ProjectFileWatcher`, and `PluginPreLoader`
were moved into `termin-assets`. The generic watcher now accepts an injected
ignored-root policy instead of importing project settings. `termin-app` keeps
the editor/project behavior through compatibility wrappers in
`termin.assets.project_file_watcher`. The unused `termin.assets.plugin_preloader`
shim was removed on 2026-06-18; use `termin_assets.plugin_preloader` directly.

Status 2026-06-17: `VoxelGridAsset` and voxel-grid asset plugins were moved to
`termin-voxels` as `termin.voxels.asset` and `termin.voxels.asset_plugin`.
`termin-app` now keeps `termin.assets.voxel_grid_asset` as a compatibility
re-export. The unused `termin.assets.voxel_grid_plugin` shim was removed on
2026-06-18; use `termin.default_assets.voxels.asset_plugin` directly. Default
registration calls the default asset registration helpers, and the package also
exposes entry points for external plugin discovery.

Status 2026-06-17: `NavMeshAsset` and navmesh asset plugins were moved to
`termin-navmesh` as `termin.navmesh.asset` and
`termin.navmesh.asset_plugin`. `termin-app` now keeps
`termin.assets.navmesh_asset` as a compatibility re-export. The unused
`termin.assets.navmesh_plugin` shim was removed on 2026-06-18; use
`termin.default_assets.navmesh.asset_plugin` directly. Default registration
calls the default asset registration helpers, and the package exposes entry
points for external plugin discovery.

Status 2026-06-17: `NavMeshHandle` was moved to `termin-navmesh` as
`termin.navmesh.handle.NavMeshHandle`. The app path
`termin.assets.navmesh_handle` is now a compatibility re-export, and
`termin.assets.resources` explicitly configures the shared
`termin_assets.ResourceHandle` resource-manager factory instead of relying on
the old `termin.assets.resource_handle` import side effect.

Status 2026-06-17: `AnimationClipAsset` and `SkeletonAsset` were moved to
`termin-animation` and `termin-skeleton` as `termin.animation.asset` and
`termin.skeleton.asset`. The old app modules remain only compatibility
re-exports. These asset families still do not have standalone file plugins;
GLB import continues to create their child assets through the shared
`ResourceManager`.

Status 2026-06-17: audio runtime, audio clip assets, audio clip handles, audio
asset plugins, and audio scene components were moved to a new `termin-audio`
package. `termin-app` keeps old asset/handle paths as compatibility re-exports,
but the unused `termin.assets.audio_clip_plugin` shim was removed on
2026-06-18; use `termin.default_assets.audio.asset_plugin` directly.
`termin-app` no longer owns the `termin.audio` namespace. `termin-audio`
exposes import/runtime plugin entry points for `audio_clip`.

Status 2026-06-17: `MeshAsset`, standalone mesh import/runtime plugins, mesh
specs, and OBJ/STL loaders were moved out of `termin-app`.

Status 2026-06-18: the mesh asset adapter was moved again from `termin-mesh`
to `termin-default-assets` under `termin.default_assets.mesh`. `termin-mesh`
now stays focused on `tmesh`/mesh resource data and does not declare a
`termin-assets` dependency or mesh asset plugin entry points. The old app
module `termin.assets.mesh_asset` remains a compatibility re-export. Obsolete
app-path shims for `termin.assets.mesh_plugin`, `termin.loaders.mesh_spec`,
`termin.loaders.obj_loader`, and `termin.loaders.stl_loader` were removed on
2026-06-18; use `termin.default_assets.mesh.*` paths directly.
`termin-default-assets` exposes import/runtime plugin entry points for `mesh`;
GLB remains app-owned until the importer package boundary is decided.

Status 2026-06-18: the same default-adapter boundary was applied to navmesh,
voxel, audio, and render asset families. `NavMeshAsset`, `NavMeshHandle`,
navmesh plugins, `VoxelGridAsset`, voxel plugins, `AudioClipAsset`,
`AudioClipHandle`, audio plugins, and render texture/GLSL/material/shader/
pipeline/scene-pipeline asset helpers and plugins now live under
`termin.default_assets.{navmesh,voxels,audio,render}`. The domain packages
`termin-navmesh`, `termin-voxels`, `termin-audio`, and `termin-render` no
longer declare `termin-assets` dependencies or asset plugin entry points. Old
domain paths remain compatibility re-exports.

Status 2026-06-18: `UIAsset`, `UIHandle`, and UI import/runtime plugins moved
from `termin-app` to `termin-default-assets` under `termin.default_assets.ui`.
The `ui` entry points now come from `termin-default-assets`; old
`termin.assets.ui_asset`, `termin.assets.ui_handle`, and
`termin.assets.ui_plugin` modules remain compatibility re-exports.

Status 2026-06-18: prefab ownership moved from `termin-app`/the
default-adapter layer to a dedicated `termin-prefab` package. `termin.prefab`
now owns
`PrefabAsset`, prefab import/runtime plugins, `PrefabInstanceMarker`,
`PrefabRegistry`, and `PropertyPath`. `termin.default_assets.prefab`,
`termin.assets.prefab_asset`, and `termin.assets.prefab_plugin` are
compatibility re-exports. The unused old `termin.visualization.core` prefab
modules were removed on 2026-06-18; use `termin.prefab.*` directly.
`PrefabAsset` deserializes entities through `termin.scene.Entity`, and
`PrefabInstanceMarker` depends on `termin.scene.python_component` directly.
Prefab resource lookups use the process resource-manager factory from
`termin-assets` instead of importing app resources directly. The remaining
app-owned boundary is the concrete typed lookup surface still implemented by
the app `ResourceManager`.

Status 2026-06-17: default asset plugin composition moved from
`termin.assets.default_plugins` to `termin_assets.default_plugins`.
`termin-app` now declares its remaining app-owned asset plugins through
`termin.asset_import_plugins` and `termin.asset_runtime_plugins` entry points,
and the old app module was removed on 2026-06-18. This removes the app as the
central registry hub for already-extracted domain plugins; the remaining
technical debt is the GLB/importer ownership and app facade boundaries.

Status 2026-06-17: the shared runtime-management core moved to
`termin_assets.resource_manager.AssetRuntimeManager`. It owns the UUID index,
asset plugin registry, external asset catalog, generic runtime registry
dispatch, and `register_file`/`reload_file`. The app `ResourceManager` now
inherits this core and remains the domain/application facade for typed
registries, builtins, render/material/pipeline/prefab/UI/GLB accessors,
component/frame-pass registration, and legacy import paths.

Status 2026-06-17: component class and frame-pass class registries moved out of
the app resource manager into domain packages. `termin.scene.component_registry`
now owns `ComponentClassRegistry`, while
`termin.render_framework.frame_pass_registry` owns `FramePassRegistry`.
`termin.assets.resources.ResourceManager` keeps compatibility facade methods and
the old `components`/`frame_passes` dict views, but delegates registration,
lookup, listing, and scanning to the domain registries. The old app
`visualization.core.plugin_loader` compatibility re-export was removed on
2026-06-18 after internal imports moved to `termin.scene.class_scanner`.

Status 2026-06-18: texture and GLSL include asset classes/plugins first moved
to `termin-render`, then to `termin-default-assets` as
`termin.default_assets.render.texture_asset`,
`termin.default_assets.render.texture_plugin`,
`termin.default_assets.render.glsl_asset`, and
`termin.default_assets.render.glsl_plugin`. Texture import settings moved to
`termin.default_assets.render.texture_spec`.

Status 2026-06-18 cleanup: unused app compatibility modules
`termin.assets.texture_asset`, `termin.assets.texture_plugin`,
`termin.assets.glsl_asset`, `termin.assets.glsl_plugin`, and
`termin.loaders.texture_spec` were removed. Use the
`termin.default_assets.render.*` paths directly.

Status 2026-06-18: texture handles and simple texture helper/singleton wrappers
moved to `termin-render` as `termin.render.texture_handle` and
`termin.render.texture`. The old app modules `termin.visualization.render.texture`
and `termin.assets.texture_handle` were removed on 2026-06-18 after app C++
handle helpers were redirected to canonical Python modules. The Python API is
now canonical in `termin-render`; the underlying native `TextureHandle` binding
still comes from the transitional app-owned `termin._native.assets` module and
remains a C++ extraction follow-up.

Status 2026-06-18: material and shader asset runtime moved to `termin-render`,
then to `termin-default-assets`.
`MaterialAsset`, `ShaderAsset`, material/shader asset plugins, shader interface
comparison helpers, and shader-to-material/pipeline hot-reload dependency
helpers now live under `termin.default_assets.render.material_asset`,
`termin.default_assets.render.shader_asset`,
`termin.default_assets.render.material_plugin`,
`termin.default_assets.render.shader_plugin`,
`termin.default_assets.render.shader_interface`, and
`termin.default_assets.render.pipeline_dependencies`.

Status 2026-06-18 cleanup: unused app compatibility modules
`termin.assets.material_asset`, `termin.assets.material_plugin`,
`termin.assets.shader_asset`, `termin.assets.shader_plugin`,
`termin.assets.shader_interface`, and `termin.assets.pipeline_dependencies`
were removed. Use the `termin.default_assets.render.*` paths directly.

Status 2026-06-18: render pipeline asset runtime moved to `termin-render`,
then to `termin-default-assets`.
`PipelineAsset`, `ScenePipelineAsset`, their import/runtime plugins, and the
`pipeline`/`scene_pipeline` entry points now live under
`termin.default_assets.render.pipeline_asset`,
`termin.default_assets.render.scene_pipeline_asset`,
`termin.default_assets.render.pipeline_plugin`, and
`termin.default_assets.render.scene_pipeline_plugin`. The old
`termin.assets.pipeline_*`, `termin.assets.scene_pipeline_*`, and
`termin.render.*` modules remain compatibility re-exports. Remaining render
asset follow-ups: material file parse/save and pipeline pass-list
deserialization still use the app `ResourceManager` facade at runtime for
typed lookups, and live pipeline reload notifications still bridge through the
app `RenderingManager` when available.

### Domain Packages

Domain packages should own engine/domain data and remain usable without the
project asset runtime. Concrete default asset adapters should not force these
packages to depend on `termin-assets`.

- `termin-mesh`: `tmesh`, mesh resource containers and mesh bindings.
- `termin-render`: render runtime, render bindings, shader/material/pipeline domain logic.
- `termin-animation`: `AnimationClipAsset`; add `AnimationClipAssetPlugin` only
  when a standalone animation file pipeline exists.
- `termin-skeleton`: `SkeletonAsset`; add `SkeletonAssetPlugin` only when a
  standalone skeleton file pipeline exists.
- `termin-navmesh`: navmesh runtime/data.
- `termin-audio`: `AudioEngine`, `AudioClip`, audio scene components.
- `termin-gui` or a future UI package: UI runtime/data.

### Default Asset Packages

Default asset adapters live in `termin-default-assets`. It may depend on
`termin-assets` and on domain packages, but domain packages should not depend
back on it.

- `termin.default_assets.mesh`: `MeshAsset`, `MeshAssetPlugin`, `MeshSpec`,
  OBJ/STL loaders, and mesh import/runtime plugin entry points.
- `termin.default_assets.navmesh`: `NavMeshAsset`, `NavMeshHandle`, navmesh
  import/runtime plugin entry points.
- `termin.default_assets.voxels`: `VoxelGridAsset`, voxel-grid import/runtime
  plugin entry points.
- `termin.default_assets.audio`: `AudioClipAsset`, `AudioClipHandle`,
  audio-clip import/runtime plugin entry points.
- `termin.default_assets.render`: texture, GLSL, material, shader, pipeline,
  and scene-pipeline default asset adapters and plugin entry points.
- `termin.default_assets.ui`: `UIAsset`, `UIHandle`, and `.uiscript`
  import/runtime plugin entry points.
- `termin.prefab`: `PrefabAsset`, `.prefab` import/runtime plugin entry
  points, prefab instance markers, registry, and override path helpers.
- Future importer-style adapters should move here or to a dedicated importer
  package when they are not pure domain runtime.

### Importer Packages

Complex formats that produce several child asset types should not be forced into one low-level domain package.

Examples:

- `GLBAssetPlugin` can produce meshes, skeletons, animations, materials, textures.
- `FBXAssetPlugin` may do the same.

Good homes:

- `termin-importers`
- `termin-scene-assets`
- another explicit multi-domain importer package

Avoid putting GLB/FBX ownership into `termin-mesh` if they create skeletons/animations/materials too.

### `termin-app`

`termin-app` should be a composition layer:

- start editor/player/launcher;
- initialize runtime/editor services;
- call registration functions for default plugins;
- provide UI/editor orchestration.

It should not implement concrete file processors.

## Plugin Contract Sketch

The asset hub should dispatch by registered plugins instead of hard-coded resource types.

```python
class AssetTypePlugin:
    type_id: str
    extensions: set[str]
    priority: int

    def preload(self, path: str) -> PreLoadResult | None:
        ...

    def register(self, context: AssetContext, result: PreLoadResult) -> None:
        ...

    def reload(self, context: AssetContext, result: PreLoadResult) -> None:
        ...

    def remove(self, context: AssetContext, path: str) -> None:
        ...
```

The core hub should know only:

- plugin registry;
- UUID index;
- generic name/type registries;
- lifecycle dispatch;
- diagnostics/logging.

It should not contain `if result.resource_type == "material"` style dispatch.

## Current Hot Spots

### Hard-Coded Dispatch

Status 2026-05-27: central `register_file()` / `reload_file()` dispatch now goes through
`AssetTypeRegistry` runtime plugins. The old per-type `_register_*_file` /
`_reload_*_file` methods were removed from `ResourceManager`.

Status 2026-05-27: `ResourceManager` has the first public runtime asset API on
top of typed registries: `get_runtime_asset(type_id, name)`,
`get_runtime_asset_by_uuid(type_id, uuid)`, and
`register_runtime_asset(type_id, name, asset, ...)`, plus
`get_or_create_runtime_asset(type_id, name, ...)` for create paths. The `mesh`,
`texture`, `audio_clip`, `navmesh`, `voxel_grid`, `ui`, `glsl`, `pipeline`, and
`scene_pipeline` runtime plugins use this API instead of direct access to
`_assets_by_uuid` and their private typed registries.

The migrated runtime/import plugins currently cover:

- `material`
- `shader`
- `texture`
- `mesh`
- `voxel_grid`
- `navmesh`
- `glb`
- `glsl`
- `prefab`
- `audio_clip`
- `ui`
- `pipeline`
- `scene_pipeline`

Remaining work is no longer central dispatch replacement. The next pressure points are
moving GLB/importer plugins out of `termin-app`, reducing direct plugin access to
`ResourceManager` private registries, and deciding the long-term home for render
asset dependency refresh.

### Typed ResourceManager API

`ResourceManager` also exposes many typed methods:

- `get_material()`
- `get_mesh()`
- `get_shader()`
- `get_or_create_mesh_asset()`
- `register_texture_asset()`
- and similar methods for other asset families.

These can remain as compatibility/domain convenience facades during the first migration. They should eventually delegate to typed registries contributed by plugins or domain-specific accessor mixins.

### GLB Child Assets

GLB currently creates child assets for meshes, skeletons, and animations. The plugin API must support registering additional child assets into the shared UUID/name index.

This should be designed intentionally; otherwise GLB will keep forcing type-specific knowledge back into the central manager.

### Shader/Material/Pipeline Dependencies

Shader reload can refresh materials and then reload dependent pipelines. This dependency logic should not stay in the central asset hub.

Possible homes:

- `ShaderAssetPlugin`
- render asset dependency graph service
- render-domain asset registry extension

## Migration Plan

### Phase 1: Prepare Names And Contracts

- Add `termin-assets` package.
- Move or introduce:
  - `PreLoadResult`
  - `FilePreLoader` or replacement plugin base
  - `AssetTypePlugin`
  - `AssetTypeRegistry`
  - generic watcher/scanner code
- Update imports so editor/player/project builder no longer import asset file processing from `termin.editor_core`.

### Phase 2: Replace Resource Type Dispatch

- Register existing asset type handlers as plugins.
- Replace `_registration.py` `if/elif` dispatch with:
  - lookup plugin by `result.resource_type`, or
  - lookup plugin by extension before preload.
- Keep existing typed APIs in `ResourceManager`.
- Keep behavior equivalent for current editor/player asset scanning.

### Phase 3: Move Concrete Plugins To Default Adapter Modules

Move plugins gradually:

- Mesh support to `termin-default-assets`.
- Render asset support to `termin-default-assets` or a dedicated render asset
  adapter package.
- Animation support to `termin-animation`.
- Skeleton support to `termin-skeleton`.
- Navmesh support to `termin-default-assets`.
- UI support to `termin-default-assets`.
- GLB/FBX importers to `termin-importers` or equivalent.

Each adapter package should expose asset plugin entry points:

```toml
termin.asset_import_plugins:
  mesh = termin.default_assets.mesh.asset_plugin:create_import_plugin
termin.asset_runtime_plugins:
  mesh = termin.default_assets.mesh.asset_plugin:create_runtime_plugin
```

### Phase 4: Composition Layer

Central composition lives in `termin_assets.default_plugins` and should remain
entry-point driven:

```python
def register_default_runtime_asset_plugins(registry: AssetTypeRegistry) -> None:
    register_runtime_plugins_from_entry_points(registry)
    register_combined_plugins_from_entry_points(registry)
```

`termin-app` can call this helper, but should not own composition or domain
plugin discovery. Its current app-owned entry points are transitional until the
corresponding concrete assets/plugins move to domain packages.

### Phase 5: Clean Up Typed Manager Surface

After plugin dispatch works:

- Decide which typed `ResourceManager` methods remain as stable domain accessors.
- Move domain-specific accessors into domain packages or adapter mixins.
- Move builtin resource registration and component/frame-pass default catalogs
  out of the asset runtime facade.
- Prefer generic APIs for new code:
  - `get_asset(type_id, name)`
  - `get_asset_by_uuid(uuid)`
  - `get_data(type_id, name)`
  - `list_assets(type_id)`

## Install Order

`termin-assets` should be installed before packages that contribute plugins.

Expected dependency direction:

```text
termin-assets
  ↑
termin-mesh
termin-render
termin-animation
termin-skeleton
termin-navmesh
termin-importers
  ↑
termin-app
```

`termin-app` should come after all runtime/domain packages because it composes them.

## Risks

- Namespace packaging: `termin.*` packages already share a namespace. Moving modules between packages needs careful `setup.py`/package exclusion updates.
- Build order: plugin packages must be installed after `termin-assets` and before `termin-app`.
- GLB/FBX ownership: multi-domain importers need a deliberate home.
- Hot reload behavior: shader/material/pipeline dependency refresh must remain intact.
- Existing code may rely on typed `ResourceManager` methods; do not remove them in the first pass.
- Tests may be hard to run on Windows until native DLL environment setup is reliable.

## First Useful Milestone

The first useful milestone is not a full module split. It is:

- asset plugin registry exists;
- current concrete file processors are registered as plugins;
- central `register_file()`/`reload_file()` no longer know concrete resource types;
- editor, player, and project builder use the same plugin registry;
- no imports from player/build tooling into `termin.editor_core.file_processors`.

This milestone gives the architectural benefit without forcing every asset class into its final package immediately.
