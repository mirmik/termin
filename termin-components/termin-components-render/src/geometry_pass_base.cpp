#include <algorithm>
#include <set>

#include <tcbase/tc_log.hpp>

#include <termin/render/geometry_pass_base.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/render/material_pipeline_shader_assembler.hpp>

namespace termin {

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
        const char* phase_mark = nullptr;
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

        std::vector<int> geometry_ids;
        std::vector<GeometryDrawCall> material_phase_draws;
        const bool use_material_phase =
            ctx->pass->uses_material_phase_shader_override();

        if (tc_component_get_drawable_vtable(c) == &Drawable::cxx_drawable_vtable()) {
            auto* drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(c));
            if (drawable) {
                geometry_ids = drawable->get_geometry_ids_for_phase(ctx->phase_mark);
                if (use_material_phase) {
                    std::string mark = ctx->phase_mark;
                    material_phase_draws = drawable->get_geometry_draws(&mark);
                }
            }
        }
        if (geometry_ids.empty()) {
            geometry_ids.push_back(0);
        }

        for (int geometry_id : geometry_ids) {
            tc_shader_handle original_shader = ctx->base_shader;
            for (const GeometryDrawCall& draw : material_phase_draws) {
                tc_material_phase* phase = draw.resolve_phase();
                if (draw.geometry_id == geometry_id &&
                    phase &&
                    !tc_shader_handle_is_invalid(phase->shader)) {
                    original_shader = phase->shader;
                    break;
                }
            }

            ShaderOverrideContext override_context;
            override_context.phase_mark = ctx->phase_mark;
            override_context.geometry_id = geometry_id;
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
        collect_phase_mark};

    tc_scene_foreach_drawable(scene, callback, &context, TC_SCENE_FILTER_NONE, 0);
}

void GeometryPassBase::collect_draw_calls(
    tc_scene_handle scene,
    uint64_t layer_mask,
    tc_shader_handle base_shader
) const {
    cached_draw_calls_.clear();

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
        tc_shader_handle base_shader = tc_shader_handle_invalid();
        MaterialPipelinePassContract pass_contract;
        const char* phase_mark = nullptr;
    };

    auto callback = [](tc_component* c, void* user_data) -> bool {
        auto* ctx = static_cast<CollectContext*>(user_data);
        Entity ent(c->owner);

        if (!ctx->pass->entity_filter(ent)) {
            return true;
        }

        std::vector<int> geometry_ids;
        std::vector<GeometryDrawCall> material_phase_draws;
        const bool use_material_phase =
            ctx->pass->uses_material_phase_shader_override();
        if (tc_component_get_drawable_vtable(c) == &Drawable::cxx_drawable_vtable()) {
            auto* drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(c));
            if (drawable) {
                geometry_ids = drawable->get_geometry_ids_for_phase(ctx->phase_mark);

                if (use_material_phase) {
                    std::string mark = ctx->phase_mark;
                    material_phase_draws = drawable->get_geometry_draws(&mark);
                }
            }
        }
        if (geometry_ids.empty()) {
            geometry_ids.push_back(0);
        }

        const int pick_id = ctx->pass->get_pick_id(ent);
        for (int geometry_id : geometry_ids) {
            tc_shader_handle original_shader = ctx->base_shader;
            const GeometryDrawCall* selected_material_draw = nullptr;
            for (const GeometryDrawCall& draw : material_phase_draws) {
                tc_material_phase* phase = draw.resolve_phase();
                if (draw.geometry_id == geometry_id &&
                    phase &&
                    !tc_shader_handle_is_invalid(phase->shader)) {
                    original_shader = phase->shader;
                    selected_material_draw = &draw;
                    break;
                }
            }

            ShaderOverrideContext override_context;
            override_context.phase_mark = ctx->phase_mark;
            override_context.geometry_id = geometry_id;
            override_context.original_shader = TcShader(original_shader);
            override_context.pass_contract = ctx->pass_contract;
            tc_shader_handle final_shader =
                override_drawable_shader(c, override_context).handle;

            DrawCall dc;
            dc.entity = ent;
            dc.component = c;
            dc.final_shader = final_shader;
            dc.geometry_id = geometry_id;
            dc.pick_id = pick_id;
            if (selected_material_draw) {
                dc.material_phase = selected_material_draw->phase;
                dc.material = selected_material_draw->material;
                dc.phase_index = selected_material_draw->phase_index;
            }
            ctx->draw_calls->push_back(dc);
        }
        return true;
    };

    CollectContext context{
        this,
        &cached_draw_calls_,
        base_shader,
        shader_pass_contract(),
        collect_phase_mark};

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

} // namespace termin
