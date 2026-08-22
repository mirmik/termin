#include <termin/render/line_renderer.hpp>

#include <algorithm>
#include <cstring>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/render/material_pipeline.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/world_tube_line_renderer.hpp>

extern "C" {
#include <core/tc_drawable_protocol.h>
#include <tgfx/resources/tc_shader_registry.h>
}

namespace termin {

    constexpr const char* DEFAULT_LINE_SHADER_UUID = "termin-engine-line-default";

    namespace {

        double value_as_double(const tc_value* value) {
            if (!value) {
                return 0.0;
            }
            switch (value->type) {
            case TC_VALUE_INT:
                return static_cast<double>(value->data.i);
            case TC_VALUE_FLOAT:
                return static_cast<double>(value->data.f);
            case TC_VALUE_DOUBLE:
                return value->data.d;
            default:
                return 0.0;
            }
        }

        bool value_to_vec3(const tc_value* value, tc_vec3& out) {
            if (!value || value->type != TC_VALUE_LIST || tc_value_list_size(value) < 3) {
                return false;
            }
            out.x = value_as_double(tc_value_list_get(const_cast<tc_value*>(value), 0));
            out.y = value_as_double(tc_value_list_get(const_cast<tc_value*>(value), 1));
            out.z = value_as_double(tc_value_list_get(const_cast<tc_value*>(value), 2));
            return true;
        }

        tc_value vec3_to_value(const tc_vec3& point) {
            tc_value value = tc_value_list_new();
            tc_value_list_push(&value, tc_value_double(point.x));
            tc_value_list_push(&value, tc_value_double(point.y));
            tc_value_list_push(&value, tc_value_double(point.z));
            return value;
        }

        tgfx::LinePoint3 transform_line_point(const Mat44f& model, const tc_vec3& point) {
            return model.transform_point(point.to_float());
        }

        tc_material_phase* find_phase(tc_material* material, tc_phase_mask requested_phase) {
            if (!material) {
                return nullptr;
            }
            for (size_t i = 0; i < material->phase_count; ++i) {
                if (requested_phase == material->phases[i].phase) {
                    return &material->phases[i];
                }
            }
            return nullptr;
        }

        bool accepts_phase(tc_phase_mask phase, bool cast_shadow) {
            if (phase == TC_PHASE_SHADOW) {
                return cast_shadow;
            }
            return true;
        }

        MaterialPipelineSemantic line_semantic(std::string name, MaterialPipelineValueType type) {
            return {std::move(name), type};
        }

        bool consumes_only_world_position(const VertexOutputAdapter& adapter) {
            const auto& semantics = adapter.consumed_world_semantics.semantics;
            return semantics.size() == 1 && semantics[0].name == "world_pos" &&
                   semantics[0].type == MaterialPipelineValueType::Float3;
        }

        VertexTransformProvider world_tube_vertex_transform_provider(
            const MaterialPipelinePassContract& pass_contract) {
            VertexTransformProvider provider;
            // Render-item transform kinds are coarse pass compatibility metadata.
            // The explicit provider below is the authoritative line geometry ABI.
            provider.kind = VertexTransformKind::StaticMesh;
            provider.debug_name = "world_tube_line";
            provider.vertex_entry = "vs_main";
            provider.vertex_inputs.mesh_attributes = {
                line_semantic("corner", MaterialPipelineValueType::Float3),
                line_semantic("p0", MaterialPipelineValueType::Float3),
                line_semantic("width", MaterialPipelineValueType::Float),
                line_semantic("p1", MaterialPipelineValueType::Float3),
            };
            provider.produced_fragment_input = material_pipeline_standard_material_fragment_interface();
            provider.produced_world_semantics = material_pipeline_standard_material_fragment_interface();
            provider.source_module = {"termin_world_tube_line_transform",
                                      "builtin_shaders/termin_world_tube_line_transform.slang"};
            provider.entry_input_declaration = R"(
struct VertexInput {
    float3 corner : TEXCOORD0;
    float3 p0 : POSITION0;
    float width : TEXCOORD1;
    float3 p1 : POSITION1;
};)";
            provider.adapter_input_expression =
                "termin_world_tube_vertex(input.corner, input.p0, input.width, input.p1)";
            if (pass_contract.vertex_output_adapter &&
                consumes_only_world_position(*pass_contract.vertex_output_adapter)) {
                provider.adapter_input_expression += ".position";
            }
            return provider;
        }

