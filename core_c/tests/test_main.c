// test_main.c - Tests for Termin Core
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "../include/termin_core.h"
#include "../include/tc_resource_map.h"
#include "../include/tc_mesh.h"
#include "../include/tc_mesh_registry.h"

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            printf("FAIL: %s (line %d)\n", msg, __LINE__); \
            return 1; \
        } \
    } while(0)

#define EPSILON 1e-9

// ============================================================================
// Vec3 tests
// ============================================================================

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

    double len = tc_vec3_length(a);
    TEST_ASSERT(fabs(len - sqrt(14.0)) < EPSILON, "vec3 length");

    tc_vec3 norm = tc_vec3_normalize(a);
    TEST_ASSERT(fabs(tc_vec3_length(norm) - 1.0) < EPSILON, "vec3 normalize");

    printf("  Vec3: PASS\n");
    return 0;
}

// ============================================================================
// Quat tests
// ============================================================================

static int test_quat(void) {
    printf("Testing Quat...\n");

    tc_quat q = tc_quat_identity();
    TEST_ASSERT(fabs(q.w - 1.0) < EPSILON, "quat identity w");
    TEST_ASSERT(fabs(q.x) < EPSILON, "quat identity x");
    TEST_ASSERT(fabs(q.y) < EPSILON, "quat identity y");
    TEST_ASSERT(fabs(q.z) < EPSILON, "quat identity z");

    // Rotate around Y axis by 90 degrees
    tc_quat rot = tc_quat_from_axis_angle((tc_vec3){0, 1, 0}, M_PI / 2.0);
    tc_vec3 v = {1, 0, 0};
    tc_vec3 rotated = tc_quat_rotate(rot, v);

    // Should be approximately (0, 0, -1)
    TEST_ASSERT(fabs(rotated.x) < 0.01, "quat rotate x");
    TEST_ASSERT(fabs(rotated.y) < 0.01, "quat rotate y");
    TEST_ASSERT(fabs(rotated.z - (-1.0)) < 0.01, "quat rotate z");

    // Test multiplication
    tc_quat q2 = tc_quat_mul(rot, rot);  // 180 degrees
    tc_vec3 rotated2 = tc_quat_rotate(q2, v);
    TEST_ASSERT(fabs(rotated2.x - (-1.0)) < 0.01, "quat mul rotate x");

    printf("  Quat: PASS\n");
    return 0;
}

// ============================================================================
// Entity Pool tests
// ============================================================================

static int test_entity_pool(void) {
    printf("Testing Entity Pool...\n");

    tc_entity_pool* pool = tc_entity_pool_create(16);
    TEST_ASSERT(pool != NULL, "pool create");
    TEST_ASSERT(tc_entity_pool_count(pool) == 0, "initial count is 0");

    // Allocate entity
    tc_entity_id e1 = tc_entity_pool_alloc(pool, "Entity1");
    TEST_ASSERT(tc_entity_id_valid(e1), "alloc returns valid id");
    TEST_ASSERT(tc_entity_pool_alive(pool, e1), "entity is alive");
    TEST_ASSERT(tc_entity_pool_count(pool) == 1, "count is 1");

    // Check name
    const char* name = tc_entity_pool_name(pool, e1);
    TEST_ASSERT(strcmp(name, "Entity1") == 0, "entity name");

    // Check UUID
    const char* uuid = tc_entity_pool_uuid(pool, e1);
    TEST_ASSERT(uuid != NULL && strlen(uuid) > 0, "entity has uuid");

    // Find by UUID
    tc_entity_id found = tc_entity_pool_find_by_uuid(pool, uuid);
    TEST_ASSERT(tc_entity_id_eq(found, e1), "find by uuid");

    // Test flags
    TEST_ASSERT(tc_entity_pool_visible(pool, e1) == true, "visible default");
    TEST_ASSERT(tc_entity_pool_active(pool, e1) == true, "active default");

    tc_entity_pool_set_visible(pool, e1, false);
    TEST_ASSERT(tc_entity_pool_visible(pool, e1) == false, "set visible");

    // Test transform
    double pos[3] = {1.0, 2.0, 3.0};
    tc_entity_pool_set_local_position(pool, e1, pos);

    double out_pos[3];
    tc_entity_pool_get_local_position(pool, e1, out_pos);
    TEST_ASSERT(fabs(out_pos[0] - 1.0) < EPSILON, "position x");
    TEST_ASSERT(fabs(out_pos[1] - 2.0) < EPSILON, "position y");
    TEST_ASSERT(fabs(out_pos[2] - 3.0) < EPSILON, "position z");

    // Free entity
    tc_entity_pool_free(pool, e1);
    TEST_ASSERT(!tc_entity_pool_alive(pool, e1), "freed entity not alive");
    TEST_ASSERT(tc_entity_pool_count(pool) == 0, "count back to 0");

    // Old ID should be invalid (generation mismatch)
    tc_entity_id e2 = tc_entity_pool_alloc(pool, "Entity2");
    TEST_ASSERT(e2.index == e1.index, "slot reused");
    TEST_ASSERT(e2.generation > e1.generation, "generation incremented");

    tc_entity_pool_destroy(pool);

    printf("  Entity Pool: PASS\n");
    return 0;
}

