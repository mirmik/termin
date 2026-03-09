# Коллайдеры

## Иерархия типов

```
Collider (абстрактный)
├── ColliderPrimitive (абстрактный, хранит GeneralPose3 transform)
│   ├── BoxCollider
│   ├── SphereCollider
│   ├── CapsuleCollider
│   └── ConvexHullCollider
├── AttachedCollider (привязка примитива к entity transform)
└── UnionCollider (объединение нескольких коллайдеров)
```

## Базовый интерфейс `Collider`

Каждый коллайдер реализует:

| Метод | Описание |
|-------|----------|
| `type()` | Тип: Box, Sphere, Capsule, ConvexHull |
| `center()` | Центр в мировых координатах |
| `aabb()` | Axis-aligned bounding box |
| `closest_to_ray(ray)` | Ближайшие точки между коллайдером и лучом → `RayHit` |
| `closest_to_collider(other)` | Ближайшие точки между двумя коллайдерами → `ColliderHit` |

Дополнительно на `Collider` есть velocity hints для физики:
- `linear_velocity`, `angular_velocity` — задаются физическим солвером.
- `point_velocity(world_point)` — скорость в конкретной точке (линейная + вклад вращения).

## Результаты запросов

**RayHit** (из `colliders` namespace):
- `point_on_collider` — ближайшая точка на поверхности коллайдера
- `point_on_ray` — ближайшая точка на луче
- `distance` — расстояние между точками (0 = пересечение)

**ColliderHit**:
- `point_on_a`, `point_on_b` — ближайшие точки на каждом коллайдере
- `normal` — нормаль контакта (от A к B)
- `distance` — расстояние (отрицательное = пенетрация)
- `colliding()` — true если distance < 0

## Transform-модель

`ColliderPrimitive` хранит `GeneralPose3 transform`:
- `lin` — позиция центра
- `ang` — ориентация (Quat)
- `scale` — масштаб (Vec3)

Каждый примитив интерпретирует scale по-своему:

| Примитив | Масштаб |
|----------|---------|
| BoxCollider | Полный non-uniform: `effective_half_size = half_size * scale` |
| SphereCollider | Uniform: `effective_radius = radius * min(scale)` |
| CapsuleCollider | `effective_half_height = half_height * scale.z`, `effective_radius = radius * min(scale.x, scale.y)` |
| ConvexHullCollider | Non-uniform: каждая вершина масштабируется по осям |

## BoxCollider

Ориентированный параллелепипед. Параметры:
- `half_size` — половинные размеры до применения scale
- Фабрика: `BoxCollider::from_size(full_size)` — создание из полного размера

Специфичные методы:
- `get_corners_world()` — 8 вершин в мировых координатах
- `get_axes_world()` — 3 оси (нормали граней)
- `collide_ground(height)` — коллизия с плоскостью земли (z = height)
- `support(direction)` — support-функция для GJK

Алгоритм box-box: **SAT (Separating Axis Theorem)** по 15 осям (3+3+9 кросс-произведений).

## SphereCollider

Сфера. Параметры:
- `radius` — радиус до применения scale

Коллизии sphere-sphere, sphere-box, sphere-capsule решаются аналитически (closest-point).

## CapsuleCollider

Капсула (цилиндр + полусферы). Ось — local Z. Параметры:
- `half_height` — половина высоты цилиндрической части (без полусфер)
- `radius` — радиус цилиндра и полусфер
- Фабрика: `CapsuleCollider::from_total_height(total, radius)` — из общей высоты

Ключевые методы:
- `world_a()`, `world_b()` — центры полусфер в мировых координатах
- `axis_direction()` — направление оси

Коллизии сводятся к поиску ближайших точек между отрезками + радиусы.

## ConvexHullCollider

Выпуклая оболочка из набора вершин. Параметры:
- `vertices` — вершины в локальном пространстве
- `faces` — грани (треугольники) с нормалями
- `edges` — уникальные рёбра (предвычислены из граней)

Фабрика: `ConvexHullCollider::from_points(points)` — строит оболочку алгоритмом **Quickhull**.

Все коллизии с ConvexHull проходят через **GJK + EPA**.

Raycast: **Moller-Trumbore** по каждой грани.

## AttachedCollider

Обёртка, привязывающая `ColliderPrimitive` к `GeneralTransform3` (entity transform). Мировой трансформ:

```
world = entity_transform.global_pose() * collider.transform
```

При каждом запросе создаёт world-space копию примитива через `clone_at()`. Хранит `owner_entity_id_` для связи с entity.

## UnionCollider

Объединение нескольких коллайдеров. Запросы перебирают все вложенные коллайдеры и возвращают ближайший результат. При коллизии Union vs Union — проверяются все пары.

## Double Dispatch

Narrow-phase для примитивов использует double dispatch по типу:

- Box vs Box — SAT (аналитика)
- Box vs Sphere — closest-point clamp (аналитика)
- Box vs Capsule — итеративный closest-point (аналитика)
- Sphere vs Sphere — расстояние центров (аналитика)
- Sphere vs Capsule — проекция на ось + радиусы (аналитика)
- Capsule vs Capsule — closest-points-segments + радиусы (аналитика)
- Любой vs ConvexHull — GJK + EPA
- ConvexHull vs ConvexHull — GJK + EPA
