# termin-prefab

`termin-prefab` owns Termin's prefab runtime and `.prefab` asset integration.

The package contains:

- `termin.prefab.asset.PrefabAsset` for serialized entity hierarchy documents.
- `termin.prefab.asset_plugin` import/runtime plugins for asset discovery and hot reload.
- native `PrefabDocument` v3 for strict source parsing, validation and capture.
- native `PrefabInstanceState` for serialized source-to-runtime identity on an
  instantiated root and its typed property override set.
- native `PrefabOverrideValue`, a strict versioned tagged tree over `tc_value`.
  It preserves scalar types, list/tuple identity, dictionaries, dense-array
  dtype/shape, registered inspect kinds and typed UUID resource references.
  Ordinary numeric lists are never guessed to be vectors or arrays.
- scene-owned live-instance queries backed by the scene's exact component-type
  index; no Python registry or wrapper retention is involved.
- `termin.prefab.property_path.PropertyPath` for prefab override paths.

Current boundary note: `Entity` is imported from `termin.scene`. Resource
reference capture in Python uses registered inspect-kind serializers. Native
application requires an explicit `PrefabOverrideResourceResolver`; UUID names
are diagnostic only and are never a lookup fallback. The application
`ResourceManager` still provides concrete editor-side lookup methods until
those facades move to a non-editor package.
