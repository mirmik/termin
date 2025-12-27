/**
 * Entity native module (_entity_native).
 *
 * Contains Component, Entity, EntityHandle, EntityRegistry, ComponentRegistry.
 * Separated from _native to allow other modules (like _native with MeshRenderer)
 * to properly inherit from Component.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include <unordered_set>
#include <iostream>

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
#include "termin/entity/entity_handle.hpp"
#include "termin/entity/entity_registry.hpp"
#include "termin/entity/components/rotator_component.hpp"
#include "termin/geom/general_transform3.hpp"
#include "trent/trent.h"

namespace py = pybind11;
using namespace termin;

// --- trent <-> Python conversion ---

static nos::trent py_to_trent(py::object obj) {
    if (obj.is_none()) {
        return nos::trent::nil();
    }
    if (py::isinstance<py::bool_>(obj)) {
        return nos::trent(obj.cast<bool>());
    }
    if (py::isinstance<py::int_>(obj)) {
        return nos::trent(obj.cast<int64_t>());
    }
    if (py::isinstance<py::float_>(obj)) {
        return nos::trent(obj.cast<double>());
    }
    if (py::isinstance<py::str>(obj)) {
        return nos::trent(obj.cast<std::string>());
    }
    if (py::isinstance<py::list>(obj)) {
        nos::trent result;
        result.init(nos::trent_type::list);
        for (auto item : obj) {
            result.as_list().push_back(py_to_trent(py::reinterpret_borrow<py::object>(item)));
        }
        return result;
    }
    if (py::isinstance<py::dict>(obj)) {
        nos::trent result;
        result.init(nos::trent_type::dict);
        for (auto item : obj.cast<py::dict>()) {
            std::string key = item.first.cast<std::string>();
            result[key] = py_to_trent(py::reinterpret_borrow<py::object>(item.second));
        }
        return result;
    }
    return nos::trent::nil();
}

static py::object trent_to_py(const nos::trent& t) {
    switch (t.get_type()) {
        case nos::trent_type::nil:
            return py::none();
        case nos::trent_type::boolean:
            return py::bool_(t.as_bool());
        case nos::trent_type::numer: {
            double val = t.as_numer();
            // Return int if it's a whole number
            if (val == static_cast<int64_t>(val)) {
                return py::int_(static_cast<int64_t>(val));
            }
            return py::float_(val);
        }
        case nos::trent_type::string:
            return py::str(t.as_string());
        case nos::trent_type::list: {
            py::list result;
            for (const auto& item : t.as_list()) {
                result.append(trent_to_py(item));
            }
            return result;
        }
        case nos::trent_type::dict: {
            py::dict result;
            for (const auto& [key, val] : t.as_dict()) {
                result[py::str(key)] = trent_to_py(val);
            }
            return result;
        }
    }
    return py::none();
}

/**
 * Trampoline class for Component.
 * Allows Python classes to inherit from C++ Component.
 */
class PyComponent : public Component {
public:
    using Component::Component;

    void start() override {
        PYBIND11_OVERRIDE(void, Component, start);
    }

    void update(float dt) override {
        PYBIND11_OVERRIDE(void, Component, update, dt);
    }

    void fixed_update(float dt) override {
        PYBIND11_OVERRIDE(void, Component, fixed_update, dt);
    }

    void on_destroy() override {
        PYBIND11_OVERRIDE(void, Component, on_destroy);
    }

    void on_added_to_entity() override {
        PYBIND11_OVERRIDE(void, Component, on_added_to_entity);
    }

    void on_removed_from_entity() override {
        PYBIND11_OVERRIDE(void, Component, on_removed_from_entity);
    }

    void on_added(py::object scene) override {
        PYBIND11_OVERRIDE(void, Component, on_added, scene);
    }

    void on_removed() override {
        PYBIND11_OVERRIDE(void, Component, on_removed);
    }
};

// Helper: numpy array (3,) -> Vec3
static Vec3 numpy_to_vec3(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return Vec3{buf(0), buf(1), buf(2)};
}

// Helper: Vec3 -> numpy array (3,)
static py::array_t<double> vec3_to_numpy(const Vec3& v) {
    auto result = py::array_t<double>(3);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v.x;
    buf(1) = v.y;
    buf(2) = v.z;
    return result;
}

// Helper: numpy array (4,) -> Quat
static Quat numpy_to_quat(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return Quat{buf(0), buf(1), buf(2), buf(3)};
}

