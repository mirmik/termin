#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "termin/entity/component.hpp"
#include "termin/entity/component_registry.hpp"
#include "termin/entity/entity.hpp"
#include "termin/entity/entity_registry.hpp"
#include "termin/entity/components/rotator_component.hpp"
#include "termin/geom/general_transform3.hpp"

namespace py = pybind11;
using namespace termin;
using namespace termin::geom;

/**
 * Trampoline class for Component.
 * Allows Python classes to inherit from C++ Component.
 */
class PyComponent : public Component {
public:
    using Component::Component;

    const char* type_name() const override {
        PYBIND11_OVERRIDE_PURE(const char*, Component, type_name);
    }

    void start() override {
        PYBIND11_OVERRIDE(void, Component, start);
    }

    void update(float dt) override {
        PYBIND11_OVERRIDE(void, Component, update, dt);
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
    m.doc() = "Native C++ entity/component system for termin";

    // --- Component ---
    py::class_<Component, PyComponent>(m, "Component")
        .def(py::init<>())
        .def("type_name", &Component::type_name)
        .def("start", &Component::start)
        .def("update", &Component::update, py::arg("dt"))
        .def("on_destroy", &Component::on_destroy)
        .def("on_added_to_entity", &Component::on_added_to_entity)
        .def("on_removed_from_entity", &Component::on_removed_from_entity)
        .def_readwrite("enabled", &Component::enabled)
        .def_readonly("is_native", &Component::is_native)
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

    // --- Entity ---
    py::class_<Entity>(m, "Entity")
        .def(py::init<const std::string&, const std::string&>(),
             py::arg("name") = "entity", py::arg("uuid") = "")
        .def(py::init([](py::object pose, const std::string& name, const std::string& uuid) {
            if (pose.is_none()) {
                return new Entity(name, uuid);
            }
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
            return new Entity(gpose, name, uuid);
        }), py::arg("pose") = py::none(), py::arg("name") = "entity", py::arg("uuid") = "")

        // Identity
        .def_readwrite("uuid", &Entity::uuid)
        .def_readwrite("name", &Entity::name)

        // Flags
        .def_readwrite("visible", &Entity::visible)
        .def_readwrite("active", &Entity::active)
        .def_readwrite("pickable", &Entity::pickable)
        .def_readwrite("selectable", &Entity::selectable)

        // Rendering
        .def_readwrite("priority", &Entity::priority)
        .def_readwrite("layer", &Entity::layer)
        .def_readwrite("flags", &Entity::flags)

        // Scene
        .def_readwrite("scene", &Entity::scene)

        // Pick ID
        .def_property_readonly("pick_id", &Entity::pick_id)

        // Transform access
        .def_property_readonly("transform", [](Entity& e) {
            return e.transform.get();
        }, py::return_value_policy::reference)

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
            // Convert column-major to numpy row-major
            for (int i = 0; i < 4; ++i) {
                for (int j = 0; j < 4; ++j) {
                    buf(i, j) = m[j * 4 + i];
                }
            }
            return result;
        })

        // Component management
        .def("add_component", &Entity::add_component, py::arg("component"),
             py::keep_alive<1, 2>())  // Entity keeps component alive
        .def("remove_component", &Entity::remove_component, py::arg("component"))
        .def("get_component_by_type", &Entity::get_component_by_type,
             py::arg("type_name"), py::return_value_policy::reference)
        .def_property_readonly("components", [](Entity& e) {
            py::list result;
            for (Component* c : e.components) {
                result.append(py::cast(c, py::return_value_policy::reference));
            }
            return result;
        })

        // Hierarchy
        .def("set_parent", &Entity::set_parent, py::arg("parent"))
        .def_property_readonly("parent", &Entity::parent, py::return_value_policy::reference)
        .def("children", &Entity::children)

        // Lifecycle
        .def("update", &Entity::update, py::arg("dt"))
        .def("on_added_to_scene", &Entity::on_added_to_scene, py::arg("scene"))
        .def("on_removed_from_scene", &Entity::on_removed_from_scene);

    // --- EntityRegistry ---
    py::class_<EntityRegistry>(m, "EntityRegistry")
        .def_static("instance", &EntityRegistry::instance, py::return_value_policy::reference)
        .def("get", &EntityRegistry::get, py::arg("uuid"),
             py::return_value_policy::reference)
        .def("get_by_pick_id", &EntityRegistry::get_by_pick_id, py::arg("pick_id"),
             py::return_value_policy::reference)
        .def("clear", &EntityRegistry::clear)
        .def_property_readonly("entity_count", &EntityRegistry::entity_count);

    // --- Native Components ---
    py::class_<CXXRotatorComponent, Component>(m, "CXXRotatorComponent")
        .def(py::init<>())
        .def_readwrite("speed", &CXXRotatorComponent::speed);
}
