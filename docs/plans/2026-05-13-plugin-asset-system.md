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
`termin.assets.resource_handle`, and `termin.core.identifiable` modules are now
compatibility re-exports so existing imports keep working during the migration.

Status 2026-06-17: `FilePreLoader`, `ProjectFileWatcher`, and `PluginPreLoader`
were moved into `termin-assets`. The generic watcher now accepts an injected
ignored-root policy instead of importing project settings. `termin-app` keeps
the editor/project behavior through compatibility wrappers in
`termin.assets.project_file_watcher` and `termin.assets.plugin_preloader`.

Status 2026-06-17: `VoxelGridAsset` and voxel-grid asset plugins were moved to
`termin-voxels` as `termin.voxels.asset` and `termin.voxels.asset_plugin`.
`termin-app` now keeps `termin.assets.voxel_grid_asset` and
`termin.assets.voxel_grid_plugin` only as compatibility re-exports. Default
registration calls the domain registration helpers from `termin-voxels`, and
the package also exposes entry points for external plugin discovery.

Status 2026-06-17: `NavMeshAsset` and navmesh asset plugins were moved to
`termin-navmesh` as `termin.navmesh.asset` and
`termin.navmesh.asset_plugin`. `termin-app` now keeps
`termin.assets.navmesh_asset` and `termin.assets.navmesh_plugin` only as
compatibility re-exports. Default registration calls the domain registration
helpers from `termin-navmesh`, and the package exposes entry points for
external plugin discovery.

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
package. `termin-app` now keeps the old `termin.assets.audio_clip_*` modules
only as compatibility re-exports and no longer owns the `termin.audio`
namespace. `termin-audio` exposes import/runtime plugin entry points for
`audio_clip`.

Status 2026-06-17: `MeshAsset`, standalone mesh import/runtime plugins, mesh
specs, and OBJ/STL loaders were moved to `termin-mesh` under `termin.mesh`.
The old app modules `termin.assets.mesh_asset`, `termin.assets.mesh_plugin`,
and `termin.loaders.{mesh_spec,obj_loader,stl_loader}` are compatibility
re-exports. `termin-mesh` exposes import/runtime plugin entry points for
`mesh`; GLB remains app-owned until the importer package boundary is decided.

Status 2026-06-17: default asset plugin composition moved from
`termin.assets.default_plugins` to `termin_assets.default_plugins`.
`termin-app` now declares its remaining app-owned asset plugins through
`termin.asset_import_plugins` and `termin.asset_runtime_plugins` entry points,
and the old app module is only a compatibility re-export. This removes the app
as the central registry hub for already-extracted domain plugins; the remaining
technical debt is the concrete render/UI/GLB/prefab plugin ownership itself.

### Domain Packages

Concrete plugins should live near the domain implementation:

- `termin-mesh`: `MeshAsset`, `MeshAssetPlugin`, mesh file loaders/specs for mesh-owned formats.
- `termin-render` or a render-facing package: `TextureAssetPlugin`, `ShaderAssetPlugin`, `MaterialAssetPlugin`, `PipelineAssetPlugin`, render pipeline asset support.
- `termin-animation`: `AnimationClipAsset`; add `AnimationClipAssetPlugin` only
  when a standalone animation file pipeline exists.
- `termin-skeleton`: `SkeletonAsset`; add `SkeletonAssetPlugin` only when a
  standalone skeleton file pipeline exists.
- `termin-navmesh`: `NavMeshAsset`, `NavMeshAssetPlugin`.
- `termin-audio`: `AudioClipAsset`, `AudioClipHandle`, `AudioClipAssetPlugin`,
  `AudioEngine`, `AudioClip`, audio scene components.
- `termin-gui` or a future UI package: `UIAsset`, `UIAssetPlugin`.

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
moving concrete plugins out of `termin-app`, reducing direct plugin access to
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

### Phase 3: Move Concrete Plugins To Domain Modules

Move plugins gradually:

- Mesh support to `termin-mesh`.
- Render asset support to `termin-render` or a dedicated render asset package.
- Animation support to `termin-animation`.
- Skeleton support to `termin-skeleton`.
- Navmesh support to `termin-navmesh`.
- UI support to `termin-gui` or future UI package.
- GLB/FBX importers to `termin-importers` or equivalent.

Each domain package should expose asset plugin entry points:

```toml
termin.asset_import_plugins:
  mesh = termin.mesh.asset_plugin:create_import_plugin
termin.asset_runtime_plugins:
  mesh = termin.mesh.asset_plugin:create_runtime_plugin
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
