#pragma once

#include <vector>
#include <array>
#include <string>

#include "termin/skeleton/skeleton_data.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/entity/entity.hpp"

namespace termin {

// Runtime skeleton state that references Entity transforms.
//
// Instead of storing its own bone transforms, reads world transforms
// directly from Entity hierarchy. Animation updates Entity transforms,
// and this class computes bone matrices for GPU.
//
// Bone matrices are computed in skeleton-local space (not world space),
// so that u_model can be applied uniformly as with non-skinned meshes.
class SkeletonInstance {
public:
    static constexpr int MAX_BONES = 128;

    // Data
    SkeletonData* _data = nullptr;
    std::vector<Entity> _bone_entities;
    Entity _skeleton_root;

private:
    // Computed matrices
    std::vector<Mat44> _bone_matrices;

public:
    SkeletonInstance() = default;

    SkeletonInstance(
        SkeletonData* skeleton_data,
        std::vector<Entity> bone_entities,
        Entity skeleton_root
    );

    // Accessors
    SkeletonData* skeleton_data() const { return _data; }
    void set_skeleton_data(SkeletonData* data);

    const std::vector<Entity>& bone_entities() const { return _bone_entities; }
    void set_bone_entities(std::vector<Entity> entities);

    Entity skeleton_root() const { return _skeleton_root; }
    void set_skeleton_root(Entity root) { _skeleton_root = root; }

    Entity get_bone_entity(int bone_index) const;
    Entity get_bone_entity_by_name(const std::string& bone_name) const;

    /**
     * Set local transform for a bone by name.
     */
    void set_bone_transform_by_name(
        const std::string& bone_name,
        const double* translation,  // 3 doubles or nullptr
        const double* rotation,     // 4 doubles (xyzw) or nullptr
        const double* scale         // 3 doubles or nullptr
    );

    /**
     * Recompute bone matrices from Entity world transforms.
     *
     * Computes: inv(skeleton_world) @ bone_world @ inverse_bind_matrix
     */
    void update();

    /**
     * Get bone matrices for GPU upload.
     * Copies to float array (bone_count * 16 floats).
     */
    void get_bone_matrices_float(float* out) const;

    /**
     * Get number of bones.
     */
    int bone_count() const;

    /**
     * Get world matrix for a specific bone.
     */
    Mat44 get_bone_world_matrix(int bone_index) const;

    /**
     * Get computed bone matrix at index.
     */
    const Mat44& get_bone_matrix(int bone_index) const;

private:
    Entity find_skeleton_root();
};

} // namespace termin
