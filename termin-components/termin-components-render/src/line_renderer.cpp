#include <termin/render/line_renderer.hpp>

#include <algorithm>
#include <array>
#include <cstring>
#include <limits>
#include <unordered_map>

#include <termin/render/material_pipeline.hpp>
#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/line_mesh_builder.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/screen_space_line_renderer.hpp>
#include <tgfx2/tc_shader_bridge.hpp>
#include <tgfx2/world_space_line_renderer.hpp>
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

tgfx::LinePoint3 to_line_point(const tc_vec3& point) {
    return {
        static_cast<float>(point.x),
        static_cast<float>(point.y),
        static_cast<float>(point.z),
    };
}

tgfx::LinePoint3 transform_line_point(const Mat44f& model, const tc_vec3& point) {
    Vec3 world = model.transform_point(Vec3{point.x, point.y, point.z});
    return {
        static_cast<float>(world.x),
        static_cast<float>(world.y),
        static_cast<float>(world.z),
    };
}

std::array<float, 16> to_tgfx_matrix(const Mat44f& matrix) {
    std::array<float, 16> result{};
    std::memcpy(result.data(), matrix.data, sizeof(matrix.data));
    return result;
}

std::array<float, 4> phase_color(const tc_material_phase* phase) {
    std::array<float, 4> color{1.0f, 1.0f, 1.0f, 1.0f};
    if (!phase) {
        return color;
    }
    tc_material_phase_get_color(phase, &color[0], &color[1], &color[2], &color[3]);
    return color;
}

tc_material_phase* find_phase(tc_material* material, const std::string& phase_mark) {
    if (!material) {
        return nullptr;
    }
    for (size_t i = 0; i < material->phase_count; ++i) {
        if (phase_mark == material->phases[i].phase_mark) {
            return &material->phases[i];
        }
    }
    return nullptr;
}

bool is_direct_line_mode(LineRenderMode mode) {
    return mode == LineRenderMode::WorldBillboard
        || mode == LineRenderMode::ScreenSpace
        || mode == LineRenderMode::WorldTube;
}

bool decode_line_render_mode(int value, LineRenderMode& mode) {
    switch (value) {
        case static_cast<int>(LineRenderMode::WorldBillboard):
        case static_cast<int>(LineRenderMode::ScreenSpace):
        case static_cast<int>(LineRenderMode::WorldMesh):
        case static_cast<int>(LineRenderMode::RawLines):
        case static_cast<int>(LineRenderMode::WorldTube):
            mode = static_cast<LineRenderMode>(value);
            return true;
    }
    return false;
}

bool decode_line_render_mode(uint32_t value, LineRenderMode& mode) {
    if (value > static_cast<uint32_t>(LineRenderMode::WorldTube)) {
        return false;
    }
    return decode_line_render_mode(static_cast<int>(value), mode);
}

bool uses_material_fragment_variant_for_pass(
    LineRenderMode mode,
    const MaterialPipelinePassContract& pass_contract)
{
    if (!pass_contract.uses_material_fragment ||
        pass_contract.required_material_fragment_input.semantics.empty()) {
        return false;
    }
    return mode == LineRenderMode::WorldBillboard
        || mode == LineRenderMode::WorldTube;
}

bool accepts_phase(const std::string& phase_mark, bool cast_shadow) {
    if (phase_mark == "shadow") {
        return cast_shadow;
    }
    return true;
}

TcShader get_line_material_fragment_shader(TcShader original_shader);
TcShader get_line_tube_material_shader(TcShader original_shader, bool cap_variant);

struct TcShaderHash {
    size_t operator()(const TcShader& shader) const {
        return std::hash<uint32_t>()(shader.handle.index)
            ^ (std::hash<uint32_t>()(shader.handle.generation) << 1);
    }
};

struct TcShaderEqual {
    bool operator()(const TcShader& a, const TcShader& b) const {
        return a.handle.index == b.handle.index
            && a.handle.generation == b.handle.generation;
    }
};

struct LineBatchEncoderState {
    std::unique_ptr<tgfx::ScreenSpaceLineRenderer> screen_space_renderer;
    std::unique_ptr<tgfx::WorldSpaceLineRenderer> world_space_renderer;
    std::unique_ptr<tgfx::WorldTubeLineRenderer> world_tube_renderer;
};

static_assert(sizeof(tc_render_item_vec3) == sizeof(tc_vec3),
              "tc_render_item_vec3 must match tc_vec3 storage");
static_assert(alignof(tc_render_item_vec3) == alignof(tc_vec3),
              "tc_render_item_vec3 must match tc_vec3 alignment");

