// test_archetype.c - Tests for SoA archetype storage
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "core/tc_archetype.h"
#include "core/tc_entity_pool.h"

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            printf("FAIL: %s (line %d)\n", msg, __LINE__); \
            return 1; \
        } \
    } while(0)

// ============================================================================
// Test data types
// ============================================================================

typedef struct {
    float x, y, z;
} Vec3f;

typedef struct {
    Vec3f linear;
    Vec3f angular;
} Velocity;

typedef struct {
    float current;
    float max;
} Health;

typedef struct {
    int state;
    float timer;
} AIState;

// ============================================================================
// Destroy tracking for leak detection
// ============================================================================

static int g_velocity_destroy_count = 0;
static int g_health_destroy_count = 0;
static int g_ai_destroy_count = 0;

static void velocity_destroy(void* ptr) {
    (void)ptr;
    g_velocity_destroy_count++;
}

static void health_init(void* ptr) {
    Health* h = (Health*)ptr;
    h->current = 100.0f;
    h->max = 100.0f;
}

static void health_destroy(void* ptr) {
    (void)ptr;
    g_health_destroy_count++;
}

static void ai_destroy(void* ptr) {
    (void)ptr;
    g_ai_destroy_count++;
}

static void reset_destroy_counts(void) {
    g_velocity_destroy_count = 0;
    g_health_destroy_count = 0;
    g_ai_destroy_count = 0;
}

// ============================================================================
// Test: Type Registry
// ============================================================================

static int test_type_registry(void) {
    printf("Testing SoA Type Registry...\n");

    tc_soa_type_registry reg;
    memset(&reg, 0, sizeof(reg));

    tc_soa_type_id vel_id = tc_soa_register_type(&reg, &(tc_soa_type_desc){
        .name = "Velocity", .element_size = sizeof(Velocity),
    });
    TEST_ASSERT(vel_id == 0, "first type gets id 0");
    TEST_ASSERT(reg.count == 1, "count is 1");

    tc_soa_type_id hp_id = tc_soa_register_type(&reg, &(tc_soa_type_desc){
        .name = "Health", .element_size = sizeof(Health),
        .init = health_init,
    });
    TEST_ASSERT(hp_id == 1, "second type gets id 1");

    const tc_soa_type_desc* desc = tc_soa_get_type(&reg, vel_id);
    TEST_ASSERT(desc != NULL, "get type 0");
    TEST_ASSERT(desc->element_size == sizeof(Velocity), "velocity size");

    desc = tc_soa_get_type(&reg, hp_id);
    TEST_ASSERT(desc != NULL, "get type 1");
    TEST_ASSERT(desc->init == health_init, "health init callback");

    // Invalid id
    TEST_ASSERT(tc_soa_get_type(&reg, 99) == NULL, "invalid id returns NULL");

    // Zero-size rejected
    tc_soa_type_id bad = tc_soa_register_type(&reg, &(tc_soa_type_desc){
        .name = "Bad", .element_size = 0,
    });
    TEST_ASSERT(bad == TC_SOA_TYPE_INVALID, "zero-size rejected");

    // Free names
    free((char*)reg.types[0].name);
    free((char*)reg.types[1].name);

    printf("  SoA Type Registry: PASS\n");
    return 0;
}

// ============================================================================
// Test: Archetype basic ops
// ============================================================================

