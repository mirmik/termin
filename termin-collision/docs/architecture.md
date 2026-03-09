# Архитектура

## Общая схема

```
┌─────────────────────────────────────────────────────────┐
│  C API / Python bindings                                │
│  tc_collision.h, _colliders_native, _collision_native   │
├─────────────────────────────────────────────────────────┤
│  CollisionWorld                                         │
│  Broad-phase (BVH) + Narrow-phase + Contact manifolds  │
├──────────────────────┬──────────────────────────────────┤
│  Составные           │  Примитивы                       │
│  AttachedCollider    │  BoxCollider                     │
│  UnionCollider       │  SphereCollider                  │
│                      │  CapsuleCollider                 │
│                      │  ConvexHullCollider               │
├──────────────────────┴──────────────────────────────────┤
│  Collider (абстрактный интерфейс)                       │
│  center(), aabb(), closest_to_ray(), closest_to_collider│
└─────────────────────────────────────────────────────────┘
```

## Два пространства имён

| Namespace | Ответственность |
|-----------|----------------|
| `termin::colliders` | Геометрические примитивы, GJK/EPA, double dispatch |
| `termin::collision` | CollisionWorld, BVH, ContactManifold, RayHit |

## Поток обнаружения столкновений

```
1. CollisionWorld::update_all()
   └── Обновить AABB всех коллайдеров в BVH

2. CollisionWorld::detect_contacts()
   ├── Broad-phase: BVH::query_all_pairs()
   │   └── Пары с пересекающимися AABB
   └── Narrow-phase: Collider::closest_to_collider()
       ├── Примитив-примитив: аналитика (SAT, closest-point)
       ├── С ConvexHull: GJK + EPA
       └── Box-Box коллизия: SAT + Sutherland-Hodgman clipping
```

## Интеграция со сценой

CollisionWorld регистрируется как `tc_scene_extension` с типом `TC_SCENE_EXT_TYPE_COLLISION_WORLD`. Это позволяет:

- Автоматическое создание/уничтожение CollisionWorld при создании/уничтожении сцены.
- Доступ через C API: `tc_collision_world_get_scene(scene)`.
- Компоненты-коллайдеры (из entity_lib) добавляют `AttachedCollider` в CollisionWorld при `start()` и удаляют при `destroy()`.

## Зависимости

```
termin_collision
├── termin_base     (Vec3, Quat, Pose3, GeneralPose3, AABB, Ray3)
├── termin_inspect  (инспекция типов)
└── termin_scene    (tc_scene, tc_entity_pool, tc_scene_extension)
```

Опциональные зависимости:
- **nanobind** — для сборки Python-биндингов (`-DTERMIN_BUILD_PYTHON=ON`)

## Структура проекта

```
include/
  termin_collision/    # Точка входа: termin_collision.h (version, runtime init/shutdown)
  termin/colliders/    # C++ заголовки: Collider, Box, Sphere, Capsule, ConvexHull, GJK, EPA
  termin/collision/    # C++ заголовки: CollisionWorld, BVH, ContactManifold
  physics/             # C API: tc_collision.h, tc_collision_world.h
src/                   # Реализация C API
cpp/bindings/          # nanobind Python-биндинги
tests/                 # C++ тесты
```
