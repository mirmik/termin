#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <limits>
#include <tcbase/profiler_scope.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/entity.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/static_mesh_batch.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <vector>
extern "C" {
#include <tgfx/resources/tc_material_registry.h>
#include <tgfx/resources/tc_shader_registry.h>
}
namespace termin {
    namespace {
        constexpr double chunk_size = 8.0;
        struct Key {
            std::array<int64_t, 3> chunk{};
            tc_material_handle material{};
            tc_vertex_layout layout{};
            std::vector<size_t> phases;
            tc_phase_mask component_phases = 0;
            uint64_t layer = 0, flags = 0;
            int priority = 0;
            bool pickable = false;
        };
        bool layout_equal(const tc_vertex_layout& a, const tc_vertex_layout& b) {
            if (a.stride != b.stride || a.attrib_count != b.attrib_count ||
                a.use_shader_input_locations != b.use_shader_input_locations)
                return false;
            for (uint32_t i = 0; i < a.attrib_count; ++i) {
                const auto& x = a.attribs[i];
                const auto& y = b.attribs[i];
                if (std::strcmp(x.name, y.name) || x.size != y.size || x.type != y.type || x.location != y.location ||
                    x.offset != y.offset)
                    return false;
            }
            return true;
        }
        bool key_equal(const Key& a, const Key& b) {
            return a.chunk == b.chunk && tc_material_handle_eq(a.material, b.material) && a.phases == b.phases &&
                   a.component_phases == b.component_phases && a.layer == b.layer && a.flags == b.flags &&
                   a.priority == b.priority && a.pickable == b.pickable && layout_equal(a.layout, b.layout);
        }
        struct Signature {
            uint64_t namespace_id = 0, object_id = 0;
            uint32_t generation = 0, component_id = 0;
            int geometry_id = 0;
            tc_mesh_handle mesh{};
            uint32_t mesh_version = 0, material_version = 0, pick_id = 0;
            std::array<float, 16> model{};
            std::vector<uint64_t> shaders;
        };
        bool signature_equal(const Signature& a, const Signature& b) {
            return a.namespace_id == b.namespace_id && a.object_id == b.object_id && a.generation == b.generation &&
                   a.component_id == b.component_id && a.geometry_id == b.geometry_id &&
                   tc_mesh_handle_eq(a.mesh, b.mesh) && a.mesh_version == b.mesh_version &&
                   a.material_version == b.material_version && a.pick_id == b.pick_id && a.model == b.model &&
                   a.shaders == b.shaders;
        }
        struct Member {
            size_t begin = 0, end = 0;
            Signature signature;
        };
        struct WorkGroup {
            Key key;
            std::vector<Member> members;
        };
        struct CachedGroup {
            Key key;
            std::vector<Signature> members;
            std::shared_ptr<const TcMesh> mesh;
        };
        struct Variant {
            tc_scene_handle scene{};
            uint64_t layer = 0, category = 0;
            int filter = 0;
            std::vector<CachedGroup> groups;
        };
        bool same_geometry(const tc_render_item& a, const tc_render_item& b) {
            return a.kind == b.kind && a.geometry_id == b.geometry_id &&
                   a.source.adapter_data == b.source.adapter_data &&
                   tc_mesh_handle_eq(a.payload.mesh.mesh_handle, b.payload.mesh.mesh_handle);
        }
        double determinant(const float* m) {
            return m[0] * (double(m[5]) * m[10] - double(m[9]) * m[6]) -
                   m[4] * (double(m[1]) * m[10] - double(m[9]) * m[2]) +
                   m[8] * (double(m[1]) * m[6] - double(m[5]) * m[2]);
        }
        bool eligible(const std::vector<tc_render_item>& items, size_t begin, size_t end, Key& key, Signature& sig) {
            const auto& item = items[begin];
            constexpr uint32_t prohibited =
                TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES | TC_RENDER_ITEM_FLAG_HAS_OVERRIDE_COLOR |
                TC_RENDER_ITEM_FLAG_HAS_INLINE_UNIFORM | TC_RENDER_ITEM_FLAG_BATCHED_GEOMETRY;
            if (item.kind != TC_RENDER_ITEM_KIND_MESH || !(item.flags & TC_RENDER_ITEM_FLAG_STATIC_BATCH_ELIGIBLE) ||
                !(item.flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX) || (item.flags & prohibited))
                return false;
            auto* component = render_scene_item_component(item);
            if (!component)
                return false;
            Entity entity(component->owner);
            if (!entity.valid())
                return false;
            auto* mesh = tc_mesh_get(item.payload.mesh.mesh_handle);
            auto* material = tc_material_get(item.material);
            if (!mesh || !material || !mesh->vertices || !mesh->indices ||
                item.payload.mesh.submesh_index >= mesh->submesh_count)
                return false;
            const auto& submesh = mesh->submeshes[item.payload.mesh.submesh_index];
            if (submesh.draw_mode != TC_DRAW_TRIANGLES || submesh.index_count < 3 || submesh.index_count % 3 ||
                submesh.first_index > mesh->index_count ||
                submesh.index_count > mesh->index_count - submesh.first_index)
                return false;
            const auto& layout = mesh->layout;
            if (layout.attrib_count >= TC_VERTEX_ATTRIBS_MAX || layout.stride > UINT16_MAX - sizeof(uint32_t))
                return false;
            bool position = false;
            for (uint32_t i = 0; i < layout.attrib_count; ++i) {
                const auto& attr = layout.attribs[i];
                if (attr.location == 7 ||
                    attr.offset + tgfx_attrib_type_size(static_cast<tgfx_attrib_type>(attr.type)) * attr.size >
                        layout.stride)
                    return false;
                const bool pos = std::strcmp(attr.name, "position") == 0;
                const bool normal = std::strcmp(attr.name, "normal") == 0;
                const bool tangent = std::strcmp(attr.name, "tangent") == 0;
                const bool uv = std::strcmp(attr.name, "uv") == 0;
                const bool color = std::strcmp(attr.name, "color") == 0;
                if (!(pos || normal || tangent || uv || color))
                    return false;
                if ((pos || normal) && (attr.type != TC_ATTRIB_FLOAT32 || attr.size != 3))
                    return false;
                if (tangent && (attr.type != TC_ATTRIB_FLOAT32 || attr.size != 4))
                    return false;
                position |= pos;
            }
            if (!position)
                return false;
            for (float value : item.model_matrix)
                if (!std::isfinite(value))
                    return false;
            const auto* m = item.model_matrix;
            if (m[3] != 0 || m[7] != 0 || m[11] != 0 || m[15] != 1 || std::abs(determinant(m)) < 1e-12)
                return false;
            for (size_t axis = 0; axis < 3; ++axis) {
                const double cell = std::floor(double(m[12 + axis]) / chunk_size);
                if (std::abs(cell) > double(INT32_MAX))
                    return false;
                key.chunk[axis] = static_cast<int64_t>(cell);
            }
            key.material = item.material;
            key.layout = layout;
            key.layer = entity.layer();
            key.flags = entity.flags();
            key.pickable = entity.pickable();
            key.priority = entity.priority();
            key.component_phases = tc_component_phase_mask(component);
            for (size_t i = begin; i < end; ++i) {
                const auto& phase_item = items[i];
                if (!tc_material_handle_eq(phase_item.material, item.material) ||
                    phase_item.material_phase_index >= material->phase_count || (phase_item.flags & prohibited) ||
                    std::memcmp(phase_item.model_matrix, m, sizeof(item.model_matrix)))
                    return false;
                const auto& phase = material->phases[phase_item.material_phase_index];
                if (phase.state.blend || !phase.state.depth_write)
                    return false;
                for (size_t j = 0; j < TC_MATERIAL_MAX_MARKS; ++j)
                    if (phase.mark_state_valid[j] && phase.mark_states[j].blend)
                        return false;
                key.phases.push_back(phase_item.material_phase_index);
                const tc_shader* shader =
                    tc_shader_handle_is_invalid(phase.shader) ? nullptr : tc_shader_get(phase.shader);
                sig.shaders.push_back((uint64_t(phase.shader.generation) << 32) | phase.shader.index);
                sig.shaders.push_back(shader ? shader->version : 0);
            }
            sig.namespace_id = item.source.namespace_id;
            sig.object_id = item.source.object_id;
            sig.generation = item.source.generation;
            sig.component_id = item.source.subobject_id;
            sig.geometry_id = item.geometry_id;
            sig.mesh = item.payload.mesh.mesh_handle;
            sig.mesh_version = mesh->header.version;
            sig.material_version = material->header.version;
            sig.pick_id = entity.pick_id();
            std::copy(m, m + 16, sig.model.begin());
            return true;
        }
        using V3 = std::array<double, 3>;
        V3 normalize(V3 v) {
            const double length = std::sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
            if (length > 1e-20)
                for (double& x : v)
                    x /= length;
            return v;
        }
        V3 read3(const uint8_t* p) {
            float v[3];
            std::memcpy(v, p, sizeof(v));
            return {v[0], v[1], v[2]};
        }
        void write3(uint8_t* p, V3 v) {
            float out[3] = {float(v[0]), float(v[1]), float(v[2])};
            std::memcpy(p, out, sizeof(out));
        }
        V3 linear(const float* m, V3 v) {
            return {m[0] * v[0] + m[4] * v[1] + m[8] * v[2],
                    m[1] * v[0] + m[5] * v[1] + m[9] * v[2],
                    m[2] * v[0] + m[6] * v[1] + m[10] * v[2]};
        }
        V3 normal_transform(const float* m, V3 n) {
            const double d = determinant(m);
            return normalize({((double(m[5]) * m[10] - double(m[9]) * m[6]) * n[0] +
                               (double(m[9]) * m[2] - double(m[1]) * m[10]) * n[1] +
                               (double(m[1]) * m[6] - double(m[5]) * m[2]) * n[2]) /
                                  d,
                              ((double(m[8]) * m[6] - double(m[4]) * m[10]) * n[0] +
                               (double(m[0]) * m[10] - double(m[8]) * m[2]) * n[1] +
                               (double(m[4]) * m[2] - double(m[0]) * m[6]) * n[2]) /
                                  d,
                              ((double(m[4]) * m[9] - double(m[8]) * m[5]) * n[0] +
                               (double(m[8]) * m[1] - double(m[0]) * m[9]) * n[1] +
                               (double(m[0]) * m[5] - double(m[4]) * m[1]) * n[2]) /
                                  d});
        }
        std::shared_ptr<const TcMesh> rebuild(const WorkGroup& group, const std::vector<tc_render_item>& items) {
            const tc::ProfilerScope scope("Static batch rebuild");
            tc_vertex_layout layout = group.key.layout;
            const uint32_t pick_offset = layout.stride;
            if (!tc_vertex_layout_add(&layout, "pick_id", 1, TC_ATTRIB_UINT32, 7))
                return {};
            std::vector<uint8_t> vertices;
            std::vector<uint32_t> indices;
            const auto* pos = tc_vertex_layout_find(&layout, "position");
            const auto* normal = tc_vertex_layout_find(&layout, "normal");
            const auto* tangent = tc_vertex_layout_find(&layout, "tangent");
            for (const auto& member : group.members) {
                const auto& item = items[member.begin];
                const auto* mesh = tc_mesh_get(member.signature.mesh);
                const auto& sub = mesh->submeshes[item.payload.mesh.submesh_index];
                std::vector<uint32_t> remap(mesh->vertex_count, UINT32_MAX);
                const auto* m = item.model_matrix;
                const size_t first = indices.size();
                for (size_t j = 0; j < sub.index_count; ++j) {
                    const int64_t source = int64_t(mesh->indices[sub.first_index + j]) + sub.vertex_offset;
                    if (source < 0 || uint64_t(source) >= mesh->vertex_count) {
                        tc::Log::error("[StaticBatch] invalid vertex index in source mesh '%s'", mesh->header.uuid);
                        return {};
                    }
                    uint32_t& mapped = remap[size_t(source)];
                    if (mapped == UINT32_MAX) {
                        const size_t vertex_index = vertices.size() / layout.stride;
                        if (vertex_index >= UINT32_MAX) {
                            tc::Log::error("[StaticBatch] merged mesh exceeds uint32 vertex indices");
                            return {};
                        }
                        mapped = static_cast<uint32_t>(vertex_index);
                        const size_t start = vertices.size();
                        vertices.resize(start + layout.stride, 0);
                        auto* dst = vertices.data() + start;
                        const auto* src = static_cast<const uint8_t*>(mesh->vertices) + source * mesh->layout.stride;
                        std::memcpy(dst, src, mesh->layout.stride);
                        auto p = linear(m, read3(src + pos->offset));
                        for (size_t axis = 0; axis < 3; ++axis)
                            p[axis] += double(m[12 + axis]) - group.key.chunk[axis] * chunk_size;
                        write3(dst + pos->offset, p);
                        V3 n{};
                        if (normal) {
                            n = normal_transform(m, read3(src + normal->offset));
                            write3(dst + normal->offset, n);
                        }
                        if (tangent) {
                            auto t = linear(m, read3(src + tangent->offset));
                            if (normal) {
                                double dot = t[0] * n[0] + t[1] * n[1] + t[2] * n[2];
                                for (size_t a = 0; a < 3; ++a)
                                    t[a] -= dot * n[a];
                            }
                            write3(dst + tangent->offset, normalize(t));
                            float w;
                            std::memcpy(&w, src + tangent->offset + 12, 4);
                            if (determinant(m) < 0)
                                w = -w;
                            std::memcpy(dst + tangent->offset + 12, &w, 4);
                        }
                        std::memcpy(dst + pick_offset, &member.signature.pick_id, sizeof(uint32_t));
                    }
                    indices.push_back(mapped);
                }
                if (determinant(m) < 0)
                    for (size_t j = first; j < indices.size(); j += 3)
                        std::swap(indices[j + 1], indices[j + 2]);
            }
            TcMeshCreateInfo info;
            info.name = "Static spatial batch";
            info.data = {vertices.data(), vertices.size() / layout.stride, indices.data(), indices.size(), &layout};
            auto mesh = std::make_shared<TcMesh>(TcMesh::from_interleaved(info));
            if (!mesh->is_valid()) {
                tc::Log::error("[StaticBatch] could not create merged mesh");
                return {};
            }
            return mesh;
        }
    } // namespace
    struct StaticMeshBatchCache::Impl {
        std::vector<Variant> variants;
        StaticMeshBatchStats stats;
    };
    StaticMeshBatchCache::StaticMeshBatchCache()
        : impl_(std::make_unique<Impl>()) {}
    StaticMeshBatchCache::~StaticMeshBatchCache() = default;
    const StaticMeshBatchStats& StaticMeshBatchCache::stats() const {
        return impl_->stats;
    }
    void StaticMeshBatchCache::clear() {
        impl_->variants.clear();
    }
    void StaticMeshBatchCache::clear_scene(tc_scene_handle scene) {
        std::erase_if(impl_->variants, [&](const Variant& v) { return tc_scene_handle_eq(v.scene, scene); });
    }
    bool StaticMeshBatchCache::apply(
        RenderItemCollection& collection, tc_scene_handle scene, uint64_t layer, uint64_t category, int filter) {
        const tc::ProfilerScope scope("Static mesh batching");
        auto& stats = impl_->stats;
        stats = {};
        auto found = std::find_if(impl_->variants.begin(), impl_->variants.end(), [&](const Variant& v) {
            return tc_scene_handle_eq(v.scene, scene) && v.layer == layer && v.category == category &&
                   v.filter == filter;
        });
        if (found == impl_->variants.end()) {
            impl_->variants.push_back({scene, layer, category, filter, {}});
            found = std::prev(impl_->variants.end());
        }
        std::vector<WorkGroup> groups;
        const auto& items = collection.items;
        for (size_t begin = 0; begin < items.size();) {
            size_t end = begin + 1;
            if (items[begin].kind == TC_RENDER_ITEM_KIND_MESH)
                while (end < items.size() && items[end].kind == TC_RENDER_ITEM_KIND_MESH &&
                       same_geometry(items[begin], items[end]))
                    ++end;
            ++stats.input_geometry;
            if (items[begin].flags & TC_RENDER_ITEM_FLAG_STATIC_BATCH_ELIGIBLE) {
                Key key;
                Signature signature;
                if (eligible(items, begin, end, key, signature)) {
                    ++stats.eligible_geometry;
                    auto group = std::find_if(
                        groups.begin(), groups.end(), [&](const WorkGroup& g) { return key_equal(g.key, key); });
                    if (group == groups.end()) {
                        groups.push_back({std::move(key), {}});
                        group = std::prev(groups.end());
                    }
                    group->members.push_back({begin, end, std::move(signature)});
                } else
                    ++stats.unsupported_geometry;
            }
            begin = end;
        }
        if (std::none_of(groups.begin(), groups.end(), [](const WorkGroup& g) { return g.members.size() >= 2; })) {
            found->groups.clear();
            return true;
        }
        std::vector<CachedGroup> next;
        std::vector<tc_render_item> output;
        std::vector<bool> consumed(items.size(), false);
        for (const auto& group : groups) {
            if (group.members.size() < 2)
                continue;
            auto previous = std::find_if(found->groups.begin(), found->groups.end(), [&](const CachedGroup& c) {
                if (!key_equal(c.key, group.key) || c.members.size() != group.members.size())
                    return false;
                for (size_t i = 0; i < c.members.size(); ++i)
                    if (!signature_equal(c.members[i], group.members[i].signature))
                        return false;
                return true;
            });
            std::shared_ptr<const TcMesh> mesh;
            if (previous != found->groups.end()) {
                mesh = previous->mesh;
                ++stats.reused_batches;
            } else {
                mesh = rebuild(group, items);
                if (!mesh)
                    return false;
                ++stats.rebuilt_batches;
            }
            CachedGroup cached{group.key, {}, mesh};
            for (const auto& m : group.members) {
                cached.members.push_back(m.signature);
                for (size_t i = m.begin; i < m.end; ++i)
                    consumed[i] = true;
            }
            next.push_back(std::move(cached));
            collection.retain_adapter_payload(mesh);
            const auto& representative = group.members.front();
            for (size_t i = representative.begin; i < representative.end; ++i) {
                auto item = items[i];
                item.flags =
                    (item.flags & ~TC_RENDER_ITEM_FLAG_STATIC_BATCH_ELIGIBLE) | TC_RENDER_ITEM_FLAG_BATCHED_GEOMETRY;
                item.payload.mesh.mesh_handle = mesh->handle;
                item.payload.mesh.submesh_index = 0;
                // Unique negative geometry ids keep adjacent batches distinct while
                // all phases of one merged geometry stay grouped in auxiliary passes.
                item.geometry_id = -1 - static_cast<int>(stats.output_batches);
                std::fill(std::begin(item.model_matrix), std::end(item.model_matrix), 0.0f);
                item.model_matrix[0] = item.model_matrix[5] = item.model_matrix[10] = item.model_matrix[15] = 1;
                for (size_t a = 0; a < 3; ++a)
                    item.model_matrix[12 + a] = float(group.key.chunk[a] * chunk_size);
                output.push_back(item);
            }
            stats.merged_geometry += group.members.size();
            ++stats.output_batches;
        }
        for (size_t i = 0; i < items.size(); ++i)
            if (!consumed[i])
                output.push_back(items[i]);
        collection.items = std::move(output);
        found->groups = std::move(next);
        if (stats.rebuilt_batches)
            tc::Log::info(
                "[StaticBatch] inputs=%llu eligible=%llu merged=%llu batches=%llu rebuilt=%llu unsupported=%llu",
                (unsigned long long)stats.input_geometry,
                (unsigned long long)stats.eligible_geometry,
                (unsigned long long)stats.merged_geometry,
                (unsigned long long)stats.output_batches,
                (unsigned long long)stats.rebuilt_batches,
                (unsigned long long)stats.unsupported_geometry);
        return true;
    }
} // namespace termin
