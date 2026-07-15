# termin-prefab

`termin-prefab` owns Termin's prefab runtime and `.prefab` asset integration.

The package contains:

- `termin.prefab.asset.PrefabAsset` for serialized entity hierarchy documents.
- `termin.prefab.asset_plugin` import/runtime plugins for asset discovery and hot reload.
- native `PrefabDocument` v3 for strict source parsing, validation and capture.
- native `PrefabInstanceState` for serialized source-to-runtime identity on an
  instantiated root.
- scene-owned live-instance queries backed by the scene's exact component-type
  index; no Python registry or wrapper retention is involved.
- `termin.prefab.property_path.PropertyPath` for prefab override paths.

Current boundary note: `Entity` is imported from `termin.scene`. Resource
reference resolution uses the process resource-manager factory from
`termin-assets`; the application `ResourceManager` still provides the concrete
typed lookup methods until those facades move to a non-editor package.
