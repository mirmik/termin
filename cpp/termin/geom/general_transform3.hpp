#pragma once

#include <vector>
#include <string>
#include <algorithm>
#include <cstdint>
#include "general_pose3.hpp"

namespace termin {
namespace geom {

struct GeneralTransform3 {
    // Core data
    GeneralPose3 _local_pose;
    std::string name;

    // Hierarchy (raw pointers, non-owning)
    GeneralTransform3* parent = nullptr;
    std::vector<GeneralTransform3*> children;

    // Cached global pose
    mutable GeneralPose3 _cached_global_pose;
    mutable bool _dirty = true;

    // Version tracking for change propagation
    uint32_t _version_for_walking_to_proximal = 0;
    uint32_t _version_for_walking_to_distal = 0;
    uint32_t _version_only_my = 0;

    // Constructors
    GeneralTransform3()
        : _local_pose(GeneralPose3::identity())
        , name("")
        , parent(nullptr)
        , _dirty(true) {}

    explicit GeneralTransform3(const GeneralPose3& local_pose, const std::string& name_ = "")
        : _local_pose(local_pose)
        , name(name_)
        , parent(nullptr)
        , _dirty(true) {}

    // Destructor - automatically unparent
    ~GeneralTransform3() {
        unparent();
        // Detach all children
        for (auto* child : children) {
            child->parent = nullptr;
        }
        children.clear();
    }

    // Disable copy (would mess up hierarchy pointers)
    GeneralTransform3(const GeneralTransform3&) = delete;
    GeneralTransform3& operator=(const GeneralTransform3&) = delete;

    // Move is allowed
    GeneralTransform3(GeneralTransform3&& other) noexcept
        : _local_pose(std::move(other._local_pose))
        , name(std::move(other.name))
        , parent(other.parent)
        , children(std::move(other.children))
        , _cached_global_pose(std::move(other._cached_global_pose))
        , _dirty(other._dirty)
        , _version_for_walking_to_proximal(other._version_for_walking_to_proximal)
        , _version_for_walking_to_distal(other._version_for_walking_to_distal)
        , _version_only_my(other._version_only_my) {
        // Update parent's children list
        if (parent) {
            auto it = std::find(parent->children.begin(), parent->children.end(), &other);
            if (it != parent->children.end()) {
                *it = this;
            }
        }
        // Update children's parent pointer
        for (auto* child : children) {
            child->parent = this;
        }
        other.parent = nullptr;
        other.children.clear();
    }

    GeneralTransform3& operator=(GeneralTransform3&& other) noexcept {
        if (this != &other) {
            unparent();
            for (auto* child : children) {
                child->parent = nullptr;
            }

            _local_pose = std::move(other._local_pose);
            name = std::move(other.name);
            parent = other.parent;
            children = std::move(other.children);
            _cached_global_pose = std::move(other._cached_global_pose);
            _dirty = other._dirty;
            _version_for_walking_to_proximal = other._version_for_walking_to_proximal;
            _version_for_walking_to_distal = other._version_for_walking_to_distal;
            _version_only_my = other._version_only_my;

            if (parent) {
                auto it = std::find(parent->children.begin(), parent->children.end(), &other);
                if (it != parent->children.end()) {
                    *it = this;
                }
            }
            for (auto* child : children) {
                child->parent = this;
            }
            other.parent = nullptr;
            other.children.clear();
        }
        return *this;
    }

    // --- Hierarchy operations ---

    void unparent() {
        if (parent) {
            auto& siblings = parent->children;
            siblings.erase(std::remove(siblings.begin(), siblings.end(), this), siblings.end());
            parent = nullptr;
            _mark_dirty();
        }
    }

    void add_child(GeneralTransform3* child) {
        if (!child || child == this) return;
        child->unparent();
        children.push_back(child);
        child->parent = this;
        child->_mark_dirty();
    }

    void set_parent(GeneralTransform3* new_parent) {
        if (new_parent == parent) return;
        if (new_parent && new_parent->_has_ancestor(this)) {
            // Would create cycle
            return;
        }
        unparent();
        if (new_parent) {
            new_parent->children.push_back(this);
            parent = new_parent;
            _mark_dirty();
        }
    }

    bool _has_ancestor(const GeneralTransform3* possible_ancestor) const {
        const GeneralTransform3* current = parent;
        while (current) {
            if (current == possible_ancestor) return true;
            current = current->parent;
        }
        return false;
    }

    // --- Pose accessors ---

    const GeneralPose3& local_pose() const { return _local_pose; }

    void set_local_pose(const GeneralPose3& pose) {
        _local_pose = pose;
        _mark_dirty();
    }

    // relocate with GeneralPose3
    void relocate(const GeneralPose3& pose) {
        _local_pose = pose;
        _mark_dirty();
    }

    // relocate with Pose3 (preserves current scale)
    void relocate(const Pose3& pose) {
        _local_pose.ang = pose.ang;
        _local_pose.lin = pose.lin;
        // scale preserved
        _mark_dirty();
    }

    const GeneralPose3& global_pose() const {
        if (_dirty) {
            if (parent) {
                _cached_global_pose = parent->global_pose() * _local_pose;
            } else {
                _cached_global_pose = _local_pose;
            }
            _dirty = false;
        }
        return _cached_global_pose;
    }

    void set_global_pose(const GeneralPose3& global_pose) {
        relocate_global(global_pose);
    }

    void relocate_global(const GeneralPose3& gpose) {
        if (parent) {
            const GeneralPose3& parent_global = parent->global_pose();
            GeneralPose3 inv_parent = parent_global.inverse();
            _local_pose = inv_parent * gpose;
        } else {
            _local_pose = gpose;
        }
        _mark_dirty();
    }

    void relocate_global(const Pose3& pose) {
        // Preserve current global scale
        Vec3 current_global_scale = global_pose().scale;
        GeneralPose3 gpose(pose.ang, pose.lin, current_global_scale);
        relocate_global(gpose);
    }

    // --- Dirty tracking ---

    bool is_dirty() const { return _dirty; }

    static uint32_t increment_version(uint32_t version) {
        return (version + 1) % ((1u << 31) - 1);
    }

    void _spread_changes_to_distal() {
        _version_for_walking_to_proximal = increment_version(_version_for_walking_to_proximal);
        _dirty = true;
        for (auto* child : children) {
            child->_spread_changes_to_distal();
        }
    }

    void _spread_changes_to_proximal() {
        _version_for_walking_to_distal = increment_version(_version_for_walking_to_distal);
        if (parent) {
            parent->_spread_changes_to_proximal();
        }
    }

    void _mark_dirty() {
        _version_only_my = increment_version(_version_only_my);
        _spread_changes_to_proximal();
        _spread_changes_to_distal();
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

    // --- Direction helpers (Y-forward convention: X=right, Y=forward, Z=up) ---

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
};

} // namespace geom
} // namespace termin
