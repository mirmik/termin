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
