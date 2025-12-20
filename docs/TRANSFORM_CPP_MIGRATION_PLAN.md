# План: Перенос Transform Hierarchy в C++

## Обзор архитектуры

```
┌─────────────────────────────────────────────────────────────┐
│ Python                                                       │
│                                                             │
│   class GeneralTransform3:                                  │
│       _id: int  # index в C++ storage                       │
│       # Все операции делегируются в C++                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼ pybind11
┌─────────────────────────────────────────────────────────────┐
│ C++ TransformStorage                                        │
│                                                             │
│   Pose3 local_poses[MAX_TRANSFORMS]                         │
│   Pose3 global_poses[MAX_TRANSFORMS]                        │
│   Vec3 scales[MAX_TRANSFORMS]                               │
│   int32_t parents[MAX_TRANSFORMS]                           │
│   uint8_t dirty[MAX_TRANSFORMS]                             │
│   ...                                                       │
│                                                             │
│   + lazy global_pose(id)                                    │
│   + batch update_all_dirty()                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Этап 1: C++ ядро TransformStorage

### Файл: `termin/core/transform_storage.hpp`

```cpp
#pragma once
#include <cstdint>
#include <vector>
#include "geombase/pose3.hpp"
#include "geombase/vec3.hpp"

namespace termin {

struct TransformStorage {
    // Конфигурация
    static constexpr int32_t INVALID_ID = -1;
    int32_t max_transforms;

    // Данные (Structure of Arrays для cache-friendly доступа)
    std::vector<Pose3> local_poses;
    std::vector<Pose3> global_poses;
    std::vector<Vec3> scales;           // local scale
    std::vector<Vec3> global_scales;    // computed
    std::vector<int32_t> parents;       // INVALID_ID = root
    std::vector<int32_t> first_child;   // INVALID_ID = no children
    std::vector<int32_t> next_sibling;  // INVALID_ID = last sibling
    std::vector<uint8_t> dirty;         // 0 = clean, 1 = dirty
    std::vector<uint8_t> active;        // Slot is in use

    // Free list
    std::vector<int32_t> free_list;
    int32_t count = 0;  // Active transforms

    // Topological order для batch update (parents before children)
    std::vector<int32_t> topo_order;
    bool topo_dirty = true;

    // Methods
    explicit TransformStorage(int32_t max_size);

    // Lifecycle
    int32_t create();
    void destroy(int32_t id);
    bool is_valid(int32_t id) const;

    // Hierarchy
    void set_parent(int32_t id, int32_t parent_id);
    int32_t get_parent(int32_t id) const;
    void unlink(int32_t id);  // Remove from parent

    // Local pose
    void set_local_pose(int32_t id, const Pose3& pose);
    const Pose3& get_local_pose(int32_t id) const;
    void set_local_position(int32_t id, const Vec3& pos);
    void set_local_rotation(int32_t id, const Quat& rot);
    void set_local_scale(int32_t id, const Vec3& scale);

    // Global pose (lazy)
    const Pose3& get_global_pose(int32_t id);
    void set_global_pose(int32_t id, const Pose3& pose);  // Recomputes local

    // Dirty propagation
    void mark_dirty(int32_t id);
    void mark_dirty_recursive(int32_t id);  // id + all descendants

    // Batch update
    void rebuild_topo_order();
    void update_all_dirty();  // Batch: пересчёт всех dirty в topo order

    // Iteration helpers
    template<typename F>
    void foreach_child(int32_t id, F&& fn);

    template<typename F>
    void foreach_descendant(int32_t id, F&& fn);
};

} // namespace termin
```

---

## Этап 2: Реализация C++

### Файл: `termin/core/transform_storage.cpp`

```cpp
#include "transform_storage.hpp"
#include <algorithm>
#include <stdexcept>

