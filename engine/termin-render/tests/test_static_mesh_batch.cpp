#include "../src/static_mesh_batch_index.hpp"

#include <cassert>
#include <cmath>
#include <cstring>
#include <termin/render/render_item_culling.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/static_mesh_batch.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
extern "C" {
#include <core/tc_component.h>
#include <core/tc_drawable_capability.h>
#include <core/tc_entity_pool.h>
#include <core/tc_scene.h>
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
}
namespace {
    void check_collision_index() {
        termin::detail::StaticBatchKeyIndex index;
        constexpr uint64_t collision_hash = 7;
        index.reset(256);
        for (size_t i = 0; i < 256; ++i)
            index.insert(collision_hash, i);
        for (size_t i = 0; i < 256; ++i)
            assert(index.find(collision_hash, [&](size_t candidate) { return candidate == i; }) == i);
        size_t comparisons = 0;
        assert(index.find(collision_hash, [&](size_t) { ++comparisons; return false; }) == index.missing);
        assert(comparisons == 256);
        // Same bucket but different hashes never bypass hash/equality verification.
        index.insert(collision_hash + 256, 256);
        assert(index.find(collision_hash, [](size_t candidate) { return candidate == 256; }) == index.missing);
        assert(index.find(collision_hash + 256, [](size_t candidate) { return candidate == 256; }) == 256);
        index.reset(2);
        assert(index.find(collision_hash, [](size_t) { return true; }) == index.missing);
        index.insert(collision_hash, 42);
        assert(index.find(collision_hash, [](size_t candidate) { return candidate == 42; }) == 42);
    }
    tc_phase_mask phases(tc_component*) {
        return TC_PHASE_OPAQUE | TC_PHASE_DEPTH | TC_PHASE_ID;
    }
    bool collect_materials(tc_component* component, const tc_render_item_collect_context*, tc_material_sink* sink) {
        auto* material = static_cast<tc_material_handle*>(tc_component_get_drawable_userdata(component));
        return sink->emit(*material, sink->user_data);
    }
    const tc_drawable_vtable drawable{&phases, nullptr, &collect_materials};
    float f(const uint8_t* bytes, size_t offset) {
        float result;
        std::memcpy(&result, bytes + offset, 4);
        return result;
    }
    tc_render_item
    make_item(tc_component& component, tc_mesh_handle mesh, tc_material_handle material, uint64_t id, float x) {
        tc_render_item item{};
        item.kind = TC_RENDER_ITEM_KIND_MESH;
        item.flags = TC_RENDER_ITEM_FLAG_STATIC_BATCH_ELIGIBLE | TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX |
                     TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE | TC_RENDER_ITEM_FLAG_CONSERVATIVE_MESH_BOUNDS;
        item.source.domain_id = TC_RENDER_ITEM_SOURCE_DOMAIN_SCENE;
        item.source.object_id = id;
        item.source.adapter_data = reinterpret_cast<uintptr_t>(&component);
        item.payload.mesh.mesh_handle = mesh;
        item.material = material;
        item.material_phase_index = 0;
        item.material_phase = &tc_material_get(material)->phases[0];
        item.model_matrix[0] = item.model_matrix[5] = item.model_matrix[10] = item.model_matrix[15] = 1;
        item.model_matrix[12] = x;
        return item;
    }
    struct SceneProducerData {
        tc_mesh_handle mesh;
        tc_material_handle material;
        float x;
        uint64_t category = 1;
        size_t calls = 0;
    };
    bool scene_collect_items(tc_component* component,
                             const tc_render_item_collect_context* context,
                             tc_render_item_sink* sink) {
        auto* data = static_cast<SceneProducerData*>(tc_component_get_drawable_userdata(component));
        ++data->calls;
        if ((context->render_category_mask & data->category) == 0)
            return true;
        auto item = make_item(*component, data->mesh, data->material, 0, data->x);
        item.source = {}; // The scene adapter supplies actual entity/generation identity.
        return sink->emit(&item, sink->user_data);
    }
    bool scene_collect_materials(tc_component* component,
                                 const tc_render_item_collect_context* context,
                                 tc_material_sink* sink) {
        auto* data = static_cast<SceneProducerData*>(tc_component_get_drawable_userdata(component));
        return (context->render_category_mask & data->category) == 0 || sink->emit(data->material, sink->user_data);
    }
    const tc_drawable_vtable scene_drawable{&phases, &scene_collect_items, &scene_collect_materials};

