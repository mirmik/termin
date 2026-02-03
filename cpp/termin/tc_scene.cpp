// tc_scene.cpp - TcSceneRef implementation
#include "tc_scene.hpp"
#include "entity/entity.hpp"
#include "entity/component.hpp"
#include "entity/tc_component_ref.hpp"
#include "render/rendering_manager.hpp"
#include "../../core_c/include/tc_scene_skybox.h"
#include "render/scene_pipeline_template.hpp"
#include "render/tc_value_trent.hpp"
#include "collision/collision_world.hpp"
#include "colliders/collider_component.hpp"
#include "geom/ray3.hpp"
#include "tc_log.hpp"
#include <sstream>
#include <iomanip>
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
    tc_scene_get_background_color(_h, &r, &g, &b, &a);
    return {r, g, b, a};
}

void TcSceneRef::set_background_color(float r, float g, float b, float a) {
    tc_scene_set_background_color(_h, r, g, b, a);
}

Vec4 TcSceneRef::background_color() const {
    float r = 0, g = 0, b = 0, a = 1;
    tc_scene_get_background_color(_h, &r, &g, &b, &a);
    return Vec4(r, g, b, a);
}

void TcSceneRef::set_background_color(const Vec4& color) {
    tc_scene_set_background_color(_h,
        static_cast<float>(color.x),
        static_cast<float>(color.y),
        static_cast<float>(color.z),
        static_cast<float>(color.w));
}

Vec3 TcSceneRef::skybox_color() const {
    float r, g, b;
    tc_scene_get_skybox_color(_h, &r, &g, &b);
    return Vec3(r, g, b);
}

void TcSceneRef::set_skybox_color(const Vec3& color) {
    tc_scene_set_skybox_color(_h,
        static_cast<float>(color.x),
        static_cast<float>(color.y),
        static_cast<float>(color.z));
}

Vec3 TcSceneRef::skybox_top_color() const {
    float r, g, b;
    tc_scene_get_skybox_top_color(_h, &r, &g, &b);
    return Vec3(r, g, b);
}

void TcSceneRef::set_skybox_top_color(const Vec3& color) {
    tc_scene_set_skybox_top_color(_h,
        static_cast<float>(color.x),
        static_cast<float>(color.y),
        static_cast<float>(color.z));
}

Vec3 TcSceneRef::skybox_bottom_color() const {
    float r, g, b;
    tc_scene_get_skybox_bottom_color(_h, &r, &g, &b);
    return Vec3(r, g, b);
}

void TcSceneRef::set_skybox_bottom_color(const Vec3& color) {
    tc_scene_set_skybox_bottom_color(_h,
        static_cast<float>(color.x),
        static_cast<float>(color.y),
        static_cast<float>(color.z));
}

Vec3 TcSceneRef::ambient_color() const {
    tc_scene_lighting* lit = tc_scene_get_lighting(_h);
    if (lit) {
        return Vec3(lit->ambient_color[0], lit->ambient_color[1], lit->ambient_color[2]);
    }
    return Vec3(1.0, 1.0, 1.0);
}

void TcSceneRef::set_ambient_color(const Vec3& color) {
    tc_scene_lighting* lit = tc_scene_get_lighting(_h);
    if (lit) {
        lit->ambient_color[0] = static_cast<float>(color.x);
        lit->ambient_color[1] = static_cast<float>(color.y);
        lit->ambient_color[2] = static_cast<float>(color.z);
    }
}

float TcSceneRef::ambient_intensity() const {
    tc_scene_lighting* lit = tc_scene_get_lighting(_h);
    return lit ? lit->ambient_intensity : 0.1f;
}

void TcSceneRef::set_ambient_intensity(float intensity) {
    tc_scene_lighting* lit = tc_scene_get_lighting(_h);
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
    return tc_scene_viewport_config_count(_h);
}

ViewportConfig TcSceneRef::viewport_config_at(size_t index) const {
    tc_viewport_config* c = tc_scene_viewport_config_at(_h, index);
    return ViewportConfig::from_c(c);
}

