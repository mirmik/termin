# termin-mesh / tmesh

`termin-mesh` содержит canonical mesh/resource data layer и Python-пакет
`tmesh`. Стандартная asset integration для standalone mesh files живет в
`termin-default-assets`, чтобы mesh domain package не зависел от
`termin-assets`.

Связанные документы:

- [Module Map](../../../docs/modules.md#termin-mesh--tmesh)
- [termin-base](../../../core/termin-base/docs/index.md)

## Основные области

- C/C++ headers в `include/tgfx/` для `tc_mesh`, `tc_texture` и resource registry primitives.
- Реализация resource containers в `src/resources/`.
- Python bindings в `python/bindings/`.
- Python пакет `tmesh` в `python/tmesh/`.
- Python package `termin.mesh` for mesh runtime handles and scene mesh
  components. Канонические `MeshAsset`, `MeshSpec`, OBJ/STL loaders и mesh
  import/runtime plugins находятся в `termin.default_assets.mesh`.
- Tests в `tests/`.

## Публичный API

Python:

```python
import tmesh
from termin.geombase import Ray3, Vec3
from termin.default_assets.mesh.asset import MeshAsset
from termin.default_assets.mesh.asset_plugin import register_mesh_import_plugin

hit = mesh.raycast(
    Ray3(Vec3(0.25, 0.25, 1.0), Vec3.down()),
    min_distance=0.0,
    max_distance=100.0,
)
if hit is not None:
    print(hit.distance, hit.position, hit.normal)
```

`TcMesh.raycast(ray, min_distance=0.0, max_distance=1_000_000.0)` принимает
канонический `Ray3` и возвращает read-only `TcMeshRayHit` либо `None`. Поля
результата: `distance`, `position`, `normal`, `barycentric`,
`triangle_index` и `indices`; геометрические поля представлены `Vec3`.
Диапазон расстояний замкнутый и может включать отрицательные значения.
На packed-float границе его нижняя и верхняя границы округляются внутрь,
поэтому возвращённый hit никогда не выходит за исходный double-интервал;
интервал без представимых float-расстояний возвращает `None`.

В отличие от `RayTriangleHit.ray_parameter`, `TcMeshRayHit.distance` — это
знаковое метрическое расстояние в локальных координатах mesh вдоль
нормализованного направления. Модуль `ray.direction` не влияет на результат:
для ненормализованного направления позиция равна
`ray.origin + ray.direction.try_normalized() * hit.distance`, а не
`ray.point_at(hit.distance)`. Нефинитные, вырожденные и не представимые в
packed float boundary лучи или диапазоны отклоняются с `None`.

Прежняя плоская форма
`raycast(origin_tuple, direction_tuple, t_min, t_max)` удалена. Миграция
выполняется явно: координаты собираются в `Vec3`, пара значений — в `Ray3`, а
границы передаются как `min_distance` и `max_distance`.

C/C++ API публикуется через installed headers из `include/`.

`tc_mesh` и `tc_texture` считаются canonical engine resources. Renderer/device-specific upload и handle adapters должны оставаться отдельным слоем поверх этих типов.

Compatibility status:
- Domain compatibility re-exports `termin.mesh.asset`,
  `termin.mesh.mesh_asset`, `termin.mesh.asset_plugin`,
  `termin.mesh.mesh_plugin`, `termin.mesh.mesh_spec`,
  `termin.mesh.obj_loader`, and `termin.mesh.stl_loader` were removed. Use
  `termin.default_assets.mesh.*` directly.
- App compatibility modules `termin.assets.mesh_asset`,
  `termin.assets.mesh_plugin`, `termin.loaders.mesh_spec`,
  `termin.loaders.obj_loader`, and `termin.loaders.stl_loader` were removed on
  2026-06-18/2026-06-19. Use
  `termin.default_assets.mesh.mesh_spec`,
  `termin.default_assets.mesh.asset_plugin`,
  `termin.default_assets.mesh.obj_loader`, and
  `termin.default_assets.mesh.stl_loader` directly.
