#include "guard_main.h"

#include <array>
#include <cmath>
#include <cstddef>
#include <limits>
#include <memory>
#include <resources/tc_skeleton_registry.h>
#include <stdexcept>
#include <string>
#include <tcbase/tc_log.h>
#include <termin/skeleton/skeleton_instance.hpp>
#include <type_traits>
#include <utility>
#include <vector>

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

    void check_near(double actual, double expected) {
        CHECK(std::abs(actual - expected) < 1.0e-9);
    }

    tc_mat44 translation_matrix(double x, double y = 0.0, double z = 0.0) {
        tc_mat44 result = tc_mat44_identity();
        result.m[12] = x;
        result.m[13] = y;
        result.m[14] = z;
        return result;
    }

    termin::TcSkeleton
    create_skeleton(const std::string& name, const tc_skeleton_bone_desc* descriptors, size_t count) {
        termin::TcSkeleton skeleton = termin::TcSkeleton::create(name);
        if (!skeleton.is_valid())
            throw std::runtime_error("failed to create test skeleton");
        if (!skeleton.replace_bones(descriptors, count))
            throw std::runtime_error("failed to populate test skeleton");
        return skeleton;
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

    struct PoolGrowingSkeletonLoader {
        std::string expected_uuid;
        std::vector<termin::TcSkeleton> created_resources;
        bool invoked = false;
        bool received_expected_uuid = false;
    };

    bool grow_skeleton_pool_loader(const char* uuid, void* user_data) {
        auto* loader = static_cast<PoolGrowingSkeletonLoader*>(user_data);
        loader->invoked = true;
        loader->received_expected_uuid = uuid && loader->expected_uuid == uuid;
        loader->created_resources.reserve(80);
        for (int index = 0; index < 80; ++index) {
            termin::TcSkeleton resource = termin::TcSkeleton::create("LazyLoadGrowth" + std::to_string(index));
            if (!resource.is_valid())
                return false;
            loader->created_resources.emplace_back(std::move(resource));
        }
        return loader->received_expected_uuid;
    }

    struct ResourceLoaderScope {
        ~ResourceLoaderScope() {
            tc_resource_clear_loader();
        }
    };

    struct PoolGrowingLogCallback {
        std::vector<std::string> resource_names;
        std::vector<termin::TcSkeleton> created_resources;
        termin::TcSkeleton* replacement_target = nullptr;
        const tc_skeleton_bone_desc* replacement_bones = nullptr;
        size_t replacement_bone_count = 0;
        bool invoked = false;
        bool succeeded = true;
    };

    PoolGrowingLogCallback* g_pool_growing_log_callback = nullptr;

    void grow_skeleton_pool_on_log(tc_log_level, const char*) {
        PoolGrowingLogCallback* callback = g_pool_growing_log_callback;
        if (!callback || callback->invoked)
            return;

        callback->invoked = true;
        for (const std::string& name : callback->resource_names) {
            termin::TcSkeleton resource = termin::TcSkeleton::create(name);
            if (!resource.is_valid()) {
                callback->succeeded = false;
                return;
            }
            callback->created_resources.emplace_back(std::move(resource));
        }
        if (callback->replacement_target && !callback->replacement_target->replace_bones(
                                                callback->replacement_bones, callback->replacement_bone_count)) {
            callback->succeeded = false;
        }
    }

    struct LogCallbackScope {
        explicit LogCallbackScope(PoolGrowingLogCallback& callback) {
            g_pool_growing_log_callback = &callback;
            tc_log_set_callback(grow_skeleton_pool_on_log);
        }

        ~LogCallbackScope() {
            tc_log_set_callback(nullptr);
            g_pool_growing_log_callback = nullptr;
        }
    };

    void prepare_pool_growing_log_callback(PoolGrowingLogCallback& callback,
                                           size_t resource_count,
                                           const std::string& name_prefix) {
        callback.resource_names.reserve(resource_count);
        callback.created_resources.reserve(resource_count);
        for (size_t index = 0; index < resource_count; ++index)
            callback.resource_names.emplace_back(name_prefix + std::to_string(index));
    }
} // namespace

