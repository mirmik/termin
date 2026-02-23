// test_data_structures.c - Tests for tc_pool, tc_hash_map, tc_dlist
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tgfx/tc_pool.h>
#include "tc_hash_map.h"
#include "core/tc_dlist.h"

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            printf("FAIL: %s (line %d)\n", msg, __LINE__); \
            return 1; \
        } \
    } while(0)

// ============================================================================
// tc_pool tests
// ============================================================================

typedef struct {
    int value;
    char name[32];
} TestItem;

static int test_pool_basic(void) {
    printf("Testing Pool Basic...\n");

    tc_pool pool;
    TEST_ASSERT(tc_pool_init(&pool, sizeof(TestItem), 4), "pool init");
    TEST_ASSERT(pool.capacity == 4, "initial capacity");
    TEST_ASSERT(tc_pool_count(&pool) == 0, "initial count is 0");

    // Allocate first item
    tc_handle h1 = tc_pool_alloc(&pool);
    TEST_ASSERT(!tc_handle_is_invalid(h1), "alloc h1");
    TEST_ASSERT(tc_pool_count(&pool) == 1, "count is 1");
    TEST_ASSERT(tc_pool_is_valid(&pool, h1), "h1 is valid");

    // Get and modify item
    TestItem* item1 = (TestItem*)tc_pool_get(&pool, h1);
    TEST_ASSERT(item1 != NULL, "get h1");
    item1->value = 42;
    strcpy(item1->name, "first");

    // Verify data persists
    TestItem* item1_again = (TestItem*)tc_pool_get(&pool, h1);
    TEST_ASSERT(item1_again->value == 42, "value persists");
    TEST_ASSERT(strcmp(item1_again->name, "first") == 0, "name persists");

    // Allocate more items
    tc_handle h2 = tc_pool_alloc(&pool);
    tc_handle h3 = tc_pool_alloc(&pool);
    TEST_ASSERT(tc_pool_count(&pool) == 3, "count is 3");

    // Free middle item
    TEST_ASSERT(tc_pool_free_slot(&pool, h2), "free h2");
    TEST_ASSERT(tc_pool_count(&pool) == 2, "count is 2");
    TEST_ASSERT(!tc_pool_is_valid(&pool, h2), "h2 no longer valid");

    // h1 and h3 still valid
    TEST_ASSERT(tc_pool_is_valid(&pool, h1), "h1 still valid");
    TEST_ASSERT(tc_pool_is_valid(&pool, h3), "h3 still valid");

    tc_pool_free(&pool);
    printf("  Pool Basic: PASS\n");
    return 0;
}

static int test_pool_generation(void) {
    printf("Testing Pool Generation...\n");

    tc_pool pool;
    tc_pool_init(&pool, sizeof(TestItem), 4);

    // Allocate and free
    tc_handle h1 = tc_pool_alloc(&pool);
    uint32_t gen1 = h1.generation;
    tc_pool_free_slot(&pool, h1);

    // Reallocate same slot
    tc_handle h2 = tc_pool_alloc(&pool);
    TEST_ASSERT(h2.index == h1.index, "same slot reused");
    TEST_ASSERT(h2.generation > gen1, "generation incremented");

    // Old handle is now invalid
    TEST_ASSERT(!tc_pool_is_valid(&pool, h1), "old handle invalid");
    TEST_ASSERT(tc_pool_is_valid(&pool, h2), "new handle valid");
    TEST_ASSERT(tc_pool_get(&pool, h1) == NULL, "get with old handle returns NULL");

    tc_pool_free(&pool);
    printf("  Pool Generation: PASS\n");
    return 0;
}

static int test_pool_growth(void) {
    printf("Testing Pool Growth...\n");

    tc_pool pool;
    tc_pool_init(&pool, sizeof(TestItem), 2);
    TEST_ASSERT(pool.capacity == 2, "initial capacity 2");

    // Allocate beyond initial capacity
    tc_handle handles[10];
    for (int i = 0; i < 10; i++) {
        handles[i] = tc_pool_alloc(&pool);
        TEST_ASSERT(!tc_handle_is_invalid(handles[i]), "alloc succeeds");

        TestItem* item = (TestItem*)tc_pool_get(&pool, handles[i]);
        item->value = i * 100;
    }

    TEST_ASSERT(pool.capacity >= 10, "capacity grew");
    TEST_ASSERT(tc_pool_count(&pool) == 10, "count is 10");

    // Verify all handles still valid and data intact
    for (int i = 0; i < 10; i++) {
        TEST_ASSERT(tc_pool_is_valid(&pool, handles[i]), "handle still valid");
        TestItem* item = (TestItem*)tc_pool_get(&pool, handles[i]);
        TEST_ASSERT(item->value == i * 100, "data intact after growth");
    }

    tc_pool_free(&pool);
    printf("  Pool Growth: PASS\n");
    return 0;
}

