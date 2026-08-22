#include <termin/render/world2d_pass.hpp>

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstring>
#include <vector>

#include <tcbase/tc_log.hpp>
#include <termin/geom/vec4.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/render_scene_item_collector.hpp>
#include <termin/render/world2d_ordering.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

extern "C" {
#include <tgfx/resources/tc_shader.h>
}

namespace termin {
    namespace {

        constexpr const char* WORLD2D_SHADER_UUID = "termin-engine-world2d";

        // Raw vertex-buffer payload consumed by the World2D shader layout.
        struct World2DVertex {
            float position[3];
            float uv[2];
            float tint[4];
        };
        static_assert(sizeof(World2DVertex) == sizeof(float) * 9);
        static_assert(offsetof(World2DVertex, position) == 0);
        static_assert(offsetof(World2DVertex, uv) == sizeof(float) * 3);
        static_assert(offsetof(World2DVertex, tint) == sizeof(float) * 5);

        bool quad_outside_frustum(const tc_render_item_world_quad_payload& quad, const Mat44f& model_view_projection) {
            const std::array<Vec4f, 4> corners{{
                model_view_projection.transform_homogeneous({quad.min_x, 0.0f, quad.min_z, 1.0f}),
                model_view_projection.transform_homogeneous({quad.min_x, 0.0f, quad.max_z, 1.0f}),
                model_view_projection.transform_homogeneous({quad.max_x, 0.0f, quad.max_z, 1.0f}),
                model_view_projection.transform_homogeneous({quad.max_x, 0.0f, quad.min_z, 1.0f}),
            }};
            const auto all = [&corners](auto predicate) {
                return std::all_of(corners.begin(), corners.end(), predicate);
            };
            return all([](const Vec4f& p) { return p.x < -p.w; }) ||
                   all([](const Vec4f& p) { return p.x > p.w; }) ||
                   all([](const Vec4f& p) { return p.y < -p.w; }) ||
                   all([](const Vec4f& p) { return p.y > p.w; }) ||
                   all([](const Vec4f& p) { return p.z < 0.0f; }) ||
                   all([](const Vec4f& p) { return p.z > p.w; });
        }

        Vec3f transform_world(const Mat44f& model, float x, float z) {
            return model.transform_point(Vec3f{x, 0.0f, z});
        }

        void append_vertex(std::vector<World2DVertex>& vertices,
                           const Vec3f& position,
                           float u,
                           float v,
                           const tc_render_item_vec4& tint) {
            vertices.push_back({
                {
                    position.x,
                    position.y,
                    position.z,
                },
                {u, v},
                {
                    static_cast<float>(tint.x),
                    static_cast<float>(tint.y),
                    static_cast<float>(tint.z),
                    static_cast<float>(tint.w),
                },
            });
        }

        void append_quad_vertices(std::vector<World2DVertex>& vertices, const tc_render_item& item) {
            Mat44f model{};
            std::memcpy(model.data, item.model_matrix, sizeof(model.data));
            const auto& q = item.payload.world_quad;
            const Vec3f bottom_left = transform_world(model, q.min_x, q.min_z);
            const Vec3f top_left = transform_world(model, q.min_x, q.max_z);
            const Vec3f top_right = transform_world(model, q.max_x, q.max_z);
            const Vec3f bottom_right = transform_world(model, q.max_x, q.min_z);

            append_vertex(vertices, bottom_left, q.u0, q.v1, q.tint);
            append_vertex(vertices, top_left, q.u0, q.v0, q.tint);
            append_vertex(vertices, top_right, q.u1, q.v0, q.tint);
            append_vertex(vertices, bottom_left, q.u0, q.v1, q.tint);
            append_vertex(vertices, top_right, q.u1, q.v0, q.tint);
            append_vertex(vertices, bottom_right, q.u1, q.v1, q.tint);
        }

        bool compatible_batch(const tc_render_item& lhs, const tc_render_item& rhs) {
            return lhs.payload.world_quad.texture_handle.index == rhs.payload.world_quad.texture_handle.index &&
                   lhs.payload.world_quad.texture_handle.generation ==
                       rhs.payload.world_quad.texture_handle.generation &&
                   lhs.payload.world_quad.sampling == rhs.payload.world_quad.sampling;
        }

    } // namespace

