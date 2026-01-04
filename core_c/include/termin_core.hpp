// termin_core.hpp - C++ wrapper for Termin Core
#pragma once

#include "termin_core.h"
#include <string>
#include <string_view>
#include <vector>
#include <memory>
#include <functional>

namespace tc {

// ============================================================================
// Geometry types - zero-cost wrappers
// ============================================================================

struct Vec3 : tc_vec3 {
    Vec3() : tc_vec3{0, 0, 0} {}
    Vec3(double x, double y, double z) : tc_vec3{x, y, z} {}
    Vec3(tc_vec3 v) : tc_vec3(v) {}

    static Vec3 zero() { return tc_vec3_zero(); }
    static Vec3 one() { return tc_vec3_one(); }
    static Vec3 up() { return {0, 1, 0}; }
    static Vec3 forward() { return {0, 0, 1}; }
    static Vec3 right() { return {1, 0, 0}; }

    Vec3 operator+(const Vec3& o) const { return tc_vec3_add(*this, o); }
    Vec3 operator-(const Vec3& o) const { return tc_vec3_sub(*this, o); }
    Vec3 operator*(double s) const { return tc_vec3_scale(*this, s); }
    Vec3 operator-() const { return tc_vec3_neg(*this); }

    double dot(const Vec3& o) const { return tc_vec3_dot(*this, o); }
    Vec3 cross(const Vec3& o) const { return tc_vec3_cross(*this, o); }
    double length() const { return tc_vec3_length(*this); }
    double length_sq() const { return tc_vec3_length_sq(*this); }
    Vec3 normalized() const { return tc_vec3_normalize(*this); }
    Vec3 lerp(const Vec3& to, double t) const { return tc_vec3_lerp(*this, to, t); }
};

struct Quat : tc_quat {
    Quat() : tc_quat{0, 0, 0, 1} {}
    Quat(double x, double y, double z, double w) : tc_quat{x, y, z, w} {}
    Quat(tc_quat q) : tc_quat(q) {}

    static Quat identity() { return tc_quat_identity(); }
    static Quat from_axis_angle(const Vec3& axis, double angle) {
        return tc_quat_from_axis_angle(axis, angle);
    }
    static Quat from_euler(double x, double y, double z) {
        return tc_quat_from_euler(x, y, z);
    }

    Quat operator*(const Quat& o) const { return tc_quat_mul(*this, o); }
    Vec3 operator*(const Vec3& v) const { return tc_quat_rotate(*this, v); }

    Quat conjugate() const { return tc_quat_conjugate(*this); }
    Quat inverse() const { return tc_quat_inverse(*this); }
    Quat normalized() const { return tc_quat_normalize(*this); }
    Vec3 rotate(const Vec3& v) const { return tc_quat_rotate(*this, v); }
    Quat slerp(const Quat& to, double t) const { return tc_quat_slerp(*this, to, t); }
};

struct Pose3 : tc_pose3 {
    Pose3() : tc_pose3{Vec3::zero(), Quat::identity()} {}
    Pose3(Vec3 pos, Quat rot) : tc_pose3{pos, rot} {}
    Pose3(tc_pose3 p) : tc_pose3(p) {}

    static Pose3 identity() { return tc_pose3_identity(); }

    Vec3& pos() { return reinterpret_cast<Vec3&>(position); }
    const Vec3& pos() const { return reinterpret_cast<const Vec3&>(position); }
    Quat& rot() { return reinterpret_cast<Quat&>(rotation); }
    const Quat& rot() const { return reinterpret_cast<const Quat&>(rotation); }

    Pose3 operator*(const Pose3& o) const { return tc_pose3_mul(*this, o); }
    Pose3 inverse() const { return tc_pose3_inverse(*this); }
    Vec3 transform_point(const Vec3& p) const { return tc_pose3_transform_point(*this, p); }
    Vec3 transform_vector(const Vec3& v) const { return tc_pose3_transform_vector(*this, v); }
};

struct GeneralPose3 : tc_general_pose3 {
    GeneralPose3() : tc_general_pose3{Vec3::zero(), Quat::identity(), Vec3::one()} {}
    GeneralPose3(Vec3 pos, Quat rot, Vec3 scl) : tc_general_pose3{pos, rot, scl} {}
    GeneralPose3(tc_general_pose3 p) : tc_general_pose3(p) {}

    static GeneralPose3 identity() { return tc_gpose_identity(); }

    Vec3& pos() { return reinterpret_cast<Vec3&>(position); }
    const Vec3& pos() const { return reinterpret_cast<const Vec3&>(position); }
    Quat& rot() { return reinterpret_cast<Quat&>(rotation); }
    const Quat& rot() const { return reinterpret_cast<const Quat&>(rotation); }
    Vec3& scl() { return reinterpret_cast<Vec3&>(scale); }
    const Vec3& scl() const { return reinterpret_cast<const Vec3&>(scale); }

