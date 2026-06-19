# termin-navmesh

`termin-navmesh` содержит NavMesh Python bindings и navigation utilities.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-navmesh)
- [Algorithm notes](../python/termin/navmesh/ALGORITHM.md)

## Основные области

- Python package в `python/termin/navmesh`.
- Algorithm notes рядом с package-кодом.
- Packaging metadata в `setup.py` / `pyproject.toml`.

## Публичный API

Python package: `termin.navmesh` через пакет `termin-navmesh`.

Верхний импорт `import termin.navmesh` должен оставаться лёгким и не поднимать
native Recast/app цепочку. Данные и алгоритмы (`NavMesh`, `NavMeshConfig`,
`PolygonBuilder`) доступны через ленивые top-level экспорты, а native
Recast/Detour компоненты загружаются только при обращении к соответствующим
именам (`RecastNavMeshBuilderComponent`, `DetourPathfindingWorldComponent`,
`TcNavMesh` и т.п.).

## Asset integration

Navmesh asset ownership живет в `termin-default-assets`:

- `termin.default_assets.navmesh.asset.NavMeshAsset`
- `termin.default_assets.navmesh.handle.NavMeshHandle`
- `termin.default_assets.navmesh.asset_plugin.NavMeshImportPlugin`
- `termin.default_assets.navmesh.asset_plugin.NavMeshRuntimePlugin`

Compatibility status:
- `termin.navmesh.asset`, `termin.navmesh.asset_plugin`,
  `termin.navmesh.handle`, and `termin.navmesh.navmesh_asset` remain temporary
  domain compatibility re-exports during migration.
- App compatibility modules `termin.assets.navmesh_asset`,
  `termin.assets.navmesh_handle`, and `termin.assets.navmesh_plugin` were
  removed. Use `termin.default_assets.navmesh.*` directly.
