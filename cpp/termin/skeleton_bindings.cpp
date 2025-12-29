// SkeletonInstance bindings only.
// Bone and SkeletonData are in _skeleton_native module.

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "termin/skeleton/bone.hpp"
#include "termin/skeleton/skeleton_data.hpp"
#include "termin/skeleton/skeleton_instance.hpp"
#include "termin/entity/entity.hpp"
#include "termin/assets/handles.hpp"
#include "../../core_c/include/tc_kind.hpp"

namespace py = pybind11;
using namespace termin;

// Helper: numpy (3,) -> std::array<double, 3>
static std::array<double, 3> numpy_to_vec3(py::object obj) {
    auto arr = py::array_t<double>::ensure(obj);
    if (arr && arr.size() >= 3) {
        auto buf = arr.unchecked<1>();
        return {buf(0), buf(1), buf(2)};
    }
    auto seq = obj.cast<py::sequence>();
    return {seq[0].cast<double>(), seq[1].cast<double>(), seq[2].cast<double>()};
}

// Helper: numpy (4,) -> std::array<double, 4>
static std::array<double, 4> numpy_to_vec4(py::object obj) {
    auto arr = py::array_t<double>::ensure(obj);
    if (arr && arr.size() >= 4) {
        auto buf = arr.unchecked<1>();
        return {buf(0), buf(1), buf(2), buf(3)};
    }
    auto seq = obj.cast<py::sequence>();
    return {seq[0].cast<double>(), seq[1].cast<double>(),
            seq[2].cast<double>(), seq[3].cast<double>()};
}

namespace termin {

void bind_skeleton(py::module_& m) {
    // Note: Bone and SkeletonData are now in _skeleton_native module.
    // This module only binds SkeletonInstance which depends on Entity.

    // Register skeleton_handle kind for InspectRegistry
    tc::register_cpp_handle_kind<SkeletonHandle>("skeleton_handle");

    // SkeletonInstance - now uses Entity values instead of pointers
    py::class_<SkeletonInstance>(m, "SkeletonInstance")
        .def(py::init<>())
        .def_property("skeleton_data",
            &SkeletonInstance::skeleton_data,
            &SkeletonInstance::set_skeleton_data,
            py::return_value_policy::reference)
        .def_property("bone_entities",
            [](const SkeletonInstance& si) {
                py::list result;
                for (const Entity& e : si.bone_entities()) {
                    if (e.valid()) {
                        result.append(py::cast(e));
                    } else {
                        result.append(py::none());
                    }
                }
                return result;
            },
            [](SkeletonInstance& si, py::list entities) {
                std::vector<Entity> vec;
                for (auto item : entities) {
                    if (!item.is_none()) {
                        vec.push_back(item.cast<Entity>());
                    }
                }
                si.set_bone_entities(std::move(vec));
            })
        .def_property("skeleton_root",
            [](const SkeletonInstance& si) -> py::object {
                Entity root = si.skeleton_root();
                if (root.valid()) return py::cast(root);
                return py::none();
            },
            [](SkeletonInstance& si, py::object root_obj) {
                if (root_obj.is_none()) {
                    si.set_skeleton_root(Entity());
                } else {
                    si.set_skeleton_root(root_obj.cast<Entity>());
                }
            })
        .def("get_bone_entity", [](const SkeletonInstance& si, int index) -> py::object {
            Entity e = si.get_bone_entity(index);
            if (e.valid()) return py::cast(e);
            return py::none();
        }, py::arg("bone_index"))
        .def("get_bone_entity_by_name", [](const SkeletonInstance& si, const std::string& name) -> py::object {
            Entity e = si.get_bone_entity_by_name(name);
            if (e.valid()) return py::cast(e);
            return py::none();
        }, py::arg("bone_name"))
        .def("set_bone_transform_by_name", [](SkeletonInstance& si,
                const std::string& bone_name,
                py::object translation,
                py::object rotation,
                py::object scale) {
            std::array<double, 3> t_arr;
            std::array<double, 4> r_arr;
            std::array<double, 3> s_arr;
            const double* t_ptr = nullptr;
            const double* r_ptr = nullptr;
            const double* s_ptr = nullptr;

            if (!translation.is_none()) {
                t_arr = numpy_to_vec3(translation);
                t_ptr = t_arr.data();
            }
            if (!rotation.is_none()) {
                r_arr = numpy_to_vec4(rotation);
                r_ptr = r_arr.data();
            }
            if (!scale.is_none()) {
                // Handle both scalar and vec3 scale
                if (py::isinstance<py::float_>(scale) || py::isinstance<py::int_>(scale)) {
                    double s = scale.cast<double>();
                    s_arr = {s, s, s};
                } else {
                    s_arr = numpy_to_vec3(scale);
                }
                s_ptr = s_arr.data();
            }
            si.set_bone_transform_by_name(bone_name, t_ptr, r_ptr, s_ptr);
        }, py::arg("bone_name"),
           py::arg("translation") = py::none(),
           py::arg("rotation") = py::none(),
           py::arg("scale") = py::none())
        .def("update", &SkeletonInstance::update)
        .def("get_bone_matrices", [](SkeletonInstance& si) {
            si.update();
            int n = si.bone_count();
            auto result = py::array_t<float>({n, 4, 4});
            auto buf = result.mutable_unchecked<3>();
            for (int i = 0; i < n; ++i) {
                const Mat44& m = si.get_bone_matrix(i);
                // Convert column-major Mat44 to row-major numpy array
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        buf(i, row, col) = static_cast<float>(m(col, row));
                    }
                }
            }
            return result;
        })
        .def("bone_count", &SkeletonInstance::bone_count)
        .def("get_bone_world_matrix", [](const SkeletonInstance& si, int bone_index) {
            Mat44 m = si.get_bone_world_matrix(bone_index);
            auto result = py::array_t<float>({4, 4});
            auto buf = result.mutable_unchecked<2>();
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    buf(row, col) = static_cast<float>(m(col, row));
                }
            }
            return result;
        }, py::arg("bone_index"))
        .def("__repr__", [](const SkeletonInstance& si) {
            bool has_entities = !si.bone_entities().empty();
            return "<SkeletonInstance bones=" + std::to_string(si.bone_count()) +
                   " has_entities=" + (has_entities ? "True" : "False") + ">";
        });
}

} // namespace termin