namespace termin {

TransformStorage::TransformStorage(int32_t max_size)
    : max_transforms(max_size)
{
    // Pre-allocate all arrays
    local_poses.resize(max_size);
    global_poses.resize(max_size);
    scales.resize(max_size, Vec3(1, 1, 1));
    global_scales.resize(max_size, Vec3(1, 1, 1));
    parents.resize(max_size, INVALID_ID);
    first_child.resize(max_size, INVALID_ID);
    next_sibling.resize(max_size, INVALID_ID);
    dirty.resize(max_size, 0);
    active.resize(max_size, 0);

    // Initially all slots are free
    free_list.reserve(max_size);
    for (int32_t i = max_size - 1; i >= 0; --i) {
        free_list.push_back(i);
    }

    topo_order.reserve(max_size);
}

int32_t TransformStorage::create() {
    if (free_list.empty()) {
        throw std::runtime_error("TransformStorage: limit reached");
    }

    int32_t id = free_list.back();
    free_list.pop_back();

    // Initialize
    active[id] = 1;
    local_poses[id] = Pose3::identity();
    global_poses[id] = Pose3::identity();
    scales[id] = Vec3(1, 1, 1);
    global_scales[id] = Vec3(1, 1, 1);
    parents[id] = INVALID_ID;
    first_child[id] = INVALID_ID;
    next_sibling[id] = INVALID_ID;
    dirty[id] = 1;  // New transform is dirty

    count++;
    topo_dirty = true;

    return id;
}

void TransformStorage::destroy(int32_t id) {
    if (!is_valid(id)) return;

    // Unlink from parent
    unlink(id);

    // Orphan all children (they become roots)
    int32_t child = first_child[id];
    while (child != INVALID_ID) {
        int32_t next = next_sibling[child];
        parents[child] = INVALID_ID;
        next_sibling[child] = INVALID_ID;
        mark_dirty(child);
        child = next;
    }
    first_child[id] = INVALID_ID;

    active[id] = 0;
    free_list.push_back(id);
    count--;
    topo_dirty = true;
}

void TransformStorage::set_parent(int32_t id, int32_t parent_id) {
    if (!is_valid(id)) return;
    if (parent_id != INVALID_ID && !is_valid(parent_id)) return;
    if (parents[id] == parent_id) return;

    // Remove from old parent
    unlink(id);

    // Add to new parent
    if (parent_id != INVALID_ID) {
        parents[id] = parent_id;
        next_sibling[id] = first_child[parent_id];
        first_child[parent_id] = id;
    }

    mark_dirty(id);
    topo_dirty = true;
}

void TransformStorage::unlink(int32_t id) {
    int32_t parent_id = parents[id];
    if (parent_id == INVALID_ID) return;

    // Remove from sibling list
    if (first_child[parent_id] == id) {
        first_child[parent_id] = next_sibling[id];
    } else {
        int32_t prev = first_child[parent_id];
        while (prev != INVALID_ID && next_sibling[prev] != id) {
            prev = next_sibling[prev];
        }
        if (prev != INVALID_ID) {
            next_sibling[prev] = next_sibling[id];
        }
    }

    parents[id] = INVALID_ID;
    next_sibling[id] = INVALID_ID;
}

void TransformStorage::mark_dirty(int32_t id) {
    if (!is_valid(id) || dirty[id]) return;
    dirty[id] = 1;
}

void TransformStorage::mark_dirty_recursive(int32_t id) {
    if (!is_valid(id)) return;

    // BFS or DFS to mark all descendants
    mark_dirty(id);
    int32_t child = first_child[id];
    while (child != INVALID_ID) {
        mark_dirty_recursive(child);
        child = next_sibling[child];
    }
}

void TransformStorage::set_local_pose(int32_t id, const Pose3& pose) {
    if (!is_valid(id)) return;
    local_poses[id] = pose;
    mark_dirty_recursive(id);
}

const Pose3& TransformStorage::get_global_pose(int32_t id) {
    if (!is_valid(id)) {
        static Pose3 identity;
        return identity;
    }

    // Lazy evaluation
    if (dirty[id]) {
        int32_t p = parents[id];
        if (p == INVALID_ID) {
            global_poses[id] = local_poses[id];
            global_scales[id] = scales[id];
        } else {
            // Ensure parent is computed first (recursive)
            const Pose3& parent_global = get_global_pose(p);
            global_poses[id] = parent_global * local_poses[id];
            global_scales[id] = global_scales[p] * scales[id];  // component-wise
        }
        dirty[id] = 0;
    }

    return global_poses[id];
}

void TransformStorage::rebuild_topo_order() {
    if (!topo_dirty) return;

    topo_order.clear();

    // Find all roots and BFS
    for (int32_t i = 0; i < max_transforms; ++i) {
        if (active[i] && parents[i] == INVALID_ID) {
            // BFS from this root
            std::vector<int32_t> queue;
            queue.push_back(i);
            size_t head = 0;

            while (head < queue.size()) {
                int32_t curr = queue[head++];
                topo_order.push_back(curr);

                int32_t child = first_child[curr];
                while (child != INVALID_ID) {
                    queue.push_back(child);
                    child = next_sibling[child];
                }
            }
        }
    }

    topo_dirty = false;
}

void TransformStorage::update_all_dirty() {
    rebuild_topo_order();

    // Process in topological order: parents before children
    for (int32_t id : topo_order) {
        if (!dirty[id]) continue;

        int32_t p = parents[id];
        if (p == INVALID_ID) {
            global_poses[id] = local_poses[id];
            global_scales[id] = scales[id];
        } else {
            // Parent already computed (topo order guarantees this)
            global_poses[id] = global_poses[p] * local_poses[id];
            global_scales[id] = global_scales[p] * scales[id];
        }
        dirty[id] = 0;
    }
}

} // namespace termin
```

---

## Этап 3: Python bindings

### Файл: `termin/core/transform_bindings.cpp`

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "transform_storage.hpp"

namespace py = pybind11;
using namespace termin;

// Global storage instance
static std::unique_ptr<TransformStorage> g_storage;

void init_transform_storage(int32_t max_size) {
    g_storage = std::make_unique<TransformStorage>(max_size);
}

TransformStorage& get_storage() {
    if (!g_storage) {
        throw std::runtime_error("TransformStorage not initialized");
    }
    return *g_storage;
}

PYBIND11_MODULE(_transform_native, m) {
    m.doc() = "Native transform storage";

    // Initialization
    m.def("init", &init_transform_storage, py::arg("max_size") = 65536);

    // Lifecycle
    m.def("create", []() { return get_storage().create(); });
    m.def("destroy", [](int32_t id) { get_storage().destroy(id); });
    m.def("is_valid", [](int32_t id) { return get_storage().is_valid(id); });

    // Hierarchy
    m.def("set_parent", [](int32_t id, int32_t parent) {
        get_storage().set_parent(id, parent);
    });
    m.def("get_parent", [](int32_t id) {
        return get_storage().get_parent(id);
    });
    m.def("get_children", [](int32_t id) {
        std::vector<int32_t> children;
        get_storage().foreach_child(id, [&](int32_t child) {
            children.push_back(child);
        });
        return children;
    });

    // Local pose
    m.def("set_local_pose", [](int32_t id, const Pose3& pose) {
        get_storage().set_local_pose(id, pose);
    });
    m.def("get_local_pose", [](int32_t id) {
        return get_storage().get_local_pose(id);
    });
    m.def("set_local_position", [](int32_t id, const Vec3& pos) {
        get_storage().set_local_position(id, pos);
    });
    m.def("set_local_rotation", [](int32_t id, const Quat& rot) {
        get_storage().set_local_rotation(id, rot);
    });
    m.def("set_local_scale", [](int32_t id, const Vec3& scale) {
        get_storage().set_local_scale(id, scale);
    });

    // Global pose
    m.def("get_global_pose", [](int32_t id) {
        return get_storage().get_global_pose(id);
    });
    m.def("set_global_pose", [](int32_t id, const Pose3& pose) {
        get_storage().set_global_pose(id, pose);
    });

    // Batch operations
    m.def("update_all_dirty", []() {
        get_storage().update_all_dirty();
    });

    // Stats
    m.def("count", []() { return get_storage().count; });
    m.def("capacity", []() { return get_storage().max_transforms; });
}
```