static int test_archetype_basic(void) {
    printf("Testing Archetype Basic...\n");

    reset_destroy_counts();

    tc_soa_type_registry reg;
    memset(&reg, 0, sizeof(reg));

    tc_soa_type_id vel_id = tc_soa_register_type(&reg, &(tc_soa_type_desc){
        .name = "Velocity", .element_size = sizeof(Velocity),
        .destroy = velocity_destroy,
    });
    tc_soa_type_id hp_id = tc_soa_register_type(&reg, &(tc_soa_type_desc){
        .name = "Health", .element_size = sizeof(Health),
        .init = health_init, .destroy = health_destroy,
    });

    tc_soa_type_id types[] = { vel_id, hp_id };
    uint64_t mask = (1ULL << vel_id) | (1ULL << hp_id);
    tc_archetype* arch = tc_archetype_create(mask, types, 2, &reg);
    TEST_ASSERT(arch != NULL, "archetype created");
    TEST_ASSERT(arch->type_mask == mask, "mask correct");
    TEST_ASSERT(arch->type_count == 2, "type_count is 2");
    TEST_ASSERT(arch->count == 0, "empty initially");

    // Alloc entities
    tc_entity_id e0 = {0, 1};
    tc_entity_id e1 = {1, 1};
    tc_entity_id e2 = {2, 1};

    uint32_t row0 = tc_archetype_alloc_row(arch, e0, &reg);
    uint32_t row1 = tc_archetype_alloc_row(arch, e1, &reg);
    uint32_t row2 = tc_archetype_alloc_row(arch, e2, &reg);
    TEST_ASSERT(arch->count == 3, "count is 3");
    TEST_ASSERT(row0 == 0 && row1 == 1 && row2 == 2, "rows sequential");

    // Check health was initialized
    Health* hp_arr = (Health*)tc_archetype_get_array(arch, hp_id);
    TEST_ASSERT(hp_arr != NULL, "health array exists");
    TEST_ASSERT(hp_arr[0].current == 100.0f, "e0 health init");
    TEST_ASSERT(hp_arr[1].current == 100.0f, "e1 health init");
    TEST_ASSERT(hp_arr[2].current == 100.0f, "e2 health init");

    // Write velocity data
    Velocity* vel_arr = (Velocity*)tc_archetype_get_array(arch, vel_id);
    vel_arr[0].linear = (Vec3f){1, 0, 0};
    vel_arr[1].linear = (Vec3f){0, 2, 0};
    vel_arr[2].linear = (Vec3f){0, 0, 3};

    // Get element
    Velocity* v1 = (Velocity*)tc_archetype_get_element(arch, 1, vel_id, &reg);
    TEST_ASSERT(v1 != NULL, "get_element works");
    TEST_ASSERT(v1->linear.y == 2.0f, "v1 data correct");

    // Non-existent type
    TEST_ASSERT(tc_archetype_get_array(arch, 99) == NULL, "missing type returns NULL");

    // Free row 1 (swap-remove: e2 moves to row 1)
    tc_entity_id swapped = tc_archetype_free_row(arch, 1, &reg);
    TEST_ASSERT(arch->count == 2, "count is 2 after free");
    TEST_ASSERT(tc_entity_id_eq(swapped, e2), "e2 swapped into row 1");
    TEST_ASSERT(tc_entity_id_eq(arch->entities[1], e2), "entities[1] is e2");

    // e2's velocity should now be at row 1
    TEST_ASSERT(vel_arr[1].linear.z == 3.0f, "swapped velocity data correct");

    // Destroy counters: row 1 was destroyed (velocity + health)
    TEST_ASSERT(g_velocity_destroy_count == 1, "velocity destroy called once");
    TEST_ASSERT(g_health_destroy_count == 1, "health destroy called once");

    // Destroy archetype: remaining 2 entities destroyed
    tc_archetype_destroy(arch, &reg);
    TEST_ASSERT(g_velocity_destroy_count == 3, "all velocities destroyed");
    TEST_ASSERT(g_health_destroy_count == 3, "all healths destroyed");

    free((char*)reg.types[0].name);
    free((char*)reg.types[1].name);

    printf("  Archetype Basic: PASS\n");
    return 0;
}

// ============================================================================
// Test: Entity pool SoA integration
// ============================================================================

