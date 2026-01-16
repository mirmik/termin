// entity_bindings.cpp - Entity class binding
#include "entity_bindings.hpp"
#include "entity_helpers.hpp"

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/ndarray.h>
#include <functional>

#include "tc_log.hpp"
#include "termin/entity/component.hpp"
#include "termin/entity/component_registry.hpp"
#include "termin/entity/entity.hpp"
#include "termin/geom/general_transform3.hpp"
#include "termin/geom/general_pose3.hpp"
#include "termin/geom/pose3.hpp"
#include "../../../../core_c/include/tc_scene.h"
#include "../../../../core_c/include/tc_inspect.hpp"

namespace nb = nanobind;

namespace termin {

// Iterator for traversing ancestor entities
class EntityAncestorIterator {
public:
    Entity _current;

    explicit EntityAncestorIterator(Entity start) : _current(start.parent()) {}

    nb::object next() {
        if (!_current.valid()) {
            throw nb::stop_iteration();
        }
        Entity result = _current;
        _current = _current.parent();
        return nb::cast(result);
    }
};

// Helper: register component with Python Scene if entity is in a scene's pool
static void register_component_with_scene(Entity& e, nb::object component) {
    tc_entity_pool* pool = e.pool();
    if (!pool) return;

    tc_scene* scene = tc_entity_pool_get_scene(pool);
    if (!scene) return;

    void* py_wrapper = tc_scene_get_py_wrapper(scene);
    if (!py_wrapper) return;

    nb::object py_scene = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(py_wrapper));
    if (nb::hasattr(py_scene, "register_component")) {
        py_scene.attr("register_component")(component);
    }
}

