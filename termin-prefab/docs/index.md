# termin-prefab

`termin-prefab` owns Termin's prefab runtime and `.prefab` asset integration.

The package contains:

- `termin.prefab.asset.PrefabAsset` for serialized entity hierarchy documents.
- `termin.prefab.asset_plugin` import/runtime plugins for asset discovery and hot reload.
- `termin.prefab.instance_marker.PrefabInstanceMarker` for linking instances to their source prefab.
- `termin.prefab.registry.PrefabRegistry` for hot-reload instance lookup.
- `termin.prefab.property_path.PropertyPath` for prefab override paths.

Current boundary note: `Entity` is imported from `termin.scene`. Resource
reference resolution uses the process resource-manager factory from
`termin-assets`; the application `ResourceManager` still provides the concrete
typed lookup methods until those facades move to a non-editor package.
