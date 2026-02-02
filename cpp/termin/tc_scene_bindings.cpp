// tc_scene_bindings.cpp - Python bindings for TcScene
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>

#include "tc_scene.hpp"
#include "entity/component.hpp"
#include "bindings/entity/entity_helpers.hpp"
#include "mesh/tc_mesh_handle.hpp"
#include "material/tc_material_handle.hpp"
#include "input/input_events.hpp"
#include "scene_bindings.hpp"
#include "render/rendering_manager.hpp"
#include "render/scene_pipeline_template.hpp"
#include "collision/collision_world.hpp"
#include "colliders/collider_component.hpp"
#include "geom/ray3.hpp"
#include "../../core_c/include/tc_scene_lighting.h"
#include "../../core_c/include/tc_scene_skybox.h"

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
    // Fallback: convert to string
    return nos::trent(nb::cast<std::string>(nb::str(obj)));
}

// ============================================================================
// Helper structs for callbacks (defined outside lambdas for MSVC compatibility)
// ============================================================================

struct ForeachCallbackData {
    nb::object* py_callback;
    bool should_continue;
};

// Forward declaration for dispatch_input_to_scene (defined at end of file)
template<typename EventT>
void dispatch_input_to_scene(tc_scene_handle h, const char* method_name, const EventT& event, bool editor_mode);

// ============================================================================
// Python bindings
// ============================================================================

