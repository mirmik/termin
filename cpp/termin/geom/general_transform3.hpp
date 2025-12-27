#pragma once

#include <cstdint>
#include "general_pose3.hpp"
#include "../../../core_c/include/tc_transform.h"

// DLL export/import macros for Windows
#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define ENTITY_API __declspec(dllexport)
    #else
        #define ENTITY_API __declspec(dllimport)
    #endif
#else
    #define ENTITY_API
#endif

namespace termin {

class Entity;

// Thin non-owning wrapper around tc_transform*.
// Provides C++ interface with zero-cost access to C core data.
// Layout of tc_general_pose3 matches GeneralPose3 for reinterpret_cast.
struct GeneralTransform3 {
    tc_transform* _t;

    // Construct from tc_transform pointer (non-owning)
    explicit GeneralTransform3(tc_transform* t) : _t(t) {}

    // Default constructor - null transform
    GeneralTransform3() : _t(nullptr) {}

    // Check if valid
    bool valid() const { return _t != nullptr; }
    explicit operator bool() const { return valid(); }

    // --- Pose accessors (zero-copy via reinterpret_cast) ---

    const GeneralPose3& local_pose() const {
        tc_general_pose3 p = tc_transform_local_pose(_t);
        // Store in thread-local for reference return
        static thread_local GeneralPose3 cached;
        cached = *reinterpret_cast<const GeneralPose3*>(&p);
        return cached;
    }

    void set_local_pose(const GeneralPose3& pose) {
        tc_transform_set_local_pose(_t, *reinterpret_cast<const tc_general_pose3*>(&pose));
    }

    void relocate(const GeneralPose3& pose) {
        set_local_pose(pose);
    }

    void relocate(const Pose3& pose) {
        GeneralPose3 gp = local_pose();
        gp.ang = pose.ang;
        gp.lin = pose.lin;
        set_local_pose(gp);
    }

    const GeneralPose3& global_pose() const {
        tc_general_pose3 p = tc_transform_global_pose(_t);
        static thread_local GeneralPose3 cached;
        cached = *reinterpret_cast<const GeneralPose3*>(&p);
        return cached;
    }

    void set_global_pose(const GeneralPose3& pose) {
        tc_transform_set_global_pose(_t, *reinterpret_cast<const tc_general_pose3*>(&pose));
    }

    void relocate_global(const GeneralPose3& gpose) {
        set_global_pose(gpose);
    }

    void relocate_global(const Pose3& pose) {
        Vec3 current_scale = global_pose().scale;
        GeneralPose3 gp(pose.ang, pose.lin, current_scale);
        set_global_pose(gp);
    }

    // --- Hierarchy ---

    GeneralTransform3 parent() const {
        return GeneralTransform3(tc_transform_parent(_t));
    }

    void set_parent(GeneralTransform3 new_parent) {
        tc_transform_set_parent(_t, new_parent._t);
    }

    void unparent() {
        tc_transform_unparent(_t);
    }

    void add_child(GeneralTransform3 child) {
        tc_transform_add_child(_t, child._t);
    }

    size_t children_count() const {
        return tc_transform_children_count(_t);
    }

    GeneralTransform3 child_at(size_t index) const {
        return GeneralTransform3(tc_transform_child_at(_t, index));
    }

    // Iterator support for children
    struct ChildIterator {
        tc_transform* _parent;
        size_t _index;

        GeneralTransform3 operator*() const {
            return GeneralTransform3(tc_transform_child_at(_parent, _index));
        }
        ChildIterator& operator++() { ++_index; return *this; }
        bool operator!=(const ChildIterator& other) const { return _index != other._index; }
    };

    struct ChildRange {
        tc_transform* _t;
        ChildIterator begin() const { return {_t, 0}; }
        ChildIterator end() const { return {_t, tc_transform_children_count(_t)}; }
    };

    ChildRange children() const { return {_t}; }

    // --- Entity back-pointer ---

    ENTITY_API Entity* entity() const;
    ENTITY_API void set_entity(Entity* e);

    // --- Name (from entity) ---

    ENTITY_API const char* name() const;

    // --- Dirty tracking ---

    bool is_dirty() const {
        return tc_transform_is_dirty(_t);
    }

    uint32_t version() const {
        return tc_transform_version(_t);
    }

    // --- Transformations ---

    Vec3 transform_point(const Vec3& p) const {
        return global_pose().transform_point(p);
    }

    Vec3 transform_point_inverse(const Vec3& p) const {
        return global_pose().inverse_transform_point(p);
    }

    Vec3 transform_vector(const Vec3& v) const {
        return global_pose().transform_vector(v);
    }

    Vec3 transform_vector_inverse(const Vec3& v) const {
        return global_pose().inverse_transform_vector(v);
    }

    // --- Direction helpers (Y-forward convention) ---

    Vec3 forward(double distance = 1.0) const {
        return transform_vector(Vec3{0.0, distance, 0.0});
    }

    Vec3 backward(double distance = 1.0) const {
        return transform_vector(Vec3{0.0, -distance, 0.0});
    }

    Vec3 up(double distance = 1.0) const {
        return transform_vector(Vec3{0.0, 0.0, distance});
    }

    Vec3 down(double distance = 1.0) const {
        return transform_vector(Vec3{0.0, 0.0, -distance});
    }

    Vec3 right(double distance = 1.0) const {
        return transform_vector(Vec3{distance, 0.0, 0.0});
    }

    Vec3 left(double distance = 1.0) const {
        return transform_vector(Vec3{-distance, 0.0, 0.0});
    }

    // --- Matrix ---

    void world_matrix(double* m) const {
        global_pose().matrix4(m);
    }

    // --- Raw access ---

    tc_transform* raw() const { return _t; }
};

} // namespace termin