    World2DPass::World2DPass(const std::string& input, const std::string& output)
        : input_res(input),
          output_res(output) {
        pass_name_set("World2D");
        link_to_type_registry("World2DPass");
    }

    World2DPass::~World2DPass() {
        release_resources();
    }

    std::set<const char*> World2DPass::compute_reads() const {
        return {input_res.c_str()};
    }

    std::set<const char*> World2DPass::compute_writes() const {
        return {output_res.c_str()};
    }

    std::vector<std::pair<std::string, std::string>> World2DPass::get_inplace_aliases() const {
        return {{input_res, output_res}};
    }

    void World2DPass::ensure_resources(tgfx::IRenderDevice& device) {
        if (device_ != &device) {
            release_resources();
            device_ = &device;
        }
        if (tc_shader_handle_is_invalid(shader_handle_)) {
            shader_handle_ = tgfx::register_builtin_shader_from_catalog(WORLD2D_SHADER_UUID);
        }
        if (!linear_sampler_) {
            tgfx::SamplerDesc desc{};
            desc.address_u = tgfx::AddressMode::ClampToEdge;
            desc.address_v = tgfx::AddressMode::ClampToEdge;
            desc.address_w = tgfx::AddressMode::ClampToEdge;
            linear_sampler_ = device.create_sampler(desc);
            desc.min_filter = tgfx::FilterMode::Nearest;
            desc.mag_filter = tgfx::FilterMode::Nearest;
            desc.mip_filter = tgfx::FilterMode::Nearest;
            nearest_sampler_ = device.create_sampler(desc);
            if (!linear_sampler_ || !nearest_sampler_) {
                tc::Log::error("[World2DPass] failed to create sprite samplers");
            }
        }
    }

    void World2DPass::release_resources() {
        if (device_) {
            if (linear_sampler_) {
                device_->destroy(linear_sampler_);
            }
            if (nearest_sampler_) {
                device_->destroy(nearest_sampler_);
            }
        }
        linear_sampler_ = {};
        nearest_sampler_ = {};
        device_ = nullptr;
        shader_handle_ = tc_shader_handle_invalid();
    }

