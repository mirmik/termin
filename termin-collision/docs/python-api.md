# Python API

Python-биндинги реализованы через nanobind и разделены на два модуля.

## Модуль `termin.colliders` (`_colliders_native`)

Геометрические примитивы и запросы.

### Типы

```python
from termin.colliders import (
    ColliderType,      # enum: Box, Sphere, Capsule
    Collider,          # базовый интерфейс
    ColliderPrimitive, # примитив с transform
    BoxCollider,
    SphereCollider,
    CapsuleCollider,
    AttachedCollider,
    UnionCollider,
    Ray3,
    RayHit,
    ColliderHit,
)
```

### Создание коллайдеров

```python
from termin.geombase import Vec3, GeneralPose3

# Box
box = BoxCollider(half_size=Vec3(1, 0.5, 0.3))
box = BoxCollider.from_size(Vec3(2, 1, 0.6))

# Sphere
sphere = SphereCollider(radius=0.5)

# Capsule
capsule = CapsuleCollider(half_height=0.5, radius=0.25)
capsule = CapsuleCollider.from_total_height(1.5, radius=0.25)

# С трансформом
box = BoxCollider(Vec3(1, 1, 1), transform=GeneralPose3(...))
```

### Запросы

```python
# Raycast
ray = Ray3(origin=Vec3(0, 0, 5), direction=Vec3(0, 0, -1))
hit = box.closest_to_ray(ray)
if hit.hit():
    print(hit.point_on_collider, hit.distance)

# Коллизия между коллайдерами
result = box.closest_to_collider(sphere)
if result.colliding():
    print(result.normal, result.distance, result.point_on_a, result.point_on_b)
```

### AttachedCollider

```python
attached = AttachedCollider(collider=box, transform=entity_transform)
print(attached.world_transform())
print(attached.colliding(other_collider))
print(attached.distance(other_collider))
```

### UnionCollider

```python
union = UnionCollider()
union.add(box)
union.add(sphere)
# или
union = UnionCollider([box, sphere])
```

### Velocity hints

```python
collider.linear_velocity = Vec3(1, 0, 0)
collider.angular_velocity = Vec3(0, 0, 3.14)
vel = collider.point_velocity(world_point)
```

## Модуль `termin.collision` (`_collision_native`)

CollisionWorld, BVH, контактные данные.

### Типы

```python
from termin.collision import (
    CollisionWorld,
    BVH,
    ContactManifold,
    ContactPoint,
    ContactID,
    RayHit,        # расширенная версия с collider pointer
    ColliderPair,
)
```

### CollisionWorld

```python
world = CollisionWorld()

# Управление
world.add(collider)
world.remove(collider)
world.update_pose(collider)
world.update_all()

# Детекция
manifolds = world.detect_contacts()
for m in manifolds:
    print(m.collider_a, m.collider_b, m.normal)
    for pt in m.get_points():
        print(pt.position, pt.penetration)

# Raycast
hits = world.raycast(ray)
closest = world.raycast_closest(ray)

# AABB-запрос
colliders = world.query_aabb(aabb)

# Из сцены
world = CollisionWorld.from_scene(scene)
```

### ContactManifold

```python
m.collider_a        # Collider*
m.collider_b        # Collider*
m.normal             # Vec3
m.point_count        # int
m.get_points()       # list[ContactPoint]
m.same_pair(other)   # bool
m.pair_key()         # uint64
```

### BVH

```python
bvh = world.bvh  # read-only доступ

bvh.insert(collider, aabb)
bvh.remove(collider)
bvh.update(collider, new_aabb)

# Запросы
colliders = bvh.query_aabb(aabb)
hits = bvh.query_ray(ray)        # list[(collider, t_min, t_max)]
pairs = bvh.query_all_pairs()    # list[(collider_a, collider_b)]

bvh.node_count()
bvh.compute_height()
bvh.validate()
```

## Зависимости модулей

```
_collision_native
├── _colliders_native
├── _geom_native (termin.geombase)
└── _entity_native (termin.entity)

_colliders_native
└── _geom_native (termin.geombase)
```
