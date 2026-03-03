// tc_scene.cpp - TcSceneRef implementation
#include "termin/tc_scene.hpp"
#include "entity/entity.hpp"
#include "entity/component.hpp"
#include "entity/tc_component_ref.hpp"
#include "render/rendering_manager.hpp"
#include "core/tc_scene_extension.h"
#include "core/tc_scene_skybox.h"
#include "physics/tc_collision_world.h"
#include "render/scene_pipeline_template.hpp"
#include "render/tc_value_trent.hpp"
#include "collision/collision_world.hpp"
#include "colliders/collider_component.hpp"
#include "geom/ray3.hpp"
#include <tcbase/tc_log.hpp>
#include <functional>

namespace termin {

TcSceneRef TcSceneRef::create(const std::string& name, const std::string& uuid) {
    tc_scene_handle h = tc_scene_new();
    if (!name.empty()) {
        tc_scene_set_name(h, name.c_str());
    }
    if (!uuid.empty()) {
        tc_scene_set_uuid(h, uuid.c_str());
    }
    tc::Log::info("[TcSceneRef] create() handle=(%u,%u), name='%s'", h.index, h.generation, name.c_str());
    return TcSceneRef(h);
}

void TcSceneRef::destroy() {
    if (tc_scene_handle_valid(_h)) {
        tc::Log::info("[TcSceneRef] destroy() handle=(%u,%u)", _h.index, _h.generation);
        RenderingManager::instance().clear_scene_pipelines(_h);
        tc_scene_free(_h);
        _h = TC_SCENE_HANDLE_INVALID;
    }
}

void TcSceneRef::add_entity(const Entity& e) {
    (void)e;
}

void TcSceneRef::remove_entity(const Entity& e) {
    if (!e.valid()) return;
    tc_entity_pool_free(e.pool(), e.id());
}

size_t TcSceneRef::entity_count() const {
    return tc_scene_entity_count(_h);
}

void TcSceneRef::register_component(CxxComponent* c) {
    if (!c) return;
    tc_scene_register_component(_h, c->c_component());
}

void TcSceneRef::unregister_component(CxxComponent* c) {
    if (!c) return;
    tc_scene_unregister_component(_h, c->c_component());
}

void TcSceneRef::register_component_ptr(uintptr_t ptr) {
    tc_component* c = reinterpret_cast<tc_component*>(ptr);
    if (c) {
        tc_scene_register_component(_h, c);
    }
}

void TcSceneRef::unregister_component_ptr(uintptr_t ptr) {
    tc_component* c = reinterpret_cast<tc_component*>(ptr);
    if (c) {
        tc_scene_unregister_component(_h, c);
    }
}

void TcSceneRef::update(double dt) {
    tc_scene_update(_h, dt);
}

void TcSceneRef::editor_update(double dt) {
    tc_scene_editor_update(_h, dt);
}

void TcSceneRef::before_render() {
    tc_scene_before_render(_h);
}

double TcSceneRef::fixed_timestep() const {
    return tc_scene_fixed_timestep(_h);
}

void TcSceneRef::set_fixed_timestep(double dt) {
    tc_scene_set_fixed_timestep(_h, dt);
}

double TcSceneRef::accumulated_time() const {
    return tc_scene_accumulated_time(_h);
}

void TcSceneRef::reset_accumulated_time() {
    tc_scene_reset_accumulated_time(_h);
}

size_t TcSceneRef::pending_start_count() const {
    return tc_scene_pending_start_count(_h);
}

size_t TcSceneRef::update_list_count() const {
    return tc_scene_update_list_count(_h);
}

size_t TcSceneRef::fixed_update_list_count() const {
    return tc_scene_fixed_update_list_count(_h);
}

tc_entity_pool* TcSceneRef::entity_pool() const {
    return tc_scene_entity_pool(_h);
}

Entity TcSceneRef::create_entity(const std::string& name) {
    tc_entity_pool* pool = entity_pool();
    if (!pool) return Entity();
    return Entity::create(pool, name);
}

Entity TcSceneRef::get_entity(const std::string& uuid) const {
    tc_entity_pool* pool = entity_pool();
    if (!pool || uuid.empty()) return Entity();

    tc_entity_id id = tc_entity_pool_find_by_uuid(pool, uuid.c_str());
    if (!tc_entity_id_valid(id)) return Entity();

    return Entity(pool, id);
}

Entity TcSceneRef::get_entity_by_pick_id(uint32_t pick_id) const {
    tc_entity_pool* pool = entity_pool();
    if (!pool || pick_id == 0) return Entity();

    tc_entity_id id = tc_entity_pool_find_by_pick_id(pool, pick_id);
    if (!tc_entity_id_valid(id)) return Entity();

    return Entity(pool, id);
}

Entity TcSceneRef::find_entity_by_name(const std::string& name) const {
    if (name.empty()) return Entity();

    tc_entity_id id = tc_scene_find_entity_by_name(_h, name.c_str());
    if (!tc_entity_id_valid(id)) return Entity();

    return Entity(entity_pool(), id);
}

std::string TcSceneRef::name() const {
    const char* n = tc_scene_get_name(_h);
    return n ? std::string(n) : "";
}

void TcSceneRef::set_name(const std::string& n) {
    tc_scene_set_name(_h, n.c_str());
}

std::string TcSceneRef::uuid() const {
    const char* u = tc_scene_get_uuid(_h);
    return u ? std::string(u) : "";
}

void TcSceneRef::set_uuid(const std::string& u) {
    tc_scene_set_uuid(_h, u.empty() ? nullptr : u.c_str());
}

std::string TcSceneRef::get_layer_name(int index) const {
    const char* n = tc_scene_get_layer_name(_h, index);
    return n ? std::string(n) : "";
}

void TcSceneRef::set_layer_name(int index, const std::string& name) {
    tc_scene_set_layer_name(_h, index, name.empty() ? nullptr : name.c_str());
}

std::string TcSceneRef::get_flag_name(int index) const {
    const char* n = tc_scene_get_flag_name(_h, index);
    return n ? std::string(n) : "";
}

void TcSceneRef::set_flag_name(int index, const std::string& name) {
    tc_scene_set_flag_name(_h, index, name.empty() ? nullptr : name.c_str());
}

std::tuple<float, float, float, float> TcSceneRef::get_background_color() const {
    float r = 0, g = 0, b = 0, a = 1;
    if (tc_scene_render_state* state = tc_scene_render_state_get(_h)) {
        r = state->background_color[0];
        g = state->background_color[1];
        b = state->background_color[2];
        a = state->background_color[3];
    }
    return {r, g, b, a};
}

void TcSceneRef::set_background_color(float r, float g, float b, float a) {
    if (!tc_scene_render_state_ensure(_h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(_h);
    if (!state) return;
    state->background_color[0] = r;
    state->background_color[1] = g;
    state->background_color[2] = b;
    state->background_color[3] = a;
}

Vec4 TcSceneRef::background_color() const {
    float r = 0, g = 0, b = 0, a = 1;
    if (tc_scene_render_state* state = tc_scene_render_state_get(_h)) {
        r = state->background_color[0];
        g = state->background_color[1];
        b = state->background_color[2];
        a = state->background_color[3];
    }
    return Vec4(r, g, b, a);
}

void TcSceneRef::set_background_color(const Vec4& color) {
    set_background_color(
        static_cast<float>(color.x),
        static_cast<float>(color.y),
        static_cast<float>(color.z),
        static_cast<float>(color.w)
    );
}

Vec3 TcSceneRef::skybox_color() const {
    float r = 0.5f, g = 0.7f, b = 0.9f;
    if (tc_scene_render_state* state = tc_scene_render_state_get(_h)) {
        r = state->skybox.color[0];
        g = state->skybox.color[1];
        b = state->skybox.color[2];
    }
    return Vec3(r, g, b);
}

void TcSceneRef::set_skybox_color(const Vec3& color) {
    if (!tc_scene_render_state_ensure(_h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(_h);
    if (!state) return;
    state->skybox.color[0] = static_cast<float>(color.x);
    state->skybox.color[1] = static_cast<float>(color.y);
    state->skybox.color[2] = static_cast<float>(color.z);
}

Vec3 TcSceneRef::skybox_top_color() const {
    float r = 0.4f, g = 0.6f, b = 0.9f;
    if (tc_scene_render_state* state = tc_scene_render_state_get(_h)) {
        r = state->skybox.top_color[0];
        g = state->skybox.top_color[1];
        b = state->skybox.top_color[2];
    }
    return Vec3(r, g, b);
}

void TcSceneRef::set_skybox_top_color(const Vec3& color) {
    if (!tc_scene_render_state_ensure(_h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(_h);
    if (!state) return;
    state->skybox.top_color[0] = static_cast<float>(color.x);
    state->skybox.top_color[1] = static_cast<float>(color.y);
    state->skybox.top_color[2] = static_cast<float>(color.z);
}

Vec3 TcSceneRef::skybox_bottom_color() const {
    float r = 0.6f, g = 0.5f, b = 0.4f;
    if (tc_scene_render_state* state = tc_scene_render_state_get(_h)) {
        r = state->skybox.bottom_color[0];
        g = state->skybox.bottom_color[1];
        b = state->skybox.bottom_color[2];
    }
    return Vec3(r, g, b);
}

void TcSceneRef::set_skybox_bottom_color(const Vec3& color) {
    if (!tc_scene_render_state_ensure(_h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(_h);
    if (!state) return;
    state->skybox.bottom_color[0] = static_cast<float>(color.x);
    state->skybox.bottom_color[1] = static_cast<float>(color.y);
    state->skybox.bottom_color[2] = static_cast<float>(color.z);
}

Vec3 TcSceneRef::ambient_color() const {
    tc_scene_render_state* state = tc_scene_render_state_get(_h);
    tc_scene_lighting* lit = state ? &state->lighting : nullptr;
    if (lit) {
        return Vec3(lit->ambient_color[0], lit->ambient_color[1], lit->ambient_color[2]);
    }
    return Vec3(1.0, 1.0, 1.0);
}

void TcSceneRef::set_ambient_color(const Vec3& color) {
    if (!tc_scene_render_state_ensure(_h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(_h);
    tc_scene_lighting* lit = state ? &state->lighting : nullptr;
    if (lit) {
        lit->ambient_color[0] = static_cast<float>(color.x);
        lit->ambient_color[1] = static_cast<float>(color.y);
        lit->ambient_color[2] = static_cast<float>(color.z);
    }
}

float TcSceneRef::ambient_intensity() const {
    tc_scene_render_state* state = tc_scene_render_state_get(_h);
    tc_scene_lighting* lit = state ? &state->lighting : nullptr;
    return lit ? lit->ambient_intensity : 0.1f;
}

void TcSceneRef::set_ambient_intensity(float intensity) {
    if (!tc_scene_render_state_ensure(_h)) return;
    tc_scene_render_state* state = tc_scene_render_state_get(_h);
    tc_scene_lighting* lit = state ? &state->lighting : nullptr;
    if (lit) {
        lit->ambient_intensity = intensity;
    }
}

void TcSceneRef::add_viewport_config(const ViewportConfig& config) {
    tc_viewport_config c = config.to_c();
    tc_scene_add_viewport_config(_h, &c);
}

void TcSceneRef::remove_viewport_config(size_t index) {
    tc_scene_remove_viewport_config(_h, index);
}

void TcSceneRef::clear_viewport_configs() {
    tc_scene_clear_viewport_configs(_h);
}

size_t TcSceneRef::viewport_config_count() const {
    tc_scene_render_mount* mount = tc_scene_render_mount_get(_h);
    return mount ? mount->viewport_config_count : 0;
}

ViewportConfig TcSceneRef::viewport_config_at(size_t index) const {
    tc_scene_render_mount* mount = tc_scene_render_mount_get(_h);
    if (!mount || index >= mount->viewport_config_count) {
        return ViewportConfig();
    }
    tc_viewport_config* c = &mount->viewport_configs[index];
    return ViewportConfig::from_c(c);
}

std::vector<ViewportConfig> TcSceneRef::viewport_configs() const {
    std::vector<ViewportConfig> result;
    tc_scene_render_mount* mount = tc_scene_render_mount_get(_h);
    size_t count = mount ? mount->viewport_config_count : 0;
    result.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        tc_viewport_config* c = &mount->viewport_configs[i];
        result.push_back(ViewportConfig::from_c(c));
    }
    return result;
}

nos::trent TcSceneRef::metadata() const {
    tc_value* v = tc_scene_get_metadata(_h);
    if (v) {
        return tc::tc_value_to_trent(*v);
    }
    nos::trent result;
    result.init(nos::trent::type::dict);
    return result;
}

nos::trent TcSceneRef::get_metadata_at_path(const std::string& path) const {
    nos::trent md = metadata();
    const nos::trent* current = &md;
    std::string remaining = path;

    while (!remaining.empty() && current != nullptr) {
        size_t dot_pos = remaining.find('.');
        std::string key = (dot_pos == std::string::npos)
            ? remaining
            : remaining.substr(0, dot_pos);

        if (!current->is_dict() || !current->contains(key)) {
            return nos::trent();  // nil
        }
        current = current->_get(key);

        if (dot_pos == std::string::npos) {
            break;
        }
        remaining = remaining.substr(dot_pos + 1);
    }

    if (current && !current->is_nil()) {
        return *current;
    }
    return nos::trent();  // nil
}

void TcSceneRef::set_metadata_at_path(const std::string& path, const nos::trent& value) {
    if (path.empty()) return;

    // Load current metadata
    nos::trent md = metadata();

    if (!md.is_dict()) {
        md.init(nos::trent::type::dict);
    }

    nos::trent* current = &md;
    std::string remaining = path;

    while (true) {
        size_t dot_pos = remaining.find('.');
        std::string key = (dot_pos == std::string::npos)
            ? remaining
            : remaining.substr(0, dot_pos);

        if (dot_pos == std::string::npos) {
            (*current)[key] = value;
            break;
        }

        if (!current->contains(key) || !(*current)[key].is_dict()) {
            (*current)[key].init(nos::trent::type::dict);
        }
        current = &(*current)[key];
        remaining = remaining.substr(dot_pos + 1);
    }

    // Save back to tc_value
    tc_value new_val = tc::trent_to_tc_value(md);
    tc_scene_set_metadata(_h, new_val);
}

bool TcSceneRef::has_metadata_at_path(const std::string& path) const {
    return !get_metadata_at_path(path).is_nil();
}

std::string TcSceneRef::metadata_to_json() const {
    return nos::json::dump(metadata());
}

void TcSceneRef::metadata_from_json(const std::string& json_str) {
    nos::trent md;
    if (json_str.empty()) {
        md.init(nos::trent::type::dict);
    } else {
        try {
            md = nos::json::parse(json_str);
            if (!md.is_dict()) {
                md.init(nos::trent::type::dict);
            }
        } catch (const std::exception& e) {
            tc::Log::error("[TcSceneRef] Failed to parse metadata JSON: %s", e.what());
            md.init(nos::trent::type::dict);
        }
    }
    // Save to tc_value
    tc_value new_val = tc::trent_to_tc_value(md);
    tc_scene_set_metadata(_h, new_val);
}

tc_scene_lighting* TcSceneRef::lighting() {
    tc_scene_render_state* state = tc_scene_render_state_get(_h);
    return state ? &state->lighting : nullptr;
}

std::vector<Entity> TcSceneRef::get_all_entities() const {
    std::vector<Entity> result;
    tc_entity_pool* pool = entity_pool();
    if (!pool) return result;

    tc_entity_pool_foreach(pool, [](tc_entity_pool* p, tc_entity_id id, void* user_data) -> bool {
        auto* vec = static_cast<std::vector<Entity>*>(user_data);
        vec->push_back(Entity(p, id));
        return true;
    }, &result);

    return result;
}

Entity TcSceneRef::migrate_entity(Entity& entity) {
    tc_entity_pool* dst_pool = entity_pool();
    if (!entity.valid() || !dst_pool) {
        return Entity();
    }

    tc_entity_pool* src_pool = entity.pool();
    if (src_pool == dst_pool) {
        return entity;
    }

    tc_entity_id new_id = tc_entity_pool_migrate(src_pool, entity.id(), dst_pool);
    if (!tc_entity_id_valid(new_id)) {
        return Entity();
    }

    return Entity(dst_pool, new_id);
}

void TcSceneRef::add_pipeline_template(const TcScenePipelineTemplate& templ) {
    tc_scene_add_pipeline_template(_h, templ.handle());
}

void TcSceneRef::clear_pipeline_templates() {
    tc_scene_clear_pipeline_templates(_h);
}

size_t TcSceneRef::pipeline_template_count() const {
    tc_scene_render_mount* mount = tc_scene_render_mount_get(_h);
    return mount ? mount->pipeline_template_count : 0;
}

TcScenePipelineTemplate TcSceneRef::pipeline_template_at(size_t index) const {
    tc_scene_render_mount* mount = tc_scene_render_mount_get(_h);
    if (!mount || index >= mount->pipeline_template_count) {
        return TcScenePipelineTemplate(TC_SPT_HANDLE_INVALID);
    }
    return TcScenePipelineTemplate(mount->pipeline_templates[index]);
}

RenderPipeline* TcSceneRef::get_pipeline(const std::string& name) const {
    return RenderingManager::instance().get_scene_pipeline(_h, name);
}

std::vector<std::string> TcSceneRef::get_pipeline_names() const {
    return RenderingManager::instance().get_pipeline_names(_h);
}

const std::vector<std::string>& TcSceneRef::get_pipeline_targets(const std::string& name) const {
    return RenderingManager::instance().get_pipeline_targets(name);
}

collision::CollisionWorld* TcSceneRef::collision_world() const {
    return reinterpret_cast<collision::CollisionWorld*>(tc_collision_world_get_scene(_h));
}

SceneRaycastHit TcSceneRef::raycast(const Ray3& ray) const {
    struct Context {
        SceneRaycastHit* result;
        double best_dist;
        const Ray3* ray;
        Vec3 origin;
    };

    SceneRaycastHit result;
    Context ctx{&result, std::numeric_limits<double>::infinity(), &ray, ray.origin};

    tc_scene_foreach_component_of_type(_h, "ColliderComponent",
        [](tc_component* c, void* user_data) -> bool {
            auto* ctx = static_cast<Context*>(user_data);

            CxxComponent* cxx = CxxComponent::from_tc(c);
            if (!cxx) return true;

            auto* collider_comp = dynamic_cast<ColliderComponent*>(cxx);
            if (!collider_comp) return true;

            auto* attached = collider_comp->attached_collider();
            if (!attached) return true;

            colliders::RayHit hit = attached->closest_to_ray(*ctx->ray);

            // raycast returns only exact hits (distance == 0)
            if (!hit.hit()) return true;

            Vec3 p_ray = hit.point_on_ray;
            double d_ray = (p_ray - ctx->origin).norm();

            if (d_ray < ctx->best_dist) {
                ctx->best_dist = d_ray;
                ctx->result->entity = cxx->entity().handle();
                ctx->result->component = collider_comp;
                ctx->result->point_on_ray[0] = p_ray.x;
                ctx->result->point_on_ray[1] = p_ray.y;
                ctx->result->point_on_ray[2] = p_ray.z;
                ctx->result->point_on_collider[0] = hit.point_on_collider.x;
                ctx->result->point_on_collider[1] = hit.point_on_collider.y;
                ctx->result->point_on_collider[2] = hit.point_on_collider.z;
                ctx->result->distance = hit.distance;
            }
            return true;
        },
        &ctx
    );

    return result;
}

SceneRaycastHit TcSceneRef::closest_to_ray(const Ray3& ray) const {
    struct Context {
        SceneRaycastHit* result;
        double best_dist;
        const Ray3* ray;
    };

    SceneRaycastHit result;
    Context ctx{&result, std::numeric_limits<double>::infinity(), &ray};

    tc_scene_foreach_component_of_type(_h, "ColliderComponent",
        [](tc_component* c, void* user_data) -> bool {
            auto* ctx = static_cast<Context*>(user_data);

            CxxComponent* cxx = CxxComponent::from_tc(c);
            if (!cxx) return true;

            auto* collider_comp = dynamic_cast<ColliderComponent*>(cxx);
            if (!collider_comp) return true;

            auto* attached = collider_comp->attached_collider();
            if (!attached) return true;

            colliders::RayHit hit = attached->closest_to_ray(*ctx->ray);

            if (hit.distance < ctx->best_dist) {
                ctx->best_dist = hit.distance;
                ctx->result->entity = cxx->entity().handle();
                ctx->result->component = collider_comp;
                ctx->result->point_on_ray[0] = hit.point_on_ray.x;
                ctx->result->point_on_ray[1] = hit.point_on_ray.y;
                ctx->result->point_on_ray[2] = hit.point_on_ray.z;
                ctx->result->point_on_collider[0] = hit.point_on_collider.x;
                ctx->result->point_on_collider[1] = hit.point_on_collider.y;
                ctx->result->point_on_collider[2] = hit.point_on_collider.z;
                ctx->result->distance = hit.distance;
            }
            return true;
        },
        &ctx
    );

    return result;
}

nos::trent serialize_entity_recursive(const Entity& e) {
    if (!e.valid() || !e.serializable()) {
        return nos::trent();
    }

    // Serialize base data
    tc_value base_val = e.serialize_base();
    nos::trent data = tc::tc_value_to_trent(base_val);
    tc_value_free(&base_val);

    // Serialize components
    nos::trent components;
    components.init(nos::trent::type::list);
    size_t comp_count = e.component_count();
    for (size_t i = 0; i < comp_count; i++) {
        tc_component* tc = e.component_at(i);
        if (!tc) continue;

        TcComponentRef ref(tc);
        nos::trent comp_data = ref.serialize_trent();
        if (!comp_data.is_nil()) {
            components.push_back(std::move(comp_data));
        }
    }
    data["components"] = std::move(components);

    // Serialize children
    std::vector<Entity> child_list = e.children();
    if (!child_list.empty()) {
        nos::trent children;
        children.init(nos::trent::type::list);
        for (const Entity& child : child_list) {
            if (child.serializable()) {
                nos::trent child_data = serialize_entity_recursive(child);
                if (!child_data.is_nil()) {
                    children.push_back(std::move(child_data));
                }
            }
        }
        if (!children.as_list().empty()) {
            data["children"] = std::move(children);
        }
    }

    return data;
}

// --- TcSceneRef serialization ---

nos::trent TcSceneRef::serialize() const {
    nos::trent result;

    result["uuid"] = uuid();

    // Root entities (no parent, serializable)
    nos::trent entities;
    entities.init(nos::trent::type::list);
    for (const Entity& e : get_all_entities()) {
        // Only root entities (no parent)
        if (e.parent().valid()) continue;
        if (!e.serializable()) continue;

        nos::trent ent_data = serialize_entity_recursive(e);
        if (!ent_data.is_nil()) {
            entities.push_back(std::move(ent_data));
        }
    }
    result["entities"] = std::move(entities);

    // Layer names
    nos::trent layer_names;
    layer_names.init(nos::trent::type::dict);
    for (int i = 0; i < 64; i++) {
        std::string ln = get_layer_name(i);
        if (!ln.empty()) {
            layer_names[std::to_string(i)] = ln;
        }
    }
    result["layer_names"] = std::move(layer_names);

    // Flag names
    nos::trent flag_names;
    flag_names.init(nos::trent::type::dict);
    for (int i = 0; i < 64; i++) {
        std::string fn = get_flag_name(i);
        if (!fn.empty()) {
            flag_names[std::to_string(i)] = fn;
        }
    }
    result["flag_names"] = std::move(flag_names);

    // Metadata
    nos::trent md = metadata();
    if (!md.is_nil() && md.is_dict() && !md.as_dict().empty()) {
        result["metadata"] = std::move(md);
    }

    // Extensions
    tc_value ext_val = tc_scene_ext_serialize_scene(_h);
    nos::trent ext = tc::tc_value_to_trent(ext_val);
    tc_value_free(&ext_val);
    if (!ext.is_nil() && ext.is_dict() && !ext.as_dict().empty()) {
        result["extensions"] = std::move(ext);
    }

    return result;
}

int TcSceneRef::load_from_data(const nos::trent& data, bool update_settings) {
    if (update_settings) {
        // Layer names
        if (data.contains("layer_names") && data["layer_names"].is_dict()) {
            for (const auto& [k, v] : data["layer_names"].as_dict()) {
                int idx = std::stoi(k);
                set_layer_name(idx, v.as_string());
            }
        }

        // Flag names
        if (data.contains("flag_names") && data["flag_names"].is_dict()) {
            for (const auto& [k, v] : data["flag_names"].as_dict()) {
                int idx = std::stoi(k);
                set_flag_name(idx, v.as_string());
            }
        }

        // Render mount state
        clear_viewport_configs();
        clear_pipeline_templates();

        // Metadata
        if (data.contains("metadata")) {
            tc_value md_val = tc::trent_to_tc_value(data["metadata"]);
            tc_scene_set_metadata(_h, md_val);
        }

        // Extensions (including legacy fallback adapters)
        nos::trent merged_extensions;
        if (data.contains("extensions") && data["extensions"].is_dict()) {
            merged_extensions = data["extensions"];
        }
        if (!merged_extensions.is_dict()) {
            merged_extensions.init(nos::trent::type::dict);
        }

        if (!merged_extensions.contains("render_mount")) {
            bool has_legacy_render_mount =
                (data.contains("viewport_configs") && data["viewport_configs"].is_list()) ||
                (data.contains("scene_pipelines") && data["scene_pipelines"].is_list());

            if (has_legacy_render_mount) {
                nos::trent render_mount;
                if (data.contains("viewport_configs") && data["viewport_configs"].is_list()) {
                    render_mount["viewport_configs"] = data["viewport_configs"];
                }
                if (data.contains("scene_pipelines") && data["scene_pipelines"].is_list()) {
                    render_mount["scene_pipelines"] = data["scene_pipelines"];
                }
                merged_extensions["render_mount"] = std::move(render_mount);
            }
        }

        if (!merged_extensions.contains("render_state")) {
            bool has_legacy_render_state =
                data.contains("background_color") ||
                data.contains("ambient_color") ||
                data.contains("ambient_intensity") ||
                data.contains("shadow_settings") ||
                data.contains("skybox_type") ||
                data.contains("skybox_color") ||
                data.contains("skybox_top_color") ||
                data.contains("skybox_bottom_color");

            if (has_legacy_render_state) {
                nos::trent render_state;

                if (data.contains("background_color")) {
                    render_state["background_color"] = data["background_color"];
                }

                nos::trent lighting;
                bool has_lighting = false;
                if (data.contains("ambient_color")) {
                    lighting["ambient_color"] = data["ambient_color"];
                    has_lighting = true;
                }
                if (data.contains("ambient_intensity")) {
                    lighting["ambient_intensity"] = data["ambient_intensity"];
                    has_lighting = true;
                }
                if (data.contains("shadow_settings")) {
                    lighting["shadow_settings"] = data["shadow_settings"];
                    has_lighting = true;
                }
                if (has_lighting) {
                    render_state["lighting"] = std::move(lighting);
                }

                nos::trent skybox;
                bool has_skybox = false;
                if (data.contains("skybox_type")) {
                    std::string type_str = data["skybox_type"].as_string_default("gradient");
                    int type_int = TC_SKYBOX_GRADIENT;
                    if (type_str == "none") type_int = TC_SKYBOX_NONE;
                    else if (type_str == "solid") type_int = TC_SKYBOX_SOLID;
                    skybox["type"] = static_cast<int64_t>(type_int);
                    has_skybox = true;
                }
                if (data.contains("skybox_color")) {
                    skybox["color"] = data["skybox_color"];
                    has_skybox = true;
                }
                if (data.contains("skybox_top_color")) {
                    skybox["top_color"] = data["skybox_top_color"];
                    has_skybox = true;
                }
                if (data.contains("skybox_bottom_color")) {
                    skybox["bottom_color"] = data["skybox_bottom_color"];
                    has_skybox = true;
                }
                if (has_skybox) {
                    render_state["skybox"] = std::move(skybox);
                }

                merged_extensions["render_state"] = std::move(render_state);
            }
        }

        if (!merged_extensions.as_dict().empty()) {
            tc_value ext_val = tc::trent_to_tc_value(merged_extensions);
            tc_scene_ext_deserialize_scene(_h, &ext_val);
            tc_value_free(&ext_val);
        }
    }

    // === Two-phase entity deserialization ===
    if (!data.contains("entities") || !data["entities"].is_list()) {
        return 0;
    }

    const auto& entities_data = data["entities"].as_list();

    // Collect (entity, data) pairs for phase 2
    std::vector<std::pair<Entity, nos::trent>> entity_data_pairs;

    // Helper to recursively deserialize entity hierarchy
    std::function<void(const nos::trent&, Entity*)> deserialize_hierarchy;
    deserialize_hierarchy = [&](const nos::trent& ent_data, Entity* parent_ent) {
        Entity ent = Entity::deserialize_base_trent(ent_data, _h);
        if (!ent.valid()) return;

        // Set parent if provided
        if (parent_ent && parent_ent->valid()) {
            ent.set_parent(*parent_ent);
        }

        // Collect for phase 2
        entity_data_pairs.emplace_back(ent, ent_data);

        // Process children
        if (ent_data.contains("children") && ent_data["children"].is_list()) {
            for (const auto& child_data : ent_data["children"].as_list()) {
                deserialize_hierarchy(child_data, &ent);
            }
        }
    };

    // Phase 1: Create all entities with hierarchy
    for (const auto& ent_data : entities_data) {
        deserialize_hierarchy(ent_data, nullptr);
    }

    // Phase 2: Deserialize components (now all entities exist for reference resolution)
    for (auto& [ent, ent_data] : entity_data_pairs) {
        ent.deserialize_components_trent(ent_data, _h);
    }

    return static_cast<int>(entity_data_pairs.size());
}

std::string TcSceneRef::to_json_string() const {
    return nos::json::dump(serialize(), 2);
}

void TcSceneRef::from_json_string(const std::string& json) {
    try {
        nos::trent data = nos::json::parse(json);
        load_from_data(data, true);
    } catch (const std::exception& e) {
        tc::Log::error("[TcSceneRef] Failed to parse JSON: %s", e.what());
    }
}

} // namespace termin