static int test_pool_soa_basic(void) {
    printf("Testing Pool SoA Basic...\n");

    reset_destroy_counts();

    tc_entity_pool* pool = tc_entity_pool_create(16);
    TEST_ASSERT(pool != NULL, "pool created");

    tc_soa_type_id vel_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Velocity", .element_size = sizeof(Velocity),
        .destroy = velocity_destroy,
    });
    tc_soa_type_id hp_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Health", .element_size = sizeof(Health),
        .init = health_init, .destroy = health_destroy,
    });
    TEST_ASSERT(vel_id == 0, "vel_id is 0");
    TEST_ASSERT(hp_id == 1, "hp_id is 1");

    // Create entity and add SoA components
    tc_entity_id e = tc_entity_pool_alloc(pool, "test_entity");
    TEST_ASSERT(tc_entity_pool_alive(pool, e), "entity alive");

    TEST_ASSERT(!tc_entity_pool_has_soa(pool, e, vel_id), "no velocity yet");
    TEST_ASSERT(tc_entity_pool_soa_mask(pool, e) == 0, "mask is 0");

    // Add velocity
    tc_entity_pool_add_soa(pool, e, vel_id);
    TEST_ASSERT(tc_entity_pool_has_soa(pool, e, vel_id), "has velocity");
    TEST_ASSERT(!tc_entity_pool_has_soa(pool, e, hp_id), "no health");
    TEST_ASSERT(tc_entity_pool_soa_mask(pool, e) == (1ULL << vel_id), "mask has vel");

    // Write data
    Velocity* vel = (Velocity*)tc_entity_pool_get_soa(pool, e, vel_id);
    TEST_ASSERT(vel != NULL, "get velocity");
    vel->linear = (Vec3f){10, 20, 30};

    // Add health (entity migrates to new archetype)
    tc_entity_pool_add_soa(pool, e, hp_id);
    TEST_ASSERT(tc_entity_pool_has_soa(pool, e, vel_id), "still has velocity");
    TEST_ASSERT(tc_entity_pool_has_soa(pool, e, hp_id), "now has health");

    // Velocity data should survive archetype migration
    vel = (Velocity*)tc_entity_pool_get_soa(pool, e, vel_id);
    TEST_ASSERT(vel != NULL, "velocity survived migration");
    TEST_ASSERT(vel->linear.x == 10.0f && vel->linear.y == 20.0f && vel->linear.z == 30.0f,
                "velocity data intact after migration");

    // Health should be initialized
    Health* hp = (Health*)tc_entity_pool_get_soa(pool, e, hp_id);
    TEST_ASSERT(hp != NULL, "get health");
    TEST_ASSERT(hp->current == 100.0f, "health initialized");

    // Duplicate add is no-op
    tc_entity_pool_add_soa(pool, e, vel_id);
    TEST_ASSERT(tc_entity_pool_soa_mask(pool, e) == ((1ULL << vel_id) | (1ULL << hp_id)),
                "duplicate add is no-op");

    tc_entity_pool_destroy(pool);

    printf("  Pool SoA Basic: PASS\n");
    return 0;
}

// ============================================================================
// Test: Multiple entities in same archetype
// ============================================================================

static int test_pool_soa_multiple_entities(void) {
    printf("Testing Pool SoA Multiple Entities...\n");

    reset_destroy_counts();

    tc_entity_pool* pool = tc_entity_pool_create(16);

    tc_soa_type_id vel_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Velocity", .element_size = sizeof(Velocity),
        .destroy = velocity_destroy,
    });
    tc_soa_type_id hp_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Health", .element_size = sizeof(Health),
        .init = health_init, .destroy = health_destroy,
    });

    // Create 5 entities all with [Velocity, Health]
    tc_entity_id entities[5];
    for (int i = 0; i < 5; i++) {
        char name[32];
        snprintf(name, sizeof(name), "entity_%d", i);
        entities[i] = tc_entity_pool_alloc(pool, name);
        tc_entity_pool_add_soa(pool, entities[i], vel_id);
        tc_entity_pool_add_soa(pool, entities[i], hp_id);

        // Write distinct velocity
        Velocity* v = (Velocity*)tc_entity_pool_get_soa(pool, entities[i], vel_id);
        v->linear = (Vec3f){(float)i, (float)(i * 10), (float)(i * 100)};
    }

    // Verify all data
    for (int i = 0; i < 5; i++) {
        Velocity* v = (Velocity*)tc_entity_pool_get_soa(pool, entities[i], vel_id);
        TEST_ASSERT(v != NULL, "entity has velocity");
        TEST_ASSERT(v->linear.x == (float)i, "velocity.x correct");
        TEST_ASSERT(v->linear.y == (float)(i * 10), "velocity.y correct");
        TEST_ASSERT(v->linear.z == (float)(i * 100), "velocity.z correct");

        Health* h = (Health*)tc_entity_pool_get_soa(pool, entities[i], hp_id);
        TEST_ASSERT(h != NULL, "entity has health");
        TEST_ASSERT(h->current == 100.0f, "health correct");
    }

    // Delete entity in the middle
    tc_entity_pool_free(pool, entities[2]);

    // Others should still be accessible with correct data
    for (int i = 0; i < 5; i++) {
        if (i == 2) continue;
        TEST_ASSERT(tc_entity_pool_alive(pool, entities[i]), "entity alive");
        Velocity* v = (Velocity*)tc_entity_pool_get_soa(pool, entities[i], vel_id);
        TEST_ASSERT(v != NULL, "velocity after delete");
        TEST_ASSERT(v->linear.x == (float)i, "velocity data intact after neighbor delete");
    }

    tc_entity_pool_destroy(pool);

    printf("  Pool SoA Multiple Entities: PASS\n");
    return 0;
}