---

## Этап 4: Python wrapper

### Файл: `termin/kinematic/general_transform.py` (новая версия)

```python
"""GeneralTransform3 - Python wrapper over C++ TransformStorage."""

from __future__ import annotations
from typing import TYPE_CHECKING, Iterator

from termin.core import _transform_native as _native
from termin.geombase import Pose3, Vec3, Quat, GeneralPose3

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity


class GeneralTransform3:
    """
    Transform handle - thin wrapper over C++ storage.

    All data lives in C++. Python only holds the id.
    """

    __slots__ = ('_id', 'entity')

    def __init__(self, pose: GeneralPose3 | None = None, id: int | None = None):
        if id is None:
            self._id = _native.create()
            if pose is not None:
                _native.set_local_pose(self._id, pose.as_pose3())
                _native.set_local_scale(self._id, pose.scale)
        else:
            self._id = id
        self.entity: Entity | None = None

    def destroy(self) -> None:
        """Release this transform slot."""
        if self._id >= 0:
            _native.destroy(self._id)
            self._id = -1

    @property
    def id(self) -> int:
        return self._id

    # --- Hierarchy ---

    @property
    def parent(self) -> GeneralTransform3 | None:
        parent_id = _native.get_parent(self._id)
        if parent_id < 0:
            return None
        # Note: возвращает новый wrapper, не кешированный
        t = GeneralTransform3.__new__(GeneralTransform3)
        t._id = parent_id
        t.entity = None
        return t

    def set_parent(self, parent: GeneralTransform3 | None) -> None:
        parent_id = parent._id if parent else -1
        _native.set_parent(self._id, parent_id)

    @property
    def children(self) -> list[GeneralTransform3]:
        result = []
        for cid in _native.get_children(self._id):
            t = GeneralTransform3.__new__(GeneralTransform3)
            t._id = cid
            t.entity = None
            result.append(t)
        return result

    def link(self, child: GeneralTransform3) -> None:
        """Add child to this transform."""
        child.set_parent(self)

    def unlink(self, child: GeneralTransform3) -> None:
        """Remove child from this transform."""
        if _native.get_parent(child._id) == self._id:
            child.set_parent(None)

    # --- Local pose ---

    def local_pose(self) -> GeneralPose3:
        pose = _native.get_local_pose(self._id)
        scale = _native.get_local_scale(self._id)
        return GeneralPose3(ang=pose.ang, lin=pose.lin, scale=scale)

    def set_local_pose(self, pose: GeneralPose3) -> None:
        _native.set_local_pose(self._id, pose.as_pose3())
        _native.set_local_scale(self._id, pose.scale)

    def relocate_local(self, pose: GeneralPose3) -> None:
        self.set_local_pose(pose)

    # --- Global pose ---

    def global_pose(self) -> GeneralPose3:
        """Get world-space pose. Lazy: computes if dirty."""
        pose = _native.get_global_pose(self._id)
        scale = _native.get_global_scale(self._id)
        return GeneralPose3(ang=pose.ang, lin=pose.lin, scale=scale)

    def set_global_pose(self, pose: GeneralPose3) -> None:
        """Set world-space pose. Recomputes local pose."""
        _native.set_global_pose(self._id, pose.as_pose3())
        _native.set_global_scale(self._id, pose.scale)

    def relocate_global(self, pose: GeneralPose3) -> None:
        """Alias for set_global_pose."""
        self.set_global_pose(pose)

    # --- Compatibility with old API ---

    @property
    def _local_pose(self) -> GeneralPose3:
        return self.local_pose()

    @_local_pose.setter
    def _local_pose(self, pose: GeneralPose3) -> None:
        self.set_local_pose(pose)


# --- Module-level batch operations ---

def init_transform_storage(max_size: int = 65536) -> None:
    """Initialize C++ storage. Call once at startup."""
    _native.init(max_size)


def update_all_transforms() -> None:
    """Batch update all dirty transforms. Call once per frame."""
    _native.update_all_dirty()


def transform_count() -> int:
    """Number of active transforms."""
    return _native.count()


def transform_capacity() -> int:
    """Maximum transforms (from settings)."""
    return _native.capacity()
```

