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
#include <cstdio>

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

// Shortcut for standalone pool
static tc_entity_pool* get_standalone_pool() {
    return Entity::standalone_pool();
}

// Migrate entity from one pool to another (e.g., when adding to Scene)
// Returns new Entity in dst_pool, old entity becomes invalid
static Entity migrate_entity_to_pool(Entity& entity, tc_entity_pool* dst_pool) {
    if (!entity.valid() || !dst_pool) {
        return Entity();
    }

    tc_entity_pool* src_pool = entity.pool();
    if (src_pool == dst_pool) {
        // Already in target pool
        return entity;
    }

    tc_entity_id new_id = tc_entity_pool_migrate(src_pool, entity.id(), dst_pool);
    if (!tc_entity_id_valid(new_id)) {
        return Entity();
    }

    return Entity(dst_pool, new_id);
}

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

// Trampoline class for CxxComponent.
// Allows Python classes to inherit from C++ CxxComponent.
class PyCxxComponent : public CxxComponent {
public:
    using CxxComponent::CxxComponent;

    void start() override {
        PYBIND11_OVERRIDE(void, CxxComponent, start);
    }

    void update(float dt) override {
        PYBIND11_OVERRIDE(void, CxxComponent, update, dt);
    }

    void fixed_update(float dt) override {
        PYBIND11_OVERRIDE(void, CxxComponent, fixed_update, dt);
    }

    void on_destroy() override {
        PYBIND11_OVERRIDE(void, CxxComponent, on_destroy);
    }

    void on_added_to_entity() override {
        PYBIND11_OVERRIDE(void, CxxComponent, on_added_to_entity);
    }

    void on_removed_from_entity() override {
        PYBIND11_OVERRIDE(void, CxxComponent, on_removed_from_entity);
    }

    void on_added(py::object scene) override {
        PYBIND11_OVERRIDE(void, CxxComponent, on_added, scene);
    }