// ============================================================================
// Test: Remove SoA component (archetype downgrade)
// ============================================================================

static int test_pool_soa_remove(void) {
    printf("Testing Pool SoA Remove...\n");

    reset_destroy_counts();

    tc_entity_pool* pool = tc_entity_pool_create(16);

    tc_soa_type_id vel_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Velocity", .element_size = sizeof(Velocity),
        .destroy = velocity_destroy,
    });
    tc_soa_type_id hp_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Health", .element_size = sizeof(Health),
        .init = health_init, .destroy = health_destroy,
    });

    tc_entity_id e = tc_entity_pool_alloc(pool, "test");
    tc_entity_pool_add_soa(pool, e, vel_id);
    tc_entity_pool_add_soa(pool, e, hp_id);

    // Write data
    Velocity* v = (Velocity*)tc_entity_pool_get_soa(pool, e, vel_id);
    v->linear = (Vec3f){99, 88, 77};

    // Remove health — entity migrates from [vel, hp] to [vel]
    tc_entity_pool_remove_soa(pool, e, hp_id);
    TEST_ASSERT(tc_entity_pool_has_soa(pool, e, vel_id), "still has velocity");
    TEST_ASSERT(!tc_entity_pool_has_soa(pool, e, hp_id), "health removed");

    // Velocity data should survive
    v = (Velocity*)tc_entity_pool_get_soa(pool, e, vel_id);
    TEST_ASSERT(v != NULL, "velocity exists");
    TEST_ASSERT(v->linear.x == 99.0f, "velocity.x survived");
    TEST_ASSERT(v->linear.y == 88.0f, "velocity.y survived");

    // Remove velocity — entity has no SoA components
    tc_entity_pool_remove_soa(pool, e, vel_id);
    TEST_ASSERT(!tc_entity_pool_has_soa(pool, e, vel_id), "velocity removed");
    TEST_ASSERT(tc_entity_pool_soa_mask(pool, e) == 0, "mask is 0");
    TEST_ASSERT(tc_entity_pool_get_soa(pool, e, vel_id) == NULL, "get returns NULL");

    // Entity is still alive (just has no SoA components)
    TEST_ASSERT(tc_entity_pool_alive(pool, e), "entity still alive");

    tc_entity_pool_destroy(pool);

    printf("  Pool SoA Remove: PASS\n");
    return 0;
}

// ============================================================================
// Test: Query across archetypes
// ============================================================================

