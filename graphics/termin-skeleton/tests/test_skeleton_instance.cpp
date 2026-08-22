#include "guard_main.h"

#include <array>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <resources/tc_skeleton_registry.h>
#include <string>
#include <termin/skeleton/skeleton_instance.hpp>

namespace {
    struct SkeletonFixture {
        tc_bone bones[2];
        tc_skeleton skeleton{};

        SkeletonFixture() {
            tc_bone_init(&bones[0]);
            tc_bone_init(&bones[1]);
            bones[0].index = 0;
            bones[0].parent_index = -1;
            bones[0].bind_translation[0] = 1.0;
            bones[1].index = 1;
            bones[1].parent_index = 0;
            bones[1].bind_translation[0] = 2.0;
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
            skeleton.bones = static_cast<tc_bone*>(std::calloc(1, sizeof(tc_bone)));
            skeleton.root_indices = static_cast<int32_t*>(std::malloc(sizeof(int32_t)));
            REQUIRE(skeleton.bones != nullptr);
            REQUIRE(skeleton.root_indices != nullptr);
            tc_bone_init(skeleton.bones);
            std::memcpy(skeleton.bones[0].name, "Original", sizeof("Original"));
            skeleton.bones[0].index = 0;
            skeleton.bones[0].parent_index = -1;
            skeleton.root_indices[0] = 0;
            skeleton.bone_count = 1;
            skeleton.root_count = 1;
            skeleton.header.version = 7;
        }

        ~OwnedSkeletonPayload() {
            std::free(skeleton.bones);
            std::free(skeleton.root_indices);
        }
    };

    struct BoneDescriptorStorage {
        std::array<double, 16> inverse_bind = {
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            0.0,
            0.0,
            1.0,
        };
        std::array<double, 3> translation = {0.0, 0.0, 0.0};
        std::array<double, 4> rotation = {0.0, 0.0, 0.0, 1.0};
        std::array<double, 3> scale = {1.0, 1.0, 1.0};

        tc_skeleton_bone_desc descriptor(const char* name = "Replacement") const {
            return {name, -1, inverse_bind.data(), translation.data(), rotation.data(), scale.data()};
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

    const double child_translation[3] = {4.0, 0.0, 0.0};
    instance.set_bone_transform(1, child_translation, nullptr, nullptr);
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

TEST_CASE("skeleton replacement normalizes full-range finite rotations") {
    OwnedSkeletonPayload payload;
    BoneDescriptorStorage storage;
    storage.rotation.fill(std::numeric_limits<double>::max());
    const tc_skeleton_bone_desc descriptor = storage.descriptor("Scaled");

    REQUIRE(tc_skeleton_replace_bones(&payload.skeleton, &descriptor, 1));
    REQUIRE_EQ(payload.skeleton.header.version, 8u);
    REQUIRE_EQ(payload.skeleton.bone_count, 1u);
    CHECK_EQ(std::string(payload.skeleton.bones[0].name), std::string("Scaled"));
    check_near(payload.skeleton.bones[0].bind_rotation[0], 0.5);
    check_near(payload.skeleton.bones[0].bind_rotation[1], 0.5);
    check_near(payload.skeleton.bones[0].bind_rotation[2], 0.5);
    check_near(payload.skeleton.bones[0].bind_rotation[3], 0.5);
}

TEST_CASE("skeleton replacement rejects invalid rotations transactionally") {
    OwnedSkeletonPayload payload;
    BoneDescriptorStorage storage;
    const tc_bone* original_bones = payload.skeleton.bones;
    const int32_t* original_roots = payload.skeleton.root_indices;
    const uint32_t original_version = payload.skeleton.header.version;

    const std::array<std::array<double, 4>, 3> invalid_rotations = {{
        {0.0, 0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0, std::numeric_limits<double>::quiet_NaN()},
        {0.0, 0.0, 0.0, std::numeric_limits<double>::infinity()},
    }};
    for (const auto& rotation : invalid_rotations) {
        storage.rotation = rotation;
        storage.translation = {9.0, 8.0, 7.0};
        const tc_skeleton_bone_desc descriptor = storage.descriptor("Rejected");

        CHECK(!tc_skeleton_replace_bones(&payload.skeleton, &descriptor, 1));
        CHECK(payload.skeleton.bones == original_bones);
        CHECK(payload.skeleton.root_indices == original_roots);
        CHECK_EQ(payload.skeleton.header.version, original_version);
        CHECK_EQ(std::string(payload.skeleton.bones[0].name), std::string("Original"));
        check_near(payload.skeleton.bones[0].bind_translation[0], 0.0);
    }
}

TEST_CASE("SkeletonInstance applies checked bone transforms transactionally") {
    SkeletonFixture fixture;
    termin::SkeletonInstance instance(&fixture.skeleton);
    const double original_translation[3] = {2.0, 3.0, 4.0};
    const double original_rotation[4] = {0.0, 0.0, 0.0, 2.0};
    const double original_scale[3] = {1.0, 2.0, 3.0};
    REQUIRE(instance.try_set_bone_transform(0, original_translation, original_rotation, original_scale));
    const termin::GeneralPose3 expected = instance.local_pose(0);

    const double rejected_translation[3] = {9.0, 8.0, 7.0};
    const double rejected_scale[3] = {4.0, 5.0, 6.0};
    const std::array<std::array<double, 4>, 3> invalid_rotations = {{
        {0.0, 0.0, 0.0, 0.0},
        {0.0, 0.0, 0.0, std::numeric_limits<double>::quiet_NaN()},
        {0.0, 0.0, 0.0, std::numeric_limits<double>::infinity()},
    }};
    for (const auto& rotation : invalid_rotations) {
        CHECK(!instance.try_set_bone_transform(0, rejected_translation, rotation.data(), rejected_scale));
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

    const double largest = std::numeric_limits<double>::max();
    const double full_range_rotation[4] = {largest, largest, largest, largest};
    REQUIRE(instance.try_set_bone_transform(0, nullptr, full_range_rotation, nullptr));
    const termin::Quat& normalized = instance.local_pose(0).ang;
    check_near(normalized.x, 0.5);
    check_near(normalized.y, 0.5);
    check_near(normalized.z, 0.5);
    check_near(normalized.w, 0.5);
}

GUARD_TEST_MAIN();