TEST_CASE("SkeletonInstance evaluates a portable local pose hierarchy") {
    std::array<BoneDescriptorStorage, 2> storage;
    storage[0].translation.x = 1.0;
    storage[1].translation.x = 2.0;
    std::array<tc_skeleton_bone_desc, 2> descriptors = {
        storage[0].descriptor("Root"),
        storage[1].descriptor("Child"),
    };
    descriptors[1].parent_index = 0;
    termin::TcSkeleton skeleton = create_skeleton("Hierarchy", descriptors.data(), descriptors.size());
    termin::SkeletonInstance instance(skeleton);

    REQUIRE_EQ(instance.bone_count(), 2);
    check_near(instance.get_bone_world_matrix(0)(3, 0), 1.0);
    check_near(instance.get_bone_world_matrix(1)(3, 0), 3.0);
    check_near(instance.get_bone_matrix(1)(3, 0), 3.0);

    const termin::Vec3 child_translation{4.0, 0.0, 0.0};
    instance.set_bone_transform(1, &child_translation, nullptr, nullptr);
    REQUIRE(instance.update());
    check_near(instance.get_bone_world_matrix(1)(3, 0), 5.0);
}

TEST_CASE("SkeletonInstance accepts scene-neutral externally evaluated matrices") {
    std::array<BoneDescriptorStorage, 2> storage;
    std::array<tc_skeleton_bone_desc, 2> descriptors = {
        storage[0].descriptor("Root"),
        storage[1].descriptor("Child"),
    };
    descriptors[1].parent_index = 0;
    termin::TcSkeleton skeleton = create_skeleton("ExternalMatrices", descriptors.data(), descriptors.size());
    termin::SkeletonInstance instance(skeleton);
    std::vector<termin::Mat44> bone_world = {
        termin::Mat44::translation(11.0, 0.0, 0.0),
        termin::Mat44::translation(13.0, 0.0, 0.0),
    };

    REQUIRE(instance.update_from_world_matrices(termin::Mat44::translation(10.0, 0.0, 0.0), bone_world));
    check_near(instance.get_bone_matrix(0)(3, 0), 1.0);
    check_near(instance.get_bone_matrix(1)(3, 0), 3.0);
}

TEST_CASE("SkeletonInstance survives skeleton pool growth with instance-only ownership") {
    BoneDescriptorStorage root_storage;
    root_storage.translation.x = 3.0;
    const tc_skeleton_bone_desc root = root_storage.descriptor("Root");
    termin::SkeletonInstance instance;
    tc_skeleton_handle target_handle = tc_skeleton_handle_invalid();
    {
        termin::TcSkeleton target = create_skeleton("PoolGrowthTarget", &root, 1);
        target_handle = target.native_handle();
        instance.set_skeleton(target);
    }

    const tc_skeleton* target = tc_skeleton_get(target_handle);
    REQUIRE(target != nullptr);
    REQUIRE_EQ(target->header.ref_count, 1u);

    std::vector<termin::TcSkeleton> growth_resources;
    growth_resources.reserve(40);
    for (int i = 0; i < 40; ++i) {
        termin::TcSkeleton resource = termin::TcSkeleton::create("PoolGrowth" + std::to_string(i));
        REQUIRE(resource.is_valid());
        growth_resources.emplace_back(std::move(resource));
    }

    REQUIRE_GT(tc_skeleton_count(), 32u);
    REQUIRE(tc_skeleton_is_valid(target_handle));
    REQUIRE(instance.update());
    REQUIRE_EQ(instance.bone_count(), 1);
    check_near(instance.get_bone_world_matrix(0)(3, 0), 3.0);
    target = tc_skeleton_get(target_handle);
    REQUIRE(target != nullptr);
    CHECK_EQ(target->header.ref_count, 1u);
}

