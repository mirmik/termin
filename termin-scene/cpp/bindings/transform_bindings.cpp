#include <termin/bindings/transform_bindings.hpp>
#include <termin/bindings/entity_helpers.hpp>

#include <termin/entity/entity.hpp>
#include <termin/geom/general_transform3.hpp>
#include <termin/geom/general_pose3.hpp>
#include <termin/geom/pose3.hpp>
#include "core/tc_entity_pool_registry.h"

namespace nb = nanobind;

namespace termin {

void bind_transform(nb::module_& m) {
    nb::class_<GeneralTransform3>(m, "GeneralTransform3")
        .def("__init__", [](GeneralTransform3* self) {
            tc_entity_pool_handle pool_handle = get_standalone_pool_handle();
            tc_entity_pool* pool = tc_entity_pool_registry_get(pool_handle);
            tc_entity_id id = tc_entity_pool_alloc(pool, "transform");
            new (self) GeneralTransform3(pool_handle, id);
        })
        .def("__init__", [](GeneralTransform3* self, const GeneralPose3& pose) {
            tc_entity_pool_handle pool_handle = get_standalone_pool_handle();
            tc_entity_pool* pool = tc_entity_pool_registry_get(pool_handle);
            tc_entity_id id = tc_entity_pool_alloc(pool, "transform");
            new (self) GeneralTransform3(pool_handle, id);
            self->set_local_pose(pose);
        }, nb::arg("pose"))
        .def("valid", &GeneralTransform3::valid)
        .def("__bool__", &GeneralTransform3::valid)
        .def_prop_ro("name", [](const GeneralTransform3& self) -> nb::object {
            const char* n = self.name();
            if (n) return nb::str(n);
            return nb::none();
        })
        .def_prop_ro("parent", [](const GeneralTransform3& self) -> nb::object {
            GeneralTransform3 p = self.parent();
            if (!p.valid()) return nb::none();
            return nb::cast(p);
        })
        .def_prop_ro("children", [](const GeneralTransform3& self) -> nb::list {
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
        .def_prop_ro("entity", [](const GeneralTransform3& self) -> nb::object {
            Entity e = self.entity();
            if (!e.valid()) return nb::none();
            return nb::cast(e);
        })
        .def("local_pose", &GeneralTransform3::local_pose)
        .def("global_pose", &GeneralTransform3::global_pose)
        .def("set_local_pose", [](GeneralTransform3& self, const GeneralPose3& pose) {
            self.set_local_pose(pose);
        })
        .def("set_global_pose", [](GeneralTransform3& self, const GeneralPose3& pose) {
            self.set_global_pose(pose);
        })
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
        .def("set_local_scale", [](GeneralTransform3& self, float x, float y, float z) {
            self.set_local_scale(Vec3(x, y, z));
        }, nb::arg("x"), nb::arg("y"), nb::arg("z"))
        .def_prop_ro("global_position", &GeneralTransform3::global_position)
        .def_prop_ro("global_rotation", &GeneralTransform3::global_rotation)
        .def_prop_ro("global_scale", &GeneralTransform3::global_scale)
        .def("relocate", [](GeneralTransform3& self, const Pose3& pose) {
            self.relocate(pose);
        })
        .def("relocate", [](GeneralTransform3& self, const GeneralPose3& pose) {
            self.relocate(pose);
        })
        .def("relocate_global", [](GeneralTransform3& self, const Pose3& pose) {
            self.relocate_global(pose);
        })
        .def("relocate_global", [](GeneralTransform3& self, const GeneralPose3& pose) {
            self.relocate_global(pose);
        })
        .def("add_child", [](GeneralTransform3& self, GeneralTransform3 child) {
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
            child.set_parent(self);
        })
        .def("transform_point", [](const GeneralTransform3& self, const Vec3& point) {
            return self.transform_point(point);
        })
        .def("transform_point_inverse", [](const GeneralTransform3& self, const Vec3& point) {
            return self.transform_point_inverse(point);
        })
        .def("transform_vector", [](const GeneralTransform3& self, const Vec3& vec) {
            return self.transform_vector(vec);
        })
        .def("transform_vector_inverse", [](const GeneralTransform3& self, const Vec3& vec) {
            return self.transform_vector_inverse(vec);
        })
        .def("transform_direction", [](const GeneralTransform3& self, const Vec3& vec) {
            return self.transform_direction(vec);
        })
        .def("transform_direction_inverse", [](const GeneralTransform3& self, const Vec3& vec) {
            return self.transform_direction_inverse(vec);
        })
        .def("forward", [](const GeneralTransform3& self, double distance) {
            return self.forward(distance);
        }, nb::arg("distance") = 1.0)
        .def("backward", [](const GeneralTransform3& self, double distance) {
            return self.backward(distance);
        }, nb::arg("distance") = 1.0)
        .def("up", [](const GeneralTransform3& self, double distance) {
            return self.up(distance);
        }, nb::arg("distance") = 1.0)
        .def("down", [](const GeneralTransform3& self, double distance) {
            return self.down(distance);
        }, nb::arg("distance") = 1.0)
        .def("right", [](const GeneralTransform3& self, double distance) {
            return self.right(distance);
        }, nb::arg("distance") = 1.0)
        .def("left", [](const GeneralTransform3& self, double distance) {
            return self.left(distance);
        }, nb::arg("distance") = 1.0)
        .def("world_matrix", [](const GeneralTransform3& self) {
            double data[16];
            double m44[16];
            self.world_matrix(m44);
            for (int row = 0; row < 4; row++) {
                for (int col = 0; col < 4; col++) {
                    data[row * 4 + col] = m44[col * 4 + row];
                }
            }
            return mat44_row_tuple(data);
        })
        .def("__repr__", [](const GeneralTransform3& self) {
            const char* n = self.name();
            std::string name_str = n ? n : "<unnamed>";
            return "GeneralTransform3(" + name_str + ")";
        });
}

} // namespace termin
