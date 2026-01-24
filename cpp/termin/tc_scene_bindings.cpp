// tc_scene_bindings.cpp - Direct bindings for tc_scene C API
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "entity/entity.hpp"
#include "entity/component.hpp"
#include "bindings/entity/entity_helpers.hpp"
#include "tc_scene_ref.hpp"
#include "../../core_c/include/tc_scene.h"
#include "../../core_c/include/tc_scene_lighting.h"
#include "../../core_c/include/tc_scene_registry.h"
#include "../../core_c/include/tc_entity_pool.h"
#include "../../core_c/include/tc_log.h"
#include "scene_bindings.hpp"

namespace nb = nanobind;

namespace termin {

// Opaque wrapper for tc_scene*
class TcScene {
public:
    tc_scene* _s = nullptr;

    TcScene() {
        _s = tc_scene_new();
    }

    ~TcScene() {
        destroy();
    }

    void destroy() {
        if (_s) {
            tc_scene_free(_s);
            _s = nullptr;
        }
    }

    // Get non-owning reference to this scene
    TcSceneRef scene_ref() const {
        return TcSceneRef(_s);
    }

    // Disable copy
    TcScene(const TcScene&) = delete;
    TcScene& operator=(const TcScene&) = delete;

    // Move
    TcScene(TcScene&& other) noexcept : _s(other._s) {
        other._s = nullptr;
    }

    TcScene& operator=(TcScene&& other) noexcept {
        if (this != &other) {
            if (_s) tc_scene_free(_s);
            _s = other._s;
            other._s = nullptr;
        }
        return *this;
    }

    // Entity management
    // Entities live in pool, scene just references them
    void add_entity(const Entity& e) {
        (void)e;
    }

    void remove_entity(const Entity& e) {
        if (!e.valid()) return;

        // Just free entity from pool
        // Components should be unregistered by Python Scene.remove() first
        tc_entity_pool_free(e.pool(), e.id());
    }

    size_t entity_count() const {
        return tc_scene_entity_count(_s);
    }

    // Component registration (C++ Component)
    void register_component(Component* c) {
        if (!c) return;
        tc_scene_register_component(_s, c->c_component());
    }

    void unregister_component(Component* c) {
        if (!c) return;
        tc_scene_unregister_component(_s, c->c_component());
    }

    // Component registration by pointer (for TcComponent/pure Python components)
    void register_component_ptr(uintptr_t ptr) {
        tc_component* c = reinterpret_cast<tc_component*>(ptr);
        if (c) {
            tc_scene_register_component(_s, c);
        }
    }

    void unregister_component_ptr(uintptr_t ptr) {
        tc_component* c = reinterpret_cast<tc_component*>(ptr);
        if (c) {
            tc_scene_unregister_component(_s, c);
        }
    }

    // Update loop
    void update(double dt) {
        // GIL is held by Python caller, callbacks will re-acquire if needed
        tc_scene_update(_s, dt);
    }

    void editor_update(double dt) {
        tc_scene_editor_update(_s, dt);
    }

    void before_render() {
        tc_scene_before_render(_s);
    }

    // Fixed timestep
    double fixed_timestep() const {
        return tc_scene_fixed_timestep(_s);
    }

    void set_fixed_timestep(double dt) {
        tc_scene_set_fixed_timestep(_s, dt);
    }

    double accumulated_time() const {
        return tc_scene_accumulated_time(_s);
    }

    void reset_accumulated_time() {
        tc_scene_reset_accumulated_time(_s);
    }

    // Component queries
    size_t pending_start_count() const {
        return tc_scene_pending_start_count(_s);
    }

    size_t update_list_count() const {
        return tc_scene_update_list_count(_s);
    }

    size_t fixed_update_list_count() const {
        return tc_scene_fixed_update_list_count(_s);
    }

    // Get entity pool owned by this scene
    tc_entity_pool* entity_pool() const {
        return tc_scene_entity_pool(_s);
    }