    void on_removed() override {
        PYBIND11_OVERRIDE(void, CxxComponent, on_removed);
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

    // --- CxxComponent (also exported as Component for compatibility) ---
    py::class_<CxxComponent, PyCxxComponent>(m, "Component")
        .def(py::init<>())
        .def(py::init([](bool enabled) {
            auto c = new PyCxxComponent();
            c->set_enabled(enabled);
            return c;
        }), py::arg("enabled") = true)
        .def("type_name", &CxxComponent::type_name)
        .def("set_type_name", &CxxComponent::set_type_name, py::arg("name"))
        .def("start", &CxxComponent::start)
        .def("update", &CxxComponent::update, py::arg("dt"))
        .def("fixed_update", &CxxComponent::fixed_update, py::arg("dt"))
        .def("on_editor_start", &CxxComponent::on_editor_start)
        .def("setup_editor_defaults", &CxxComponent::setup_editor_defaults)
        .def("on_destroy", &CxxComponent::on_destroy)
        .def("on_added_to_entity", &CxxComponent::on_added_to_entity)
        .def("on_removed_from_entity", &CxxComponent::on_removed_from_entity)
        .def("on_added", &CxxComponent::on_added, py::arg("scene"))
        .def("on_removed", &CxxComponent::on_removed)
        .def_property("enabled", &CxxComponent::enabled, &CxxComponent::set_enabled)
        .def_property("active_in_editor", &CxxComponent::active_in_editor, &CxxComponent::set_active_in_editor)
        .def_property("_started", &CxxComponent::started, &CxxComponent::set_started)
        .def_property("has_update", &CxxComponent::has_update, &CxxComponent::set_has_update)
        .def_property("has_fixed_update", &CxxComponent::has_fixed_update, &CxxComponent::set_has_fixed_update)
        .def("c_component", static_cast<tc_component* (CxxComponent::*)()>(&CxxComponent::c_component),
             py::return_value_policy::reference)
        .def_property("entity",
            [](CxxComponent& c) -> py::object {
                if (c.entity.valid()) {
                    return py::cast(c.entity);
                }
                return py::none();
            },
            [](CxxComponent& c, py::object obj) {
                if (obj.is_none()) {
                    c.entity = Entity();  // Invalid entity
                } else {
                    c.entity = obj.cast<Entity>();
                }
            })
        .def("serialize_data", [](CxxComponent& c) {
            return trent_to_py(c.serialize_data());
        })
        .def("serialize", [](CxxComponent& c) {
            return trent_to_py(c.serialize());
        })
        .def("deserialize_data", [](CxxComponent& c, py::object data, py::object) {
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
        .def(py::init([](const std::string& name, const std::string& uuid) {
            // Create entity in standalone pool
            // TODO: Entities should be created through Scene instead
            Entity ent = Entity::create(get_standalone_pool(), name);
            return ent;
        }), py::arg("name") = "entity", py::arg("uuid") = "")
        .def(py::init([](py::object pose, const std::string& name, int priority,
                        bool pickable, bool selectable, bool serializable,
                        int layer, uint64_t flags, const std::string& uuid) {
            // Create entity in standalone pool
            Entity ent = Entity::create(get_standalone_pool(), name);

            if (!pose.is_none()) {
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
                ent.transform().set_local_pose(gpose);
            }
            // Set additional attributes
            ent.set_priority(priority);
            ent.set_pickable(pickable);
            ent.set_selectable(selectable);
            ent.set_serializable(serializable);
            ent.set_layer(static_cast<uint64_t>(layer));
            ent.set_flags(flags);
            return ent;
        }), py::arg("pose") = py::none(), py::arg("name") = "entity",
            py::arg("priority") = 0, py::arg("pickable") = true,
            py::arg("selectable") = true, py::arg("serializable") = true,
            py::arg("layer") = 0, py::arg("flags") = 0, py::arg("uuid") = "")

        // Validity
        .def("valid", &Entity::valid)
        .def("__bool__", &Entity::valid)

        // Identity
        .def_property_readonly("uuid", [](const Entity& e) -> py::object {
            const char* u = e.uuid();
            if (u) return py::str(u);
            return py::none();
        })
        // Equality based on (pool, id) - required for dict/set lookups
        .def("__eq__", [](const Entity& a, const Entity& b) {
            return a.pool() == b.pool() &&
                   a.id().index == b.id().index &&
                   a.id().generation == b.id().generation;
        })
        .def("__hash__", [](const Entity& e) {
            // Hash based on pool pointer and entity id
            size_t h = std::hash<void*>()(e.pool());
            h ^= std::hash<uint32_t>()(e.id().index) + 0x9e3779b9 + (h << 6) + (h >> 2);
            h ^= std::hash<uint32_t>()(e.id().generation) + 0x9e3779b9 + (h << 6) + (h >> 2);
            return h;
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
            GeneralPose3 gp = e.transform().global_pose();
            py::dict result;
            result["lin"] = vec3_to_numpy(gp.lin);
            auto ang_arr = py::array_t<double>(4);
            auto ang_buf = ang_arr.mutable_unchecked<1>();
            ang_buf(0) = gp.ang.x;
            ang_buf(1) = gp.ang.y;
            ang_buf(2) = gp.ang.z;
            ang_buf(3) = gp.ang.w;
            result["ang"] = ang_arr;
            result["scale"] = vec3_to_numpy(gp.scale);
            return result;
        })

        .def("model_matrix", [](Entity& e) {
            auto result = py::array_t<double>({4, 4});
            auto buf = result.mutable_unchecked<2>();
            double m[16];
            e.transform().world_matrix(m);
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
            GeneralPose3 gp = e.transform().global_pose();
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
            for (Entity child : e.children()) {
                child.set_visible(flag);
            }
        }, py::arg("flag"))

        .def("is_pickable", [](Entity& e) {
            return e.pickable() && e.visible() && e.active();
        })

        .def_static("lookup_by_pick_id", [](uint32_t pid) -> py::object {
            Entity ent = EntityRegistry::instance().get_by_pick_id(pid);
            if (ent.valid()) {
                return py::cast(ent);
            }
            return py::none();
        }, py::arg("pick_id"))

        // Component management
        // Accepts both C++ Component and PythonComponent (via py::object)
        // Note: Scene registration is handled by Python Scene.add(), not here
        .def("add_component", [](Entity& e, py::object component) -> py::object {
            // Check if it's a C++ Component
            if (py::isinstance<Component>(component)) {
                Component* c = component.cast<Component*>();
                // Store Python wrapper in py_wrap to keep it alive while attached to entity
                // set_py_wrap does INCREF
                c->set_py_wrap(component);
                e.add_component(c);
                return component;
            }

            // Check if it's a PythonComponent (has c_component_ptr method)
            if (py::hasattr(component, "c_component_ptr")) {
                uintptr_t ptr = component.attr("c_component_ptr")().cast<uintptr_t>();
                tc_component* tc = reinterpret_cast<tc_component*>(ptr);

                // Set entity reference on PythonComponent
                if (py::hasattr(component, "entity")) {
                    component.attr("entity") = py::cast(e);
                }

                e.add_component_ptr(tc);
                return component;
            }

            throw std::runtime_error("add_component requires Component or PythonComponent");
        }, py::arg("component"))
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
            if (!e.valid()) {
                return py::none();
            }
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                py::object py_comp = CxxComponent::tc_to_python(tc);

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

                py::object py_comp = CxxComponent::tc_to_python(tc);

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

                py::object py_comp = CxxComponent::tc_to_python(tc);
                if (!py_comp.is_none()) {
                    result.append(py_comp);
                }
            }
            return result;
        })

