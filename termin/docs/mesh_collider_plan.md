# План добавления MeshCollider

## 1. Цели и рамки
- Добавить `MeshCollider` в C++ collision stack (`Collider`, `CollisionWorld`, bindings, `ColliderComponent`).
- В первой итерации поддержать только **статический** triangle mesh (без динамического пересчёта topology).
- Для динамических тел оставить `Box/Sphere/Capsule/ConvexHull` (если нужен) как отдельный этап.

## 2. Архитектурное решение
- Добавить новый тип `ColliderType::Mesh` в `cpp/termin/colliders/collider.hpp`.
- Реализовать `MeshCollider` как отдельный класс `ColliderPrimitive`-наследник:
  - immutable геометрия: вершины, индексы, локальный BVH по треугольникам;
  - transform берётся из существующего `ColliderPrimitive::transform`.
- Не добавлять pair-specific формулы для `Mesh-vs-*` в стиле текущего double-dispatch.
- Вынести mesh narrow-phase в отдельный модуль:
  - `mesh_query.hpp/.cpp`: raycast, closest-point, overlap query по triangle BVH;
  - `mesh_contacts.hpp/.cpp`: генерация контактов `primitive-vs-mesh`.

## 3. Этапы внедрения

### Этап A. API и типы
- Обновить `ColliderType`, forward declarations, virtual dispatch методы.
- Добавить `MeshCollider` в `colliders.hpp` и nanobind (`_colliders_native`).
- Обновить Python re-export (`termin/colliders/__init__.py`).
- Обновить `ColliderComponent`:
  - новый `collider_type = "Mesh"`;
  - поле `mesh_asset` (или handle/id) для выбора меша;
  - корректная регистрация в inspect choices.

### Этап B. Геометрия и ускоряющая структура
- В `MeshCollider` хранить:
  - `std::vector<Vec3> vertices_local`;
  - `std::vector<uint32_t> indices` (треугольники);
  - локальный BVH/AABB tree по треугольникам.
- Построение BVH один раз при создании/смене меша.
- `aabb()` коллайдера: трансформировать bounds локального BVH в world-space AABB.

### Этап C. Запросы к Mesh
- Реализовать:
  - `closest_to_ray` через ray-triangle traversal по BVH;
  - closest point from primitive to triangle set (с BVH pruning);
  - intersection primitive-vs-triangle для Box/Sphere/Capsule.
- Контактные данные возвращать в формате `ColliderHit`/`ContactManifold` с текущим знаком penetration (negative == penetrating).

### Этап D. Интеграция в CollisionWorld
- В `detect_contacts()` добавить обработку пар `Mesh-vs-*` и `*-vs-Mesh`.
- Для первой версии:
  - `Sphere-vs-Mesh`: полноценный и стабильный;
  - `Capsule-vs-Mesh`: через segment-triangle distance + penetration;
  - `Box-vs-Mesh`: SAT/closest-feature с ограничением числа контактных точек.
- `Mesh-vs-Mesh` не включать в первую итерацию (отдельный milestone).

### Этап E. AttachedCollider/UnionCollider
- Добавить `MeshCollider` во все `dynamic_cast` ветки `AttachedCollider`.
- Проверить `UnionCollider` на корректный выбор минимальной дистанции и нормали для mix-пар с mesh.

### Этап F. Тесты
- Unit tests (`cpp/tests/tests_colliders.cpp`):
  - raycast hit/miss по mesh;
  - sphere/box/capsule vs mesh (separated, touching, penetrating);
  - инвариант направления normal (A -> B).
- Integration (`cpp/tests/tests_collision.cpp`):
  - `CollisionWorld` пары с Mesh;
  - корректный `point_count`, знак penetration, стабильность при update_pose.
- Python smoke tests для bindings и `ColliderComponent`.

## 4. Алгоритмы (минимально необходимые)
- Triangle BVH (SAH или median-split; для начала median-split достаточно).
- Ray-triangle intersection (Moller-Trumbore).
- Closest point point/segment/triangle.
- Primitive-triangle overlap:
  - sphere-triangle;
  - capsule-triangle (segment-triangle distance);
  - box-triangle SAT (Akenine-Moller style).
- Контактный manifold builder с лимитом `ContactManifold::MAX_POINTS`.

## 5. Критерии готовности (Definition of Done)
- `MeshCollider` доступен в C++/Python API и выбирается в `ColliderComponent`.
- `CollisionWorld` корректно детектирует `Sphere/Capsule/Box vs Mesh`.
- Raycast по `MeshCollider` работает и сортируется по distance.
- Все новые тесты зелёные локально и в CI.
- Нет silent-fallback логики и нет проглатывания исключений/ошибок без `error`-лога.

## 6. Риски и порядок приоритета
- Главный риск: нестабильность контактных нормалей на острых рёбрах и тонких треугольниках.
- Второй риск: производительность без triangle BVH и без агрессивного pruning.
- Приоритет реализации:
  1. `Sphere-vs-Mesh`
  2. `Capsule-vs-Mesh`
  3. `Box-vs-Mesh`
  4. `Mesh-vs-Mesh` (отдельный этап)
