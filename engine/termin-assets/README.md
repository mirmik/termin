# termin-assets

Shared asset-system contracts for Termin.

This package provides the neutral asset infrastructure shared by editor, player,
build tooling, and domain asset plugins. Standard SDK asset adapters live in
`termin-default-assets` or dedicated domain packages; `termin-app` should only
compose editor behavior.

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
their own ignored-root policy; the Termin editor keeps its project-settings
behavior through `termin.editor_core.project_file_watcher`.
