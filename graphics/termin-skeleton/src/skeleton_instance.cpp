#include <tcbase/tc_log.hpp>
#include <termin/skeleton/skeleton_instance.hpp>

namespace termin {
    namespace {
        const GeneralPose3& identity_pose() {
            static const GeneralPose3 value = GeneralPose3::identity();
            return value;
        }

        const Mat44& identity_matrix() {
            static const Mat44 value = Mat44::identity();
            return value;
        }
    } // namespace

    SkeletonInstance::SkeletonInstance(const TcSkeleton& skeleton) {
        set_skeleton(skeleton);
    }

    void SkeletonInstance::set_skeleton(const TcSkeleton& skeleton) {
        if (_skeleton.refers_to(skeleton)) {
            (void)synchronize();
            return;
        }

        _skeleton = skeleton;
        clear_runtime_state();
        (void)synchronize();
    }

    void SkeletonInstance::clear_runtime_state() {
        _observed_skeleton_version = 0;
        _has_observed_skeleton_version = false;
        _local_poses.clear();
        _bone_world_matrices.clear();
        _bone_matrices.clear();
    }

    bool SkeletonInstance::resolve(const char* operation, const tc_skeleton** out_skeleton) {
        *out_skeleton = nullptr;
        if (!_skeleton.has_handle()) {
            clear_runtime_state();
            return true;
        }

        const tc_skeleton* skeleton = _skeleton.get();
        if (!skeleton) {
            const tc_skeleton_handle handle = _skeleton.native_handle();
            tc::Log::error("[SkeletonInstance::%s] skeleton handle index=%u generation=%u is stale",
                           operation,
                           handle.index,
                           handle.generation);
            clear_runtime_state();
            return false;
        }
        if (skeleton->bone_count > 0 && !skeleton->bones) {
            tc::Log::error("[SkeletonInstance::%s] skeleton '%s' has %zu bones but no bone payload",
                           operation,
                           skeleton->header.uuid,
                           skeleton->bone_count);
            clear_runtime_state();
            return false;
        }

        *out_skeleton = skeleton;
        return true;
    }

    bool SkeletonInstance::synchronize_resolved(const tc_skeleton& skeleton, const char* operation) {
        const size_t count = skeleton.bone_count;
        const uint32_t previous_version = _observed_skeleton_version;
        const uint32_t current_version = skeleton.header.version;
        const bool version_changed = _has_observed_skeleton_version && previous_version != current_version;
        const bool storage_changed =
            _local_poses.size() != count || _bone_world_matrices.size() != count || _bone_matrices.size() != count;
        if (_has_observed_skeleton_version && !version_changed && !storage_changed)
            return true;

        // Logging invokes a public callback that may replace this payload or
        // grow the registry pool. Snapshot diagnostics, emit them before
        // committing the refresh, then resolve the handle again so the runtime
        // state is always rebuilt from the latest version.
        const bool report_storage_change = _has_observed_skeleton_version && storage_changed;
        const std::string skeleton_uuid = skeleton.header.uuid;
        if (version_changed) {
            tc::Log::info(
                "[SkeletonInstance::%s] skeleton '%s' changed from version %u to %u; resetting local pose to bind pose",
                operation,
                skeleton_uuid.c_str(),
                previous_version,
                current_version);
        } else if (report_storage_change) {
            tc::Log::warn("[SkeletonInstance::%s] skeleton '%s' runtime storage did not match bone_count=%zu; "
                          "rebuilding bind pose",
                          operation,
                          skeleton_uuid.c_str(),
                          count);
        }

        const tc_skeleton* latest_skeleton = nullptr;
        if (!resolve(operation, &latest_skeleton))
            return false;
        if (!latest_skeleton)
            return true;
        return reset_to_bind_pose_resolved(*latest_skeleton);
    }

    bool SkeletonInstance::synchronize() {
        const tc_skeleton* skeleton = nullptr;
        if (!resolve("synchronize", &skeleton))
            return false;
        if (!skeleton)
            return true;
        return synchronize_resolved(*skeleton, "synchronize");
    }

    bool SkeletonInstance::reset_to_bind_pose_resolved(const tc_skeleton& skeleton) {
        const size_t count = skeleton.bone_count;
        _local_poses.assign(count, GeneralPose3::identity());
        _bone_world_matrices.assign(count, Mat44::identity());
        _bone_matrices.assign(count, Mat44::identity());
        for (size_t i = 0; i < count; ++i) {
            const tc_bone& bone = skeleton.bones[i];
            _local_poses[i] = GeneralPose3(bone.bind_rotation, bone.bind_translation, bone.bind_scale);
        }

        _observed_skeleton_version = skeleton.header.version;
        _has_observed_skeleton_version = true;
        return evaluate_local_pose(skeleton);
    }