TEST_CASE("skeleton lazy loading reacquires its slot after reentrant pool growth") {
    const std::string target_uuid = "lazy-load-growth-target";
    const tc_skeleton_handle handle = tc_skeleton_declare(target_uuid.c_str(), "LazyLoadTarget");
    termin::TcSkeleton target(handle);
    REQUIRE(target.is_valid());
    REQUIRE_FALSE(target.is_loaded());
    const tc_skeleton* address_before_load = target.get();
    REQUIRE(address_before_load != nullptr);

    PoolGrowingSkeletonLoader loader;
    loader.expected_uuid = target_uuid;
    ResourceLoaderScope loader_scope;
    tc_resource_set_loader(grow_skeleton_pool_loader, &loader);

    REQUIRE(target.ensure_loaded());
    REQUIRE(loader.invoked);
    REQUIRE(loader.received_expected_uuid);
    REQUIRE_EQ(loader.created_resources.size(), 80u);
    REQUIRE(target.is_valid());
    REQUIRE(target.is_loaded());
    const tc_skeleton* address_after_load = target.get();
    REQUIRE(address_after_load != nullptr);
    CHECK(address_after_load != address_before_load);
}

TEST_CASE("skeleton creation normalizes logging inputs before acquiring a movable pool slot") {
    const std::string create_uuid = "create-" + std::string(TC_UUID_SIZE, 'c');
    const std::string expected_create_uuid = create_uuid.substr(0, TC_UUID_SIZE - 1);
    PoolGrowingLogCallback create_callback;
    prepare_pool_growing_log_callback(create_callback, 320, "CreateLogGrowth");

    tc_skeleton_handle created_handle = tc_skeleton_handle_invalid();
    {
        LogCallbackScope callback_scope(create_callback);
        created_handle = tc_skeleton_create(create_uuid.c_str());
    }

    REQUIRE(create_callback.invoked);
    REQUIRE(create_callback.succeeded);
    termin::TcSkeleton created(created_handle);
    REQUIRE(created.is_valid());
    CHECK_EQ(std::string(created.uuid()), expected_create_uuid);
    CHECK(tc_skeleton_handle_eq(tc_skeleton_find(create_uuid.c_str()), created_handle));

    const std::string declare_uuid = "declare-" + std::string(TC_UUID_SIZE, 'd');
    const std::string expected_declare_uuid = declare_uuid.substr(0, TC_UUID_SIZE - 1);
    PoolGrowingLogCallback declare_callback;
    prepare_pool_growing_log_callback(declare_callback, 800, "DeclareLogGrowth");

    tc_skeleton_handle declared_handle = tc_skeleton_handle_invalid();
    {
        LogCallbackScope callback_scope(declare_callback);
        declared_handle = tc_skeleton_declare(declare_uuid.c_str(), "DeclaredAfterLogGrowth");
    }

    REQUIRE(declare_callback.invoked);
    REQUIRE(declare_callback.succeeded);
    termin::TcSkeleton declared(declared_handle);
    REQUIRE(declared.is_valid());
    CHECK_EQ(std::string(declared.uuid()), expected_declare_uuid);
    CHECK(tc_skeleton_handle_eq(tc_skeleton_find(declare_uuid.c_str()), declared_handle));
}

TEST_CASE("SkeletonInstance finishes version refresh before a reentrant log callback grows the pool") {
    BoneDescriptorStorage initial_storage;
    initial_storage.translation.x = 1.0;
    const tc_skeleton_bone_desc initial = initial_storage.descriptor("Root");
    termin::TcSkeleton skeleton = create_skeleton("LogCallbackGrowthTarget", &initial, 1);
    termin::SkeletonInstance instance(skeleton);

    BoneDescriptorStorage replacement_storage;
    replacement_storage.translation.x = 9.0;
    const tc_skeleton_bone_desc replacement = replacement_storage.descriptor("Root");
    REQUIRE(skeleton.replace_bones(&replacement, 1));

    const tc_skeleton* address_before_refresh = skeleton.get();
    REQUIRE(address_before_refresh != nullptr);

    PoolGrowingLogCallback callback;
    prepare_pool_growing_log_callback(callback, 2500, "LogCallbackGrowth");

    {
        LogCallbackScope callback_scope(callback);
        REQUIRE_EQ(instance.bone_count(), 1);
    }

    REQUIRE(callback.invoked);
    REQUIRE(callback.succeeded);
    REQUIRE_EQ(callback.created_resources.size(), callback.resource_names.size());
    const tc_skeleton* address_after_refresh = skeleton.get();
    REQUIRE(address_after_refresh != nullptr);
    CHECK(address_after_refresh != address_before_refresh);
    check_near(instance.local_pose(0).lin.x, 9.0);
    REQUIRE(instance.update());
    check_near(instance.get_bone_world_matrix(0)(3, 0), 9.0);
}