---

## Этап 5: Интеграция

### 5.1 Инициализация при старте

```python
# termin/visualization/core/engine.py или main.py

from termin.kinematic.general_transform import init_transform_storage

def init_engine(config: EngineConfig):
    # Читаем лимит из настроек
    max_transforms = config.get("max_transforms", 65536)
    init_transform_storage(max_transforms)
    # ...
```

### 5.2 Entity использует новый GeneralTransform3

```python
# termin/visualization/core/entity.py

from termin.kinematic.general_transform import GeneralTransform3

class Entity:
    def __init__(self, ...):
        self.transform = GeneralTransform3(general_pose)
        self.transform.entity = self
        # ...

    def destroy(self):
        self.transform.destroy()
        # ...
```

### 5.3 Batch update в game loop

```python
# termin/editor/game_mode_controller.py

from termin.kinematic.general_transform import update_all_transforms

def _tick(self) -> None:
    dt = self._elapsed_timer.restart() / 1000.0

    # Update components (may modify transforms)
    self.scene.update(dt)

    # Batch recompute all dirty global transforms
    update_all_transforms()

    # Now render - all global_poses are valid
    self._on_request_update()
```

---

## Этап 6: Миграция существующего кода

### Что заменить:

| Старое | Новое |
|--------|-------|
| `GeneralTransform3(pose)` | `GeneralTransform3(pose)` (тот же API) |
| `transform._local_pose` | `transform.local_pose()` |
| `transform._global_pose` | `transform.global_pose()` |
| `transform.children` | `transform.children` (теперь из C++) |
| `transform.parent` | `transform.parent` (теперь из C++) |

### Шаги миграции:

1. Добавить C++ код, собрать модуль `_transform_native`
2. Создать новую версию `GeneralTransform3` с тем же API
3. Переключить импорты
4. Убедиться что тесты проходят
5. Удалить старую реализацию

---

## Файловая структура

```
termin/
├── core/
│   ├── CMakeLists.txt          # Добавить transform_storage
│   ├── transform_storage.hpp
│   ├── transform_storage.cpp
│   └── transform_bindings.cpp
├── kinematic/
│   ├── general_transform.py    # Новая версия (C++ wrapper)
│   └── general_transform_old.py # Старая версия (удалить после миграции)
```

---

## Опциональные улучшения (позже)

1. **SIMD batch update** — AVX для умножения матриц
2. **Parallel update** — разбить topo_order на независимые поддеревья
3. **Transform registry** — id → GeneralTransform3 mapping для parent property
4. **Generational indices** — защита от dangling references
