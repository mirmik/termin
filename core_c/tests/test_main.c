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

static int test_tc_value(void) {
    printf("Testing tc_value...\n");

    // Test primitives
    tc_value v_nil = tc_value_nil();
    TEST_ASSERT(v_nil.type == TC_VALUE_NIL, "nil type");

    tc_value v_bool = tc_value_bool(true);
    TEST_ASSERT(v_bool.type == TC_VALUE_BOOL, "bool type");
    TEST_ASSERT(v_bool.data.b == true, "bool value");

    tc_value v_int = tc_value_int(42);
    TEST_ASSERT(v_int.type == TC_VALUE_INT, "int type");
    TEST_ASSERT(v_int.data.i == 42, "int value");

    tc_value v_str = tc_value_string("hello");
    TEST_ASSERT(v_str.type == TC_VALUE_STRING, "string type");
    TEST_ASSERT(strcmp(v_str.data.s, "hello") == 0, "string value");
    tc_value_free(&v_str);

    // Test list
    tc_value list = tc_value_list_new();
    tc_value_list_push(&list, tc_value_int(1));
    tc_value_list_push(&list, tc_value_int(2));
    tc_value_list_push(&list, tc_value_int(3));
    TEST_ASSERT(tc_value_list_count(&list) == 3, "list count");
    TEST_ASSERT(tc_value_list_get(&list, 1)->data.i == 2, "list get");
    tc_value_free(&list);

    // Test dict
    tc_value dict = tc_value_dict_new();
    tc_value_dict_set(&dict, "name", tc_value_string("test"));
    tc_value_dict_set(&dict, "value", tc_value_int(123));
    TEST_ASSERT(tc_value_dict_has(&dict, "name"), "dict has");
    TEST_ASSERT(tc_value_dict_get(&dict, "value")->data.i == 123, "dict get");
    tc_value_free(&dict);

    printf("  tc_value: PASS\n");
    return 0;
}

// Test component type for inspect
typedef struct {
    float speed;
    int health;
    bool active;
} TestComponentData;

static tc_value test_getter(void* obj, const tc_field_desc* field, void* user_data) {
    (void)user_data;
    TestComponentData* data = (TestComponentData*)obj;

    if (strcmp(field->path, "speed") == 0) return tc_value_float(data->speed);
    if (strcmp(field->path, "health") == 0) return tc_value_int(data->health);
    if (strcmp(field->path, "active") == 0) return tc_value_bool(data->active);

    return tc_value_nil();
}

static void test_setter(void* obj, const tc_field_desc* field, tc_value value, void* user_data) {
    (void)user_data;
    TestComponentData* data = (TestComponentData*)obj;

    if (strcmp(field->path, "speed") == 0 && value.type == TC_VALUE_FLOAT) {
        data->speed = value.data.f;
    } else if (strcmp(field->path, "health") == 0 && value.type == TC_VALUE_INT) {
        data->health = (int)value.data.i;
    } else if (strcmp(field->path, "active") == 0 && value.type == TC_VALUE_BOOL) {
        data->active = value.data.b;
    }
}

static int test_inspect(void) {
    printf("Testing tc_inspect...\n");

    // Define fields
    static const tc_field_desc test_fields[] = {
        { .path = "speed",  .label = "Speed",  .kind = "float", .min = 0, .max = 100, .step = 0.1 },
        { .path = "health", .label = "Health", .kind = "int",   .min = 0, .max = 100, .step = 1 },
        { .path = "active", .label = "Active", .kind = "bool" },
    };

    static const tc_type_vtable test_vtable = {
        .get = test_getter,
        .set = test_setter,
        .action = NULL,
        .user_data = NULL,
    };

    static const tc_type_desc test_desc = {
        .type_name = "TestComponent",
        .base_type = NULL,
        .fields = test_fields,
        .field_count = 3,
        .vtable = &test_vtable,
    };

    // Register type
    tc_inspect_register(&test_desc);

    // Verify registration
    TEST_ASSERT(tc_inspect_get_type("TestComponent") != NULL, "type registered");
    TEST_ASSERT(tc_inspect_field_count("TestComponent") == 3, "field count");

    // Find field
    const tc_field_desc* speed_field = tc_inspect_find_field("TestComponent", "speed");
    TEST_ASSERT(speed_field != NULL, "find field");
    TEST_ASSERT(strcmp(speed_field->label, "Speed") == 0, "field label");

    // Get/Set through registry
    TestComponentData data = { .speed = 5.0f, .health = 100, .active = true };

    tc_value v = tc_inspect_get(&data, "TestComponent", "speed");
    TEST_ASSERT(v.type == TC_VALUE_FLOAT, "get returns float");
    TEST_ASSERT(fabs(v.data.f - 5.0f) < 0.001f, "get value");

    tc_inspect_set(&data, "TestComponent", "health", tc_value_int(50));
    TEST_ASSERT(data.health == 50, "set value");

    // Serialize
    tc_value serialized = tc_inspect_serialize(&data, "TestComponent");
    TEST_ASSERT(serialized.type == TC_VALUE_DICT, "serialize returns dict");
    TEST_ASSERT(tc_value_dict_has(&serialized, "speed"), "serialized has speed");
    TEST_ASSERT(tc_value_dict_has(&serialized, "health"), "serialized has health");
    tc_value_free(&serialized);

    // Cleanup
    tc_inspect_unregister("TestComponent");
    TEST_ASSERT(tc_inspect_get_type("TestComponent") == NULL, "type unregistered");

    printf("  tc_inspect: PASS\n");
    return 0;
}

static int test_kind_handler(void) {
    printf("Testing kind handlers...\n");

    // Parse parameterized kind
    char container[32], element[32];
    bool ok = tc_kind_parse("list[entity_handle]", container, sizeof(container), element, sizeof(element));
    TEST_ASSERT(ok, "parse list[entity_handle]");
    TEST_ASSERT(strcmp(container, "list") == 0, "container is list");
    TEST_ASSERT(strcmp(element, "entity_handle") == 0, "element is entity_handle");

    ok = tc_kind_parse("float", container, sizeof(container), element, sizeof(element));
    TEST_ASSERT(!ok, "float is not parameterized");

    printf("  Kind handlers: PASS\n");
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
    result |= test_tc_value();
    result |= test_inspect();
    result |= test_kind_handler();

    tc_shutdown();

    printf("\n");
    if (result == 0) {
        printf("=== ALL TESTS PASSED ===\n");
    } else {
        printf("=== SOME TESTS FAILED ===\n");
    }

    return result;
}