// ============================================================================
// Entity Hierarchy tests
// ============================================================================

static int test_entity_hierarchy(void) {
    printf("Testing Entity Hierarchy...\n");

    tc_entity_pool* pool = tc_entity_pool_create(16);

    tc_entity_id parent = tc_entity_pool_alloc(pool, "Parent");
    tc_entity_id child = tc_entity_pool_alloc(pool, "Child");

    // Set positions
    double parent_pos[3] = {10.0, 0.0, 0.0};
    double child_pos[3] = {5.0, 0.0, 0.0};
    tc_entity_pool_set_local_position(pool, parent, parent_pos);
    tc_entity_pool_set_local_position(pool, child, child_pos);

    // Set parent
    tc_entity_pool_set_parent(pool, child, parent);

    TEST_ASSERT(tc_entity_id_eq(tc_entity_pool_parent(pool, child), parent), "child has parent");
    TEST_ASSERT(tc_entity_pool_children_count(pool, parent) == 1, "parent has 1 child");
    TEST_ASSERT(tc_entity_id_eq(tc_entity_pool_child_at(pool, parent, 0), child), "child at 0");

    // Update transforms
    tc_entity_pool_update_transforms(pool);

    // Check world position
    double world_pos[3];
    tc_entity_pool_get_global_position(pool, child, world_pos);
    TEST_ASSERT(fabs(world_pos[0] - 15.0) < EPSILON, "child world pos x");

    tc_entity_pool_destroy(pool);

    printf("  Entity Hierarchy: PASS\n");
    return 0;
}

// ============================================================================
// UUID tests
// ============================================================================

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

// ============================================================================
// tc_value tests
// ============================================================================

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

    // Test vec3
    tc_value v_vec = tc_value_vec3((tc_vec3){1, 2, 3});
    TEST_ASSERT(v_vec.type == TC_VALUE_VEC3, "vec3 type");
    TEST_ASSERT(fabs(v_vec.data.v3.x - 1.0) < EPSILON, "vec3 x");

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

