// tc_scene.cpp - TcSceneRef core implementation (no render dependencies)
#include <termin/tc_scene.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/component.hpp>
#include "core/tc_scene_extension.h"
#include <tcbase/tc_value_trent.hpp>
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
            return nos::trent();
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
    return nos::trent();
}

void TcSceneRef::set_metadata_at_path(const std::string& path, const nos::trent& value) {
    if (path.empty()) return;

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
    tc_value new_val = tc::trent_to_tc_value(md);
    tc_scene_set_metadata(_h, new_val);
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

        // Serialize via tc_inspect
        const char* type_name = tc_component_type_name(tc);
        if (!type_name) continue;

        void* obj_ptr = nullptr;
        if (tc->kind == TC_CXX_COMPONENT) {
            obj_ptr = CxxComponent::from_tc(tc);
        } else {
            obj_ptr = tc->body;
        }

        nos::trent comp_data;
        comp_data["type"] = type_name;
        if (obj_ptr) {
            tc_value v = tc_inspect_serialize(obj_ptr, type_name);
            comp_data["data"] = tc::tc_value_to_trent(v);
            tc_value_free(&v);
        }
        components.push_back(std::move(comp_data));
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

    std::vector<std::pair<Entity, nos::trent>> entity_data_pairs;

    std::function<void(const nos::trent&, Entity*)> deserialize_hierarchy;
    deserialize_hierarchy = [&](const nos::trent& ent_data, Entity* parent_ent) {
        Entity ent = Entity::deserialize_base_trent(ent_data, _h);
        if (!ent.valid()) return;

        if (parent_ent && parent_ent->valid()) {
            ent.set_parent(*parent_ent);
        }

        entity_data_pairs.emplace_back(ent, ent_data);

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

    // Phase 2: Deserialize components
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