static int test_query(void) {
    printf("Testing SoA Query...\n");

    tc_entity_pool* pool = tc_entity_pool_create(32);

    tc_soa_type_id vel_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Velocity", .element_size = sizeof(Velocity),
    });
    tc_soa_type_id hp_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Health", .element_size = sizeof(Health),
        .init = health_init,
    });
    tc_soa_type_id ai_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "AI", .element_size = sizeof(AIState),
    });

    // Create entities with different component sets:
    // Group A: [Velocity, Health] — 3 entities
    tc_entity_id group_a[3];
    for (int i = 0; i < 3; i++) {
        group_a[i] = tc_entity_pool_alloc(pool, "group_a");
        tc_entity_pool_add_soa(pool, group_a[i], vel_id);
        tc_entity_pool_add_soa(pool, group_a[i], hp_id);

        Velocity* v = (Velocity*)tc_entity_pool_get_soa(pool, group_a[i], vel_id);
        v->linear.x = (float)(i + 1);
    }

    // Group B: [Velocity, Health, AI] — 2 entities
    tc_entity_id group_b[2];
    for (int i = 0; i < 2; i++) {
        group_b[i] = tc_entity_pool_alloc(pool, "group_b");
        tc_entity_pool_add_soa(pool, group_b[i], vel_id);
        tc_entity_pool_add_soa(pool, group_b[i], hp_id);
        tc_entity_pool_add_soa(pool, group_b[i], ai_id);

        Velocity* v = (Velocity*)tc_entity_pool_get_soa(pool, group_b[i], vel_id);
        v->linear.x = (float)(i + 100);
    }

    // Group C: [Health] — 1 entity (no velocity!)
    tc_entity_id group_c = tc_entity_pool_alloc(pool, "group_c");
    tc_entity_pool_add_soa(pool, group_c, hp_id);

    // Query: all entities with Velocity + Health (should match groups A and B)
    // Need to access pool internals for query - use the archetype arrays
    // For now construct query from pool's archetype data
    // We'll use a helper to get pool's archetypes

    // Access pool internals through the C API
    // The query needs archetype array — we'll test through the public archetype API
    // Since tc_soa_query_init takes archetype** directly, and pool stores them internally,
    // we need to access pool fields. Let's use tc_entity_pool_get_soa to verify instead.

    // Alternative: test query through archetype API directly
    // But we don't have pool->archetypes exposed...
    // Let's verify by iterating all entities and checking masks

    // Verify group A: mask = vel | hp
    uint64_t mask_vel_hp = (1ULL << vel_id) | (1ULL << hp_id);
    for (int i = 0; i < 3; i++) {
        uint64_t m = tc_entity_pool_soa_mask(pool, group_a[i]);
        TEST_ASSERT(m == mask_vel_hp, "group_a mask correct");
    }

    // Verify group B: mask = vel | hp | ai
    uint64_t mask_vel_hp_ai = (1ULL << vel_id) | (1ULL << hp_id) | (1ULL << ai_id);
    for (int i = 0; i < 2; i++) {
        uint64_t m = tc_entity_pool_soa_mask(pool, group_b[i]);
        TEST_ASSERT(m == mask_vel_hp_ai, "group_b mask correct");
    }

    // Verify group C: mask = hp only
    TEST_ASSERT(tc_entity_pool_soa_mask(pool, group_c) == (1ULL << hp_id), "group_c mask correct");

    // All entities with velocity should have correct data
    float sum_x = 0;
    for (int i = 0; i < 3; i++) {
        Velocity* v = (Velocity*)tc_entity_pool_get_soa(pool, group_a[i], vel_id);
        sum_x += v->linear.x;
    }
    for (int i = 0; i < 2; i++) {
        Velocity* v = (Velocity*)tc_entity_pool_get_soa(pool, group_b[i], vel_id);
        sum_x += v->linear.x;
    }
    // group_a: 1+2+3=6, group_b: 100+101=201, total=207
    TEST_ASSERT(sum_x == 207.0f, "velocity sum across archetypes");

    // group_c should not have velocity
    TEST_ASSERT(tc_entity_pool_get_soa(pool, group_c, vel_id) == NULL, "group_c has no velocity");

    tc_entity_pool_destroy(pool);

    printf("  SoA Query: PASS\n");
    return 0;
}

// ============================================================================
// Test: Query API (tc_soa_query)
// ============================================================================

