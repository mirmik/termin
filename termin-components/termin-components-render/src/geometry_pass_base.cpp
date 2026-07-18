#include <algorithm>
#include <cstdint>
#include <set>

#include <tcbase/tc_log.hpp>

#include <termin/render/geometry_pass_base.hpp>

#include <termin/camera/camera_component.hpp>
#include <termin/render/material_pipeline_shader_assembler.hpp>
#include <termin/render/render_task.hpp>

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

RenderItemTaskPlanningContract geometry_task_planning_contract(
    RenderItemPassSemantic semantic,
    const MaterialPipelinePassContract& shader_contract,
    const char* debug_pass_name)
{
    RenderItemTaskPlanningContract contract{};
    contract.pass_semantic = semantic;
    contract.material_phase_policy = RenderItemMaterialPhasePolicy::Optional;
    contract.provided_input_mask =
        render_item_task_input_bit(RenderItemTaskInput::DrawContext);
    if (semantic == RenderItemPassSemantic::Id) {
        contract.provided_input_mask |=
            render_item_task_input_bit(RenderItemTaskInput::OverrideColor);
    }
    contract.required_input_mask =
        render_item_task_input_bit(RenderItemTaskInput::DrawContext);
    contract.accepted_vertex_transform_kind_mask =
        render_item_vertex_transform_kind_bit(VertexTransformKind::StaticMesh)
        | render_item_vertex_transform_kind_bit(VertexTransformKind::SkinnedMesh);
    contract.shader_contract = &shader_contract;
    contract.debug_pass_name = debug_pass_name;
    return contract;
}

bool plan_geometry_item_shader(
    const tc_render_item& item,
    tc_material_phase* phase,
    tc_shader_handle candidate_shader,
    RenderItemPassSemantic semantic,
    const MaterialPipelinePassContract& shader_contract,
    const char* debug_pass_name,
    RenderTaskList& tasks)
{
    RenderItemTaskPlanningContract contract = geometry_task_planning_contract(
        semantic,
        shader_contract,
        debug_pass_name);
    RenderItemTaskPlanningRequest request{};
    request.item = &item;
    request.material_phase = phase;
    request.candidate_shader = candidate_shader;
    request.contract = &contract;
    return plan_render_item_task(request, tasks).accepted();
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

            RenderTaskList tasks;
            if (!plan_geometry_item_shader(
                    item,
                    ctx->pass->uses_material_phase_shader_override()
                        ? resolve_render_item_material_phase(item)
                        : nullptr,
                    original_shader,
                    ctx->pass_semantic,
                    ctx->pass_contract,
                    ctx->pass_name.c_str(),
                    tasks)) {
                continue;
            }
            const RenderTask& task = tasks.at(0);
            for (uint32_t i = 0; i < task.shader_usage_count; ++i) {
                (*ctx->emit)(TcShader(task.shader_usages[i]));
            }
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
    tc_shader_handle base_shader,
    const RenderSceneItemSnapshot& snapshot
) const {
    (void)layer_mask;
    (void)render_category_mask;
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

    const MaterialPipelinePassContract pass_contract = shader_pass_contract();
    const RenderItemPassSemantic pass_semantic = render_item_pass_semantic();
    const std::string pass_name = get_pass_name();
    const auto& items = snapshot.items();

    for (size_t group_begin = 0; group_begin < items.size();) {
        const tc_render_item& representative = items[group_begin];
        size_t group_end = group_begin + 1;
        while (group_end < items.size() &&
               items[group_end].component == representative.component &&
               items[group_end].kind == representative.kind &&
               items[group_end].geometry_id == representative.geometry_id) {
            ++group_end;
        }

        tc_component* component = representative.component;
        Entity ent(component ? component->owner : TC_ENTITY_HANDLE_INVALID);
        if (!component || !ent.valid() || !entity_filter(ent) ||
            !render_item_encoder_supports_pass(representative.kind, pass_semantic)) {
            group_begin = group_end;
            continue;
        }

        size_t selected_index = group_begin;
        for (size_t i = group_begin; i < group_end; ++i) {
            if (render_item_matches_phase(items[i], collect_phase_mark)) {
                selected_index = i;
                break;
            }
        }
        const tc_render_item& item = items[selected_index];
        tc_material_phase* selected_phase = nullptr;
        tc_shader_handle original_shader = base_shader;
        if (uses_material_phase_shader_override() &&
            render_item_matches_phase(item, collect_phase_mark)) {
            selected_phase = resolve_render_item_material_phase(item);
            if (selected_phase && !tc_shader_handle_is_invalid(selected_phase->shader)) {
                original_shader = selected_phase->shader;
            }
        }

        RenderTaskList planned_shader;
        if (plan_geometry_item_shader(
                item,
                selected_phase,
                original_shader,
                pass_semantic,
                pass_contract,
                pass_name.c_str(),
                planned_shader)) {
            DrawCall dc;
            dc.entity = ent;
            dc.component = component;
            dc.final_shader = TcShader(planned_shader.at(0).final_shader);
            dc.item = item;
            dc.geometry_id = item.geometry_id;
            dc.pick_id = get_pick_id(ent);
            if (selected_phase) {
                dc.material_phase = selected_phase;
                dc.material = item.material;
                dc.phase_index = item.material_phase_index;
            }
            cached_draw_calls_.push_back(std::move(dc));
        }
        group_begin = group_end;
    }
}

void GeometryPassBase::sort_draw_calls_by_shader() const {
    if (cached_draw_calls_.size() <= 1) {
        return;
    }

    std::sort(cached_draw_calls_.begin(), cached_draw_calls_.end(),
        [](const DrawCall& a, const DrawCall& b) {
            return a.final_shader.handle.index < b.final_shader.handle.index;
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
