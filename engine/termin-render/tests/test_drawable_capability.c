#include <string.h>

#include "guard_c.h"

#include "core/tc_component.h"
#include "core/tc_drawable_capability.h"
#include "core/tc_drawable_protocol.h"
#include "core/tc_entity_pool.h"
#include "core/tc_scene.h"
#include "core/tc_scene_drawable.h"

static int g_render_item_emit_count = 0;
static int g_render_item_collect_count = 0;

typedef struct {
    tc_material_handle materials[2];
    size_t material_count;
    int calls;
    const tc_render_item_collect_context* last_context;
} material_producer;

typedef struct {
    tc_material_handle materials[2];
    size_t count;
    bool accept;
} material_recorder;

static tc_phase_mask test_drawable_phase_mask(tc_component* self) {
    (void)self;
    return TC_PHASE_OPAQUE;
}

static bool test_drawable_collect_render_items(tc_component* self,
                                               const tc_render_item_collect_context* context,
                                               tc_render_item_sink* sink) {
    (void)self;
    ++g_render_item_collect_count;
    if (!context || !sink || !sink->emit) {
        return false;
    }

    tc_render_item item;
    memset(&item, 0, sizeof(item));
    item.kind = TC_RENDER_ITEM_KIND_MESH;
    item.geometry_id = 7;
    return sink->emit(&item, sink->user_data);
}

static bool test_drawable_collect_materials(tc_component* self,
                                           const tc_render_item_collect_context* context,
                                           tc_material_sink* sink) {
    material_producer* producer = (material_producer*)tc_component_get_drawable_userdata(self);
    ++producer->calls;
    producer->last_context = context;
    for (size_t i = 0; i < producer->material_count; ++i) {
        if (!sink->emit(producer->materials[i], sink->user_data))
            return false;
    }
    return true;
}

static const tc_drawable_vtable g_test_drawable_vtable = {
    .phase_mask = test_drawable_phase_mask,
    .collect_render_items = test_drawable_collect_render_items,
    .collect_materials = test_drawable_collect_materials,
};

static bool record_material_emit(tc_material_handle material, void* user_data) {
    material_recorder* recorder = (material_recorder*)user_data;
    if (recorder->count < 2)
        recorder->materials[recorder->count] = material;
    ++recorder->count;
    return recorder->accept;
}

static bool count_render_item_emit(const tc_render_item* item, void* user_data) {
    (void)user_data;
    if (item && item->kind == TC_RENDER_ITEM_KIND_MESH && item->geometry_id == 7) {
        g_render_item_emit_count++;
    }
    return true;
}

static bool count_components(tc_component* c, void* user_data) {
    (void)c;
    int* count = (int*)user_data;
    (*count)++;
    return true;
}

GUARD_C_TEST(test_live_reindex_for_drawable_capability) {
    tc_component_cap_id drawable_cap = tc_drawable_capability_id();
    GUARD_C_REQUIRE(drawable_cap != TC_COMPONENT_CAPABILITY_INVALID_ID);

    tc_scene_handle scene = tc_scene_new_named("drawable-reindex-scene");
    GUARD_C_REQUIRE(tc_scene_alive(scene));

    tc_entity_pool* pool = tc_scene_entity_pool(scene);
    tc_entity_id entity = tc_entity_pool_alloc(pool, "entity");
    GUARD_C_REQUIRE(tc_entity_id_valid(entity));

    tc_component component;
    tc_component_init(&component, NULL);

    tc_entity_pool_add_component(pool, entity, &component);
    GUARD_C_CHECK_EQ_INT(0, tc_scene_capability_count(scene, drawable_cap));

    GUARD_C_REQUIRE(tc_drawable_capability_attach(&component, &g_test_drawable_vtable, (void*)0x1234));
    GUARD_C_CHECK_EQ_INT(1, tc_scene_capability_count(scene, drawable_cap));
    GUARD_C_CHECK(tc_component_is_drawable(&component));
    GUARD_C_CHECK_PTR_EQ((void*)0x1234, tc_component_get_drawable_userdata(&component));
    GUARD_C_CHECK_EQ_INT(TC_PHASE_OPAQUE, tc_component_phase_mask(&component));

    g_render_item_emit_count = 0;
    tc_render_item_collect_context collect_context;
    memset(&collect_context, 0, sizeof(collect_context));
    collect_context.phase = TC_PHASE_OPAQUE;
    tc_render_item_sink sink;
    sink.emit = count_render_item_emit;
    sink.user_data = NULL;
    GUARD_C_CHECK(tc_component_collect_render_items(&component, &collect_context, &sink));
    GUARD_C_CHECK_EQ_INT(1, g_render_item_emit_count);

    int count = 0;
    tc_scene_foreach_drawable(scene, count_components, &count, TC_SCENE_FILTER_NONE, 0);
    GUARD_C_CHECK_EQ_INT(1, count);

    tc_component_detach_capability(&component, drawable_cap);
    GUARD_C_CHECK_EQ_INT(0, tc_scene_capability_count(scene, drawable_cap));

    tc_entity_pool_remove_component(pool, entity, &component);
    tc_scene_free(scene);
    return 0;
}

