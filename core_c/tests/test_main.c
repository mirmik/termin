// test_main.c - Basic tests for Termin Core
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "../include/termin_core.h"

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            printf("FAIL: %s (line %d)\n", msg, __LINE__); \
            return 1; \
        } \
    } while(0)

#define EPSILON 1e-9

static int test_vec3(void) {
    printf("Testing Vec3...\n");

    tc_vec3 a = {1.0, 2.0, 3.0};
    tc_vec3 b = {4.0, 5.0, 6.0};

    tc_vec3 sum = tc_vec3_add(a, b);
    TEST_ASSERT(fabs(sum.x - 5.0) < EPSILON, "vec3 add x");
    TEST_ASSERT(fabs(sum.y - 7.0) < EPSILON, "vec3 add y");
    TEST_ASSERT(fabs(sum.z - 9.0) < EPSILON, "vec3 add z");

    tc_vec3 diff = tc_vec3_sub(b, a);
    TEST_ASSERT(fabs(diff.x - 3.0) < EPSILON, "vec3 sub x");
    TEST_ASSERT(fabs(diff.y - 3.0) < EPSILON, "vec3 sub y");
    TEST_ASSERT(fabs(diff.z - 3.0) < EPSILON, "vec3 sub z");

    double dot = tc_vec3_dot(a, b);
    TEST_ASSERT(fabs(dot - 32.0) < EPSILON, "vec3 dot");

    tc_vec3 cross = tc_vec3_cross(a, b);
    TEST_ASSERT(fabs(cross.x - (-3.0)) < EPSILON, "vec3 cross x");
    TEST_ASSERT(fabs(cross.y - 6.0) < EPSILON, "vec3 cross y");
    TEST_ASSERT(fabs(cross.z - (-3.0)) < EPSILON, "vec3 cross z");

    printf("  Vec3: PASS\n");
    return 0;
}

static int test_quat(void) {
    printf("Testing Quat...\n");

    tc_quat q = tc_quat_identity();
    TEST_ASSERT(fabs(q.w - 1.0) < EPSILON, "quat identity w");
    TEST_ASSERT(fabs(q.x) < EPSILON, "quat identity x");
    TEST_ASSERT(fabs(q.y) < EPSILON, "quat identity y");
    TEST_ASSERT(fabs(q.z) < EPSILON, "quat identity z");

    // Rotate around Y axis by 90 degrees
    tc_quat rot = tc_quat_from_axis_angle((tc_vec3){0, 1, 0}, 3.14159265358979323846 / 2.0);
    tc_vec3 v = {1, 0, 0};
    tc_vec3 rotated = tc_quat_rotate(rot, v);

    // Should be approximately (0, 0, -1)
    TEST_ASSERT(fabs(rotated.x) < 0.01, "quat rotate x");
    TEST_ASSERT(fabs(rotated.y) < 0.01, "quat rotate y");
    TEST_ASSERT(fabs(rotated.z - (-1.0)) < 0.01, "quat rotate z");

    printf("  Quat: PASS\n");
    return 0;
}

static int test_transform(void) {
    printf("Testing Transform...\n");

    tc_transform* t = tc_transform_new();
    TEST_ASSERT(t != NULL, "transform create");

    tc_vec3 pos = tc_transform_position(t);
    TEST_ASSERT(fabs(pos.x) < EPSILON, "transform initial pos x");
    TEST_ASSERT(fabs(pos.y) < EPSILON, "transform initial pos y");
    TEST_ASSERT(fabs(pos.z) < EPSILON, "transform initial pos z");

    tc_transform_set_position(t, (tc_vec3){1, 2, 3});
    pos = tc_transform_position(t);
    TEST_ASSERT(fabs(pos.x - 1.0) < EPSILON, "transform set pos x");
    TEST_ASSERT(fabs(pos.y - 2.0) < EPSILON, "transform set pos y");
    TEST_ASSERT(fabs(pos.z - 3.0) < EPSILON, "transform set pos z");

    tc_transform_free(t);

    printf("  Transform: PASS\n");
    return 0;
}

static int test_transform_hierarchy(void) {
    printf("Testing Transform Hierarchy...\n");

    tc_transform* parent = tc_transform_new();
    tc_transform* child = tc_transform_new();

    tc_transform_set_position(parent, (tc_vec3){10, 0, 0});
    tc_transform_set_position(child, (tc_vec3){5, 0, 0});

    tc_transform_add_child(parent, child);

    TEST_ASSERT(tc_transform_parent(child) == parent, "child has parent");
    TEST_ASSERT(tc_transform_children_count(parent) == 1, "parent has 1 child");

    // Global position should be parent + child local
    tc_vec3 global_pos = tc_transform_global_position(child);
    TEST_ASSERT(fabs(global_pos.x - 15.0) < EPSILON, "child global pos x");

    tc_transform_free(child);
    tc_transform_free(parent);

    printf("  Transform Hierarchy: PASS\n");
    return 0;
}

