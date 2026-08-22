#include "guard_main.h"

#include <array>
#include <cmath>
#include <cstddef>
#include <limits>
#include <resources/tc_skeleton_registry.h>
#include <string>
#include <termin/skeleton/skeleton_instance.hpp>
#include <type_traits>

static_assert(std::is_same_v<decltype(tc_bone{}.inverse_bind_matrix), tc_mat44>);
static_assert(std::is_same_v<decltype(tc_bone{}.bind_translation), tc_vec3>);
static_assert(std::is_same_v<decltype(tc_bone{}.bind_rotation), tc_quat>);
static_assert(std::is_same_v<decltype(tc_bone{}.bind_scale), tc_vec3>);
static_assert(std::is_same_v<decltype(tc_skeleton_bone_desc{}.inverse_bind_matrix), tc_mat44>);
static_assert(std::is_same_v<decltype(tc_skeleton_bone_desc{}.bind_translation), tc_vec3>);
static_assert(std::is_same_v<decltype(tc_skeleton_bone_desc{}.bind_rotation), tc_quat>);
static_assert(std::is_same_v<decltype(tc_skeleton_bone_desc{}.bind_scale), tc_vec3>);
static_assert(sizeof(tc_bone) == 280);
static_assert(alignof(tc_bone) == alignof(double));
static_assert(offsetof(tc_bone, inverse_bind_matrix) == 72);
static_assert(offsetof(tc_bone, bind_translation) == 200);
static_assert(offsetof(tc_bone, bind_rotation) == 224);
static_assert(offsetof(tc_bone, bind_scale) == 256);

namespace {
    struct BoneDescriptorStorage {
        tc_mat44 inverse_bind = tc_mat44_identity();
        tc_vec3 translation = tc_vec3_zero();
        tc_quat rotation = tc_quat_identity();
        tc_vec3 scale = tc_vec3_one();

        tc_skeleton_bone_desc descriptor(const char* name = "Replacement") const {
            return {name, -1, inverse_bind, translation, rotation, scale};
        }
    };

    struct SkeletonFixture {
        tc_bone bones[2];
        tc_skeleton skeleton{};

        SkeletonFixture() {
            tc_bone_init(&bones[0]);
            tc_bone_init(&bones[1]);
            bones[0].index = 0;
            bones[0].parent_index = -1;
            bones[0].bind_translation.x = 1.0;
            bones[1].index = 1;
            bones[1].parent_index = 0;
            bones[1].bind_translation.x = 2.0;
            skeleton.bones = bones;
            skeleton.bone_count = 2;
        }
    };

    void check_near(double actual, double expected) {
        CHECK(std::abs(actual - expected) < 1.0e-9);
    }

    struct OwnedSkeletonPayload {
        tc_skeleton skeleton{};

        OwnedSkeletonPayload() {
            const BoneDescriptorStorage storage;
            const tc_skeleton_bone_desc original = storage.descriptor("Original");
            REQUIRE(tc_skeleton_replace_bones(&skeleton, &original, 1));
            skeleton.header.version = 7;
        }

        ~OwnedSkeletonPayload() {
            (void)tc_skeleton_replace_bones(&skeleton, nullptr, 0);
        }
    };
} // namespace

TEST_CASE("SkeletonInstance evaluates a portable local pose hierarchy") {
    SkeletonFixture fixture;
    termin::SkeletonInstance instance(&fixture.skeleton);

    REQUIRE_EQ(instance.bone_count(), 2);
    check_near(instance.get_bone_world_matrix(0)(3, 0), 1.0);
    check_near(instance.get_bone_world_matrix(1)(3, 0), 3.0);
    check_near(instance.get_bone_matrix(1)(3, 0), 3.0);

    const termin::Vec3 child_translation{4.0, 0.0, 0.0};
    instance.set_bone_transform(1, &child_translation, nullptr, nullptr);
    instance.update();
    check_near(instance.get_bone_world_matrix(1)(3, 0), 5.0);
}

