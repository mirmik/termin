/**
 * Entity native module (_entity_native).
 *
 * Contains Component, Entity, EntityRegistry, ComponentRegistry.
 * Separated from _native to allow other modules (like _native with MeshRenderer)
 * to properly inherit from Component.
 */

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/vector.h>
#include <nanobind/ndarray.h>
#include <nanobind/trampoline.h>
#include <unordered_set>
#include <iostream>
#include <cstdio>
#include <functional>

#include "tc_log.hpp"
#include "entity_helpers.hpp"
#include "entity_bindings.hpp"

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#undef near
#undef far

inline bool check_heap_entity() {
    HANDLE heaps[100];
    DWORD numHeaps = GetProcessHeaps(100, heaps);
    for (DWORD i = 0; i < numHeaps; i++) {
        if (!HeapValidate(heaps[i], 0, nullptr)) {
            std::cerr << "[HEAP CORRUPT] Heap " << i << " is corrupted!" << std::endl;
            return false;
        }
    }
    return true;
}
#else
inline bool check_heap_entity() { return true; }
#endif

#include "termin/entity/component.hpp"
#include "termin/entity/component_registry.hpp"
#include "termin/entity/vtable_utils.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/entity_registry.hpp"
#include "termin/entity/components/rotator_component.hpp"
#include "termin/geom/general_transform3.hpp"
#include "termin/geom/pose3.hpp"
#include "trent/trent.h"
#include "../../../../core_c/include/tc_kind.hpp"

namespace nb = nanobind;
using namespace termin;

// Trampoline class for CxxComponent.
// Allows Python classes to inherit from C++ CxxComponent.
class PyCxxComponent : public CxxComponent {
public:
    NB_TRAMPOLINE(CxxComponent, 10);

    void start() override {
        NB_OVERRIDE(start);
    }
    void update(float dt) override {
        NB_OVERRIDE(update, dt);
    }
    void fixed_update(float dt) override {
        NB_OVERRIDE(fixed_update, dt);
    }
    void on_destroy() override {
        NB_OVERRIDE(on_destroy);
    }
    void on_editor_start() override {
        NB_OVERRIDE(on_editor_start);
    }
    void setup_editor_defaults() override {
        NB_OVERRIDE(setup_editor_defaults);
    }
    void on_added_to_entity() override {
        NB_OVERRIDE(on_added_to_entity);
    }
    void on_removed_from_entity() override {
        NB_OVERRIDE(on_removed_from_entity);
    }
    void on_added(nb::object scene) override {
        NB_OVERRIDE(on_added, scene);
    }
    void on_removed() override {
        NB_OVERRIDE(on_removed);
    }
    void on_scene_active() override {
        NB_OVERRIDE(on_scene_active);
    }
};