    GeneralPose3 operator*(const GeneralPose3& o) const { return tc_gpose_mul(*this, o); }
    GeneralPose3 inverse() const { return tc_gpose_inverse(*this); }
    Vec3 transform_point(const Vec3& p) const { return tc_gpose_transform_point(*this, p); }
};

struct Mat44 : tc_mat44 {
    Mat44() : tc_mat44{{1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1}} {}
    Mat44(tc_mat44 m) : tc_mat44(m) {}

    static Mat44 identity() { return Mat44(); }

    double& operator()(int row, int col) { return m[col * 4 + row]; }
    double operator()(int row, int col) const { return m[col * 4 + row]; }

    const double* data() const { return m; }
    double* data() { return m; }
};

// ============================================================================
// Transform - RAII wrapper
// ============================================================================

class Entity;  // Forward declaration

class Transform {
    tc_transform* handle_;
    bool owned_;

public:
    // Take ownership
    explicit Transform(tc_transform* h, bool owned = false) : handle_(h), owned_(owned) {}

    // Create new
    Transform() : handle_(tc_transform_new()), owned_(true) {}
    explicit Transform(GeneralPose3 pose) : handle_(tc_transform_new_with_pose(pose)), owned_(true) {}

    ~Transform() {
        if (owned_ && handle_) {
            tc_transform_free(handle_);
        }
    }

    // Non-copyable, movable
    Transform(const Transform&) = delete;
    Transform& operator=(const Transform&) = delete;
    Transform(Transform&& o) noexcept : handle_(o.handle_), owned_(o.owned_) {
        o.handle_ = nullptr;
        o.owned_ = false;
    }
    Transform& operator=(Transform&& o) noexcept {
        if (this != &o) {
            if (owned_ && handle_) tc_transform_free(handle_);
            handle_ = o.handle_;
            owned_ = o.owned_;
            o.handle_ = nullptr;
            o.owned_ = false;
        }
        return *this;
    }

    tc_transform* raw() const { return handle_; }

    // Pose access
    GeneralPose3 local_pose() const { return tc_transform_local_pose(handle_); }
    void set_local_pose(GeneralPose3 pose) { tc_transform_set_local_pose(handle_, pose); }

    GeneralPose3 global_pose() const { return tc_transform_global_pose(handle_); }
    void set_global_pose(GeneralPose3 pose) { tc_transform_set_global_pose(handle_, pose); }

    Vec3 position() const { return tc_transform_position(handle_); }
    void set_position(Vec3 pos) { tc_transform_set_position(handle_, pos); }

    Quat rotation() const { return tc_transform_rotation(handle_); }
    void set_rotation(Quat rot) { tc_transform_set_rotation(handle_, rot); }

    Vec3 scale() const { return tc_transform_scale(handle_); }
    void set_scale(Vec3 s) { tc_transform_set_scale(handle_, s); }

    Vec3 global_position() const { return tc_transform_global_position(handle_); }
    Quat global_rotation() const { return tc_transform_global_rotation(handle_); }

    // Hierarchy
    void set_parent(Transform* parent) {
        tc_transform_set_parent(handle_, parent ? parent->raw() : nullptr);
    }

    tc_transform* parent() const { return tc_transform_parent(handle_); }
    size_t children_count() const { return tc_transform_children_count(handle_); }
    tc_transform* child_at(size_t i) const { return tc_transform_child_at(handle_, i); }

    // Operations
    void translate(Vec3 delta) { tc_transform_translate(handle_, delta); }
    void rotate(Quat delta) { tc_transform_rotate(handle_, delta); }
    void look_at(Vec3 target, Vec3 up = Vec3::up()) { tc_transform_look_at(handle_, target, up); }

    Vec3 local_to_world(Vec3 point) const { return tc_transform_local_to_world(handle_, point); }
    Vec3 world_to_local(Vec3 point) const { return tc_transform_world_to_local(handle_, point); }

    // Matrix
    Mat44 world_matrix() const {
        Mat44 m;
        tc_transform_world_matrix(handle_, &m);
        return m;
    }

    Mat44 local_matrix() const {
        Mat44 m;
        tc_transform_local_matrix(handle_, &m);
        return m;
    }

    // Dirty tracking
    bool is_dirty() const { return tc_transform_is_dirty(handle_); }
    uint32_t version() const { return tc_transform_version(handle_); }
};

// ============================================================================
// Component - base class for C++ components
// ============================================================================

class Component {
protected:
    tc_component comp_;

    static const tc_component_vtable* get_vtable();

public:
    Component() {
        tc_component_init(&comp_, get_vtable());
        comp_.data = this;
        // C++ components manage their own lifetime
        // Entity should NOT call free() on them
        comp_.is_native = false;
    }