TEST_CASE("SkeletonInstance refreshes from a payload replaced by its version-change log callback") {
    BoneDescriptorStorage initial_storage;
    initial_storage.translation.x = 1.0;
    const tc_skeleton_bone_desc initial = initial_storage.descriptor("Root");
    termin::TcSkeleton skeleton = create_skeleton("LogCallbackReplacementTarget", &initial, 1);
    termin::SkeletonInstance instance(skeleton);

    BoneDescriptorStorage observed_storage;
    observed_storage.translation.x = 9.0;
    observed_storage.inverse_bind = translation_matrix(-1.0);
    const tc_skeleton_bone_desc observed = observed_storage.descriptor("Root");
    REQUIRE(skeleton.replace_bones(&observed, 1));

    std::array<BoneDescriptorStorage, 2> latest_storage;
    latest_storage[0].translation.x = 17.0;
    latest_storage[1].translation.x = 3.0;
    latest_storage[1].inverse_bind = translation_matrix(-2.0);
    std::array<tc_skeleton_bone_desc, 2> latest = {
        latest_storage[0].descriptor("Root"),
        latest_storage[1].descriptor("Child"),
    };
    latest[1].parent_index = 0;

    PoolGrowingLogCallback callback;
    callback.replacement_target = &skeleton;
    callback.replacement_bones = latest.data();
    callback.replacement_bone_count = latest.size();

    std::array<float, 32> output{};
    {
        LogCallbackScope callback_scope(callback);
        REQUIRE(instance.get_bone_matrices_float(output.data()));
    }

    REQUIRE(callback.invoked);
    REQUIRE(callback.succeeded);
    REQUIRE_EQ(instance.bone_count(), 2);
    check_near(output[12], 17.0);
    check_near(output[28], 18.0);
    check_near(instance.local_pose(0).lin.x, 17.0);
    check_near(instance.local_pose(1).lin.x, 3.0);
}

TEST_CASE("Skeleton handles and instances retain registry resources across copy and move") {
    BoneDescriptorStorage storage;
    const tc_skeleton_bone_desc descriptor = storage.descriptor("Root");
    termin::TcSkeleton owner = create_skeleton("CopyMoveOwnership", &descriptor, 1);
    const tc_skeleton_handle handle = owner.native_handle();
    REQUIRE_EQ(tc_skeleton_get(handle)->header.ref_count, 1u);

    {
        termin::TcSkeleton copied_owner = owner;
        REQUIRE_EQ(tc_skeleton_get(handle)->header.ref_count, 2u);
        termin::TcSkeleton moved_owner = std::move(copied_owner);
        CHECK_FALSE(copied_owner.has_handle());
        REQUIRE(moved_owner.is_valid());
        REQUIRE_EQ(tc_skeleton_get(handle)->header.ref_count, 2u);

        termin::SkeletonInstance instance(owner);
        REQUIRE_EQ(tc_skeleton_get(handle)->header.ref_count, 3u);
        termin::SkeletonInstance copied_instance = instance;
        REQUIRE_EQ(tc_skeleton_get(handle)->header.ref_count, 4u);
        termin::SkeletonInstance moved_instance = std::move(copied_instance);
        CHECK_FALSE(copied_instance.skeleton_resource().has_handle());
        REQUIRE(moved_instance.update());
        REQUIRE_EQ(tc_skeleton_get(handle)->header.ref_count, 4u);
    }

    REQUIRE(tc_skeleton_is_valid(handle));
    REQUIRE_EQ(tc_skeleton_get(handle)->header.ref_count, 1u);
    owner = termin::TcSkeleton();
    CHECK_FALSE(tc_skeleton_is_valid(handle));
}