bool encode_line_batch_render_item_tgfx2(
    tgfx::RenderContext2& ctx,
    const tc_render_item& item,
    const RenderItemDrawSubmitRequest& request,
    LineBatchEncoderState& state)
{
    if (item.kind != TC_RENDER_ITEM_KIND_LINE_BATCH) {
        tc::Log::error(
            "[LineRenderer] line encoder received unsupported item kind %u",
            item.kind);
        return false;
    }
    if (!request.draw_context) {
        tc::Log::error("[LineRenderer] cannot encode line batch without draw context");
        return false;
    }

    const RenderContext& context = *request.draw_context;
    const char* phase_mark_c = request.phase_mark
        ? request.phase_mark
        : context.phase.c_str();
    const std::string phase_mark = phase_mark_c ? phase_mark_c : "";
    tc_material_phase* phase = request.material_phase
        ? request.material_phase
        : item.material_phase;

    LineRenderMode mode = LineRenderMode::WorldBillboard;
    if (!decode_line_render_mode(item.payload.line_batch.render_mode, mode)) {
        tc::Log::error(
            "[LineRenderer] cannot encode line batch with invalid render mode %u",
            item.payload.line_batch.render_mode);
        return false;
    }
    if (!is_direct_line_mode(mode)) {
        return false;
    }
    if (!accepts_phase(phase_mark, true)) {
        return false;
    }
    if (!item.payload.line_batch.points || item.payload.line_batch.point_count < 2) {
        return true;
    }

    std::vector<tgfx::LinePoint3> world_points;
    world_points.reserve(item.payload.line_batch.point_count);
    for (size_t i = 0; i < item.payload.line_batch.point_count; ++i) {
        const tc_render_item_vec3& point = item.payload.line_batch.points[i];
        world_points.push_back(transform_line_point(
            context.model,
            tc_vec3{point.x, point.y, point.z}));
    }

    Mat44f view_projection = context.projection * context.view;
    std::array<float, 4> color = phase_color(phase);
    const bool has_item_override_color =
        (item.flags & TC_RENDER_ITEM_FLAG_HAS_OVERRIDE_COLOR) != 0u;
    if (context.has_override_color) {
        color = {
            static_cast<float>(context.override_color.x),
            static_cast<float>(context.override_color.y),
            static_cast<float>(context.override_color.z),
            static_cast<float>(context.override_color.w),
        };
    } else if (has_item_override_color) {
        color = {
            static_cast<float>(item.override_color.x),
            static_cast<float>(item.override_color.y),
            static_cast<float>(item.override_color.z),
            static_cast<float>(item.override_color.w),
        };
    }
    const bool has_override_color = context.has_override_color || has_item_override_color;

    tgfx::ShaderHandle material_fragment_shader{};
    MaterialPipelineShaderBinding tube_body_shader{};
    MaterialPipelineShaderBinding tube_cap_shader{};
    const bool use_material_fragment =
        uses_material_fragment_variant_for_pass(mode, context.pass_contract);
    if (!has_override_color && mode == LineRenderMode::WorldTube
        && use_material_fragment) {
        TcShader material_shader(phase ? phase->shader : tc_shader_handle_invalid());
        TcShader body_variant = get_line_tube_material_shader(material_shader, false);
        TcShader cap_variant = get_line_tube_material_shader(material_shader, true);
        if (!body_variant.is_valid() || !cap_variant.is_valid()) {
            tc::Log::error("[LineRenderer] failed to create line tube material shader variants");
            return false;
        }

        if (!ensure_material_pipeline_shader(
                ctx,
                ctx.device(),
                body_variant.handle,
                "LineRenderer/WorldTubeBody",
                tube_body_shader) ||
            !ensure_material_pipeline_shader(
                ctx,
                ctx.device(),
                cap_variant.handle,
                "LineRenderer/WorldTubeCap",
                tube_cap_shader)) {
            tc::Log::error("[LineRenderer] failed to prepare line tube material shader variants");
            return false;
        }
    } else if (!has_override_color && use_material_fragment) {
        tc_shader* shader = context.current_tc_shader.get();
        if (!shader) {
            tc::Log::error(
                "[LineRenderer] cannot draw line with material fragment: current shader is invalid");
            return false;
        }
        if (!tc_shader_ensure_tgfx2(shader, &ctx.device(), nullptr, &material_fragment_shader)
            || !material_fragment_shader) {
            tc::Log::error(
                "[LineRenderer] failed to compile material fragment shader variant for '%s'",
                shader->name ? shader->name : shader->uuid);
            return false;
        }
    }

    if (mode == LineRenderMode::WorldTube) {
        if (!state.world_tube_renderer) {
            state.world_tube_renderer = std::make_unique<tgfx::WorldTubeLineRenderer>();
        }
        tgfx::WorldTubeLineStyle style;
        style.width = std::max(item.payload.line_batch.width, 0.0f);
        style.color = color;
        style.up_hint = to_line_point(tc_vec3{
            item.payload.line_batch.up_hint.x,
            item.payload.line_batch.up_hint.y,
            item.payload.line_batch.up_hint.z,
        });
        style.sides = std::clamp(item.payload.line_batch.tube_sides, 3, 32);

        tgfx::WorldTubeLineParams params;
        params.view_projection = to_tgfx_matrix(view_projection);
        params.lighting_enabled = !has_override_color;
        params.fragment_shader = material_fragment_shader;
        if (tube_body_shader.shader && tube_cap_shader.shader) {
            params.body_vertex_shader = tube_body_shader.vertex;
            params.body_fragment_shader = tube_body_shader.fragment;
            params.body_shader_layout = tube_body_shader.shader;
            params.cap_vertex_shader = tube_cap_shader.vertex;
            params.cap_fragment_shader = tube_cap_shader.fragment;
            params.cap_shader_layout = tube_cap_shader.shader;
            params.bind_resources =
                [&request, phase](tgfx::RenderContext2& line_ctx, const tc_shader* shader_layout) {
                    RenderItemDrawSubmitRequest line_request = request;
                    line_request.material_phase = phase;
                    bind_render_item_common_resources(line_ctx, shader_layout, line_request);
                };
        }

        state.world_tube_renderer->draw_polyline(ctx, world_points, style, params);
        return true;
    }

    if (mode == LineRenderMode::WorldBillboard) {
        if (!state.world_space_renderer) {
            state.world_space_renderer = std::make_unique<tgfx::WorldSpaceLineRenderer>();
        }
        tgfx::WorldSpaceLineStyle style;
        style.width = std::max(item.payload.line_batch.width, 0.0f);
        style.color = color;
        style.cap = tgfx::LineCapStyle::Round;
        style.join = tgfx::LineJoinStyle::Round;
        style.round_segments = 12;

        tgfx::WorldSpaceLineParams params;
        params.view_projection = to_tgfx_matrix(view_projection);
        params.camera_position = {
            static_cast<float>(context.camera_position.x),
            static_cast<float>(context.camera_position.y),
            static_cast<float>(context.camera_position.z),
        };
        params.lighting_enabled = !has_override_color;
        params.fragment_shader = material_fragment_shader;

        ctx.set_cull(tgfx::CullMode::None);
        state.world_space_renderer->draw_polyline(ctx, world_points, style, params);
        return true;
    }

    if (!state.screen_space_renderer) {
        state.screen_space_renderer = std::make_unique<tgfx::ScreenSpaceLineRenderer>();
    }
    tgfx::ScreenSpaceLineStyle style;
    style.width_px = std::max(item.payload.line_batch.width, 0.0f);
    style.color = color;
    style.cap = tgfx::LineCapStyle::Round;
    style.join = tgfx::LineJoinStyle::Round;
    style.round_segments = 12;

    tgfx::ScreenSpaceLineParams params;
    params.view_projection = to_tgfx_matrix(view_projection);
    params.viewport_width = static_cast<float>(std::max(context.viewport_width, 1));
    params.viewport_height = static_cast<float>(std::max(context.viewport_height, 1));

    ctx.set_cull(tgfx::CullMode::None);
    state.screen_space_renderer->draw_polyline(ctx, world_points, style, params);
    return true;
}