static bool iter_sum_callback(uint32_t index, void* item, void* user_data) {
    (void)index;
    TestItem* ti = (TestItem*)item;
    int* sum = (int*)user_data;
    *sum += ti->value;
    return true;
}

static int test_pool_iteration(void) {
    printf("Testing Pool Iteration...\n");

    tc_pool pool;
    tc_pool_init(&pool, sizeof(TestItem), 8);

    // Add items with values 1, 2, 3, 4, 5
    for (int i = 1; i <= 5; i++) {
        tc_handle h = tc_pool_alloc(&pool);
        TestItem* item = (TestItem*)tc_pool_get(&pool, h);
        item->value = i;
    }

    // Sum via iteration
    int sum = 0;
    tc_pool_foreach(&pool, iter_sum_callback, &sum);
    TEST_ASSERT(sum == 15, "iteration sum is 15");

    tc_pool_free(&pool);
    printf("  Pool Iteration: PASS\n");
    return 0;
}

static int test_pool_clear(void) {
    printf("Testing Pool Clear...\n");

    tc_pool pool;
    tc_pool_init(&pool, sizeof(TestItem), 4);

    tc_handle h1 = tc_pool_alloc(&pool);
    tc_handle h2 = tc_pool_alloc(&pool);
    TEST_ASSERT(tc_pool_count(&pool) == 2, "count is 2");

    tc_pool_clear(&pool);
    TEST_ASSERT(tc_pool_count(&pool) == 0, "count is 0 after clear");
    TEST_ASSERT(!tc_pool_is_valid(&pool, h1), "h1 invalid after clear");
    TEST_ASSERT(!tc_pool_is_valid(&pool, h2), "h2 invalid after clear");

    // Can allocate again
    tc_handle h3 = tc_pool_alloc(&pool);
    TEST_ASSERT(!tc_handle_is_invalid(h3), "can alloc after clear");
    TEST_ASSERT(tc_pool_count(&pool) == 1, "count is 1");

    tc_pool_free(&pool);
    printf("  Pool Clear: PASS\n");
    return 0;
}

// ============================================================================
// tc_str_map tests
// ============================================================================

static int test_str_map_basic(void) {
    printf("Testing String Map Basic...\n");

    tc_str_map* map = tc_str_map_new(4);
    TEST_ASSERT(map != NULL, "map create");
    TEST_ASSERT(tc_str_map_count(map) == 0, "initial count is 0");

    // Set values
    tc_str_map_set(map, "one", 1);
    tc_str_map_set(map, "two", 2);
    tc_str_map_set(map, "three", 3);
    TEST_ASSERT(tc_str_map_count(map) == 3, "count is 3");

    // Get values
    uint64_t value;
    TEST_ASSERT(tc_str_map_get(map, "one", &value) && value == 1, "get one");
    TEST_ASSERT(tc_str_map_get(map, "two", &value) && value == 2, "get two");
    TEST_ASSERT(tc_str_map_get(map, "three", &value) && value == 3, "get three");

    // Key not found
    TEST_ASSERT(!tc_str_map_get(map, "four", &value), "four not found");

    // Update existing key
    tc_str_map_set(map, "one", 100);
    TEST_ASSERT(tc_str_map_get(map, "one", &value) && value == 100, "updated value");
    TEST_ASSERT(tc_str_map_count(map) == 3, "count unchanged after update");

    tc_str_map_free(map);
    printf("  String Map Basic: PASS\n");
    return 0;
}