        TcShader assemble_world_tube_material_shader(TcShader original_shader,
                                                     const MaterialPipelinePassContract& pass_contract,
                                                     const char* debug_context) {
            MaterialShaderOverrideRequest override_request{};
            override_request.original_shader = std::move(original_shader);
            override_request.vertex_transform_kind = VertexTransformKind::StaticMesh;
            override_request.vertex_transform_contract = world_tube_vertex_transform_provider(pass_contract);
            override_request.pass_contract = pass_contract;
            override_request.shader_variant_op = TC_SHADER_VARIANT_LINE_TUBE;
            override_request.debug_context = debug_context ? debug_context : "LineRenderer/WorldTube";
            return assemble_material_shader_override(override_request);
        }

        struct LineBatchEncoderState {
            std::unique_ptr<tgfx::WorldTubeLineRenderer> world_tube_renderer;
        };

        static_assert(sizeof(tc_render_item_vec3) == sizeof(tc_vec3), "tc_render_item_vec3 must match tc_vec3 storage");
        static_assert(alignof(tc_render_item_vec3) == alignof(tc_vec3),
                      "tc_render_item_vec3 must match tc_vec3 alignment");

        bool encode_line_batch_render_item_tgfx2(tgfx::RenderContext2& ctx,
                                                 const tc_render_item& item,
                                                 const RenderItemDrawSubmitRequest& request,
                                                 LineBatchEncoderState& state) {
            if (item.kind != TC_RENDER_ITEM_KIND_LINE_BATCH) {
                tc::Log::error("[LineRenderer] line encoder received unsupported item kind %u", item.kind);
                return false;
            }
            if (!request.draw_context) {
                tc::Log::error("[LineRenderer] cannot encode line batch without draw context");
                return false;
            }

            const RenderContext& context = *request.draw_context;
            tc_material_phase* phase = request.material_phase ? request.material_phase : item.material_phase;
            const tc_phase_mask requested_phase =
                request.phase != TC_PHASE_NONE ? request.phase : (phase ? phase->phase : TC_PHASE_NONE);

            if (!accepts_phase(requested_phase, true)) {
                return false;
            }
            if (!item.payload.line_batch.points || item.payload.line_batch.point_count < 2) {
                return true;
            }

            std::vector<tgfx::LinePoint3> world_points;
            world_points.reserve(item.payload.line_batch.point_count);
            for (size_t i = 0; i < item.payload.line_batch.point_count; ++i) {
                const tc_render_item_vec3& point = item.payload.line_batch.points[i];
                world_points.push_back(transform_line_point(context.model, tc_vec3{point.x, point.y, point.z}));
            }

            if (!request.device || tc_shader_handle_is_invalid(request.shader_handle)) {
                tc::Log::error("[LineRenderer] planned WorldTube draw has no final shader/device");
                return false;
            }
            MaterialPipelineShaderBinding shader_binding{};
            if (!ensure_material_pipeline_shader(
                    ctx, *request.device, request.shader_handle, "LineRenderer/WorldTube", shader_binding)) {
                tc::Log::error("[LineRenderer] failed to prepare planned WorldTube shader");
                return false;
            }

            if (!state.world_tube_renderer) {
                state.world_tube_renderer = std::make_unique<tgfx::WorldTubeLineRenderer>();
            }
            tgfx::WorldTubeLineStyle style;
            style.width = std::max(item.payload.line_batch.width, 0.0f);
            style.sides = std::clamp(item.payload.line_batch.tube_sides, 3, 32);

            tgfx::WorldTubeLineParams params;
            params.vertex_shader = shader_binding.vertex;
            params.fragment_shader = shader_binding.fragment;
            params.shader_layout = shader_binding.shader;
            params.bind_resources = [&request, phase](tgfx::RenderContext2& line_ctx,
                                                      const tc_shader* shader_layout) -> bool {
                RenderItemDrawSubmitRequest line_request = request;
                line_request.material_phase = phase;
                return bind_render_item_common_resources(line_ctx, shader_layout, line_request);
            };

            return state.world_tube_renderer->draw_polyline(ctx, world_points, style, params);
        }