    // Set Python wrapper for callbacks from C to Python
    void set_py_wrapper(nb::object wrapper) {
        // Store raw PyObject* - Python Scene must outlive TcScene
        tc_scene_set_py_wrapper(_s, wrapper.ptr());
    }

private:
    // Update entity references in all components of an entity (and its children)
    void update_component_entity_refs(Entity& ent) {
        size_t count = ent.component_count();
        for (size_t i = 0; i < count; i++) {
            tc_component* tc = ent.component_at(i);
            if (!tc) continue;

            if (tc->kind == TC_CXX_COMPONENT) {
                // C++ component - update entity field directly
                CxxComponent* cxx = CxxComponent::from_tc(tc);
                if (cxx) {
                    cxx->entity = ent;
                }
            } else if (tc->native_language == TC_BINDING_PYTHON && tc->body) {
                // Python component - update via Python attribute
                // All Python components have 'entity' field declared in base class
                nb::gil_scoped_acquire gil;
                nb::object py_comp = nb::borrow<nb::object>((PyObject*)tc->body);
                py_comp.attr("entity") = nb::cast(ent);
            }
        }

        // Recursively update children
        for (Entity child : ent.children()) {
            update_component_entity_refs(child);
        }
    }

public:
    // Create a new entity directly in scene's pool
    Entity create_entity(const std::string& name = "") {
        tc_entity_pool* pool = entity_pool();
        if (!pool) return Entity();
        return Entity::create(pool, name);
    }

    // Find entity by UUID in scene's pool
    Entity get_entity(const std::string& uuid) const {
        tc_entity_pool* pool = entity_pool();
        if (!pool || uuid.empty()) return Entity();

        tc_entity_id id = tc_entity_pool_find_by_uuid(pool, uuid.c_str());
        if (!tc_entity_id_valid(id)) return Entity();

        return Entity(pool, id);
    }

    // Find entity by pick_id in scene's pool
    Entity get_entity_by_pick_id(uint32_t pick_id) const {
        tc_entity_pool* pool = entity_pool();
        if (!pool || pick_id == 0) return Entity();

        tc_entity_id id = tc_entity_pool_find_by_pick_id(pool, pick_id);
        if (!tc_entity_id_valid(id)) return Entity();

        return Entity(pool, id);
    }

    // Find entity by name in scene's pool
    Entity find_entity_by_name(const std::string& name) const {
        if (name.empty()) return Entity();

        tc_entity_id id = tc_scene_find_entity_by_name(_s, name.c_str());
        if (!tc_entity_id_valid(id)) return Entity();

        return Entity(entity_pool(), id);
    }

    // Scene name (from registry)
    std::string name() const {
        const char* n = tc_scene_registry_get_name(_s);
        return n ? std::string(n) : "";
    }

    void set_name(const std::string& n) {
        tc_scene_registry_set_name(_s, n.c_str());
    }

    // Lighting properties
    tc_scene_lighting* lighting() {
        return tc_scene_get_lighting(_s);
    }

