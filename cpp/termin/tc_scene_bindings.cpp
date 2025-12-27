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
    void add_entity(Entity* e) {
        if (!e) return;
        tc_entity* te = e->c_entity();
        if (te) {
            tc_scene_add_entity(_s, te);
        }
    }

    void remove_entity(Entity* e) {
        if (!e) return;
        tc_entity* te = e->c_entity();
        if (te) {
            tc_scene_remove_entity(_s, te);
        }
    }

    size_t entity_count() const {
        return tc_scene_entity_count(_s);
    }

    // Component registration
    void register_component(Component* c) {
        if (!c) return;
        c->sync_to_c();
        tc_scene_register_component(_s, c->c_component());
    }

    void unregister_component(Component* c) {
        if (!c) return;
        tc_scene_unregister_component(_s, c->c_component());
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
};

void bind_tc_scene(py::module_& m) {
    py::class_<TcScene>(m, "TcScene")
        .def(py::init<>())

        // Entity management
        .def("add_entity", &TcScene::add_entity, py::arg("entity"))
        .def("remove_entity", &TcScene::remove_entity, py::arg("entity"))
        .def("entity_count", &TcScene::entity_count)

        // Component registration
        .def("register_component", &TcScene::register_component, py::arg("component"))
        .def("unregister_component", &TcScene::unregister_component, py::arg("component"))

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
        ;
}

} // namespace termin