    bool SkeletonInstance::reset_to_bind_pose() {
        const tc_skeleton* skeleton = nullptr;
        if (!resolve("reset_to_bind_pose", &skeleton))
            return false;
        if (!skeleton)
            return true;
        return reset_to_bind_pose_resolved(*skeleton);
    }

    const GeneralPose3& SkeletonInstance::local_pose(int bone_index) {
        if (!synchronize())
            return identity_pose();
        if (bone_index >= 0 && bone_index < static_cast<int>(_local_poses.size()))
            return _local_poses[static_cast<size_t>(bone_index)];
        tc::Log::warn("[SkeletonInstance::local_pose] invalid bone_index=%d", bone_index);
        return identity_pose();
    }

    bool SkeletonInstance::try_set_bone_transform(int bone_index,
                                                  const Vec3* translation,
                                                  const Quat* rotation,
                                                  const Vec3* scale) {
        if (!synchronize())
            return false;
        if (bone_index < 0 || bone_index >= static_cast<int>(_local_poses.size())) {
            tc::Log::warn("[SkeletonInstance::set_bone_transform] invalid bone_index=%d", bone_index);
            return false;
        }

        GeneralPose3 candidate = _local_poses[static_cast<size_t>(bone_index)];
        if (translation) {
            if (!translation->is_finite()) {
                tc::Log::warn("[SkeletonInstance::set_bone_transform] translation for bone_index=%d is not finite",
                              bone_index);
                return false;
            }
            candidate.lin = *translation;
        }
        if (rotation) {
            Quat normalized;
            if (!rotation->try_normalized(normalized, 0.0)) {
                tc::Log::warn(
                    "[SkeletonInstance::set_bone_transform] rotation for bone_index=%d must be finite and non-zero",
                    bone_index);
                return false;
            }
            candidate.ang = normalized;
        }
        if (scale) {
            if (!scale->is_finite()) {
                tc::Log::warn("[SkeletonInstance::set_bone_transform] scale for bone_index=%d is not finite",
                              bone_index);
                return false;
            }
            candidate.scale = *scale;
        }

        _local_poses[static_cast<size_t>(bone_index)] = candidate;
        return true;
    }

    void SkeletonInstance::set_bone_transform(int bone_index,
                                              const Vec3* translation,
                                              const Quat* rotation,
                                              const Vec3* scale) {
        (void)try_set_bone_transform(bone_index, translation, rotation, scale);
    }

    bool SkeletonInstance::try_set_bone_transform_by_name(const std::string& bone_name,
                                                          const Vec3* translation,
                                                          const Quat* rotation,
                                                          const Vec3* scale) {
        if (!synchronize())
            return false;

        const tc_skeleton* skeleton = nullptr;
        if (!resolve("set_bone_transform_by_name", &skeleton))
            return false;
        if (!skeleton) {
            tc::Log::warn("[SkeletonInstance::set_bone_transform_by_name] skeleton is empty");
            return false;
        }
        const int index = tc_skeleton_find_bone(skeleton, bone_name.c_str());
        if (index < 0) {
            tc::Log::warn("[SkeletonInstance::set_bone_transform_by_name] unknown bone '%s'", bone_name.c_str());
            return false;
        }
        return try_set_bone_transform(index, translation, rotation, scale);
    }

    void SkeletonInstance::set_bone_transform_by_name(const std::string& bone_name,
                                                      const Vec3* translation,
                                                      const Quat* rotation,
                                                      const Vec3* scale) {
        (void)try_set_bone_transform_by_name(bone_name, translation, rotation, scale);
    }