// ============================================================================
// tc_inspect tests
// ============================================================================

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

    tc_inspect_register(&test_desc);

    TEST_ASSERT(tc_inspect_get_type("TestComponent") != NULL, "type registered");
    TEST_ASSERT(tc_inspect_field_count("TestComponent") == 3, "field count");

    const tc_field_desc* speed_field = tc_inspect_find_field("TestComponent", "speed");
    TEST_ASSERT(speed_field != NULL, "find field");
    TEST_ASSERT(strcmp(speed_field->label, "Speed") == 0, "field label");

    TestComponentData data = { .speed = 5.0f, .health = 100, .active = true };

    tc_value v = tc_inspect_get(&data, "TestComponent", "speed");
    TEST_ASSERT(v.type == TC_VALUE_FLOAT, "get returns float");
    TEST_ASSERT(fabs(v.data.f - 5.0f) < 0.001f, "get value");

    tc_inspect_set(&data, "TestComponent", "health", tc_value_int(50));
    TEST_ASSERT(data.health == 50, "set value");

    tc_value serialized = tc_inspect_serialize(&data, "TestComponent");
    TEST_ASSERT(serialized.type == TC_VALUE_DICT, "serialize returns dict");
    TEST_ASSERT(tc_value_dict_has(&serialized, "speed"), "serialized has speed");
    tc_value_free(&serialized);

    tc_inspect_unregister("TestComponent");
    TEST_ASSERT(tc_inspect_get_type("TestComponent") == NULL, "type unregistered");

    printf("  tc_inspect: PASS\n");
    return 0;
}

// ============================================================================
// Kind handler tests
// ============================================================================