static int test_query_api(void) {
    printf("Testing SoA Query API...\n");

    tc_soa_type_registry reg;
    memset(&reg, 0, sizeof(reg));

    tc_soa_type_id vel_id = tc_soa_register_type(&reg, &(tc_soa_type_desc){
        .name = "Velocity", .element_size = sizeof(Velocity),
    });
    tc_soa_type_id hp_id = tc_soa_register_type(&reg, &(tc_soa_type_desc){
        .name = "Health", .element_size = sizeof(Health),
        .init = health_init,
    });
    tc_soa_type_id ai_id = tc_soa_register_type(&reg, &(tc_soa_type_desc){
        .name = "AI", .element_size = sizeof(AIState),
    });

    // Create 3 archetypes
    tc_soa_type_id types_vh[] = { vel_id, hp_id };
    tc_soa_type_id types_vha[] = { vel_id, hp_id, ai_id };
    tc_soa_type_id types_h[] = { hp_id };

    uint64_t mask_vh = (1ULL << vel_id) | (1ULL << hp_id);
    uint64_t mask_vha = mask_vh | (1ULL << ai_id);
    uint64_t mask_h = (1ULL << hp_id);

    tc_archetype* arch_vh = tc_archetype_create(mask_vh, types_vh, 2, &reg);
    tc_archetype* arch_vha = tc_archetype_create(mask_vha, types_vha, 3, &reg);
    tc_archetype* arch_h = tc_archetype_create(mask_h, types_h, 1, &reg);

    // Populate
    tc_entity_id e0 = {0, 1}, e1 = {1, 1}, e2 = {2, 1}, e3 = {3, 1}, e4 = {4, 1};

    tc_archetype_alloc_row(arch_vh, e0, &reg);
    tc_archetype_alloc_row(arch_vh, e1, &reg);

    tc_archetype_alloc_row(arch_vha, e2, &reg);

    tc_archetype_alloc_row(arch_h, e3, &reg);
    tc_archetype_alloc_row(arch_h, e4, &reg);

    // Write velocities
    Velocity* v_vh = (Velocity*)tc_archetype_get_array(arch_vh, vel_id);
    v_vh[0].linear.x = 1.0f;
    v_vh[1].linear.x = 2.0f;

    Velocity* v_vha = (Velocity*)tc_archetype_get_array(arch_vha, vel_id);
    v_vha[0].linear.x = 3.0f;

    tc_archetype* all_archetypes[] = { arch_vh, arch_vha, arch_h };

    // Query: entities with Velocity (should match arch_vh and arch_vha)
    tc_soa_type_id req_vel[] = { vel_id };
    tc_soa_query q = tc_soa_query_init(all_archetypes, 3, req_vel, 1, NULL, 0);

    void* data_ptrs[3];
    tc_soa_chunk chunk;
    chunk.data = data_ptrs;

    int total_entities = 0;
    float total_x = 0;

    while (tc_soa_query_next(&q, &chunk)) {
        Velocity* velocities = (Velocity*)chunk.data[0];
        for (size_t i = 0; i < chunk.count; i++) {
            total_x += velocities[i].linear.x;
        }
        total_entities += (int)chunk.count;
    }

    TEST_ASSERT(total_entities == 3, "query found 3 entities with velocity");
    TEST_ASSERT(total_x == 6.0f, "velocity sum is 6.0");

    // Query: entities with Health (should match all 3 archetypes)
    tc_soa_type_id req_hp[] = { hp_id };
    q = tc_soa_query_init(all_archetypes, 3, req_hp, 1, NULL, 0);
    total_entities = 0;

    while (tc_soa_query_next(&q, &chunk)) {
        total_entities += (int)chunk.count;
    }
    TEST_ASSERT(total_entities == 5, "query found 5 entities with health");

    // Query: entities with Velocity + AI (should match only arch_vha)
    tc_soa_type_id req_vel_ai[] = { vel_id, ai_id };
    q = tc_soa_query_init(all_archetypes, 3, req_vel_ai, 2, NULL, 0);
    total_entities = 0;

    while (tc_soa_query_next(&q, &chunk)) {
        total_entities += (int)chunk.count;
    }
    TEST_ASSERT(total_entities == 1, "query found 1 entity with vel+ai");

    // Query with exclusion: Health but NOT Velocity
    tc_soa_type_id excl_vel[] = { vel_id };
    q = tc_soa_query_init(all_archetypes, 3, req_hp, 1, excl_vel, 1);
    total_entities = 0;

    while (tc_soa_query_next(&q, &chunk)) {
        total_entities += (int)chunk.count;
    }
    TEST_ASSERT(total_entities == 2, "query found 2 entities with health but not velocity");

    // Cleanup
    tc_archetype_destroy(arch_vh, &reg);
    tc_archetype_destroy(arch_vha, &reg);
    tc_archetype_destroy(arch_h, &reg);
    free((char*)reg.types[0].name);
    free((char*)reg.types[1].name);
    free((char*)reg.types[2].name);

    printf("  SoA Query API: PASS\n");
    return 0;
}

