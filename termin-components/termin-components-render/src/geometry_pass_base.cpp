#include <algorithm>
#include <set>

#include <tcbase/tc_log.hpp>

#include <termin/render/geometry_pass_base.hpp>

#include <termin/camera/camera_component.hpp>

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
    _shader = TcShader();
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

bool GeometryPassBase::entity_filter(const Entity& ent) const {
    (void)ent;
    return true;
}

int GeometryPassBase::get_pick_id(const Entity& ent) const {
    (void)ent;
    return 0;
}

TcShader& GeometryPassBase::get_shader() {
    if (!_shader.is_valid()) {
        _shader = TcShader::from_sources(
            vertex_shader_source(),
            fragment_shader_source(),
            "",
            get_pass_name()
        );
        // tgfx2 path compiles lazily via tc_shader_ensure_tgfx2; the
        // _shader here is only used for its handle (as base shader key
        // for per-draw override matching).
    }
    return _shader;
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

    struct CollectContext {
    public:
        const GeometryPassBase* pass = nullptr;
        std::vector<DrawCall>* draw_calls = nullptr;
        tc_shader_handle base_shader = tc_shader_handle_invalid();
    };

    auto callback = [](tc_component* c, void* user_data) -> bool {
        auto* ctx = static_cast<CollectContext*>(user_data);
        Entity ent(c->owner);

        if (!ctx->pass->entity_filter(ent)) {
            return true;
        }

        tc_shader_handle final_shader = tc_component_override_shader(
            c, ctx->pass->phase_name(), 0, ctx->base_shader
        );

        DrawCall dc;
        dc.entity = ent;
        dc.component = c;
        dc.final_shader = final_shader;
        dc.geometry_id = 0;
        dc.pick_id = ctx->pass->get_pick_id(ent);
        ctx->draw_calls->push_back(dc);
        return true;
    };

    CollectContext context{this, &cached_draw_calls_, base_shader};

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
