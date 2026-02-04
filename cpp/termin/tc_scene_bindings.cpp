// tc_scene_bindings.cpp - Python bindings for TcSceneRef
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>

#include "termin/tc_scene.hpp"
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
#include "geom/vec3.hpp"
#include "geom/vec4.hpp"
#include "render/tc_value_trent.hpp"
#include "tc_scene_lighting.h"
#include "tc_scene_skybox.h"
#include "tc_component.h"

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
    // ViewportConfig binding
    nb::class_<ViewportConfig>(m, "ViewportConfig")
        .def(nb::init<>())
        .def(nb::init<const std::string&, const std::string&, const std::string&,
                      float, float, float, float,
                      const std::string&, const std::string&,
                      int, const std::string&, bool, uint64_t, bool>(),
             nb::arg("name") = "",
             nb::arg("display_name") = "Main",
             nb::arg("camera_uuid") = "",
             nb::arg("region_x") = 0.0f,
             nb::arg("region_y") = 0.0f,
             nb::arg("region_w") = 1.0f,
             nb::arg("region_h") = 1.0f,
             nb::arg("pipeline_uuid") = "",
             nb::arg("pipeline_name") = "",
             nb::arg("depth") = 0,
             nb::arg("input_mode") = "simple",
             nb::arg("block_input_in_editor") = false,
             nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL,
             nb::arg("enabled") = true)
        .def_rw("name", &ViewportConfig::name)
        .def_rw("display_name", &ViewportConfig::display_name)
        .def_rw("camera_uuid", &ViewportConfig::camera_uuid)
        .def_rw("region_x", &ViewportConfig::region_x)
        .def_rw("region_y", &ViewportConfig::region_y)
        .def_rw("region_w", &ViewportConfig::region_w)
        .def_rw("region_h", &ViewportConfig::region_h)
        .def_rw("pipeline_uuid", &ViewportConfig::pipeline_uuid)
        .def_rw("pipeline_name", &ViewportConfig::pipeline_name)
        .def_rw("depth", &ViewportConfig::depth)
        .def_rw("input_mode", &ViewportConfig::input_mode)
        .def_rw("block_input_in_editor", &ViewportConfig::block_input_in_editor)
        .def_rw("layer_mask", &ViewportConfig::layer_mask)
        .def_rw("enabled", &ViewportConfig::enabled)
        .def_prop_ro("region", &ViewportConfig::region,
                     "Get region as (x, y, w, h) tuple")
        .def("set_region", &ViewportConfig::set_region,
             nb::arg("x"), nb::arg("y"), nb::arg("w"), nb::arg("h"),
             "Set region (x, y, width, height)");

    // SceneRaycastHit binding
    nb::class_<SceneRaycastHit>(m, "SceneRaycastHit")
        .def_prop_ro("valid", &SceneRaycastHit::valid)
        .def_prop_ro("entity", [](const SceneRaycastHit& h) -> nb::object {
            if (!h.valid()) return nb::none();
            return nb::cast(Entity(h.entity));
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

    nb::class_<TcSceneRef>(m, "TcScene")
        .def(nb::init<>(), "Create invalid scene reference")
        .def(nb::init<tc_scene_handle>(), nb::arg("handle"),
             "Create from existing handle")
        .def_static("create", &TcSceneRef::create,
             nb::arg("name") = "", nb::arg("uuid") = "",
             "Create a new scene in the pool")
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

        // Component registration by pointer (for pure Python components)
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

        // Scene handle access (for debugging)
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
        }, nb::arg("uuid"), "Find entity by UUID. Returns None if not found.")

        .def("get_entity_by_pick_id", [](TcSceneRef& self, uint32_t pick_id) -> nb::object {
            Entity e = self.get_entity_by_pick_id(pick_id);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("pick_id"), "Find entity by pick_id. Returns None if not found.")

        .def("find_entity_by_name", [](TcSceneRef& self, const std::string& name) -> nb::object {
            Entity e = self.find_entity_by_name(name);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("name"), "Find entity by name. Returns None if not found.")

        // Scene name and UUID
        .def_prop_rw("name", &TcSceneRef::name, &TcSceneRef::set_name)
        .def_prop_rw("uuid", &TcSceneRef::uuid, &TcSceneRef::set_uuid)

        // Layer and flag names (0-63) - with default names
        .def("get_layer_name", [](TcSceneRef& self, int index) -> std::string {
            std::string name = self.get_layer_name(index);
            if (name.empty()) {
                return "Layer " + std::to_string(index);
            }
            return name;
        }, nb::arg("index"),
             "Get layer name by index (0-63), returns 'Layer N' if not set")
        .def("set_layer_name", &TcSceneRef::set_layer_name, nb::arg("index"), nb::arg("name"),
             "Set layer name by index (0-63), empty string removes")
        .def("get_flag_name", [](TcSceneRef& self, int index) -> std::string {
            std::string name = self.get_flag_name(index);
            if (name.empty()) {
                return "Flag " + std::to_string(index);
            }
            return name;
        }, nb::arg("index"),
             "Get flag name by index (0-63), returns 'Flag N' if not set")
        .def("set_flag_name", &TcSceneRef::set_flag_name, nb::arg("index"), nb::arg("name"),
             "Set flag name by index (0-63), empty string removes")

        // Background color (RGBA)
        .def("get_background_color", &TcSceneRef::get_background_color,
             "Get background color as (r, g, b, a) tuple")
        .def("set_background_color", static_cast<void(TcSceneRef::*)(float,float,float,float)>(&TcSceneRef::set_background_color),
             nb::arg("r"), nb::arg("g"), nb::arg("b"), nb::arg("a"),
             "Set background color RGBA")

        // Background color as Vec4 property
        .def_prop_rw("background_color",
            &TcSceneRef::background_color,
            static_cast<void(TcSceneRef::*)(const Vec4&)>(&TcSceneRef::set_background_color),
            "Background color as Vec4 (RGBA)")

        // Skybox colors as Vec3 properties
        .def_prop_rw("skybox_color",
            static_cast<Vec3(TcSceneRef::*)() const>(&TcSceneRef::skybox_color),
            static_cast<void(TcSceneRef::*)(const Vec3&)>(&TcSceneRef::set_skybox_color),
            "Skybox color as Vec3 (RGB)")
        .def_prop_rw("skybox_top_color",
            &TcSceneRef::skybox_top_color,
            static_cast<void(TcSceneRef::*)(const Vec3&)>(&TcSceneRef::set_skybox_top_color),
            "Skybox top color as Vec3 (RGB)")
        .def_prop_rw("skybox_bottom_color",
            &TcSceneRef::skybox_bottom_color,
            static_cast<void(TcSceneRef::*)(const Vec3&)>(&TcSceneRef::set_skybox_bottom_color),
            "Skybox bottom color as Vec3 (RGB)")

        // Ambient lighting as Vec3 property
        .def_prop_rw("ambient_color",
            &TcSceneRef::ambient_color,
            &TcSceneRef::set_ambient_color,
            "Ambient color as Vec3 (RGB)")
        .def_prop_rw("ambient_intensity",
            &TcSceneRef::ambient_intensity,
            &TcSceneRef::set_ambient_intensity,
            "Ambient light intensity")

        // Viewport configurations (stored in C++ TcScene)
        .def("add_viewport_config", &TcSceneRef::add_viewport_config,
             nb::arg("config"), "Add a viewport configuration")
        .def("remove_viewport_config", &TcSceneRef::remove_viewport_config,
             nb::arg("index"), "Remove viewport configuration by index")
        .def("clear_viewport_configs", &TcSceneRef::clear_viewport_configs,
             "Clear all viewport configurations")
        .def("viewport_config_count", &TcSceneRef::viewport_config_count,
             "Get number of viewport configurations")
        .def("viewport_config_at", [](TcSceneRef& self, size_t index) -> nb::object {
            if (index >= self.viewport_config_count()) return nb::none();
            return nb::cast(self.viewport_config_at(index));
        }, nb::arg("index"), "Get viewport configuration by index")
        .def_prop_ro("viewport_configs", [](TcSceneRef& self) {
            return self.viewport_configs();
        }, "Get all viewport configurations")

        // Metadata (trent stored in C++, converted to Python at boundary)
        .def("get_metadata", [](TcSceneRef& self) -> nb::object {
            return trent_to_python(self.metadata());
        }, "Get all metadata as Python dict")
        .def("set_metadata", [](TcSceneRef& self, nb::handle data) {
            nos::trent t = python_to_trent(data);
            tc_value new_val = tc::trent_to_tc_value(t);
            tc_scene_set_metadata(self._h, new_val);
        }, nb::arg("data"), "Set all metadata from Python dict")
        .def("get_metadata_value", [](TcSceneRef& self, const std::string& path) -> nb::object {
            nos::trent t = self.get_metadata_at_path(path);
            if (t.is_nil()) return nb::none();
            return trent_to_python(t);
        }, nb::arg("path"), "Get metadata value at path (e.g. 'termin.editor.camera_name')")
        .def("set_metadata_value", [](TcSceneRef& self, const std::string& path, nb::handle value) {
            self.set_metadata_at_path(path, python_to_trent(value));
        }, nb::arg("path"), nb::arg("value"), "Set metadata value at path")
        .def("has_metadata_value", &TcSceneRef::has_metadata_at_path,
             nb::arg("path"), "Check if metadata value exists at path")
        .def("clear_metadata_value", [](TcSceneRef& self, const std::string& path) {
            self.set_metadata_at_path(path, nos::trent());
        }, nb::arg("path"), "Clear metadata value at path (set to None)")
        .def("metadata_to_json", &TcSceneRef::metadata_to_json,
             "Serialize metadata to JSON string")
        .def("metadata_from_json", &TcSceneRef::metadata_from_json,
             nb::arg("json_str"), "Load metadata from JSON string")

        // Scene mode
        .def("get_mode", [](TcSceneRef& self) {
            return tc_scene_get_mode(self._h);
        }, "Get scene mode (INACTIVE, STOP, PLAY)")
        .def("set_mode", [](TcSceneRef& self, tc_scene_mode mode) {
            tc_scene_set_mode(self._h, mode);
        }, nb::arg("mode"), "Set scene mode")

        // Skybox type
        .def("get_skybox_type", [](TcSceneRef& self) -> int {
            return tc_scene_get_skybox_type(self._h);
        })
        .def("set_skybox_type", [](TcSceneRef& self, int type) {
            tc_scene_set_skybox_type(self._h, type);
        })

        // Skybox colors
        .def("get_skybox_color", [](TcSceneRef& self) -> std::tuple<float, float, float> {
            float r, g, b;
            tc_scene_get_skybox_color(self._h, &r, &g, &b);
            return {r, g, b};
        })
        .def("set_skybox_color", [](TcSceneRef& self, float r, float g, float b) {
            tc_scene_set_skybox_color(self._h, r, g, b);
        })
        .def("get_skybox_top_color", [](TcSceneRef& self) -> std::tuple<float, float, float> {
            float r, g, b;
            tc_scene_get_skybox_top_color(self._h, &r, &g, &b);
            return {r, g, b};
        })
        .def("set_skybox_top_color", [](TcSceneRef& self, float r, float g, float b) {
            tc_scene_set_skybox_top_color(self._h, r, g, b);
        })
        .def("get_skybox_bottom_color", [](TcSceneRef& self) -> std::tuple<float, float, float> {
            float r, g, b;
            tc_scene_get_skybox_bottom_color(self._h, &r, &g, &b);
            return {r, g, b};
        })
        .def("set_skybox_bottom_color", [](TcSceneRef& self, float r, float g, float b) {
            tc_scene_set_skybox_bottom_color(self._h, r, g, b);
        })

        // Skybox mesh (lazy creation)
        .def("get_skybox_mesh", [](TcSceneRef& self) -> TcMesh {
            tc_mesh* mesh = tc_scene_get_skybox_mesh(self._h);
            return TcMesh(mesh);
        })
        .def("skybox_mesh", [](TcSceneRef& self) -> TcMesh {
            tc_mesh* mesh = tc_scene_get_skybox_mesh(self._h);
            return TcMesh(mesh);
        })
        .def("skybox_material", [](TcSceneRef& self) -> TcMaterial {
            tc_material* mat = tc_scene_get_skybox_material(self._h);
            return TcMaterial(mat);
        })
        .def("ensure_skybox_material", [](TcSceneRef& self, int skybox_type) -> TcMaterial {
            tc_scene_skybox* skybox = tc_scene_get_skybox(self._h);
            if (!skybox) return TcMaterial(nullptr);

            // ensure_material already sets skybox->material internally
            tc_material* mat = tc_scene_skybox_ensure_material(skybox, skybox_type);
            return TcMaterial(mat);
        }, nb::arg("skybox_type"))

        // Lighting access
        .def("lighting_ptr", [](TcSceneRef& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self.lighting());
        })
        .def("lighting", [](TcSceneRef& self) -> nb::object {
            uintptr_t ptr = reinterpret_cast<uintptr_t>(self.lighting());
            if (ptr == 0) return nb::none();
            // Get TcSceneLighting class from module and construct instance
            nb::module_ scene_module = nb::module_::import_("termin._native.scene");
            nb::object cls = scene_module.attr("TcSceneLighting");
            return cls(ptr);
        }, "Get TcSceneLighting view for scene lighting properties")

        // Collision world
        .def_prop_ro("collision_world", &TcSceneRef::collision_world,
                     nb::rv_policy::reference_internal)

        // Raycast methods
        .def("raycast", &TcSceneRef::raycast, nb::arg("ray"),
             "Find first intersection with a collider (distance == 0)")
        .def("closest_to_ray", &TcSceneRef::closest_to_ray, nb::arg("ray"),
             "Find closest collider to ray (minimum distance)")

        // Component type iteration
        .def("count_components_of_type", [](TcSceneRef& self, const std::string& type_name) {
            return tc_scene_count_components_of_type(self._h, type_name.c_str());
        }, nb::arg("type_name"))

        .def("foreach_component_of_type", [](TcSceneRef& self, const std::string& type_name, nb::object callback) {
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

        .def("get_components_of_type", [](TcSceneRef& self, const std::string& type_name) {
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

        .def("find_component_by_name", [](TcSceneRef& self, const std::string& class_name) -> nb::object {
            nb::object result = nb::none();
            tc_scene_foreach_component_of_type(
                self._h,
                class_name.c_str(),
                [](tc_component* c, void* user_data) -> bool {
                    auto* result_ptr = static_cast<nb::object*>(user_data);
                    nb::object py_comp = tc_component_to_python(c);
                    if (!py_comp.is_none()) {
                        *result_ptr = py_comp;
                        return false;  // stop iteration
                    }
                    return true;
                },
                &result
            );
            return result;
        }, nb::arg("class_name"),
           "Find first component by class name string. Returns None if not found.")

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

        // Input dispatch
        .def("dispatch_mouse_button", [](TcSceneRef& self, const MouseButtonEvent& event) {
            dispatch_input_to_scene(self._h, "on_mouse_button", event, false);
        }, nb::arg("event"))
        .def("dispatch_mouse_move", [](TcSceneRef& self, const MouseMoveEvent& event) {
            dispatch_input_to_scene(self._h, "on_mouse_move", event, false);
        }, nb::arg("event"))
        .def("dispatch_scroll", [](TcSceneRef& self, const ScrollEvent& event) {
            dispatch_input_to_scene(self._h, "on_scroll", event, false);
        }, nb::arg("event"))
        .def("dispatch_key", [](TcSceneRef& self, const KeyEvent& event) {
            dispatch_input_to_scene(self._h, "on_key", event, false);
        }, nb::arg("event"))

        .def("dispatch_mouse_button_editor", [](TcSceneRef& self, const MouseButtonEvent& event) {
            dispatch_input_to_scene(self._h, "on_mouse_button", event, true);
        }, nb::arg("event"))
        .def("dispatch_mouse_move_editor", [](TcSceneRef& self, const MouseMoveEvent& event) {
            dispatch_input_to_scene(self._h, "on_mouse_move", event, true);
        }, nb::arg("event"))
        .def("dispatch_scroll_editor", [](TcSceneRef& self, const ScrollEvent& event) {
            dispatch_input_to_scene(self._h, "on_scroll", event, true);
        }, nb::arg("event"))
        .def("dispatch_key_editor", [](TcSceneRef& self, const KeyEvent& event) {
            dispatch_input_to_scene(self._h, "on_key", event, true);
        }, nb::arg("event"))

        // Pipeline templates
        .def("add_pipeline_template", &TcSceneRef::add_pipeline_template, nb::arg("template"))
        .def("clear_pipeline_templates", &TcSceneRef::clear_pipeline_templates)
        .def("pipeline_template_count", &TcSceneRef::pipeline_template_count)
        .def("pipeline_template_at", &TcSceneRef::pipeline_template_at, nb::arg("index"))
        .def_prop_ro("scene_pipelines", [](TcSceneRef& self) {
            std::vector<TcScenePipelineTemplate> result;
            size_t count = self.pipeline_template_count();
            result.reserve(count);
            for (size_t i = 0; i < count; i++) {
                result.push_back(self.pipeline_template_at(i));
            }
            return result;
        }, "Get all scene pipeline templates")

        // Compiled pipelines (from RenderingManager)
        .def("get_pipeline", &TcSceneRef::get_pipeline, nb::arg("name"),
             nb::rv_policy::reference)
        .def("get_pipeline_names", &TcSceneRef::get_pipeline_names)
        .def("get_pipeline_targets", &TcSceneRef::get_pipeline_targets, nb::arg("name"),
             nb::rv_policy::reference)

        // --- Serialization ---
        .def("serialize", [](TcSceneRef& self) -> nb::object {
            return trent_to_python(self.serialize());
        }, "Serialize scene settings and entities to dict")

        .def("load_from_data", [](TcSceneRef& self, nb::handle data, nb::object context, bool update_settings) -> int {
            // context is ignored - kept for API compatibility with old Python Scene
            (void)context;
            nos::trent t = python_to_trent(data);
            return self.load_from_data(t, update_settings);
        }, nb::arg("data"), nb::arg("context") = nb::none(), nb::arg("update_settings") = true,
           "Load settings and entities from dict. Returns entity count.")

        .def("to_json_string", &TcSceneRef::to_json_string,
             "Serialize scene to JSON string")
        .def("from_json_string", &TcSceneRef::from_json_string, nb::arg("json"),
             "Load scene settings from JSON string")

        // --- Convenience properties ---
        .def_prop_ro("is_destroyed", [](TcSceneRef& self) {
            return !self.is_alive();
        }, "Check if scene has been destroyed (opposite of is_alive)")

        .def_prop_ro("entities", [](TcSceneRef& self) {
            return self.get_all_entities();
        }, "Get all entities in the scene (alias for get_all_entities)")

        // Shadow settings (convenience - delegates to lighting())
        .def_prop_rw("shadow_settings",
            [](TcSceneRef& self) -> nb::object {
                tc_scene_lighting* lit = self.lighting();
                if (!lit) return nb::none();
                nb::module_ lighting_module = nb::module_::import_("termin.lighting._lighting_native");
                nb::object cls = lighting_module.attr("ShadowSettings");
                return cls(lit->shadow_method, lit->shadow_softness, lit->shadow_bias);
            },
            [](TcSceneRef& self, nb::object value) {
                tc_scene_lighting* lit = self.lighting();
                if (!lit) return;
                lit->shadow_method = nb::cast<int>(value.attr("method"));
                lit->shadow_softness = static_cast<float>(nb::cast<double>(value.attr("softness")));
                lit->shadow_bias = static_cast<float>(nb::cast<double>(value.attr("bias")));
            },
            "Shadow settings (convenience property)")

        // --- Skybox type as string ---
        .def_prop_rw("skybox_type",
            [](TcSceneRef& self) -> std::string {
                int t = tc_scene_get_skybox_type(self._h);
                if (t == TC_SKYBOX_NONE) return "none";
                if (t == TC_SKYBOX_SOLID) return "solid";
                return "gradient";
            },
            [](TcSceneRef& self, const std::string& s) {
                int t = TC_SKYBOX_GRADIENT;
                if (s == "none") t = TC_SKYBOX_NONE;
                else if (s == "solid") t = TC_SKYBOX_SOLID;
                tc_scene_set_skybox_type(self._h, t);
            },
            "Skybox type as string: 'none', 'solid', or 'gradient'")

        // --- Entity management with callbacks ---
        .def("add", [](TcSceneRef& self, Entity& entity) -> Entity {
            Entity migrated = self.migrate_entity(entity);
            if (!migrated.valid()) {
                throw std::runtime_error("Failed to migrate entity to scene's pool");
            }
            return migrated;
        }, nb::arg("entity"),
           "Add entity to scene (migrates to scene's pool). Returns migrated entity.")

        .def("remove", [](TcSceneRef& self, Entity& entity) {
            if (!entity.valid()) return;
            // Call on_removed on all components
            size_t count = entity.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* c = entity.component_at(i);
                if (c) {
                    tc_component_on_removed(c);
                }
            }
            self.remove_entity(entity);
        }, nb::arg("entity"),
           "Remove entity from scene");

    // --- Static/class methods ---
    m.def("deserialize_scene", [](nb::handle data, const std::string& name) -> TcSceneRef {
        TcSceneRef scene = TcSceneRef::create(name, "");
        nos::trent t = python_to_trent(data);

        // Extract uuid and background_color before load_from_data
        if (t.contains("uuid") && t["uuid"].is_string()) {
            scene.set_uuid(t["uuid"].as_string());
        }
        if (t.contains("background_color") && t["background_color"].is_list()) {
            const auto& bg = t["background_color"].as_list();
            if (bg.size() >= 4) {
                scene.set_background_color(
                    static_cast<float>(bg[0].as_numer_default(0.05)),
                    static_cast<float>(bg[1].as_numer_default(0.05)),
                    static_cast<float>(bg[2].as_numer_default(0.08)),
                    static_cast<float>(bg[3].as_numer_default(1.0)));
            }
        }

        scene.load_from_data(t, true);
        return scene;
    }, nb::arg("data"), nb::arg("name") = "",
       "Create scene from serialized data (classmethod equivalent)");
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
