#include <algorithm>
#include <cstdint>
#include <set>

#include <tcbase/tc_log.hpp>

#include <termin/render/geometry_pass_base.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/render/material_pipeline_shader_assembler.hpp>

namespace termin {

namespace {

tc_material_phase* resolve_render_item_material_phase(const tc_render_item& item) {
    if (!tc_material_handle_is_invalid(item.material) &&
        item.material_phase_index != SIZE_MAX) {
        tc_material* material = tc_material_get(item.material);
        if (material && item.material_phase_index < material->phase_count) {
            return &material->phases[item.material_phase_index];
        }
    }
    return item.material_phase;
}

} // anonymous namespace

GeometryPassBase::GeometryPassBase(
    const std::string& name,
    const std::string& input,
    const std::string& output
) : input_res(input)
  , output_res(output) {
    set_pass_name(name);
}

std::vector<std::string> GeometryPassBase::get_internal_symbols() const {
    return entity_names;
}

std::set<const char*> GeometryPassBase::compute_reads() const {
    return {input_res.c_str()};
}

std::set<const char*> GeometryPassBase::compute_writes() const {
    return {output_res.c_str()};
}

std::vector<std::pair<std::string, std::string>> GeometryPassBase::get_inplace_aliases() const {
    return {{input_res, output_res}};
}

void GeometryPassBase::destroy() {
}

CameraComponent* GeometryPassBase::find_camera_by_name(tc_scene_handle scene, const std::string& name) const {
    if (name.empty() || !tc_scene_handle_valid(scene)) {
        return nullptr;
    }

    tc_entity_id eid = tc_scene_find_entity_by_name(scene, name.c_str());
    if (!tc_entity_id_valid(eid)) {
        return nullptr;
    }

    Entity ent(tc_scene_entity_pool(scene), eid);
    return ent.get_component<CameraComponent>();
}

std::optional<std::string> GeometryPassBase::fbo_format() const {
    return std::nullopt;
}

bool GeometryPassBase::uses_material_phase_shader_override() const {
    return false;
}

bool GeometryPassBase::entity_filter(const Entity& ent) const {
    (void)ent;
    return true;
}

int GeometryPassBase::get_pick_id(const Entity& ent) const {
    (void)ent;
    return 0;
}

void GeometryPassBase::collect_shader_usages(
    tc_scene_handle scene,
    const std::function<void(TcShader)>& emit
) const {
    if (!emit) {
        return;
    }
    if (!tc_scene_handle_valid(scene)) {
        tc::Log::error(
            "[GeometryPassBase] pass '%s' cannot collect shader usages for invalid scene",
            get_pass_name().c_str());
        return;
    }

    const char* collect_phase_mark = phase_mark();
    if (!collect_phase_mark || collect_phase_mark[0] == '\0') {
        tc::Log::error(
            "[GeometryPassBase] pass '%s' has empty phase mark; shader usage collection requires an explicit phase",
            get_pass_name().c_str());
        return;
    }

    tc_shader_handle base_shader = shader_usage_base_shader();
    if (tc_shader_handle_is_invalid(base_shader)) {
        tc::Log::error(
            "[GeometryPassBase] pass '%s' cannot collect shader usages without a valid base shader",
            get_pass_name().c_str());
        return;
    }

    struct UsageContext {
    public:
        const GeometryPassBase* pass = nullptr;
        const std::function<void(TcShader)>* emit = nullptr;
        tc_shader_handle base_shader = tc_shader_handle_invalid();
        MaterialPipelinePassContract pass_contract;
        RenderItemPassSemantic pass_semantic = RenderItemPassSemantic::Color;
        const char* phase_mark = nullptr;
        std::string pass_name;
    };

    auto callback = [](tc_component* c, void* user_data) -> bool {
        auto* ctx = static_cast<UsageContext*>(user_data);
        if (!ctx || !ctx->pass || !ctx->emit || !c) {
            return true;
        }

        Entity ent(c->owner);
        if (!ctx->pass->entity_filter(ent)) {
            return true;
        }

        tc_render_item_collect_context item_context{};
        item_context.phase_mark = ctx->phase_mark;
        item_context.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
        item_context.layer_mask = UINT64_MAX;
        item_context.render_category_mask = UINT64_MAX;
        item_context.pass_semantic = static_cast<uint32_t>(ctx->pass_semantic);
        item_context.debug_pass_name = ctx->pass_name.c_str();
        item_context.pass_contract = &ctx->pass_contract;

        RenderItemCollection items;
        if (!collect_drawable_render_items(c, item_context, items)) {
            return true;
        }

        for (const tc_render_item& item : items.items) {
            if (!render_item_encoder_supports_pass(item.kind, ctx->pass_semantic)) {
                continue;
            }

            tc_shader_handle original_shader = ctx->base_shader;
            if (ctx->pass->uses_material_phase_shader_override()) {
                tc_material_phase* phase = resolve_render_item_material_phase(item);
                if (phase && !tc_shader_handle_is_invalid(phase->shader)) {
                    original_shader = phase->shader;
                }
            }

            ShaderOverrideContext override_context;
            override_context.phase_mark = ctx->phase_mark;
            override_context.geometry_id = item.geometry_id;
            override_context.original_shader = TcShader(original_shader);
            override_context.pass_contract = ctx->pass_contract;
            collect_drawable_shader_usages_with_context(c, override_context, *ctx->emit);
        }
        return true;
    };

    UsageContext context{
        this,
        &emit,
        base_shader,
        shader_pass_contract(),
        render_item_pass_semantic(),
        collect_phase_mark,
        get_pass_name()};

    tc_scene_foreach_drawable(scene, callback, &context, TC_SCENE_FILTER_NONE, 0);
}

void GeometryPassBase::collect_draw_calls(
    tc_scene_handle scene,
    uint64_t layer_mask,
    uint64_t render_category_mask,
    tc_shader_handle base_shader
) const {
    cached_draw_calls_.clear();
    cached_render_items_.clear();

    if (!tc_scene_handle_valid(scene)) {
        return;
    }

    const char* collect_phase_mark = phase_mark();
    if (!collect_phase_mark || collect_phase_mark[0] == '\0') {
        tc::Log::error(
            "[GeometryPassBase] pass '%s' has empty phase mark; geometry collection requires an explicit phase",
            get_pass_name().c_str());
        return;
    }

    struct CollectContext {
    public:
        const GeometryPassBase* pass = nullptr;
        std::vector<DrawCall>* draw_calls = nullptr;
        RenderItemCollection* render_items = nullptr;
        tc_shader_handle base_shader = tc_shader_handle_invalid();
        MaterialPipelinePassContract pass_contract;
        RenderItemPassSemantic pass_semantic = RenderItemPassSemantic::Color;
        const char* phase_mark = nullptr;
        RenderContext* render_context = nullptr;
        std::string pass_name;
    };

    auto callback = [](tc_component* c, void* user_data) -> bool {
        auto* ctx = static_cast<CollectContext*>(user_data);
        Entity ent(c->owner);

        if (!ctx->pass->entity_filter(ent)) {
            return true;
        }

        tc_render_item_collect_context item_context{};
        item_context.phase_mark = ctx->phase_mark;
        item_context.flags = TC_RENDER_ITEM_COLLECT_FLAG_ALLOW_MISSING_MATERIAL_PHASE;
        item_context.layer_mask = ctx->render_context
            ? ctx->render_context->layer_mask
            : UINT64_MAX;
        item_context.render_category_mask = ctx->render_context
            ? ctx->render_context->render_category_mask
            : UINT64_MAX;
        item_context.pass_semantic = static_cast<uint32_t>(ctx->pass_semantic);
        item_context.debug_pass_name = ctx->pass_name.c_str();
        item_context.pass_contract = &ctx->pass_contract;
        item_context.camera = ctx->render_context
            ? ctx->render_context->camera
            : nullptr;

        const size_t first_item_index = ctx->render_items
            ? ctx->render_items->items.size()
            : 0u;
        if (!ctx->render_items) {
            tc::Log::error(
                "[GeometryPassBase] pass '%s' has no render item storage",
                ctx->pass->get_pass_name().c_str());
            return true;
        }
        if (!collect_drawable_render_items(c, item_context, *ctx->render_items)) {
            return true;
        }

        const int pick_id = ctx->pass->get_pick_id(ent);
        for (size_t item_index = first_item_index;
             item_index < ctx->render_items->items.size();
             ++item_index) {
            const tc_render_item& item = ctx->render_items->items[item_index];
            if (!render_item_encoder_supports_pass(item.kind, ctx->pass_semantic)) {
                continue;
            }

            tc_shader_handle original_shader = ctx->base_shader;
            tc_material_phase* selected_phase = nullptr;
            if (ctx->pass->uses_material_phase_shader_override()) {
                selected_phase = resolve_render_item_material_phase(item);
                if (selected_phase &&
                    !tc_shader_handle_is_invalid(selected_phase->shader)) {
                    original_shader = selected_phase->shader;
                }
            }

            ShaderOverrideContext override_context;
            override_context.phase_mark = ctx->phase_mark;
            override_context.geometry_id = item.geometry_id;
            override_context.original_shader = TcShader(original_shader);
            override_context.pass_contract = ctx->pass_contract;
            tc_shader_handle final_shader =
                override_drawable_shader(c, override_context).handle;

            DrawCall dc;
            dc.entity = ent;
            dc.component = c;
            dc.final_shader = final_shader;
            dc.item = item;
            dc.geometry_id = item.geometry_id;
            dc.pick_id = pick_id;
            if (selected_phase) {
                dc.material_phase = selected_phase;
                dc.material = item.material;
                dc.phase_index = item.material_phase_index;
            }
            ctx->draw_calls->push_back(dc);
        }
        return true;
    };

    RenderContext render_context;
    render_context.phase = collect_phase_mark;
    render_context.pass_contract = shader_pass_contract();
    render_context.layer_mask = layer_mask;
    render_context.render_category_mask = render_category_mask;
    render_context.scene = TcSceneRef(scene);

    CollectContext context{
        this,
        &cached_draw_calls_,
        &cached_render_items_,
        base_shader,
        shader_pass_contract(),
        render_item_pass_semantic(),
        collect_phase_mark,
        &render_context,
        get_pass_name()};

    int filter_flags = TC_SCENE_FILTER_ENABLED
                     | TC_SCENE_FILTER_VISIBLE
                     | TC_SCENE_FILTER_ENTITY_ENABLED;
    tc_scene_foreach_drawable(scene, callback, &context, filter_flags, layer_mask);
}

void GeometryPassBase::sort_draw_calls_by_shader() const {
    if (cached_draw_calls_.size() <= 1) {
        return;
    }

    std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
        [](const DrawCall& a, const DrawCall& b) {
            return a.final_shader.index < b.final_shader.index;
        });
}

std::vector<ResourceSpec> GeometryPassBase::make_resource_specs() const {
    std::vector<ResourceSpec> specs;
    ResourceSpec spec;
    spec.resource = output_res;
    if (auto fmt = fbo_format(); fmt.has_value()) {
        spec.format = *fmt;
    }
    specs.push_back(spec);
    return specs;
}

void GeometryPassBase::register_type() {
    _register_inspect_input_res();
    _register_inspect_output_res();
    _register_inspect_camera_name();
    _register_inspect_metadata_graph();
}

} // namespace termin