void bind_tc_scene(nb::module_& m) {
    // SceneRaycastHit binding
    nb::class_<SceneRaycastHit>(m, "SceneRaycastHit")
        .def_prop_ro("valid", &SceneRaycastHit::valid)
        .def_prop_ro("entity", [](const SceneRaycastHit& h) -> nb::object {
            if (!h.valid()) return nb::none();
            return nb::cast(Entity(h.pool, h.entity_id));
        })
        .def_prop_ro("component", [](const SceneRaycastHit& h) -> nb::object {
            if (!h.component) return nb::none();
            return nb::cast(h.component, nb::rv_policy::reference);
        })
        .def_prop_ro("point_on_ray", [](const SceneRaycastHit& h) {
            return std::make_tuple(h.point_on_ray[0], h.point_on_ray[1], h.point_on_ray[2]);
        })
        .def_prop_ro("point_on_collider", [](const SceneRaycastHit& h) {
            return std::make_tuple(h.point_on_collider[0], h.point_on_collider[1], h.point_on_collider[2]);
        })
        .def_ro("distance", &SceneRaycastHit::distance);

    nb::class_<TcScene>(m, "TcScene")
        .def(nb::init<>())
        .def("destroy", &TcScene::destroy, "Explicitly release tc_scene resources")
        .def("is_alive", &TcScene::is_alive, "Check if scene is alive (not destroyed)")
        .def("scene_ref", &TcScene::scene_ref, "Get non-owning reference to this scene")

        // Entity management
        .def("add_entity", &TcScene::add_entity, nb::arg("entity"))
        .def("remove_entity", &TcScene::remove_entity, nb::arg("entity"))
        .def("entity_count", &TcScene::entity_count)

        // Component registration (C++ Component)
        .def("register_component", &TcScene::register_component, nb::arg("component"))
        .def("unregister_component", &TcScene::unregister_component, nb::arg("component"))

        // Component registration by pointer (for pure Python components)
        .def("register_component_ptr", &TcScene::register_component_ptr, nb::arg("ptr"))
        .def("unregister_component_ptr", &TcScene::unregister_component_ptr, nb::arg("ptr"))

        // Update loop
        .def("update", &TcScene::update, nb::arg("dt"))
        .def("editor_update", &TcScene::editor_update, nb::arg("dt"))
        .def("before_render", &TcScene::before_render)

        // Fixed timestep
        .def_prop_rw("fixed_timestep", &TcScene::fixed_timestep, &TcScene::set_fixed_timestep)
        .def_prop_ro("accumulated_time", &TcScene::accumulated_time)
        .def("reset_accumulated_time", &TcScene::reset_accumulated_time)

        // Component queries
        .def_prop_ro("pending_start_count", &TcScene::pending_start_count)
        .def_prop_ro("update_list_count", &TcScene::update_list_count)
        .def_prop_ro("fixed_update_list_count", &TcScene::fixed_update_list_count)

        // Pool access
        .def("entity_pool_ptr", [](TcScene& self) {
            return reinterpret_cast<uintptr_t>(self.entity_pool());
        }, "Get scene's entity pool as uintptr_t")

        // Scene handle access (for debugging)
        .def("scene_handle", [](TcScene& self) {
            return std::make_tuple(self._h.index, self._h.generation);
        }, "Get scene handle as (index, generation) tuple")

        // Entity creation in pool
        .def("create_entity", &TcScene::create_entity, nb::arg("name") = "",
             "Create a new entity directly in scene's pool.")

        // Get all entities
        .def("get_all_entities", &TcScene::get_all_entities,
             "Get all entities in scene's pool.")

        // Entity migration
        .def("migrate_entity", &TcScene::migrate_entity, nb::arg("entity"),
             "Migrate entity to scene's pool. Returns new Entity, old becomes invalid.")

        // Entity lookup
        .def("get_entity", [](TcScene& self, const std::string& uuid) -> nb::object {
            Entity e = self.get_entity(uuid);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("uuid"), "Find entity by UUID. Returns None if not found.")

        .def("get_entity_by_pick_id", [](TcScene& self, uint32_t pick_id) -> nb::object {
            Entity e = self.get_entity_by_pick_id(pick_id);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("pick_id"), "Find entity by pick_id. Returns None if not found.")

        .def("find_entity_by_name", [](TcScene& self, const std::string& name) -> nb::object {
            Entity e = self.find_entity_by_name(name);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("name"), "Find entity by name. Returns None if not found.")

        // Scene name and UUID
        .def_prop_rw("name", &TcScene::name, &TcScene::set_name)
        .def_prop_rw("uuid", &TcScene::uuid, &TcScene::set_uuid)

        // Layer and flag names (0-63)
        .def("get_layer_name", &TcScene::get_layer_name, nb::arg("index"),
             "Get layer name by index (0-63), empty string if not set")
        .def("set_layer_name", &TcScene::set_layer_name, nb::arg("index"), nb::arg("name"),
             "Set layer name by index (0-63), empty string removes")
        .def("get_flag_name", &TcScene::get_flag_name, nb::arg("index"),
             "Get flag name by index (0-63), empty string if not set")
        .def("set_flag_name", &TcScene::set_flag_name, nb::arg("index"), nb::arg("name"),
             "Set flag name by index (0-63), empty string removes")

        // Background color (RGBA)
        .def("get_background_color", &TcScene::get_background_color,
             "Get background color as (r, g, b, a) tuple")
        .def("set_background_color", &TcScene::set_background_color,
             nb::arg("r"), nb::arg("g"), nb::arg("b"), nb::arg("a"),
             "Set background color RGBA")

        // Viewport configurations
        .def("add_viewport_config", &TcScene::add_viewport_config,
             nb::arg("name"), nb::arg("display_name"), nb::arg("camera_uuid"),
             nb::arg("x"), nb::arg("y"), nb::arg("w"), nb::arg("h"),
             nb::arg("pipeline_uuid"), nb::arg("pipeline_name"),
             nb::arg("depth"), nb::arg("input_mode"), nb::arg("block_input_in_editor"),
             nb::arg("layer_mask"), nb::arg("enabled"),
             "Add a viewport configuration")
        .def("remove_viewport_config", &TcScene::remove_viewport_config,
             nb::arg("index"), "Remove viewport configuration by index")
        .def("clear_viewport_configs", &TcScene::clear_viewport_configs,
             "Clear all viewport configurations")
        .def("viewport_config_count", &TcScene::viewport_config_count,
             "Get number of viewport configurations")
        .def("get_viewport_config", [](TcScene& self, size_t index) -> nb::dict {
            tc_viewport_config* config = tc_scene_viewport_config_at(self._h, index);
            if (!config) return nb::dict();
            nb::dict d;
            d["name"] = config->name ? std::string(config->name) : "";
            d["display_name"] = config->display_name ? std::string(config->display_name) : "Main";
            d["camera_uuid"] = config->camera_uuid ? std::string(config->camera_uuid) : "";
            d["region"] = std::make_tuple(config->region[0], config->region[1], config->region[2], config->region[3]);
            d["pipeline_uuid"] = config->pipeline_uuid ? std::string(config->pipeline_uuid) : "";
            d["pipeline_name"] = config->pipeline_name ? std::string(config->pipeline_name) : "";
            d["depth"] = config->depth;
            d["input_mode"] = config->input_mode ? std::string(config->input_mode) : "simple";
            d["block_input_in_editor"] = config->block_input_in_editor;
            d["layer_mask"] = config->layer_mask;
            d["enabled"] = config->enabled;
            return d;
        }, nb::arg("index"), "Get viewport configuration as dict")

        // Metadata (trent stored in C++, converted to Python at boundary)
        .def("get_metadata", [](TcScene& self) -> nb::object {
            return trent_to_python(self.metadata());
        }, "Get all metadata as Python dict")
        .def("set_metadata", [](TcScene& self, nb::handle data) {
            self._metadata = python_to_trent(data);
        }, nb::arg("data"), "Set all metadata from Python dict")
        .def("get_metadata_value", [](TcScene& self, const std::string& path) -> nb::object {
            const nos::trent* t = self.get_metadata_at_path(path);
            if (!t) return nb::none();
            return trent_to_python(*t);
        }, nb::arg("path"), "Get metadata value at path (e.g. 'termin.editor.camera_name')")
        .def("set_metadata_value", [](TcScene& self, const std::string& path, nb::handle value) {
            self.set_metadata_at_path(path, python_to_trent(value));
        }, nb::arg("path"), nb::arg("value"), "Set metadata value at path")
        .def("has_metadata_value", &TcScene::has_metadata_at_path,
             nb::arg("path"), "Check if metadata value exists at path")
        .def("clear_metadata_value", [](TcScene& self, const std::string& path) {
            self.set_metadata_at_path(path, nos::trent());
        }, nb::arg("path"), "Clear metadata value at path (set to None)")
        .def("metadata_to_json", &TcScene::metadata_to_json,
             "Serialize metadata to JSON string")
        .def("metadata_from_json", &TcScene::metadata_from_json,
             nb::arg("json_str"), "Load metadata from JSON string")

        // Scene mode
        .def("get_mode", [](TcScene& self) {
            return tc_scene_get_mode(self._h);
        }, "Get scene mode (INACTIVE, STOP, PLAY)")
        .def("set_mode", [](TcScene& self, tc_scene_mode mode) {
            tc_scene_set_mode(self._h, mode);
        }, nb::arg("mode"), "Set scene mode")

        // Python wrapper for callbacks
        .def("set_py_wrapper", [](TcScene& self, nb::object wrapper) {
            tc::Log::info("[TcScene] set_py_wrapper handle=(%u,%u), py_wrapper=%p",
                         self._h.index, self._h.generation, (void*)wrapper.ptr());
            tc_scene_set_py_wrapper(self._h, wrapper.ptr());
        }, nb::arg("wrapper"), "Set Python Scene wrapper for component auto-registration")

        // Skybox type
        .def("get_skybox_type", [](TcScene& self) -> int {
            return tc_scene_get_skybox_type(self._h);
        })
        .def("set_skybox_type", [](TcScene& self, int type) {
            tc_scene_set_skybox_type(self._h, type);
        })

        // Skybox colors
        .def("get_skybox_color", [](TcScene& self) -> std::tuple<float, float, float> {
            float r, g, b;
            tc_scene_get_skybox_color(self._h, &r, &g, &b);
            return {r, g, b};
        })
        .def("set_skybox_color", [](TcScene& self, float r, float g, float b) {
            tc_scene_set_skybox_color(self._h, r, g, b);
        })
        .def("get_skybox_top_color", [](TcScene& self) -> std::tuple<float, float, float> {
            float r, g, b;
            tc_scene_get_skybox_top_color(self._h, &r, &g, &b);
            return {r, g, b};
        })
        .def("set_skybox_top_color", [](TcScene& self, float r, float g, float b) {
            tc_scene_set_skybox_top_color(self._h, r, g, b);
        })
        .def("get_skybox_bottom_color", [](TcScene& self) -> std::tuple<float, float, float> {
            float r, g, b;
            tc_scene_get_skybox_bottom_color(self._h, &r, &g, &b);
            return {r, g, b};
        })
        .def("set_skybox_bottom_color", [](TcScene& self, float r, float g, float b) {
            tc_scene_set_skybox_bottom_color(self._h, r, g, b);
        })

        // Skybox mesh (lazy creation)
        .def("get_skybox_mesh", [](TcScene& self) -> TcMesh {
            tc_mesh* mesh = tc_scene_get_skybox_mesh(self._h);
            return TcMesh(mesh);
        })
        .def("ensure_skybox_material", [](TcScene& self, int skybox_type) -> TcMaterial {
            tc_scene_skybox* skybox = tc_scene_get_skybox(self._h);
            if (!skybox) return TcMaterial(nullptr);

            tc_material* mat = tc_scene_skybox_ensure_material(skybox, skybox_type);
            if (mat) {
                tc_scene_set_skybox_material(self._h, mat);
            }
            return TcMaterial(mat);
        }, nb::arg("skybox_type"))

        // Lighting access
        .def("lighting_ptr", [](TcScene& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self.lighting());
        })

        // Collision world
        .def_prop_ro("collision_world", &TcScene::collision_world,
                     nb::rv_policy::reference_internal)

        // Raycast methods
        .def("raycast", &TcScene::raycast, nb::arg("ray"),
             "Find first intersection with a collider (distance == 0)")
        .def("closest_to_ray", &TcScene::closest_to_ray, nb::arg("ray"),
             "Find closest collider to ray (minimum distance)")

        // Component type iteration
        .def("count_components_of_type", [](TcScene& self, const std::string& type_name) {
            return tc_scene_count_components_of_type(self._h, type_name.c_str());
        }, nb::arg("type_name"))

        .def("foreach_component_of_type", [](TcScene& self, const std::string& type_name, nb::object callback) {
            ForeachCallbackData data{&callback, true};

            tc_scene_foreach_component_of_type(
                self._h,
                type_name.c_str(),
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
                &data
            );
        }, nb::arg("type_name"), nb::arg("callback"))

        .def("get_components_of_type", [](TcScene& self, const std::string& type_name) {
            nb::list result;
            tc_scene_foreach_component_of_type(
                self._h,
                type_name.c_str(),
                [](tc_component* c, void* user_data) -> bool {
                    auto* list = static_cast<nb::list*>(user_data);
                    nb::object py_comp = tc_component_to_python(c);
                    if (!py_comp.is_none()) {
                        list->append(py_comp);
                    }
                    return true;
                },
                &result
            );
            return result;
        }, nb::arg("type_name"))

        .def("get_component_type_counts", [](TcScene& self) {
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
        .def("notify_editor_start", [](TcScene& self) {
            tc_scene_notify_editor_start(self._h);
        })
        .def("notify_scene_inactive", [](TcScene& self) {
            tc_scene_notify_scene_inactive(self._h);
        })
        .def("notify_scene_active", [](TcScene& self) {
            tc_scene_notify_scene_active(self._h);
        })

        // Input dispatch
        .def("dispatch_mouse_button", [](TcScene& self, const MouseButtonEvent& event) {
            dispatch_input_to_scene(self._h, "on_mouse_button", event, false);
        }, nb::arg("event"))
        .def("dispatch_mouse_move", [](TcScene& self, const MouseMoveEvent& event) {
            dispatch_input_to_scene(self._h, "on_mouse_move", event, false);
        }, nb::arg("event"))
        .def("dispatch_scroll", [](TcScene& self, const ScrollEvent& event) {
            dispatch_input_to_scene(self._h, "on_scroll", event, false);
        }, nb::arg("event"))
        .def("dispatch_key", [](TcScene& self, const KeyEvent& event) {
            dispatch_input_to_scene(self._h, "on_key", event, false);
        }, nb::arg("event"))

        .def("dispatch_mouse_button_editor", [](TcScene& self, const MouseButtonEvent& event) {
            dispatch_input_to_scene(self._h, "on_mouse_button", event, true);
        }, nb::arg("event"))
        .def("dispatch_mouse_move_editor", [](TcScene& self, const MouseMoveEvent& event) {
            dispatch_input_to_scene(self._h, "on_mouse_move", event, true);
        }, nb::arg("event"))
        .def("dispatch_scroll_editor", [](TcScene& self, const ScrollEvent& event) {
            dispatch_input_to_scene(self._h, "on_scroll", event, true);
        }, nb::arg("event"))
        .def("dispatch_key_editor", [](TcScene& self, const KeyEvent& event) {
            dispatch_input_to_scene(self._h, "on_key", event, true);
        }, nb::arg("event"))

        // Pipeline templates
        .def("add_pipeline_template", &TcScene::add_pipeline_template, nb::arg("template"))
        .def("clear_pipeline_templates", &TcScene::clear_pipeline_templates)
        .def("pipeline_template_count", &TcScene::pipeline_template_count)
        .def("pipeline_template_at", &TcScene::pipeline_template_at, nb::arg("index"))

        // Compiled pipelines (from RenderingManager)
        .def("get_pipeline", &TcScene::get_pipeline, nb::arg("name"),
             nb::rv_policy::reference)
        .def("get_pipeline_names", &TcScene::get_pipeline_names)
        .def("get_pipeline_targets", &TcScene::get_pipeline_targets, nb::arg("name"),
             nb::rv_policy::reference);
}

// ============================================================================
// Input dispatch helpers
// ============================================================================

static std::vector<nb::object> collect_input_handlers(tc_scene_handle h, bool editor_mode) {
    std::vector<nb::object> result;
    if (!tc_scene_alive(h)) return result;

    int filter_flags = TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED;
    if (editor_mode) {
        filter_flags |= TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR;
    }

    tc_scene_foreach_input_handler(
        h,
        [](tc_component* c, void* user_data) -> bool {
            auto* vec = static_cast<std::vector<nb::object>*>(user_data);
            nb::object py_comp = tc_component_to_python(c);
            if (!py_comp.is_none()) {
                vec->push_back(py_comp);
            }
            return true;
        },
        &result,
        filter_flags
    );

    return result;
}

template<typename EventT>
void dispatch_input_to_scene(tc_scene_handle h, const char* method_name, const EventT& event, bool editor_mode) {
    auto handlers = collect_input_handlers(h, editor_mode);

    for (auto& handler : handlers) {
        try {
            if (nb::hasattr(handler, method_name)) {
                handler.attr(method_name)(event);
            }
        } catch (const std::exception& e) {
            tc::Log::error("Error in input handler %s: %s", method_name, e.what());
        }
    }
}

// Explicit instantiations
template void dispatch_input_to_scene<MouseButtonEvent>(tc_scene_handle, const char*, const MouseButtonEvent&, bool);
template void dispatch_input_to_scene<MouseMoveEvent>(tc_scene_handle, const char*, const MouseMoveEvent&, bool);
template void dispatch_input_to_scene<ScrollEvent>(tc_scene_handle, const char*, const ScrollEvent&, bool);
template void dispatch_input_to_scene<KeyEvent>(tc_scene_handle, const char*, const KeyEvent&, bool);

} // namespace termin