bool line_render_item_draw_encoder(
    tgfx::RenderContext2& ctx,
    const tc_render_item& item,
    const RenderItemDrawSubmitRequest& request,
    void* user_data)
{
    auto* state = static_cast<LineBatchEncoderState*>(user_data);
    if (!state) {
        tc::Log::error("[LineRenderer] line encoder has no state");
        return false;
    }
    return encode_line_batch_render_item_tgfx2(ctx, item, request, *state);
}

void ensure_line_render_item_encoder_registered()
{
    static bool registered = false;
    static LineBatchEncoderState state;
    if (registered) {
        return;
    }

    RenderItemDrawEncoderDesc desc{};
    desc.encode = line_render_item_draw_encoder;
    desc.plan_task_shader = plan_render_item_passthrough_shader;
    desc.user_data = &state;
    desc.debug_name = "LineRenderer";
    desc.capabilities.pass_semantic_mask =
        render_item_pass_semantic_bit(RenderItemPassSemantic::Color)
        | render_item_pass_semantic_bit(RenderItemPassSemantic::Shadow)
        | render_item_pass_semantic_bit(RenderItemPassSemantic::Id);
    desc.capabilities.supported_task_input_mask =
        render_item_task_input_bit(RenderItemTaskInput::DrawContext)
        | render_item_task_input_bit(RenderItemTaskInput::ModelMatrix)
        | render_item_task_input_bit(RenderItemTaskInput::OverrideColor);
    desc.capabilities.required_task_input_mask =
        render_item_task_input_bit(RenderItemTaskInput::DrawContext);
    desc.capabilities.requires_draw_context = true;
    desc.capabilities.consumes_common_resources = true;
    registered = register_render_item_draw_encoder(TC_RENDER_ITEM_KIND_LINE_BATCH, desc);
}

std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual>& line_fragment_shader_cache() {
    static std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual> cache;
    return cache;
}

std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual>& line_tube_body_shader_cache() {
    static std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual> cache;
    return cache;
}

std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual>& line_tube_cap_shader_cache() {
    static std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual> cache;
    return cache;
}

MaterialPipelinePassContract legacy_line_material_pass_contract()
{
    MaterialPipelinePassContract contract;
    contract.debug_name = "legacy_line_material";
    contract.required_material_fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.uses_material_fragment = true;
    return contract;
}

MaterialPipelinePassContract legacy_line_auxiliary_pass_contract(const char* debug_name)
{
    MaterialPipelinePassContract contract;
    contract.debug_name = debug_name ? debug_name : "legacy_line_auxiliary";
    contract.required_material_fragment_input = MaterialFragmentInterface{};
    contract.uses_material_fragment = true;
    return contract;
}

MaterialPipelinePassContract legacy_line_pass_contract_for_phase(const std::string& phase_mark)
{
    // Compatibility adapter for old Drawable::override_shader callers. Pass-owned
    // render code must provide ShaderOverrideContext::pass_contract explicitly so
    // material-fragment variant intent does not depend on phase_mark strings.
    if (phase_mark == "shadow") {
        return legacy_line_auxiliary_pass_contract("shadow");
    }
    if (phase_mark == "pick") {
        return legacy_line_auxiliary_pass_contract("pick");
    }
    return legacy_line_material_pass_contract();
}