void bind_entity_class(nb::module_& m) {
    // Ancestor iterator
    nb::class_<EntityAncestorIterator>(m, "_EntityAncestorIterator")
        .def("__iter__", [](EntityAncestorIterator& self) -> EntityAncestorIterator& { return self; })
        .def("__next__", &EntityAncestorIterator::next);

    nb::class_<Entity>(m, "Entity")
        .def("__init__", [](Entity* self, const std::string& name, const std::string& uuid) {
            new (self) Entity(Entity::create(get_standalone_pool(), name));
        }, nb::arg("name") = "entity", nb::arg("uuid") = "")
        .def("__init__", [](Entity* self, nb::object pose, const std::string& name, int priority,
                        bool pickable, bool selectable, bool serializable,
                        int layer, uint64_t flags, const std::string& uuid) {
            new (self) Entity(Entity::create(get_standalone_pool(), name));

            if (!pose.is_none()) {
                try {
                    GeneralPose3 gpose = nb::cast<GeneralPose3>(pose);
                    self->transform().set_local_pose(gpose);
                } catch (const nb::cast_error&) {
                    try {
                        Pose3 p = nb::cast<Pose3>(pose);
                        self->transform().set_local_pose(GeneralPose3(p.ang, p.lin, Vec3{1, 1, 1}));
                    } catch (const nb::cast_error&) {
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
        .def("__eq__", [](const Entity& a, const Entity& b) {
            return a.pool() == b.pool() &&
                   a.id().index == b.id().index &&
                   a.id().generation == b.id().generation;
        })
        .def("__hash__", [](const Entity& e) {
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
        .def_prop_rw("enabled",
            [](const Entity& e) { return e.enabled(); },
            [](Entity& e, bool v) { e.set_enabled(v); })
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

        // Transform access
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
            return e.pickable() && e.visible() && e.enabled();
        })

        // Component management
        .def("add_component", [](Entity& e, nb::object component) -> nb::object {
            if (nb::isinstance<Component>(component)) {
                Component* c = nb::cast<Component*>(component);
                c->set_py_wrap(component);
                e.add_component(c);
                register_component_with_scene(e, component);
                return component;
            }

            if (nb::hasattr(component, "c_component_ptr")) {
                uintptr_t ptr = nb::cast<uintptr_t>(component.attr("c_component_ptr")());
                tc_component* tc = reinterpret_cast<tc_component*>(ptr);

                if (nb::hasattr(component, "entity")) {
                    component.attr("entity") = nb::cast(e);
                }

                e.add_component_ptr(tc);
                register_component_with_scene(e, component);
                return component;
            }

            throw std::runtime_error("add_component requires Component or PythonComponent");
        }, nb::arg("component"))
        .def("remove_component", [](Entity& e, nb::object component) {
            if (nb::isinstance<Component>(component)) {
                e.remove_component(nb::cast<Component*>(component));
                return;
            }

            if (nb::hasattr(component, "c_component_ptr")) {
                uintptr_t ptr = nb::cast<uintptr_t>(component.attr("c_component_ptr")());
                e.remove_component_ptr(reinterpret_cast<tc_component*>(ptr));
                return;
            }

            throw std::runtime_error("remove_component requires Component or PythonComponent");
        }, nb::arg("component"))
        .def("get_component_by_type", [](Entity& e, const std::string& type_name) -> nb::object {
            tc_component* tc = e.get_component_by_type_name(type_name);
            if (!tc) {
                return nb::none();
            }
            return CxxComponent::tc_to_python(tc);
        }, nb::arg("type_name"))
        .def("get_python_component", &Entity::get_python_component,
             nb::arg("type_name"))
        .def("get_component", [](Entity& e, nb::object type_class) -> nb::object {
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
                e.set_parent(Entity());
            } else {
                Entity parent = nb::cast<Entity>(parent_obj);
                e.set_parent(parent);
            }
        }, nb::arg("parent").none())
        .def_prop_ro("parent", [](Entity& e) -> nb::object {
            Entity p = e.parent();
            if (p.valid()) {
                return nb::cast(p);
            }
            return nb::none();
        })
        .def("children", &Entity::children)
        .def("find_child", &Entity::find_child, nb::arg("name"),
             "Find a child entity by name. Returns invalid Entity if not found.")
        .def("ancestors", [](Entity& e) {
            return EntityAncestorIterator(e);
        }, "Iterate over ancestor entities from immediate parent to root.")

        // Lifecycle
        .def("update", &Entity::update, nb::arg("dt"))
        .def("on_added_to_scene", &Entity::on_added_to_scene, nb::arg("scene"))
        .def("on_removed_from_scene", &Entity::on_removed_from_scene)
        .def("on_added", [](Entity& e, nb::object scene) {
            e.on_added_to_scene(scene);
        }, nb::arg("scene"))
        .def("on_removed", [](Entity& e) {
            e.on_removed_from_scene();
        })

        // Validation
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
        .def_static("deserialize", [](nb::object data, nb::object context, nb::object scene) -> nb::object {
            try {
                if (data.is_none() || !nb::isinstance<nb::dict>(data)) {
                    return nb::none();
                }

                nb::dict dict_data = nb::cast<nb::dict>(data);

                std::string name = "entity";
                if (dict_data.contains("name")) {
                    nb::object name_obj = dict_data["name"];
                    name = nb::cast<std::string>(name_obj);
                }

                // Get pool and scene from scene object or use standalone pool
                tc_entity_pool* pool = nullptr;
                tc_scene* c_scene = nullptr;
                if (!scene.is_none() && nb::hasattr(scene, "_tc_scene")) {
                    nb::object tc_scene_obj = scene.attr("_tc_scene");
                    if (nb::hasattr(tc_scene_obj, "entity_pool_ptr")) {
                        uintptr_t pool_ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("entity_pool_ptr")());
                        pool = reinterpret_cast<tc_entity_pool*>(pool_ptr);
                    }
                    if (nb::hasattr(tc_scene_obj, "scene_ptr")) {
                        uintptr_t scene_ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                        c_scene = reinterpret_cast<tc_scene*>(scene_ptr);
                    }
                }
                if (!pool) {
                    pool = get_standalone_pool();
                }
                if (!pool) {
                    tc::Log::error("Entity::deserialize: pool is null");
                    return nb::none();
                }
                Entity ent = Entity::create(pool, name);
                if (!ent.valid()) {
                    tc::Log::error("Entity::deserialize: failed to create entity '%s'", name.c_str());
                    return nb::none();
                }

                // Restore flags
                if (dict_data.contains("priority")) {
                    ent.set_priority(nb::cast<int>(dict_data["priority"]));
                }
                if (dict_data.contains("visible")) {
                    ent.set_visible(nb::cast<bool>(dict_data["visible"]));
                }
                if (dict_data.contains("enabled")) {
                    ent.set_enabled(nb::cast<bool>(dict_data["enabled"]));
                }
                if (dict_data.contains("pickable")) {
                    ent.set_pickable(nb::cast<bool>(dict_data["pickable"]));
                }
                if (dict_data.contains("selectable")) {
                    ent.set_selectable(nb::cast<bool>(dict_data["selectable"]));
                }
                if (dict_data.contains("layer")) {
                    ent.set_layer(nb::cast<uint64_t>(dict_data["layer"]));
                }
                if (dict_data.contains("flags")) {
                    ent.set_flags(nb::cast<uint64_t>(dict_data["flags"]));
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
                                    double xyz[3] = {
                                        nb::cast<double>(pos[0]),
                                        nb::cast<double>(pos[1]),
                                        nb::cast<double>(pos[2])
                                    };
                                    ent.set_local_position(xyz);
                                }
                            }
                        }
                        if (pose.contains("rotation")) {
                            nb::object rot_obj = pose["rotation"];
                            if (nb::isinstance<nb::list>(rot_obj)) {
                                nb::list rot = nb::cast<nb::list>(rot_obj);
                                if (nb::len(rot) >= 4) {
                                    double xyzw[4] = {
                                        nb::cast<double>(rot[0]),
                                        nb::cast<double>(rot[1]),
                                        nb::cast<double>(rot[2]),
                                        nb::cast<double>(rot[3])
                                    };
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
                            double xyz[3] = {
                                nb::cast<double>(scl[0]),
                                nb::cast<double>(scl[1]),
                                nb::cast<double>(scl[2])
                            };
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

                    auto& registry = ComponentRegistry::instance();

                    for (size_t i = 0; i < nb::len(components); ++i) {
                        nb::object comp_data_item = components[i];
                        if (!nb::isinstance<nb::dict>(comp_data_item)) continue;
                        nb::dict comp_data = nb::cast<nb::dict>(comp_data_item);

                        if (!comp_data.contains("type")) continue;

                        std::string type_name = nb::cast<std::string>(comp_data["type"]);

                        if (!registry.has(type_name)) {
                            tc::Log::warn("Unknown component type: %s (skipping)", type_name.c_str());
                            continue;
                        }

                        try {
                            nb::object comp = registry.create(type_name);
                            if (comp.is_none()) continue;

                            nb::object data_field;
                            if (comp_data.contains("data")) {
                                data_field = comp_data["data"];
                            } else {
                                data_field = nb::dict();
                            }

                            const auto* info = registry.get_info(type_name);
                            if (info && info->kind == TC_CXX_COMPONENT) {
                                if (nb::isinstance<nb::dict>(data_field)) {
                                    nb::dict data_dict = nb::cast<nb::dict>(data_field);
                                    void* raw_ptr = nb::inst_ptr<void>(comp);
                                    // Use C API for deserialization
                                    tc_value tc_data = tc::nb_to_tc_value(data_dict);
                                    tc_inspect_deserialize_with_scene(raw_ptr, type_name.c_str(), &tc_data, c_scene);
                                    tc_value_free(&tc_data);
                                }
                            } else {
                                if (nb::hasattr(comp, "deserialize_data")) {
                                    comp.attr("deserialize_data")(data_field, context);
                                }
                            }

                            nb::object py_ent = nb::cast(ent);
                            py_ent.attr("add_component")(comp);

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
        }, nb::arg("data"), nb::arg("context") = nb::none(), nb::arg("scene") = nb::none())

        // Phase 1: Create entity with properties but NO components
        .def_static("deserialize_base", [](nb::object data, nb::object context, nb::object scene) -> nb::object {
            try {
                if (data.is_none() || !nb::isinstance<nb::dict>(data)) {
                    return nb::none();
                }

                nb::dict dict_data = nb::cast<nb::dict>(data);

                std::string name = "entity";
                if (dict_data.contains("name")) {
                    name = nb::cast<std::string>(dict_data["name"]);
                }

                std::string uuid_str;
                if (dict_data.contains("uuid")) {
                    uuid_str = nb::cast<std::string>(dict_data["uuid"]);
                }

                // Get pool from scene or use standalone
                tc_entity_pool* pool = nullptr;
                if (!scene.is_none() && nb::hasattr(scene, "_tc_scene")) {
                    nb::object tc_scene_obj = scene.attr("_tc_scene");
                    if (nb::hasattr(tc_scene_obj, "entity_pool_ptr")) {
                        uintptr_t pool_ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("entity_pool_ptr")());
                        pool = reinterpret_cast<tc_entity_pool*>(pool_ptr);
                    }
                }
                if (!pool) {
                    pool = get_standalone_pool();
                }
                if (!pool) {
                    tc::Log::error("Entity::deserialize_base: pool is null");
                    return nb::none();
                }

                // Create entity with UUID directly to avoid hash map collisions
                Entity ent = uuid_str.empty()
                    ? Entity::create(pool, name)
                    : Entity::create_with_uuid(pool, name, uuid_str);
                if (!ent.valid()) {
                    tc::Log::error("Entity::deserialize_base: failed to create entity '%s'", name.c_str());
                    return nb::none();
                }

                // Restore flags
                if (dict_data.contains("priority")) {
                    ent.set_priority(nb::cast<int>(dict_data["priority"]));
                }
                if (dict_data.contains("visible")) {
                    ent.set_visible(nb::cast<bool>(dict_data["visible"]));
                }
                if (dict_data.contains("enabled")) {
                    ent.set_enabled(nb::cast<bool>(dict_data["enabled"]));
                }
                if (dict_data.contains("pickable")) {
                    ent.set_pickable(nb::cast<bool>(dict_data["pickable"]));
                }
                if (dict_data.contains("selectable")) {
                    ent.set_selectable(nb::cast<bool>(dict_data["selectable"]));
                }
                if (dict_data.contains("layer")) {
                    ent.set_layer(nb::cast<uint64_t>(dict_data["layer"]));
                }
                if (dict_data.contains("flags")) {
                    ent.set_flags(nb::cast<uint64_t>(dict_data["flags"]));
                }

                // Restore pose
                if (dict_data.contains("pose")) {
                    nb::object pose_obj = dict_data["pose"];
                    if (nb::isinstance<nb::dict>(pose_obj)) {
                        nb::dict pose = nb::cast<nb::dict>(pose_obj);
                        if (pose.contains("position")) {
                            nb::list pos = nb::cast<nb::list>(pose["position"]);
                            if (nb::len(pos) >= 3) {
                                double xyz[3] = {
                                    nb::cast<double>(pos[0]),
                                    nb::cast<double>(pos[1]),
                                    nb::cast<double>(pos[2])
                                };
                                ent.set_local_position(xyz);
                            }
                        }
                        if (pose.contains("rotation")) {
                            nb::list rot = nb::cast<nb::list>(pose["rotation"]);
                            if (nb::len(rot) >= 4) {
                                double xyzw[4] = {
                                    nb::cast<double>(rot[0]),
                                    nb::cast<double>(rot[1]),
                                    nb::cast<double>(rot[2]),
                                    nb::cast<double>(rot[3])
                                };
                                ent.set_local_rotation(xyzw);
                            }
                        }
                    }
                }

                // Restore scale
                if (dict_data.contains("scale")) {
                    nb::list scl = nb::cast<nb::list>(dict_data["scale"]);
                    if (nb::len(scl) >= 3) {
                        double xyz[3] = {
                            nb::cast<double>(scl[0]),
                            nb::cast<double>(scl[1]),
                            nb::cast<double>(scl[2])
                        };
                        ent.set_local_scale(xyz);
                    }
                }

                return nb::cast(ent);
            } catch (const std::exception& e) {
                tc::Log::error(e, "Entity::deserialize_base");
                return nb::none();
            }
        }, nb::arg("data"), nb::arg("context") = nb::none(), nb::arg("scene") = nb::none())

        // Phase 2: Deserialize components for existing entity
        .def_static("deserialize_components", [](nb::object py_entity, nb::object data, nb::object context, nb::object scene) {
            try {
                if (py_entity.is_none() || data.is_none()) return;

                Entity ent = nb::cast<Entity>(py_entity);
                if (!ent.valid()) return;

                nb::dict dict_data = nb::cast<nb::dict>(data);
                if (!dict_data.contains("components")) return;

                nb::object comp_list_obj = dict_data["components"];
                if (!nb::isinstance<nb::list>(comp_list_obj)) return;
                nb::list components = nb::cast<nb::list>(comp_list_obj);

                // Get scene pointer for entity reference resolution
                tc_scene* c_scene = nullptr;
                if (!scene.is_none() && nb::hasattr(scene, "_tc_scene")) {
                    nb::object tc_scene_obj = scene.attr("_tc_scene");
                    if (nb::hasattr(tc_scene_obj, "scene_ptr")) {
                        uintptr_t scene_ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                        c_scene = reinterpret_cast<tc_scene*>(scene_ptr);
                    }
                }

                auto& registry = ComponentRegistry::instance();

                for (size_t i = 0; i < nb::len(components); ++i) {
                    nb::object comp_data_item = components[i];
                    if (!nb::isinstance<nb::dict>(comp_data_item)) continue;
                    nb::dict comp_data = nb::cast<nb::dict>(comp_data_item);

                    if (!comp_data.contains("type")) continue;
                    std::string type_name = nb::cast<std::string>(comp_data["type"]);

                    if (!registry.has(type_name)) {
                        tc::Log::warn("Unknown component type: %s (skipping)", type_name.c_str());
                        continue;
                    }

                    try {
                        nb::object comp = registry.create(type_name);
                        if (comp.is_none()) continue;

                        nb::object data_field;
                        if (comp_data.contains("data")) {
                            data_field = comp_data["data"];
                        } else {
                            data_field = nb::dict();
                        }

                        const auto* info = registry.get_info(type_name);
                        if (info && info->kind == TC_CXX_COMPONENT) {
                            if (nb::isinstance<nb::dict>(data_field)) {
                                nb::dict data_dict = nb::cast<nb::dict>(data_field);
                                void* raw_ptr = nb::inst_ptr<void>(comp);
                                // Use C API for deserialization
                                tc_value tc_data = tc::nb_to_tc_value(data_dict);
                                tc_inspect_deserialize_with_scene(raw_ptr, type_name.c_str(), &tc_data, c_scene);
                                tc_value_free(&tc_data);
                            }
                        } else {
                            if (nb::hasattr(comp, "deserialize_data")) {
                                comp.attr("deserialize_data")(data_field, context);
                            }
                        }

                        py_entity.attr("add_component")(comp);

                        if (!ent.validate_components()) {
                            tc::Log::error("Component validation failed after adding %s", type_name.c_str());
                        }
                    } catch (const std::exception& e) {
                        tc::Log::warn(e, "Failed to deserialize component %s", type_name.c_str());
                    }
                }
            } catch (const std::exception& e) {
                tc::Log::error(e, "Entity::deserialize_components");
            }
        }, nb::arg("entity"), nb::arg("data"), nb::arg("context") = nb::none(), nb::arg("scene") = nb::none())

        .def_static("deserialize_with_children", [](nb::object data, nb::object context, nb::object scene) -> nb::object {
            std::function<nb::object(nb::object, nb::object, nb::object)> deserialize_recursive;
            deserialize_recursive = [&deserialize_recursive](nb::object data, nb::object context, nb::object scene) -> nb::object {
                nb::object entity_cls = nb::module_::import_("termin.entity").attr("Entity");
                nb::object ent = entity_cls.attr("deserialize")(data, context, scene);
                if (ent.is_none()) {
                    return nb::none();
                }

                if (nb::isinstance<nb::dict>(data)) {
                    nb::dict dict_data = nb::cast<nb::dict>(data);
                    if (dict_data.contains("children")) {
                        nb::object children_obj = dict_data["children"];
                        if (nb::isinstance<nb::list>(children_obj)) {
                            nb::list children = nb::cast<nb::list>(children_obj);
                            for (size_t i = 0; i < nb::len(children); ++i) {
                                nb::object child_data = children[i];
                                nb::object child = deserialize_recursive(child_data, context, scene);
                                if (!child.is_none()) {
                                    child.attr("set_parent")(ent);
                                }
                            }
                        }
                    }
                }

                return ent;
            };

            return deserialize_recursive(data, context, scene);
        }, nb::arg("data"), nb::arg("context") = nb::none(), nb::arg("scene") = nb::none());
}

} // namespace termin
