// tc_scene_bindings.cpp - Direct bindings for tc_scene C API
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "entity/entity.hpp"
#include "entity/component.hpp"
#include "../../core_c/include/tc_scene.h"

namespace py = pybind11;

namespace termin {

// Opaque wrapper for tc_scene*
class TcScene {
public:
    tc_scene* _s = nullptr;

    TcScene() {
        _s = tc_scene_new();
    }

    ~TcScene() {
        if (_s) {
            tc_scene_free(_s);
            _s = nullptr;
        }
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
        (void)e;
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
            } else if (tc->kind == TC_PYTHON_COMPONENT && tc->py_wrap) {
                // Python component - update via Python attribute
                py::gil_scoped_acquire gil;
                py::object py_comp = py::reinterpret_borrow<py::object>((PyObject*)tc->py_wrap);
                if (py::hasattr(py_comp, "entity")) {
                    py_comp.attr("entity") = py::cast(ent);
                }
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

void bind_tc_scene(py::module_& m) {
    py::class_<TcScene>(m, "TcScene")
        .def(py::init<>())

        // Entity management
        .def("add_entity", &TcScene::add_entity, py::arg("entity"))
        .def("remove_entity", &TcScene::remove_entity, py::arg("entity"))
        .def("entity_count", &TcScene::entity_count)

        // Component registration (C++ Component)
        .def("register_component", &TcScene::register_component, py::arg("component"))
        .def("unregister_component", &TcScene::unregister_component, py::arg("component"))

        // Component registration by pointer (for pure Python components)
        .def("register_component_ptr", &TcScene::register_component_ptr, py::arg("ptr"))
        .def("unregister_component_ptr", &TcScene::unregister_component_ptr, py::arg("ptr"))

        // Update loop
        .def("update", &TcScene::update, py::arg("dt"))
        .def("editor_update", &TcScene::editor_update, py::arg("dt"))

        // Fixed timestep
        .def_property("fixed_timestep", &TcScene::fixed_timestep, &TcScene::set_fixed_timestep)
        .def_property_readonly("accumulated_time", &TcScene::accumulated_time)
        .def("reset_accumulated_time", &TcScene::reset_accumulated_time)

        // Component queries
        .def_property_readonly("pending_start_count", &TcScene::pending_start_count)
        .def_property_readonly("update_list_count", &TcScene::update_list_count)
        .def_property_readonly("fixed_update_list_count", &TcScene::fixed_update_list_count)

        // Pool access
        .def("entity_pool_ptr", [](TcScene& self) {
            return reinterpret_cast<uintptr_t>(self.entity_pool());
        }, "Get scene's entity pool as uintptr_t")

        // Entity creation in pool
        .def("create_entity", &TcScene::create_entity, py::arg("name") = "",
             "Create a new entity directly in scene's pool.")

        // Entity migration
        .def("migrate_entity", &TcScene::migrate_entity, py::arg("entity"),
             "Migrate entity to scene's pool. Returns new Entity, old becomes invalid.")

        // Entity lookup
        .def("get_entity", [](TcScene& self, const std::string& uuid) -> py::object {
            Entity e = self.get_entity(uuid);
            if (e.valid()) return py::cast(e);
            return py::none();
        }, py::arg("uuid"), "Find entity by UUID. Returns None if not found.")

        .def("get_entity_by_pick_id", [](TcScene& self, uint32_t pick_id) -> py::object {
            Entity e = self.get_entity_by_pick_id(pick_id);
            if (e.valid()) return py::cast(e);
            return py::none();
        }, py::arg("pick_id"), "Find entity by pick_id. Returns None if not found.")
        ;
}

} // namespace termin