    void check_scene_snapshot_membership(tc_mesh_handle mesh, tc_material_handle material) {
        auto scene = tc_scene_new_named("static-batch-snapshot-membership");
        auto* pool = tc_scene_entity_pool(scene);
        auto first_id = tc_entity_pool_alloc(pool, "first");
        auto second_id = tc_entity_pool_alloc(pool, "second");
        tc_entity_pool_set_layer(pool, first_id, 1);
        tc_entity_pool_set_layer(pool, second_id, 1);
        tc_component first{}, second{}, third{};
        tc_component_init(&first, nullptr);
        tc_component_init(&second, nullptr);
        tc_component_init(&third, nullptr);
        SceneProducerData first_data{mesh, material, 1};
        SceneProducerData second_data{mesh, material, 3};
        SceneProducerData third_data{mesh, material, 5, 2};
        assert(tc_drawable_capability_attach(&first, &scene_drawable, &first_data));
        assert(tc_drawable_capability_attach(&second, &scene_drawable, &second_data));
        assert(tc_drawable_capability_attach(&third, &scene_drawable, &third_data));
        tc_entity_pool_add_component(pool, first_id, &first);
        tc_entity_pool_add_component(pool, second_id, &second);
        termin::StaticMeshBatchCache cache;
        constexpr int filters = TC_SCENE_FILTER_ENABLED | TC_SCENE_FILTER_VISIBLE | TC_SCENE_FILTER_ENTITY_ENABLED;
        termin::TcSceneRenderItemSource source(scene, nullptr, filters, &cache);
        termin::RenderItemSourceRequest request{};
        auto publish = [&]() {
            termin::RenderItemSnapshot snapshot;
            assert(source.publish(snapshot, request));
            assert(snapshot.valid());
            assert(snapshot.counters().source_traversals == 1);
            return snapshot;
        };
        auto check_drop = [&]() {
            const size_t second_calls = second_data.calls;
            auto snapshot = publish();
            assert(snapshot.counters().producers == 1 && snapshot.item_count() == 1);
            assert((snapshot.item(0)->flags & TC_RENDER_ITEM_FLAG_BATCHED_GEOMETRY) == 0);
            assert(cache.stats().input_geometry == 1 && cache.stats().output_batches == 0);
            assert(cache.stats().rebuilt_batches == 0 && cache.stats().reused_batches == 0);
            assert(second_data.calls == second_calls); // Excluded before producer invocation.
        };
        auto check_restore = [&]() {
            auto snapshot = publish();
            assert(snapshot.counters().producers == 2 && snapshot.item_count() == 1);
            assert(cache.stats().merged_geometry == 2 && cache.stats().rebuilt_batches == 1);
            assert(cache.stats().cached_groups == 0 && cache.stats().signature_copies == 2);
            auto warm = publish();
            assert(cache.stats().rebuilt_batches == 0 && cache.stats().reused_batches == 1);
            assert(cache.stats().signature_copies == 0);
        };
        auto original = publish();
        assert(original.counters().producers == 2 && original.item_count() == 1);
        assert(original.item(0)->source.domain_id == TC_RENDER_ITEM_SOURCE_DOMAIN_SCENE);
        assert(original.item(0)->source.object_id != 0 && original.item(0)->source.namespace_id != 0);
        assert(cache.stats().rebuilt_batches == 1 && cache.stats().merged_geometry == 2);
        const auto original_mesh = original.item(0)->payload.mesh.mesh_handle;
        assert(tc_mesh_get(original_mesh)->index_count == 6);
        auto warm = publish();
        assert(cache.stats().reused_batches == 1 && cache.stats().rebuilt_batches == 0);
        assert(tc_mesh_handle_eq(warm.item(0)->payload.mesh.mesh_handle, original_mesh));

        tc_entity_pool_set_visible(pool, second_id, false);
        check_drop();
        tc_entity_pool_set_visible(pool, second_id, true);
        check_restore();
        tc_entity_pool_set_enabled(pool, second_id, false);
        check_drop();
        tc_entity_pool_set_enabled(pool, second_id, true);
        check_restore();
        tc_component_set_enabled(&second, false);
        check_drop();
        tc_component_set_enabled(&second, true);
        check_restore();

        auto third_id = tc_entity_pool_alloc(pool, "third");
        tc_entity_pool_set_layer(pool, third_id, 1);
        tc_entity_pool_add_component(pool, third_id, &third);
        auto added = publish();
        assert(added.counters().producers == 3 && added.item_count() == 1);
        assert(cache.stats().merged_geometry == 3 && cache.stats().rebuilt_batches == 1);
        const auto added_mesh = added.item(0)->payload.mesh.mesh_handle;
        assert(tc_mesh_get(added_mesh)->index_count == 9);
        publish();
        assert(cache.stats().reused_batches == 1 && cache.stats().signature_copies == 0);
        tc_entity_pool_remove_component(pool, third_id, &third);
        auto removed = publish();
        assert(removed.counters().producers == 2 && cache.stats().merged_geometry == 2);
        assert(cache.stats().rebuilt_batches == 1);
        tc_entity_pool_add_component(pool, third_id, &third);
        publish();
        assert(cache.stats().merged_geometry == 3 && cache.stats().rebuilt_batches == 1);

        // Real source masks feed distinct membership and independent cache variants.
        request.render_category_mask = 1;
        auto category_view = publish();
        assert(category_view.counters().producers == 3 && cache.stats().input_geometry == 2);
        assert(cache.stats().merged_geometry == 2 && cache.stats().rebuilt_batches == 1);
        request.render_category_mask = UINT64_MAX;
        publish();
        assert(cache.stats().merged_geometry == 3 && cache.stats().reused_batches == 1);
        tc_entity_pool_set_layer(pool, third_id, 2);
        request.layer_mask = UINT64_C(1) << 1; // Entity layer is an index; request uses its bit mask.
        auto layer_view = publish();
        assert(layer_view.counters().producers == 2 && cache.stats().merged_geometry == 2);
        assert(cache.stats().rebuilt_batches == 1);
        request.layer_mask = UINT64_MAX;
        auto split_layers = publish();
        assert(split_layers.counters().producers == 3 && split_layers.item_count() == 2);
        assert(cache.stats().merged_geometry == 2 && cache.stats().rebuilt_batches == 1);
        tc_entity_pool_set_layer(pool, third_id, 1);
        publish();
        assert(cache.stats().merged_geometry == 3 && cache.stats().rebuilt_batches == 1);

        tc_entity_pool_free(pool, third_id);
        auto deleted = publish();
        assert(deleted.counters().producers == 2 && cache.stats().merged_geometry == 2);
        assert(cache.stats().rebuilt_batches == 1);
        auto replacement_id = tc_entity_pool_alloc(pool, "replacement");
        tc_entity_pool_set_layer(pool, replacement_id, 1);
        tc_entity_pool_add_component(pool, replacement_id, &third);
        publish();
        assert(cache.stats().merged_geometry == 3 && cache.stats().rebuilt_batches == 1);
        cache.clear_scene(scene);
        // Previously published snapshots retain both old memberships' meshes.
        assert(tc_mesh_is_valid(original_mesh) && tc_mesh_get(original_mesh)->index_count == 6);
        assert(tc_mesh_is_valid(added_mesh) && tc_mesh_get(added_mesh)->index_count == 9);
        assert(original.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_VALID);
        assert(added.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_VALID);

        tc_component_detach_capability(&first, tc_drawable_capability_id());
        tc_component_detach_capability(&second, tc_drawable_capability_id());
        tc_component_detach_capability(&third, tc_drawable_capability_id());
        tc_entity_pool_remove_component(pool, first_id, &first);
        tc_entity_pool_remove_component(pool, second_id, &second);
        tc_entity_pool_remove_component(pool, replacement_id, &third);
        tc_scene_free(scene);
        assert(tc_mesh_is_valid(original_mesh) && tc_mesh_is_valid(added_mesh));
    }
} // namespace
int main() {
    check_collision_index();
    tc_shader_init();
    tc_mesh_init();
    tc_material_init();
    auto scene = tc_scene_new_named("static-batch-test");
    auto* pool = tc_scene_entity_pool(scene);
    auto first_id = tc_entity_pool_alloc(pool, "first");
    auto second_id = tc_entity_pool_alloc(pool, "second");
    tc_entity_pool_set_pickable(pool, first_id, true);
    tc_entity_pool_set_pickable(pool, second_id, true);
    tc_component first{}, second{};
    tc_component_init(&first, nullptr);
    tc_component_init(&second, nullptr);
    tc_entity_pool_add_component(pool, first_id, &first);
    tc_entity_pool_add_component(pool, second_id, &second);
    auto material = tc_material_create("static-batch-material", "static-batch-material");
    auto* mat = tc_material_get(material);
    tc_material_add_phase(mat, tc_shader_handle_invalid(), "opaque", 0);
    mat->phases[0].state = tc_render_state_opaque();
    assert(tc_drawable_capability_attach(&first, &drawable, &material));
    assert(tc_drawable_capability_attach(&second, &drawable, &material));
    auto layout = tc_vertex_layout_pos_normal_uv_tangent();
    const float n = std::sqrt(0.5f);
    const float vertices[] = {0, 0, 0, n,  n, 0, 0, 0, n, -n, 0, 1, 1, 0, 0, n,  n, 0,
                              1, 0, n, -n, 0, 1, 0, 1, 0, n,  n, 0, 0, 1, n, -n, 0, 1};
    const uint32_t indices[] = {0, 1, 2};
    {
        termin::TcMeshCreateInfo info;
        info.name = "static-batch-triangle";
        info.data = {vertices, 3, indices, 3, &layout};
        auto source = termin::TcMesh::from_interleaved(info);
        assert(source.is_valid());
        termin::StaticMeshBatchCache cache;
        auto a = make_item(first, source.handle, material, 1, 1);
        auto b = make_item(second, source.handle, material, 2, 3);
        a.model_matrix[0] = -2;
        auto collect = [&]() {
            termin::RenderItemCollection result;
            result.items = {a, b};
            assert(cache.apply(result, scene, UINT64_MAX, UINT64_MAX));
            for (auto& item : result.items) termin::update_render_item_world_bounds(item);
            return result;
        };
        auto first_snapshot = collect();
        assert(first_snapshot.items.size() == 1);
        assert(cache.stats().rebuilt_batches == 1);
        assert(cache.stats().merged_geometry == 2);
        const auto& first_bounds = first_snapshot.items[0].world_bounds;
        assert(first_snapshot.items[0].bounds_state == TC_RENDER_ITEM_BOUNDS_VALID);
        assert(first_bounds.min_point.x == -1 && first_bounds.max_point.x == 4);
        assert(first_bounds.min_point.y == 0 && first_bounds.max_point.y == 1);
        const auto merged = first_snapshot.items[0].payload.mesh.mesh_handle;
        auto* geometry = tc_mesh_get(merged);
        assert(geometry && geometry->vertex_count == 6 && geometry->index_count == 6);
        assert(geometry->indices[1] == 2 && geometry->indices[2] == 1);
        const auto* pick = tc_vertex_layout_find(&geometry->layout, "pick_id");
        const auto* normal = tc_vertex_layout_find(&geometry->layout, "normal");
        const auto* tangent = tc_vertex_layout_find(&geometry->layout, "tangent");
        assert(pick && normal && tangent);
        const auto* data = static_cast<const uint8_t*>(geometry->vertices);
        uint32_t pick_a, pick_b;
        std::memcpy(&pick_a, data + pick->offset, 4);
        std::memcpy(&pick_b, data + 3 * geometry->layout.stride + pick->offset, 4);
        assert(pick_a == tc_entity_pool_pick_id(pool, first_id));
        assert(pick_b == tc_entity_pool_pick_id(pool, second_id));
        assert(std::abs(f(data, normal->offset) + 1 / std::sqrt(5.0f)) < 1e-5f);
        assert(std::abs(f(data, normal->offset + 4) - 2 / std::sqrt(5.0f)) < 1e-5f);
        assert(std::abs(f(data, tangent->offset) + 2 / std::sqrt(5.0f)) < 1e-5f);
        assert(f(data, tangent->offset + 12) == -1);
        auto warm = collect();
        assert(cache.stats().rebuilt_batches == 0 && cache.stats().reused_batches == 1);
        assert(tc_mesh_handle_eq(warm.items[0].payload.mesh.mesh_handle, merged));
        assert(warm.items[0].world_bounds.min_point.x == -1 && warm.items[0].world_bounds.max_point.x == 4);
        b.model_matrix[12] = 4;
        auto moved = collect();
        assert(cache.stats().rebuilt_batches == 1);
        assert(!tc_mesh_handle_eq(moved.items[0].payload.mesh.mesh_handle, merged));
        assert(moved.items[0].world_bounds.min_point.x == -1 && moved.items[0].world_bounds.max_point.x == 5);
        assert(tc_mesh_is_valid(merged)); // Previous immutable snapshot still owns it.
        const float changed_x = 2;
        std::memcpy(static_cast<uint8_t*>(source.get()->vertices) + layout.stride, &changed_x, sizeof(changed_x));
        tc_mesh_bump_version(source.get());
        auto revised = collect();
        assert(cache.stats().rebuilt_batches == 1);
        assert(revised.items[0].world_bounds.min_point.x == -3 && revised.items[0].world_bounds.max_point.x == 6);
        // The retained earlier snapshot still describes its original geometry.
        assert(first_snapshot.items[0].world_bounds.min_point.x == -1 && first_snapshot.items[0].world_bounds.max_point.x == 4);

        // Both entity pivots stay in chunk zero, while the mesh itself extends
        // beyond the chunk. Culling must use merged geometry, not the chunk cube.
        float far_vertices[36];
        std::memcpy(far_vertices, vertices, sizeof(vertices));
        far_vertices[0] += 20;
        far_vertices[12] += 20;
        far_vertices[24] += 20;
        info.name = "static-batch-offset-triangle";
        info.data = {far_vertices, 3, indices, 3, &layout};
        auto replacement = termin::TcMesh::from_interleaved(info);
        assert(replacement.is_valid());
        a.payload.mesh.mesh_handle = replacement.handle;
        b.payload.mesh.mesh_handle = replacement.handle;
        a.model_matrix[0] = 1;
        auto replaced = collect();
        assert(cache.stats().rebuilt_batches == 1 && replaced.items.size() == 1);
        assert(replaced.items[0].world_bounds.min_point.x == 21 && replaced.items[0].world_bounds.max_point.x == 25);
        termin::RenderItemCullingCounters offscreen_counters;
        termin::RenderItemCullingView origin_view(termin::Mat44f::identity(), termin::Mat44f::identity());
        assert(!origin_view.visible(replaced.items[0], offscreen_counters));
        auto shifted_view = termin::Mat44f::identity();
        shifted_view.data[12] = -23;
        termin::RenderItemCullingCounters shifted_counters;
        termin::RenderItemCullingView destination_view(shifted_view, termin::Mat44f::identity());
        assert(destination_view.visible(replaced.items[0], shifted_counters));
        assert(offscreen_counters.culled == 1 && shifted_counters.culled == 0);
        tc_entity_pool_set_pickable(pool, second_id, false);
        auto split_pickability = collect();
        assert(split_pickability.items.size() == 2 && cache.stats().output_batches == 0);
        tc_entity_pool_set_pickable(pool, second_id, true);
        b.model_matrix[12] = 12;
        auto split_chunk = collect();
        assert(split_chunk.items.size() == 2);
        b.model_matrix[12] = 4;
        mat->phases[0].state.blend = 1;
        auto transparent = collect();
        assert(transparent.items.size() == 2 && cache.stats().unsupported_geometry == 2);
        mat->phases[0].state.blend = 0;
        auto restored = collect();
        assert(restored.items.size() == 1);
        b.flags |= TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES;
        auto skinned = collect();
        assert(skinned.items.size() == 2);
        b.flags &= ~TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES;
        termin::RenderItemCollection removed;
        removed.items = {a};
        assert(cache.apply(removed, scene, UINT64_MAX, UINT64_MAX));
        assert(removed.items.size() == 1 && cache.stats().output_batches == 0);
        cache.clear_scene(scene);
        assert(tc_mesh_is_valid(merged));

        // Many spatial groups exercise indexed lookup while preserving first-seen
        // batch order, source member order, and trailing unbatched item order.
        constexpr size_t group_count = 96;
        termin::StaticMeshBatchCache indexed_cache;
        std::vector<tc_render_item> grouped;
        for (size_t i = 0; i < group_count; ++i) {
            const size_t chunk = (i * 37) % group_count;
            grouped.push_back(make_item(first, source.handle, material, 1000 + i * 2, float(chunk * 16 + 1)));
            grouped.back().geometry_id = static_cast<int>(i * 2);
            grouped.push_back(make_item(second, source.handle, material, 1001 + i * 2, float(chunk * 16 + 3)));
            grouped.back().geometry_id = static_cast<int>(i * 2 + 1);
        }
        auto standalone = make_item(first, source.handle, material, 9999, -100);
        standalone.flags &= ~TC_RENDER_ITEM_FLAG_STATIC_BATCH_ELIGIBLE;
        grouped.push_back(standalone);
        auto indexed_collect = [&](uint64_t layer, uint64_t category, int filter) {
            termin::RenderItemCollection result;
            result.items = grouped;
            assert(indexed_cache.apply(result, scene, layer, category, filter));
            return result;
        };
        auto many = indexed_collect(UINT64_MAX, UINT64_MAX, 0);
        assert(many.items.size() == group_count + 1);
        assert(indexed_cache.stats().work_groups == group_count);
        assert(indexed_cache.stats().work_key_comparisons == group_count);
        assert(indexed_cache.stats().rebuilt_batches == group_count);
        assert(indexed_cache.stats().signature_copies == group_count * 2);
        for (size_t i = 0; i < group_count; ++i) {
            assert(many.items[i].geometry_id == -1 - static_cast<int>(i));
            assert(many.items[i].model_matrix[12] == float(((i * 37) % group_count) * 16));
            assert(many.items[i].source.object_id == grouped[i * 2].source.object_id);
        }
        assert(many.items.back().source.object_id == standalone.source.object_id);
        auto many_warm = indexed_collect(UINT64_MAX, UINT64_MAX, 0);
        assert(indexed_cache.stats().cached_groups == group_count);
        assert(indexed_cache.stats().cache_key_comparisons == group_count);
        assert(indexed_cache.stats().signature_comparisons == group_count * 2);
        assert(indexed_cache.stats().signature_copies == 0);
        assert(indexed_cache.stats().rebuilt_batches == 0 && indexed_cache.stats().reused_batches == group_count);
        for (size_t i = 0; i < group_count; ++i)
            assert(tc_mesh_handle_eq(many.items[i].payload.mesh.mesh_handle, many_warm.items[i].payload.mesh.mesh_handle));

        // Masks/filters select independent cache variants, even with identical input.
        indexed_collect(1, UINT64_MAX, 0);
        // Identical merged content can share a resource handle across variants.
        // A fresh variant must still perform its own cache population.
        assert(indexed_cache.stats().cached_groups == 0);
        assert(indexed_cache.stats().rebuilt_batches == group_count);
        assert(indexed_cache.stats().reused_batches == 0);
        assert(indexed_cache.stats().signature_copies == group_count * 2);
        indexed_collect(1, UINT64_MAX, 0);
        assert(indexed_cache.stats().reused_batches == group_count);
        indexed_collect(1, 2, 0);
        assert(indexed_cache.stats().rebuilt_batches == group_count);
        indexed_collect(1, 2, 3);
        assert(indexed_cache.stats().rebuilt_batches == group_count);
        indexed_collect(UINT64_MAX, UINT64_MAX, 0);
        assert(indexed_cache.stats().reused_batches == group_count);

        // Existing signatures are recomputed: runtime material/shader revisions
        // and member reorder invalidate meshes even when semantic keys are unchanged.
        ++mat->header.version;
        indexed_collect(UINT64_MAX, UINT64_MAX, 0);
        assert(indexed_cache.stats().rebuilt_batches == group_count);
        const auto shader_handle = tc_shader_create("static-batch-revision-shader");
        assert(tc_shader_is_valid(shader_handle));
        mat->phases[0].shader = shader_handle;
        indexed_collect(UINT64_MAX, UINT64_MAX, 0);
        assert(indexed_cache.stats().rebuilt_batches == group_count);
        ++tc_shader_get(shader_handle)->version;
        indexed_collect(UINT64_MAX, UINT64_MAX, 0);
        assert(indexed_cache.stats().rebuilt_batches == group_count);
        std::swap(grouped[0], grouped[1]);
        indexed_collect(UINT64_MAX, UINT64_MAX, 0);
        assert(indexed_cache.stats().rebuilt_batches == 1 && indexed_cache.stats().reused_batches == group_count - 1);
        assert(indexed_cache.stats().signature_copies == 2);
        tc_entity_pool_set_layer(pool, second_id, 2);
        auto changed_layers = indexed_collect(UINT64_MAX, UINT64_MAX, 0);
        assert(changed_layers.items.size() == grouped.size() && indexed_cache.stats().work_groups == group_count * 2);
        tc_entity_pool_set_layer(pool, second_id, tc_entity_pool_layer(pool, first_id));
        indexed_collect(UINT64_MAX, UINT64_MAX, 0);
        assert(indexed_cache.stats().rebuilt_batches == group_count);
        grouped.erase(grouped.begin(), grouped.begin() + 2);
        indexed_collect(UINT64_MAX, UINT64_MAX, 0);
        assert(indexed_cache.stats().reused_batches == group_count - 1 && indexed_cache.stats().rebuilt_batches == 0);

        // A later rebuild failure must not consume an earlier cache hit. Retry
        // with the old sources reuses the entire prior cache and snapshot meshes.
        termin::StaticMeshBatchCache retry_cache;
        auto left_a = make_item(first, source.handle, material, 20001, 1);
        auto left_b = make_item(second, source.handle, material, 20002, 3);
        auto right_a = make_item(first, source.handle, material, 20003, 17);
        auto right_b = make_item(second, source.handle, material, 20004, 19);
        termin::RenderItemCollection retry_initial;
        retry_initial.items = {left_a, left_b, right_a, right_b};
        assert(retry_cache.apply(retry_initial, scene, UINT64_MAX, UINT64_MAX));
        const auto preserved_left = retry_initial.items[0].payload.mesh.mesh_handle;
        const auto preserved_right = retry_initial.items[1].payload.mesh.mesh_handle;
        auto bad_source = termin::TcMesh::from_interleaved(info);
        assert(bad_source.is_valid());
        bad_source.get()->indices[0] = UINT32_MAX;
        auto invalid_right = right_b;
        invalid_right.payload.mesh.mesh_handle = bad_source.handle;
        termin::RenderItemCollection failed;
        failed.items = {left_a, left_b, right_a, invalid_right};
        assert(!retry_cache.apply(failed, scene, UINT64_MAX, UINT64_MAX));
        assert(failed.items.size() == 4 && failed.adapter_payloads.empty());
        termin::RenderItemCollection retried;
        retried.items = {left_a, left_b, right_a, right_b};
        assert(retry_cache.apply(retried, scene, UINT64_MAX, UINT64_MAX));
        assert(retry_cache.stats().reused_batches == 2 && retry_cache.stats().rebuilt_batches == 0);
        assert(retry_cache.stats().signature_copies == 0);
        assert(tc_mesh_handle_eq(retried.items[0].payload.mesh.mesh_handle, preserved_left));
        assert(tc_mesh_handle_eq(retried.items[1].payload.mesh.mesh_handle, preserved_right));
        retry_cache.clear();
        assert(tc_mesh_is_valid(preserved_left) && tc_mesh_is_valid(preserved_right));
        check_scene_snapshot_membership(source.handle, material);

    }
    tc_component_detach_capability(&first, tc_drawable_capability_id());
    tc_component_detach_capability(&second, tc_drawable_capability_id());
    tc_entity_pool_remove_component(pool, first_id, &first);
    tc_entity_pool_remove_component(pool, second_id, &second);
    tc_scene_free(scene);
    tc_material_shutdown();
    tc_mesh_shutdown();
    tc_shader_shutdown();
}