static int test_str_map_remove(void) {
    printf("Testing String Map Remove...\n");

    tc_str_map* map = tc_str_map_new(4);

    tc_str_map_set(map, "a", 1);
    tc_str_map_set(map, "b", 2);
    tc_str_map_set(map, "c", 3);

    TEST_ASSERT(tc_str_map_remove(map, "b"), "remove b");
    TEST_ASSERT(tc_str_map_count(map) == 2, "count is 2");

    uint64_t value;
    TEST_ASSERT(!tc_str_map_get(map, "b", &value), "b not found");
    TEST_ASSERT(tc_str_map_get(map, "a", &value), "a still exists");
    TEST_ASSERT(tc_str_map_get(map, "c", &value), "c still exists");

    // Remove non-existent
    TEST_ASSERT(!tc_str_map_remove(map, "nonexistent"), "remove nonexistent fails");

    tc_str_map_free(map);
    printf("  String Map Remove: PASS\n");
    return 0;
}

static int test_str_map_growth(void) {
    printf("Testing String Map Growth...\n");

    tc_str_map* map = tc_str_map_new(2);

    char key[32];
    for (int i = 0; i < 100; i++) {
        snprintf(key, sizeof(key), "key_%d", i);
        tc_str_map_set(map, key, (uint64_t)i);
    }

    TEST_ASSERT(tc_str_map_count(map) == 100, "count is 100");

    // Verify all values
    uint64_t value;
    for (int i = 0; i < 100; i++) {
        snprintf(key, sizeof(key), "key_%d", i);
        TEST_ASSERT(tc_str_map_get(map, key, &value), "key exists");
        TEST_ASSERT(value == (uint64_t)i, "value correct");
    }

    tc_str_map_free(map);
    printf("  String Map Growth: PASS\n");
    return 0;
}

static int test_str_map_clear(void) {
    printf("Testing String Map Clear...\n");

    tc_str_map* map = tc_str_map_new(4);

    tc_str_map_set(map, "x", 1);
    tc_str_map_set(map, "y", 2);
    TEST_ASSERT(tc_str_map_count(map) == 2, "count is 2");

    tc_str_map_clear(map);
    TEST_ASSERT(tc_str_map_count(map) == 0, "count is 0 after clear");

    uint64_t value;
    TEST_ASSERT(!tc_str_map_get(map, "x", &value), "x not found after clear");

    // Can add again
    tc_str_map_set(map, "z", 3);
    TEST_ASSERT(tc_str_map_count(map) == 1, "count is 1 after re-add");

    tc_str_map_free(map);
    printf("  String Map Clear: PASS\n");
    return 0;
}

// ============================================================================
// tc_u32_map tests
// ============================================================================

static int test_u32_map_basic(void) {
    printf("Testing U32 Map Basic...\n");

    tc_u32_map* map = tc_u32_map_new(4);
    TEST_ASSERT(map != NULL, "map create");
    TEST_ASSERT(tc_u32_map_count(map) == 0, "initial count is 0");

    // Set values
    tc_u32_map_set(map, 100, 1000);
    tc_u32_map_set(map, 200, 2000);
    tc_u32_map_set(map, 300, 3000);

    // Get values
    uint64_t value;
    TEST_ASSERT(tc_u32_map_get(map, 100, &value) && value == 1000, "get 100");
    TEST_ASSERT(tc_u32_map_get(map, 200, &value) && value == 2000, "get 200");
    TEST_ASSERT(tc_u32_map_get(map, 300, &value) && value == 3000, "get 300");

    // Not found
    TEST_ASSERT(!tc_u32_map_get(map, 999, &value), "999 not found");

    // Remove
    TEST_ASSERT(tc_u32_map_remove(map, 200), "remove 200");
    TEST_ASSERT(!tc_u32_map_get(map, 200, &value), "200 gone");
    TEST_ASSERT(tc_u32_map_count(map) == 2, "count is 2");

    tc_u32_map_free(map);
    printf("  U32 Map Basic: PASS\n");
    return 0;
}

static int test_u32_map_edge_cases(void) {
    printf("Testing U32 Map Edge Cases...\n");

    tc_u32_map* map = tc_u32_map_new(4);

    // Test with 0 key
    tc_u32_map_set(map, 0, 999);
    uint64_t value;
    TEST_ASSERT(tc_u32_map_get(map, 0, &value) && value == 999, "key 0 works");

    // Note: 0xFFFFFFFF (EMPTY) and 0xFFFFFFFE (DELETED) are reserved sentinels
    // Test with valid near-max key
    tc_u32_map_set(map, 0xFFFFFFFD, 123);
    TEST_ASSERT(tc_u32_map_get(map, 0xFFFFFFFD, &value) && value == 123, "near-max key works");

    // Test with 1
    tc_u32_map_set(map, 1, 456);
    TEST_ASSERT(tc_u32_map_get(map, 1, &value) && value == 456, "key 1 works");

    tc_u32_map_free(map);
    printf("  U32 Map Edge Cases: PASS\n");
    return 0;
}

