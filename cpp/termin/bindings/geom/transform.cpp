#include "common.hpp"

namespace termin {

// Helper to convert Python GeneralPose3 (with numpy arrays) to C++ GeneralPose3
static GeneralPose3 py_pose_to_cpp(py::object py_pose) {
    if (py_pose.is_none()) {
        return GeneralPose3::identity();
    }
    // Check if it's already a C++ GeneralPose3
    if (py::isinstance<GeneralPose3>(py_pose)) {
        return py_pose.cast<GeneralPose3>();
    }
    // Otherwise, extract ang, lin, scale from Python object
    Quat ang = Quat::identity();
    Vec3 lin = Vec3::zero();
    Vec3 scale{1.0, 1.0, 1.0};

    if (py::hasattr(py_pose, "ang")) {
        py::object ang_obj = py_pose.attr("ang");
        if (py::isinstance<Quat>(ang_obj)) {
            ang = ang_obj.cast<Quat>();
        } else {
            auto arr = ang_obj.cast<py::array_t<double>>();
            auto buf = arr.unchecked<1>();
            ang = Quat{buf(0), buf(1), buf(2), buf(3)};
        }
    }
    if (py::hasattr(py_pose, "lin")) {
        py::object lin_obj = py_pose.attr("lin");
        if (py::isinstance<Vec3>(lin_obj)) {
            lin = lin_obj.cast<Vec3>();
        } else {
            auto arr = lin_obj.cast<py::array_t<double>>();
            auto buf = arr.unchecked<1>();
            lin = Vec3{buf(0), buf(1), buf(2)};
        }
    }
    if (py::hasattr(py_pose, "scale")) {
        py::object scale_obj = py_pose.attr("scale");
        if (py::isinstance<Vec3>(scale_obj)) {
            scale = scale_obj.cast<Vec3>();
        } else {
            auto arr = scale_obj.cast<py::array_t<double>>();
            auto buf = arr.unchecked<1>();
            scale = Vec3{buf(0), buf(1), buf(2)};
        }
    }
    return GeneralPose3{ang, lin, scale};
}

void bind_transform(py::module_& m) {
    // GeneralTransform3
    py::class_<GeneralTransform3>(m, "GeneralTransform3", py::dynamic_attr())
        .def(py::init<>())
        .def(py::init<const GeneralPose3&, const std::string&>(),
             py::arg("local_pose") = GeneralPose3::identity(),
             py::arg("name") = "")
        // Constructor accepting any Python object with ang/lin/scale (including Python GeneralPose3)
        .def(py::init([](py::object local_pose, GeneralTransform3* parent, const std::string& name) {
            GeneralPose3 pose = py_pose_to_cpp(local_pose);
            auto* t = new GeneralTransform3(pose, name);
            if (parent) {
                parent->add_child(t);
            }
            return t;
        }), py::arg("local_pose") = py::none(), py::arg("parent") = nullptr, py::arg("name") = "",
            py::return_value_policy::take_ownership)

        // Attributes
        .def_readwrite("name", &GeneralTransform3::name)
        .def_property_readonly("parent",
            [](GeneralTransform3& self) { return self.parent; },
            py::return_value_policy::reference)
        .def_property_readonly("children",
            [](GeneralTransform3& self) -> py::list {
                py::list result;
                for (GeneralTransform3* child : self.children) {
                    py::object py_child = py::cast(child, py::return_value_policy::reference);
                    // If child has C++ entity pointer but no _entity attr, try to set it
                    if (child->entity != nullptr && !py::hasattr(py_child, "_entity")) {
                        // Try to find the entity in Python - use capsule workaround
                        // Store the pointer as a capsule for later resolution
                        py_child.attr("_entity_ptr") = py::capsule(child->entity, "Entity*");
                    }
                    result.append(py_child);
                }
                return result;
            })

        // entity back-pointer
        // C++ code uses self.entity field directly
        // Python getter uses _entity attribute (set by entity_bindings), with fallback to C++ field
        .def_property("entity",
            [](GeneralTransform3& self) -> py::object {
                py::object py_self = py::cast(&self, py::return_value_policy::reference);
                // First check _entity Python attribute
                if (py::hasattr(py_self, "_entity")) {
                    return py_self.attr("_entity");
                }
                // Fallback: check C++ entity pointer and use EntityRegistry to find Python object
                if (self.entity != nullptr) {
                    try {
                        // Import entity module to get EntityRegistry
                        py::module_ entity_module = py::module_::import("termin._native.entity");
                        py::object registry = entity_module.attr("EntityRegistry").attr("instance")();
                        // Get entity by transform pointer
                        py::object entity = registry.attr("get_by_transform")(py::cast(&self, py::return_value_policy::reference));
                        if (!entity.is_none()) {
                            // Cache it for next access
                            py_self.attr("_entity") = entity;
                            return entity;
                        }
                    } catch (...) {
                        // Module not loaded yet, ignore
                    }
                }
                return py::none();
            },
            [](GeneralTransform3& self, py::object entity) {
                py::object py_self = py::cast(&self, py::return_value_policy::reference);
                py_self.attr("_entity") = entity;
            })

        // Pose access
        .def("local_pose", &GeneralTransform3::local_pose, py::return_value_policy::reference)
        .def("global_pose", &GeneralTransform3::global_pose, py::return_value_policy::reference)
        .def("set_local_pose", [](GeneralTransform3& self, py::object pose) {
            self.set_local_pose(py_pose_to_cpp(pose));
        })
        .def("set_global_pose", [](GeneralTransform3& self, py::object pose) {
            self.set_global_pose(py_pose_to_cpp(pose));
        })

        // Relocate (accepts Python GeneralPose3, C++ GeneralPose3, Python Pose3, or C++ Pose3)
        .def("relocate", [](GeneralTransform3& self, py::object pose) {
            // Check if it's a C++ Pose3
            if (py::isinstance<Pose3>(pose)) {
                self.relocate(pose.cast<Pose3>());
            }
            // Check if it's a Python Pose3 (has ang and lin but no scale)
            else if (py::hasattr(pose, "ang") && py::hasattr(pose, "lin") && !py::hasattr(pose, "scale")) {
                py::object ang_obj = pose.attr("ang");
                py::object lin_obj = pose.attr("lin");
                Quat ang = Quat::identity();
                Vec3 lin = Vec3::zero();
                if (py::isinstance<Quat>(ang_obj)) {
                    ang = ang_obj.cast<Quat>();
                } else {
                    auto arr = ang_obj.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    ang = Quat{buf(0), buf(1), buf(2), buf(3)};
                }
                if (py::isinstance<Vec3>(lin_obj)) {
                    lin = lin_obj.cast<Vec3>();
                } else {
                    auto arr = lin_obj.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    lin = Vec3{buf(0), buf(1), buf(2)};
                }
                self.relocate(Pose3{ang, lin});
            } else {
                self.relocate(py_pose_to_cpp(pose));
            }
        })
        .def("relocate_global", [](GeneralTransform3& self, py::object pose) {
            // Check if it's a C++ Pose3
            if (py::isinstance<Pose3>(pose)) {
                self.relocate_global(pose.cast<Pose3>());
            }
            // Check if it's a Python Pose3 (has ang and lin but no scale)
            else if (py::hasattr(pose, "ang") && py::hasattr(pose, "lin") && !py::hasattr(pose, "scale")) {
                py::object ang_obj = pose.attr("ang");
                py::object lin_obj = pose.attr("lin");
                Quat ang = Quat::identity();
                Vec3 lin = Vec3::zero();
                if (py::isinstance<Quat>(ang_obj)) {
                    ang = ang_obj.cast<Quat>();
                } else {
                    auto arr = ang_obj.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    ang = Quat{buf(0), buf(1), buf(2), buf(3)};
                }
                if (py::isinstance<Vec3>(lin_obj)) {
                    lin = lin_obj.cast<Vec3>();
                } else {
                    auto arr = lin_obj.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    lin = Vec3{buf(0), buf(1), buf(2)};
                }
                self.relocate_global(Pose3{ang, lin});
            } else {
                self.relocate_global(py_pose_to_cpp(pose));
            }
        })

        // Hierarchy
        .def("add_child", &GeneralTransform3::add_child, py::keep_alive<1, 2>())
        .def("set_parent", &GeneralTransform3::set_parent, py::keep_alive<2, 1>())
        .def("_unparent", &GeneralTransform3::unparent)
        .def("unparent", &GeneralTransform3::unparent)
        .def("link", &GeneralTransform3::add_child, py::keep_alive<1, 2>())  // alias

        // Dirty tracking
        .def("is_dirty", &GeneralTransform3::is_dirty)
        .def("_mark_dirty", &GeneralTransform3::_mark_dirty)
        .def("increment_version", [](GeneralTransform3&, uint32_t v) {
            return GeneralTransform3::increment_version(v);
        })

        // Version attributes
        .def_readwrite("_version_for_walking_to_proximal", &GeneralTransform3::_version_for_walking_to_proximal)
        .def_readwrite("_version_for_walking_to_distal", &GeneralTransform3::_version_for_walking_to_distal)
        .def_readwrite("_version_only_my", &GeneralTransform3::_version_only_my)

        // Transformations - return numpy arrays
        .def("transform_point", [](const GeneralTransform3& self, py::array_t<double> point) {
            Vec3 p = numpy_to_vec3(point);
            Vec3 result = self.transform_point(p);
            return vec3_to_numpy(result);
        })
        .def("transform_point_inverse", [](const GeneralTransform3& self, py::array_t<double> point) {
            Vec3 p = numpy_to_vec3(point);
            Vec3 result = self.transform_point_inverse(p);
            return vec3_to_numpy(result);
        })
        .def("transform_vector", [](const GeneralTransform3& self, py::array_t<double> vec) {
            Vec3 v = numpy_to_vec3(vec);
            Vec3 result = self.transform_vector(v);
            return vec3_to_numpy(result);
        })
        .def("transform_vector_inverse", [](const GeneralTransform3& self, py::array_t<double> vec) {
            Vec3 v = numpy_to_vec3(vec);
            Vec3 result = self.transform_vector_inverse(v);
            return vec3_to_numpy(result);
        })

        // Direction helpers - return numpy arrays
        .def("forward", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.forward(distance));
        }, py::arg("distance") = 1.0)
        .def("backward", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.backward(distance));
        }, py::arg("distance") = 1.0)
        .def("up", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.up(distance));
        }, py::arg("distance") = 1.0)
        .def("down", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.down(distance));
        }, py::arg("distance") = 1.0)
        .def("right", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.right(distance));
        }, py::arg("distance") = 1.0)
        .def("left", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.left(distance));
        }, py::arg("distance") = 1.0)

        // World matrix - return 4x4 numpy array
        .def("world_matrix", [](const GeneralTransform3& self) {
            auto result = make_mat(4, 4);
            auto buf = result.mutable_unchecked<2>();
            double m[16];
            self.world_matrix(m);
            for (int i = 0; i < 4; i++)
                for (int j = 0; j < 4; j++)
                    buf(i, j) = m[i * 4 + j];
            return result;
        })

        .def("__repr__", [](const GeneralTransform3& self) {
            return "GeneralTransform3(" + self.name + ", local_pose=GeneralPose3(...))";
        });

    // TransformHandle
    py::class_<TransformHandle>(m, "TransformHandle")
        .def(py::init<>())
        .def_readonly("index", &TransformHandle::index)
        .def_readonly("generation", &TransformHandle::generation)
        .def("is_null", &TransformHandle::is_null)
        .def("__bool__", &TransformHandle::operator bool)
        .def("__eq__", &TransformHandle::operator==)
        .def("__ne__", &TransformHandle::operator!=)
        .def("__repr__", [](const TransformHandle& h) {
            if (h.is_null()) return std::string("TransformHandle(null)");
            return "TransformHandle(index=" + std::to_string(h.index) +
                   ", generation=" + std::to_string(h.generation) + ")";
        });

    // GeneralTransform3Pool
    py::class_<GeneralTransform3Pool>(m, "GeneralTransform3Pool")
        .def(py::init<size_t>(), py::arg("initial_capacity") = 256)

        .def("create", &GeneralTransform3Pool::create,
             py::arg("local_pose") = GeneralPose3::identity(),
             py::arg("name") = "")
        .def("destroy", &GeneralTransform3Pool::destroy)
        .def("destroy_by_ptr", &GeneralTransform3Pool::destroy_by_ptr)

        .def("get", py::overload_cast<TransformHandle>(&GeneralTransform3Pool::get),
             py::return_value_policy::reference)
        .def("is_valid", &GeneralTransform3Pool::is_valid)
        .def("is_valid_ptr", &GeneralTransform3Pool::is_valid_ptr)
        .def("handle_from_ptr", &GeneralTransform3Pool::handle_from_ptr)

        .def("__len__", &GeneralTransform3Pool::size)
        .def_property_readonly("size", &GeneralTransform3Pool::size)
        .def_property_readonly("capacity", &GeneralTransform3Pool::capacity)

        .def("__repr__", [](const GeneralTransform3Pool& pool) {
            return "GeneralTransform3Pool(size=" + std::to_string(pool.size()) +
                   ", capacity=" + std::to_string(pool.capacity()) + ")";
        });
}

} // namespace termin