        bool line_render_item_draw_encoder(tgfx::RenderContext2& ctx,
                                           const tc_render_item& item,
                                           const RenderItemDrawSubmitRequest& request,
                                           void* user_data) {
            auto* state = static_cast<LineBatchEncoderState*>(user_data);
            if (!state) {
                tc::Log::error("[LineRenderer] line encoder has no state");
                return false;
            }
            return encode_line_batch_render_item_tgfx2(ctx, item, request, *state);
        }

        RenderItemTaskRejection line_render_item_task_shader_planner(const RenderItemTaskPlanningRequest& request,
                                                                     RenderItemTaskShaderPlan& out_plan,
                                                                     const char*& out_detail,
                                                                     void* user_data);

        void ensure_line_render_item_encoder_registered() {
            static bool registered = false;
            static LineBatchEncoderState state;
            if (registered) {
                return;
            }

            RenderItemDrawEncoderDesc desc{};
            desc.encode = line_render_item_draw_encoder;
            desc.plan_task_shader = line_render_item_task_shader_planner;
            desc.user_data = &state;
            desc.debug_name = "LineRenderer";
            desc.capabilities.phase_mask = TC_PHASE_ALL & ~TC_PHASE_NORMAL;
            desc.capabilities.vertex_transform_kind_mask =
                render_item_vertex_transform_kind_bit(VertexTransformKind::StaticMesh);
            desc.capabilities.supported_task_input_mask =
                render_item_task_input_bit(RenderItemTaskInput::DrawContext) |
                render_item_task_input_bit(RenderItemTaskInput::ModelMatrix) |
                render_item_task_input_bit(RenderItemTaskInput::OverrideColor);
            desc.capabilities.required_task_input_mask = render_item_task_input_bit(RenderItemTaskInput::DrawContext);
            desc.capabilities.requires_draw_context = true;
            desc.capabilities.consumes_common_resources = true;
            registered = register_render_item_draw_encoder(TC_RENDER_ITEM_KIND_LINE_BATCH, desc);
        }

    } // namespace

    bool emit_line_batch_render_items(tc_component* component,
                                      const tc_render_item_collect_context& context,
                                      tc_render_item_sink& sink,
                                      const LineBatchRenderItemDesc& desc) {
        if (!component) {
            tc::Log::error("[LineBatchRenderItem] cannot emit from null component");
            return false;
        }
        if (!sink.emit) {
            tc::Log::error("[LineBatchRenderItem] cannot emit with null sink");
            return false;
        }
        if (!desc.points || desc.point_count < 2) {
            return true;
        }

        const bool collect_all_phases = context.phase == TC_PHASE_NONE;
        if (!collect_all_phases && !accepts_phase(context.phase, desc.cast_shadow)) {
            return true;
        }

        tc_material* raw = desc.material.get();
        if (!raw) {
            return true;
        }

        const bool allow_missing_material_phase =
            (context.flags & TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE) != 0u;
        bool emitted = false;

        auto emit_phase = [&](tc_material_phase* phase, tc_material_handle material_handle) -> bool {
            if (!phase && !allow_missing_material_phase) {
                return true;
            }

            tc_render_item item{};
            item.kind = TC_RENDER_ITEM_KIND_LINE_BATCH;
            item.flags = TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX;
            item.geometry_id = desc.geometry_id;
            item.material_phase = phase;
            item.material = material_handle;
            item.material_phase_index = SIZE_MAX;
            item.payload.line_batch.points = reinterpret_cast<const tc_render_item_vec3*>(desc.points);
            item.payload.line_batch.point_count = desc.point_count;
            item.payload.line_batch.width = desc.width;
            item.payload.line_batch.tube_sides = desc.tube_sides;

            if (phase) {
                item.flags |= TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE;
                tc_material* owner = tc_material_get(material_handle);
                item.material_phase_index = owner ? static_cast<size_t>(phase - owner->phases) : SIZE_MAX;
            }
            if (desc.has_override_color) {
                item.flags |= TC_RENDER_ITEM_FLAG_HAS_OVERRIDE_COLOR;
                item.override_color = {desc.override_color.r,
                                       desc.override_color.g,
                                       desc.override_color.b,
                                       desc.override_color.a};
            }

            std::memcpy(item.model_matrix, desc.model_matrix.data, sizeof(float) * 16);
            emitted = true;
            return sink.emit(&item, sink.user_data);
        };

        bool found_shadow_phase = false;
        for (size_t i = 0; i < raw->phase_count; ++i) {
            tc_material_phase* phase = &raw->phases[i];
            if (!accepts_phase(phase->phase, desc.cast_shadow)) {
                continue;
            }
            if (phase->phase == TC_PHASE_SHADOW) {
                found_shadow_phase = true;
            }
            if ((collect_all_phases || context.phase == phase->phase) && !emit_phase(phase, desc.material.handle)) {
                return false;
            }
        }

        if (desc.cast_shadow && (collect_all_phases || context.phase == TC_PHASE_SHADOW) && !found_shadow_phase) {
            if (!emit_phase(find_phase(desc.shadow_fallback_material.get(), TC_PHASE_SHADOW),
                            desc.shadow_fallback_material.handle)) {
                return false;
            }
        }

        if (!emitted && allow_missing_material_phase) {
            return emit_phase(nullptr, desc.material.handle);
        }

        return true;
    }

    namespace {

        RenderItemTaskRejection line_render_item_task_shader_planner(const RenderItemTaskPlanningRequest& request,
                                                                     RenderItemTaskShaderPlan& out_plan,
                                                                     const char*& out_detail,
                                                                     void* user_data) {
            (void)user_data;
            if (!request.item || request.item->kind != TC_RENDER_ITEM_KIND_LINE_BATCH || !request.contract ||
                !request.contract->shader_contract) {
                out_detail = "line planner received an invalid request";
                return RenderItemTaskRejection::ShaderPlanningRejected;
            }
            out_plan.has_vertex_transform_kind = true;
            out_plan.vertex_transform_kind = VertexTransformKind::StaticMesh;
            const uint64_t transform_bit =
                render_item_vertex_transform_kind_bit(out_plan.vertex_transform_kind);
            if ((request.contract->accepted_vertex_transform_kind_mask & transform_bit) == 0u) {
                out_detail = "pass contract does not accept the WorldTube vertex transform";
                return RenderItemTaskRejection::PassVertexTransformUnsupported;
            }

            TcShader variant = assemble_world_tube_material_shader(
                TcShader(request.candidate_shader),
                *request.contract->shader_contract,
                request.contract->debug_pass_name);
            if (!variant.is_valid()) {
                out_detail = "failed to assemble the WorldTube material shader";
                return RenderItemTaskRejection::ShaderPlanningRejected;
            }
            if (!out_plan.set_final_shader(std::move(variant))) {
                out_detail = "WorldTube shader usage packet is full";
                return RenderItemTaskRejection::ShaderPlanningRejected;
            }
            out_detail = nullptr;
            return RenderItemTaskRejection::None;
        }

    } // namespace

    LineRenderer::LineRenderer(const char* type_name)
        : Component(type_name) {
        install_drawable_vtable(&_c);
    }

    void LineRenderer::register_type() {
        ensure_line_render_item_encoder_registered();
        auto descriptor = ComponentTypeDescriptorBuilder::native<LineRenderer>(
            "LineRenderer", "termin-components-render", "Component");
        descriptor.category("Rendering");
        auto& inspect = descriptor.inspect();
        inspect.add_with_callbacks<LineRenderer, TcMaterial>(
            "LineRenderer",
            "material",
            "Material",
            "tc_material",
            [](LineRenderer* self) -> TcMaterial& { return self->material; },
            [](LineRenderer* self, const TcMaterial& value) { self->set_material(value); });
        inspect.add_with_callbacks<LineRenderer, float>(
            "LineRenderer",
            "width",
            "Width",
            "float",
            [](LineRenderer* self) -> float& { return self->width; },
            [](LineRenderer* self, const float& value) { self->set_width(value); },
            0.001,
            10.0,
            0.01);
        inspect.add_with_callbacks<LineRenderer, bool>(
            "LineRenderer",
            "cast_shadow",
            "Cast Shadow",
            "bool",
            [](LineRenderer* self) -> bool& { return self->cast_shadow; },
            [](LineRenderer* self, const bool& value) { self->set_cast_shadow(value); });
        inspect.add_with_callbacks<LineRenderer, int>(
            "LineRenderer",
            "tube_sides",
            "Tube Sides",
            "int",
            [](LineRenderer* self) -> int& { return self->tube_sides; },
            [](LineRenderer* self, const int& value) { self->set_tube_sides(value); },
            3,
            32,
            1);
        inspect.add_with_accessors<LineRenderer, std::vector<tc_vec3>>(
            "LineRenderer",
            "points",
            "Positions",
            "list[vec3]",
            [](LineRenderer* self) { return self->points(); },
            [](LineRenderer* self, std::vector<tc_vec3> value) { self->set_points(std::move(value)); });
        (void)descriptor.commit();
    }

    LineRenderer::~LineRenderer() = default;

    TcMaterial LineRenderer::default_material() {
        static TcMaterial mat;
        if (mat.is_valid()) {
            return mat;
        }

        mat = TcMaterial::create("DefaultLineMaterial", "");
        if (!mat.is_valid()) {
            tc::Log::error("[LineRenderer] failed to create default material");
            return mat;
        }

        mat.set_shader_name("DefaultLineShader");
        tc_render_state state = tc_render_state_opaque();
        state.cull = 0;
        tc_shader_handle shader_handle = tgfx::register_builtin_shader_from_catalog(DEFAULT_LINE_SHADER_UUID);
        if (tc_shader_handle_is_invalid(shader_handle)) {
            tc::Log::error("[LineRenderer] failed to register default line shader");
            return mat;
        }

        tc_material_phase* phase = mat.add_phase(shader_handle, "opaque", 0);
        if (!phase) {
            tc::Log::error("[LineRenderer] failed to create default material phase");
            return mat;
        }
        phase->state = state;
        {
            const LinearColor linear_white{1.0f, 1.0f, 1.0f, 1.0f};
            const float color[4] = {linear_white.r, linear_white.g, linear_white.b, linear_white.a};
            tc_material_phase_set_uniform(phase, "u_color", TC_UNIFORM_VEC4, color);
        }

        tc_material_phase* shadow_phase = mat.add_phase(shader_handle, "shadow", 0);
        if (!shadow_phase) {
            tc::Log::error("[LineRenderer] failed to create default shadow material phase");
            return mat;
        }
        shadow_phase->state = state;
        {
            const LinearColor linear_white{1.0f, 1.0f, 1.0f, 1.0f};
            const float color[4] = {linear_white.r, linear_white.g, linear_white.b, linear_white.a};
            tc_material_phase_set_uniform(shadow_phase, "u_color", TC_UNIFORM_VEC4, color);
        }
        return mat;
    }

    TcMaterial LineRenderer::effective_material() const {
        if (material.is_valid()) {
            return material;
        }
        return default_material();
    }

    void LineRenderer::set_points(const std::vector<tc_vec3>& points) {
        points_ = points;
    }

    void LineRenderer::set_points(std::vector<tc_vec3>&& points) {
        points_ = std::move(points);
    }

    void LineRenderer::clear_points() {
        points_.clear();
    }

    void LineRenderer::add_point(const tc_vec3& point) {
        points_.push_back(point);
    }

    void LineRenderer::set_segment(const tc_vec3& start, const tc_vec3& end) {
        if (points_.size() != 2) {
            points_.resize(2);
        }
        points_[0] = start;
        points_[1] = end;
    }

    void LineRenderer::set_width(float value) {
        width = value;
    }

    void LineRenderer::set_cast_shadow(bool value) {
        cast_shadow = value;
    }

    void LineRenderer::set_tube_sides(int value) {
        tube_sides = std::clamp(value, 3, 32);
    }

    void LineRenderer::set_material(const TcMaterial& value) {
        material = value;
    }

    void LineRenderer::set_material_by_name(const std::string& name) {
        tc_material_handle handle = tc_material_find_by_name(name.c_str());
        if (tc_material_handle_is_invalid(handle)) {
            tc::Log::error("[LineRenderer] material '%s' not found", name.c_str());
            material = TcMaterial();
            return;
        }
        material = TcMaterial(handle);
    }

    tc_value LineRenderer::serialize_points() const {
        tc_value result = tc_value_list_new();
        for (const tc_vec3& point : points_) {
            tc_value_list_push(&result, vec3_to_value(point));
        }
        return result;
    }

    void LineRenderer::deserialize_points(const tc_value* value) {
        std::vector<tc_vec3> loaded;
        if (value && value->type == TC_VALUE_LIST) {
            loaded.reserve(tc_value_list_size(value));
            for (size_t i = 0; i < tc_value_list_size(value); ++i) {
                tc_value* item = tc_value_list_get(const_cast<tc_value*>(value), i);
                tc_vec3 point = {0.0, 0.0, 0.0};
                if (value_to_vec3(item, point)) {
                    loaded.push_back(point);
                } else {
                    tc::Log::error("[LineRenderer] invalid point at index %zu during deserialize", i);
                }
            }
        }
        set_points(std::move(loaded));
    }

    tc_value LineRenderer::serialize_data() const {
        return Component::serialize_data();
    }

    void LineRenderer::deserialize_data(const tc_value* data, tc_scene_handle scene) {
        Component::deserialize_data(data, scene);
    }

    tc_phase_mask LineRenderer::get_phase_mask() const {
        tc_phase_mask mask = TC_PHASE_NONE;
        TcMaterial mat = effective_material();
        tc_material* raw = mat.get();
        if (!raw)
            return mask;
        for (size_t i = 0; i < raw->phase_count; ++i) {
            if (accepts_phase(raw->phases[i].phase, cast_shadow)) {
                mask |= raw->phases[i].phase;
            }
        }
        mask |= TC_PHASE_DEPTH | TC_PHASE_ID;
        if (cast_shadow)
            mask |= TC_PHASE_SHADOW;
        return mask;
    }

    bool LineRenderer::collect_render_items(const tc_render_item_collect_context& context, tc_render_item_sink& sink) {
        if (points_.size() < 2) {
            return true;
        }

        const bool collect_all_phases = context.phase == TC_PHASE_NONE;
        if (!collect_all_phases && !accepts_phase(context.phase, cast_shadow)) {
            return true;
        }

        TcMaterial mat = effective_material();
        if (!mat.is_valid()) {
            return true;
        }

        LineBatchRenderItemDesc desc;
        desc.points = points_.data();
        desc.point_count = points_.size();
        desc.material = mat;
        desc.shadow_fallback_material = default_material();
        desc.width = width;
        desc.cast_shadow = cast_shadow;
        desc.tube_sides = tube_sides;
        desc.geometry_id = 0;
        desc.model_matrix = get_model_matrix(entity());
        return emit_line_batch_render_items(this->tc_component_ptr(), context, sink, desc);
    }

    bool LineRenderer::encode_render_item_tgfx2(tgfx::RenderContext2& ctx2,
                                                const tc_render_item& item,
                                                const RenderItemDrawSubmitRequest& request) {
        static LineBatchEncoderState state;
        return encode_line_batch_render_item_tgfx2(ctx2, item, request, state);
    }

} // namespace termin
