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
- checked native override clearing against the current `PrefabDocument`.
  Successful fields are restored before metadata is erased; failed batch
  entries remain present with structured diagnostics.
- native property reconciliation for existing instances. It audits mapped
  structure without mutating it, refreshes non-overridden source fields,
  reapplies and retains typed overrides, and advances the source revision only
  after a completely successful pass. `PrefabAsset` hot reload is a thin caller
  of this native transaction.
- `termin.prefab.property_path.PropertyPath` for prefab override paths.

Current boundary note: `Entity` is imported from `termin.scene`. Resource
reference capture in Python uses registered inspect-kind serializers. Native
callers applying a tagged resource `PrefabOverrideValue` supply an explicit
`PrefabOverrideResourceResolver`; the Python binding supplies a canonical
UUID-payload adapter and leaves actual resolution to the registered target
kind. Restoring a source value during clear uses the registered native handle
kind and rejects unresolved non-empty UUIDs;
UUID names are diagnostic only and are never a lookup fallback. The application
`ResourceManager` still provides concrete editor-side lookup methods until
those facades move to a non-editor package.

Property reconciliation is intentionally not full structural reconciliation.
Source additions/removals, owner/type/parent drift and missing runtime targets
are diagnosed deterministically and leave the previous revision in place;
entities and components are not created, deleted, reordered or reparented.
Local entities/components absent from the source mapping are unrelated local
structure and are preserved.
