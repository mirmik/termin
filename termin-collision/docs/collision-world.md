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
std::vector<ContactManifold> manifolds = world.detect_contacts();
```

Поток:
1. **Broad-phase**: `BVH::query_all_pairs()` — все пары с пересекающимися AABB.
2. **Narrow-phase**: `Collider::closest_to_collider()` — точная проверка.
3. Для box-box: дополнительно Sutherland-Hodgman clipping для множественных контактных точек.

## ContactManifold

```cpp
struct ContactManifold {
    static constexpr int MAX_POINTS = 4;

    Collider* collider_a;
    Collider* collider_b;
    Vec3 normal;                          // от A к B
    std::array<ContactPoint, MAX_POINTS> points;
    int point_count;

    void* body_a;   // пользовательские данные (для физики)
    void* body_b;
};
```

## ContactPoint

```cpp
struct ContactPoint {
    Vec3 position;       // мировые координаты
    Vec3 local_a;        // на коллайдере A
    Vec3 local_b;        // на коллайдере B
    double penetration;  // < 0 = пенетрация, > 0 = разделение

    ContactID id;                // для матчинга между кадрами
    double normal_impulse;       // для warm-starting (заполняется солвером)
    double tangent1_impulse;
    double tangent2_impulse;
};
```

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