static int test_entity(void) {
    printf("Testing Entity...\n");

    tc_entity* e = tc_entity_new("TestEntity");
    TEST_ASSERT(e != NULL, "entity create");

    const char* name = tc_entity_name(e);
    TEST_ASSERT(strcmp(name, "TestEntity") == 0, "entity name");

    const char* uuid = tc_entity_uuid(e);
    TEST_ASSERT(strlen(uuid) == 36, "entity uuid length");

    uint64_t rid = tc_entity_runtime_id(e);
    TEST_ASSERT(rid != 0, "entity runtime id");

    tc_transform* t = tc_entity_transform(e);
    TEST_ASSERT(t != NULL, "entity has transform");

    TEST_ASSERT(tc_entity_visible(e) == true, "entity visible default");
    TEST_ASSERT(tc_entity_active(e) == true, "entity active default");

    tc_entity_set_visible(e, false);
    TEST_ASSERT(tc_entity_visible(e) == false, "entity set visible");

    tc_entity_free(e);

    printf("  Entity: PASS\n");
    return 0;
}

static int test_entity_hierarchy(void) {
    printf("Testing Entity Hierarchy...\n");

    tc_entity* parent = tc_entity_new("Parent");
    tc_entity* child = tc_entity_new("Child");

    tc_entity_set_local_pose(parent, (tc_general_pose3){
        .position = {10, 0, 0},
        .rotation = tc_quat_identity(),
        .scale = {1, 1, 1}
    });

    tc_entity_set_local_pose(child, (tc_general_pose3){
        .position = {5, 0, 0},
        .rotation = tc_quat_identity(),
        .scale = {1, 1, 1}
    });

    tc_entity_set_parent(child, parent);

    TEST_ASSERT(tc_entity_parent(child) == parent, "child has parent entity");
    TEST_ASSERT(tc_entity_children_count(parent) == 1, "parent has 1 child entity");

    tc_general_pose3 gpose = tc_entity_global_pose(child);
    TEST_ASSERT(fabs(gpose.position.x - 15.0) < EPSILON, "child global pose x");

    tc_entity_free(child);
    tc_entity_free(parent);

    printf("  Entity Hierarchy: PASS\n");
    return 0;
}

static int test_entity_registry(void) {
    printf("Testing Entity Registry...\n");

    size_t initial_count = tc_entity_registry_count();

    tc_entity* e1 = tc_entity_new("Entity1");
    tc_entity* e2 = tc_entity_new("Entity2");

    TEST_ASSERT(tc_entity_registry_count() == initial_count + 2, "registry count after add");

    tc_entity* found = tc_entity_registry_find_by_uuid(tc_entity_uuid(e1));
    TEST_ASSERT(found == e1, "find by uuid");

    found = tc_entity_registry_find_by_runtime_id(tc_entity_runtime_id(e2));
    TEST_ASSERT(found == e2, "find by runtime id");

    tc_entity_free(e1);
    TEST_ASSERT(tc_entity_registry_count() == initial_count + 1, "registry count after remove");

    tc_entity_free(e2);
    TEST_ASSERT(tc_entity_registry_count() == initial_count, "registry count back to initial");

    printf("  Entity Registry: PASS\n");
    return 0;
}

static int test_uuid(void) {
    printf("Testing UUID...\n");

    char uuid1[40];
    char uuid2[40];

    tc_generate_uuid(uuid1);
    tc_generate_uuid(uuid2);

    TEST_ASSERT(strlen(uuid1) == 36, "uuid1 length");
    TEST_ASSERT(strlen(uuid2) == 36, "uuid2 length");
    TEST_ASSERT(strcmp(uuid1, uuid2) != 0, "uuids are unique");

    // Check format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    TEST_ASSERT(uuid1[8] == '-', "uuid format dash 1");
    TEST_ASSERT(uuid1[13] == '-', "uuid format dash 2");
    TEST_ASSERT(uuid1[18] == '-', "uuid format dash 3");
    TEST_ASSERT(uuid1[23] == '-', "uuid format dash 4");

    printf("  UUID: PASS\n");
    return 0;
}

int main(void) {
    printf("=== Termin Core Tests ===\n");
    printf("Version: %s\n\n", tc_version());

    tc_init();

    int result = 0;

    result |= test_vec3();
    result |= test_quat();
    result |= test_transform();
    result |= test_transform_hierarchy();
    result |= test_entity();
    result |= test_entity_hierarchy();
    result |= test_entity_registry();
    result |= test_uuid();

    tc_shutdown();

    printf("\n");
    if (result == 0) {
        printf("=== ALL TESTS PASSED ===\n");
    } else {
        printf("=== SOME TESTS FAILED ===\n");
    }

    return result;
}
