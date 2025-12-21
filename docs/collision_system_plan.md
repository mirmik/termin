# План унификации системы коллизий

## Цель

Создать единую систему обнаружения коллизий и вычисления контактов,
которую будут использовать все физические движки (Rigid Body, FEM, будущие).

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    Collision Pipeline                        │
├─────────────────────────────────────────────────────────────┤
│  1. BROAD PHASE (BVH)                                       │
│     └─ Output: List[Pair[Collider*, Collider*]]             │
│                                                              │
│  2. NARROW PHASE (SAT, GJK+EPA)                             │
│     └─ Output: List[ContactManifold]                        │
│                                                              │
│  3. CONTACT MANIFOLD (унифицированный формат)               │
│     ├─ points: List[ContactPoint]                           │
│     ├─ normal: Vec3                                         │
│     └─ collider_a, collider_b: Collider*                    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Physics Solvers                            │
├──────────────────────┬──────────────────────────────────────┤
│  Sequential Impulses │  FEM Constraint Solver               │
│  (rigid body)        │  (contacts as constraints)           │
└──────────────────────┴──────────────────────────────────────┘
```

## Владение объектами

- **Collider** — владеет `ColliderComponent`
- **CollisionWorld** — хранит указатели на коллайдеры
- При удалении Entity → `on_removed()` → `collision_world.remove()`

## Фазы реализации

### Фаза 1: BVH + CollisionWorld [DONE]

**Файлы:**
```
cpp/termin/collision/
├── bvh.hpp              # BVH дерево с incremental update
├── collision_world.hpp  # Главный класс
├── contact_manifold.hpp # Унифицированный контакт
└── collision_bindings.cpp
```

**BVH:**
- Insert/remove/update по указателю Collider*
- Fattened AABB для уменьшения перестроек
- SAH эвристика для качественного разбиения
- Incremental refit при движении объектов

**CollisionWorld:**
```cpp
class CollisionWorld {
    void add(Collider* collider);
    void remove(Collider* collider);
    void update_pose(Collider* collider, const Pose3& pose);

    const std::vector<ContactManifold>& detect_contacts();

    std::vector<RayHit> raycast(const Ray3& ray);
    std::vector<Collider*> query_aabb(const AABB& aabb);
};
```

### Фаза 2: Унификация [DONE]

- [x] RigidBody — чистая динамика (без collider_type/half_size/radius)
- [x] Удалён `cpp/termin/physics/collider.hpp`
- [x] PhysicsWorld использует CollisionWorld через set_collision_world()
- [x] Маппинг collider→body хранится в PhysicsWorld (не в Collider)
- [x] Фабричные методы add_box/add_sphere создают тело + коллайдер
- [x] sync_collider_poses() синхронизирует позы перед detect
- [x] Земля временно как отдельный кейс (до PlaneCollider)
- [x] Python биндинги обновлены

### Фаза 3: GJK + EPA

**Файлы:**
```
cpp/termin/collision/
├── gjk.hpp    # GJK алгоритм
├── epa.hpp    # EPA алгоритм
└── support.hpp # Support functions
```

- Support functions для всех примитивов
- GJK для определения пересечения/расстояния
- EPA для глубины проникновения и нормали
- ConvexCollider для произвольных выпуклых mesh

### Фаза 4: Persistent Contacts

**ContactID:**
```cpp
struct ContactID {
    uint32_t feature_a;  // Вершина/ребро/грань на A
    uint32_t feature_b;  // Вершина/ребро/грань на B
};
```

**ManifoldCache:**
- Сохраняет манифолды между кадрами
- Переносит accumulated impulses (warm-starting)
- Улучшает стабильность стекинга

### Фаза 5: FEM интеграция

- FEM получает те же ContactManifold
- Преобразование контактов в constraint forces
- Унифицированные тесты для обоих движков

## Статус

- [x] Фаза 1: BVH + CollisionWorld — DONE
- [x] Фаза 2: Унификация — DONE
- [ ] Фаза 3: GJK + EPA
- [ ] Фаза 4: Persistent Contacts
- [ ] Фаза 5: FEM интеграция