    void World2DPass::execute(ExecuteContext& ctx) {
        if (!ctx.ctx2) {
            tc::Log::error("[World2DPass] render context is missing");
            return;
        }
        const RenderCamera* primary_view = ctx.view.primary_view();
        if (!primary_view) {
            tc::Log::error("[World2DPass] primary render view is missing");
            return;
        }
        auto color_it = ctx.tex2_writes.find(output_res);
        if (color_it == ctx.tex2_writes.end() || !color_it->second) {
            tc::Log::error("[World2DPass] output resource '%s' is missing", output_res.c_str());
            return;
        }
        auto depth_it = ctx.tex2_depth_writes.find(output_res);
        const tgfx::TextureHandle depth =
            depth_it == ctx.tex2_depth_writes.end() ? tgfx::TextureHandle{} : depth_it->second;
        const auto* snapshot = require_render_item_snapshot(ctx, "World2DPass");
        if (!snapshot) {
            return;
        }

        ensure_resources(ctx.ctx2->device());
        if (tc_shader_handle_is_invalid(shader_handle_) || !linear_sampler_ || !nearest_sampler_) {
            return;
        }
        tc_shader* shader = tc_shader_get(shader_handle_);
        tgfx::ShaderHandle vertex_shader;
        tgfx::ShaderHandle fragment_shader;
        if (!shader || !tc_shader_ensure_tgfx2(shader, &ctx.ctx2->device(), &vertex_shader, &fragment_shader)) {
            tc::Log::error("[World2DPass] failed to prepare world2d shader");
            return;
        }

        const Mat44f view = primary_view->view.to_float();
        const Mat44f projection = primary_view->projection.to_float();
        const Mat44f view_projection = projection * view;
        std::vector<const tc_render_item*> submissions;
        std::vector<World2DOrderEntry> order;
        submissions.reserve(snapshot->item_count());
        order.reserve(snapshot->item_count());
        for (const tc_render_item& item : snapshot->items()) {
            if (item.kind != TC_RENDER_ITEM_KIND_WORLD_QUAD || !(item.flags & TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX)) {
                continue;
            }
            Mat44f model{};
            std::memcpy(model.data, item.model_matrix, sizeof(model.data));
            if (quad_outside_frustum(item.payload.world_quad, view_projection * model)) {
                continue;
            }
            const size_t index = submissions.size();
            submissions.push_back(&item);
            const auto& quad = item.payload.world_quad;
            order.push_back({
                {
                    quad.sorting_layer,
                    quad.order_in_layer,
                    quad.spatial_depth,
                    quad.stable_tie_breaker,
                },
                index,
            });
        }
        if (!sort_world2d_order_entries(order)) {
            tc::Log::error("[World2DPass] rejected malformed world2d order keys");
            return;
        }

        const auto output_desc = ctx.ctx2->device().texture_desc(color_it->second);
        ctx.ctx2->begin_pass(color_it->second, depth, nullptr, 1.0f, false);
        ctx.ctx2->set_viewport(0, 0, static_cast<int>(output_desc.width), static_cast<int>(output_desc.height));
        ctx.ctx2->set_depth_test(true);
        ctx.ctx2->set_depth_write(false);
        ctx.ctx2->set_blend(true);
        ctx.ctx2->set_blend_func(tgfx::BlendFactor::SrcAlpha, tgfx::BlendFactor::OneMinusSrcAlpha);
        ctx.ctx2->set_cull(tgfx::CullMode::None);
        ctx.ctx2->bind_shader(vertex_shader, fragment_shader);
        ctx.ctx2->use_shader_resource_layout(shader);
        ctx.ctx2->bind_uniform_data("world2d_frame", view_projection.data, sizeof(view_projection.data));

        tgfx::VertexLayoutDesc layout{};
        layout.stride = sizeof(World2DVertex);
        layout.use_shader_input_locations = true;
        layout.attribute_count = 3;
        layout.attributes[0] = {0, tgfx::VertexFormat::Float3, offsetof(World2DVertex, position), nullptr};
        layout.attributes[1] = {1, tgfx::VertexFormat::Float2, offsetof(World2DVertex, uv), nullptr};
        layout.attributes[2] = {2, tgfx::VertexFormat::Float4, offsetof(World2DVertex, tint), nullptr};

        std::vector<World2DVertex> vertices;
        size_t begin = 0;
        while (begin < order.size()) {
            size_t end = begin + 1;
            const tc_render_item& first = *submissions[order[begin].submission_index];
            while (end < order.size() && compatible_batch(first, *submissions[order[end].submission_index])) {
                ++end;
            }

            vertices.clear();
            vertices.reserve((end - begin) * 6);
            for (size_t index = begin; index < end; ++index) {
                append_quad_vertices(vertices, *submissions[order[index].submission_index]);
            }
            tgfx::TextureHandle texture = ctx.ctx2->device().ensure_tc_texture(first.payload.world_quad.texture);
            const tgfx::SamplerHandle sampler = first.payload.world_quad.sampling == TC_WORLD_QUAD_SAMPLING_NEAREST
                                                    ? nearest_sampler_
                                                    : linear_sampler_;
            if (!texture) {
                tc::Log::error("[World2DPass] failed to upload sprite texture");
            } else {
                ctx.ctx2->bind_texture("u_texture", texture, sampler);
                ctx.ctx2->draw_transient_arrays(vertices.data(),
                                                static_cast<uint32_t>(vertices.size() * sizeof(World2DVertex)),
                                                static_cast<uint32_t>(vertices.size()),
                                                layout,
                                                tgfx::PrimitiveTopology::TriangleList);
            }
            begin = end;
        }
        ctx.ctx2->end_pass();
    }

    void World2DPass::destroy() {
        release_resources();
    }

    void World2DPass::register_type() {
        auto descriptor = FramePassTypeDescriptorBuilder::native<World2DPass>("World2DPass", "termin-render-passes");
        _register_inspect_input_res(descriptor.inspect());
        _register_inspect_output_res(descriptor.inspect());
        _register_inspect_metadata_graph(descriptor.inspect());
        (void)descriptor.commit();
    }

} // namespace termin