TcShader get_line_material_fragment_shader(TcShader original_shader) {
    if (!original_shader.is_valid()) {
        return TcShader();
    }
    if (original_shader.variant_op() == TC_SHADER_VARIANT_LINE_MATERIAL_FRAGMENT) {
        return original_shader;
    }

    auto& cache = line_fragment_shader_cache();
    auto it = cache.find(original_shader);
    if (it != cache.end()) {
        TcShader& cached = it->second;
        if (!cached.variant_is_stale()) {
            return cached;
        }
        cache.erase(it);
    }

    const char* fragment_source = original_shader.fragment_source();
    if (!fragment_source || fragment_source[0] == '\0') {
        tc::Log::error(
            "[LineRenderer] cannot create line material shader variant for '%s': fragment source is empty",
            original_shader.name()
        );
        return TcShader();
    }

    std::string variant_name = std::string(original_shader.name()) + "_LineFragment";
    char variant_uuid[40];
    tc_shader_make_variant_uuid(
        variant_uuid,
        sizeof(variant_uuid),
        original_shader.uuid(),
        TC_SHADER_VARIANT_LINE_MATERIAL_FRAGMENT
    );

    tc_shader_handle handle = tc_shader_from_sources(
        nullptr,
        fragment_source,
        nullptr,
        variant_name.c_str(),
        original_shader.source_path(),
        variant_uuid
    );
    if (tc_shader_handle_is_invalid(handle)) {
        tc::Log::error(
            "[LineRenderer] failed to create line material shader variant for '%s'",
            original_shader.name()
        );
        return TcShader();
    }

    TcShader variant(handle);
    variant.set_features(original_shader.features());

    tc_shader* original_raw = original_shader.get();
    tc_shader* variant_raw = variant.get();
    if (original_raw && variant_raw) {
        tc_shader_set_material_ubo_layout(
            variant_raw,
            original_raw->material_ubo_entries,
            original_raw->material_ubo_entry_count,
            original_raw->material_ubo_block_size
        );
    }

    variant.set_variant_info(original_shader, TC_SHADER_VARIANT_LINE_MATERIAL_FRAGMENT);
    cache[original_shader] = variant;
    return variant;
}

TcShader get_line_tube_material_shader(TcShader original_shader, bool cap_variant) {
    if (!original_shader.is_valid()) {
        return TcShader();
    }
    const tc_shader_variant_op variant_op = cap_variant
        ? TC_SHADER_VARIANT_LINE_TUBE_CAP
        : TC_SHADER_VARIANT_LINE_TUBE_BODY;
    if (original_shader.variant_op() == variant_op) {
        return original_shader;
    }

    auto& cache = cap_variant
        ? line_tube_cap_shader_cache()
        : line_tube_body_shader_cache();
    auto it = cache.find(original_shader);
    if (it != cache.end()) {
        TcShader& cached = it->second;
        if (!cached.variant_is_stale()) {
            return cached;
        }
        cache.erase(it);
    }

    const char* fragment_source = original_shader.fragment_source();
    if (!fragment_source || fragment_source[0] == '\0') {
        tc::Log::error(
            "[LineRenderer] cannot create line tube material shader variant for '%s': fragment source is empty",
            original_shader.name()
        );
        return TcShader();
    }

    const char* vertex_uuid = cap_variant
        ? "termin-engine-world-tube-line-cap"
        : "termin-engine-world-tube-line";
    std::string vertex_source =
        tgfx::load_builtin_shader_stage_source_from_catalog(vertex_uuid, "vertex");
    if (vertex_source.empty()) {
        tc::Log::error(
            "[LineRenderer] failed to load line tube vertex shader template '%s'",
            vertex_uuid
        );
        return TcShader();
    }

    std::string variant_name = std::string(original_shader.name())
        + (cap_variant ? "_LineTubeCap" : "_LineTubeBody");
    char variant_uuid[40];
    tc_shader_make_variant_uuid(
        variant_uuid,
        sizeof(variant_uuid),
        original_shader.uuid(),
        variant_op
    );

    tc_shader* original_raw = original_shader.get();
    const char* fragment_entry = original_raw ? original_raw->fragment_entry : nullptr;
    if (!fragment_entry || fragment_entry[0] == '\0') {
        fragment_entry = "main";
    }

    const tc_shader_create_desc shader_desc = {
        {
            vertex_source.c_str(),
            fragment_source,
            nullptr,
            variant_name.c_str(),
            original_shader.source_path(),
            cap_variant ? "vs_cap_main" : "vs_main",
            fragment_entry,
            nullptr
        },
        variant_uuid,
        TC_SHADER_LANGUAGE_SLANG,
        TC_SHADER_ARTIFACT_REQUIRED
    };
    tc_shader_handle handle = tc_shader_from_sources_desc(&shader_desc);
    if (tc_shader_handle_is_invalid(handle)) {
        tc::Log::error(
            "[LineRenderer] failed to create line tube material shader variant for '%s'",
            original_shader.name()
        );
        return TcShader();
    }

    TcShader variant(handle);
    variant.set_features(original_shader.features());
    variant.set_language(TC_SHADER_LANGUAGE_SLANG);
    variant.set_artifact_policy(TC_SHADER_ARTIFACT_REQUIRED);

    tc_shader* variant_raw = variant.get();
    if (original_raw && variant_raw) {
        // Slang line-tube variants get material field layout from their
        // shaderc sidecar after compilation. Do not copy parser-authored
        // legacy material_ubo_entries from the source material shader.
        tc_shader_set_material_ubo_layout(variant_raw, nullptr, 0, 0);
    }

    variant.set_variant_info(original_shader, variant_op);
    cache[original_shader] = variant;
    return variant;
}

} // namespace

