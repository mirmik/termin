// tc_scene_bindings.cpp - Core TcSceneRef bindings (no render dependencies)
#include <termin/bindings/scene_bindings.hpp>
#include <termin/bindings/entity_helpers.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>

#include <tcbase/tc_log.hpp>
#include <termin/tc_scene.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/component_registry_python.hpp>
#include <trent/trent.h>
#include <trent/json.h>
#include "core/tc_component.h"
#include "core/tc_scene.h"

namespace nb = nanobind;

namespace termin {

// ============================================================================
// Trent <-> Python conversion helpers
// ============================================================================

static nb::object trent_to_python(const nos::trent& t) {
    switch (t.get_type()) {
        case nos::trent_type::nil:
            return nb::none();
        case nos::trent_type::boolean:
            return nb::bool_(t.as_bool());
        case nos::trent_type::numer:
            return nb::float_(static_cast<double>(t.as_numer()));
        case nos::trent_type::string:
            return nb::str(t.as_string().c_str());
        case nos::trent_type::list: {
            nb::list result;
            for (const auto& item : t.as_list()) {
                result.append(trent_to_python(item));
            }
            return result;
        }
        case nos::trent_type::dict: {
            nb::dict result;
            for (const auto& [key, value] : t.as_dict()) {
                result[nb::str(key.c_str())] = trent_to_python(value);
            }
            return result;
        }
        default:
            return nb::none();
    }
}

static nos::trent python_to_trent(nb::handle obj) {
    if (obj.is_none()) {
        return nos::trent();
    }
    if (nb::isinstance<nb::bool_>(obj)) {
        return nos::trent(nb::cast<bool>(obj));
    }
    if (nb::isinstance<nb::int_>(obj)) {
        return nos::trent(static_cast<int64_t>(nb::cast<int64_t>(obj)));
    }
    if (nb::isinstance<nb::float_>(obj)) {
        return nos::trent(nb::cast<double>(obj));
    }
    if (nb::isinstance<nb::str>(obj)) {
        return nos::trent(nb::cast<std::string>(obj));
    }
    if (nb::isinstance<nb::list>(obj) || nb::isinstance<nb::tuple>(obj)) {
        nos::trent result;
        result.init(nos::trent::type::list);
        for (auto item : obj) {
            result.push_back(python_to_trent(item));
        }
        return result;
    }
    if (nb::isinstance<nb::dict>(obj)) {
        nos::trent result;
        result.init(nos::trent::type::dict);
        for (auto [key, value] : nb::cast<nb::dict>(obj)) {
            std::string key_str = nb::cast<std::string>(nb::str(key));
            result[key_str] = python_to_trent(value);
        }
        return result;
    }
    return nos::trent(nb::cast<std::string>(nb::str(obj)));
}

// ============================================================================
// Callback helper
// ============================================================================

struct ForeachCallbackData {
    nb::object* py_callback;
    bool should_continue;
};

// ============================================================================
// Core TcSceneRef binding
// ============================================================================

void bind_tc_scene_core(nb::module_& m) {
    nb::class_<TcSceneRef>(m, "TcScene")
        .def(nb::init<>(), "Create invalid scene reference")
        .def(nb::init<tc_scene_handle>(), nb::arg("handle"),
             "Create from existing handle")
        .def_static("create", &TcSceneRef::create,
             nb::arg("name") = "", nb::arg("uuid") = "",
             "Create a new core scene (no render extensions)")
        .def_static("from_handle", [](uint32_t index, uint32_t generation) {
            tc_scene_handle h;
            h.index = index;
            h.generation = generation;
            return TcSceneRef(h);
        }, nb::arg("index"), nb::arg("generation"),
           "Create from handle (index, generation)")
        .def("destroy", [](TcSceneRef& self) {
            if (!self.is_alive()) return;

            // Call on_destroy on all components before destroying scene
            for (Entity& e : self.get_all_entities()) {
                size_t count = e.component_count();
                for (size_t i = 0; i < count; i++) {
                    tc_component* c = e.component_at(i);
                    if (c) {
                        tc_component_on_destroy(c);
                    }
                }
            }

            self.destroy();
        }, "Explicitly destroy scene and release all resources")
        .def("is_alive", &TcSceneRef::is_alive, "Check if scene is alive (not destroyed)")

        // Entity management
        .def("add_entity", &TcSceneRef::add_entity, nb::arg("entity"))
        .def("remove_entity", &TcSceneRef::remove_entity, nb::arg("entity"))
        .def("entity_count", &TcSceneRef::entity_count)

        // Component registration (C++ Component)
        .def("register_component", &TcSceneRef::register_component, nb::arg("component"))
        .def("unregister_component", &TcSceneRef::unregister_component, nb::arg("component"))

        // Component registration by pointer
        .def("register_component_ptr", &TcSceneRef::register_component_ptr, nb::arg("ptr"))
        .def("unregister_component_ptr", &TcSceneRef::unregister_component_ptr, nb::arg("ptr"))

        // Update loop
        .def("update", &TcSceneRef::update, nb::arg("dt"))
        .def("editor_update", &TcSceneRef::editor_update, nb::arg("dt"))
        .def("before_render", &TcSceneRef::before_render)

        // Fixed timestep
        .def_prop_rw("fixed_timestep", &TcSceneRef::fixed_timestep, &TcSceneRef::set_fixed_timestep)
        .def_prop_ro("accumulated_time", &TcSceneRef::accumulated_time)
        .def("reset_accumulated_time", &TcSceneRef::reset_accumulated_time)

        // Component queries
        .def_prop_ro("pending_start_count", &TcSceneRef::pending_start_count)
        .def_prop_ro("update_list_count", &TcSceneRef::update_list_count)
        .def_prop_ro("fixed_update_list_count", &TcSceneRef::fixed_update_list_count)

        // Pool access
        .def("entity_pool_ptr", [](TcSceneRef& self) {
            return reinterpret_cast<uintptr_t>(self.entity_pool());
        }, "Get scene's entity pool as uintptr_t")

        // Scene handle access
        .def("scene_handle", [](TcSceneRef& self) {
            return std::make_tuple(self._h.index, self._h.generation);
        }, "Get scene handle as (index, generation) tuple")

        // Entity creation in pool
        .def("create_entity", &TcSceneRef::create_entity, nb::arg("name") = "",
             "Create a new entity directly in scene's pool.")

        // Get all entities
        .def("get_all_entities", &TcSceneRef::get_all_entities,
             "Get all entities in scene's pool.")

        // Entity migration
        .def("migrate_entity", &TcSceneRef::migrate_entity, nb::arg("entity"),
             "Migrate entity to scene's pool. Returns new Entity, old becomes invalid.")

        // Entity lookup
        .def("get_entity", [](TcSceneRef& self, const std::string& uuid) -> nb::object {
            Entity e = self.get_entity(uuid);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("uuid"), "Find entity by UUID.")

        .def("get_entity_by_pick_id", [](TcSceneRef& self, uint32_t pick_id) -> nb::object {
            Entity e = self.get_entity_by_pick_id(pick_id);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("pick_id"), "Find entity by pick_id.")

        .def("find_entity_by_name", [](TcSceneRef& self, const std::string& name) -> nb::object {
            Entity e = self.find_entity_by_name(name);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("name"), "Find entity by name.")

        // Scene name and UUID
        .def_prop_rw("name", &TcSceneRef::name, &TcSceneRef::set_name)
        .def_prop_rw("uuid", &TcSceneRef::uuid, &TcSceneRef::set_uuid)

        // Layer names (0-63)
        .def("get_layer_name", [](TcSceneRef& self, int index) -> std::string {
            std::string name = self.get_layer_name(index);
            if (name.empty()) return "Layer " + std::to_string(index);
            return name;
        }, nb::arg("index"))
        .def("set_layer_name", &TcSceneRef::set_layer_name, nb::arg("index"), nb::arg("name"))
        .def("get_flag_name", [](TcSceneRef& self, int index) -> std::string {
            std::string name = self.get_flag_name(index);
            if (name.empty()) return "Flag " + std::to_string(index);
            return name;
        }, nb::arg("index"))
        .def("set_flag_name", &TcSceneRef::set_flag_name, nb::arg("index"), nb::arg("name"))

        .def_prop_ro("layer_names", [](TcSceneRef& self) -> nb::dict {
            nb::dict result;
            for (int i = 0; i < 64; i++) {
                std::string name = self.get_layer_name(i);
                if (!name.empty()) {
                    result[nb::int_(i)] = nb::str(name.c_str(), name.size());
                }
            }
            return result;
        })
        .def_prop_ro("flag_names", [](TcSceneRef& self) -> nb::dict {
            nb::dict result;
            for (int i = 0; i < 64; i++) {
                std::string name = self.get_flag_name(i);
                if (!name.empty()) {
                    result[nb::int_(i)] = nb::str(name.c_str(), name.size());
                }
            }
            return result;
        })

        // Metadata
        .def("get_metadata", [](TcSceneRef& self) -> nb::object {
            return trent_to_python(self.metadata());
        })
        .def("set_metadata", [](TcSceneRef& self, nb::handle data) {
            nos::trent t = python_to_trent(data);
            std::string json = nos::json::dump(t);
            self.metadata_from_json(json);
        }, nb::arg("data"))
        .def("get_metadata_value", [](TcSceneRef& self, const std::string& path) -> nb::object {
            nos::trent t = self.get_metadata_at_path(path);
            if (t.is_nil()) return nb::none();
            return trent_to_python(t);
        }, nb::arg("path"))
        .def("set_metadata_value", [](TcSceneRef& self, const std::string& path, nb::handle value) {
            self.set_metadata_at_path(path, python_to_trent(value));
        }, nb::arg("path"), nb::arg("value"))
        .def("has_metadata_value", &TcSceneRef::has_metadata_at_path, nb::arg("path"))
        .def("clear_metadata_value", [](TcSceneRef& self, const std::string& path) {
            self.set_metadata_at_path(path, nos::trent());
        }, nb::arg("path"))
        .def("metadata_to_json", &TcSceneRef::metadata_to_json)
        .def("metadata_from_json", &TcSceneRef::metadata_from_json, nb::arg("json_str"))

        // Scene mode
        .def("get_mode", [](TcSceneRef& self) {
            return tc_scene_get_mode(self._h);
        })
        .def("set_mode", [](TcSceneRef& self, tc_scene_mode mode) {
            tc_scene_set_mode(self._h, mode);
        }, nb::arg("mode"))

        // Component type iteration
        .def("count_components_of_type", [](TcSceneRef& self, const std::string& type_name) {
            return tc_scene_count_components_of_type(self._h, type_name.c_str());
        }, nb::arg("type_name"))

        .def("foreach_component_of_type", [](TcSceneRef& self, const std::string& type_name, nb::object callback) {
            ForeachCallbackData data{&callback, true};
            tc_scene_foreach_component_of_type(
                self._h, type_name.c_str(),
                [](tc_component* c, void* user_data) -> bool {
                    auto* data = static_cast<ForeachCallbackData*>(user_data);
                    if (!data->should_continue) return false;
                    nb::object py_comp = tc_component_to_python(c);
                    if (py_comp.is_none()) return true;
                    try {
                        nb::object result = (*data->py_callback)(py_comp);
                        if (!result.is_none() && nb::isinstance<nb::bool_>(result)) {
                            data->should_continue = nb::cast<bool>(result);
                        }
                    } catch (const std::exception& e) {
                        tc::Log::error("Error in foreach callback: %s", e.what());
                        data->should_continue = false;
                    }
                    return data->should_continue;
                },
                &data);
        }, nb::arg("type_name"), nb::arg("callback"))

        .def("get_components_of_type", [](TcSceneRef& self, const std::string& type_name) {
            nb::list result;
            tc_scene_foreach_component_of_type(
                self._h, type_name.c_str(),
                [](tc_component* c, void* user_data) -> bool {
                    auto* list = static_cast<nb::list*>(user_data);
                    nb::object py_comp = tc_component_to_python(c);
                    if (!py_comp.is_none()) list->append(py_comp);
                    return true;
                },
                &result);
            return result;
        }, nb::arg("type_name"))

        .def("find_component_by_name", [](TcSceneRef& self, const std::string& class_name) -> nb::object {
            nb::object result = nb::none();
            tc_scene_foreach_component_of_type(
                self._h, class_name.c_str(),
                [](tc_component* c, void* user_data) -> bool {
                    auto* result_ptr = static_cast<nb::object*>(user_data);
                    nb::object py_comp = tc_component_to_python(c);
                    if (!py_comp.is_none()) {
                        *result_ptr = py_comp;
                        return false;
                    }
                    return true;
                },
                &result);
            return result;
        }, nb::arg("class_name"))

        .def("get_component_type_counts", [](TcSceneRef& self) {
            nb::dict result;
            size_t count = 0;
            tc_scene_component_type* types = tc_scene_get_all_component_types(self._h, &count);
            if (types) {
                for (size_t i = 0; i < count; i++) {
                    result[nb::str(types[i].type_name)] = types[i].count;
                }
                free(types);
            }
            return result;
        })

        // Scene lifecycle notifications
        .def("notify_editor_start", [](TcSceneRef& self) {
            tc_scene_notify_editor_start(self._h);
        })
        .def("notify_scene_inactive", [](TcSceneRef& self) {
            tc_scene_notify_scene_inactive(self._h);
        })
        .def("notify_scene_active", [](TcSceneRef& self) {
            tc_scene_notify_scene_active(self._h);
        })
        .def("notify_render_attach", [](TcSceneRef& self) {
            tc_scene_notify_render_attach(self._h);
        })
        .def("notify_render_detach", [](TcSceneRef& self) {
            tc_scene_notify_render_detach(self._h);
        })

        // Serialization
        .def("serialize", [](TcSceneRef& self) -> nb::object {
            return trent_to_python(self.serialize());
        })
        .def("load_from_data", [](TcSceneRef& self, nb::handle data, nb::object context, bool update_settings) -> int {
            (void)context;
            nos::trent t = python_to_trent(data);
            return self.load_from_data(t, update_settings);
        }, nb::arg("data"), nb::arg("context") = nb::none(), nb::arg("update_settings") = true)
        .def("to_json_string", &TcSceneRef::to_json_string)
        .def("from_json_string", &TcSceneRef::from_json_string, nb::arg("json"))

        // Convenience
        .def_prop_ro("is_destroyed", [](TcSceneRef& self) {
            return !self.is_alive();
        })
        .def_prop_ro("entities", [](TcSceneRef& self) {
            return self.get_all_entities();
        })

        // Entity management with callbacks
        .def("add", [](TcSceneRef& self, Entity& entity) -> Entity {
            Entity migrated = self.migrate_entity(entity);
            if (!migrated.valid()) {
                throw std::runtime_error("Failed to migrate entity to scene's pool");
            }
            return migrated;
        }, nb::arg("entity"))

        .def("remove", [](TcSceneRef& self, Entity& entity) {
            if (!entity.valid()) return;
            size_t count = entity.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* c = entity.component_at(i);
                if (c) tc_component_on_removed(c);
            }
            self.remove_entity(entity);
        }, nb::arg("entity"))

        // Input dispatch (generic: iterates input handlers and calls method by name)
        .def("dispatch_input", [](TcSceneRef& self, const std::string& method_name, nb::object event, bool editor_mode) {
            if (!self.is_alive()) return;

            int filter_flags = TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED;
            if (editor_mode) {
                filter_flags |= TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR;
            }

            std::vector<nb::object> handlers;
            tc_scene_foreach_input_handler(
                self._h,
                [](tc_component* c, void* user_data) -> bool {
                    auto* vec = static_cast<std::vector<nb::object>*>(user_data);
                    nb::object py_comp = tc_component_to_python(c);
                    if (!py_comp.is_none()) {
                        vec->push_back(py_comp);
                    }
                    return true;
                },
                &handlers,
                filter_flags
            );

            for (auto& handler : handlers) {
                try {
                    if (nb::hasattr(handler, method_name.c_str())) {
                        handler.attr(method_name.c_str())(event);
                    }
                } catch (const std::exception& e) {
                    tc::Log::error("Error in input handler %s: %s", method_name.c_str(), e.what());
                }
            }
        }, nb::arg("method_name"), nb::arg("event"), nb::arg("editor_mode") = false,
           "Dispatch input event to all input handlers in scene");
}

} // namespace termin