TEST_CASE("SkeletonInstance accepts scene-neutral externally evaluated matrices") {
    SkeletonFixture fixture;
    termin::SkeletonInstance instance(&fixture.skeleton);
    std::vector<termin::Mat44> bone_world = {
        termin::Mat44::translation(11.0, 0.0, 0.0),
        termin::Mat44::translation(13.0, 0.0, 0.0),
    };

    REQUIRE(instance.update_from_world_matrices(termin::Mat44::translation(10.0, 0.0, 0.0), bone_world));
    check_near(instance.get_bone_matrix(0)(3, 0), 1.0);
    check_near(instance.get_bone_matrix(1)(3, 0), 3.0);
}

TEST_CASE("SkeletonInstance rejects resource count changes before accessing stale derived storage") {
    OwnedSkeletonPayload payload;
    termin::SkeletonInstance instance(&payload.skeleton);

    const std::array<BoneDescriptorStorage, 2> storage;
    std::array<tc_skeleton_bone_desc, 2> descriptors = {
        storage[0].descriptor("Root"),
        storage[1].descriptor("Child"),
    };
    descriptors[1].parent_index = 0;
    REQUIRE(tc_skeleton_replace_bones(&payload.skeleton, descriptors.data(), descriptors.size()));

    const std::vector<termin::Mat44> world_matrices(2, termin::Mat44::identity());
    CHECK(!instance.update_from_world_matrices(termin::Mat44::identity(), world_matrices));

    std::array<float, 32> output;
    output.fill(-17.0f);
    instance.get_bone_matrices_float(output.data());
    for (float value : output) {
        CHECK_EQ(value, -17.0f);
    }
}

TEST_CASE("skeleton replacement normalizes full-range finite rotations") {
    OwnedSkeletonPayload payload;
    BoneDescriptorStorage storage;
    const double largest = std::numeric_limits<double>::max();
    storage.rotation = {largest, largest, largest, largest};
    const tc_skeleton_bone_desc descriptor = storage.descriptor("Scaled");

    REQUIRE(tc_skeleton_replace_bones(&payload.skeleton, &descriptor, 1));
    REQUIRE_EQ(payload.skeleton.header.version, 8u);
    REQUIRE_EQ(payload.skeleton.bone_count, 1u);
    CHECK_EQ(std::string(payload.skeleton.bones[0].name), std::string("Scaled"));
    check_near(payload.skeleton.bones[0].bind_rotation.x, 0.5);
    check_near(payload.skeleton.bones[0].bind_rotation.y, 0.5);
    check_near(payload.skeleton.bones[0].bind_rotation.z, 0.5);
    check_near(payload.skeleton.bones[0].bind_rotation.w, 0.5);
}

TEST_CASE("skeleton replacement rejects invalid rotations transactionally") {
    OwnedSkeletonPayload payload;
    BoneDescriptorStorage storage;
    const tc_bone* original_bones = payload.skeleton.bones;
    const int32_t* original_roots = payload.skeleton.root_indices;
    const uint32_t original_version = payload.skeleton.header.version;

    const std::array<tc_quat, 3> invalid_rotations = {{
        {0.0, 0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0, std::numeric_limits<double>::quiet_NaN()},
        {0.0, 0.0, 0.0, std::numeric_limits<double>::infinity()},
    }};
    for (const auto& rotation : invalid_rotations) {
        storage.rotation = rotation;
        storage.translation = tc_vec3{9.0, 8.0, 7.0};
        const tc_skeleton_bone_desc descriptor = storage.descriptor("Rejected");

        CHECK(!tc_skeleton_replace_bones(&payload.skeleton, &descriptor, 1));
        CHECK(payload.skeleton.bones == original_bones);
        CHECK(payload.skeleton.root_indices == original_roots);
        CHECK_EQ(payload.skeleton.header.version, original_version);
        CHECK_EQ(std::string(payload.skeleton.bones[0].name), std::string("Original"));
        check_near(payload.skeleton.bones[0].bind_translation.x, 0.0);
    }
}

