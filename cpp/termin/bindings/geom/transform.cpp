#include "common.hpp"
#include "termin/entity/entity.hpp"

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
    // GeneralTransform3 - thin wrapper around tc_transform*
    py::class_<GeneralTransform3>(m, "GeneralTransform3", py::dynamic_attr())
        // Default constructor - null transform
        .def(py::init<>())

        // Check validity
        .def("valid", &GeneralTransform3::valid)
        .def("__bool__", &GeneralTransform3::valid)

        // Attributes
        .def_property_readonly("name",
            [](const GeneralTransform3& self) -> py::object {
                const char* n = self.name();
                if (n) return py::str(n);
                return py::none();
            })
        .def_property_readonly("parent",
            [](const GeneralTransform3& self) -> py::object {
                GeneralTransform3 p = self.parent();
                if (!p.valid()) return py::none();
                return py::cast(p);
            })
        .def_property_readonly("children",
            [](const GeneralTransform3& self) -> py::list {
                py::list result;
                size_t count = self.children_count();
                for (size_t i = 0; i < count; i++) {
                    GeneralTransform3 child = self.child_at(i);
                    if (child.valid()) {
                        result.append(py::cast(child));
                    }
                }
                return result;
            })

        // Entity back-pointer
        .def_property_readonly("entity",
            [](const GeneralTransform3& self) -> py::object {
                Entity e = self.entity();
                if (!e.valid()) return py::none();
                return py::cast(e);
            })

        // Pose access
        .def("local_pose", &GeneralTransform3::local_pose)
        .def("global_pose", &GeneralTransform3::global_pose)
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
        .def("add_child", [](GeneralTransform3& self, GeneralTransform3 child) {
            // add_child is implemented as set_parent on the child
            child.set_parent(self);
        })
        .def("set_parent", [](GeneralTransform3& self, py::object parent) {
            if (parent.is_none()) {
                self.unparent();
            } else {
                self.set_parent(parent.cast<GeneralTransform3>());
            }
        })
        .def("_unparent", &GeneralTransform3::unparent)
        .def("unparent", &GeneralTransform3::unparent)
        .def("link", [](GeneralTransform3& self, GeneralTransform3 child) {
            // link is implemented as set_parent on the child
            child.set_parent(self);
        })

        // Dirty tracking - removed, pool handles this internally
        // .def("is_dirty", ...) - not exposed in pool API
        // .def_property_readonly("version", ...) - not exposed in pool API

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
            const char* n = self.name();
            std::string name_str = n ? n : "<unnamed>";
            return "GeneralTransform3(" + name_str + ")";
        });
}

} // namespace termin
