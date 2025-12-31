/**
 * Entity native module (_entity_native).
 *
 * Contains Component, Entity, EntityHandle, EntityRegistry, ComponentRegistry.
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
#include "termin/geom/pose3.hpp"
#include "trent/trent.h"
#include "../../../../core_c/include/tc_kind.hpp"

namespace nb = nanobind;
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

static nos::trent py_to_trent(nb::object obj) {
    if (obj.is_none()) {
        return nos::trent::nil();
    }
    if (nb::isinstance<nb::bool_>(obj)) {
        return nos::trent(nb::cast<bool>(obj));
    }
    if (nb::isinstance<nb::int_>(obj)) {
        return nos::trent(nb::cast<int64_t>(obj));
    }
    if (nb::isinstance<nb::float_>(obj)) {
        return nos::trent(nb::cast<double>(obj));
    }
    if (nb::isinstance<nb::str>(obj)) {
        return nos::trent(nb::cast<std::string>(obj));
    }
    if (nb::isinstance<nb::list>(obj)) {
        nos::trent result;
        result.init(nos::trent_type::list);
        for (auto item : obj) {
            result.as_list().push_back(py_to_trent(nb::borrow<nb::object>(item)));
        }
        return result;
    }
    if (nb::isinstance<nb::dict>(obj)) {
        nos::trent result;
        result.init(nos::trent_type::dict);
        for (auto item : nb::cast<nb::dict>(obj)) {
            std::string key = nb::cast<std::string>(item.first);
            result[key] = py_to_trent(nb::borrow<nb::object>(item.second));
        }
        return result;
    }
    return nos::trent::nil();
}

static nb::object trent_to_py(const nos::trent& t) {
    switch (t.get_type()) {
        case nos::trent_type::nil:
            return nb::none();
        case nos::trent_type::boolean:
            return nb::bool_(t.as_bool());
        case nos::trent_type::numer: {
            double val = t.as_numer();
            // Return int if it's a whole number
            if (val == static_cast<int64_t>(val)) {
                return nb::int_(static_cast<int64_t>(val));
            }
            return nb::float_(val);
        }
        case nos::trent_type::string:
            return nb::str(t.as_string().c_str());
        case nos::trent_type::list: {
            nb::list result;
            for (const auto& item : t.as_list()) {
                result.append(trent_to_py(item));
            }
            return result;
        }
        case nos::trent_type::dict: {
            nb::dict result;
            for (const auto& [key, val] : t.as_dict()) {
                result[nb::str(key.c_str())] = trent_to_py(val);
            }
            return result;
        }
    }
    return nb::none();
}

// Trampoline class for CxxComponent.
// Allows Python classes to inherit from C++ CxxComponent.
class PyCxxComponent : public CxxComponent {
public:
    NB_TRAMPOLINE(CxxComponent, 8);

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
};

// Helper: numpy array (3,) -> Vec3
static Vec3 numpy_to_vec3(nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
    const double* data = arr.data();
    return Vec3{data[0], data[1], data[2]};
}

// Helper: Vec3 -> numpy array (3,)
static nb::object vec3_to_numpy(const Vec3& v) {
    double* buf = new double[3];
    buf[0] = v.x;
    buf[1] = v.y;
    buf[2] = v.z;
    nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<double*>(p); });
    size_t shape[1] = {3};
    return nb::cast(nb::ndarray<nb::numpy, double>(buf, 1, shape, owner));
}

// Helper: numpy array (4,) -> Quat
static Quat numpy_to_quat(nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
    const double* data = arr.data();
    return Quat{data[0], data[1], data[2], data[3]};
}

NB_MODULE(_entity_native, m) {
    m.doc() = "Entity native module (Component, Entity, EntityHandle, registries)";

    // --- CxxComponent (also exported as Component for compatibility) ---
    nb::class_<CxxComponent, PyCxxComponent>(m, "Component")
        .def(nb::init<>())
        .def("__init__", [](CxxComponent* self, bool enabled) {
            new (self) PyCxxComponent();
            self->set_enabled(enabled);
        }, nb::arg("enabled") = true)
        .def("type_name", &CxxComponent::type_name)
        .def("set_type_name", &CxxComponent::set_type_name, nb::arg("name"))
        .def("start", &CxxComponent::start)
        .def("update", &CxxComponent::update, nb::arg("dt"))
        .def("fixed_update", &CxxComponent::fixed_update, nb::arg("dt"))
        .def("on_editor_start", &CxxComponent::on_editor_start)
        .def("setup_editor_defaults", &CxxComponent::setup_editor_defaults)
        .def("on_destroy", &CxxComponent::on_destroy)
        .def("on_added_to_entity", &CxxComponent::on_added_to_entity)
        .def("on_removed_from_entity", &CxxComponent::on_removed_from_entity)
        .def("on_added", &CxxComponent::on_added, nb::arg("scene"))
        .def("on_removed", &CxxComponent::on_removed)
        .def_prop_rw("enabled", &CxxComponent::enabled, &CxxComponent::set_enabled)
        .def_prop_rw("active_in_editor", &CxxComponent::active_in_editor, &CxxComponent::set_active_in_editor)
        .def_prop_rw("_started", &CxxComponent::started, &CxxComponent::set_started)
        .def_prop_rw("has_update", &CxxComponent::has_update, &CxxComponent::set_has_update)
        .def_prop_rw("has_fixed_update", &CxxComponent::has_fixed_update, &CxxComponent::set_has_fixed_update)
        .def("c_component", static_cast<tc_component* (CxxComponent::*)()>(&CxxComponent::c_component),
             nb::rv_policy::reference)
        .def_prop_rw("entity",
            [](CxxComponent& c) -> nb::object {
                if (c.entity.valid()) {
                    return nb::cast(c.entity);
                }
                return nb::none();
            },
            [](CxxComponent& c, nb::object obj) {
                if (obj.is_none()) {
                    c.entity = Entity();  // Invalid entity
                } else {
                    c.entity = nb::cast<Entity>(obj);
                }
            })
        .def("serialize_data", [](CxxComponent& c) {
            return trent_to_py(c.serialize_data());
        })
        .def("serialize", [](CxxComponent& c) {
            return trent_to_py(c.serialize());
        })
        .def("deserialize_data", [](CxxComponent& c, nb::object data, nb::object) {
            c.deserialize_data(py_to_trent(data));
        });

    // --- ComponentRegistry ---
    nb::class_<ComponentRegistry>(m, "ComponentRegistry")
        .def_static("instance", &ComponentRegistry::instance, nb::rv_policy::reference)
        .def("register_python", &ComponentRegistry::register_python,
             nb::arg("name"), nb::arg("cls"))
        .def("unregister", &ComponentRegistry::unregister, nb::arg("name"))
        .def("create", &ComponentRegistry::create, nb::arg("name"))
        .def("has", &ComponentRegistry::has, nb::arg("name"))
        .def("list_all", &ComponentRegistry::list_all)
        .def("list_native", &ComponentRegistry::list_native)
        .def("list_python", &ComponentRegistry::list_python)
        .def("clear", &ComponentRegistry::clear);

    // --- EntityHandle ---
    nb::class_<EntityHandle>(m, "EntityHandle")
        .def(nb::init<>())
        .def(nb::init<const std::string&>(), nb::arg("uuid"))
        .def("__init__", [](EntityHandle* self, const std::string& uuid, uintptr_t pool_ptr) {
            new (self) EntityHandle(uuid, reinterpret_cast<tc_entity_pool*>(pool_ptr));
        }, nb::arg("uuid"), nb::arg("pool_ptr"))
        .def_rw("uuid", &EntityHandle::uuid)
        .def_prop_rw("pool_ptr",
            [](const EntityHandle& h) { return reinterpret_cast<uintptr_t>(h.pool); },
            [](EntityHandle& h, uintptr_t ptr) { h.pool = reinterpret_cast<tc_entity_pool*>(ptr); })
        .def_prop_ro("entity", &EntityHandle::get, nb::rv_policy::reference)
        .def_prop_ro("is_valid", &EntityHandle::is_valid)
        .def_prop_ro("name", &EntityHandle::name)
        .def_static("from_entity", &EntityHandle::from_entity, nb::arg("entity"))
        .def("get", &EntityHandle::get, nb::rv_policy::reference)
        .def("__repr__", [](const EntityHandle& h) {
            std::string status = h.get().valid() ? "resolved" : "unresolved";
            std::string uuid_short = h.uuid.size() > 8 ? h.uuid.substr(0, 8) + "..." : h.uuid;
            return "<EntityHandle " + uuid_short + " (" + status + ")>";
        })
        .def("serialize", &EntityHandle::serialize)
        .def_static("deserialize", [](nb::dict d, uintptr_t pool_ptr) -> EntityHandle {
            EntityHandle h;
            h.pool = reinterpret_cast<tc_entity_pool*>(pool_ptr);
            if (d.contains("uuid")) {
                h.uuid = nb::cast<std::string>(d["uuid"]);
            }
            return h;
        }, nb::arg("data"), nb::arg("pool_ptr") = 0);

    // --- Entity ---
    nb::class_<Entity>(m, "Entity")
        .def("__init__", [](Entity* self, const std::string& name, const std::string& uuid) {
            // Create entity in standalone pool
            new (self) Entity(Entity::create(get_standalone_pool(), name));
        }, nb::arg("name") = "entity", nb::arg("uuid") = "")
        .def("__init__", [](Entity* self, nb::object pose, const std::string& name, int priority,
                        bool pickable, bool selectable, bool serializable,
                        int layer, uint64_t flags, const std::string& uuid) {
            // Create entity in standalone pool
            new (self) Entity(Entity::create(get_standalone_pool(), name));

            if (!pose.is_none()) {
                // Try direct cast to GeneralPose3 or Pose3 first
                try {
                    GeneralPose3 gpose = nb::cast<GeneralPose3>(pose);
                    self->transform().set_local_pose(gpose);
                } catch (const nb::cast_error&) {
                    try {
                        Pose3 p = nb::cast<Pose3>(pose);
                        self->transform().set_local_pose(GeneralPose3(p.ang, p.lin, Vec3{1, 1, 1}));
                    } catch (const nb::cast_error&) {
                        // Fall back to extracting from Python object with numpy arrays
                        GeneralPose3 gpose;
                        if (nb::hasattr(pose, "lin") && nb::hasattr(pose, "ang")) {
                            try {
                                auto lin = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(pose.attr("lin"));
                                auto ang = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(pose.attr("ang"));
                                gpose.lin = numpy_to_vec3(lin);
                                gpose.ang = numpy_to_quat(ang);
                                if (nb::hasattr(pose, "scale")) {
                                    auto scale = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(pose.attr("scale"));
                                    gpose.scale = numpy_to_vec3(scale);
                                }
                            } catch (const nb::cast_error&) {
                                // Try extracting Vec3/Quat directly
                                gpose.lin = nb::cast<Vec3>(pose.attr("lin"));
                                gpose.ang = nb::cast<Quat>(pose.attr("ang"));
                                if (nb::hasattr(pose, "scale")) {
                                    gpose.scale = nb::cast<Vec3>(pose.attr("scale"));
                                }
                            }
                        }
                        self->transform().set_local_pose(gpose);
                    }
                }
            }
            // Set additional attributes
            self->set_priority(priority);
            self->set_pickable(pickable);
            self->set_selectable(selectable);
            self->set_serializable(serializable);
            self->set_layer(static_cast<uint64_t>(layer));
            self->set_flags(flags);
        }, nb::arg("pose") = nb::none(), nb::arg("name") = "entity",
            nb::arg("priority") = 0, nb::arg("pickable") = true,
            nb::arg("selectable") = true, nb::arg("serializable") = true,
            nb::arg("layer") = 0, nb::arg("flags") = 0, nb::arg("uuid") = "")

        // Validity
        .def("valid", &Entity::valid)
        .def("__bool__", &Entity::valid)

        // Identity
        .def_prop_ro("uuid", [](const Entity& e) -> nb::object {
            const char* u = e.uuid();
            if (u) return nb::str(u);
            return nb::none();
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
        .def_prop_rw("name",
            [](const Entity& e) -> nb::object {
                const char* n = e.name();
                if (n) return nb::str(n);
                return nb::none();
            },
            [](Entity& e, const std::string& n) {
                e.set_name(n);
            })
        .def_prop_ro("runtime_id", [](const Entity& e) -> uint64_t {
            return e.runtime_id();
        })

        // Flags
        .def_prop_rw("visible",
            [](const Entity& e) { return e.visible(); },
            [](Entity& e, bool v) { e.set_visible(v); })
        .def_prop_rw("active",
            [](const Entity& e) { return e.active(); },
            [](Entity& e, bool v) { e.set_active(v); })
        .def_prop_rw("pickable",
            [](const Entity& e) { return e.pickable(); },
            [](Entity& e, bool v) { e.set_pickable(v); })
        .def_prop_rw("selectable",
            [](const Entity& e) { return e.selectable(); },
            [](Entity& e, bool v) { e.set_selectable(v); })

        // Rendering
        .def_prop_rw("priority",
            [](const Entity& e) { return e.priority(); },
            [](Entity& e, int p) { e.set_priority(p); })
        .def_prop_rw("layer",
            [](const Entity& e) { return e.layer(); },
            [](Entity& e, uint64_t l) { e.set_layer(l); })
        .def_prop_rw("flags",
            [](const Entity& e) { return e.flags(); },
            [](Entity& e, uint64_t f) { e.set_flags(f); })

        // Pick ID
        .def_prop_ro("pick_id", &Entity::pick_id)

        // Transform access - returns the GeneralTransform3 wrapper
        .def_prop_ro("transform", [](Entity& e) -> GeneralTransform3 {
            return e.transform();
        })

        // Pose shortcuts
        .def("global_pose", [](Entity& e) {
            GeneralPose3 gp = e.transform().global_pose();
            nb::dict result;
            result["lin"] = vec3_to_numpy(gp.lin);
            double* ang_buf = new double[4];
            ang_buf[0] = gp.ang.x;
            ang_buf[1] = gp.ang.y;
            ang_buf[2] = gp.ang.z;
            ang_buf[3] = gp.ang.w;
            nb::capsule owner(ang_buf, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[1] = {4};
            result["ang"] = nb::ndarray<nb::numpy, double>(ang_buf, 1, shape, owner);
            result["scale"] = vec3_to_numpy(gp.scale);
            return result;
        })

        .def("model_matrix", [](Entity& e) {
            double m[16];
            e.transform().world_matrix(m);
            double* buf = new double[16];
            for (int i = 0; i < 16; ++i) buf[i] = m[i];
            nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, double>(buf, 2, shape, owner);
        })

        .def("inverse_model_matrix", [](Entity& e) {
            // Get global pose and compute inverse matrix
            GeneralPose3 gp = e.transform().global_pose();
            double m[16];
            gp.inverse_matrix4(m);
            double* buf = new double[16];
            for (int i = 0; i < 16; ++i) buf[i] = m[i];
            nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, double>(buf, 2, shape, owner);
        })

        .def("set_visible", [](Entity& e, bool flag) {
            e.set_visible(flag);
            for (Entity child : e.children()) {
                child.set_visible(flag);
            }
        }, nb::arg("flag"))

        .def("is_pickable", [](Entity& e) {
            return e.pickable() && e.visible() && e.active();
        })

        // Component management
        // Accepts both C++ Component and PythonComponent (via nb::object)
        // Note: Scene registration is handled by Python Scene.add(), not here
        .def("add_component", [](Entity& e, nb::object component) -> nb::object {
            // Check if it's a C++ Component
            if (nb::isinstance<Component>(component)) {
                Component* c = nb::cast<Component*>(component);
                // Store Python wrapper in py_wrap to keep it alive while attached to entity
                // set_py_wrap does INCREF
                c->set_py_wrap(component);
                e.add_component(c);
                return component;
            }

            // Check if it's a PythonComponent (has c_component_ptr method)
            if (nb::hasattr(component, "c_component_ptr")) {
                uintptr_t ptr = nb::cast<uintptr_t>(component.attr("c_component_ptr")());
                tc_component* tc = reinterpret_cast<tc_component*>(ptr);

                // Set entity reference on PythonComponent
                if (nb::hasattr(component, "entity")) {
                    component.attr("entity") = nb::cast(e);
                }

                e.add_component_ptr(tc);
                return component;
            }

            throw std::runtime_error("add_component requires Component or PythonComponent");
        }, nb::arg("component"))
        .def("remove_component", [](Entity& e, nb::object component) {
            // Check if it's a C++ Component
            if (nb::isinstance<Component>(component)) {
                e.remove_component(nb::cast<Component*>(component));
                return;
            }

            // Check if it's a PythonComponent
            if (nb::hasattr(component, "c_component_ptr")) {
                uintptr_t ptr = nb::cast<uintptr_t>(component.attr("c_component_ptr")());
                e.remove_component_ptr(reinterpret_cast<tc_component*>(ptr));
                return;
            }

            throw std::runtime_error("remove_component requires Component or PythonComponent");
        }, nb::arg("component"))
        .def("get_component_by_type", &Entity::get_component_by_type,
             nb::arg("type_name"), nb::rv_policy::reference)
        .def("get_component", [](Entity& e, nb::object type_class) -> nb::object {
            // Get component by Python type class (like Unity's GetComponent<T>())
            if (!e.valid()) {
                return nb::none();
            }
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                nb::object py_comp = CxxComponent::tc_to_python(tc);

                if (nb::isinstance(py_comp, type_class)) {
                    return py_comp;
                }
            }
            return nb::none();
        }, nb::arg("component_type"))
        .def("find_component", [](Entity& e, nb::object type_class) -> nb::object {
            // Get component by Python type class, raise if not found
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                nb::object py_comp = CxxComponent::tc_to_python(tc);

                if (nb::isinstance(py_comp, type_class)) {
                    return py_comp;
                }
            }
            throw std::runtime_error("Component not found");
        }, nb::arg("component_type"))
        .def_prop_ro("components", [](Entity& e) {
            nb::list result;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                nb::object py_comp = CxxComponent::tc_to_python(tc);
                if (!py_comp.is_none()) {
                    result.append(py_comp);
                }
            }
            return result;
        })

        // Hierarchy
        .def("set_parent", [](Entity& e, nb::object parent_obj) {
            if (parent_obj.is_none()) {
                e.set_parent(Entity());  // Invalid entity = no parent
            } else {
                Entity parent = nb::cast<Entity>(parent_obj);
                e.set_parent(parent);
            }
        }, nb::arg("parent"))
        .def_prop_ro("parent", [](Entity& e) -> nb::object {
            Entity p = e.parent();
            if (p.valid()) {
                return nb::cast(p);
            }
            return nb::none();
        })
        .def("children", &Entity::children)

        // Lifecycle
        .def("update", &Entity::update, nb::arg("dt"))
        .def("on_added_to_scene", &Entity::on_added_to_scene, nb::arg("scene"))
        .def("on_removed_from_scene", &Entity::on_removed_from_scene)
        // Lifecycle - Scene handles component registration in Python
        .def("on_added", [](Entity& e, nb::object scene) {
            e.on_added_to_scene(scene);
        }, nb::arg("scene"))
        .def("on_removed", [](Entity& e) {
            e.on_removed_from_scene();
        })

        // Validation - for debugging memory corruption
        .def("validate_components", &Entity::validate_components)

        // Serialization
        .def_prop_rw("serializable",
            [](const Entity& e) { return e.serializable(); },
            [](Entity& e, bool v) { e.set_serializable(v); })
        .def("serialize", [](Entity& e) -> nb::object {
            nos::trent data = e.serialize_base();
            if (data.is_nil()) {
                return nb::none();
            }
            nb::dict result = nb::cast<nb::dict>(trent_to_py(data));

            // Serialize components by calling their Python serialize() methods
            nb::list comp_list;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                nb::object py_comp = CxxComponent::tc_to_python(tc);

                if (nb::hasattr(py_comp, "serialize")) {
                    nb::object comp_data = py_comp.attr("serialize")();
                    if (!comp_data.is_none()) {
                        comp_list.append(comp_data);
                    }
                }
            }
            result["components"] = comp_list;

            // Serialize children recursively (call Python serialize to include components)
            nb::list children_list;
            for (Entity child : e.children()) {
                if (child.serializable()) {
                    nb::object py_child = nb::cast(child);
                    nb::object child_data = py_child.attr("serialize")();
                    if (!child_data.is_none()) {
                        children_list.append(child_data);
                    }
                }
            }
            result["children"] = children_list;

            return result;
        })
        .def_static("deserialize", [](nb::object data, nb::object context) -> nb::object {
            try {
                if (data.is_none() || !nb::isinstance<nb::dict>(data)) {
                    return nb::none();
                }

                nb::dict dict_data = nb::cast<nb::dict>(data);

                // Get entity name
                std::string name = "entity";
                if (dict_data.contains("name")) {
                    nb::object name_obj = dict_data["name"];
                    name = nb::cast<std::string>(name_obj);
                }

                // Create entity using standalone pool
                tc_entity_pool* pool = get_standalone_pool();
                if (!pool) {
                    tc::Log::error("Entity::deserialize: standalone pool is null");
                    return nb::none();
                }
                Entity ent = Entity::create(pool, name);
                if (!ent.valid()) {
                    tc::Log::error("Entity::deserialize: failed to create entity '%s'", name.c_str());
                    return nb::none();
                }

                // Restore flags
                if (dict_data.contains("priority")) {
                    nb::object val = dict_data["priority"];
                    ent.set_priority(nb::cast<int>(val));
                }
                if (dict_data.contains("visible")) {
                    nb::object val = dict_data["visible"];
                    ent.set_visible(nb::cast<bool>(val));
                }
                if (dict_data.contains("active")) {
                    nb::object val = dict_data["active"];
                    ent.set_active(nb::cast<bool>(val));
                }
                if (dict_data.contains("pickable")) {
                    nb::object val = dict_data["pickable"];
                    ent.set_pickable(nb::cast<bool>(val));
                }
                if (dict_data.contains("selectable")) {
                    nb::object val = dict_data["selectable"];
                    ent.set_selectable(nb::cast<bool>(val));
                }
                if (dict_data.contains("layer")) {
                    nb::object val = dict_data["layer"];
                    ent.set_layer(nb::cast<uint64_t>(val));
                }
                if (dict_data.contains("flags")) {
                    nb::object val = dict_data["flags"];
                    ent.set_flags(nb::cast<uint64_t>(val));
                }

                // Restore pose
                if (dict_data.contains("pose")) {
                    nb::object pose_obj = dict_data["pose"];
                    if (nb::isinstance<nb::dict>(pose_obj)) {
                        nb::dict pose = nb::cast<nb::dict>(pose_obj);
                        if (pose.contains("position")) {
                            nb::object pos_obj = pose["position"];
                            if (nb::isinstance<nb::list>(pos_obj)) {
                                nb::list pos = nb::cast<nb::list>(pos_obj);
                                if (nb::len(pos) >= 3) {
                                    nb::object p0 = pos[0], p1 = pos[1], p2 = pos[2];
                                    double xyz[3] = {nb::cast<double>(p0), nb::cast<double>(p1), nb::cast<double>(p2)};
                                    ent.set_local_position(xyz);
                                }
                            }
                        }
                        if (pose.contains("rotation")) {
                            nb::object rot_obj = pose["rotation"];
                            if (nb::isinstance<nb::list>(rot_obj)) {
                                nb::list rot = nb::cast<nb::list>(rot_obj);
                                if (nb::len(rot) >= 4) {
                                    nb::object r0 = rot[0], r1 = rot[1], r2 = rot[2], r3 = rot[3];
                                    double xyzw[4] = {nb::cast<double>(r0), nb::cast<double>(r1), nb::cast<double>(r2), nb::cast<double>(r3)};
                                    ent.set_local_rotation(xyzw);
                                }
                            }
                        }
                    }
                }

                // Restore scale
                if (dict_data.contains("scale")) {
                    nb::object scl_obj = dict_data["scale"];
                    if (nb::isinstance<nb::list>(scl_obj)) {
                        nb::list scl = nb::cast<nb::list>(scl_obj);
                        if (nb::len(scl) >= 3) {
                            nb::object s0 = scl[0], s1 = scl[1], s2 = scl[2];
                            double xyz[3] = {nb::cast<double>(s0), nb::cast<double>(s1), nb::cast<double>(s2)};
                            ent.set_local_scale(xyz);
                        }
                    }
                }

                // Deserialize components via ComponentRegistry
                if (dict_data.contains("components")) {
                    nb::object comp_list_obj = dict_data["components"];
                    if (!nb::isinstance<nb::list>(comp_list_obj)) {
                        return nb::cast(ent);
                    }
                    nb::list components = nb::cast<nb::list>(comp_list_obj);

                    // Use C++ ComponentRegistry
                    auto& registry = ComponentRegistry::instance();

                    for (size_t i = 0; i < nb::len(components); ++i) {
                        nb::object comp_data_item = components[i];
                        if (!nb::isinstance<nb::dict>(comp_data_item)) continue;
                        nb::dict comp_data = nb::cast<nb::dict>(comp_data_item);

                        if (!comp_data.contains("type")) continue;

                        nb::object type_obj = comp_data["type"];
                        std::string type_name = nb::cast<std::string>(type_obj);

                        // Check if component type is registered
                        if (!registry.has(type_name)) {
                            tc::Log::warn("Unknown component type: %s (skipping)", type_name.c_str());
                            continue;
                        }

                        try {
                            // Create component via ComponentRegistry
                            nb::object comp = registry.create(type_name);
                            if (comp.is_none()) continue;

                            // Get data field
                            nb::object data_field;
                            if (comp_data.contains("data")) {
                                data_field = comp_data["data"];
                            } else {
                                data_field = nb::dict();
                            }

                            // Deserialize based on component kind
                            const auto* info = registry.get_info(type_name);
                            if (info && info->kind == TC_CXX_COMPONENT) {
                                // Native component: use InspectRegistry directly
                                if (nb::isinstance<nb::dict>(data_field)) {
                                    nb::dict data_dict = nb::cast<nb::dict>(data_field);
                                    void* raw_ptr = nb::inst_ptr<void>(comp);
                                    InspectRegistry::instance().deserialize_component_fields_over_python(
                                        raw_ptr, comp, type_name, data_dict);
                                }
                            } else {
                                // Python component: call deserialize_data method
                                if (nb::hasattr(comp, "deserialize_data")) {
                                    comp.attr("deserialize_data")(data_field, context);
                                }
                            }

                            // Add to entity via Python add_component
                            nb::object py_ent = nb::cast(ent);
                            py_ent.attr("add_component")(comp);

                            // Validate after each component add
                            if (!ent.validate_components()) {
                                tc::Log::error("Component validation failed after adding %s", type_name.c_str());
                            }
                        } catch (const std::exception& e) {
                            tc::Log::warn(e, "Failed to deserialize component %s", type_name.c_str());
                        }
                    }
                }

                return nb::cast(ent);
            } catch (const std::exception& e) {
                tc::Log::error(e, "Entity::deserialize");
                return nb::none();
            }
        }, nb::arg("data"), nb::arg("context") = nb::none())

        .def_static("deserialize_with_children", [](nb::object data, nb::object context) -> nb::object {
            // Recursive helper function
            std::function<nb::object(nb::object, nb::object)> deserialize_recursive;
            deserialize_recursive = [&deserialize_recursive](nb::object data, nb::object context) -> nb::object {
                // Get Entity class and call deserialize
                nb::object entity_cls = nb::module_::import_("termin.entity").attr("Entity");
                nb::object ent = entity_cls.attr("deserialize")(data, context);
                if (ent.is_none()) {
                    return nb::none();
                }

                // Deserialize children
                if (nb::isinstance<nb::dict>(data)) {
                    nb::dict dict_data = nb::cast<nb::dict>(data);
                    if (dict_data.contains("children")) {
                        nb::object children_obj = dict_data["children"];
                        if (nb::isinstance<nb::list>(children_obj)) {
                            nb::list children = nb::cast<nb::list>(children_obj);
                            for (size_t i = 0; i < nb::len(children); ++i) {
                                nb::object child_data = children[i];
                                nb::object child = deserialize_recursive(child_data, context);
                                if (!child.is_none()) {
                                    child.attr("set_parent")(ent);
                                }
                            }
                        }
                    }
                }

                return ent;
            };

            return deserialize_recursive(data, context);
        }, nb::arg("data"), nb::arg("context") = nb::none());

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
            // Convert Python dicts to C++ maps
            std::unordered_map<std::string, Entity> cpp_by_uuid;
            std::unordered_map<uint32_t, Entity> cpp_by_pick_id;

            // new_by_uuid: dict[str, Entity] or WeakValueDictionary
            if (!new_by_uuid.is_none()) {
                for (auto item : new_by_uuid.attr("items")()) {
                    auto pair = nb::cast<nb::tuple>(item);
                    std::string uuid = nb::cast<std::string>(pair[0]);
                    Entity ent = nb::cast<Entity>(pair[1]);
                    cpp_by_uuid[uuid] = ent;
                }
            }

            // new_by_pick_id: dict[int, Entity]
            if (!new_by_pick_id.is_none()) {
                for (auto item : new_by_pick_id.attr("items")()) {
                    auto pair = nb::cast<nb::tuple>(item);
                    uint32_t pick_id = nb::cast<uint32_t>(pair[0]);
                    Entity ent = nb::cast<Entity>(pair[1]);
                    cpp_by_pick_id[pick_id] = ent;
                }
            }

            // Perform the swap
            auto [old_by_uuid, old_by_pick_id] = reg.swap_registries(
                std::move(cpp_by_uuid), std::move(cpp_by_pick_id));

            // Convert old registries back to Python dicts
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

    // Get standalone pool (for entities created outside of Scene)
    m.def("get_standalone_pool", []() {
        return reinterpret_cast<uintptr_t>(Entity::standalone_pool());
    }, "Get the global standalone entity pool as uintptr_t");

    // Migrate entity to a different pool (returns new Entity, old becomes invalid)
    m.def("migrate_entity", [](Entity& entity, uintptr_t dst_pool_ptr) -> Entity {
        tc_entity_pool* dst_pool = reinterpret_cast<tc_entity_pool*>(dst_pool_ptr);
        return migrate_entity_to_pool(entity, dst_pool);
    }, nb::arg("entity"), nb::arg("dst_pool"),
       "Migrate entity to destination pool. Returns new Entity, old becomes invalid.");

    // ===== Register entity_handle kind handler =====
    // C++ handlers for entity_handle and list[entity_handle]
    tc::register_cpp_handle_kind<EntityHandle>("entity_handle");

    // Python handler for Python fields
    tc::KindRegistry::instance().register_python(
        "entity_handle",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            EntityHandle handle = nb::cast<EntityHandle>(obj);
            nb::dict d;
            d["uuid"] = handle.uuid;
            return d;
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            // Handle UUID string (legacy format)
            if (nb::isinstance<nb::str>(data)) {
                return nb::cast(EntityHandle(nb::cast<std::string>(data)));
            }
            // Handle dict format
            if (nb::isinstance<nb::dict>(data)) {
                nb::dict d = nb::cast<nb::dict>(data);
                if (d.contains("uuid")) {
                    return nb::cast(EntityHandle(nb::cast<std::string>(d["uuid"])));
                }
            }
            return nb::cast(EntityHandle());
        }),
        // convert
        nb::cpp_function([](nb::object value) -> nb::object {
            if (value.is_none()) {
                return nb::cast(EntityHandle());
            }
            if (nb::isinstance<EntityHandle>(value)) {
                return value;
            }
            return value;
        })
    );
    // list[entity_handle] Python handler is auto-generated by InspectRegistry

    // Register atexit handler to clear Python references before Python finalization.
    // This prevents segfault when static singleton destructors try to decref dead Python objects.
    nb::object atexit_mod = nb::module_::import_("atexit");
    nb::object cleanup_fn = nb::cpp_function([]() {
        ComponentRegistry::instance().clear();
        EntityRegistry::instance().clear();
        tc::KindRegistry::instance().clear_python();
    });
    atexit_mod.attr("register")(cleanup_fn);
}