// ============================================================================
// Test: Destroy tracking (leak detection)
// ============================================================================

static int test_destroy_tracking(void) {
    printf("Testing Destroy Tracking...\n");

    reset_destroy_counts();

    tc_entity_pool* pool = tc_entity_pool_create(16);

    tc_soa_type_id vel_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Velocity", .element_size = sizeof(Velocity),
        .destroy = velocity_destroy,
    });
    tc_soa_type_id hp_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Health", .element_size = sizeof(Health),
        .destroy = health_destroy,
    });

    // Create 3 entities with [vel, hp]
    tc_entity_id entities[3];
    for (int i = 0; i < 3; i++) {
        entities[i] = tc_entity_pool_alloc(pool, "test");
        tc_entity_pool_add_soa(pool, entities[i], vel_id);
        tc_entity_pool_add_soa(pool, entities[i], hp_id);
    }

    // Delete one entity — should call destroy for vel + hp
    reset_destroy_counts();
    tc_entity_pool_free(pool, entities[1]);
    TEST_ASSERT(g_velocity_destroy_count == 1, "1 velocity destroyed on entity free");
    TEST_ASSERT(g_health_destroy_count == 1, "1 health destroyed on entity free");

    // Destroy pool — remaining 2 entities should be cleaned up
    reset_destroy_counts();
    tc_entity_pool_destroy(pool);
    TEST_ASSERT(g_velocity_destroy_count == 2, "2 velocities destroyed on pool destroy");
    TEST_ASSERT(g_health_destroy_count == 2, "2 healths destroyed on pool destroy");

    printf("  Destroy Tracking: PASS\n");
    return 0;
}

// ============================================================================
// Test: Heavy migration (many archetype transitions)
// ============================================================================

static int test_heavy_migration(void) {
    printf("Testing Heavy Migration...\n");

    reset_destroy_counts();

    tc_entity_pool* pool = tc_entity_pool_create(16);

    tc_soa_type_id types[4];
    types[0] = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "A", .element_size = sizeof(float),
    });
    types[1] = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "B", .element_size = sizeof(float),
    });
    types[2] = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "C", .element_size = sizeof(float),
    });
    types[3] = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "D", .element_size = sizeof(float),
    });

    tc_entity_id e = tc_entity_pool_alloc(pool, "migrator");

    // Add A, write value
    tc_entity_pool_add_soa(pool, e, types[0]);
    *(float*)tc_entity_pool_get_soa(pool, e, types[0]) = 1.0f;

    // Add B — migrate [A] → [A,B]
    tc_entity_pool_add_soa(pool, e, types[1]);
    *(float*)tc_entity_pool_get_soa(pool, e, types[1]) = 2.0f;
    TEST_ASSERT(*(float*)tc_entity_pool_get_soa(pool, e, types[0]) == 1.0f, "A survives A→AB");

    // Add C — migrate [A,B] → [A,B,C]
    tc_entity_pool_add_soa(pool, e, types[2]);
    *(float*)tc_entity_pool_get_soa(pool, e, types[2]) = 3.0f;
    TEST_ASSERT(*(float*)tc_entity_pool_get_soa(pool, e, types[0]) == 1.0f, "A survives AB→ABC");
    TEST_ASSERT(*(float*)tc_entity_pool_get_soa(pool, e, types[1]) == 2.0f, "B survives AB→ABC");

    // Add D — migrate [A,B,C] → [A,B,C,D]
    tc_entity_pool_add_soa(pool, e, types[3]);
    *(float*)tc_entity_pool_get_soa(pool, e, types[3]) = 4.0f;
    TEST_ASSERT(*(float*)tc_entity_pool_get_soa(pool, e, types[0]) == 1.0f, "A survives ABC→ABCD");
    TEST_ASSERT(*(float*)tc_entity_pool_get_soa(pool, e, types[1]) == 2.0f, "B survives ABC→ABCD");
    TEST_ASSERT(*(float*)tc_entity_pool_get_soa(pool, e, types[2]) == 3.0f, "C survives ABC→ABCD");

    // Remove B — migrate [A,B,C,D] → [A,C,D]
    tc_entity_pool_remove_soa(pool, e, types[1]);
    TEST_ASSERT(!tc_entity_pool_has_soa(pool, e, types[1]), "B removed");
    TEST_ASSERT(*(float*)tc_entity_pool_get_soa(pool, e, types[0]) == 1.0f, "A survives ABCD→ACD");
    TEST_ASSERT(*(float*)tc_entity_pool_get_soa(pool, e, types[2]) == 3.0f, "C survives ABCD→ACD");
    TEST_ASSERT(*(float*)tc_entity_pool_get_soa(pool, e, types[3]) == 4.0f, "D survives ABCD→ACD");

    // Remove all
    tc_entity_pool_remove_soa(pool, e, types[0]);
    tc_entity_pool_remove_soa(pool, e, types[2]);
    tc_entity_pool_remove_soa(pool, e, types[3]);
    TEST_ASSERT(tc_entity_pool_soa_mask(pool, e) == 0, "all removed");
    TEST_ASSERT(tc_entity_pool_alive(pool, e), "entity still alive");

    tc_entity_pool_destroy(pool);

    printf("  Heavy Migration: PASS\n");
    return 0;
}

