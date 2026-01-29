// entity_bindings.cpp - Entity class binding
#include "entity_bindings.hpp"
#include "entity_helpers.hpp"

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/ndarray.h>
#include <functional>
#include <cstring>

#include "tc_log.hpp"
#include "termin/entity/component.hpp"
#include "termin/entity/component_registry_python.hpp"
#include "termin/entity/entity.hpp"
#include "termin/camera/camera_component.hpp"
#include "termin/geom/general_transform3.hpp"
#include "termin/geom/general_pose3.hpp"
#include "termin/geom/pose3.hpp"
#include "../../../../core_c/include/tc_scene.h"
#include "../../../../core_c/include/tc_inspect.hpp"
#include "../tc_value_helpers.hpp"
#include "../../tc_scene_ref.hpp"
#include "../../viewport/tc_viewport_ref.hpp"
#include "../../mesh/tc_mesh_handle.hpp"
#include "../../material/tc_material_handle.hpp"
#include "../../collision/collision_world.hpp"

namespace nb = nanobind;

namespace termin {

// component_to_python and tc_component_to_python are defined in entity_helpers.hpp

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

// Non-owning reference to a tc_component - allows working with components
// without requiring Python bindings for their specific type
class TcComponentRef {
public:
    tc_component* _c = nullptr;

    TcComponentRef() = default;
    explicit TcComponentRef(tc_component* c) : _c(c) {}

    bool valid() const { return _c != nullptr; }

    const char* type_name() const {
        return _c ? tc_component_type_name(_c) : "";
    }

    bool enabled() const { return _c ? _c->enabled : false; }
    void set_enabled(bool v) { if (_c) _c->enabled = v; }

    bool active_in_editor() const { return _c ? _c->active_in_editor : false; }
    void set_active_in_editor(bool v) { if (_c) _c->active_in_editor = v; }

    bool is_drawable() const { return tc_component_is_drawable(_c); }
    bool is_input_handler() const { return tc_component_is_input_handler(_c); }

    tc_component_kind kind() const {
        return _c ? _c->kind : TC_NATIVE_COMPONENT;
    }

    // Try to get typed Python object (may return None if no bindings available)
    nb::object to_python() const {
        if (!_c) return nb::none();
        return tc_component_to_python(_c);
    }

    // Get owner entity
    Entity entity() const {
        if (!_c || !_c->owner_pool) return Entity();
        return Entity(_c->owner_pool, _c->owner_entity_id);
    }

    // Serialize component data using tc_inspect
    nb::object serialize_data() const {
        if (!_c) return nb::none();

        void* obj_ptr = nullptr;
        if (_c->kind == TC_NATIVE_COMPONENT) {
            // For C++ components, get CxxComponent pointer
            obj_ptr = CxxComponent::from_tc(_c);
        } else {
            // For external (Python) components, body holds the object
            obj_ptr = _c->body;
        }
        if (!obj_ptr) return nb::none();

        tc_value v = tc_inspect_serialize(obj_ptr, tc_component_type_name(_c));
        nb::object result = tc_value_to_py(&v);
        tc_value_free(&v);
        return result;
    }

    // Full serialize (type + data) - returns dict with "type" and "data"
    nb::object serialize() const {
        if (!_c) return nb::none();

        // For Python components, check if they have a custom serialize method
        if (_c->native_language == TC_LANGUAGE_PYTHON && _c->body) {
            nb::object py_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(_c->body));
            if (nb::hasattr(py_obj, "serialize")) {
                // Call Python serialize method (e.g., for UnknownComponent)
                nb::object result = py_obj.attr("serialize")();
                if (!result.is_none()) {
                    return result;
                }
            }
        }

        nb::dict result;
        result["type"] = type_name();
        result["data"] = serialize_data();
        return result;
    }

