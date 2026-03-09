# termin-collision

Библиотека обнаружения столкновений для движка **Termin**.

Реализует коллайдеры, broad-phase (BVH), narrow-phase (аналитика, GJK/EPA) и контактные манифолды на C++.
Предоставляет C API для интеграции через FFI и Python-биндинги через nanobind.

## Возможности

- **Примитивы** — Box (OBB), Sphere, Capsule, ConvexHull (Quickhull).
- **Составные коллайдеры** — AttachedCollider (привязка к entity), UnionCollider (объединение).
- **Broad-phase** — динамический BVH с fattened AABB, SAH-вставкой и AVL-балансировкой.
- **Narrow-phase** — аналитические формулы для простых пар, GJK+EPA для выпуклых оболочек.
- **Контактные манифолды** — до 4 точек, Sutherland-Hodgman clipping для box-box.
- **Raycast** — через BVH + точный тест на примитивах (slab, Moller-Trumbore).
- **Scene extension** — CollisionWorld как расширение tc_scene.

## Быстрый старт

```cpp
#include <termin/collision/collision.hpp>

using namespace termin::colliders;
using namespace termin::collision;

BoxCollider box(Vec3(1, 1, 1));
SphereCollider sphere(0.5, GeneralPose3(Quat::identity(), Vec3(2, 0, 0)));

CollisionWorld world;
world.add(&box);
world.add(&sphere);

world.update_all();
auto manifolds = world.detect_contacts();

Ray3 ray(Vec3(0, 0, 5), Vec3(0, 0, -1));
auto hit = world.raycast_closest(ray);
```

## Сборка

```bash
cmake -S . -B build
cmake --build build -j$(nproc)
```

С тестами:
```bash
cmake -S . -B build -DTERMIN_COLLISION_BUILD_TESTS=ON
cmake --build build -j$(nproc)
ctest --test-dir build --output-on-failure
```

С Python-биндингами:
```bash
cmake -S . -B build -DTERMIN_BUILD_PYTHON=ON
cmake --build build -j$(nproc)
```

## Зависимости

- `termin_base` — геометрические типы (Vec3, Quat, Pose3, AABB, Ray3)
- `termin_inspect` — инспекция типов
- `termin_scene` — сцена, entity pool, scene extensions

Опционально: `nanobind` (Python-биндинги).

## Документация

- Исходники: [`docs/`](docs/)
- Точка входа: [`docs/index.md`](docs/index.md)

## Структура проекта

```
include/
  termin_collision/    # Точка входа: version, runtime init/shutdown
  termin/colliders/    # C++: Collider, Box, Sphere, Capsule, ConvexHull, GJK, EPA
  termin/collision/    # C++: CollisionWorld, BVH, ContactManifold
  physics/             # C API: tc_collision.h, tc_collision_world.h
src/                   # Реализация C API и scene extension
cpp/bindings/          # nanobind Python-биндинги
tests/                 # C++ тесты
```