bool emit_line_batch_render_items(
    tc_component* component,
    const tc_render_item_collect_context& context,
    tc_render_item_sink& sink,
    const LineBatchRenderItemDesc& desc)
{
    if (!component) {
        tc::Log::error("[LineBatchRenderItem] cannot emit from null component");
        return false;
    }
    if (!sink.emit) {
        tc::Log::error("[LineBatchRenderItem] cannot emit with null sink");
        return false;
    }
    if (!context.phase_mark || context.phase_mark[0] == '\0') {
        tc::Log::error("[LineBatchRenderItem] cannot emit without phase mark");
        return false;
    }
    if (!desc.points || desc.point_count < 2) {
        return true;
    }

    const std::string phase_mark = context.phase_mark;
    if (!accepts_phase(phase_mark, desc.cast_shadow)) {
        return true;
    }

    LineRenderMode mode = LineRenderMode::WorldBillboard;
    if (!decode_line_render_mode(static_cast<int>(desc.render_mode), mode)) {
        tc::Log::error(
            "[LineBatchRenderItem] cannot emit line batch with invalid render mode %d",
            static_cast<int>(desc.render_mode));
        return false;
    }
    if (!is_direct_line_mode(mode)) {
        tc::Log::error(
            "[LineBatchRenderItem] render mode %d is not a direct line batch mode",
            static_cast<int>(mode));
        return false;
    }

    tc_material* raw = desc.material.get();
    if (!raw) {
        return true;
    }

    const bool allow_missing_material_phase =
        (context.flags & TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE) != 0u;
    bool emitted = false;

    auto emit_phase = [&](tc_material_phase* phase) -> bool {
        if (!phase && !allow_missing_material_phase) {
            return true;
        }

        tc_render_item item{};
        item.kind = TC_RENDER_ITEM_KIND_LINE_BATCH;
        item.flags = TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX;
        item.component = component;
        item.geometry_id = desc.geometry_id;
        item.material_phase = phase;
        item.material = tc_material_handle_invalid();
        item.material_phase_index = SIZE_MAX;
        item.payload.line_batch.points =
            reinterpret_cast<const tc_render_item_vec3*>(desc.points);
        item.payload.line_batch.point_count = desc.point_count;
        item.payload.line_batch.width = desc.width;
        item.payload.line_batch.render_mode = static_cast<uint32_t>(mode);
        item.payload.line_batch.up_hint = {
            desc.up_hint.x,
            desc.up_hint.y,
            desc.up_hint.z,
        };
        item.payload.line_batch.tube_sides = desc.tube_sides;

        if (phase) {
            item.flags |= TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE;
            tc_material_find_phase_ref(phase, &item.material, &item.material_phase_index);
        }
        if (desc.has_override_color) {
            item.flags |= TC_RENDER_ITEM_FLAG_HAS_OVERRIDE_COLOR;
            item.override_color = desc.override_color;
        }

        std::memcpy(item.model_matrix, desc.model_matrix.data, sizeof(float) * 16);
        emitted = true;
        return sink.emit(&item, sink.user_data);
    };

    bool found_shadow_phase = false;
    for (size_t i = 0; i < raw->phase_count; ++i) {
        tc_material_phase* phase = &raw->phases[i];
        const std::string draw_phase_mark = phase->phase_mark;
        if (!accepts_phase(draw_phase_mark, desc.cast_shadow)) {
            continue;
        }
        if (draw_phase_mark == "shadow") {
            found_shadow_phase = true;
        }
        if (phase_mark == draw_phase_mark && !emit_phase(phase)) {
            return false;
        }
    }

    if (desc.cast_shadow && phase_mark == "shadow" && !found_shadow_phase) {
        if (!emit_phase(find_phase(desc.shadow_fallback_material.get(), "shadow"))) {
            return false;
        }
    }

    if (!emitted && allow_missing_material_phase) {
        return emit_phase(nullptr);
    }

    return true;
}

TcShader override_line_batch_shader(
    const ShaderOverrideContext& context,
    LineRenderMode mode,
    bool cast_shadow)
{
    TcShader original_shader = context.original_shader;
    if (!uses_material_fragment_variant_for_pass(mode, context.pass_contract)
        || !accepts_phase(context.phase_mark, cast_shadow)) {
        return original_shader;
    }

    if (mode == LineRenderMode::WorldTube) {
        TcShader variant = get_line_tube_material_shader(original_shader, false);
        return variant.is_valid() ? variant : original_shader;
    }

    TcShader variant = get_line_material_fragment_shader(original_shader);
    return variant.is_valid() ? variant : original_shader;
}

void collect_line_batch_shader_usages(
    const ShaderOverrideContext& context,
    LineRenderMode mode,
    bool cast_shadow,
    const std::function<void(TcShader)>& emit)
{
    if (!emit) {
        return;
    }

    TcShader original_shader = context.original_shader;
    if (original_shader.is_valid()) {
        emit(original_shader);
    }

    if (!uses_material_fragment_variant_for_pass(mode, context.pass_contract)
        || !accepts_phase(context.phase_mark, cast_shadow)) {
        return;
    }

    if (mode == LineRenderMode::WorldTube) {
        TcShader body = get_line_tube_material_shader(original_shader, false);
        if (body.is_valid()) {
            emit(body);
        }
        TcShader cap = get_line_tube_material_shader(original_shader, true);
        if (cap.is_valid()) {
            emit(cap);
        }
        return;
    }

    TcShader variant = get_line_material_fragment_shader(original_shader);
    if (variant.is_valid()) {
        emit(variant);
    }
}