// ============================================================================
// tc_dlist tests
// ============================================================================

typedef struct {
    int value;
    tc_dlist_node node;
} ListItem;

static int test_dlist_basic(void) {
    printf("Testing DList Basic...\n");

    tc_dlist_head list;
    tc_dlist_init_head(&list);
    TEST_ASSERT(tc_dlist_empty(&list), "list is empty");
    TEST_ASSERT(tc_dlist_size(&list) == 0, "size is 0");

    // Add items
    ListItem items[3];
    for (int i = 0; i < 3; i++) {
        items[i].value = i + 1;
        tc_dlist_init_node(&items[i].node);
        tc_dlist_add_tail(&items[i].node, &list);
    }

    TEST_ASSERT(!tc_dlist_empty(&list), "list not empty");
    TEST_ASSERT(tc_dlist_size(&list) == 3, "size is 3");

    // Check order (1, 2, 3)
    ListItem* first = tc_dlist_first_entry(&list, ListItem, node);
    TEST_ASSERT(first->value == 1, "first is 1");

    ListItem* last = tc_dlist_last_entry(&list, ListItem, node);
    TEST_ASSERT(last->value == 3, "last is 3");

    printf("  DList Basic: PASS\n");
    return 0;
}

static int test_dlist_add_front(void) {
    printf("Testing DList Add Front...\n");

    tc_dlist_head list;
    tc_dlist_init_head(&list);

    ListItem items[3];
    for (int i = 0; i < 3; i++) {
        items[i].value = i + 1;
        tc_dlist_init_node(&items[i].node);
        tc_dlist_add(&items[i].node, &list);  // add to front
    }

    // Order should be 3, 2, 1 (reverse)
    ListItem* first = tc_dlist_first_entry(&list, ListItem, node);
    TEST_ASSERT(first->value == 3, "first is 3");

    ListItem* last = tc_dlist_last_entry(&list, ListItem, node);
    TEST_ASSERT(last->value == 1, "last is 1");

    printf("  DList Add Front: PASS\n");
    return 0;
}

static int test_dlist_remove(void) {
    printf("Testing DList Remove...\n");

    tc_dlist_head list;
    tc_dlist_init_head(&list);

    ListItem items[3];
    for (int i = 0; i < 3; i++) {
        items[i].value = i + 1;
        tc_dlist_init_node(&items[i].node);
        tc_dlist_add_tail(&items[i].node, &list);
    }

    // Remove middle item (value=2)
    tc_dlist_del(&items[1].node);
    TEST_ASSERT(tc_dlist_size(&list) == 2, "size is 2");
    TEST_ASSERT(!tc_dlist_is_linked(&items[1].node), "removed node not linked");

    // Check remaining items
    ListItem* first = tc_dlist_first_entry(&list, ListItem, node);
    ListItem* last = tc_dlist_last_entry(&list, ListItem, node);
    TEST_ASSERT(first->value == 1, "first is 1");
    TEST_ASSERT(last->value == 3, "last is 3");

    // Double remove is safe
    tc_dlist_del(&items[1].node);  // should be no-op
    TEST_ASSERT(tc_dlist_size(&list) == 2, "size still 2");

    printf("  DList Remove: PASS\n");
    return 0;
}

static int test_dlist_iteration(void) {
    printf("Testing DList Iteration...\n");

    tc_dlist_head list;
    tc_dlist_init_head(&list);

    ListItem items[5];
    for (int i = 0; i < 5; i++) {
        items[i].value = (i + 1) * 10;  // 10, 20, 30, 40, 50
        tc_dlist_init_node(&items[i].node);
        tc_dlist_add_tail(&items[i].node, &list);
    }

    // Forward iteration
    int sum = 0;
    ListItem* pos;
    tc_dlist_for_each_entry(pos, &list, ListItem, node) {
        sum += pos->value;
    }
    TEST_ASSERT(sum == 150, "forward sum is 150");

    // Reverse iteration
    sum = 0;
    int expected_values[] = {50, 40, 30, 20, 10};
    int idx = 0;
    tc_dlist_for_each_entry_reverse(pos, &list, ListItem, node) {
        TEST_ASSERT(pos->value == expected_values[idx], "reverse order correct");
        sum += pos->value;
        idx++;
    }
    TEST_ASSERT(sum == 150, "reverse sum is 150");

    printf("  DList Iteration: PASS\n");
    return 0;
}

