# termin-navmesh

`termin-navmesh` содержит NavMesh Python bindings и navigation utilities.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-navmesh)
- [Algorithm notes](../python/termin/navmesh/ALGORITHM.md)

## Основные области

- Python package в `python/termin/navmesh`.
- Native package ownership:
  - `termin_navmesh` - C registry for `TcNavMesh` assets.
  - `termin_navmesh_components` - Recast/Detour-backed scene components.
  - `termin.navmesh._navmesh_native` - Python bindings for the native
    components and `TcNavMesh`.
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

Native Recast/Detour ownership больше не находится в `termin-app`: app-side
код может подключать editor-specific визуализацию, но runtime/builder
components и `_navmesh_native` собираются здесь.

Нейтральный helper `termin.navmesh.ribbon_geometry.build_line_ribbon`
является публичной границей для построения debug-контуров. Navigation package
не зависит от `termin-components-voxels`; voxelizer integration направлена в
обратную сторону и объявляется самим `termin-components-voxels`.

## Asset integration

Navmesh asset ownership живет в `termin-default-assets`:

- `termin.default_assets.navmesh.asset.NavMeshAsset`
- `termin.default_assets.navmesh.asset_plugin.NavMeshImportPlugin`
- `termin.default_assets.navmesh.asset_plugin.NavMeshRuntimePlugin`

`TcNavMesh` is the canonical runtime identity. `NavMeshHandle` compatibility
imports are aliases for `TcNavMesh`, not separate wrappers.

Compatibility status:
- Domain compatibility re-exports `termin.navmesh.asset`,
  `termin.navmesh.asset_plugin`, `termin.navmesh.handle`, and
  `termin.navmesh.navmesh_asset` were removed. Use
  `termin.default_assets.navmesh.*` and `termin.navmesh.TcNavMesh` directly.
- App compatibility modules `termin.assets.navmesh_asset`,
  `termin.assets.navmesh_handle`, and `termin.assets.navmesh_plugin` were
  removed. Use `termin.default_assets.navmesh.*` directly.