std::vector<ViewportConfig> TcSceneRef::viewport_configs() const {
    std::vector<ViewportConfig> result;
    size_t count = tc_scene_viewport_config_count(_h);
    result.reserve(count);
    for (size_t i = 0; i < count; ++i) {
        tc_viewport_config* c = tc_scene_viewport_config_at(_h, i);
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
    return tc_scene_get_lighting(_h);
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
    return tc_scene_pipeline_template_count(_h);
}

TcScenePipelineTemplate TcSceneRef::pipeline_template_at(size_t index) const {
    return TcScenePipelineTemplate(tc_scene_pipeline_template_at(_h, index));
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
    return reinterpret_cast<collision::CollisionWorld*>(tc_scene_get_collision_world(_h));
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

// --- Serialization helpers ---

namespace {

nos::trent serialize_viewport_config(const ViewportConfig& vc) {
    nos::trent data;
    data["name"] = vc.name;
    data["display_name"] = vc.display_name;
    data["camera_uuid"] = vc.camera_uuid;

    nos::trent region;
    region.push_back(nos::trent(static_cast<double>(vc.region_x)));
    region.push_back(nos::trent(static_cast<double>(vc.region_y)));
    region.push_back(nos::trent(static_cast<double>(vc.region_w)));
    region.push_back(nos::trent(static_cast<double>(vc.region_h)));
    data["region"] = std::move(region);

    data["depth"] = static_cast<int64_t>(vc.depth);
    data["input_mode"] = vc.input_mode;
    data["block_input_in_editor"] = vc.block_input_in_editor;

    if (!vc.pipeline_uuid.empty()) {
        data["pipeline_uuid"] = vc.pipeline_uuid;
    }
    if (!vc.pipeline_name.empty()) {
        data["pipeline_name"] = vc.pipeline_name;
    }

    // Only serialize layer_mask if not all layers
    if (vc.layer_mask != 0xFFFFFFFFFFFFFFFFULL) {
        std::ostringstream oss;
        oss << "0x" << std::hex << vc.layer_mask;
        data["layer_mask"] = oss.str();
    }

    // Only serialize enabled if False
    if (!vc.enabled) {
        data["enabled"] = false;
    }

    return data;
}

ViewportConfig deserialize_viewport_config(const nos::trent& data) {
    ViewportConfig vc;

    vc.name = data["name"].as_string_default("");
    vc.display_name = data["display_name"].as_string_default("Main");
    vc.camera_uuid = data["camera_uuid"].as_string_default("");

    if (data.contains("region") && data["region"].is_list()) {
        const auto& r = data["region"].as_list();
        if (r.size() >= 4) {
            vc.region_x = static_cast<float>(r[0].as_numer_default(0.0));
            vc.region_y = static_cast<float>(r[1].as_numer_default(0.0));
            vc.region_w = static_cast<float>(r[2].as_numer_default(1.0));
            vc.region_h = static_cast<float>(r[3].as_numer_default(1.0));
        }
    }

    vc.depth = static_cast<int>(data["depth"].as_numer_default(0));
    vc.input_mode = data["input_mode"].as_string_default("simple");
    vc.block_input_in_editor = data["block_input_in_editor"].as_bool_default(false);
    vc.pipeline_uuid = data["pipeline_uuid"].as_string_default("");
    vc.pipeline_name = data["pipeline_name"].as_string_default("");
    vc.enabled = data["enabled"].as_bool_default(true);

    // Parse layer_mask (may be hex string or int)
    if (data.contains("layer_mask")) {
        auto& lm = data["layer_mask"];
        if (lm.is_string()) {
            std::string s = lm.as_string();
            if (s.size() > 2 && s[0] == '0' && s[1] == 'x') {
                vc.layer_mask = std::stoull(s.substr(2), nullptr, 16);
            } else {
                vc.layer_mask = std::stoull(s, nullptr, 10);
            }
        } else if (lm.is_numer()) {
            vc.layer_mask = static_cast<uint64_t>(lm.as_numer());
        }
    }

    return vc;
}

nos::trent serialize_shadow_settings(const tc_scene_lighting* lighting) {
    nos::trent data;
    data["method"] = static_cast<int64_t>(lighting->shadow_method);
    data["softness"] = static_cast<double>(lighting->shadow_softness);
    data["bias"] = static_cast<double>(lighting->shadow_bias);
    return data;
}

void deserialize_shadow_settings(tc_scene_lighting* lighting, const nos::trent& data) {
    if (data.contains("method")) {
        lighting->shadow_method = static_cast<int>(data["method"].as_numer_default(1));
    }
    if (data.contains("softness")) {
        lighting->shadow_softness = static_cast<float>(data["softness"].as_numer_default(1.0));
    }
    if (data.contains("bias")) {
        lighting->shadow_bias = static_cast<float>(data["bias"].as_numer_default(0.005));
    }
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

} // anonymous namespace

// --- TcSceneRef serialization ---

nos::trent TcSceneRef::serialize() const {
    nos::trent result;

    result["uuid"] = uuid();

    // Background color
    auto [r, g, b, a] = get_background_color();
    nos::trent bg;
    bg.push_back(nos::trent(static_cast<double>(r)));
    bg.push_back(nos::trent(static_cast<double>(g)));
    bg.push_back(nos::trent(static_cast<double>(b)));
    bg.push_back(nos::trent(static_cast<double>(a)));
    result["background_color"] = std::move(bg);

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

    // Viewport configs
    nos::trent viewport_configs_list;
    viewport_configs_list.init(nos::trent::type::list);
    for (const ViewportConfig& vc : viewport_configs()) {
        viewport_configs_list.push_back(serialize_viewport_config(vc));
    }
    result["viewport_configs"] = std::move(viewport_configs_list);

    // Pipeline templates
    nos::trent pipelines;
    pipelines.init(nos::trent::type::list);
    for (size_t i = 0; i < pipeline_template_count(); i++) {
        TcScenePipelineTemplate t = pipeline_template_at(i);
        if (t.is_valid()) {
            nos::trent p;
            p["uuid"] = t.uuid();
            pipelines.push_back(std::move(p));
        }
    }
    result["scene_pipelines"] = std::move(pipelines);

    // Lighting
    tc_scene_lighting* lit = tc_scene_get_lighting(_h);
    if (lit) {
        nos::trent ambient;
        ambient.push_back(nos::trent(static_cast<double>(lit->ambient_color[0])));
        ambient.push_back(nos::trent(static_cast<double>(lit->ambient_color[1])));
        ambient.push_back(nos::trent(static_cast<double>(lit->ambient_color[2])));
        result["ambient_color"] = std::move(ambient);
        result["ambient_intensity"] = static_cast<double>(lit->ambient_intensity);
        result["shadow_settings"] = serialize_shadow_settings(lit);
    }

    // Skybox
    float sr, sg, sb_c, str, stg, stb, sbr, sbg, sbb;
    tc_scene_get_skybox_color(_h, &sr, &sg, &sb_c);
    tc_scene_get_skybox_top_color(_h, &str, &stg, &stb);
    tc_scene_get_skybox_bottom_color(_h, &sbr, &sbg, &sbb);

    // Convert skybox type to string for JSON compatibility
    int skybox_type_int = tc_scene_get_skybox_type(_h);
    const char* skybox_type_str = "gradient";
    if (skybox_type_int == TC_SKYBOX_NONE) skybox_type_str = "none";
    else if (skybox_type_int == TC_SKYBOX_SOLID) skybox_type_str = "solid";
    result["skybox_type"] = skybox_type_str;

    nos::trent sc, st, sb;
    sc.push_back(nos::trent(static_cast<double>(sr)));
    sc.push_back(nos::trent(static_cast<double>(sg)));
    sc.push_back(nos::trent(static_cast<double>(sb_c)));
    result["skybox_color"] = std::move(sc);

    st.push_back(nos::trent(static_cast<double>(str)));
    st.push_back(nos::trent(static_cast<double>(stg)));
    st.push_back(nos::trent(static_cast<double>(stb)));
    result["skybox_top_color"] = std::move(st);

    sb.push_back(nos::trent(static_cast<double>(sbr)));
    sb.push_back(nos::trent(static_cast<double>(sbg)));
    sb.push_back(nos::trent(static_cast<double>(sbb)));
    result["skybox_bottom_color"] = std::move(sb);

    // Metadata
    nos::trent md = metadata();
    if (!md.is_nil() && md.is_dict() && !md.as_dict().empty()) {
        result["metadata"] = std::move(md);
    }

    return result;
}

int TcSceneRef::load_from_data(const nos::trent& data, bool update_settings) {
    if (update_settings) {
        // Background color
        if (data.contains("background_color") && data["background_color"].is_list()) {
            const auto& bg = data["background_color"].as_list();
            if (bg.size() >= 4) {
                set_background_color(
                    static_cast<float>(bg[0].as_numer_default(0.05)),
                    static_cast<float>(bg[1].as_numer_default(0.05)),
                    static_cast<float>(bg[2].as_numer_default(0.08)),
                    static_cast<float>(bg[3].as_numer_default(1.0))
                );
            }
        }

        // Lighting
        tc_scene_lighting* lit = tc_scene_get_lighting(_h);
        if (lit) {
            if (data.contains("ambient_color") && data["ambient_color"].is_list()) {
                const auto& ac = data["ambient_color"].as_list();
                if (ac.size() >= 3) {
                    lit->ambient_color[0] = static_cast<float>(ac[0].as_numer_default(1.0));
                    lit->ambient_color[1] = static_cast<float>(ac[1].as_numer_default(1.0));
                    lit->ambient_color[2] = static_cast<float>(ac[2].as_numer_default(1.0));
                }
            }
            if (data.contains("ambient_intensity")) {
                lit->ambient_intensity = static_cast<float>(data["ambient_intensity"].as_numer_default(0.1));
            }
            if (data.contains("shadow_settings")) {
                deserialize_shadow_settings(lit, data["shadow_settings"]);
            }
        }

        // Skybox
        if (data.contains("skybox_type")) {
            // Convert string to int enum
            std::string type_str = data["skybox_type"].as_string_default("gradient");
            int type_int = TC_SKYBOX_GRADIENT;
            if (type_str == "none") type_int = TC_SKYBOX_NONE;
            else if (type_str == "solid") type_int = TC_SKYBOX_SOLID;
            tc_scene_set_skybox_type(_h, type_int);
        }
        if (data.contains("skybox_color") && data["skybox_color"].is_list()) {
            const auto& c = data["skybox_color"].as_list();
            if (c.size() >= 3) {
                tc_scene_set_skybox_color(_h,
                    static_cast<float>(c[0].as_numer_default(0.5)),
                    static_cast<float>(c[1].as_numer_default(0.7)),
                    static_cast<float>(c[2].as_numer_default(0.9)));
            }
        }
        if (data.contains("skybox_top_color") && data["skybox_top_color"].is_list()) {
            const auto& c = data["skybox_top_color"].as_list();
            if (c.size() >= 3) {
                tc_scene_set_skybox_top_color(_h,
                    static_cast<float>(c[0].as_numer_default(0.4)),
                    static_cast<float>(c[1].as_numer_default(0.6)),
                    static_cast<float>(c[2].as_numer_default(0.9)));
            }
        }
        if (data.contains("skybox_bottom_color") && data["skybox_bottom_color"].is_list()) {
            const auto& c = data["skybox_bottom_color"].as_list();
            if (c.size() >= 3) {
                tc_scene_set_skybox_bottom_color(_h,
                    static_cast<float>(c[0].as_numer_default(0.6)),
                    static_cast<float>(c[1].as_numer_default(0.5)),
                    static_cast<float>(c[2].as_numer_default(0.4)));
            }
        }

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

        // Viewport configs
        clear_viewport_configs();
        if (data.contains("viewport_configs") && data["viewport_configs"].is_list()) {
            for (const auto& vc_data : data["viewport_configs"].as_list()) {
                add_viewport_config(deserialize_viewport_config(vc_data));
            }
        }

        // Pipeline templates
        clear_pipeline_templates();
        if (data.contains("scene_pipelines") && data["scene_pipelines"].is_list()) {
            for (const auto& sp : data["scene_pipelines"].as_list()) {
                std::string templ_uuid = sp["uuid"].as_string_default("");
                if (!templ_uuid.empty()) {
                    TcScenePipelineTemplate templ = TcScenePipelineTemplate::find_by_uuid(templ_uuid);
                    if (templ.is_valid()) {
                        add_pipeline_template(templ);
                    }
                }
            }
        }

        // Metadata
        if (data.contains("metadata")) {
            tc_value md_val = tc::trent_to_tc_value(data["metadata"]);
            tc_scene_set_metadata(_h, md_val);
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