static int test_kind_handler(void) {
    printf("Testing kind handlers...\n");

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

// ============================================================================
// Resource map tests
// ============================================================================

typedef struct {
    int value;
} TestResource;

static void test_resource_free(void* ptr) {
    free(ptr);
}

static int test_resource_map(void) {
    printf("Testing Resource Map...\n");

    tc_resource_map* map = tc_resource_map_new(test_resource_free);
    TEST_ASSERT(map != NULL, "map create");
    TEST_ASSERT(tc_resource_map_count(map) == 0, "initial count is 0");

    // Add resources
    TestResource* r1 = malloc(sizeof(TestResource));
    r1->value = 42;
    TEST_ASSERT(tc_resource_map_add(map, "res-001", r1), "add r1");
    TEST_ASSERT(tc_resource_map_count(map) == 1, "count is 1");

    TestResource* r2 = malloc(sizeof(TestResource));
    r2->value = 100;
    TEST_ASSERT(tc_resource_map_add(map, "res-002", r2), "add r2");

    // Get
    TestResource* got = tc_resource_map_get(map, "res-001");
    TEST_ASSERT(got == r1, "get returns r1");
    TEST_ASSERT(got->value == 42, "r1 value");

    // Contains
    TEST_ASSERT(tc_resource_map_contains(map, "res-001"), "contains res-001");
    TEST_ASSERT(!tc_resource_map_contains(map, "res-999"), "not contains res-999");

    // Duplicate rejected
    TestResource* dup = malloc(sizeof(TestResource));
    TEST_ASSERT(!tc_resource_map_add(map, "res-001", dup), "duplicate rejected");
    free(dup);

    // Remove (destructor called)
    TEST_ASSERT(tc_resource_map_remove(map, "res-001"), "remove");
    TEST_ASSERT(tc_resource_map_count(map) == 1, "count is 1 after remove");
    TEST_ASSERT(!tc_resource_map_contains(map, "res-001"), "removed gone");

    tc_resource_map_free(map);

    printf("  Resource Map: PASS\n");
    return 0;
}

// ============================================================================
// Vertex layout tests
// ============================================================================

static int test_vertex_layout(void) {
    printf("Testing Vertex Layout...\n");

    tc_vertex_layout layout;
    tc_vertex_layout_init(&layout);

    TEST_ASSERT(layout.stride == 0, "initial stride is 0");
    TEST_ASSERT(layout.attrib_count == 0, "initial attrib count is 0");

    tc_vertex_layout_add(&layout, "position", 3, TC_ATTRIB_FLOAT32);
    TEST_ASSERT(layout.stride == 12, "stride is 12 after position");

    tc_vertex_layout_add(&layout, "normal", 3, TC_ATTRIB_FLOAT32);
    TEST_ASSERT(layout.stride == 24, "stride is 24 after normal");

    tc_vertex_layout_add(&layout, "uv", 2, TC_ATTRIB_FLOAT32);
    TEST_ASSERT(layout.stride == 32, "stride is 32 after uv");

    const tc_vertex_attrib* pos = tc_vertex_layout_find(&layout, "position");
    TEST_ASSERT(pos != NULL && pos->offset == 0, "position at offset 0");

    const tc_vertex_attrib* uv = tc_vertex_layout_find(&layout, "uv");
    TEST_ASSERT(uv != NULL && uv->offset == 24, "uv at offset 24");

    tc_vertex_layout mesh3 = tc_vertex_layout_pos_normal_uv();
    TEST_ASSERT(mesh3.stride == 32, "predefined mesh3 layout");

    printf("  Vertex Layout: PASS\n");
    return 0;
}

// ============================================================================
// Mesh tests (global API)
// ============================================================================

static int test_mesh(void) {
    printf("Testing Mesh...\n");

    tc_mesh_init();
    TEST_ASSERT(tc_mesh_count() == 0, "initial count is 0");

    // Add mesh
    tc_mesh* mesh1 = tc_mesh_add("test-mesh-001");
    TEST_ASSERT(mesh1 != NULL, "add returns mesh");
    TEST_ASSERT(tc_mesh_count() == 1, "count is 1");
    TEST_ASSERT(strcmp(mesh1->uuid, "test-mesh-001") == 0, "uuid matches");

    // Get by UUID
    TEST_ASSERT(tc_mesh_get("test-mesh-001") == mesh1, "get returns same mesh");
    TEST_ASSERT(tc_mesh_contains("test-mesh-001"), "contains");

    // Set data
    tc_vertex_layout layout = tc_vertex_layout_pos_normal_uv();
    float verts[] = {
        0, 0, 0,  0, 1, 0,  0, 0,
        1, 0, 0,  0, 1, 0,  1, 0,
        0, 0, 1,  0, 1, 0,  0, 1,
    };
    uint32_t idx[] = { 0, 1, 2 };

    tc_mesh_set_data(mesh1, verts, 3, &layout, idx, 3, "test-mesh");
    TEST_ASSERT(mesh1->vertex_count == 3, "vertex count");
    TEST_ASSERT(mesh1->index_count == 3, "index count");
    TEST_ASSERT(mesh1->version == 2, "version is 2");

    // Duplicate rejected
    TEST_ASSERT(tc_mesh_add("test-mesh-001") == NULL, "duplicate rejected");

    // Auto UUID
    tc_mesh* mesh2 = tc_mesh_add(NULL);
    TEST_ASSERT(mesh2 != NULL, "auto uuid works");
    TEST_ASSERT(tc_mesh_count() == 2, "count is 2");

    // Remove
    TEST_ASSERT(tc_mesh_remove("test-mesh-001"), "remove");
    TEST_ASSERT(tc_mesh_count() == 1, "count is 1");

    tc_mesh_shutdown();

    printf("  Mesh: PASS\n");
    return 0;
}

// ============================================================================
// Main
// ============================================================================

int main(void) {
    printf("=== Termin Core Tests ===\n");
    printf("Version: %s\n\n", tc_version());

    tc_init();

    int result = 0;

    result |= test_vec3();
    result |= test_quat();
    result |= test_entity_pool();
    result |= test_entity_hierarchy();
    result |= test_uuid();
    result |= test_tc_value();
    result |= test_inspect();
    result |= test_kind_handler();
    result |= test_resource_map();
    result |= test_vertex_layout();
    result |= test_mesh();

    tc_shutdown();

    printf("\n");
    if (result == 0) {
        printf("=== ALL TESTS PASSED ===\n");
    } else {
        printf("=== SOME TESTS FAILED ===\n");
    }

    return result;
}