TEST_CASE("tc_skeleton_destroy refuses resources with strong wrapper or instance ownership") {
    BoneDescriptorStorage storage;
    const tc_skeleton_bone_desc descriptor = storage.descriptor("Root");
    termin::TcSkeleton owner = create_skeleton("StrongDestroy", &descriptor, 1);
    const tc_skeleton_handle handle = owner.native_handle();

    {
        termin::SkeletonInstance instance(owner);
        REQUIRE_EQ(tc_skeleton_get(handle)->header.ref_count, 2u);
        CHECK_FALSE(tc_skeleton_destroy(handle));
        REQUIRE(tc_skeleton_is_valid(handle));
    }

    REQUIRE_EQ(tc_skeleton_get(handle)->header.ref_count, 1u);
    CHECK_FALSE(tc_skeleton_destroy(handle));
    REQUIRE(tc_skeleton_is_valid(handle));
    owner = termin::TcSkeleton();
    CHECK_FALSE(tc_skeleton_is_valid(handle));
}

TEST_CASE("SkeletonInstance resets overrides and inverse bind data on same-count replacement") {
    BoneDescriptorStorage initial_storage;
    initial_storage.translation.x = 1.0;
    const tc_skeleton_bone_desc initial = initial_storage.descriptor("Root");
    termin::TcSkeleton skeleton = create_skeleton("SameCountRefresh", &initial, 1);
    termin::SkeletonInstance instance(skeleton);

    const termin::Vec3 override_translation{9.0, 0.0, 0.0};
    REQUIRE(instance.try_set_bone_transform(0, &override_translation, nullptr, nullptr));
    REQUIRE(instance.update());
    check_near(instance.get_bone_world_matrix(0)(3, 0), 9.0);
    const uint32_t previous_version = skeleton.version();

    BoneDescriptorStorage replacement_storage;
    replacement_storage.translation.x = 4.0;
    replacement_storage.inverse_bind = translation_matrix(-2.0);
    const tc_skeleton_bone_desc replacement = replacement_storage.descriptor("Root");
    REQUIRE(skeleton.replace_bones(&replacement, 1));
    REQUIRE_EQ(skeleton.version(), previous_version + 1);

    REQUIRE(instance.synchronize());
    check_near(instance.local_pose(0).lin.x, 4.0);
    check_near(instance.get_bone_world_matrix(0)(3, 0), 4.0);
    check_near(instance.get_bone_matrix(0)(3, 0), 2.0);
}

TEST_CASE("SkeletonInstance auto-resizes after count-changing replacement") {
    BoneDescriptorStorage initial_storage;
    initial_storage.translation.x = 1.0;
    const tc_skeleton_bone_desc initial = initial_storage.descriptor("Root");
    termin::TcSkeleton skeleton = create_skeleton("CountRefresh", &initial, 1);
    termin::SkeletonInstance instance(skeleton);

    const termin::Vec3 override_translation{7.0, 0.0, 0.0};
    REQUIRE(instance.try_set_bone_transform(0, &override_translation, nullptr, nullptr));
    REQUIRE(instance.update());

    std::array<BoneDescriptorStorage, 2> storage;
    storage[0].translation.x = 2.0;
    storage[1].translation.x = 3.0;
    storage[1].inverse_bind = translation_matrix(-1.0);
    std::array<tc_skeleton_bone_desc, 2> descriptors = {
        storage[0].descriptor("Root"),
        storage[1].descriptor("Child"),
    };
    descriptors[1].parent_index = 0;
    REQUIRE(skeleton.replace_bones(descriptors.data(), descriptors.size()));

    REQUIRE(instance.update());
    REQUIRE_EQ(instance.bone_count(), 2);
    check_near(instance.local_pose(0).lin.x, 2.0);
    check_near(instance.local_pose(1).lin.x, 3.0);
    check_near(instance.get_bone_world_matrix(1)(3, 0), 5.0);
    check_near(instance.get_bone_matrix(1)(3, 0), 4.0);

    const std::vector<termin::Mat44> world_matrices = {
        termin::Mat44::translation(11.0, 0.0, 0.0),
        termin::Mat44::translation(13.0, 0.0, 0.0),
    };
    REQUIRE(instance.update_from_world_matrices(termin::Mat44::translation(10.0, 0.0, 0.0), world_matrices));
    check_near(instance.get_bone_matrix(0)(3, 0), 1.0);
    check_near(instance.get_bone_matrix(1)(3, 0), 2.0);

    std::array<float, 32> output{};
    REQUIRE(instance.get_bone_matrices_float(output.data()));
    check_near(output[12], 1.0);
    check_near(output[28], 2.0);
}