PYBIND11_MODULE(_entity_native, m) {
    m.doc() = "Entity native module (Component, Entity, EntityHandle, registries)";

    // --- Component ---
    py::class_<Component, PyComponent>(m, "Component")
        .def(py::init<>())
        .def(py::init([](bool enabled) {
            auto c = new PyComponent();
            c->enabled = enabled;
            return c;
        }), py::arg("enabled") = true)
        .def("type_name", &Component::type_name)
        .def("set_type_name", &Component::set_type_name, py::arg("name"))
        .def("start", &Component::start)
        .def("update", &Component::update, py::arg("dt"))
        .def("fixed_update", &Component::fixed_update, py::arg("dt"))
        .def("on_editor_start", &Component::on_editor_start)
        .def("setup_editor_defaults", &Component::setup_editor_defaults)
        .def("on_destroy", &Component::on_destroy)
        .def("on_added_to_entity", &Component::on_added_to_entity)
        .def("on_removed_from_entity", &Component::on_removed_from_entity)
        .def("on_added", &Component::on_added, py::arg("scene"))
        .def("on_removed", &Component::on_removed)
        .def_readwrite("enabled", &Component::enabled)
        .def_readwrite("active_in_editor", &Component::active_in_editor)
        .def_readonly("is_native", &Component::is_native)
        .def_readwrite("_started", &Component::_started)
        .def_readwrite("has_update", &Component::has_update)
        .def_readwrite("has_fixed_update", &Component::has_fixed_update)
        .def("sync_to_c", &Component::sync_to_c)
        .def("sync_from_c", &Component::sync_from_c)
        .def("c_component", static_cast<tc_component* (Component::*)()>(&Component::c_component),
             py::return_value_policy::reference)
        .def_property("entity",
            [](Component& c) -> py::object {
                if (c.entity) {
                    return py::cast(c.entity, py::return_value_policy::reference);
                }
                return py::none();
            },
            [](Component& c, py::object obj) {
                if (obj.is_none()) {
                    c.entity = nullptr;
                } else {
                    c.entity = obj.cast<Entity*>();
                }
            })
        .def("serialize_data", [](Component& c) {
            return trent_to_py(c.serialize_data());
        })
        .def("serialize", [](Component& c) {
            return trent_to_py(c.serialize());
        })
        .def("deserialize_data", [](Component& c, py::object data, py::object) {
            c.deserialize_data(py_to_trent(data));
        });

    // --- ComponentRegistry ---
    py::class_<ComponentRegistry>(m, "ComponentRegistry")
        .def_static("instance", &ComponentRegistry::instance, py::return_value_policy::reference)
        .def("register_python", &ComponentRegistry::register_python,
             py::arg("name"), py::arg("cls"))
        .def("unregister", &ComponentRegistry::unregister, py::arg("name"))
        .def("create", &ComponentRegistry::create, py::arg("name"))
        .def("has", &ComponentRegistry::has, py::arg("name"))
        .def("list_all", &ComponentRegistry::list_all)
        .def("list_native", &ComponentRegistry::list_native)
        .def("list_python", &ComponentRegistry::list_python)
        .def("clear", &ComponentRegistry::clear);

    // --- EntityHandle ---
    py::class_<EntityHandle>(m, "EntityHandle")
        .def(py::init<>())
        .def(py::init<const std::string&>(), py::arg("uuid"))
        .def_readwrite("uuid", &EntityHandle::uuid)
        .def_property_readonly("entity", &EntityHandle::get, py::return_value_policy::reference)
        .def_property_readonly("is_valid", &EntityHandle::is_valid)
        .def_property_readonly("name", &EntityHandle::name)
        .def_static("from_entity", &EntityHandle::from_entity, py::arg("entity"))
        .def("get", &EntityHandle::get, py::return_value_policy::reference)
        .def("__repr__", [](const EntityHandle& h) {
            std::string status = h.get() ? "resolved" : "unresolved";
            std::string uuid_short = h.uuid.size() > 8 ? h.uuid.substr(0, 8) + "..." : h.uuid;
            return "<EntityHandle " + uuid_short + " (" + status + ")>";
        });

    // --- Entity ---
    py::class_<Entity>(m, "Entity")
        .def(py::init<const std::string&, const std::string&>(),
             py::arg("name") = "entity", py::arg("uuid") = "")
        .def(py::init([](py::object pose, const std::string& name, int priority,
                        bool pickable, bool selectable, bool serializable,
                        int layer, uint64_t flags, const std::string& uuid) {
            Entity* ent;
            if (pose.is_none()) {
                ent = new Entity(name, uuid);
            } else {
                // Extract GeneralPose3 from Python object
                GeneralPose3 gpose;
                if (py::hasattr(pose, "lin") && py::hasattr(pose, "ang")) {
                    auto lin = pose.attr("lin").cast<py::array_t<double>>();
                    auto ang = pose.attr("ang").cast<py::array_t<double>>();
                    gpose.lin = numpy_to_vec3(lin);
                    gpose.ang = numpy_to_quat(ang);
                    if (py::hasattr(pose, "scale")) {
                        auto scale = pose.attr("scale").cast<py::array_t<double>>();
                        gpose.scale = numpy_to_vec3(scale);
                    }
                }
                ent = new Entity(gpose, name, uuid);
            }
            // Set additional attributes
            ent->set_priority(priority);
            ent->set_pickable(pickable);
            ent->set_selectable(selectable);
            ent->set_serializable(serializable);
            ent->set_layer(static_cast<uint64_t>(layer));
            ent->set_flags(flags);
            return ent;
        }), py::arg("pose") = py::none(), py::arg("name") = "entity",
            py::arg("priority") = 0, py::arg("pickable") = true,
            py::arg("selectable") = true, py::arg("serializable") = true,
            py::arg("layer") = 0, py::arg("flags") = 0, py::arg("uuid") = "")

        // Identity
        .def_property_readonly("uuid", [](const Entity& e) -> py::object {
            const char* u = e.uuid();
            if (u) return py::str(u);
            return py::none();
        })
        .def_property("name",
            [](const Entity& e) -> py::object {
                const char* n = e.name();
                if (n) return py::str(n);
                return py::none();
            },
            [](Entity& e, const std::string& n) {
                e.set_name(n);
            })
        .def_property_readonly("runtime_id", [](const Entity& e) -> uint64_t {
            return e.runtime_id();
        })

        // Flags
        .def_property("visible",
            [](const Entity& e) { return e.visible(); },
            [](Entity& e, bool v) { e.set_visible(v); })
        .def_property("active",
            [](const Entity& e) { return e.active(); },
            [](Entity& e, bool v) { e.set_active(v); })
        .def_property("pickable",
            [](const Entity& e) { return e.pickable(); },
            [](Entity& e, bool v) { e.set_pickable(v); })
        .def_property("selectable",
            [](const Entity& e) { return e.selectable(); },
            [](Entity& e, bool v) { e.set_selectable(v); })

        // Rendering
        .def_property("priority",
            [](const Entity& e) { return e.priority(); },
            [](Entity& e, int p) { e.set_priority(p); })
        .def_property("layer",
            [](const Entity& e) { return e.layer(); },
            [](Entity& e, uint64_t l) { e.set_layer(l); })
        .def_property("flags",
            [](const Entity& e) { return e.flags(); },
            [](Entity& e, uint64_t f) { e.set_flags(f); })

        // Pick ID
        .def_property_readonly("pick_id", &Entity::pick_id)

        // Transform access - returns the GeneralTransform3 wrapper
        .def_property_readonly("transform", [](Entity& e) -> GeneralTransform3 {
            return e.transform();
        })

        // Pose shortcuts
        .def("global_pose", [](Entity& e) {
            const GeneralPose3& gp = e.global_pose();
            py::dict result;
            result["lin"] = vec3_to_numpy(gp.lin);
            result["ang"] = py::array_t<double>({4}, {sizeof(double)},
                &gp.ang.x);
            result["scale"] = vec3_to_numpy(gp.scale);
            return result;
        })

        .def("model_matrix", [](Entity& e) {
            auto result = py::array_t<double>({4, 4});
            auto buf = result.mutable_unchecked<2>();
            double m[16];
            e.model_matrix(m);
            // matrix4() already produces row-major, copy directly
            for (int i = 0; i < 4; ++i) {
                for (int j = 0; j < 4; ++j) {
                    buf(i, j) = m[i * 4 + j];
                }
            }
            return result;
        })

        .def("inverse_model_matrix", [](Entity& e) {
            // Get global pose and compute inverse matrix
            const GeneralPose3& gp = e.global_pose();
            auto result = py::array_t<double>({4, 4});
            auto buf = result.mutable_unchecked<2>();
            double m[16];
            gp.inverse_matrix4(m);
            // inverse_matrix4() already produces row-major, copy directly
            for (int i = 0; i < 4; ++i) {
                for (int j = 0; j < 4; ++j) {
                    buf(i, j) = m[i * 4 + j];
                }
            }
            return result;
        })

        .def("set_visible", [](Entity& e, bool flag) {
            e.set_visible(flag);
            for (Entity* child : e.children()) {
                py::cast(child, py::return_value_policy::reference).attr("set_visible")(flag);
            }
        }, py::arg("flag"))

        .def("is_pickable", [](Entity& e) {
            return e.pickable() && e.visible() && e.active();
        })

        .def_static("lookup_by_pick_id", [](uint32_t pid) -> Entity* {
            return EntityRegistry::instance().get_by_pick_id(pid);
        }, py::arg("pick_id"), py::return_value_policy::reference)

        // Component management
        // Accepts both C++ Component and PythonComponent (via py::object)
        // Note: Scene registration is handled by Python Scene.add(), not here
        .def("add_component", [](Entity& e, py::object component) -> py::object {
            // Check if it's a C++ Component
            if (py::isinstance<Component>(component)) {
                e.add_component(component.cast<Component*>());
                return component;
            }

            // Check if it's a PythonComponent (has c_component_ptr method)
            if (py::hasattr(component, "c_component_ptr")) {
                uintptr_t ptr = component.attr("c_component_ptr")().cast<uintptr_t>();
                tc_component* tc = reinterpret_cast<tc_component*>(ptr);

                // Set entity reference on PythonComponent
                if (py::hasattr(component, "entity")) {
                    component.attr("entity") = py::cast(&e, py::return_value_policy::reference);
                }

                e.add_component_ptr(tc);
                return component;
            }

            throw std::runtime_error("add_component requires Component or PythonComponent");
        }, py::arg("component"), py::keep_alive<1, 2>())
        .def("remove_component", [](Entity& e, py::object component) {
            // Check if it's a C++ Component
            if (py::isinstance<Component>(component)) {
                e.remove_component(component.cast<Component*>());
                return;
            }

            // Check if it's a PythonComponent
            if (py::hasattr(component, "c_component_ptr")) {
                uintptr_t ptr = component.attr("c_component_ptr")().cast<uintptr_t>();
                e.remove_component_ptr(reinterpret_cast<tc_component*>(ptr));
                return;
            }

            throw std::runtime_error("remove_component requires Component or PythonComponent");
        }, py::arg("component"))
        .def("get_component_by_type", &Entity::get_component_by_type,
             py::arg("type_name"), py::return_value_policy::reference)
        .def("get_component", [](Entity& e, py::object type_class) -> py::object {
            // Get component by Python type class (like Unity's GetComponent<T>())
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                py::object py_comp;
                if (tc->is_native) {
                    Component* comp = static_cast<Component*>(tc->data);
                    py_comp = py::cast(comp, py::return_value_policy::reference);
                } else {
                    // PythonComponent - data is PyObject*
                    py_comp = py::reinterpret_borrow<py::object>((PyObject*)tc->data);
                }

                if (py::isinstance(py_comp, type_class)) {
                    return py_comp;
                }
            }
            return py::none();
        }, py::arg("component_type"))
        .def("find_component", [](Entity& e, py::object type_class) -> py::object {
            // Get component by Python type class, raise if not found
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                py::object py_comp;
                if (tc->is_native) {
                    Component* comp = static_cast<Component*>(tc->data);
                    py_comp = py::cast(comp, py::return_value_policy::reference);
                } else {
                    py_comp = py::reinterpret_borrow<py::object>((PyObject*)tc->data);
                }

                if (py::isinstance(py_comp, type_class)) {
                    return py_comp;
                }
            }
            throw std::runtime_error("Component not found");
        }, py::arg("component_type"))
        .def_property_readonly("components", [](Entity& e) {
            py::list result;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                if (tc->is_native) {
                    Component* comp = static_cast<Component*>(tc->data);
                    result.append(py::cast(comp, py::return_value_policy::reference));
                } else {
                    // PythonComponent - data is PyObject*
                    result.append(py::reinterpret_borrow<py::object>((PyObject*)tc->data));
                }
            }
            return result;
        })

        // Hierarchy
        .def("set_parent", &Entity::set_parent, py::arg("parent"),
             py::keep_alive<2, 1>())  // parent keeps child alive
        .def_property_readonly("parent", &Entity::parent, py::return_value_policy::reference)
        .def("children", &Entity::children)

        // Lifecycle
        .def("update", &Entity::update, py::arg("dt"))
        .def("on_added_to_scene", &Entity::on_added_to_scene, py::arg("scene"))
        .def("on_removed_from_scene", &Entity::on_removed_from_scene)
        // Lifecycle - Scene handles component registration in Python
        .def("on_added", [](Entity& e, py::object scene) {
            e.on_added_to_scene(scene);
        }, py::arg("scene"))
        .def("on_removed", [](Entity& e) {
            e.on_removed_from_scene();
        })

        // Serialization
        .def_property("serializable",
            [](const Entity& e) { return e.serializable(); },
            [](Entity& e, bool v) { e.set_serializable(v); })
        .def("serialize", [](Entity& e) -> py::object {
            nos::trent data = e.serialize();
            if (data.is_nil()) {
                return py::none();
            }
            py::dict result = trent_to_py(data).cast<py::dict>();

            // Serialize components by calling their Python serialize() methods
            py::list comp_list;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                py::object py_comp;
                if (tc->is_native) {
                    py_comp = py::cast(static_cast<Component*>(tc->data), py::return_value_policy::reference);
                } else {
                    py_comp = py::reinterpret_borrow<py::object>((PyObject*)tc->data);
                }

                if (py::hasattr(py_comp, "serialize")) {
                    py::object comp_data = py_comp.attr("serialize")();
                    if (!comp_data.is_none()) {
                        comp_list.append(comp_data);
                    }
                }
            }
            result["components"] = comp_list;

            // Serialize children recursively
            py::list children_list;
            for (Entity* child : e.children()) {
                if (child->serializable()) {
                    py::object child_obj = py::cast(child, py::return_value_policy::reference);
                    py::object child_data = child_obj.attr("serialize")();
                    if (!child_data.is_none()) {
                        children_list.append(child_data);
                    }
                }
            }
            result["children"] = children_list;

            return result;
        })
        .def_static("deserialize", [](py::object data, py::object context) -> py::object {
            if (data.is_none()) {
                return py::none();
            }
            nos::trent tdata = py_to_trent(data);
            Entity* ent = Entity::deserialize(tdata);
            if (!ent) {
                return py::none();
            }
            return py::cast(ent, py::return_value_policy::take_ownership);
        }, py::arg("data"), py::arg("context") = py::none());

    // --- EntityRegistry ---
    py::class_<EntityRegistry>(m, "EntityRegistry")
        .def_static("instance", &EntityRegistry::instance, py::return_value_policy::reference)
        .def("get", &EntityRegistry::get, py::arg("uuid"),
             py::return_value_policy::reference)
        .def("get_by_pick_id", &EntityRegistry::get_by_pick_id, py::arg("pick_id"),
             py::return_value_policy::reference)
        .def("clear", &EntityRegistry::clear)
        .def_property_readonly("entity_count", &EntityRegistry::entity_count)
        .def("swap_registries", [](EntityRegistry& reg, py::object new_by_uuid, py::object new_by_pick_id) {
            // Convert Python dicts to C++ maps
            std::unordered_map<std::string, Entity*> cpp_by_uuid;
            std::unordered_map<uint32_t, Entity*> cpp_by_pick_id;

            // new_by_uuid: dict[str, Entity] or WeakValueDictionary
            if (!new_by_uuid.is_none()) {
                for (auto item : new_by_uuid.attr("items")()) {
                    auto pair = item.cast<py::tuple>();
                    std::string uuid = pair[0].cast<std::string>();
                    Entity* ent = pair[1].cast<Entity*>();
                    cpp_by_uuid[uuid] = ent;
                }
            }

            // new_by_pick_id: dict[int, Entity]
            if (!new_by_pick_id.is_none()) {
                for (auto item : new_by_pick_id.attr("items")()) {
                    auto pair = item.cast<py::tuple>();
                    uint32_t pick_id = pair[0].cast<uint32_t>();
                    Entity* ent = pair[1].cast<Entity*>();
                    cpp_by_pick_id[pick_id] = ent;
                }
            }

            // Perform the swap
            auto [old_by_uuid, old_by_pick_id] = reg.swap_registries(
                std::move(cpp_by_uuid), std::move(cpp_by_pick_id));

            // Convert old registries back to Python dicts
            py::dict py_old_by_uuid;
            for (auto& [uuid, ent] : old_by_uuid) {
                if (ent) {
                    py_old_by_uuid[py::str(uuid)] = py::cast(ent, py::return_value_policy::reference);
                }
            }

            py::dict py_old_by_pick_id;
            for (auto& [pick_id, ent] : old_by_pick_id) {
                if (ent) {
                    py_old_by_pick_id[py::int_(pick_id)] = py::cast(ent, py::return_value_policy::reference);
                }
            }

            return py::make_tuple(py_old_by_uuid, py_old_by_pick_id);
        }, py::arg("new_by_uuid"), py::arg("new_by_pick_id"));

    // --- Native Components ---
    BIND_NATIVE_COMPONENT(m, CXXRotatorComponent)
        .def_readwrite("speed", &CXXRotatorComponent::speed);

    // Register Component::enabled in InspectRegistry for all components to inherit
    InspectRegistry::instance().add<Component, bool>(
        "Component", &Component::enabled, "enabled", "Enabled", "bool"
    );
}
