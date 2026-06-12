// Entity domain bindings for _native module.
// Migrated from _entity_native to eliminate the termin.entity Python package.
//
// Core ECS types (Entity, Component, ComponentRegistry, TcScene, TcComponentRef,
// TcComponent) are owned by _scene_native and should be imported from there.
// This module provides domain-specific bindings: EntityRegistry,
// OrbitCameraController, InputEvents, TcScene render extensions.

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/vector.h>

#include <utility>
#include <tcbase/tc_log.hpp>

#include "../camera/orbit_camera_bindings.hpp"
#include "../input/input_events_bindings.hpp"
#include "../../scene_bindings.hpp"

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include "termin/entity/entity_registry.hpp"
#include "termin/inspect/tc_kind.hpp"

namespace nb = nanobind;
using namespace termin;

void bind_entity_domain(nb::module_& m) {
    // Import _scene_native first. It owns the ECS nanobind types; this module
    // adds render/editor domain helpers and re-exports the core types.
    nb::module_ scene_native = nb::module_::import_("termin.scene._scene_native");
    m.attr("TcScene") = scene_native.attr("TcScene");
    m.attr("TcSceneRef") = scene_native.attr("TcScene");
    m.attr("Component") = scene_native.attr("Component");
    m.attr("ComponentRegistry") = scene_native.attr("ComponentRegistry");
    m.attr("TcComponentRef") = scene_native.attr("TcComponentRef");
    m.attr("TcComponent") = scene_native.attr("TcComponent");
    m.attr("Entity") = scene_native.attr("Entity");
    m.attr("_EntityAncestorIterator") = scene_native.attr("_EntityAncestorIterator");
    m.attr("get_standalone_pool") = scene_native.attr("get_standalone_pool");
    m.attr("migrate_entity") = scene_native.attr("migrate_entity");
    m.attr("component_registry_get_all_info") = scene_native.attr("component_registry_get_all_info");
    m.attr("component_registry_type_count") = scene_native.attr("component_registry_type_count");
    m.attr("soa_registry_get_all_info") = scene_native.attr("soa_registry_get_all_info");
    m.attr("soa_registry_type_count") = scene_native.attr("soa_registry_type_count");

    // Import tmesh native module so TcMesh is registered before
    // SceneRenderState::skybox_mesh() bindings are attached.
    nb::module_::import_("tmesh._tmesh_native");

    // Import _viewport_native for TcViewport type (used by input events)
    nb::module_::import_("termin.viewport._viewport_native");

    // Import tcbase for Action, MouseButton, Mods enums (used by input events)
    nb::module_::import_("tcbase._tcbase_native");

    // --- TcScene render extensions (ViewportConfig, background_color, pipelines, etc.) ---
    bind_tc_scene(m);
    bind_tc_scene_lighting(m);

    // --- OrbitCameraController ---
    bind_orbit_camera_controller(m);

    // --- Input Events ---
    bind_input_events(m);

    // --- EntityRegistry ---
    nb::class_<EntityRegistry>(m, "EntityRegistry")
        .def_static("instance", &EntityRegistry::instance, nb::rv_policy::reference)
        .def("get", [](EntityRegistry& reg, const std::string& uuid) -> nb::object {
            Entity ent = reg.get(uuid);
            if (ent.valid()) {
                return nb::cast(ent);
            }
            return nb::none();
        }, nb::arg("uuid"))
        .def("get_by_pick_id", [](EntityRegistry& reg, uint32_t pick_id) -> nb::object {
            Entity ent = reg.get_by_pick_id(pick_id);
            if (ent.valid()) {
                return nb::cast(ent);
            }
            return nb::none();
        }, nb::arg("pick_id"))
        .def("register_entity", [](EntityRegistry& reg, const Entity& entity) {
            reg.register_entity(entity);
        }, nb::arg("entity"))
        .def("unregister_entity", [](EntityRegistry& reg, const Entity& entity) {
            reg.unregister_entity(entity);
        }, nb::arg("entity"))
        .def("clear", &EntityRegistry::clear)
        .def_prop_ro("entity_count", &EntityRegistry::entity_count)
        .def("swap_registries", [](EntityRegistry& reg, nb::object new_by_uuid, nb::object new_by_pick_id) {
            std::unordered_map<std::string, Entity> cpp_by_uuid;
            std::unordered_map<uint32_t, Entity> cpp_by_pick_id;

            if (!new_by_uuid.is_none()) {
                for (auto item : new_by_uuid.attr("items")()) {
                    auto pair = nb::cast<nb::tuple>(item);
                    std::string uuid = nb::cast<std::string>(pair[0]);
                    Entity ent = nb::cast<Entity>(pair[1]);
                    cpp_by_uuid[uuid] = ent;
                }
            }

            if (!new_by_pick_id.is_none()) {
                for (auto item : new_by_pick_id.attr("items")()) {
                    auto pair = nb::cast<nb::tuple>(item);
                    uint32_t pick_id = nb::cast<uint32_t>(pair[0]);
                    Entity ent = nb::cast<Entity>(pair[1]);
                    cpp_by_pick_id[pick_id] = ent;
                }
            }

            auto [old_by_uuid, old_by_pick_id] = reg.swap_registries(
                std::move(cpp_by_uuid), std::move(cpp_by_pick_id));

            nb::dict py_old_by_uuid;
            for (auto& [uuid, ent] : old_by_uuid) {
                if (ent.valid()) {
                    py_old_by_uuid[nb::str(uuid.c_str())] = nb::cast(ent);
                }
            }

            nb::dict py_old_by_pick_id;
            for (auto& [pick_id, ent] : old_by_pick_id) {
                if (ent.valid()) {
                    py_old_by_pick_id[nb::int_(pick_id)] = nb::cast(ent);
                }
            }

            return nb::make_tuple(py_old_by_uuid, py_old_by_pick_id);
        }, nb::arg("new_by_uuid"), nb::arg("new_by_pick_id"));

    // Register CxxComponent base fields in InspectRegistry.
    tc::InspectFieldInfo display_name_field;
    display_name_field.type_name = "Component";
    display_name_field.path = "display_name";
    display_name_field.label = "Name";
    display_name_field.kind = "string";
    display_name_field.is_serializable = false;
    display_name_field.is_inspectable = true;
    display_name_field.getter = [](void* obj) -> tc_value {
        return tc_value_string(static_cast<CxxComponent*>(obj)->display_name().c_str());
    };
    display_name_field.setter = [](void* obj, tc_value value, void*) {
        if (value.type == TC_VALUE_STRING) {
            static_cast<CxxComponent*>(obj)->set_display_name(value.data.s ? value.data.s : "");
        }
    };
    tc::InspectRegistry::instance().add_field_with_choices("Component", std::move(display_name_field));

    tc::InspectRegistry::instance().add_with_accessors<CxxComponent, bool>(
        "Component", "enabled", "Enabled", "bool",
        [](CxxComponent* c) { return c->enabled(); },
        [](CxxComponent* c, bool v) { c->set_enabled(v); }
    );

    // Register atexit handler
    nb::object atexit_mod = nb::module_::import_("atexit");
    nb::object cleanup_fn = nb::cpp_function([]() {
        ComponentRegistry::instance().clear();
        EntityRegistry::instance().clear();
        tc::KindRegistry::instance().clear_python();
    });
    atexit_mod.attr("register")(cleanup_fn);

    // Expose singleton address helpers at _native top level (for backward compat with shim)
    nb::module_ inspect_native = nb::module_::import_("termin.inspect._inspect_native");
    m.attr("_inspect_registry_address") = inspect_native.attr("inspect_registry_address");
    m.attr("_kind_registry_cpp_address") = inspect_native.attr("kind_registry_cpp_address");
}