TEST_CASE("failed skeleton replacement preserves instance version and runtime override") {
    BoneDescriptorStorage initial_storage;
    initial_storage.translation.x = 1.0;
    const tc_skeleton_bone_desc initial = initial_storage.descriptor("Root");
    termin::TcSkeleton skeleton = create_skeleton("FailedRefresh", &initial, 1);
    termin::SkeletonInstance instance(skeleton);

    const termin::Vec3 override_translation{9.0, 0.0, 0.0};
    REQUIRE(instance.try_set_bone_transform(0, &override_translation, nullptr, nullptr));
    REQUIRE(instance.update());
    const uint32_t previous_version = skeleton.version();

    BoneDescriptorStorage rejected_storage;
    rejected_storage.translation.x = 4.0;
    rejected_storage.rotation = tc_quat{0.0, 0.0, 0.0, 0.0};
    const tc_skeleton_bone_desc rejected = rejected_storage.descriptor("Rejected");
    CHECK_FALSE(skeleton.replace_bones(&rejected, 1));
    REQUIRE_EQ(skeleton.version(), previous_version);

    REQUIRE(instance.update());
    check_near(instance.local_pose(0).lin.x, 9.0);
    check_near(instance.get_bone_world_matrix(0)(3, 0), 9.0);
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
    BoneDescriptorStorage storage;
    const tc_skeleton_bone_desc descriptor = storage.descriptor("Root");
    termin::TcSkeleton skeleton = create_skeleton("CheckedTransforms", &descriptor, 1);
    termin::SkeletonInstance instance(skeleton);
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

TEST_CASE("SkeletonInstance rejects a stale handle after registry rebootstrap and clears runtime state") {
    REQUIRE_EQ(tc_skeleton_count(), 0u);

    std::unique_ptr<termin::SkeletonInstance> instance;
    tc_skeleton_handle stale_handle = tc_skeleton_handle_invalid();
    {
        BoneDescriptorStorage storage;
        storage.translation.x = 6.0;
        const tc_skeleton_bone_desc descriptor = storage.descriptor("Root");
        termin::TcSkeleton skeleton = create_skeleton("StaleHandle", &descriptor, 1);
        stale_handle = skeleton.native_handle();
        instance = std::make_unique<termin::SkeletonInstance>(skeleton);
        REQUIRE(instance->update());
        REQUIRE_EQ(instance->bone_count(), 1);
        check_near(instance->get_bone_world_matrix(0)(3, 0), 6.0);
    }

    REQUIRE_EQ(tc_skeleton_count(), 1u);
    tc_skeleton_shutdown();
    tc_skeleton_init();
    REQUIRE_FALSE(tc_skeleton_is_valid(stale_handle));

    CHECK_FALSE(instance->update());
    CHECK_EQ(instance->bone_count(), 0);
    std::array<float, 16> output;
    output.fill(-17.0f);
    CHECK_FALSE(instance->get_bone_matrices_float(output.data()));
    for (float value : output)
        CHECK_EQ(value, -17.0f);
    instance.reset();

    BoneDescriptorStorage fresh_storage;
    fresh_storage.translation.x = 2.0;
    const tc_skeleton_bone_desc fresh_descriptor = fresh_storage.descriptor("Root");
    {
        termin::TcSkeleton fresh = create_skeleton("AfterRebootstrap", &fresh_descriptor, 1);
        REQUIRE(fresh.is_valid());
        REQUIRE_FALSE(fresh.native_handle().generation == stale_handle.generation);
        termin::SkeletonInstance fresh_instance(fresh);
        REQUIRE(fresh_instance.update());
        check_near(fresh_instance.get_bone_world_matrix(0)(3, 0), 2.0);
    }
    CHECK_EQ(tc_skeleton_count(), 0u);
}

GUARD_TEST_MAIN();
