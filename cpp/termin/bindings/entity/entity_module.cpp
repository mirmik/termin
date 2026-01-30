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

extern "C" {
#include "tc_binding.h"
}
#include "entity_bindings.hpp"
#include "../camera/camera_bindings.hpp"
#include "../camera/orbit_camera_bindings.hpp"
#include "../input/input_events_bindings.hpp"

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
#include "termin/entity/component_registry_python.hpp"
#include "termin/entity/vtable_utils.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/entity_registry.hpp"
#include "termin/entity/components/rotator_component.hpp"
#include "termin/geom/general_transform3.hpp"
#include "termin/geom/pose3.hpp"
#include "termin/inspect/tc_kind.hpp"
#include "termin/bindings/tc_value_helpers.hpp"
#include "termin/modules/module_loader.hpp"
#include "termin/tc_scene_ref.hpp"

namespace nb = nanobind;
using namespace termin;

NB_MODULE(_entity_native, m) {
    m.doc() = "Entity native module (Component, Entity, registries)";

    // Import _viewport_native for TcViewport type (used by input events)
    nb::module_::import_("termin.viewport._viewport_native");

    // --- CxxComponent (also exported as Component for compatibility) ---
    nb::class_<CxxComponent>(m, "Component", nb::dynamic_attr())
        .def("__init__", [](nb::handle self) {
            cxx_component_init<CxxComponent>(self);
        })
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
        .def_prop_ro("is_input_handler", &CxxComponent::is_input_handler)
        .def_prop_ro("entity",
            [](CxxComponent& c) -> nb::object {
                Entity ent = c.entity();
                if (ent.valid()) {
                    return nb::cast(ent);
                }
                return nb::none();
            })
        .def("c_component_ptr", [](CxxComponent& c) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(c.c_component());
        })
        .def("serialize", [](CxxComponent& c) -> nb::dict {
            tc_value v = c.serialize();
            nb::object result = tc_value_to_py(&v);
            tc_value_free(&v);
            return nb::cast<nb::dict>(result);
        })
        .def("serialize_data", [](CxxComponent& c) -> nb::dict {
            tc_value v = c.serialize_data();
            nb::object result = tc_value_to_py(&v);
            tc_value_free(&v);
            return nb::cast<nb::dict>(result);
        })
        .def("deserialize_data", [](CxxComponent& c, nb::dict data) {
            tc_value v = py_to_tc_value(data);
            c.deserialize_data(&v);
            tc_value_free(&v);
        }, nb::arg("data"))
        .def("__eq__", [](CxxComponent& self, nb::object other) -> bool {
            if (!nb::isinstance<CxxComponent>(other)) return false;
            CxxComponent& other_c = nb::cast<CxxComponent&>(other);
            return self.c_component() == other_c.c_component();
        })
        .def("__hash__", [](CxxComponent& self) -> size_t {
            return reinterpret_cast<size_t>(self.c_component());
        });

    // --- ComponentRegistry ---
    // Note: register_native is not exposed to Python - it takes C function pointers.
    // Python components should use register_python instead.
    nb::class_<ComponentRegistry>(m, "ComponentRegistry")
        .def_static("instance", &ComponentRegistry::instance, nb::rv_policy::reference)
        .def("register_python", [](ComponentRegistry&, const std::string& name, nb::object cls, nb::object parent) {
            if (parent.is_none()) {
                ComponentRegistryPython::register_python(name, cls, nullptr);
            } else {
                std::string parent_str = nb::cast<std::string>(parent);
                ComponentRegistryPython::register_python(name, cls, parent_str.c_str());
            }
        }, nb::arg("name"), nb::arg("cls"), nb::arg("parent") = nb::none())
        .def("unregister", &ComponentRegistry::unregister, nb::arg("name"))
        .def("has", &ComponentRegistry::has, nb::arg("name"))
        .def_prop_ro("component_names", [](ComponentRegistry& reg) {
            return reg.list_all();
        })
        .def("list_all", &ComponentRegistry::list_all)
        .def("list_native", &ComponentRegistry::list_native)
        .def("list_python", [](ComponentRegistry& /*self*/) {
            return ComponentRegistryPython::list_python();
        })
        .def("clear", &ComponentRegistry::clear)
        .def_static("set_drawable", &ComponentRegistry::set_drawable,
            nb::arg("name"), nb::arg("is_drawable"),
            "Mark a component type as drawable (can render geometry)")
        .def_static("set_input_handler", &ComponentRegistry::set_input_handler,
            nb::arg("name"), nb::arg("is_input_handler"),
            "Mark a component type as input handler")
        .def_static("get_input_handler_types", []() {
            const char* types[64];
            size_t count = tc_component_registry_get_input_handler_types(types, 64);
            std::vector<std::string> result;
            for (size_t i = 0; i < count; i++) {
                result.push_back(types[i]);
            }
            return result;
        }, "Get all input handler type names");

    // --- Entity (in separate file for faster compilation) ---
    bind_entity_class(m);

    // --- CameraComponent ---
    bind_camera_component(m);

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

    // --- Native Components ---
    BIND_NATIVE_COMPONENT(m, CXXRotatorComponent)
        .def_rw("speed", &CXXRotatorComponent::speed);

    // Register CxxComponent::enabled in InspectRegistry
    tc::InspectRegistry::instance().add_with_accessors<CxxComponent, bool>(
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
            info["language"] = tc_component_registry_get_kind(type_name) == TC_CXX_COMPONENT ? "C++" : "Python";

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

            // Is drawable
            info["is_drawable"] = tc_component_registry_is_drawable(type_name);

            result.append(info);
        }
        return result;
    });

    m.def("component_registry_type_count", []() {
        return tc_component_registry_type_count();
    });

    // --- ModuleLoader (hot-reload system for C++ modules) ---
    nb::class_<ModuleDescriptor>(m, "ModuleDescriptor")
        .def_ro("name", &ModuleDescriptor::name)
        .def_ro("path", &ModuleDescriptor::path)
        .def_ro("sources", &ModuleDescriptor::sources)
        .def_ro("include_dirs", &ModuleDescriptor::include_dirs)
        .def_ro("components", &ModuleDescriptor::components);

    nb::class_<LoadedModule>(m, "LoadedModule")
        .def_ro("name", &LoadedModule::name)
        .def_ro("dll_path", &LoadedModule::dll_path)
        .def_ro("descriptor", &LoadedModule::descriptor)
        .def_ro("registered_components", &LoadedModule::registered_components);

    nb::class_<ModuleLoader>(m, "ModuleLoader")
        .def_static("instance", &ModuleLoader::instance, nb::rv_policy::reference)
        .def("load_module", &ModuleLoader::load_module, nb::arg("module_path"),
             "Load a module from .module descriptor file")
        .def("unload_module", &ModuleLoader::unload_module, nb::arg("name"),
             "Unload a module by name")
        .def("reload_module", &ModuleLoader::reload_module, nb::arg("name"),
             "Reload a module (unload + compile + load)")
        .def("compile_module", &ModuleLoader::compile_module, nb::arg("name"),
             "Compile a module, returns path to DLL or empty string on error")
        .def_prop_ro("last_error", &ModuleLoader::last_error,
             "Get last error message")
        .def_prop_ro("compiler_output", &ModuleLoader::compiler_output,
             "Get compiler output from last compilation")
        .def("list_modules", &ModuleLoader::list_modules,
             "Get list of loaded module names")
        .def("get_module", &ModuleLoader::get_module, nb::arg("name"),
             nb::rv_policy::reference,
             "Get module info by name")
        .def("is_loaded", &ModuleLoader::is_loaded, nb::arg("name"),
             "Check if a module is loaded")
        .def("set_event_callback", [](ModuleLoader& loader, nb::object callback) {
            if (callback.is_none()) {
                loader.set_event_callback(nullptr);
            } else {
                loader.set_event_callback([callback](const std::string& module_name, const std::string& event) {
                    nb::gil_scoped_acquire gil;
                    callback(module_name, event);
                });
            }
        }, nb::arg("callback"),
             "Set callback for module events (loading, loaded, unloading, etc.)")
        .def_prop_ro("core_c", &ModuleLoader::get_core_c,
             "Get C API include directory")
        .def_prop_ro("core_cpp", &ModuleLoader::get_core_cpp,
             "Get C++ include directory")
        .def_prop_ro("lib_dir", &ModuleLoader::get_lib_dir,
             "Get library directory")
        .def("set_engine_paths", &ModuleLoader::set_engine_paths,
             nb::arg("core_c"), nb::arg("core_cpp"), nb::arg("lib_dir"),
             "Set engine paths for module compilation");

    // Register atexit handler
    nb::object atexit_mod = nb::module_::import_("atexit");
    nb::object cleanup_fn = nb::cpp_function([]() {
        ComponentRegistry::instance().clear();
        EntityRegistry::instance().clear();
        tc::KindRegistry::instance().clear_python();
    });
    atexit_mod.attr("register")(cleanup_fn);
}
