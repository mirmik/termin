#include <algorithm>
#include <set>

#include <tcbase/tc_log.hpp>

#include <termin/render/geometry_pass_base.hpp>

#include "camera/camera_component.hpp"

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

void GeometryPassBase::setup_extra_uniforms(
    const DrawCall& dc,
    TcShader& shader,
    RenderContext& context
) {
    (void)dc;
    (void)shader;
    (void)context;
}

bool GeometryPassBase::entity_filter(const Entity& ent) const {
    (void)ent;
    return true;
}

int GeometryPassBase::get_pick_id(const Entity& ent) const {
    (void)ent;
    return 0;
}

TcShader& GeometryPassBase::get_shader(GraphicsBackend* graphics) {
    if (!_shader.is_valid()) {
        _shader = TcShader::from_sources(
            vertex_shader_source(),
            fragment_shader_source(),
            "",
            get_pass_name()
        );
        _shader.ensure_ready();
    }
    (void)graphics;
    return _shader;
}

void GeometryPassBase::bind_and_clear(
    GraphicsBackend* graphics,
    FramebufferHandle* fb,
    const Rect4i& rect
) const {
    auto cc = clear_color();
    graphics->bind_framebuffer(fb);
    graphics->set_viewport(0, 0, rect.width, rect.height);
    graphics->clear_color_depth(cc[0], cc[1], cc[2], cc[3]);
}

void GeometryPassBase::apply_default_render_state(GraphicsBackend* graphics) const {
    RenderState state;
    state.depth_test = true;
    state.depth_write = true;
    state.blend = false;
    state.cull = true;
    graphics->apply_render_state(state);
}

void GeometryPassBase::maybe_blit_to_debugger(
    GraphicsBackend* graphics,
    FramebufferHandle* fb,
    const std::string& entity_name,
    int width,
    int height
) {
    (void)entity_name;
    auto* cap = debug_capture();
    if (cap) {
        cap->capture_direct(fb, graphics);
        return;
    }

    if (!debugger_callbacks.is_set()) {
        return;
    }

    debugger_callbacks.blit_from_pass(
        debugger_callbacks.user_data,
        fb,
        graphics,
        width,
        height
    );
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

void GeometryPassBase::execute_geometry_pass(
    GraphicsBackend* graphics,
    const FBOMap& writes_fbos,
    const Rect4i& rect,
    tc_scene_handle scene,
    const Mat44f& view,
    const Mat44f& projection,
    uint64_t layer_mask
) {
    auto it = writes_fbos.find(output_res);
    if (it == writes_fbos.end() || it->second == nullptr) {
        tc::Log::error("[GeometryPassBase] '%s': output FBO '%s' not found!",
            get_pass_name().c_str(), output_res.c_str());
        return;
    }
    FramebufferHandle* fb = dynamic_cast<FramebufferHandle*>(it->second);
    if (!fb) {
        tc::Log::error("[GeometryPassBase] '%s': output '%s' is not FramebufferHandle!",
            get_pass_name().c_str(), output_res.c_str());
        return;
    }

    bind_and_clear(graphics, fb, rect);
    apply_default_render_state(graphics);

    TcShader& base_shader = get_shader(graphics);
    collect_draw_calls(scene, layer_mask, base_shader.handle);
    sort_draw_calls_by_shader();

    entity_names.clear();
    std::set<std::string> seen_entities;

    RenderContext context;
    context.view = view;
    context.projection = projection;
    context.graphics = graphics;
    context.phase = phase_name();

    const std::string& debug_symbol = get_debug_internal_point();
    tc_shader_handle last_shader = tc_shader_handle_invalid();

    for (const auto& dc : cached_draw_calls_) {
        auto* drawable = static_cast<Drawable*>(tc_component_get_drawable_userdata(dc.component));
        if (!drawable) {
            continue;
        }
        Mat44f model = drawable->get_model_matrix(dc.entity);
        context.model = model;

        const char* name = dc.entity.name();
        if (name && seen_entities.insert(name).second) {
            entity_names.push_back(name);
        }

        tc_shader_handle shader_handle = dc.final_shader;
        bool shader_changed = !tc_shader_handle_eq(shader_handle, last_shader);

        TcShader shader_to_use(shader_handle);
        if (shader_changed) {
            shader_to_use.use();
            shader_to_use.set_uniform_mat4("u_view", view.data, false);
            shader_to_use.set_uniform_mat4("u_projection", projection.data, false);
            last_shader = shader_handle;
        }

        shader_to_use.set_uniform_mat4("u_model", model.data, false);
        context.current_tc_shader = shader_to_use;

        setup_extra_uniforms(dc, shader_to_use, context);
        tc_component_draw_geometry(dc.component, &context, dc.geometry_id);

        if (!debug_symbol.empty() && name && debug_symbol == name) {
            maybe_blit_to_debugger(graphics, fb, name, rect.width, rect.height);
        }
    }
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