NB_MODULE(_entity_native, m) {
    m.doc() = "Entity native module (Component, Entity, registries)";

    // --- CxxComponent (also exported as Component for compatibility) ---
    nb::class_<CxxComponent, PyCxxComponent>(m, "Component")
        .def(nb::init<>())
        .def("start", &CxxComponent::start)
        .def("update", &CxxComponent::update)
        .def("fixed_update", &CxxComponent::fixed_update)
        .def("on_destroy", &CxxComponent::on_destroy)
        .def("on_editor_start", &CxxComponent::on_editor_start)
        .def("setup_editor_defaults", &CxxComponent::setup_editor_defaults)
        .def("on_added_to_entity", &CxxComponent::on_added_to_entity)
        .def("on_removed_from_entity", &CxxComponent::on_removed_from_entity)
        .def("on_added", &CxxComponent::on_added)
        .def("on_removed", &CxxComponent::on_removed)
        .def("on_scene_inactive", &CxxComponent::on_scene_inactive)
        .def("on_scene_active", &CxxComponent::on_scene_active)
        .def("type_name", &CxxComponent::type_name)
        .def_prop_rw("enabled", &CxxComponent::enabled, &CxxComponent::set_enabled)
        .def_prop_rw("active_in_editor", &CxxComponent::active_in_editor, &CxxComponent::set_active_in_editor)
        .def_prop_ro("started", &CxxComponent::started)
        .def_prop_rw("has_update", &CxxComponent::has_update, &CxxComponent::set_has_update)
        .def_prop_rw("has_fixed_update", &CxxComponent::has_fixed_update, &CxxComponent::set_has_fixed_update)
        .def_prop_rw("entity",
            [](CxxComponent& c) -> nb::object {
                if (c.entity.valid()) {
                    return nb::cast(c.entity);
                }
                return nb::none();
            },
            [](CxxComponent& c, nb::object value) {
                if (value.is_none()) {
                    c.entity = Entity();
                } else {
                    c.entity = nb::cast<Entity>(value);
                }
            })
        .def("c_component_ptr", [](CxxComponent& c) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(c.c_component());
        })
        .def("serialize", [](CxxComponent& c) -> nb::dict {
            nos::trent t = c.serialize();
            return nb::cast<nb::dict>(trent_to_py(t));
        })
        .def("serialize_data", [](CxxComponent& c) -> nb::dict {
            nos::trent t = c.serialize_data();
            return nb::cast<nb::dict>(trent_to_py(t));
        })
        .def("deserialize_data", [](CxxComponent& c, nb::dict data) {
            nos::trent t = py_to_trent(data);
            c.deserialize_data(t);
        }, nb::arg("data"));

    // --- ComponentRegistry ---
    nb::class_<ComponentRegistry>(m, "ComponentRegistry")
        .def_static("instance", &ComponentRegistry::instance, nb::rv_policy::reference)
        .def("register_native", &ComponentRegistry::register_native,
             nb::arg("name"), nb::arg("factory"), nb::arg("parent") = nullptr)
        .def("register_python", [](ComponentRegistry& reg, const std::string& name, nb::object cls, nb::object parent) {
            if (parent.is_none()) {
                reg.register_python(name, cls, nullptr);
            } else {
                std::string parent_str = nb::cast<std::string>(parent);
                reg.register_python(name, cls, parent_str.c_str());
            }
        }, nb::arg("name"), nb::arg("cls"), nb::arg("parent") = nb::none())
        .def("unregister", &ComponentRegistry::unregister, nb::arg("name"))
        .def("create", &ComponentRegistry::create, nb::arg("name"))
        .def("has", &ComponentRegistry::has, nb::arg("name"))
        .def_prop_ro("component_names", [](ComponentRegistry& reg) {
            return reg.list_all();
        })
        .def("list_all", &ComponentRegistry::list_all)
        .def("list_native", &ComponentRegistry::list_native)
        .def("list_python", &ComponentRegistry::list_python)
        .def("clear", &ComponentRegistry::clear);

    // --- Entity (in separate file for faster compilation) ---
    bind_entity_class(m);

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

    // --- Native Components ---
    BIND_NATIVE_COMPONENT(m, CXXRotatorComponent)
        .def_rw("speed", &CXXRotatorComponent::speed);

    // Register CxxComponent::enabled in InspectRegistry
    InspectRegistry::instance().add_with_accessors<CxxComponent, bool>(
        "Component", "enabled", "Enabled", "bool",
        [](CxxComponent* c) { return c->enabled(); },
        [](CxxComponent* c, bool v) { c->set_enabled(v); }
    );

    // --- Pool utilities ---

    m.def("get_standalone_pool", []() {
        return reinterpret_cast<uintptr_t>(Entity::standalone_pool());
    }, "Get the global standalone entity pool as uintptr_t");

    m.def("migrate_entity", [](Entity& entity, uintptr_t dst_pool_ptr) -> Entity {
        tc_entity_pool* dst_pool = reinterpret_cast<tc_entity_pool*>(dst_pool_ptr);
        return migrate_entity_to_pool(entity, dst_pool);
    }, nb::arg("entity"), nb::arg("dst_pool"),
       "Migrate entity to destination pool. Returns new Entity, old becomes invalid.");

    // Component registry info for debug viewer
    m.def("component_registry_get_all_info", []() {
        nb::list result;
        size_t count = tc_component_registry_type_count();
        for (size_t i = 0; i < count; i++) {
            const char* type_name = tc_component_registry_type_at(i);
            if (!type_name) continue;

            nb::dict info;
            info["name"] = type_name;
            info["kind"] = tc_component_registry_get_kind(type_name) == TC_CXX_COMPONENT ? "native" : "python";

            const char* parent = tc_component_registry_get_parent(type_name);
            info["parent"] = parent ? nb::str(parent) : nb::none();

            // Get descendants
            const char* descendants[64];
            size_t desc_count = tc_component_registry_get_type_and_descendants(type_name, descendants, 64);
            nb::list desc_list;
            for (size_t j = 1; j < desc_count; j++) {  // Skip first (self)
                desc_list.append(descendants[j]);
            }
            info["descendants"] = desc_list;

            result.append(info);
        }
        return result;
    });

    m.def("component_registry_type_count", []() {
        return tc_component_registry_type_count();
    });

    // Register atexit handler
    nb::object atexit_mod = nb::module_::import_("atexit");
    nb::object cleanup_fn = nb::cpp_function([]() {
        ComponentRegistry::instance().clear();
        EntityRegistry::instance().clear();
        tc::KindRegistry::instance().clear_python();
    });
    atexit_mod.attr("register")(cleanup_fn);
}
