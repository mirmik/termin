// SkeletonInstance bindings only.
// Bone and SkeletonData are in _skeleton_native module.

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/array.h>

#include "termin/skeleton/bone.hpp"
#include "termin/skeleton/skeleton_data.hpp"
#include "termin/skeleton/skeleton_instance.hpp"
#include "termin/entity/entity.hpp"
#include "termin/assets/handles.hpp"
#include "../../core_c/include/tc_kind.hpp"
#include "skeleton_bindings.hpp"

namespace nb = nanobind;
using namespace termin;

// Helper: numpy (3,) -> std::array<double, 3>
static std::array<double, 3> numpy_to_vec3(nb::object obj) {
    try {
        auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(obj);
        const double* data = arr.data();
        return {data[0], data[1], data[2]};
    } catch (...) {
        nb::list seq = nb::cast<nb::list>(obj);
        return {nb::cast<double>(seq[0]), nb::cast<double>(seq[1]), nb::cast<double>(seq[2])};
    }
}

// Helper: numpy (4,) -> std::array<double, 4>
static std::array<double, 4> numpy_to_vec4(nb::object obj) {
    try {
        auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(obj);
        const double* data = arr.data();
        return {data[0], data[1], data[2], data[3]};
    } catch (...) {
        nb::list seq = nb::cast<nb::list>(obj);
        return {nb::cast<double>(seq[0]), nb::cast<double>(seq[1]),
                nb::cast<double>(seq[2]), nb::cast<double>(seq[3])};
    }
}

