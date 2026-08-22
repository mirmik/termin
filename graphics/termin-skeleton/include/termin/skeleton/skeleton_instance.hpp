#pragma once

#include <cstdint>
#include <string>
#include <termin/geom/general_pose3.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/skeleton/tc_skeleton_handle.hpp>
#include <termin/skeleton/termin_skeleton_api.hpp>
#include <vector>

namespace termin {

    // Scene-neutral mutable skeleton pose and skinning-matrix runtime.
    //
    // The instance owns only local bone poses and derived matrices. Scene/ECS
    // adapters may feed externally evaluated world matrices through
    // update_from_world_matrices(), but no Entity contract leaks into this
    // Graphics-owned type.
    class TERMIN_SKELETON_API SkeletonInstance {
    public:
        static constexpr int MAX_BONES = 128;

    private:
        // The generation handle is strong-owned. Pool addresses are deliberately
        // unstable and are resolved afresh for every public operation.
        TcSkeleton _skeleton;
        uint32_t _observed_skeleton_version = 0;
        bool _has_observed_skeleton_version = false;
        std::vector<GeneralPose3> _local_poses;
        std::vector<Mat44> _bone_world_matrices;
        std::vector<Mat44> _bone_matrices;

    public:
        SkeletonInstance() = default;
        explicit SkeletonInstance(const TcSkeleton& skeleton);
        SkeletonInstance(const SkeletonInstance&) = default;
        SkeletonInstance(SkeletonInstance&&) noexcept = default;
        SkeletonInstance& operator=(const SkeletonInstance&) = default;
        SkeletonInstance& operator=(SkeletonInstance&&) noexcept = default;

        // Owning copy for public consumers and a handle-only reference for
        // internal identity comparisons. Neither exposes a pool address.
        TcSkeleton skeleton() const {
            return _skeleton;
        }
        const TcSkeleton& skeleton_resource() const {
            return _skeleton;
        }
        void set_skeleton(const TcSkeleton& skeleton);

        // Refresh from a replaced resource payload when its version changes.
        // Refresh intentionally resets all local overrides to the new bind pose.
        bool synchronize();
        bool reset_to_bind_pose();

        const GeneralPose3& local_pose(int bone_index);

        // Validate and atomically apply the supplied transform components.
        // Rotations may have any finite non-zero scale and are stored normalized.
        bool try_set_bone_transform(int bone_index, const Vec3* translation, const Quat* rotation, const Vec3* scale);

        // Logging entry point. Invalid input leaves the current local pose
        // unchanged.
        void set_bone_transform(int bone_index, const Vec3* translation, const Quat* rotation, const Vec3* scale);

        bool try_set_bone_transform_by_name(const std::string& bone_name,
                                            const Vec3* translation,
                                            const Quat* rotation,
                                            const Vec3* scale);

        void set_bone_transform_by_name(const std::string& bone_name,
                                        const Vec3* translation,
                                        const Quat* rotation,
                                        const Vec3* scale);

        // Evaluate world and skinning matrices from the owned local pose.
        bool update();

        // Evaluate skinning matrices from world matrices supplied by a host
        // adapter. The matrices must follow skeleton bone order.
        bool update_from_world_matrices(const Mat44& skinning_root_world,
                                        const std::vector<Mat44>& bone_world_matrices);

        bool get_bone_matrices_float(float* out);
        int bone_count();
        const Mat44& get_bone_world_matrix(int bone_index);
        const Mat44& get_bone_matrix(int bone_index);

    private:
        void clear_runtime_state();
        bool resolve(const char* operation, const tc_skeleton** out_skeleton);
        bool synchronize_resolved(const tc_skeleton& skeleton, const char* operation);
        bool reset_to_bind_pose_resolved(const tc_skeleton& skeleton);
        bool evaluate_local_pose(const tc_skeleton& skeleton);
        bool evaluate_world_matrix(const tc_skeleton& skeleton, int bone_index, std::vector<unsigned char>& state);
    };

} // namespace termin