GUARD_C_TEST(test_material_enumeration_dispatch_and_sink_failure) {
    tc_component component;
    tc_component_init(&component, NULL);
    material_producer producer;
    memset(&producer, 0, sizeof(producer));
    producer.materials[0] = (tc_material_handle){7, 2};
    producer.materials[1] = (tc_material_handle){11, 3};
    producer.material_count = 2;
    GUARD_C_REQUIRE(tc_drawable_capability_attach(&component, &g_test_drawable_vtable, &producer));

    tc_render_item_collect_context context;
    memset(&context, 0, sizeof(context));
    context.phase = TC_PHASE_NONE;
    context.layer_mask = 4;
    context.render_category_mask = 8;
    context.camera = &producer;
    context.scene = &component;
    material_recorder recorder;
    memset(&recorder, 0, sizeof(recorder));
    recorder.accept = true;
    tc_material_sink sink = {record_material_emit, &recorder};
    const int heavy_calls_before = g_render_item_collect_count;

    GUARD_C_CHECK(tc_component_collect_materials(&component, &context, &sink));
    GUARD_C_CHECK_EQ_INT(1, producer.calls);
    GUARD_C_CHECK_PTR_EQ(&context, producer.last_context);
    GUARD_C_CHECK_EQ_SIZE(2, recorder.count);
    GUARD_C_CHECK(tc_material_handle_eq(producer.materials[0], recorder.materials[0]));
    GUARD_C_CHECK(tc_material_handle_eq(producer.materials[1], recorder.materials[1]));
    GUARD_C_CHECK_EQ_INT(heavy_calls_before, g_render_item_collect_count);

    recorder.count = 0;
    recorder.accept = false;
    GUARD_C_CHECK(!tc_component_collect_materials(&component, &context, &sink));
    GUARD_C_CHECK_EQ_INT(2, producer.calls);
    GUARD_C_CHECK_EQ_SIZE(1, recorder.count);
    GUARD_C_CHECK_EQ_INT(heavy_calls_before, g_render_item_collect_count);

    // An explicit empty selection succeeds without touching even a sink
    // which would reject an emitted material.
    recorder.count = 0;
    producer.material_count = 0;
    GUARD_C_CHECK(tc_component_collect_materials(&component, &context, &sink));
    GUARD_C_CHECK_EQ_SIZE(0, recorder.count);
    GUARD_C_CHECK_EQ_INT(3, producer.calls);
    GUARD_C_CHECK_EQ_INT(heavy_calls_before, g_render_item_collect_count);
    tc_component_detach_capability(&component, tc_drawable_capability_id());
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_live_reindex_for_drawable_capability);
    GUARD_C_RUN(test_material_enumeration_dispatch_and_sink_failure);
    return GUARD_C_END();
}