        // Hierarchy
        .def("set_parent", [](Entity& e, py::object parent_obj) {
            if (parent_obj.is_none()) {
                e.set_parent(Entity());  // Invalid entity = no parent
            } else {
                Entity parent = parent_obj.cast<Entity>();
                e.set_parent(parent);
            }
        }, py::arg("parent"))
        .def_property_readonly("parent", [](Entity& e) -> py::object {
            Entity p = e.parent();
            if (p.valid()) {
                return py::cast(p);
            }
            return py::none();
        })
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

        // Validation - for debugging memory corruption
        .def("validate_components", &Entity::validate_components)

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

                py::object py_comp = CxxComponent::tc_to_python(tc);

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
            for (Entity child : e.children()) {
                if (child.serializable()) {
                    nos::trent child_data = child.serialize();
                    if (!child_data.is_nil()) {
                        children_list.append(trent_to_py(child_data));
                    }
                }
            }
            result["children"] = children_list;

            return result;
        })
        .def_static("deserialize", [](py::object data, py::object context) -> py::object {
            if (data.is_none() || !py::isinstance<py::dict>(data)) {
                return py::none();
            }

            py::dict dict_data = data.cast<py::dict>();

            // Get entity name
            std::string name = "entity";
            if (dict_data.contains("name")) {
                name = dict_data["name"].cast<std::string>();
            }

            // Create entity using standalone pool
            Entity ent = Entity::create(get_standalone_pool(), name);
            if (!ent.valid()) {
                return py::none();
            }

            // TODO: UUID is set at creation time, need Entity::create_with_uuid
            // For now, skip UUID restoration - entity gets a new UUID
            (void)dict_data;  // suppress unused warning if uuid handling removed

            // Restore flags
            if (dict_data.contains("priority")) {
                ent.set_priority(dict_data["priority"].cast<int>());
            }
            if (dict_data.contains("visible")) {
                ent.set_visible(dict_data["visible"].cast<bool>());
            }
            if (dict_data.contains("active")) {
                ent.set_active(dict_data["active"].cast<bool>());
            }
            if (dict_data.contains("pickable")) {
                ent.set_pickable(dict_data["pickable"].cast<bool>());
            }
            if (dict_data.contains("selectable")) {
                ent.set_selectable(dict_data["selectable"].cast<bool>());
            }
            if (dict_data.contains("layer")) {
                ent.set_layer(dict_data["layer"].cast<uint64_t>());
            }
            if (dict_data.contains("flags")) {
                ent.set_flags(dict_data["flags"].cast<uint64_t>());
            }

            // Restore pose
            if (dict_data.contains("pose") && py::isinstance<py::dict>(dict_data["pose"])) {
                py::dict pose = dict_data["pose"].cast<py::dict>();
                if (pose.contains("position") && py::isinstance<py::list>(pose["position"])) {
                    py::list pos = pose["position"].cast<py::list>();
                    if (pos.size() >= 3) {
                        double xyz[3] = {pos[0].cast<double>(), pos[1].cast<double>(), pos[2].cast<double>()};
                        ent.set_local_position(xyz);
                    }
                }
                if (pose.contains("rotation") && py::isinstance<py::list>(pose["rotation"])) {
                    py::list rot = pose["rotation"].cast<py::list>();
                    if (rot.size() >= 4) {
                        double xyzw[4] = {rot[0].cast<double>(), rot[1].cast<double>(), rot[2].cast<double>(), rot[3].cast<double>()};
                        ent.set_local_rotation(xyzw);
                    }
                }
            }

            // Restore scale
            if (dict_data.contains("scale") && py::isinstance<py::list>(dict_data["scale"])) {
                py::list scl = dict_data["scale"].cast<py::list>();
                if (scl.size() >= 3) {
                    double xyz[3] = {scl[0].cast<double>(), scl[1].cast<double>(), scl[2].cast<double>()};
                    ent.set_local_scale(xyz);
                }
            }

            // Deserialize components via ComponentRegistry
            if (dict_data.contains("components") && py::isinstance<py::list>(dict_data["components"])) {
                py::list components = dict_data["components"].cast<py::list>();

                // Use C++ ComponentRegistry
                auto& registry = ComponentRegistry::instance();

                for (auto comp_data_item : components) {
                    if (!py::isinstance<py::dict>(comp_data_item)) continue;
                    py::dict comp_data = comp_data_item.cast<py::dict>();

                    if (!comp_data.contains("type")) continue;

                    std::string type_name = comp_data["type"].cast<std::string>();

                    // Check if component type is registered
                    if (!registry.has(type_name)) {
                        fprintf(stderr, "[Warning] Unknown component type: %s (skipping)\n", type_name.c_str());
                        continue;
                    }

                    try {
                        // Create component via ComponentRegistry
                        py::object comp = registry.create(type_name);
                        if (comp.is_none()) continue;

                        // Deserialize data if component has deserialize_data method
                        if (py::hasattr(comp, "deserialize_data")) {
                            py::object data_field = comp_data.contains("data") ? comp_data["data"] : py::dict();
                            comp.attr("deserialize_data")(data_field, context);
                        }

                        // Add to entity via Python add_component
                        py::object py_ent = py::cast(ent);
                        py_ent.attr("add_component")(comp);

                        // Validate after each component add
                        if (!ent.validate_components()) {
                            fprintf(stderr, "[ERROR] Component validation failed after adding %s\n", type_name.c_str());
                        }
                    } catch (const std::exception& e) {
                        fprintf(stderr, "[Warning] Failed to deserialize component %s: %s\n", type_name.c_str(), e.what());
                    }
                }
            }

            return py::cast(ent);
        }, py::arg("data"), py::arg("context") = py::none());

    // --- EntityRegistry ---
    py::class_<EntityRegistry>(m, "EntityRegistry")
        .def_static("instance", &EntityRegistry::instance, py::return_value_policy::reference)
        .def("get", [](EntityRegistry& reg, const std::string& uuid) -> py::object {
            Entity ent = reg.get(uuid);
            if (ent.valid()) {
                return py::cast(ent);
            }
            return py::none();
        }, py::arg("uuid"))
        .def("get_by_pick_id", [](EntityRegistry& reg, uint32_t pick_id) -> py::object {
            Entity ent = reg.get_by_pick_id(pick_id);
            if (ent.valid()) {
                return py::cast(ent);
            }
            return py::none();
        }, py::arg("pick_id"))
        .def("register_entity", [](EntityRegistry& reg, const Entity& entity) {
            reg.register_entity(entity);
        }, py::arg("entity"))
        .def("unregister_entity", [](EntityRegistry& reg, const Entity& entity) {
            reg.unregister_entity(entity);
        }, py::arg("entity"))
        .def("clear", &EntityRegistry::clear)
        .def_property_readonly("entity_count", &EntityRegistry::entity_count)
        .def("swap_registries", [](EntityRegistry& reg, py::object new_by_uuid, py::object new_by_pick_id) {
            // Convert Python dicts to C++ maps
            std::unordered_map<std::string, Entity> cpp_by_uuid;
            std::unordered_map<uint32_t, Entity> cpp_by_pick_id;

            // new_by_uuid: dict[str, Entity] or WeakValueDictionary
            if (!new_by_uuid.is_none()) {
                for (auto item : new_by_uuid.attr("items")()) {
                    auto pair = item.cast<py::tuple>();
                    std::string uuid = pair[0].cast<std::string>();
                    Entity ent = pair[1].cast<Entity>();
                    cpp_by_uuid[uuid] = ent;
                }
            }

            // new_by_pick_id: dict[int, Entity]
            if (!new_by_pick_id.is_none()) {
                for (auto item : new_by_pick_id.attr("items")()) {
                    auto pair = item.cast<py::tuple>();
                    uint32_t pick_id = pair[0].cast<uint32_t>();
                    Entity ent = pair[1].cast<Entity>();
                    cpp_by_pick_id[pick_id] = ent;
                }
            }

            // Perform the swap
            auto [old_by_uuid, old_by_pick_id] = reg.swap_registries(
                std::move(cpp_by_uuid), std::move(cpp_by_pick_id));

            // Convert old registries back to Python dicts
            py::dict py_old_by_uuid;
            for (auto& [uuid, ent] : old_by_uuid) {
                if (ent.valid()) {
                    py_old_by_uuid[py::str(uuid)] = py::cast(ent);
                }
            }

            py::dict py_old_by_pick_id;
            for (auto& [pick_id, ent] : old_by_pick_id) {
                if (ent.valid()) {
                    py_old_by_pick_id[py::int_(pick_id)] = py::cast(ent);
                }
            }

            return py::make_tuple(py_old_by_uuid, py_old_by_pick_id);
        }, py::arg("new_by_uuid"), py::arg("new_by_pick_id"));

    // --- Native Components ---
    BIND_NATIVE_COMPONENT(m, CXXRotatorComponent)
        .def_readwrite("speed", &CXXRotatorComponent::speed);

    // Register CxxComponent::enabled in InspectRegistry
    InspectRegistry::instance().add_with_accessors<CxxComponent, bool>(
        "Component", "enabled", "Enabled", "bool",
        [](CxxComponent* c) { return c->enabled(); },
        [](CxxComponent* c, bool v) { c->set_enabled(v); }
    );

    // --- Pool utilities ---

    // Get standalone pool (for entities created outside of Scene)
    m.def("get_standalone_pool", []() {
        return reinterpret_cast<uintptr_t>(Entity::standalone_pool());
    }, "Get the global standalone entity pool as uintptr_t");

    // Migrate entity to a different pool (returns new Entity, old becomes invalid)
    m.def("migrate_entity", [](Entity& entity, uintptr_t dst_pool_ptr) -> Entity {
        tc_entity_pool* dst_pool = reinterpret_cast<tc_entity_pool*>(dst_pool_ptr);
        return migrate_entity_to_pool(entity, dst_pool);
    }, py::arg("entity"), py::arg("dst_pool"),
       "Migrate entity to destination pool. Returns new Entity, old becomes invalid.");
}