    // Deserialize data into component with explicit scene context
    void deserialize_data(nb::object data, TcSceneRef scene_ref = TcSceneRef()) {
        if (!_c) {
            tc::Log::warn("[Inspect] deserialize_data called on invalid component reference");
            return;
        }
        if (data.is_none()) {
            tc::Log::warn("[Inspect] deserialize_data called with None data for %s", tc_component_type_name(_c));
            return;
        }

        void* obj_ptr = nullptr;
        if (_c->kind == TC_NATIVE_COMPONENT) {
            obj_ptr = CxxComponent::from_tc(_c);
        } else {
            obj_ptr = _c->body;
        }
        if (!obj_ptr) {
            tc::Log::warn("[Inspect] deserialize_data: null object pointer for %s", tc_component_type_name(_c));
            return;
        }

        tc_value v = py_to_tc_value(data);
        tc_inspect_deserialize(obj_ptr, tc_component_type_name(_c), &v, scene_ref.ptr());
        tc_value_free(&v);
    }

    // Get field value by name
    nb::object get_field(const std::string& field_name) const {
        if (!_c) return nb::none();

        void* obj_ptr = nullptr;
        if (_c->kind == TC_NATIVE_COMPONENT) {
            obj_ptr = CxxComponent::from_tc(_c);
        } else {
            obj_ptr = _c->body;
        }
        if (!obj_ptr) return nb::none();

        try {
            return tc::InspectRegistry_get(tc::InspectRegistry::instance(),
                obj_ptr, tc_component_type_name(_c), field_name);
        } catch (...) {
            return nb::none();
        }
    }

    // Set field value by name
    void set_field(const std::string& field_name, nb::object value, TcSceneRef scene_ref = TcSceneRef()) {
        if (!_c || value.is_none()) return;

        void* obj_ptr = nullptr;
        if (_c->kind == TC_NATIVE_COMPONENT) {
            obj_ptr = CxxComponent::from_tc(_c);
        } else {
            obj_ptr = _c->body;
        }
        if (!obj_ptr) return;

        try {
            tc::InspectRegistry_set(tc::InspectRegistry::instance(),
                obj_ptr, tc_component_type_name(_c), field_name, value, scene_ref.ptr());
        } catch (...) {
            // Field not found or setter failed
        }
    }

    // Comparison
    bool operator==(const TcComponentRef& other) const { return _c == other._c; }
    bool operator!=(const TcComponentRef& other) const { return _c != other._c; }
};