static int test_dlist_safe_iteration(void) {
    printf("Testing DList Safe Iteration...\n");

    tc_dlist_head list;
    tc_dlist_init_head(&list);

    ListItem items[5];
    for (int i = 0; i < 5; i++) {
        items[i].value = i + 1;
        tc_dlist_init_node(&items[i].node);
        tc_dlist_add_tail(&items[i].node, &list);
    }

    // Remove even items during iteration
    ListItem* pos;
    ListItem* tmp;
    tc_dlist_for_each_entry_safe(pos, tmp, &list, ListItem, node) {
        if (pos->value % 2 == 0) {
            tc_dlist_del(&pos->node);
        }
    }

    TEST_ASSERT(tc_dlist_size(&list) == 3, "size is 3 after removal");

    // Check remaining: 1, 3, 5
    int expected[] = {1, 3, 5};
    int idx = 0;
    tc_dlist_for_each_entry(pos, &list, ListItem, node) {
        TEST_ASSERT(pos->value == expected[idx], "remaining values correct");
        idx++;
    }

    printf("  DList Safe Iteration: PASS\n");
    return 0;
}

static int test_dlist_move(void) {
    printf("Testing DList Move...\n");

    tc_dlist_head list1, list2;
    tc_dlist_init_head(&list1);
    tc_dlist_init_head(&list2);

    ListItem item;
    item.value = 42;
    tc_dlist_init_node(&item.node);

    tc_dlist_add_tail(&item.node, &list1);
    TEST_ASSERT(tc_dlist_size(&list1) == 1, "list1 has 1");
    TEST_ASSERT(tc_dlist_size(&list2) == 0, "list2 has 0");
    TEST_ASSERT(tc_dlist_contains(&list1, &item.node), "item in list1");

    // Move to list2
    tc_dlist_move_tail(&item.node, &list2);
    TEST_ASSERT(tc_dlist_size(&list1) == 0, "list1 has 0");
    TEST_ASSERT(tc_dlist_size(&list2) == 1, "list2 has 1");
    TEST_ASSERT(tc_dlist_contains(&list2, &item.node), "item in list2");
    TEST_ASSERT(!tc_dlist_contains(&list1, &item.node), "item not in list1");

    printf("  DList Move: PASS\n");
    return 0;
}

static int test_dlist_contains(void) {
    printf("Testing DList Contains...\n");

    tc_dlist_head list;
    tc_dlist_init_head(&list);

    ListItem in_list, not_in_list;
    in_list.value = 1;
    not_in_list.value = 2;
    tc_dlist_init_node(&in_list.node);
    tc_dlist_init_node(&not_in_list.node);

    tc_dlist_add_tail(&in_list.node, &list);

    TEST_ASSERT(tc_dlist_contains(&list, &in_list.node), "in_list found");
    TEST_ASSERT(!tc_dlist_contains(&list, &not_in_list.node), "not_in_list not found");

    printf("  DList Contains: PASS\n");
    return 0;
}

// ============================================================================
// Main
// ============================================================================

int main(void) {
    printf("=== Data Structures Tests ===\n\n");

    int result = 0;

    // Pool tests
    result |= test_pool_basic();
    result |= test_pool_generation();
    result |= test_pool_growth();
    result |= test_pool_iteration();
    result |= test_pool_clear();

    // String map tests
    result |= test_str_map_basic();
    result |= test_str_map_remove();
    result |= test_str_map_growth();
    result |= test_str_map_clear();

    // U32 map tests
    result |= test_u32_map_basic();
    result |= test_u32_map_edge_cases();

    // DList tests
    result |= test_dlist_basic();
    result |= test_dlist_add_front();
    result |= test_dlist_remove();
    result |= test_dlist_iteration();
    result |= test_dlist_safe_iteration();
    result |= test_dlist_move();
    result |= test_dlist_contains();

    printf("\n");
    if (result == 0) {
        printf("=== ALL TESTS PASSED ===\n");
    } else {
        printf("=== SOME TESTS FAILED ===\n");
    }

    return result;
}
