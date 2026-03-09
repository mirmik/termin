# termin-collision

`termin-collision` — библиотека обнаружения столкновений для движка Termin.

Основная модель:

- **Коллайдеры** (`Collider`) — абстрактный интерфейс с запросами closest-point и raycast.
- **Примитивы** (`ColliderPrimitive`) — Box, Sphere, Capsule, ConvexHull с support-функциями.
- **Составные** — `AttachedCollider` (привязка к entity transform), `UnionCollider` (объединение).
- **CollisionWorld** — централизованное управление коллайдерами, broad-phase через BVH, narrow-phase через аналитику и GJK/EPA.
- **Scene Extension** — CollisionWorld встраивается в `tc_scene` как extension, доступен через C API.

Документация описывает архитектуру, алгоритмы и публичный API текущей реализации.

## Рекомендуемый маршрут

| #  | Раздел | Описание |
|----|--------|----------|
| 1  | [Архитектура](architecture.md) | Слои, поток данных, broad/narrow phase |
| 2  | [Коллайдеры](colliders.md) | Типы коллайдеров, transform-модель, double dispatch |
| 3  | [Алгоритмы](algorithms.md) | SAT, GJK, EPA, Quickhull, Sutherland-Hodgman |
| 4  | [CollisionWorld](collision-world.md) | BVH, управление коллайдерами, детекция контактов |
| 5  | [C API](c-api.md) | Публичные C-заголовки, scene extension |
| 6  | [Python API](python-api.md) | nanobind-биндинги, модули `colliders` и `collision` |