    virtual ~Component() = default;

    tc_component* raw() { return &comp_; }
    const tc_component* raw() const { return &comp_; }

    Entity* entity() const;
    bool enabled() const { return comp_.enabled; }
    void set_enabled(bool e) { comp_.enabled = e; }

    // Override these in derived classes
    virtual const char* type_name() const { return "Component"; }
    virtual void start() {}
    virtual void update(float dt) { (void)dt; }
    virtual void fixed_update(float dt) { (void)dt; }
    virtual void before_render() {}
    virtual void on_destroy() {}
    virtual void on_added_to_entity() {}
    virtual void on_removed_from_entity() {}
};

// ============================================================================
// Entity - RAII wrapper
// ============================================================================

class Entity {
    tc_entity* handle_;
    bool owned_;

public:
    explicit Entity(tc_entity* h, bool owned = false) : handle_(h), owned_(owned) {}

    explicit Entity(const std::string& name) : handle_(tc_entity_new(name.c_str())), owned_(true) {}
    Entity(const std::string& name, const std::string& uuid)
        : handle_(tc_entity_new_with_uuid(name.c_str(), uuid.c_str())), owned_(true) {}
    Entity(GeneralPose3 pose, const std::string& name)
        : handle_(tc_entity_new_with_pose(pose, name.c_str())), owned_(true) {}

    ~Entity() {
        if (owned_ && handle_) {
            tc_entity_free(handle_);
        }
    }

    // Non-copyable, movable
    Entity(const Entity&) = delete;
    Entity& operator=(const Entity&) = delete;
    Entity(Entity&& o) noexcept : handle_(o.handle_), owned_(o.owned_) {
        o.handle_ = nullptr;
        o.owned_ = false;
    }
    Entity& operator=(Entity&& o) noexcept {
        if (this != &o) {
            if (owned_ && handle_) tc_entity_free(handle_);
            handle_ = o.handle_;
            owned_ = o.owned_;
            o.handle_ = nullptr;
            o.owned_ = false;
        }
        return *this;
    }

    tc_entity* raw() const { return handle_; }

    // Identity
    std::string_view uuid() const { return tc_entity_uuid(handle_); }
    uint64_t runtime_id() const { return tc_entity_runtime_id(handle_); }
    uint32_t pick_id() { return tc_entity_pick_id(handle_); }

    std::string_view name() const { return tc_entity_name(handle_); }
    void set_name(const std::string& n) { tc_entity_set_name(handle_, n.c_str()); }

    // Transform (non-owning reference)
    tc_transform* transform() const { return tc_entity_transform(handle_); }

    GeneralPose3 local_pose() const { return tc_entity_local_pose(handle_); }
    void set_local_pose(GeneralPose3 p) { tc_entity_set_local_pose(handle_, p); }

    GeneralPose3 global_pose() const { return tc_entity_global_pose(handle_); }
    void set_global_pose(GeneralPose3 p) { tc_entity_set_global_pose(handle_, p); }

    // Flags
    bool visible() const { return tc_entity_visible(handle_); }
    void set_visible(bool v) { tc_entity_set_visible(handle_, v); }

    bool active() const { return tc_entity_active(handle_); }
    void set_active(bool v) { tc_entity_set_active(handle_, v); }

    bool pickable() const { return tc_entity_pickable(handle_); }
    void set_pickable(bool v) { tc_entity_set_pickable(handle_, v); }

    bool selectable() const { return tc_entity_selectable(handle_); }
    void set_selectable(bool v) { tc_entity_set_selectable(handle_, v); }

    bool serializable() const { return tc_entity_serializable(handle_); }
    void set_serializable(bool v) { tc_entity_set_serializable(handle_, v); }

    int priority() const { return tc_entity_priority(handle_); }
    void set_priority(int p) { tc_entity_set_priority(handle_, p); }

    uint64_t layer() const { return tc_entity_layer(handle_); }
    void set_layer(uint64_t l) { tc_entity_set_layer(handle_, l); }

    // Components
    void add_component(Component* c) {
        tc_entity_add_component(handle_, c->raw());
    }

    void remove_component(Component* c) {
        tc_entity_remove_component(handle_, c->raw());
    }

    tc_component* get_component(const std::string& type_name) {
        return tc_entity_get_component(handle_, type_name.c_str());
    }

    template<typename T>
    T* get_component() {
        tc_component* c = get_component(T::static_type_name());
        return c ? static_cast<T*>(c->data) : nullptr;
    }

    size_t component_count() const { return tc_entity_component_count(handle_); }
    tc_component* component_at(size_t i) { return tc_entity_component_at(handle_, i); }