// ============================================================================
// Test: Swap-remove correctness with multiple entities
// ============================================================================

static int test_swap_remove_correctness(void) {
    printf("Testing Swap-Remove Correctness...\n");

    tc_entity_pool* pool = tc_entity_pool_create(32);

    tc_soa_type_id val_id = tc_entity_pool_register_soa_type(pool, &(tc_soa_type_desc){
        .name = "Value", .element_size = sizeof(float),
    });

    // Create 10 entities, all with same archetype
    tc_entity_id entities[10];
    for (int i = 0; i < 10; i++) {
        entities[i] = tc_entity_pool_alloc(pool, "e");
        tc_entity_pool_add_soa(pool, entities[i], val_id);
        *(float*)tc_entity_pool_get_soa(pool, entities[i], val_id) = (float)(i * 11);
    }

    // Delete entities in various orders: 3, 7, 0, 5
    int delete_order[] = {3, 7, 0, 5};
    for (int d = 0; d < 4; d++) {
        tc_entity_pool_free(pool, entities[delete_order[d]]);
    }

    // Remaining: 1, 2, 4, 6, 8, 9
    int remaining[] = {1, 2, 4, 6, 8, 9};
    for (int r = 0; r < 6; r++) {
        int i = remaining[r];
        TEST_ASSERT(tc_entity_pool_alive(pool, entities[i]), "entity alive");
        float* val = (float*)tc_entity_pool_get_soa(pool, entities[i], val_id);
        TEST_ASSERT(val != NULL, "value accessible");
        TEST_ASSERT(*val == (float)(i * 11), "value correct after swap-removes");
    }

    tc_entity_pool_destroy(pool);

    printf("  Swap-Remove Correctness: PASS\n");
    return 0;
}

// ============================================================================
// Main
// ============================================================================

int main(void) {
    printf("=== Archetype Tests ===\n\n");

    int result = 0;

    result |= test_type_registry();
    result |= test_archetype_basic();
    result |= test_pool_soa_basic();
    result |= test_pool_soa_multiple_entities();
    result |= test_pool_soa_remove();
    result |= test_query();
    result |= test_query_api();
    result |= test_destroy_tracking();
    result |= test_heavy_migration();
    result |= test_swap_remove_correctness();

    printf("\n");
    if (result == 0) {
        printf("=== ALL TESTS PASSED ===\n");
    } else {
        printf("=== SOME TESTS FAILED ===\n");
    }

    return result;
}
