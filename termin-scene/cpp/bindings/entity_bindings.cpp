// entity_bindings.cpp - Entity class binding
#include <termin/bindings/entity_bindings.hpp>
#include <termin/bindings/entity_helpers.hpp>

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/ndarray.h>
#include <functional>
#include <cstring>
#include <cstdint>

#include <tcbase/tc_log.hpp>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry_python.hpp>
#include <termin/entity/entity.hpp>
#include <termin/geom/general_transform3.hpp>
#include <termin/geom/general_pose3.hpp>
#include <termin/geom/pose3.hpp>
#include <termin/tc_scene.hpp>
#include "core/tc_scene.h"
#include "inspect/tc_inspect.h"
#include "inspect/tc_inspect_context.h"

extern "C" {
#include "core/tc_archetype.h"
}

namespace nb = nanobind;

namespace termin {

// Look up SoA type id by name
static tc_soa_type_id soa_type_id_by_name(const std::string& name) {
    tc_soa_type_registry* reg = tc_soa_global_registry();
    for (size_t i = 0; i < reg->count; i++) {
        if (reg->types[i].name && name == reg->types[i].name) {
            return (tc_soa_type_id)i;
        }
    }
    return TC_SOA_TYPE_INVALID;
}

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

// Forward-declare TcComponentRef (defined in tc_component_ref_bindings.cpp, registered in same module)
// We use tc_component* directly here since TcComponentRef is a local class in that TU.
// For add_component_by_name etc., we return nb::object and let nanobind find the registered type.

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
        .def_prop_ro("scene", [](const Entity& e) -> nb::object {
            TcSceneRef scene = e.scene();
            if (!scene.is_alive()) return nb::none();
            return nb::cast(scene);
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
            ang_buf[0] = gp.ang.x; ang_buf[1] = gp.ang.y;
            ang_buf[2] = gp.ang.z; ang_buf[3] = gp.ang.w;
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
            for (int row = 0; row < 4; ++row)
                for (int col = 0; col < 4; ++col)
                    buf[row * 4 + col] = m[col * 4 + row];
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
        .def("add_component_by_name", [](Entity& e, const std::string& type_name) -> nb::object {
            tc_component* tc = ComponentRegistryPython::create_tc_component(type_name);
            if (!tc) {
                throw std::runtime_error("Failed to create component: " + type_name);
            }
            e.add_component_ptr(tc);
            // Return as nb::object — nanobind will find TcComponentRef type
            // Use module import to construct TcComponentRef
            nb::module_ mod = nb::module_::import_("termin.scene._scene_native");
            nb::object cls = mod.attr("TcComponentRef");
            return cls(reinterpret_cast<uintptr_t>(tc));
        }, nb::arg("type_name"))

        .def("add_component", [](Entity& e, const std::string& type_name) -> nb::object {
            tc_component* tc = ComponentRegistryPython::create_tc_component(type_name);
            if (!tc) {
                throw std::runtime_error("Failed to create component: " + type_name);
            }
            e.add_component_ptr(tc);
            nb::module_ mod = nb::module_::import_("termin.scene._scene_native");
            nb::object cls = mod.attr("TcComponentRef");
            return cls(reinterpret_cast<uintptr_t>(tc));
        }, nb::arg("component"))

        .def("add_component", [](Entity& e, CxxComponent& comp) -> nb::object {
            tc_component* tc = comp.c_component();
            if (!tc) {
                throw std::runtime_error("CxxComponent has no tc_component");
            }
            e.add_component_ptr(tc);
            nb::module_ mod = nb::module_::import_("termin.scene._scene_native");
            nb::object cls = mod.attr("TcComponentRef");
            return cls(reinterpret_cast<uintptr_t>(tc));
        }, nb::arg("component"))

        .def("add_component", [](Entity& e, nb::object comp) -> nb::object {
            nb::object tc_wrapper = comp.attr("_tc");
            uintptr_t ptr = nb::cast<uintptr_t>(tc_wrapper.attr("c_ptr_int")());
            tc_component* tc = reinterpret_cast<tc_component*>(ptr);
            if (!tc) {
                throw std::runtime_error("Component has no tc_component");
            }
            e.add_component_ptr(tc);
            nb::module_ mod = nb::module_::import_("termin.scene._scene_native");
            nb::object cls = mod.attr("TcComponentRef");
            return cls(reinterpret_cast<uintptr_t>(tc));
        }, nb::arg("component"))

        .def("remove_component", [](Entity& e, nb::object comp) {
            nb::object tc_wrapper = comp.attr("_tc");
            uintptr_t ptr = nb::cast<uintptr_t>(tc_wrapper.attr("c_ptr_int")());
            tc_component* tc = reinterpret_cast<tc_component*>(ptr);
            if (!tc) {
                throw std::runtime_error("Component has no tc_component");
            }
            e.remove_component_ptr(tc);
        }, nb::arg("component"))

        .def("remove_component_ref", [](Entity& e, nb::object ref) {
            uintptr_t ptr = nb::cast<uintptr_t>(ref.attr("tc_component_ptr"));
            tc_component* tc = reinterpret_cast<tc_component*>(ptr);
            if (!tc) return;
            e.remove_component_ptr(tc);
        }, nb::arg("ref"))

        .def("has_component_ref", [](Entity& e, nb::object ref) -> bool {
            uintptr_t ptr = nb::cast<uintptr_t>(ref.attr("tc_component_ptr"));
            tc_component* tc = reinterpret_cast<tc_component*>(ptr);
            if (!tc) return false;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                if (e.component_at(i) == tc) return true;
            }
            return false;
        }, nb::arg("ref"))

        .def("get_component_by_type", [](Entity& e, const std::string& type_name) -> nb::object {
            tc_component* tc = e.get_component_by_type_name(type_name);
            if (!tc) return nb::none();
            return tc_component_to_python(tc);
        }, nb::arg("type_name"))
        .def("has_component_type", [](Entity& e, const std::string& type_name) -> bool {
            return e.get_component_by_type_name(type_name) != nullptr;
        }, nb::arg("type_name"))
        .def("get_python_component", [](Entity& e, const std::string& type_name) -> nb::object {
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (tc && tc->native_language == TC_LANGUAGE_PYTHON && tc->body) {
                    const char* comp_type = tc_component_type_name(tc);
                    if (comp_type && type_name == comp_type) {
                        return nb::borrow((PyObject*)tc->body);
                    }
                }
            }
            return nb::none();
        }, nb::arg("type_name"))
        .def("get_component", [](Entity& e, nb::object type_class) -> nb::object {
            if (!e.valid()) return nb::none();
            std::string target_type;
            if (nb::hasattr(type_class, "__name__")) {
                target_type = nb::cast<std::string>(type_class.attr("__name__"));
            }
            if (target_type.empty()) return nb::none();
            tc_component* tc = e.get_component_by_type_name(target_type);
            if (!tc) return nb::none();
            return tc_component_to_python(tc);
        }, nb::arg("component_type"))
        .def("find_component", [](Entity& e, nb::object type_class) -> nb::object {
            std::string target_type;
            if (nb::hasattr(type_class, "__name__")) {
                target_type = nb::cast<std::string>(type_class.attr("__name__"));
            }
            if (target_type.empty()) {
                throw std::runtime_error("Component class has no __name__");
            }
            tc_component* tc = e.get_component_by_type_name(target_type);
            if (!tc) {
                throw std::runtime_error("Component not found: " + target_type);
            }
            return tc_component_to_python(tc);
        }, nb::arg("component_type"))
        .def_prop_ro("components", [](Entity& e) {
            nb::list result;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;
                nb::object py_comp = tc_component_to_python(tc);
                if (!py_comp.is_none()) result.append(py_comp);
            }
            return result;
        })

        .def_prop_ro("tc_components", [](Entity& e) {
            nb::list result;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;
                // Construct TcComponentRef via module
                nb::module_ mod = nb::module_::import_("termin.scene._scene_native");
                nb::object cls = mod.attr("TcComponentRef");
                result.append(cls(reinterpret_cast<uintptr_t>(tc)));
            }
            return result;
        })

        // SoA component management
        .def("add_soa_by_name", [](Entity& e, const std::string& name) {
            tc_soa_type_id id = soa_type_id_by_name(name);
            if (id == TC_SOA_TYPE_INVALID) {
                throw std::runtime_error("Unknown SoA type: " + name);
            }
            tc_entity_add_soa(e._h, id);
        }, nb::arg("name"))
        .def("remove_soa_by_name", [](Entity& e, const std::string& name) {
            tc_soa_type_id id = soa_type_id_by_name(name);
            if (id == TC_SOA_TYPE_INVALID) {
                throw std::runtime_error("Unknown SoA type: " + name);
            }
            tc_entity_remove_soa(e._h, id);
        }, nb::arg("name"))
        .def("has_soa_by_name", [](Entity& e, const std::string& name) -> bool {
            tc_soa_type_id id = soa_type_id_by_name(name);
            if (id == TC_SOA_TYPE_INVALID) return false;
            return tc_entity_has_soa(e._h, id);
        }, nb::arg("name"))
        .def_prop_ro("soa_component_names", [](Entity& e) {
            nb::list result;
            uint64_t mask = tc_entity_soa_mask(e._h);
            if (mask == 0) return result;
            tc_soa_type_registry* reg = tc_soa_global_registry();
            for (size_t i = 0; i < reg->count; i++) {
                if (mask & (1ULL << i)) {
                    result.append(reg->types[i].name ? reg->types[i].name : "(unnamed)");
                }
            }
            return result;
        })

        // get_tc_component
        .def("get_tc_component", [](Entity& e, const std::string& type_name) -> nb::object {
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;
                if (strcmp(tc_component_type_name(tc), type_name.c_str()) == 0) {
                    nb::module_ mod = nb::module_::import_("termin.scene._scene_native");
                    nb::object cls = mod.attr("TcComponentRef");
                    return cls(reinterpret_cast<uintptr_t>(tc));
                }
            }
            return nb::none();
        }, nb::arg("type_name"))

        .def("has_tc_component", [](Entity& e, const std::string& type_name) -> bool {
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;
                if (strcmp(tc_component_type_name(tc), type_name.c_str()) == 0) return true;
            }
            return false;
        }, nb::arg("type_name"))

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
            if (p.valid()) return nb::cast(p);
            return nb::none();
        })
        .def("children", &Entity::children)
        .def("create_child", &Entity::create_child, nb::arg("name") = "entity")
        .def("destroy_children", &Entity::destroy_children)
        .def("find_child", &Entity::find_child, nb::arg("name"))
        .def("ancestors", [](Entity& e) {
            return EntityAncestorIterator(e);
        })

        // Lifecycle
        .def("update", &Entity::update, nb::arg("dt"))
        .def("on_added_to_scene", [](Entity& e, TcSceneRef scene) {
            e.on_added_to_scene(scene.handle());
        }, nb::arg("scene"))
        .def("on_removed_from_scene", &Entity::on_removed_from_scene)
        .def("on_added", [](Entity& e, TcSceneRef scene) {
            e.on_added_to_scene(scene.handle());
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
            tc_value data = e.serialize_base();
            if (data.type == TC_VALUE_NIL) return nb::none();
            nb::dict result = nb::cast<nb::dict>(tc_value_to_py(&data));
            tc_value_free(&data);

            nb::list comp_list;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;
                // Use TcComponentRef via module
                nb::module_ mod = nb::module_::import_("termin.scene._scene_native");
                nb::object ref_cls = mod.attr("TcComponentRef");
                nb::object ref = ref_cls(reinterpret_cast<uintptr_t>(tc));
                nb::object comp_data = ref.attr("serialize")();
                if (!comp_data.is_none()) comp_list.append(comp_data);
            }
            result["components"] = comp_list;

            nb::list children_list;
            for (Entity child : e.children()) {
                if (child.serializable()) {
                    nb::object py_child = nb::cast(child);
                    nb::object child_data = py_child.attr("serialize")();
                    if (!child_data.is_none()) children_list.append(child_data);
                }
            }
            result["children"] = children_list;
            return result;
        })

        .def_static("deserialize", [](nb::object data, nb::object context, nb::object scene) -> nb::object {
            try {
                if (data.is_none() || !nb::isinstance<nb::dict>(data)) return nb::none();
                nb::dict dict_data = nb::cast<nb::dict>(data);

                std::string name = "entity";
                if (dict_data.contains("name")) {
                    name = nb::cast<std::string>(dict_data["name"]);
                }

                tc_entity_pool* pool = nullptr;
                TcSceneRef c_scene;
                if (!scene.is_none() && nb::hasattr(scene, "scene_handle")) {
                    if (nb::hasattr(scene, "entity_pool_ptr")) {
                        uintptr_t pool_ptr = nb::cast<uintptr_t>(scene.attr("entity_pool_ptr")());
                        pool = reinterpret_cast<tc_entity_pool*>(pool_ptr);
                    }
                    auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene.attr("scene_handle")());
                    tc_scene_handle sh;
                    sh.index = std::get<0>(h);
                    sh.generation = std::get<1>(h);
                    c_scene = TcSceneRef(sh);
                }
                if (!pool) pool = get_standalone_pool();
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
                if (dict_data.contains("priority")) ent.set_priority(nb::cast<int>(dict_data["priority"]));
                if (dict_data.contains("visible")) ent.set_visible(nb::cast<bool>(dict_data["visible"]));
                if (dict_data.contains("enabled")) ent.set_enabled(nb::cast<bool>(dict_data["enabled"]));
                if (dict_data.contains("pickable")) ent.set_pickable(nb::cast<bool>(dict_data["pickable"]));
                if (dict_data.contains("selectable")) ent.set_selectable(nb::cast<bool>(dict_data["selectable"]));
                if (dict_data.contains("layer")) ent.set_layer(nb::cast<uint64_t>(dict_data["layer"]));
                if (dict_data.contains("flags")) ent.set_flags(nb::cast<uint64_t>(dict_data["flags"]));

                // Restore pose
                if (dict_data.contains("pose")) {
                    nb::object pose_obj = dict_data["pose"];
                    if (nb::isinstance<nb::dict>(pose_obj)) {
                        nb::dict pose = nb::cast<nb::dict>(pose_obj);
                        if (pose.contains("position")) {
                            nb::list pos = nb::cast<nb::list>(pose["position"]);
                            if (nb::len(pos) >= 3) {
                                double xyz[3] = {nb::cast<double>(pos[0]), nb::cast<double>(pos[1]), nb::cast<double>(pos[2])};
                                ent.set_local_position(xyz);
                            }
                        }
                        if (pose.contains("rotation")) {
                            nb::list rot = nb::cast<nb::list>(pose["rotation"]);
                            if (nb::len(rot) >= 4) {
                                double xyzw[4] = {nb::cast<double>(rot[0]), nb::cast<double>(rot[1]),
                                                  nb::cast<double>(rot[2]), nb::cast<double>(rot[3])};
                                ent.set_local_rotation(xyzw);
                            }
                        }
                    }
                }
                if (dict_data.contains("scale")) {
                    nb::list scl = nb::cast<nb::list>(dict_data["scale"]);
                    if (nb::len(scl) >= 3) {
                        double xyz[3] = {nb::cast<double>(scl[0]), nb::cast<double>(scl[1]), nb::cast<double>(scl[2])};
                        ent.set_local_scale(xyz);
                    }
                }

                // Deserialize components
                if (dict_data.contains("components")) {
                    nb::object comp_list_obj = dict_data["components"];
                    if (nb::isinstance<nb::list>(comp_list_obj)) {
                        nb::list components = nb::cast<nb::list>(comp_list_obj);
                        for (size_t i = 0; i < nb::len(components); ++i) {
                            nb::object comp_data_item = components[i];
                            if (!nb::isinstance<nb::dict>(comp_data_item)) continue;
                            nb::dict comp_data = nb::cast<nb::dict>(comp_data_item);
                            if (!comp_data.contains("type")) continue;

                            std::string type_name = nb::cast<std::string>(comp_data["type"]);
                            nb::object data_field = comp_data.contains("data") ? nb::borrow(comp_data["data"]) : nb::cast(nb::dict());

                            if (!ComponentRegistry::instance().has(type_name)) {
                                tc::Log::warn("Unknown component type: %s (creating placeholder)", type_name.c_str());
                                try {
                                    tc_component* tc = tc_component_registry_create("UnknownComponent");
                                    if (tc) {
                                        ent.add_component_ptr(tc);
                                        nb::module_ mod = nb::module_::import_("termin.scene._scene_native");
                                        nb::object ref = mod.attr("TcComponentRef")(reinterpret_cast<uintptr_t>(tc));
                                        ref.attr("set_field")("original_type", nb::str(type_name.c_str()), c_scene);
                                        ref.attr("set_field")("original_data", data_field, c_scene);
                                    }
                                } catch (const std::exception& ex) {
                                    tc::Log::error(ex, "Failed to create UnknownComponent for %s", type_name.c_str());
                                }
                                continue;
                            }

                            try {
                                tc_component* tc = ComponentRegistryPython::create_tc_component(type_name);
                                if (!tc) {
                                    tc::Log::warn("Failed to create component: %s", type_name.c_str());
                                    continue;
                                }
                                ent.add_component_ptr(tc);
                                nb::module_ mod = nb::module_::import_("termin.scene._scene_native");
                                nb::object ref = mod.attr("TcComponentRef")(reinterpret_cast<uintptr_t>(tc));
                                ref.attr("deserialize_data")(data_field, c_scene);
                            } catch (const std::exception& ex) {
                                tc::Log::warn(ex, "Failed to deserialize component %s", type_name.c_str());
                            }
                        }
                    }
                }
                return nb::cast(ent);
            } catch (const std::exception& ex) {
                tc::Log::error(ex, "Entity::deserialize");
                return nb::none();
            }
        }, nb::arg("data"), nb::arg("context") = nb::none(), nb::arg("scene") = nb::none())

        .def_static("deserialize_base", [](nb::object data, nb::object context, nb::object scene) -> nb::object {
            try {
                if (data.is_none() || !nb::isinstance<nb::dict>(data)) return nb::none();
                nb::dict dict_data = nb::cast<nb::dict>(data);

                std::string name = "entity";
                if (dict_data.contains("name")) name = nb::cast<std::string>(dict_data["name"]);
                std::string uuid_str;
                if (dict_data.contains("uuid")) uuid_str = nb::cast<std::string>(dict_data["uuid"]);

                tc_entity_pool* pool = nullptr;
                if (!scene.is_none() && nb::hasattr(scene, "entity_pool_ptr")) {
                    uintptr_t pool_ptr = nb::cast<uintptr_t>(scene.attr("entity_pool_ptr")());
                    pool = reinterpret_cast<tc_entity_pool*>(pool_ptr);
                }
                if (!pool) pool = get_standalone_pool();
                if (!pool) {
                    tc::Log::error("Entity::deserialize_base: pool is null");
                    return nb::none();
                }

                Entity ent = uuid_str.empty()
                    ? Entity::create(pool, name)
                    : Entity::create_with_uuid(pool, name, uuid_str);
                if (!ent.valid()) {
                    tc::Log::error("Entity::deserialize_base: failed to create entity '%s'", name.c_str());
                    return nb::none();
                }

                if (dict_data.contains("priority")) ent.set_priority(nb::cast<int>(dict_data["priority"]));
                if (dict_data.contains("visible")) ent.set_visible(nb::cast<bool>(dict_data["visible"]));
                if (dict_data.contains("enabled")) ent.set_enabled(nb::cast<bool>(dict_data["enabled"]));
                if (dict_data.contains("pickable")) ent.set_pickable(nb::cast<bool>(dict_data["pickable"]));
                if (dict_data.contains("selectable")) ent.set_selectable(nb::cast<bool>(dict_data["selectable"]));
                if (dict_data.contains("layer")) ent.set_layer(nb::cast<uint64_t>(dict_data["layer"]));
                if (dict_data.contains("flags")) ent.set_flags(nb::cast<uint64_t>(dict_data["flags"]));

                if (dict_data.contains("pose")) {
                    nb::object pose_obj = dict_data["pose"];
                    if (nb::isinstance<nb::dict>(pose_obj)) {
                        nb::dict pose = nb::cast<nb::dict>(pose_obj);
                        if (pose.contains("position")) {
                            nb::list pos = nb::cast<nb::list>(pose["position"]);
                            if (nb::len(pos) >= 3) {
                                double xyz[3] = {nb::cast<double>(pos[0]), nb::cast<double>(pos[1]), nb::cast<double>(pos[2])};
                                ent.set_local_position(xyz);
                            }
                        }
                        if (pose.contains("rotation")) {
                            nb::list rot = nb::cast<nb::list>(pose["rotation"]);
                            if (nb::len(rot) >= 4) {
                                double xyzw[4] = {nb::cast<double>(rot[0]), nb::cast<double>(rot[1]),
                                                  nb::cast<double>(rot[2]), nb::cast<double>(rot[3])};
                                ent.set_local_rotation(xyzw);
                            }
                        }
                    }
                }
                if (dict_data.contains("scale")) {
                    nb::list scl = nb::cast<nb::list>(dict_data["scale"]);
                    if (nb::len(scl) >= 3) {
                        double xyz[3] = {nb::cast<double>(scl[0]), nb::cast<double>(scl[1]), nb::cast<double>(scl[2])};
                        ent.set_local_scale(xyz);
                    }
                }
                return nb::cast(ent);
            } catch (const std::exception& ex) {
                tc::Log::error(ex, "Entity::deserialize_base");
                return nb::none();
            }
        }, nb::arg("data"), nb::arg("context") = nb::none(), nb::arg("scene") = nb::none())

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

                TcSceneRef scene_ref;
                if (!scene.is_none() && nb::hasattr(scene, "scene_handle")) {
                    auto h = nb::cast<std::tuple<uint32_t, uint32_t>>(scene.attr("scene_handle")());
                    tc_scene_handle sh;
                    sh.index = std::get<0>(h);
                    sh.generation = std::get<1>(h);
                    scene_ref = TcSceneRef(sh);
                }

                for (size_t i = 0; i < nb::len(components); ++i) {
                    nb::object comp_data_item = components[i];
                    if (!nb::isinstance<nb::dict>(comp_data_item)) continue;
                    nb::dict comp_data = nb::cast<nb::dict>(comp_data_item);
                    if (!comp_data.contains("type")) continue;
                    std::string type_name = nb::cast<std::string>(comp_data["type"]);
                    nb::object data_field = comp_data.contains("data") ? nb::borrow(comp_data["data"]) : nb::cast(nb::dict());

                    if (!ComponentRegistry::instance().has(type_name)) {
                        tc::Log::warn("Unknown component type: %s (creating placeholder)", type_name.c_str());
                        try {
                            nb::object ref = py_entity.attr("add_component_by_name")("UnknownComponent");
                            if (nb::cast<bool>(ref)) {
                                ref.attr("set_field")("original_type", nb::str(type_name.c_str()), scene_ref);
                                ref.attr("set_field")("original_data", data_field, scene_ref);
                            }
                        } catch (const std::exception& ex) {
                            tc::Log::error(ex, "Failed to create UnknownComponent for %s", type_name.c_str());
                        }
                        continue;
                    }

                    try {
                        nb::object ref = py_entity.attr("add_component_by_name")(type_name);
                        if (!nb::cast<bool>(ref)) {
                            tc::Log::warn("Failed to create component: %s", type_name.c_str());
                            continue;
                        }
                        ref.attr("deserialize_data")(data_field, scene_ref);
                    } catch (const std::exception& ex) {
                        tc::Log::warn(ex, "Failed to deserialize component %s", type_name.c_str());
                    }
                }
            } catch (const std::exception& ex) {
                tc::Log::error(ex, "Entity::deserialize_components");
            }
        }, nb::arg("entity"), nb::arg("data"), nb::arg("context") = nb::none(), nb::arg("scene") = nb::none())

        .def_static("deserialize_with_children", [](nb::object data, nb::object context, nb::object scene) -> nb::object {
            std::function<nb::object(nb::object, nb::object, nb::object)> deserialize_recursive;
            deserialize_recursive = [&deserialize_recursive](nb::object data, nb::object context, nb::object scene) -> nb::object {
                nb::object entity_cls = nb::module_::import_("termin.entity").attr("Entity");
                nb::object ent = entity_cls.attr("deserialize")(data, context, scene);
                if (ent.is_none()) return nb::none();

                if (nb::isinstance<nb::dict>(data)) {
                    nb::dict dict_data = nb::cast<nb::dict>(data);
                    if (dict_data.contains("children")) {
                        nb::object children_obj = dict_data["children"];
                        if (nb::isinstance<nb::list>(children_obj)) {
                            nb::list children = nb::cast<nb::list>(children_obj);
                            for (size_t i = 0; i < nb::len(children); ++i) {
                                nb::object child = deserialize_recursive(children[i], context, scene);
                                if (!child.is_none()) child.attr("set_parent")(ent);
                            }
                        }
                    }
                }
                return ent;
            };
            return deserialize_recursive(data, context, scene);
        }, nb::arg("data"), nb::arg("context") = nb::none(), nb::arg("scene") = nb::none());

    // Pool utilities
    m.def("get_standalone_pool", []() {
        return reinterpret_cast<uintptr_t>(Entity::standalone_pool());
    });
    m.def("migrate_entity", [](Entity& entity, uintptr_t dst_pool_ptr) -> Entity {
        tc_entity_pool* dst_pool = reinterpret_cast<tc_entity_pool*>(dst_pool_ptr);
        return migrate_entity_to_pool(entity, dst_pool);
    }, nb::arg("entity"), nb::arg("dst_pool"));
}

} // namespace termin