    // Hierarchy
    void set_parent(Entity* parent) {
        tc_entity_set_parent(handle_, parent ? parent->raw() : nullptr);
    }

    tc_entity* parent() const {
        return tc_entity_parent(handle_);
    }

    size_t children_count() const { return tc_entity_children_count(handle_); }
    tc_entity* child_at(size_t i) const { return tc_entity_child_at(handle_, i); }

    // Lifecycle
    void update(float dt) { tc_entity_update(handle_, dt); }
    void fixed_update(float dt) { tc_entity_fixed_update(handle_, dt); }
};

// ============================================================================
// EntityHandle - lazy reference
// ============================================================================

class EntityHandle {
    tc_entity_handle handle_;

public:
    EntityHandle() : handle_(tc_entity_handle_empty()) {}
    explicit EntityHandle(const std::string& uuid) : handle_(tc_entity_handle_from_uuid(uuid.c_str())) {}
    explicit EntityHandle(const Entity& e) : handle_(tc_entity_handle_from_entity(e.raw())) {}
    EntityHandle(tc_entity_handle h) : handle_(h) {}

    tc_entity* get() const { return tc_entity_handle_get(handle_); }
    bool is_valid() const { return tc_entity_handle_is_valid(handle_); }
    std::string_view uuid() const { return handle_.uuid; }

    explicit operator bool() const { return is_valid() && get() != nullptr; }
};

// ============================================================================
// Registry access
// ============================================================================

namespace registry {

inline tc_entity* find_by_uuid(const std::string& uuid) {
    return tc_entity_registry_find_by_uuid(uuid.c_str());
}

inline tc_entity* find_by_runtime_id(uint64_t id) {
    return tc_entity_registry_find_by_runtime_id(id);
}

inline tc_entity* find_by_pick_id(uint32_t id) {
    return tc_entity_registry_find_by_pick_id(id);
}

inline size_t count() {
    return tc_entity_registry_count();
}

inline tc_entity* at(size_t i) {
    return tc_entity_registry_at(i);
}

inline std::vector<tc_entity*> snapshot() {
    size_t n = count();
    std::vector<tc_entity*> result(n);
    tc_entity_registry_snapshot(result.data(), n);
    return result;
}

} // namespace registry

// ============================================================================
// Library init/shutdown
// ============================================================================

inline void init() { tc_init(); }
inline void shutdown() { tc_shutdown(); }

inline std::string generate_uuid() {
    char buf[40];
    tc_generate_uuid(buf);
    return buf;
}

inline const char* version() { return tc_version(); }

// ============================================================================
// Component vtable implementation
// ============================================================================

namespace detail {

inline void component_start(tc_component* c) {
    if (c && c->data) static_cast<Component*>(c->data)->start();
}

inline void component_update(tc_component* c, float dt) {
    if (c && c->data) static_cast<Component*>(c->data)->update(dt);
}

inline void component_fixed_update(tc_component* c, float dt) {
    if (c && c->data) static_cast<Component*>(c->data)->fixed_update(dt);
}

inline void component_before_render(tc_component* c) {
    if (c && c->data) static_cast<Component*>(c->data)->before_render();
}

inline void component_on_destroy(tc_component* c) {
    if (c && c->data) static_cast<Component*>(c->data)->on_destroy();
}

inline void component_on_added_to_entity(tc_component* c) {
    if (c && c->data) static_cast<Component*>(c->data)->on_added_to_entity();
}

inline void component_on_removed_from_entity(tc_component* c) {
    if (c && c->data) static_cast<Component*>(c->data)->on_removed_from_entity();
}

inline void component_drop(tc_component* c) {
    // tc_component is embedded in Component via comp_ member
    // When Component is deleted by C++ code, the embedded tc_component goes too
    // We just clear the pointer here
    if (c) c->data = nullptr;
}

inline const tc_component_vtable cpp_component_vtable = {
    "Component",
    component_start,
    component_update,
    component_fixed_update,
    component_before_render,
    component_on_destroy,
    component_on_added_to_entity,
    component_on_removed_from_entity,
    nullptr,  // on_added
    nullptr,  // on_removed
    nullptr,  // on_editor_start
    nullptr,  // setup_editor_defaults
    component_drop,
    nullptr,  // serialize
    nullptr   // deserialize
};

} // namespace detail

inline const tc_component_vtable* Component::get_vtable() {
    return &detail::cpp_component_vtable;
}

inline Entity* Component::entity() const {
    // Note: returns raw pointer, Entity is managed elsewhere
    return reinterpret_cast<Entity*>(comp_.entity);
}

// ============================================================================
// Macro for defining component types
// ============================================================================

#define TC_COMPONENT(ClassName) \
    static const char* static_type_name() { return #ClassName; } \
    const char* type_name() const override { return #ClassName; }

} // namespace tc