namespace termin {

void bind_skeleton(nb::module_& m) {
    // Note: Bone and SkeletonData are now in _skeleton_native module.
    // This module only binds SkeletonInstance which depends on Entity.

    // Register skeleton_handle kind for InspectRegistry
    tc::register_cpp_handle_kind<SkeletonHandle>("skeleton_handle");

    // SkeletonInstance - now uses Entity values instead of pointers
    nb::class_<SkeletonInstance>(m, "SkeletonInstance")
        .def(nb::init<>())
        .def_prop_rw("skeleton_data",
            &SkeletonInstance::skeleton_data,
            &SkeletonInstance::set_skeleton_data,
            nb::rv_policy::reference)
        .def_prop_rw("bone_entities",
            [](const SkeletonInstance& si) {
                nb::list result;
                for (const Entity& e : si.bone_entities()) {
                    if (e.valid()) {
                        result.append(nb::cast(e));
                    } else {
                        result.append(nb::none());
                    }
                }
                return result;
            },
            [](SkeletonInstance& si, nb::list entities) {
                std::vector<Entity> vec;
                for (auto item : entities) {
                    if (!item.is_none()) {
                        vec.push_back(nb::cast<Entity>(item));
                    }
                }
                si.set_bone_entities(std::move(vec));
            })
        .def_prop_rw("skeleton_root",
            [](const SkeletonInstance& si) -> nb::object {
                Entity root = si.skeleton_root();
                if (root.valid()) return nb::cast(root);
                return nb::none();
            },
            [](SkeletonInstance& si, nb::object root_obj) {
                if (root_obj.is_none()) {
                    si.set_skeleton_root(Entity());
                } else {
                    si.set_skeleton_root(nb::cast<Entity>(root_obj));
                }
            })
        .def("get_bone_entity", [](const SkeletonInstance& si, int index) -> nb::object {
            Entity e = si.get_bone_entity(index);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("bone_index"))
        .def("get_bone_entity_by_name", [](const SkeletonInstance& si, const std::string& name) -> nb::object {
            Entity e = si.get_bone_entity_by_name(name);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("bone_name"))
        .def("set_bone_transform", [](SkeletonInstance& si,
                int bone_index,
                nb::object translation,
                nb::object rotation,
                nb::object scale) {
            std::array<double, 3> t_arr;
            std::array<double, 4> r_arr;
            std::array<double, 3> s_arr;
            const double* t_ptr = nullptr;
            const double* r_ptr = nullptr;
            const double* s_ptr = nullptr;

            if (!translation.is_none()) {
                t_arr = ::numpy_to_vec3(translation);
                t_ptr = t_arr.data();
            }
            if (!rotation.is_none()) {
                r_arr = numpy_to_vec4(rotation);
                r_ptr = r_arr.data();
            }
            if (!scale.is_none()) {
                if (nb::isinstance<nb::float_>(scale) || nb::isinstance<nb::int_>(scale)) {
                    double s = nb::cast<double>(scale);
                    s_arr = {s, s, s};
                } else {
                    s_arr = ::numpy_to_vec3(scale);
                }
                s_ptr = s_arr.data();
            }
            si.set_bone_transform(bone_index, t_ptr, r_ptr, s_ptr);
        }, nb::arg("bone_index"),
           nb::arg("translation") = nb::none(),
           nb::arg("rotation") = nb::none(),
           nb::arg("scale") = nb::none())
        .def("set_bone_transform_by_name", [](SkeletonInstance& si,
                const std::string& bone_name,
                nb::object translation,
                nb::object rotation,
                nb::object scale) {
            std::array<double, 3> t_arr;
            std::array<double, 4> r_arr;
            std::array<double, 3> s_arr;
            const double* t_ptr = nullptr;
            const double* r_ptr = nullptr;
            const double* s_ptr = nullptr;

            if (!translation.is_none()) {
                t_arr = ::numpy_to_vec3(translation);
                t_ptr = t_arr.data();
            }
            if (!rotation.is_none()) {
                r_arr = numpy_to_vec4(rotation);
                r_ptr = r_arr.data();
            }
            if (!scale.is_none()) {
                if (nb::isinstance<nb::float_>(scale) || nb::isinstance<nb::int_>(scale)) {
                    double s = nb::cast<double>(scale);
                    s_arr = {s, s, s};
                } else {
                    s_arr = ::numpy_to_vec3(scale);
                }
                s_ptr = s_arr.data();
            }
            si.set_bone_transform_by_name(bone_name, t_ptr, r_ptr, s_ptr);
        }, nb::arg("bone_name"),
           nb::arg("translation") = nb::none(),
           nb::arg("rotation") = nb::none(),
           nb::arg("scale") = nb::none())
        .def("update", &SkeletonInstance::update)
        .def("get_bone_matrices", [](SkeletonInstance& si) {
            si.update();
            int n = si.bone_count();
            float* buf = new float[n * 16];
            for (int i = 0; i < n; ++i) {
                const Mat44& m = si.get_bone_matrix(i);
                // Convert column-major Mat44 to row-major numpy array
                for (int row = 0; row < 4; ++row) {
                    for (int col = 0; col < 4; ++col) {
                        buf[i * 16 + row * 4 + col] = static_cast<float>(m(col, row));
                    }
                }
            }
            nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<float*>(p); });
            size_t shape[3] = {static_cast<size_t>(n), 4, 4};
            return nb::ndarray<nb::numpy, float>(buf, 3, shape, owner);
        })
        .def("bone_count", &SkeletonInstance::bone_count)
        .def("get_bone_world_matrix", [](const SkeletonInstance& si, int bone_index) {
            Mat44 m = si.get_bone_world_matrix(bone_index);
            float* buf = new float[16];
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    buf[row * 4 + col] = static_cast<float>(m(col, row));
                }
            }
            nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<float*>(p); });
            size_t shape[2] = {4, 4};
            return nb::ndarray<nb::numpy, float>(buf, 2, shape, owner);
        }, nb::arg("bone_index"))
        .def("__repr__", [](const SkeletonInstance& si) {
            bool has_entities = !si.bone_entities().empty();
            return "<SkeletonInstance bones=" + std::to_string(si.bone_count()) +
                   " has_entities=" + (has_entities ? "True" : "False") + ">";
        });
}

} // namespace termin
