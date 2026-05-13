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

### Domain Packages

Concrete plugins should live near the domain implementation:

- `termin-mesh`: `MeshAsset`, `MeshAssetPlugin`, mesh file loaders/specs for mesh-owned formats.
- `termin-render` or a render-facing package: `TextureAssetPlugin`, `ShaderAssetPlugin`, `MaterialAssetPlugin`, `PipelineAssetPlugin`, render pipeline asset support.
- `termin-animation`: `AnimationClipAsset`, `AnimationClipAssetPlugin`.
- `termin-skeleton`: `SkeletonAsset`, `SkeletonAssetPlugin`.
- `termin-navmesh`: `NavMeshAsset`, `NavMeshAssetPlugin`.
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

`termin-app/termin/assets/resources/_registration.py` currently has hard-coded dispatch for:

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

This is the main place to replace with plugin dispatch.

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

Each domain package should expose an explicit registration function:

```python
def register_mesh_asset_plugins(registry: AssetTypeRegistry) -> None:
    registry.register(MeshAssetPlugin())
```

### Phase 4: Composition Layer

Add a central composition helper outside `termin-app` if useful:

```python
def register_default_runtime_asset_plugins(registry: AssetTypeRegistry) -> None:
    register_mesh_asset_plugins(registry)
    register_render_asset_plugins(registry)
    register_animation_asset_plugins(registry)
    register_skeleton_asset_plugins(registry)
    register_navmesh_asset_plugins(registry)
    register_importer_asset_plugins(registry)
```

`termin-app` can call this helper, but should not own the concrete plugins.

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
