// tc_scene.cpp - TcScene implementation
#include "tc_scene.hpp"
#include "tc_scene_ref.hpp"
#include "entity/entity.hpp"
#include "entity/component.hpp"
#include "render/rendering_manager.hpp"
#include "render/scene_pipeline_template.hpp"
#include "collision/collision_world.hpp"
#include "colliders/collider_component.hpp"
#include "geom/ray3.hpp"
#include "tc_log.hpp"

namespace termin {

TcScene::TcScene() {
    _h = tc_scene_new();
    _collision_world = std::make_unique<collision::CollisionWorld>();
    tc_scene_set_collision_world(_h, _collision_world.get());
    _metadata.init(nos::trent::type::dict);
    tc::Log::info("[TcScene] Created handle=(%u,%u), this=%p", _h.index, _h.generation, (void*)this);
}

TcScene::~TcScene() {
    tc::Log::info("[TcScene] ~TcScene handle=(%u,%u), this=%p", _h.index, _h.generation, (void*)this);
    destroy();
}

void TcScene::destroy() {
    if (tc_scene_handle_valid(_h)) {
        tc::Log::info("[TcScene] destroy() handle=(%u,%u)", _h.index, _h.generation);
        RenderingManager::instance().clear_scene_pipelines(_h);
        tc_scene_set_collision_world(_h, nullptr);
        _collision_world.reset();
        tc_scene_free(_h);
        _h = TC_SCENE_HANDLE_INVALID;
    }
}

bool TcScene::is_alive() const {
    return tc_scene_alive(_h);
}

TcSceneRef TcScene::scene_ref() const {
    return TcSceneRef(_h);
}

TcScene::TcScene(TcScene&& other) noexcept
    : _h(other._h)
    , _collision_world(std::move(other._collision_world))
    , _metadata(std::move(other._metadata))
    , _viewport_configs(std::move(other._viewport_configs))
{
    other._h = TC_SCENE_HANDLE_INVALID;
}

TcScene& TcScene::operator=(TcScene&& other) noexcept {
    if (this != &other) {
        destroy();
        _h = other._h;
        _collision_world = std::move(other._collision_world);
        _metadata = std::move(other._metadata);
        _viewport_configs = std::move(other._viewport_configs);
        other._h = TC_SCENE_HANDLE_INVALID;
    }
    return *this;
}

void TcScene::add_entity(const Entity& e) {
    (void)e;
}

void TcScene::remove_entity(const Entity& e) {
    if (!e.valid()) return;
    tc_entity_pool_free(e.pool(), e.id());
}

size_t TcScene::entity_count() const {
    return tc_scene_entity_count(_h);
}

void TcScene::register_component(CxxComponent* c) {
    if (!c) return;
    tc_scene_register_component(_h, c->c_component());
}

void TcScene::unregister_component(CxxComponent* c) {
    if (!c) return;
    tc_scene_unregister_component(_h, c->c_component());
}

void TcScene::register_component_ptr(uintptr_t ptr) {
    tc_component* c = reinterpret_cast<tc_component*>(ptr);
    if (c) {
        tc_scene_register_component(_h, c);
    }
}

void TcScene::unregister_component_ptr(uintptr_t ptr) {
    tc_component* c = reinterpret_cast<tc_component*>(ptr);
    if (c) {
        tc_scene_unregister_component(_h, c);
    }
}

void TcScene::update(double dt) {
    tc_scene_update(_h, dt);
}

void TcScene::editor_update(double dt) {
    tc_scene_editor_update(_h, dt);
}

void TcScene::before_render() {
    tc_scene_before_render(_h);
}

double TcScene::fixed_timestep() const {
    return tc_scene_fixed_timestep(_h);
}

void TcScene::set_fixed_timestep(double dt) {
    tc_scene_set_fixed_timestep(_h, dt);
}

double TcScene::accumulated_time() const {
    return tc_scene_accumulated_time(_h);
}

void TcScene::reset_accumulated_time() {
    tc_scene_reset_accumulated_time(_h);
}

size_t TcScene::pending_start_count() const {
    return tc_scene_pending_start_count(_h);
}

size_t TcScene::update_list_count() const {
    return tc_scene_update_list_count(_h);
}

size_t TcScene::fixed_update_list_count() const {
    return tc_scene_fixed_update_list_count(_h);
}

tc_entity_pool* TcScene::entity_pool() const {
    return tc_scene_entity_pool(_h);
}

Entity TcScene::create_entity(const std::string& name) {
    tc_entity_pool* pool = entity_pool();
    if (!pool) return Entity();
    return Entity::create(pool, name);
}

Entity TcScene::get_entity(const std::string& uuid) const {
    tc_entity_pool* pool = entity_pool();
    if (!pool || uuid.empty()) return Entity();

    tc_entity_id id = tc_entity_pool_find_by_uuid(pool, uuid.c_str());
    if (!tc_entity_id_valid(id)) return Entity();

    return Entity(pool, id);
}

Entity TcScene::get_entity_by_pick_id(uint32_t pick_id) const {
    tc_entity_pool* pool = entity_pool();
    if (!pool || pick_id == 0) return Entity();

    tc_entity_id id = tc_entity_pool_find_by_pick_id(pool, pick_id);
    if (!tc_entity_id_valid(id)) return Entity();

    return Entity(pool, id);
}

Entity TcScene::find_entity_by_name(const std::string& name) const {
    if (name.empty()) return Entity();

    tc_entity_id id = tc_scene_find_entity_by_name(_h, name.c_str());
    if (!tc_entity_id_valid(id)) return Entity();

    return Entity(entity_pool(), id);
}

std::string TcScene::name() const {
    const char* n = tc_scene_get_name(_h);
    return n ? std::string(n) : "";
}

void TcScene::set_name(const std::string& n) {
    tc_scene_set_name(_h, n.c_str());
}

std::string TcScene::uuid() const {
    const char* u = tc_scene_get_uuid(_h);
    return u ? std::string(u) : "";
}

void TcScene::set_uuid(const std::string& u) {
    tc_scene_set_uuid(_h, u.empty() ? nullptr : u.c_str());
}

std::string TcScene::get_layer_name(int index) const {
    const char* n = tc_scene_get_layer_name(_h, index);
    return n ? std::string(n) : "";
}

void TcScene::set_layer_name(int index, const std::string& name) {
    tc_scene_set_layer_name(_h, index, name.empty() ? nullptr : name.c_str());
}

std::string TcScene::get_flag_name(int index) const {
    const char* n = tc_scene_get_flag_name(_h, index);
    return n ? std::string(n) : "";
}

void TcScene::set_flag_name(int index, const std::string& name) {
    tc_scene_set_flag_name(_h, index, name.empty() ? nullptr : name.c_str());
}

std::tuple<float, float, float, float> TcScene::get_background_color() const {
    float r = 0, g = 0, b = 0, a = 1;
    tc_scene_get_background_color(_h, &r, &g, &b, &a);
    return {r, g, b, a};
}

void TcScene::set_background_color(float r, float g, float b, float a) {
    tc_scene_set_background_color(_h, r, g, b, a);
}

void TcScene::add_viewport_config(const ViewportConfig& config) {
    _viewport_configs.push_back(config);
}

void TcScene::remove_viewport_config(size_t index) {
    if (index < _viewport_configs.size()) {
        _viewport_configs.erase(_viewport_configs.begin() + index);
    }
}

void TcScene::clear_viewport_configs() {
    _viewport_configs.clear();
}

size_t TcScene::viewport_config_count() const {
    return _viewport_configs.size();
}

ViewportConfig* TcScene::viewport_config_at(size_t index) {
    if (index >= _viewport_configs.size()) return nullptr;
    return &_viewport_configs[index];
}

const ViewportConfig* TcScene::viewport_config_at(size_t index) const {
    if (index >= _viewport_configs.size()) return nullptr;
    return &_viewport_configs[index];
}

const nos::trent* TcScene::get_metadata_at_path(const std::string& path) const {
    const nos::trent* current = &_metadata;
    std::string remaining = path;

    while (!remaining.empty() && current != nullptr) {
        size_t dot_pos = remaining.find('.');
        std::string key = (dot_pos == std::string::npos)
            ? remaining
            : remaining.substr(0, dot_pos);

        if (!current->is_dict() || !current->contains(key)) {
            return nullptr;
        }
        current = current->_get(key);

        if (dot_pos == std::string::npos) {
            break;
        }
        remaining = remaining.substr(dot_pos + 1);
    }

    return (current && !current->is_nil()) ? current : nullptr;
}

void TcScene::set_metadata_at_path(const std::string& path, const nos::trent& value) {
    if (path.empty()) return;

    if (!_metadata.is_dict()) {
        _metadata.init(nos::trent::type::dict);
    }

    nos::trent* current = &_metadata;
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
}

bool TcScene::has_metadata_at_path(const std::string& path) const {
    return get_metadata_at_path(path) != nullptr;
}

std::string TcScene::metadata_to_json() const {
    return nos::json::dump(_metadata);
}

void TcScene::metadata_from_json(const std::string& json_str) {
    if (json_str.empty()) {
        _metadata.init(nos::trent::type::dict);
        return;
    }
    try {
        _metadata = nos::json::parse(json_str);
        if (!_metadata.is_dict()) {
            _metadata.init(nos::trent::type::dict);
        }
    } catch (const std::exception& e) {
        tc::Log::error("[TcScene] Failed to parse metadata JSON: %s", e.what());
        _metadata.init(nos::trent::type::dict);
    }
}

tc_scene_lighting* TcScene::lighting() {
    return tc_scene_get_lighting(_h);
}

std::vector<Entity> TcScene::get_all_entities() const {
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

Entity TcScene::migrate_entity(Entity& entity) {
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

void TcScene::add_pipeline_template(const TcScenePipelineTemplate& templ) {
    tc_scene_add_pipeline_template(_h, templ.handle());
}

void TcScene::clear_pipeline_templates() {
    tc_scene_clear_pipeline_templates(_h);
}

size_t TcScene::pipeline_template_count() const {
    return tc_scene_pipeline_template_count(_h);
}

TcScenePipelineTemplate TcScene::pipeline_template_at(size_t index) const {
    return TcScenePipelineTemplate(tc_scene_pipeline_template_at(_h, index));
}

RenderPipeline* TcScene::get_pipeline(const std::string& name) const {
    return RenderingManager::instance().get_scene_pipeline(_h, name);
}

std::vector<std::string> TcScene::get_pipeline_names() const {
    return RenderingManager::instance().get_pipeline_names(_h);
}

const std::vector<std::string>& TcScene::get_pipeline_targets(const std::string& name) const {
    return RenderingManager::instance().get_pipeline_targets(name);
}

collision::CollisionWorld* TcScene::collision_world() const {
    return _collision_world.get();
}

SceneRaycastHit TcScene::raycast(const Ray3& ray) const {
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

SceneRaycastHit TcScene::closest_to_ray(const Ray3& ray) const {
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

} // namespace termin
