# termin-assets

Shared asset-system contracts for Termin.

This package provides the neutral asset infrastructure shared by editor, player,
build tooling, and domain asset plugins. Concrete asset implementations still
live in `termin-app` during the migration, but the base classes no longer do.

Core infrastructure:

- `Identifiable`
- `Asset`
- `DataAsset`
- `AssetRegistry`
- `ResourceHandle`
- `PreLoadResult`
- `AssetContext`
- `AssetTypeRegistry`
- `AssetCatalog`
- `FilePreLoader`
- `ProjectFileWatcher`
- `PluginPreLoader`

The plugin API separates two roles:

- runtime plugins register and reload already discovered assets;
- import plugins turn files into preload results for editor/watch/build flows.

A concrete plugin may temporarily implement both roles while an asset type is
being migrated, but the contracts keep the runtime surface independent from
editor-only import tooling.

`ProjectFileWatcher` is intentionally policy-neutral. Applications can inject
their own ignored-root policy; `termin-app` keeps its project-settings behavior
through a compatibility wrapper in `termin.assets.project_file_watcher`.