    bool SkeletonInstance::evaluate_world_matrix(const tc_skeleton& skeleton,
                                                 int bone_index,
                                                 std::vector<unsigned char>& state) {
        if (bone_index < 0 || static_cast<size_t>(bone_index) >= skeleton.bone_count)
            return false;

        const size_t index = static_cast<size_t>(bone_index);
        if (state[index] == 2)
            return true;
        if (state[index] == 1) {
            tc::Log::error("[SkeletonInstance::update] skeleton contains a parent cycle at bone %d", bone_index);
            return false;
        }
        state[index] = 1;

        const GeneralPose3& local_pose = _local_poses[index];
        const Mat44 local = Mat44::compose(local_pose.lin, local_pose.ang, local_pose.scale);
        const int parent_index = skeleton.bones[index].parent_index;
        if (parent_index >= 0) {
            if (!evaluate_world_matrix(skeleton, parent_index, state)) {
                tc::Log::error("[SkeletonInstance::update] bone %zu has invalid parent_index=%d", index, parent_index);
                return false;
            }
            _bone_world_matrices[index] = _bone_world_matrices[static_cast<size_t>(parent_index)] * local;
        } else {
            _bone_world_matrices[index] = local;
        }

        state[index] = 2;
        return true;
    }

    bool SkeletonInstance::evaluate_local_pose(const tc_skeleton& skeleton) {
        const size_t count = skeleton.bone_count;
        if (_local_poses.size() != count || _bone_world_matrices.size() != count || _bone_matrices.size() != count) {
            tc::Log::error("[SkeletonInstance::update] runtime storage does not match skeleton bone_count=%zu", count);
            return false;
        }

        std::vector<unsigned char> state(count, 0);
        for (size_t i = 0; i < count; ++i) {
            if (!evaluate_world_matrix(skeleton, static_cast<int>(i), state))
                return false;
        }
        for (size_t i = 0; i < count; ++i) {
            _bone_matrices[i] = _bone_world_matrices[i] * Mat44::from_tc_mat44(skeleton.bones[i].inverse_bind_matrix);
        }
        return true;
    }

    bool SkeletonInstance::update() {
        if (!synchronize())
            return false;

        const tc_skeleton* skeleton = nullptr;
        if (!resolve("update", &skeleton))
            return false;
        if (!skeleton)
            return true;
        return evaluate_local_pose(*skeleton);
    }

    bool SkeletonInstance::update_from_world_matrices(const Mat44& skinning_root_world,
                                                      const std::vector<Mat44>& bone_world_matrices) {
        if (!synchronize())
            return false;

        const tc_skeleton* skeleton = nullptr;
        if (!resolve("update_from_world_matrices", &skeleton))
            return false;
        if (!skeleton) {
            tc::Log::error("[SkeletonInstance::update_from_world_matrices] skeleton is empty");
            return false;
        }
        if (bone_world_matrices.size() != skeleton->bone_count) {
            tc::Log::error(
                "[SkeletonInstance::update_from_world_matrices] matrix count=%zu does not match bone_count=%zu",
                bone_world_matrices.size(),
                skeleton->bone_count);
            return false;
        }

        _bone_world_matrices = bone_world_matrices;
        const Mat44 root_inverse = skinning_root_world.inverse();
        for (size_t i = 0; i < skeleton->bone_count; ++i) {
            _bone_matrices[i] =
                root_inverse * _bone_world_matrices[i] * Mat44::from_tc_mat44(skeleton->bones[i].inverse_bind_matrix);
        }
        return true;
    }

    bool SkeletonInstance::get_bone_matrices_float(float* out) {
        if (!out) {
            tc::Log::error("[SkeletonInstance::get_bone_matrices_float] output is null");
            return false;
        }
        if (!synchronize())
            return false;
        for (size_t i = 0; i < _bone_matrices.size(); ++i) {
            for (int j = 0; j < 16; ++j)
                out[i * 16 + static_cast<size_t>(j)] = static_cast<float>(_bone_matrices[i].data[j]);
        }
        return true;
    }

    int SkeletonInstance::bone_count() {
        if (!synchronize())
            return 0;
        return static_cast<int>(_local_poses.size());
    }

    const Mat44& SkeletonInstance::get_bone_world_matrix(int bone_index) {
        if (!synchronize())
            return identity_matrix();
        if (bone_index >= 0 && bone_index < static_cast<int>(_bone_world_matrices.size()))
            return _bone_world_matrices[static_cast<size_t>(bone_index)];
        tc::Log::warn("[SkeletonInstance::get_bone_world_matrix] invalid bone_index=%d", bone_index);
        return identity_matrix();
    }

    const Mat44& SkeletonInstance::get_bone_matrix(int bone_index) {
        if (!synchronize())
            return identity_matrix();
        if (bone_index >= 0 && bone_index < static_cast<int>(_bone_matrices.size()))
            return _bone_matrices[static_cast<size_t>(bone_index)];
        tc::Log::warn("[SkeletonInstance::get_bone_matrix] invalid bone_index=%d", bone_index);
        return identity_matrix();
    }

} // namespace termin