    // Get all entities in scene's pool
    std::vector<Entity> get_all_entities() const {
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

    // Migrate entity to this scene's pool
    // Returns new Entity in scene's pool, old entity becomes invalid
    Entity migrate_entity(Entity& entity) {
        tc_entity_pool* dst_pool = entity_pool();
        if (!entity.valid() || !dst_pool) {
            return Entity();
        }

        tc_entity_pool* src_pool = entity.pool();
        if (src_pool == dst_pool) {
            // Already in scene's pool
            return entity;
        }

        tc_entity_id new_id = tc_entity_pool_migrate(src_pool, entity.id(), dst_pool);
        if (!tc_entity_id_valid(new_id)) {
            return Entity();
        }

        Entity new_entity(dst_pool, new_id);

        // Update entity reference in all components (including children)
        update_component_entity_refs(new_entity);

        return new_entity;
    }
};

void bind_tc_scene(nb::module_& m) {
    nb::class_<TcScene>(m, "TcScene")
        .def(nb::init<>())
        .def("destroy", &TcScene::destroy, "Explicitly release tc_scene resources")
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

        // Scene pointer access
        .def("scene_ptr", [](TcScene& self) {
            return reinterpret_cast<uintptr_t>(self._s);
        }, "Get tc_scene* as uintptr_t")

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

        // Scene name
        .def_prop_rw("name", &TcScene::name, &TcScene::set_name)

        // Python wrapper for callbacks
        .def("set_py_wrapper", &TcScene::set_py_wrapper, nb::arg("wrapper"),
             "Set Python Scene wrapper for component auto-registration")

        // Lighting (returns pointer to internal tc_scene_lighting)
        .def("lighting_ptr", [](TcScene& self) {
            return reinterpret_cast<uintptr_t>(self.lighting());
        }, "Get pointer to tc_scene_lighting")

        // Component type queries
        .def("get_components_of_type", [](TcScene& self, const std::string& type_name) {
            nb::list result;
            tc_component* c = tc_scene_first_component_of_type(self._s, type_name.c_str());
            while (c != NULL) {
                // Return Python object via tc_component_to_python
                nb::object py_comp = tc_component_to_python(c);
                if (!py_comp.is_none()) {
                    result.append(py_comp);
                }
                c = c->type_next;
            }
            return result;
        }, nb::arg("type_name"), "Get all components of given type")

        .def("count_components_of_type", [](TcScene& self, const std::string& type_name) {
            return tc_scene_count_components_of_type(self._s, type_name.c_str());
        }, nb::arg("type_name"), "Count components of given type")

        .def("get_component_type_counts", [](TcScene& self) {
            // Get all component types directly from scene's type_heads
            nb::dict result;

            size_t type_count = 0;
            tc_scene_component_type* types = tc_scene_get_all_component_types(self._s, &type_count);
            if (types) {
                for (size_t i = 0; i < type_count; i++) {
                    if (types[i].type_name) {
                        result[types[i].type_name] = types[i].count;
                    }
                }
                free(types);
            }
            return result;
        }, "Get dict of component type -> count for all types in scene")

        .def("foreach_component_of_type", [](TcScene& self, const std::string& type_name, nb::callable callback) {
            // Wrap Python callback
            struct CallbackData {
                nb::callable py_callback;
                bool had_exception = false;
            };
            CallbackData data{callback};

            tc_scene_foreach_component_of_type(
                self._s,
                type_name.c_str(),
                [](tc_component* c, void* user_data) -> bool {
                    auto* data = static_cast<CallbackData*>(user_data);
                    if (data->had_exception) return false;

                    try {
                        nb::object py_comp = tc_component_to_python(c);
                        if (!py_comp.is_none()) {
                            nb::object result = data->py_callback(py_comp);
                            // If callback returns False, stop iteration
                            if (nb::isinstance<nb::bool_>(result) && !nb::cast<bool>(result)) {
                                return false;
                            }
                        }
                        return true;
                    } catch (...) {
                        data->had_exception = true;
                        return false;
                    }
                },
                &data
            );

            if (data.had_exception) {
                throw nb::python_error();
            }
        }, nb::arg("type_name"), nb::arg("callback"),
           "Iterate components of type with callback(component) -> bool. Return False to stop.")

        // Input dispatch methods - dispatch to all input handler components via vtable
        .def("dispatch_mouse_button", [](TcScene& self, nb::object event) {
            struct DispatchData {
                PyObject* event_ptr;
                bool had_exception = false;
            };
            DispatchData data{event.ptr()};

            tc_scene_foreach_input_handler(
                self._s,
                [](tc_component* c, void* user_data) -> bool {
                    auto* data = static_cast<DispatchData*>(user_data);
                    if (data->had_exception) return false;

                    try {
                        // All input handlers must have input_vtable set
                        if (c->input_vtable && c->input_vtable->on_mouse_button) {
                            c->input_vtable->on_mouse_button(c, data->event_ptr);
                        }
                        return true;
                    } catch (...) {
                        data->had_exception = true;
                        return false;
                    }
                },
                &data,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED
            );

            if (data.had_exception) {
                throw nb::python_error();
            }
        }, nb::arg("event"), "Dispatch mouse button event to all input handlers")

        .def("dispatch_mouse_move", [](TcScene& self, nb::object event) {
            struct DispatchData {
                PyObject* event_ptr;
                bool had_exception = false;
            };
            DispatchData data{event.ptr()};

            tc_scene_foreach_input_handler(
                self._s,
                [](tc_component* c, void* user_data) -> bool {
                    auto* data = static_cast<DispatchData*>(user_data);
                    if (data->had_exception) return false;

                    try {
                        if (c->input_vtable && c->input_vtable->on_mouse_move) {
                            c->input_vtable->on_mouse_move(c, data->event_ptr);
                        }
                        return true;
                    } catch (...) {
                        data->had_exception = true;
                        return false;
                    }
                },
                &data,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED
            );

            if (data.had_exception) {
                throw nb::python_error();
            }
        }, nb::arg("event"), "Dispatch mouse move event to all input handlers")

        .def("dispatch_scroll", [](TcScene& self, nb::object event) {
            struct DispatchData {
                PyObject* event_ptr;
                bool had_exception = false;
            };
            DispatchData data{event.ptr()};

            tc_scene_foreach_input_handler(
                self._s,
                [](tc_component* c, void* user_data) -> bool {
                    auto* data = static_cast<DispatchData*>(user_data);
                    if (data->had_exception) return false;

                    try {
                        if (c->input_vtable && c->input_vtable->on_scroll) {
                            c->input_vtable->on_scroll(c, data->event_ptr);
                        }
                        return true;
                    } catch (...) {
                        data->had_exception = true;
                        return false;
                    }
                },
                &data,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED
            );

            if (data.had_exception) {
                throw nb::python_error();
            }
        }, nb::arg("event"), "Dispatch scroll event to all input handlers")

        .def("dispatch_key", [](TcScene& self, nb::object event) {
            struct DispatchData {
                PyObject* event_ptr;
                bool had_exception = false;
            };
            DispatchData data{event.ptr()};

            tc_scene_foreach_input_handler(
                self._s,
                [](tc_component* c, void* user_data) -> bool {
                    auto* data = static_cast<DispatchData*>(user_data);
                    if (data->had_exception) return false;

                    try {
                        if (c->input_vtable && c->input_vtable->on_key) {
                            c->input_vtable->on_key(c, data->event_ptr);
                        }
                        return true;
                    } catch (...) {
                        data->had_exception = true;
                        return false;
                    }
                },
                &data,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED
            );

            if (data.had_exception) {
                throw nb::python_error();
            }
        }, nb::arg("event"), "Dispatch key event to all input handlers")

        // Editor dispatch methods (with active_in_editor filter)
        .def("dispatch_mouse_button_editor", [](TcScene& self, nb::object event) {
            struct DispatchData {
                PyObject* event_ptr;
                bool had_exception = false;
            };
            DispatchData data{event.ptr()};

            tc_scene_foreach_input_handler(
                self._s,
                [](tc_component* c, void* user_data) -> bool {
                    auto* data = static_cast<DispatchData*>(user_data);
                    if (data->had_exception) return false;

                    try {
                        if (c->input_vtable && c->input_vtable->on_mouse_button) {
                            c->input_vtable->on_mouse_button(c, data->event_ptr);
                        }
                        return true;
                    } catch (...) {
                        data->had_exception = true;
                        return false;
                    }
                },
                &data,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED | TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR
            );

            if (data.had_exception) {
                throw nb::python_error();
            }
        }, nb::arg("event"), "Dispatch mouse button event to editor input handlers")

        .def("dispatch_mouse_move_editor", [](TcScene& self, nb::object event) {
            struct DispatchData {
                PyObject* event_ptr;
                bool had_exception = false;
            };
            DispatchData data{event.ptr()};

            tc_scene_foreach_input_handler(
                self._s,
                [](tc_component* c, void* user_data) -> bool {
                    auto* data = static_cast<DispatchData*>(user_data);
                    if (data->had_exception) return false;

                    try {
                        if (c->input_vtable && c->input_vtable->on_mouse_move) {
                            c->input_vtable->on_mouse_move(c, data->event_ptr);
                        }
                        return true;
                    } catch (...) {
                        data->had_exception = true;
                        return false;
                    }
                },
                &data,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED | TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR
            );

            if (data.had_exception) {
                throw nb::python_error();
            }
        }, nb::arg("event"), "Dispatch mouse move event to editor input handlers")

        .def("dispatch_scroll_editor", [](TcScene& self, nb::object event) {
            struct DispatchData {
                PyObject* event_ptr;
                bool had_exception = false;
            };
            DispatchData data{event.ptr()};

            tc_scene_foreach_input_handler(
                self._s,
                [](tc_component* c, void* user_data) -> bool {
                    auto* data = static_cast<DispatchData*>(user_data);
                    if (data->had_exception) return false;

                    try {
                        if (c->input_vtable && c->input_vtable->on_scroll) {
                            c->input_vtable->on_scroll(c, data->event_ptr);
                        }
                        return true;
                    } catch (...) {
                        data->had_exception = true;
                        return false;
                    }
                },
                &data,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED | TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR
            );

            if (data.had_exception) {
                throw nb::python_error();
            }
        }, nb::arg("event"), "Dispatch scroll event to editor input handlers")

        .def("dispatch_key_editor", [](TcScene& self, nb::object event) {
            struct DispatchData {
                PyObject* event_ptr;
                bool had_exception = false;
            };
            DispatchData data{event.ptr()};

            tc_scene_foreach_input_handler(
                self._s,
                [](tc_component* c, void* user_data) -> bool {
                    auto* data = static_cast<DispatchData*>(user_data);
                    if (data->had_exception) return false;

                    try {
                        if (c->input_vtable && c->input_vtable->on_key) {
                            c->input_vtable->on_key(c, data->event_ptr);
                        }
                        return true;
                    } catch (...) {
                        data->had_exception = true;
                        return false;
                    }
                },
                &data,
                TC_DRAWABLE_FILTER_ENABLED | TC_DRAWABLE_FILTER_ENTITY_ENABLED | TC_DRAWABLE_FILTER_ACTIVE_IN_EDITOR
            );

            if (data.had_exception) {
                throw nb::python_error();
            }
        }, nb::arg("event"), "Dispatch key event to editor input handlers")

        // Notification methods - call lifecycle hooks on all components via C API
        .def("notify_editor_start", [](TcScene& self) {
            tc_scene_notify_editor_start(self._s);
        }, "Notify all components that editor has started")
        .def("notify_scene_inactive", [](TcScene& self) {
            tc_scene_notify_scene_inactive(self._s);
        }, "Notify all components that scene became inactive")
        .def("notify_scene_active", [](TcScene& self) {
            tc_scene_notify_scene_active(self._s);
        }, "Notify all components that scene became active")
        ;

    // =========================================================================
    // Scene registry module-level functions
    // =========================================================================
    m.def("tc_scene_registry_count", []() {
        return tc_scene_registry_count();
    }, "Get number of scenes in registry");

    m.def("tc_scene_registry_get_all_info", []() {
        nb::list result;
        size_t count = 0;
        tc_scene_info* infos = tc_scene_registry_get_all_info(&count);
        if (infos) {
            for (size_t i = 0; i < count; ++i) {
                nb::dict d;
                d["id"] = infos[i].id;
                d["name"] = infos[i].name ? std::string(infos[i].name) : "";
                d["entity_count"] = infos[i].entity_count;
                d["pending_count"] = infos[i].pending_count;
                d["update_count"] = infos[i].update_count;
                d["fixed_update_count"] = infos[i].fixed_update_count;
                result.append(d);
            }
            free(infos);
        }
        return result;
    }, "Get info for all scenes in registry");

    m.def("tc_scene_get_entities", [](int scene_id) {
        nb::list result;
        size_t count = 0;
        tc_scene_entity_info* infos = tc_scene_get_entities(scene_id, &count);
        if (infos) {
            for (size_t i = 0; i < count; ++i) {
                nb::dict d;
                d["name"] = infos[i].name ? std::string(infos[i].name) : "";
                d["uuid"] = infos[i].uuid ? std::string(infos[i].uuid) : "";
                d["component_count"] = infos[i].component_count;
                d["visible"] = infos[i].visible;
                d["enabled"] = infos[i].enabled;
                result.append(d);
            }
            free(infos);
        }
        return result;
    }, nb::arg("scene_id"), "Get entities for a scene by ID");

    m.def("tc_scene_get_component_types", [](int scene_id) {
        nb::list result;
        size_t count = 0;
        tc_scene_component_type_info* infos = tc_scene_get_component_types(scene_id, &count);
        if (infos) {
            for (size_t i = 0; i < count; ++i) {
                nb::dict d;
                d["type_name"] = infos[i].type_name ? std::string(infos[i].type_name) : "";
                d["count"] = infos[i].count;
                result.append(d);
            }
            free(infos);
        }
        return result;
    }, nb::arg("scene_id"), "Get component type counts for a scene by ID");
}

} // namespace termin
