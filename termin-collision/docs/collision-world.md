# CollisionWorld

`CollisionWorld` — центральный объект для управления коллайдерами и обнаружения столкновений.

Namespace: `termin::collision`.

## Управление коллайдерами

```cpp
CollisionWorld world;

// Добавить/удалить
world.add(collider);
world.remove(collider);

// Обновить позицию одного коллайдера в BVH
world.update_pose(collider);

// Обновить все позиции (вызывать раз за кадр)
world.update_all();

// Проверки
world.contains(collider);
world.size();
```

CollisionWorld не владеет коллайдерами — хранит raw-указатели. Вызывающий код отвечает за время жизни.

## Детекция контактов

```cpp
std::vector<ContactPatch> patches = world.detect_contacts();
```

Поток:
1. **Broad-phase**: `BVH::query_all_pairs()` — все пары с пересекающимися AABB.
2. **Narrow-phase**: `Collider::closest_to_collider()` — точная проверка.
3. Для box-box: дополнительно Sutherland-Hodgman clipping создаёт кандидаты.
4. Общий reducer выбирает не более четырёх репрезентативных точек: самую глубокую, затем точки с максимальным пространственным покрытием.

## ContactPatch

```cpp
struct ContactPatch {
    Collider* collider_a;
    Collider* collider_b;
    Vec3 normal_world;                    // единичная нормаль от A к B
    std::vector<ContactCandidate> points;
};
```

`ContactPatch` содержит только геометрию. Ссылки на динамические тела, импульсы,
active-set и warm-start state принадлежат конкретному решателю.

## ContactCandidate

```cpp
struct ContactCandidate {
    Vec3 point_on_a_world;
    Vec3 point_on_b_world;
    double signed_gap;            // < 0 — проникновение
    ContactFeaturePair features;
};
```

Контракт знака и координат явный:

```cpp
dot(point_on_b_world - point_on_a_world, normal_world) == signed_gap
```

`reduce_contact_candidates()` не зависит от порядка входных кандидатов и
инвариантен к общему жёсткому преобразованию сцены. Максимальное число точек и
допуски задаются через `ContactPatchReductionConfig`.

Нормаль патча валидируется редуктором: она должна быть конечной и ненулевой.
Результат редукции имеет тип `std::optional`; `std::nullopt` означает ошибку
контракта, а не корректный пустой manifold. `CollisionWorld` не публикует такой
патч, пишет ошибку в лог и сохраняет структурированный
`CollisionDiagnosticCode::InvalidContactNormal` в `diagnostics()` до следующего
вызова `detect_contacts()`.

## Raycast

```cpp
// Все попадания, отсортированные по расстоянию
std::vector<collision::RayHit> hits = world.raycast(ray);

// Только ближайшее
collision::RayHit closest = world.raycast_closest(ray);
```

`collision::RayHit`:
- `collider` — указатель на коллайдер
- `point` — точка попадания
- `normal` — нормаль в точке попадания
- `distance` — расстояние от origin луча
- `hit()` — true если `collider != nullptr`

## AABB-запрос

```cpp
std::vector<Collider*> result = world.query_aabb(aabb);
```

Возвращает все коллайдеры, чьи AABB пересекаются с заданным.

## BVH (Bounding Volume Hierarchy)

Динамическое дерево для broad-phase.

Характеристики:
- **Fattened AABB**: margin 0.1 уменьшает перестройки при малых движениях
- **SAH (Surface Area Heuristic)**: оптимальный выбор sibling при вставке
- **AVL-балансировка**: ротации при дисбалансе > 1
- **O(log n)** для insert/remove/update/query
- Free-list для переиспользования нод

Публичные запросы:
- `query_aabb(aabb, callback)` — все листья, пересекающиеся с AABB
- `query_ray(ray, callback)` — все листья на пути луча (slab test)
- `query_all_pairs(callback)` — все пары листьев с пересекающимися AABB

Доступ к BVH: `world.bvh()`.

## Интеграция со сценой

```cpp
// C++ — получить CollisionWorld из сцены
CollisionWorld* cw = CollisionWorld::from_scene(scene_handle);

// C API
tc_collision_world* cw = tc_collision_world_get_scene(scene);
```

CollisionWorld хранится как scene extension с типом `TC_SCENE_EXT_TYPE_COLLISION_WORLD`.