void bind_entity_class(nb::module_& m) {
    // Ancestor iterator
    nb::class_<EntityAncestorIterator>(m, "_EntityAncestorIterator")
        .def("__iter__", [](EntityAncestorIterator& self) -> EntityAncestorIterator& { return self; })
        .def("__next__", &EntityAncestorIterator::next);

    // Non-owning scene reference - for passing scene context
    nb::class_<TcSceneRef>(m, "TcSceneRef")
        .def(nb::init<>())
        .def("__bool__", &TcSceneRef::valid)
        .def("__repr__", [](const TcSceneRef& self) {
            if (!self.valid()) return std::string("<TcSceneRef: invalid>");
            return std::string("<TcSceneRef: valid>");
        })
        .def("skybox_mesh", [](TcSceneRef& self) -> TcMesh {
            if (!self.valid()) return TcMesh();
            tc_mesh* mesh = tc_scene_get_skybox_mesh(self.ptr());
            if (!mesh) return TcMesh();
            return TcMesh(mesh);
        })
        .def("skybox_material", [](TcSceneRef& self) -> TcMaterial {
            if (!self.valid()) return TcMaterial();
            tc_material* material = tc_scene_get_skybox_material(self.ptr());
            if (!material) return TcMaterial();
            return TcMaterial(material);
        })
        .def_prop_ro("skybox_type", [](TcSceneRef& self) -> std::string {
            if (!self.valid()) return "gradient";
            int type = tc_scene_get_skybox_type(self.ptr());
            switch (type) {
                case TC_SKYBOX_NONE: return "none";
                case TC_SKYBOX_SOLID: return "solid";
                default: return "gradient";
            }
        })
        .def_prop_ro("skybox_color", [](TcSceneRef& self) -> std::tuple<float, float, float> {
            if (!self.valid()) return {0.5f, 0.7f, 0.9f};
            float r, g, b;
            tc_scene_get_skybox_color(self.ptr(), &r, &g, &b);
            return {r, g, b};
        })
        .def_prop_ro("skybox_top_color", [](TcSceneRef& self) -> std::tuple<float, float, float> {
            if (!self.valid()) return {0.4f, 0.6f, 0.9f};
            float r, g, b;
            tc_scene_get_skybox_top_color(self.ptr(), &r, &g, &b);
            return {r, g, b};
        })
        .def_prop_ro("skybox_bottom_color", [](TcSceneRef& self) -> std::tuple<float, float, float> {
            if (!self.valid()) return {0.6f, 0.5f, 0.4f};
            float r, g, b;
            tc_scene_get_skybox_bottom_color(self.ptr(), &r, &g, &b);
            return {r, g, b};
        })
        .def("get_components_of_type", [](TcSceneRef& self, const std::string& type_name) {
            nb::list result;
            if (!self.valid()) return result;
            tc_component* c = tc_scene_first_component_of_type(self.ptr(), type_name.c_str());
            while (c != NULL) {
                nb::object py_comp = tc_component_to_python(c);
                if (!py_comp.is_none()) {
                    result.append(py_comp);
                }
                c = c->type_next;
            }
            return result;
        }, nb::arg("type_name"), "Get all components of given type")
        .def_prop_ro("collision_world", [](TcSceneRef& self) -> collision::CollisionWorld* {
            if (!self.valid()) return nullptr;
            void* cw = tc_scene_get_collision_world(self.ptr());
            return static_cast<collision::CollisionWorld*>(cw);
        }, nb::rv_policy::reference, "Get collision world for this scene")
        .def_prop_ro("colliders", [](TcSceneRef& self) {
            // Return ColliderComponent instances (not raw Collider*)
            nb::list result;
            if (!self.valid()) return result;
            tc_component* c = tc_scene_first_component_of_type(self.ptr(), "ColliderComponent");
            while (c != NULL) {
                nb::object py_comp = tc_component_to_python(c);
                if (!py_comp.is_none()) {
                    result.append(py_comp);
                }
                c = c->type_next;
            }
            return result;
        }, "Get all ColliderComponent instances");

    // Non-owning viewport reference - for passing viewport context
    nb::class_<TcViewportRef>(m, "TcViewportRef")
        .def(nb::init<>())
        .def("__bool__", &TcViewportRef::is_valid)
        .def("is_valid", &TcViewportRef::is_valid)
        .def("__repr__", [](const TcViewportRef& self) {
            if (!self.is_valid()) return std::string("<TcViewportRef: invalid>");
            return std::string("<TcViewportRef: '") + self.name() + "'>";
        })
        .def_prop_ro("name", &TcViewportRef::name)
        .def_prop_ro("enabled", &TcViewportRef::enabled)
        .def_prop_ro("depth", &TcViewportRef::depth)
        .def_prop_ro("layer_mask", &TcViewportRef::layer_mask)
        .def_prop_ro("internal_entities", [](TcViewportRef& self) -> nb::object {
            if (!self.is_valid() || !self.has_internal_entities()) return nb::none();
            tc_entity_pool* pool = self.internal_entities_pool();
            tc_entity_id id = self.internal_entities_id();
            return nb::cast(Entity(pool, id));
        });

    // Non-owning component reference - works with any component regardless of language bindings
    nb::class_<TcComponentRef>(m, "TcComponentRef")
        .def(nb::init<>())
        .def("__bool__", &TcComponentRef::valid)
        .def_prop_ro("valid", &TcComponentRef::valid)
        .def("__eq__", &TcComponentRef::operator==)
        .def("__ne__", &TcComponentRef::operator!=)
        .def("__repr__", [](const TcComponentRef& self) {
            if (!self.valid()) return std::string("<TcComponentRef: invalid>");
            return std::string("<TcComponentRef: ") + self.type_name() + ">";
        })
        .def_prop_ro("type_name", &TcComponentRef::type_name)
        .def_prop_rw("enabled", &TcComponentRef::enabled, &TcComponentRef::set_enabled)
        .def_prop_rw("active_in_editor", &TcComponentRef::active_in_editor, &TcComponentRef::set_active_in_editor)
        .def_prop_ro("is_drawable", &TcComponentRef::is_drawable)
        .def_prop_ro("is_input_handler", &TcComponentRef::is_input_handler)
        .def_prop_ro("kind", &TcComponentRef::kind)
        .def_prop_ro("entity", &TcComponentRef::entity)
        .def("to_python", &TcComponentRef::to_python,
            "Try to get typed Python component object. Returns None if no bindings available.")
        .def("serialize", &TcComponentRef::serialize,
            "Serialize component to dict with 'type' and 'data' keys.")
        .def("serialize_data", &TcComponentRef::serialize_data,
            "Serialize component data (fields only) to dict.")
        .def("deserialize_data", &TcComponentRef::deserialize_data,
            nb::arg("data"), nb::arg("scene") = TcSceneRef(),
            "Deserialize data dict into component fields. Pass scene for handle resolution.")
        .def("get_field", &TcComponentRef::get_field,
            nb::arg("field_name"),
            "Get field value by name. Returns None if field not found.")
        .def("set_field", &TcComponentRef::set_field,
            nb::arg("field_name"), nb::arg("value"), nb::arg("scene") = TcSceneRef(),
            "Set field value by name.");

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
            tc_entity_pool* pool = e.pool();
            if (!pool) return nb::none();
            tc_scene* s = tc_entity_pool_get_scene(pool);
            if (!s) return nb::none();
            void* py_wrapper = tc_scene_get_py_wrapper(s);
            if (!py_wrapper) return nb::none();
            return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(py_wrapper));
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

        // model_matrix returns row-major for Python (numpy convention)
        // world_matrix returns column-major, so transpose
        .def("model_matrix", [](Entity& e) {
            double m[16];
            e.transform().world_matrix(m);
            double* buf = new double[16];
            // Transpose: column-major to row-major
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

        // Component management - create by type name only
        // (removed add_component that accepts external objects)
        .def("add_component_by_name", [](Entity& e, const std::string& type_name) -> TcComponentRef {
            tc_component* tc = ComponentRegistryPython::create_tc_component(type_name);
            if (!tc) {
                throw std::runtime_error("Failed to create component: " + type_name);
            }
            e.add_component_ptr(tc);
            return TcComponentRef(tc);
        }, nb::arg("type_name"),
           "Create component by type name and add to entity. Returns TcComponentRef.")

        // Add existing PythonComponent (uses its tc_component instead of factory)
        .def("add_component", [](Entity& e, nb::object comp) -> TcComponentRef {
            // Get tc_component* from PythonComponent._tc.c_ptr_int()
            nb::object tc_wrapper = comp.attr("_tc");
            uintptr_t ptr = nb::cast<uintptr_t>(tc_wrapper.attr("c_ptr_int")());
            tc_component* tc = reinterpret_cast<tc_component*>(ptr);
            if (!tc) {
                throw std::runtime_error("Component has no tc_component");
            }
            e.add_component_ptr(tc);
            return TcComponentRef(tc);
        }, nb::arg("component"),
           "Add existing PythonComponent to entity. Returns TcComponentRef.")

        // Remove existing PythonComponent (uses its tc_component)
        .def("remove_component", [](Entity& e, nb::object comp) {
            // Get tc_component* from PythonComponent._tc.c_ptr_int()
            nb::object tc_wrapper = comp.attr("_tc");
            uintptr_t ptr = nb::cast<uintptr_t>(tc_wrapper.attr("c_ptr_int")());
            tc_component* tc = reinterpret_cast<tc_component*>(ptr);
            if (!tc) {
                throw std::runtime_error("Component has no tc_component");
            }
            e.remove_component_ptr(tc);
        }, nb::arg("component"),
           "Remove existing PythonComponent from entity.")

        // TcComponentRef-based methods (work without Python wrappers)
        .def("remove_component_ref", [](Entity& e, TcComponentRef ref) {
            if (!ref.valid()) return;
            e.remove_component_ptr(ref._c);
        }, nb::arg("ref"), "Remove component by TcComponentRef.")

        .def("has_component_ref", [](Entity& e, TcComponentRef ref) -> bool {
            if (!ref.valid()) return false;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                if (e.component_at(i) == ref._c) return true;
            }
            return false;
        }, nb::arg("ref"), "Check if entity has this component.")
        .def("get_component_by_type", [](Entity& e, const std::string& type_name) -> nb::object {
            tc_component* tc = e.get_component_by_type_name(type_name);
            if (!tc) {
                return nb::none();
            }
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
            if (!e.valid()) {
                return nb::none();
            }
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                nb::object py_comp = tc_component_to_python(tc);

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

                nb::object py_comp = tc_component_to_python(tc);

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

                nb::object py_comp = tc_component_to_python(tc);
                if (!py_comp.is_none()) {
                    result.append(py_comp);
                }
            }
            return result;
        })

        // tc_components - returns all components as TcComponentRef (works with any language)
        .def_prop_ro("tc_components", [](Entity& e) {
            nb::list result;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (tc) {
                    result.append(TcComponentRef(tc));
                }
            }
            return result;
        })

        // get_tc_component - get component ref by type name
        .def("get_tc_component", [](Entity& e, const std::string& type_name) -> TcComponentRef {
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;
                if (tc_component_type_name(tc) == type_name ||
                    strcmp(tc_component_type_name(tc), type_name.c_str()) == 0) {
                    return TcComponentRef(tc);
                }
            }
            return TcComponentRef();
        }, nb::arg("type_name"))

        // has_tc_component - check if entity has component with given type name
        .def("has_tc_component", [](Entity& e, const std::string& type_name) -> bool {
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;
                if (strcmp(tc_component_type_name(tc), type_name.c_str()) == 0) {
                    return true;
                }
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
        .def("on_added_to_scene", [](Entity& e, TcSceneRef scene_ref) {
            e.on_added_to_scene(scene_ref.ptr());
        }, nb::arg("scene"))
        .def("on_removed_from_scene", &Entity::on_removed_from_scene)
        .def("on_added", [](Entity& e, TcSceneRef scene_ref) {
            e.on_added_to_scene(scene_ref.ptr());
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
            if (data.type == TC_VALUE_NIL) {
                return nb::none();
            }
            nb::dict result = nb::cast<nb::dict>(tc_value_to_py(&data));
            tc_value_free(&data);

            nb::list comp_list;
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* tc = e.component_at(i);
                if (!tc) continue;

                // Use TcComponentRef for unified serialization (works for all component types)
                TcComponentRef ref(tc);
                nb::object comp_data = ref.serialize();
                if (!comp_data.is_none()) {
                    comp_list.append(comp_data);
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

                    for (size_t i = 0; i < nb::len(components); ++i) {
                        nb::object comp_data_item = components[i];
                        if (!nb::isinstance<nb::dict>(comp_data_item)) continue;
                        nb::dict comp_data = nb::cast<nb::dict>(comp_data_item);

                        if (!comp_data.contains("type")) continue;

                        std::string type_name = nb::cast<std::string>(comp_data["type"]);

                        nb::object data_field;
                        if (comp_data.contains("data")) {
                            data_field = comp_data["data"];
                        } else {
                            data_field = nb::dict();
                        }

                        TcSceneRef scene_ref(c_scene);

                        if (!ComponentRegistry::instance().has(type_name)) {
                            // Create UnknownComponent to preserve data
                            tc::Log::warn("Unknown component type: %s (creating placeholder)", type_name.c_str());
                            try {
                                tc_component* tc = ComponentRegistryPython::create_tc_component("UnknownComponent");
                                if (tc) {
                                    ent.add_component_ptr(tc);
                                    TcComponentRef ref(tc);
                                    ref.set_field("stored_type", nb::str(type_name.c_str()), scene_ref);
                                    ref.set_field("stored_data", data_field, scene_ref);
                                }
                            } catch (const std::exception& e) {
                                tc::Log::error(e, "Failed to create UnknownComponent for %s", type_name.c_str());
                            }
                            continue;
                        }

                        try {
                            // Create and add component via unified factory
                            tc_component* tc = ComponentRegistryPython::create_tc_component(type_name);
                            if (!tc) {
                                tc::Log::warn("Failed to create component: %s", type_name.c_str());
                                continue;
                            }

                            ent.add_component_ptr(tc);

                            // Deserialize via TcComponentRef (works for all component types)
                            TcComponentRef ref(tc);
                            ref.deserialize_data(data_field, scene_ref);

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
                if (!ent.valid()) {
                    return;
                }

                nb::dict dict_data = nb::cast<nb::dict>(data);
                if (!dict_data.contains("components")) return;

                nb::object comp_list_obj = dict_data["components"];
                if (!nb::isinstance<nb::list>(comp_list_obj)) return;
                nb::list components = nb::cast<nb::list>(comp_list_obj);

                // Get scene ref for entity reference resolution
                TcSceneRef scene_ref;
                if (!scene.is_none() && nb::hasattr(scene, "_tc_scene")) {
                    nb::object tc_scene_obj = scene.attr("_tc_scene");
                    if (nb::hasattr(tc_scene_obj, "scene_ptr")) {
                        uintptr_t scene_ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                        scene_ref = TcSceneRef(reinterpret_cast<tc_scene*>(scene_ptr));
                    }
                }

                for (size_t i = 0; i < nb::len(components); ++i) {
                    nb::object comp_data_item = components[i];
                    if (!nb::isinstance<nb::dict>(comp_data_item)) continue;
                    nb::dict comp_data = nb::cast<nb::dict>(comp_data_item);

                    if (!comp_data.contains("type")) continue;
                    std::string type_name = nb::cast<std::string>(comp_data["type"]);

                    nb::object data_field;
                    if (comp_data.contains("data")) {
                        data_field = comp_data["data"];
                    } else {
                        data_field = nb::dict();
                    }

                    if (!ComponentRegistry::instance().has(type_name)) {
                        // Create UnknownComponent to preserve data
                        tc::Log::warn("Unknown component type: %s (creating placeholder)", type_name.c_str());
                        try {
                            TcComponentRef ref = nb::cast<TcComponentRef>(
                                py_entity.attr("add_component_by_name")("UnknownComponent"));
                            if (ref.valid()) {
                                // Set stored_type and stored_data via tc_inspect
                                ref.set_field("stored_type", nb::str(type_name.c_str()), scene_ref);
                                ref.set_field("stored_data", data_field, scene_ref);
                            }
                        } catch (const std::exception& e) {
                            tc::Log::error(e, "Failed to create UnknownComponent for %s", type_name.c_str());
                        }
                        continue;
                    }

                    try {
                        // Create and add component via unified add_component_by_name
                        TcComponentRef ref = nb::cast<TcComponentRef>(
                            py_entity.attr("add_component_by_name")(type_name));
                        if (!ref.valid()) {
                            tc::Log::warn("Failed to create component: %s", type_name.c_str());
                            continue;
                        }

                        // Deserialize data via TcComponentRef (works for all component types)
                        ref.deserialize_data(data_field, scene_ref);

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
