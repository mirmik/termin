#include <cassert>
#include <cmath>
#include <cstring>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/static_mesh_batch.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
extern "C" {
#include <core/tc_component.h>
#include <core/tc_drawable_capability.h>
#include <core/tc_entity_pool.h>
#include <core/tc_scene.h>
#include <tgfx/resources/tc_material_registry.h>
}
namespace {
    tc_phase_mask phases(tc_component*) {
        return TC_PHASE_OPAQUE | TC_PHASE_DEPTH | TC_PHASE_ID;
    }
    const tc_drawable_vtable drawable{&phases, nullptr};
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
                     TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE;
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
} // namespace
int main() {
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
    assert(tc_drawable_capability_attach(&first, &drawable, &first));
    assert(tc_drawable_capability_attach(&second, &drawable, &second));
    auto material = tc_material_create("static-batch-material", "static-batch-material");
    auto* mat = tc_material_get(material);
    tc_material_add_phase(mat, tc_shader_handle_invalid(), "opaque", 0);
    mat->phases[0].state = tc_render_state_opaque();
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
            return result;
        };
        auto first_snapshot = collect();
        assert(first_snapshot.items.size() == 1);
        assert(cache.stats().rebuilt_batches == 1);
        assert(cache.stats().merged_geometry == 2);
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
        b.model_matrix[12] = 4;
        auto moved = collect();
        assert(cache.stats().rebuilt_batches == 1);
        assert(!tc_mesh_handle_eq(moved.items[0].payload.mesh.mesh_handle, merged));
        assert(tc_mesh_is_valid(merged)); // Previous immutable snapshot still owns it.
        tc_mesh_bump_version(source.get());
        auto revised = collect();
        assert(cache.stats().rebuilt_batches == 1);
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
    }
    tc_component_detach_capability(&first, tc_drawable_capability_id());
    tc_component_detach_capability(&second, tc_drawable_capability_id());
    tc_entity_pool_remove_component(pool, first_id, &first);
    tc_entity_pool_remove_component(pool, second_id, &second);
    tc_scene_free(scene);
    tc_material_shutdown();
    tc_mesh_shutdown();
}
