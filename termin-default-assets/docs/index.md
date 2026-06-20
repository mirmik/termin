# termin-default-assets

Default asset adapters for Termin SDK.

This package owns the standard `termin-assets` integrations for domain data
packages. Domain packages such as `tmesh` should remain usable without the
project asset runtime.

Runtime manager boundary:

- `termin_assets.AssetRuntimeManager` owns only neutral plugin dispatch,
  UUID lookup, runtime registry attachment and external asset catalog mechanics.
- `termin.default_assets.resource_manager.DefaultResourceManager` is the
  canonical runtime manager for the standard Termin SDK asset set.
- `termin.default_assets.resource_accessors.DefaultResourceAccessorsMixin` and
  `termin.default_assets.handle_accessors.HandleAccessors` own default handle
  selector access for standard kinds such as `tc_mesh`, `texture_handle`,
  `voxel_grid_handle`, and `navmesh_handle`.
- `termin.materials.UnknownMaterial` owns the standard missing-material visual
  fallback used by editor and runtime resource managers.
- `termin.assets.resources.AppResourceManager` in `termin-app` is an
  editor/app extension over `DefaultResourceManagerBase`. Runtime/player code
  should use `DefaultResourceManager` or the `termin_assets.get_resource_manager()`
  process factory instead of importing this app namespace.
- Default component/frame-pass catalogs live below the app layer:
  `CameraController`, render component/pass types and `MaterialPass` are owned
  by `termin-components-render`, `UIComponent` is owned by
  `termin-components-ui`, `UIWidgetPass`, `ImmediateDepthPass`, and
  `UnifiedGizmoPass` are owned by `termin-render-passes`, and
  `TeleportComponent` is owned by `termin-collision`. `termin-app` currently
  has no component/frame-pass builtin additions.

Current adapters:

- `termin.default_assets.mesh`: `MeshAsset`, mesh import/runtime plugins,
  mesh import specs and OBJ/STL loaders.
- `termin.default_assets.navmesh`: `NavMeshAsset`, navmesh import/runtime
  plugins, and `NavMeshHandle` as a compatibility alias for `TcNavMesh`.
- `termin.default_assets.voxels`: `VoxelGridAsset`, voxel-grid import/runtime
  plugins.
- `termin.default_assets.audio`: `AudioClipAsset`, `AudioClipHandle`,
  audio-clip import/runtime plugins.
- `termin.default_assets.render`: texture, GLSL, material, shader, pipeline
  and scene-pipeline asset adapters/plugins plus render asset helper modules.
- `termin.default_assets.ui`: `UIAsset`, `UIHandle`, and UI import/runtime
  plugins for `.uiscript` layouts backed by `tcgui`.

Compatibility paths:

- `termin.default_assets.prefab`: compatibility re-exports for prefab classes
  that now live in `termin.prefab`.
