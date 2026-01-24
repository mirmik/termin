# Component Lifetime Redesign Plan

## Goals

1. **PythonComponent**: tc_component живёт столько, сколько PythonComponent
2. **CxxComponent**: ref_count управляет временем жизни (начинает с 0)
3. **Entity**: делает retain при add, release при remove (для обоих типов)
4. **Биндинги**: отдельное пространство от "тела" компонента

## Phase 1: Core Changes

### 1.1 tc_component.h - Add binding type enum and bindings array

```c
// Binding types enum
typedef enum tc_binding_type {
    TC_BINDING_PYTHON = 0,
    TC_BINDING_CSHARP = 1,
    TC_BINDING_RUST = 2,
    TC_BINDING_MAX = 8  // Reserve space for future languages
} tc_binding_type;

// In tc_component struct:
struct tc_component {
    // ... existing fields ...

    // REMOVE: void* wrapper;  (or keep deprecated for transition)

    // NEW: Bindings array - one slot per language
    void* bindings[TC_BINDING_MAX];

    // NEW: Native language of this component (where "body" lives)
    tc_binding_type native_language;
};
```

### 1.2 CxxComponent (component.hpp/cpp) - Add ref_count

```cpp
class CxxComponent {
public:
    tc_component _c;
    Entity entity;

    // NEW: Reference count (starts at 0)
    std::atomic<int> _ref_count{0};

public:
    // NEW: Increment reference count
    void retain() { ++_ref_count; }

    // NEW: Decrement reference count, delete self if 0
    void release() {
        if (--_ref_count <= 0) {
            delete this;
        }
    }

    int ref_count() const { return _ref_count.load(); }
};

// Change _cb_retain/_cb_release to use CxxComponent ref_count
void CxxComponent::_cb_retain(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->retain();
}

void CxxComponent::_cb_release(tc_component* c) {
    auto* self = from_tc(c);
    if (self) self->release();
}
```

### 1.3 TcComponent (tc_component_python_bindings.cpp) - Remove retain from constructor

```cpp
TcComponent(nb::object py_self, const std::string& type_name) {
    ensure_callbacks_initialized();
    _c = tc_component_new_python(py_self.ptr(), type_name.c_str());
    // REMOVE: tc_component_retain(_c);  // No more retain here!
    // tc_component now lives as long as TcComponent (owned by PythonComponent)
}
```

### 1.4 tc_entity_pool.c - Unified retain/release for both types

```c
void tc_entity_pool_add_component(tc_entity_pool* pool, tc_entity_id id, tc_component* c) {
    // ... existing setup ...

    // NEW: Always retain regardless of component kind
    tc_component_retain(c);

    component_array_push(&pool->components[id.index], c);
    // ... rest ...
}

void tc_entity_pool_remove_component(tc_entity_pool* pool, tc_entity_id id, tc_component* c) {
    // ... existing cleanup ...

    // NEW: Always release regardless of component kind
    tc_component_release(c);

    // REMOVE: if (c->wrapper) { release } else { drop } logic
}
```

## Phase 2: Bindings System

### 2.1 tc_component.h - Binding management functions

```c
// Get binding for a language (NULL if not created)
void* tc_component_get_binding(tc_component* c, tc_binding_type lang);

// Set binding for a language (replaces existing)
void tc_component_set_binding(tc_component* c, tc_binding_type lang, void* binding);

// Clear binding for a language
void tc_component_clear_binding(tc_component* c, tc_binding_type lang);

// Check if component is native to a language
bool tc_component_is_native(tc_component* c, tc_binding_type lang);
```

### 2.2 entity_bindings.cpp - get_component logic

```cpp
nb::object tc_component_to_python(tc_component* c) {
    if (!c) return nb::none();

    // Case 1: Component is native Python - return the body directly
    if (c->native_language == TC_BINDING_PYTHON) {
        // wrapper is the PythonComponent body
        if (c->wrapper) {
            return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(c->wrapper));
        }
        return nb::none();
    }

    // Case 2: Component is native C++ (or other) - create/return binding
    // For now, create new wrapper each time (no caching)
    if (c->kind == TC_NATIVE_COMPONENT) {
        CxxComponent* cxx = CxxComponent::from_tc(c);
        if (!cxx) return nb::none();
        return component_to_python(cxx);  // Creates Python wrapper
    }

    return nb::none();
}
```

## Phase 3: TcComponentRef

### 3.1 Add TcComponentRef class

```cpp
// C++ reference holder that does retain/release
class TcComponentRef {
    tc_component* _c = nullptr;
public:
    TcComponentRef() = default;

    TcComponentRef(tc_component* c) : _c(c) {
        if (_c) tc_component_retain(_c);
    }

    ~TcComponentRef() {
        if (_c) tc_component_release(_c);
    }

    // Copy: retain
    TcComponentRef(const TcComponentRef& other) : _c(other._c) {
        if (_c) tc_component_retain(_c);
    }

    TcComponentRef& operator=(const TcComponentRef& other) {
        if (this != &other) {
            if (_c) tc_component_release(_c);
            _c = other._c;
            if (_c) tc_component_retain(_c);
        }
        return *this;
    }

    // Move: transfer ownership
    TcComponentRef(TcComponentRef&& other) noexcept : _c(other._c) {
        other._c = nullptr;
    }

    TcComponentRef& operator=(TcComponentRef&& other) noexcept {
        if (this != &other) {
            if (_c) tc_component_release(_c);
            _c = other._c;
            other._c = nullptr;
        }
        return *this;
    }

    tc_component* get() const { return _c; }
    tc_component* operator->() const { return _c; }
    explicit operator bool() const { return _c != nullptr; }

    // Check if component was removed from entity
    bool is_orphan() const {
        return _c && !tc_entity_id_valid(_c->owner_entity_id);
    }
};
```

## File Changes Summary

| File | Changes |
|------|---------|
| `core_c/include/tc_component.h` | Add `tc_binding_type`, `bindings[]`, `native_language` |
| `cpp/termin/entity/component.hpp` | Add `_ref_count`, `retain()`, `release()` |
| `cpp/termin/entity/component.cpp` | Implement `_cb_retain`/`_cb_release` using ref_count |
| `cpp/termin/tc_component_python_bindings.cpp` | Remove retain from TcComponent constructor |
| `core_c/src/tc_entity_pool.c` | Unified retain/release logic |
| `cpp/termin/bindings/entity/entity_bindings.cpp` | Update `tc_component_to_python` logic |

## Migration Notes

1. `wrapper` field can be kept during transition (deprecated)
2. For PythonComponent: `wrapper` = body (as before)
3. For CxxComponent: `wrapper` deprecated, use `bindings[TC_BINDING_PYTHON]`
4. All existing code using `c->wrapper` should be reviewed

## Testing

1. Create PythonComponent, add to entity, remove from entity - no leak
2. Create CxxComponent (CameraComponent), add to entity, get_component, remove - no crash
3. TcComponentRef holds component alive after entity removal
4. viewport.camera returns same-type object for CxxComponent
