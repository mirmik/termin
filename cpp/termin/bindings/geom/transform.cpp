#include "common.hpp"
#include "termin/entity/entity.hpp"
#include "../../../../core_c/include/tc_entity_pool_registry.h"

namespace termin {

// Helper to convert Python GeneralPose3 (with numpy arrays) to C++ GeneralPose3
static GeneralPose3 nb_pose_to_cpp(nb::object py_pose) {
    if (py_pose.is_none()) {
        return GeneralPose3::identity();
    }
    // Check if it's already a C++ GeneralPose3
    if (nb::isinstance<GeneralPose3>(py_pose)) {
        return nb::cast<GeneralPose3>(py_pose);
    }
    // Otherwise, extract ang, lin, scale from Python object
    Quat ang = Quat::identity();
    Vec3 lin = Vec3::zero();
    Vec3 scale{1.0, 1.0, 1.0};

    if (nb::hasattr(py_pose, "ang")) {
        nb::object ang_obj = py_pose.attr("ang");
        if (nb::isinstance<Quat>(ang_obj)) {
            ang = nb::cast<Quat>(ang_obj);
        } else {
            auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(ang_obj);
            double* ptr = arr.data();
            ang = Quat{ptr[0], ptr[1], ptr[2], ptr[3]};
        }
    }
    if (nb::hasattr(py_pose, "lin")) {
        nb::object lin_obj = py_pose.attr("lin");
        if (nb::isinstance<Vec3>(lin_obj)) {
            lin = nb::cast<Vec3>(lin_obj);
        } else {
            auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(lin_obj);
            double* ptr = arr.data();
            lin = Vec3{ptr[0], ptr[1], ptr[2]};
        }
    }
    if (nb::hasattr(py_pose, "scale")) {
        nb::object scale_obj = py_pose.attr("scale");
        if (nb::isinstance<Vec3>(scale_obj)) {
            scale = nb::cast<Vec3>(scale_obj);
        } else {
            auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(scale_obj);
            double* ptr = arr.data();
            scale = Vec3{ptr[0], ptr[1], ptr[2]};
        }
    }
    return GeneralPose3{ang, lin, scale};
}

void bind_transform(nb::module_& m) {
    // GeneralTransform3 - view into entity pool data (same as Entity, but transform-focused API)
    // NOTE: This binding depends on Entity which is in _entity_native.
    // It will be enabled when _entity_native is migrated to nanobind.
    nb::class_<GeneralTransform3>(m, "GeneralTransform3")
        // Default constructor - allocate entity in standalone pool (like Entity())
        .def("__init__", [](GeneralTransform3* self) {
            tc_entity_pool_handle pool_handle = Entity::standalone_pool_handle();
            tc_entity_pool* pool = tc_entity_pool_registry_get(pool_handle);
            tc_entity_id id = tc_entity_pool_alloc(pool, "transform");
            new (self) GeneralTransform3(pool_handle, id);
        })
        // Constructor with pose
        .def("__init__", [](GeneralTransform3* self, nb::object pose) {
            tc_entity_pool_handle pool_handle = Entity::standalone_pool_handle();
            tc_entity_pool* pool = tc_entity_pool_registry_get(pool_handle);
            tc_entity_id id = tc_entity_pool_alloc(pool, "transform");
            new (self) GeneralTransform3(pool_handle, id);
            self->set_local_pose(nb_pose_to_cpp(pose));
        }, nb::arg("pose"))

        // Check validity
        .def("valid", &GeneralTransform3::valid)
        .def("__bool__", &GeneralTransform3::valid)

        // Attributes
        .def_prop_ro("name",
            [](const GeneralTransform3& self) -> nb::object {
                const char* n = self.name();
                if (n) return nb::str(n);
                return nb::none();
            })
        .def_prop_ro("parent",
            [](const GeneralTransform3& self) -> nb::object {
                GeneralTransform3 p = self.parent();
                if (!p.valid()) return nb::none();
                return nb::cast(p);
            })
        .def_prop_ro("children",
            [](const GeneralTransform3& self) -> nb::list {
                nb::list result;
                size_t count = self.children_count();
                for (size_t i = 0; i < count; i++) {
                    GeneralTransform3 child = self.child_at(i);
                    if (child.valid()) {
                        result.append(nb::cast(child));
                    }
                }
                return result;
            })

        // Entity back-pointer
        .def_prop_ro("entity",
            [](const GeneralTransform3& self) -> nb::object {
                Entity e = self.entity();
                if (!e.valid()) return nb::none();
                return nb::cast(e);
            })

        // Pose access
        .def("local_pose", &GeneralTransform3::local_pose)
        .def("global_pose", &GeneralTransform3::global_pose)
        .def("set_local_pose", [](GeneralTransform3& self, nb::object pose) {
            self.set_local_pose(nb_pose_to_cpp(pose));
        })
        .def("set_global_pose", [](GeneralTransform3& self, nb::object pose) {
            self.set_global_pose(nb_pose_to_cpp(pose));
        })

        // Position/rotation access
        .def("local_position", &GeneralTransform3::local_position)
        .def("local_rotation", &GeneralTransform3::local_rotation)
        .def("local_scale", &GeneralTransform3::local_scale)
        .def("set_local_position", [](GeneralTransform3& self, const Vec3& pos) {
            self.set_local_position(pos);
        }, nb::arg("position"))
        .def("set_local_rotation", [](GeneralTransform3& self, const Quat& rot) {
            self.set_local_rotation(rot);
        }, nb::arg("rotation"))
        .def("set_local_scale", [](GeneralTransform3& self, const Vec3& scale) {
            self.set_local_scale(scale);
        }, nb::arg("scale"))

        // Global (world) position/rotation/scale - read-only properties
        .def_prop_ro("global_position", &GeneralTransform3::global_position)
        .def_prop_ro("global_rotation", &GeneralTransform3::global_rotation)
        .def_prop_ro("global_scale", &GeneralTransform3::global_scale)

        // Relocate (accepts Python GeneralPose3, C++ GeneralPose3, Python Pose3, or C++ Pose3)
        .def("relocate", [](GeneralTransform3& self, nb::object pose) {
            // Check if it's a C++ Pose3
            if (nb::isinstance<Pose3>(pose)) {
                self.relocate(nb::cast<Pose3>(pose));
            }
            // Check if it's a Python Pose3 (has ang and lin but no scale)
            else if (nb::hasattr(pose, "ang") && nb::hasattr(pose, "lin") && !nb::hasattr(pose, "scale")) {
                nb::object ang_obj = pose.attr("ang");
                nb::object lin_obj = pose.attr("lin");
                Quat ang = Quat::identity();
                Vec3 lin = Vec3::zero();
                if (nb::isinstance<Quat>(ang_obj)) {
                    ang = nb::cast<Quat>(ang_obj);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(ang_obj);
                    double* ptr = arr.data();
                    ang = Quat{ptr[0], ptr[1], ptr[2], ptr[3]};
                }
                if (nb::isinstance<Vec3>(lin_obj)) {
                    lin = nb::cast<Vec3>(lin_obj);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(lin_obj);
                    double* ptr = arr.data();
                    lin = Vec3{ptr[0], ptr[1], ptr[2]};
                }
                self.relocate(Pose3{ang, lin});
            } else {
                self.relocate(nb_pose_to_cpp(pose));
            }
        })
        .def("relocate_global", [](GeneralTransform3& self, nb::object pose) {
            // Check if it's a C++ Pose3
            if (nb::isinstance<Pose3>(pose)) {
                self.relocate_global(nb::cast<Pose3>(pose));
            }
            // Check if it's a Python Pose3 (has ang and lin but no scale)
            else if (nb::hasattr(pose, "ang") && nb::hasattr(pose, "lin") && !nb::hasattr(pose, "scale")) {
                nb::object ang_obj = pose.attr("ang");
                nb::object lin_obj = pose.attr("lin");
                Quat ang = Quat::identity();
                Vec3 lin = Vec3::zero();
                if (nb::isinstance<Quat>(ang_obj)) {
                    ang = nb::cast<Quat>(ang_obj);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(ang_obj);
                    double* ptr = arr.data();
                    ang = Quat{ptr[0], ptr[1], ptr[2], ptr[3]};
                }
                if (nb::isinstance<Vec3>(lin_obj)) {
                    lin = nb::cast<Vec3>(lin_obj);
                } else {
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(lin_obj);
                    double* ptr = arr.data();
                    lin = Vec3{ptr[0], ptr[1], ptr[2]};
                }
                self.relocate_global(Pose3{ang, lin});
            } else {
                self.relocate_global(nb_pose_to_cpp(pose));
            }
        })

        // Hierarchy
        .def("add_child", [](GeneralTransform3& self, GeneralTransform3 child) {
            // add_child is implemented as set_parent on the child
            child.set_parent(self);
        })
        .def("set_parent", [](GeneralTransform3& self, nb::object parent) {
            if (parent.is_none()) {
                self.unparent();
            } else {
                self.set_parent(nb::cast<GeneralTransform3>(parent));
            }
        }, nb::arg("parent").none())
        .def("_unparent", &GeneralTransform3::unparent)
        .def("unparent", &GeneralTransform3::unparent)
        .def("link", [](GeneralTransform3& self, GeneralTransform3 child) {
            // link is implemented as set_parent on the child
            child.set_parent(self);
        })

        // Transformations - return numpy arrays
        .def("transform_point", [](const GeneralTransform3& self, nb::ndarray<double, nb::c_contig, nb::device::cpu> point) {
            Vec3 p = numpy_to_vec3(point);
            Vec3 result = self.transform_point(p);
            return vec3_to_numpy(result);
        })
        .def("transform_point_inverse", [](const GeneralTransform3& self, nb::ndarray<double, nb::c_contig, nb::device::cpu> point) {
            Vec3 p = numpy_to_vec3(point);
            Vec3 result = self.transform_point_inverse(p);
            return vec3_to_numpy(result);
        })
        .def("transform_vector", [](const GeneralTransform3& self, nb::ndarray<double, nb::c_contig, nb::device::cpu> vec) {
            Vec3 v = numpy_to_vec3(vec);
            Vec3 result = self.transform_vector(v);
            return vec3_to_numpy(result);
        })
        .def("transform_vector_inverse", [](const GeneralTransform3& self, nb::ndarray<double, nb::c_contig, nb::device::cpu> vec) {
            Vec3 v = numpy_to_vec3(vec);
            Vec3 result = self.transform_vector_inverse(v);
            return vec3_to_numpy(result);
        })

        // Direction helpers - return numpy arrays
        .def("forward", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.forward(distance));
        }, nb::arg("distance") = 1.0)
        .def("backward", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.backward(distance));
        }, nb::arg("distance") = 1.0)
        .def("up", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.up(distance));
        }, nb::arg("distance") = 1.0)
        .def("down", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.down(distance));
        }, nb::arg("distance") = 1.0)
        .def("right", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.right(distance));
        }, nb::arg("distance") = 1.0)
        .def("left", [](const GeneralTransform3& self, double distance) {
            return vec3_to_numpy(self.left(distance));
        }, nb::arg("distance") = 1.0)

        // World matrix - return 4x4 numpy array (row-major for Python)
        // world_matrix returns column-major, transpose for numpy
        .def("world_matrix", [](const GeneralTransform3& self) {
            double* data = new double[16];
            double m[16];
            self.world_matrix(m);
            // Transpose: column-major to row-major
            for (int row = 0; row < 4; row++)
                for (int col = 0; col < 4; col++)
                    data[row * 4 + col] = m[col * 4 + row];
            nb::capsule owner(data, [](void* ptr) noexcept { delete[] static_cast<double*>(ptr); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, 2, shape, owner);
        })

        .def("__repr__", [](const GeneralTransform3& self) {
            const char* n = self.name();
            std::string name_str = n ? n : "<unnamed>";
            return "GeneralTransform3(" + name_str + ")";
        });
}

} // namespace termin