LineRenderer::LineRenderer(const char* type_name)
    : Component(type_name)
{
    install_drawable_vtable(&_c);
}

void LineRenderer::register_type() {
    ensure_line_render_item_encoder_registered();
    register_component_type<LineRenderer>("LineRenderer", "Component");
    ComponentRegistry::instance().set_category("LineRenderer", "Rendering");
    tc::InspectRegistry::instance().add_with_callbacks<LineRenderer, TcMaterial>(
        "LineRenderer",
        "material",
        "Material",
        "tc_material",
        [](LineRenderer* self) -> TcMaterial& { return self->material; },
        [](LineRenderer* self, const TcMaterial& value) { self->set_material(value); }
    );
    tc::InspectRegistry::instance().add_with_callbacks<LineRenderer, float>(
        "LineRenderer",
        "width",
        "Width",
        "float",
        [](LineRenderer* self) -> float& { return self->width; },
        [](LineRenderer* self, const float& value) { self->set_width(value); },
        0.001,
        10.0,
        0.01
    );
    tc::InspectAccessorFieldChoicesRegistrar<LineRenderer, int>(
        "LineRenderer",
        "render_mode",
        "Render Mode",
        "enum",
        [](LineRenderer* self) -> int { return static_cast<int>(self->render_mode); },
        [](LineRenderer* self, int value) { self->set_render_mode(static_cast<LineRenderMode>(value)); },
        {
            {"0", "World Billboard"},
            {"1", "Screen Space"},
            {"2", "World Mesh"},
            {"3", "Raw Lines"},
            {"4", "World Tube"},
        }
    );
    tc::InspectRegistry::instance().add_with_callbacks<LineRenderer, bool>(
        "LineRenderer",
        "raw_lines",
        "Raw Lines",
        "bool",
        [](LineRenderer* self) -> bool& { return self->raw_lines; },
        [](LineRenderer* self, const bool& value) { self->set_raw_lines(value); }
    );
    tc::InspectRegistry::instance().add_with_callbacks<LineRenderer, bool>(
        "LineRenderer",
        "cast_shadow",
        "Cast Shadow",
        "bool",
        [](LineRenderer* self) -> bool& { return self->cast_shadow; },
        [](LineRenderer* self, const bool& value) { self->set_cast_shadow(value); }
    );
    tc::InspectRegistry::instance().add_with_callbacks<LineRenderer, tc_vec3>(
        "LineRenderer",
        "up_hint",
        "Up Hint",
        "vec3",
        [](LineRenderer* self) -> tc_vec3& { return self->up_hint; },
        [](LineRenderer* self, const tc_vec3& value) { self->set_up_hint(value); }
    );
    tc::InspectRegistry::instance().add_with_callbacks<LineRenderer, int>(
        "LineRenderer",
        "tube_sides",
        "Tube Sides",
        "int",
        [](LineRenderer* self) -> int& { return self->tube_sides; },
        [](LineRenderer* self, const int& value) { self->set_tube_sides(value); },
        3,
        32,
        1
    );
    tc::InspectAccessorFieldRegistrar<LineRenderer, std::vector<tc_vec3>>(
        "LineRenderer",
        "points",
        "Positions",
        "list[vec3]",
        [](LineRenderer* self) { return self->points(); },
        [](LineRenderer* self, std::vector<tc_vec3> value) { self->set_points(std::move(value)); }
    );
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
    tc_shader_handle shader_handle =
        tgfx::register_builtin_shader_from_catalog(DEFAULT_LINE_SHADER_UUID);
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
    tc_material_phase_set_color(phase, 1.0f, 1.0f, 1.0f, 1.0f);
    {
        const float color[4] = {1.0f, 1.0f, 1.0f, 1.0f};
        tc_material_phase_set_uniform(phase, "u_color", TC_UNIFORM_VEC4, color);
    }

    tc_material_phase* shadow_phase = mat.add_phase(shader_handle, "shadow", 0);
    if (!shadow_phase) {
        tc::Log::error("[LineRenderer] failed to create default shadow material phase");
        return mat;
    }
    shadow_phase->state = state;
    tc_material_phase_set_color(shadow_phase, 1.0f, 1.0f, 1.0f, 1.0f);
    {
        const float color[4] = {1.0f, 1.0f, 1.0f, 1.0f};
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

bool LineRenderer::effective_render_mode(LineRenderMode& mode) const {
    if (raw_lines) {
        mode = LineRenderMode::RawLines;
        return true;
    }
    if (decode_line_render_mode(static_cast<int>(render_mode), mode)) {
        return true;
    }
    tc::Log::error("[LineRenderer] invalid render mode %d",
                   static_cast<int>(render_mode));
    return false;
}

void LineRenderer::set_points(const std::vector<tc_vec3>& points) {
    points_ = points;
    dirty_ = true;
}

void LineRenderer::set_points(std::vector<tc_vec3>&& points) {
    points_ = std::move(points);
    dirty_ = true;
}

void LineRenderer::clear_points() {
    points_.clear();
    dirty_ = true;
}

void LineRenderer::add_point(const tc_vec3& point) {
    points_.push_back(point);
    dirty_ = true;
}

void LineRenderer::set_width(float value) {
    width = value;
    dirty_ = true;
}

void LineRenderer::set_render_mode(LineRenderMode value) {
    LineRenderMode decoded = LineRenderMode::WorldBillboard;
    if (!decode_line_render_mode(static_cast<int>(value), decoded)) {
        tc::Log::error("[LineRenderer] rejected invalid render mode %d",
                       static_cast<int>(value));
        return;
    }
    render_mode = value;
    dirty_ = true;
}

void LineRenderer::set_raw_lines(bool value) {
    raw_lines = value;
    dirty_ = true;
}

void LineRenderer::set_cast_shadow(bool value) {
    cast_shadow = value;
}

void LineRenderer::set_up_hint(const tc_vec3& value) {
    up_hint = value;
    dirty_ = true;
}

void LineRenderer::set_tube_sides(int value) {
    tube_sides = std::clamp(value, 3, 32);
    dirty_ = true;
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

void LineRenderer::rebuild_geometry() {
    mesh_ = TcMesh();
    if (points_.size() < 2) {
        dirty_ = false;
        return;
    }

    tc_vertex_layout layout = tc_vertex_layout_pos();
    LineRenderMode mode = LineRenderMode::WorldBillboard;
    if (!effective_render_mode(mode)) {
        dirty_ = false;
        return;
    }

    if (is_direct_line_mode(mode)) {
        dirty_ = false;
        return;
    }

    if (mode == LineRenderMode::RawLines) {
        std::vector<float> vertices;
        vertices.reserve(points_.size() * 3);
        for (const tc_vec3& point : points_) {
            vertices.push_back(static_cast<float>(point.x));
            vertices.push_back(static_cast<float>(point.y));
            vertices.push_back(static_cast<float>(point.z));
        }

        std::vector<uint32_t> indices;
        indices.reserve((points_.size() - 1) * 2);
        for (uint32_t i = 1; i < static_cast<uint32_t>(points_.size()); ++i) {
            indices.push_back(i - 1);
            indices.push_back(i);
        }

        TcMeshCreateInfo create_info;
        create_info.data = TcMeshInterleavedDataView{
            vertices.data(),
            points_.size(),
            indices.data(),
            indices.size(),
            &layout};
        create_info.name = "line_renderer_raw";
        create_info.draw_mode = TC_DRAW_LINES;
        mesh_ = TcMesh::from_interleaved(create_info);
    } else {
        std::vector<tgfx::LinePoint3> line_points;
        line_points.reserve(points_.size());
        for (const tc_vec3& point : points_) {
            line_points.push_back(to_line_point(point));
        }

        tgfx::LineStyle style;
        style.width = std::max(width, 0.0f);
        style.up_hint = to_line_point(up_hint);
        style.cap = tgfx::LineCapStyle::Round;
        style.join = tgfx::LineJoinStyle::Round;
        style.round_segments = 8;
        tgfx::LineMesh line_mesh = tgfx::build_line_mesh(line_points, style);
        if (line_mesh.empty()) {
            dirty_ = false;
            return;
        }

        std::vector<float> vertices;
        vertices.reserve(line_mesh.vertices.size() * 3);
        for (const tgfx::LineVertex& vertex : line_mesh.vertices) {
            vertices.push_back(vertex.position.x);
            vertices.push_back(vertex.position.y);
            vertices.push_back(vertex.position.z);
        }

        TcMeshCreateInfo create_info;
        create_info.data = TcMeshInterleavedDataView{
            vertices.data(),
            line_mesh.vertices.size(),
            line_mesh.indices.data(),
            line_mesh.indices.size(),
            &layout};
        create_info.name = "line_renderer";
        create_info.draw_mode = TC_DRAW_TRIANGLES;
        mesh_ = TcMesh::from_interleaved(create_info);
    }

    if (!mesh_.is_valid()) {
        tc::Log::error("[LineRenderer] failed to rebuild line mesh");
    }
    dirty_ = false;
}

void LineRenderer::ensure_geometry() {
    if (dirty_) {
        rebuild_geometry();
    }
}

tc_mesh* LineRenderer::current_mesh_ptr() const {
    const_cast<LineRenderer*>(this)->ensure_geometry();
    return mesh_.get();
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
    dirty_ = true;
}

std::set<std::string> LineRenderer::get_phase_marks() const {
    std::set<std::string> marks;
    TcMaterial mat = effective_material();
    tc_material* raw = mat.get();
    if (!raw) {
        return marks;
    }
    LineRenderMode mode = LineRenderMode::WorldBillboard;
    if (!effective_render_mode(mode)) {
        return marks;
    }
    for (size_t i = 0; i < raw->phase_count; ++i) {
        const std::string phase_mark = raw->phases[i].phase_mark;
        if (!accepts_phase(phase_mark, cast_shadow)) {
            continue;
        }
        marks.insert(phase_mark);
    }
    if (cast_shadow) {
        marks.insert("shadow");
    }
    return marks;
}

TcShader LineRenderer::override_shader(
    const std::string& phase_mark,
    int geometry_id,
    TcShader original_shader
) {
    ShaderOverrideContext context;
    context.phase_mark = phase_mark;
    context.geometry_id = geometry_id;
    context.original_shader = original_shader;
    context.pass_contract = legacy_line_pass_contract_for_phase(phase_mark);
    return override_shader_with_context(context);
}

TcShader LineRenderer::override_shader_with_context(
    const ShaderOverrideContext& context
) {
    LineRenderMode mode = LineRenderMode::WorldBillboard;
    if (!effective_render_mode(mode)) {
        return context.original_shader;
    }
    return override_line_batch_shader(context, mode, cast_shadow);
}

void LineRenderer::collect_shader_usages(
    const std::string& phase_mark,
    int geometry_id,
    TcShader original_shader,
    const std::function<void(TcShader)>& emit
) {
    ShaderOverrideContext context;
    context.phase_mark = phase_mark;
    context.geometry_id = geometry_id;
    context.original_shader = original_shader;
    context.pass_contract = legacy_line_pass_contract_for_phase(phase_mark);
    collect_shader_usages_with_context(context, emit);
}

void LineRenderer::collect_shader_usages_with_context(
    const ShaderOverrideContext& context,
    const std::function<void(TcShader)>& emit
) {
    LineRenderMode mode = LineRenderMode::WorldBillboard;
    if (!effective_render_mode(mode)) {
        if (emit && context.original_shader.is_valid()) {
            emit(context.original_shader);
        }
        return;
    }
    collect_line_batch_shader_usages(context, mode, cast_shadow, emit);
}

bool LineRenderer::collect_render_items(
    const tc_render_item_collect_context& context,
    tc_render_item_sink& sink)
{
    if (!context.phase_mark || points_.size() < 2) {
        return true;
    }

    const std::string phase_mark = context.phase_mark;
    if (!accepts_phase(phase_mark, cast_shadow)) {
        return true;
    }

    LineRenderMode mode = LineRenderMode::WorldBillboard;
    if (!effective_render_mode(mode)) {
        return true;
    }
    TcMaterial mat = effective_material();
    tc_material* raw = mat.get();
    if (!raw) {
        return true;
    }

    const bool allow_missing_material_phase =
        (context.flags & TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE) != 0u;
    bool emitted = false;

    if (!is_direct_line_mode(mode)) {
        tc_mesh* mesh = current_mesh_ptr();
        if (!mesh) {
            return true;
        }
        if (mesh->submesh_count == 0 && !tc_mesh_ensure_default_submesh(mesh)) {
            tc::Log::error("[LineRenderer] cannot emit mesh RenderItem: failed to create default submesh");
            return false;
        }
        const tc_submesh* submesh = tc_mesh_get_submesh(mesh, 0);
        if (!submesh || submesh->index_count == 0) {
            return true;
        }

        auto emit_mesh_phase = [&](tc_material_phase* phase) -> bool {
            if (!phase && !allow_missing_material_phase) {
                return true;
            }

            tc_render_item item{};
            item.kind = TC_RENDER_ITEM_KIND_MESH;
            item.flags = TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX;
            item.component = this->tc_component_ptr();
            item.geometry_id = 0;
            item.material_phase = phase;
            item.material = tc_material_handle_invalid();
            item.material_phase_index = SIZE_MAX;
            if (phase) {
                item.flags |= TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE;
                tc_material_find_phase_ref(phase, &item.material, &item.material_phase_index);
            }
            Mat44f model = get_model_matrix(entity());
            std::memcpy(item.model_matrix, model.data, sizeof(float) * 16);
            item.payload.mesh.mesh = mesh;
            item.payload.mesh.mesh_handle = mesh_.handle;
            if (tc_mesh_handle_is_invalid(item.payload.mesh.mesh_handle)) {
                item.payload.mesh.mesh_handle = tc_mesh_find(mesh->header.uuid);
            }
            if (tc_mesh_handle_is_invalid(item.payload.mesh.mesh_handle)) {
                tc::Log::error("[LineRenderer] cannot emit mesh RenderItem: mesh has no stable registry handle");
                return false;
            }
            item.payload.mesh.submesh_index = 0;
            emitted = true;
            return sink.emit(&item, sink.user_data);
        };

        bool found_shadow_phase = false;
        for (size_t i = 0; i < raw->phase_count; ++i) {
            tc_material_phase* phase = &raw->phases[i];
            const std::string draw_phase_mark = phase->phase_mark;
            if (!accepts_phase(draw_phase_mark, cast_shadow)) {
                continue;
            }
            if (draw_phase_mark == "shadow") {
                found_shadow_phase = true;
            }
            if (phase_mark == draw_phase_mark && !emit_mesh_phase(phase)) {
                return false;
            }
        }

        if (cast_shadow && phase_mark == "shadow" && !found_shadow_phase) {
            TcMaterial fallback = default_material();
            if (!emit_mesh_phase(find_phase(fallback.get(), "shadow"))) {
                return false;
            }
        }

        if (!emitted && allow_missing_material_phase) {
            return emit_mesh_phase(nullptr);
        }

        return true;
    }

    LineBatchRenderItemDesc desc;
    desc.points = points_.data();
    desc.point_count = points_.size();
    desc.material = mat;
    desc.shadow_fallback_material = default_material();
    desc.width = width;
    desc.render_mode = mode;
    desc.cast_shadow = cast_shadow;
    desc.up_hint = up_hint;
    desc.tube_sides = tube_sides;
    desc.geometry_id = 0;
    desc.model_matrix = get_model_matrix(entity());
    return emit_line_batch_render_items(this->tc_component_ptr(), context, sink, desc);
}

bool LineRenderer::encode_render_item_tgfx2(
    tgfx::RenderContext2& ctx2,
    const tc_render_item& item,
    const RenderItemDrawSubmitRequest& request)
{
    static LineBatchEncoderState state;
    return encode_line_batch_render_item_tgfx2(ctx2, item, request, state);
}

TcMesh LineRenderer::get_mesh() {
    ensure_geometry();
    return mesh_;
}

} // namespace termin