TEST_CASE("skeleton replacement rejects non-finite matrices and vectors transactionally") {
    OwnedSkeletonPayload payload;
    const tc_bone* original_bones = payload.skeleton.bones;
    const int32_t* original_roots = payload.skeleton.root_indices;
    const uint32_t original_version = payload.skeleton.header.version;

    std::array<BoneDescriptorStorage, 3> invalid_values;
    invalid_values[0].inverse_bind.m[5] = std::numeric_limits<double>::infinity();
    invalid_values[1].translation.y = std::numeric_limits<double>::quiet_NaN();
    invalid_values[2].scale.z = std::numeric_limits<double>::infinity();

    for (const BoneDescriptorStorage& storage : invalid_values) {
        const tc_skeleton_bone_desc descriptor = storage.descriptor("Rejected");
        CHECK(!tc_skeleton_replace_bones(&payload.skeleton, &descriptor, 1));
        CHECK(payload.skeleton.bones == original_bones);
        CHECK(payload.skeleton.root_indices == original_roots);
        CHECK_EQ(payload.skeleton.header.version, original_version);
        CHECK_EQ(std::string(payload.skeleton.bones[0].name), std::string("Original"));
    }
}

TEST_CASE("SkeletonInstance applies checked bone transforms transactionally") {
    SkeletonFixture fixture;
    termin::SkeletonInstance instance(&fixture.skeleton);
    const termin::Vec3 original_translation{2.0, 3.0, 4.0};
    const termin::Quat original_rotation{0.0, 0.0, 0.0, 2.0};
    const termin::Vec3 original_scale{1.0, 2.0, 3.0};
    REQUIRE(instance.try_set_bone_transform(0, &original_translation, &original_rotation, &original_scale));
    const termin::GeneralPose3 expected = instance.local_pose(0);

    const termin::Vec3 rejected_translation{9.0, 8.0, 7.0};
    const termin::Vec3 rejected_scale{4.0, 5.0, 6.0};
    const std::array<termin::Quat, 3> invalid_rotations = {{
        {0.0, 0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0, std::numeric_limits<double>::quiet_NaN()},
        {0.0, 0.0, 0.0, std::numeric_limits<double>::infinity()},
    }};
    for (const auto& rotation : invalid_rotations) {
        CHECK(!instance.try_set_bone_transform(0, &rejected_translation, &rotation, &rejected_scale));
        const termin::GeneralPose3& actual = instance.local_pose(0);
        check_near(actual.lin.x, expected.lin.x);
        check_near(actual.lin.y, expected.lin.y);
        check_near(actual.lin.z, expected.lin.z);
        check_near(actual.ang.x, expected.ang.x);
        check_near(actual.ang.y, expected.ang.y);
        check_near(actual.ang.z, expected.ang.z);
        check_near(actual.ang.w, expected.ang.w);
        check_near(actual.scale.x, expected.scale.x);
        check_near(actual.scale.y, expected.scale.y);
        check_near(actual.scale.z, expected.scale.z);
    }

    termin::Vec3 non_finite_translation = rejected_translation;
    non_finite_translation.x = std::numeric_limits<double>::quiet_NaN();
    CHECK(!instance.try_set_bone_transform(0, &non_finite_translation, nullptr, nullptr));
    termin::Vec3 non_finite_scale = rejected_scale;
    non_finite_scale.z = std::numeric_limits<double>::infinity();
    CHECK(!instance.try_set_bone_transform(0, nullptr, nullptr, &non_finite_scale));
    const termin::GeneralPose3& preserved = instance.local_pose(0);
    check_near(preserved.lin.x, expected.lin.x);
    check_near(preserved.ang.w, expected.ang.w);
    check_near(preserved.scale.z, expected.scale.z);

    const double largest = std::numeric_limits<double>::max();
    const termin::Quat full_range_rotation{largest, largest, largest, largest};
    REQUIRE(instance.try_set_bone_transform(0, nullptr, &full_range_rotation, nullptr));
    const termin::Quat& normalized = instance.local_pose(0).ang;
    check_near(normalized.x, 0.5);
    check_near(normalized.y, 0.5);
    check_near(normalized.z, 0.5);
    check_near(normalized.w, 0.5);
}

GUARD_TEST_MAIN();
