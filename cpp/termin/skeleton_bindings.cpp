#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "termin/skeleton/bone.hpp"
#include "termin/skeleton/skeleton_data.hpp"
#include "termin/skeleton/skeleton_instance.hpp"
#include "termin/entity/entity.hpp"

namespace py = pybind11;
using namespace termin;

// Helper: numpy (4,4) -> std::array<double, 16>
static std::array<double, 16> numpy_to_mat4(py::array_t<double> arr) {
    auto buf = arr.unchecked<2>();
    std::array<double, 16> result;
    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
            result[i * 4 + j] = buf(i, j);
        }
    }
    return result;
}

// Helper: std::array<double, 16> -> numpy (4,4)
static py::array_t<double> mat4_to_numpy(const std::array<double, 16>& m) {
    auto result = py::array_t<double>({4, 4});
    auto buf = result.mutable_unchecked<2>();
    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
            buf(i, j) = m[i * 4 + j];
        }
    }
    return result;
}

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

// Helper: std::array<double, 3> -> numpy (3,)
static py::array_t<double> vec3_to_numpy(const std::array<double, 3>& v) {
    auto result = py::array_t<double>(3);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v[0];
    buf(1) = v[1];
    buf(2) = v[2];
    return result;
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

// Helper: std::array<double, 4> -> numpy (4,)
static py::array_t<double> vec4_to_numpy(const std::array<double, 4>& v) {
    auto result = py::array_t<double>(4);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v[0];
    buf(1) = v[1];
    buf(2) = v[2];
    buf(3) = v[3];
    return result;
}

namespace termin {

void bind_skeleton(py::module_& m) {

    // Bone
    py::class_<Bone>(m, "Bone")
        .def(py::init<>())
        .def(py::init<const std::string&, int, int>(),
             py::arg("name"), py::arg("index"), py::arg("parent_index"))
        .def_readwrite("name", &Bone::name)
        .def_readwrite("index", &Bone::index)
        .def_readwrite("parent_index", &Bone::parent_index)
        .def_property("inverse_bind_matrix",
            [](const Bone& b) { return mat4_to_numpy(b.inverse_bind_matrix); },
            [](Bone& b, py::array_t<double> arr) { b.inverse_bind_matrix = numpy_to_mat4(arr); })
        .def_property("bind_translation",
            [](const Bone& b) { return vec3_to_numpy(b.bind_translation); },
            [](Bone& b, py::object v) { b.bind_translation = numpy_to_vec3(v); })
        .def_property("bind_rotation",
            [](const Bone& b) { return vec4_to_numpy(b.bind_rotation); },
            [](Bone& b, py::object v) { b.bind_rotation = numpy_to_vec4(v); })
        .def_property("bind_scale",
            [](const Bone& b) { return vec3_to_numpy(b.bind_scale); },
            [](Bone& b, py::object v) { b.bind_scale = numpy_to_vec3(v); })
        .def_property_readonly("is_root", &Bone::is_root)
        .def("serialize", [](const Bone& b) {
            py::dict d;
            d["name"] = b.name;
            d["index"] = b.index;
            d["parent_index"] = b.parent_index;
            d["inverse_bind_matrix"] = mat4_to_numpy(b.inverse_bind_matrix).attr("tolist")();
            d["bind_translation"] = vec3_to_numpy(b.bind_translation).attr("tolist")();
            d["bind_rotation"] = vec4_to_numpy(b.bind_rotation).attr("tolist")();
            d["bind_scale"] = vec3_to_numpy(b.bind_scale).attr("tolist")();
            return d;
        })
        .def_static("deserialize", [](py::dict data) {
            Bone bone;
            bone.name = data["name"].cast<std::string>();
            bone.index = data["index"].cast<int>();
            bone.parent_index = data["parent_index"].cast<int>();

            // Parse inverse_bind_matrix from list of lists
            py::list ibm_list = data["inverse_bind_matrix"].cast<py::list>();
            for (int i = 0; i < 4; ++i) {
                py::list row = ibm_list[i].cast<py::list>();
                for (int j = 0; j < 4; ++j) {
                    bone.inverse_bind_matrix[i * 4 + j] = row[j].cast<double>();
                }
            }

            // Parse bind pose
            if (data.contains("bind_translation")) {
                py::list t = data["bind_translation"].cast<py::list>();
                bone.bind_translation = {t[0].cast<double>(), t[1].cast<double>(), t[2].cast<double>()};
            }
            if (data.contains("bind_rotation")) {
                py::list r = data["bind_rotation"].cast<py::list>();
                bone.bind_rotation = {r[0].cast<double>(), r[1].cast<double>(),
                                      r[2].cast<double>(), r[3].cast<double>()};
            }
            if (data.contains("bind_scale")) {
                py::list s = data["bind_scale"].cast<py::list>();
                bone.bind_scale = {s[0].cast<double>(), s[1].cast<double>(), s[2].cast<double>()};
            }

            return bone;
        }, py::arg("data"))
        .def("__repr__", [](const Bone& b) {
            std::string parent_str = b.is_root() ? "root" : "parent=" + std::to_string(b.parent_index);
            return "<Bone " + std::to_string(b.index) + ": '" + b.name + "' (" + parent_str + ")>";
        });

    // SkeletonData
    py::class_<SkeletonData>(m, "SkeletonData")
        .def(py::init<>())
        .def(py::init<std::vector<Bone>>(), py::arg("bones"))
        .def(py::init<std::vector<Bone>, std::vector<int>>(),
             py::arg("bones"), py::arg("root_bone_indices"))
        .def_property_readonly("bones", [](const SkeletonData& sd) {
            return sd.bones();
        }, py::return_value_policy::reference_internal)
        .def("get_bone_count", &SkeletonData::get_bone_count)
        .def("get_bone_by_name", [](const SkeletonData& sd, const std::string& name) -> py::object {
            const Bone* bone = sd.get_bone_by_name(name);
            if (bone) return py::cast(*bone);
            return py::none();
        }, py::arg("name"))
        .def("get_bone_index", &SkeletonData::get_bone_index, py::arg("name"))
        .def_property_readonly("root_bone_indices", &SkeletonData::root_bone_indices)
        .def("add_bone", &SkeletonData::add_bone, py::arg("bone"))
        .def("rebuild_maps", &SkeletonData::rebuild_maps)
        .def("serialize", [](const SkeletonData& sd) {
            py::dict d;
            py::list bones_list;
            for (const auto& bone : sd.bones()) {
                py::dict bd;
                bd["name"] = bone.name;
                bd["index"] = bone.index;
                bd["parent_index"] = bone.parent_index;
                bd["inverse_bind_matrix"] = mat4_to_numpy(bone.inverse_bind_matrix).attr("tolist")();
                bd["bind_translation"] = vec3_to_numpy(bone.bind_translation).attr("tolist")();
                bd["bind_rotation"] = vec4_to_numpy(bone.bind_rotation).attr("tolist")();
                bd["bind_scale"] = vec3_to_numpy(bone.bind_scale).attr("tolist")();
                bones_list.append(bd);
            }
            d["bones"] = bones_list;
            d["root_bone_indices"] = sd.root_bone_indices();
            return d;
        })
        .def_static("deserialize", [](py::dict data) {
            std::vector<Bone> bones;
            py::list bones_list = data["bones"].cast<py::list>();

            for (auto item : bones_list) {
                py::dict bd = item.cast<py::dict>();
                Bone bone;
                bone.name = bd["name"].cast<std::string>();
                bone.index = bd["index"].cast<int>();
                bone.parent_index = bd["parent_index"].cast<int>();

                py::list ibm_list = bd["inverse_bind_matrix"].cast<py::list>();
                for (int i = 0; i < 4; ++i) {
                    py::list row = ibm_list[i].cast<py::list>();
                    for (int j = 0; j < 4; ++j) {
                        bone.inverse_bind_matrix[i * 4 + j] = row[j].cast<double>();
                    }
                }

                if (bd.contains("bind_translation")) {
                    py::list t = bd["bind_translation"].cast<py::list>();
                    bone.bind_translation = {t[0].cast<double>(), t[1].cast<double>(), t[2].cast<double>()};
                }
                if (bd.contains("bind_rotation")) {
                    py::list r = bd["bind_rotation"].cast<py::list>();
                    bone.bind_rotation = {r[0].cast<double>(), r[1].cast<double>(),
                                          r[2].cast<double>(), r[3].cast<double>()};
                }
                if (bd.contains("bind_scale")) {
                    py::list s = bd["bind_scale"].cast<py::list>();
                    bone.bind_scale = {s[0].cast<double>(), s[1].cast<double>(), s[2].cast<double>()};
                }

                bones.push_back(std::move(bone));
            }

            std::vector<int> root_indices;
            if (data.contains("root_bone_indices") && !data["root_bone_indices"].is_none()) {
                root_indices = data["root_bone_indices"].cast<std::vector<int>>();
                return SkeletonData(std::move(bones), std::move(root_indices));
            }
            return SkeletonData(std::move(bones));
        }, py::arg("data"))
        .def_static("from_glb_skin", [](py::object skin, py::list nodes) {
            // Replicate the Python from_glb_skin logic
            std::vector<Bone> bones;

            py::list joint_indices = skin.attr("joint_node_indices").cast<py::list>();
            py::array_t<double> inv_bind_matrices = skin.attr("inverse_bind_matrices").cast<py::array_t<double>>();
            auto ibm_buf = inv_bind_matrices.unchecked<3>();  // (N, 4, 4)

            size_t num_joints = joint_indices.size();

            for (size_t bone_idx = 0; bone_idx < num_joints; ++bone_idx) {
                int node_idx = joint_indices[bone_idx].cast<int>();
                py::object node = nodes[node_idx];

                // Find parent bone
                int parent_bone_idx = -1;
                for (size_t other_bone_idx = 0; other_bone_idx < num_joints; ++other_bone_idx) {
                    int other_node_idx = joint_indices[other_bone_idx].cast<int>();
                    py::object other_node = nodes[other_node_idx];
                    py::list children = other_node.attr("children").cast<py::list>();
                    for (auto child : children) {
                        if (child.cast<int>() == node_idx) {
                            parent_bone_idx = static_cast<int>(other_bone_idx);
                            break;
                        }
                    }
                    if (parent_bone_idx >= 0) break;
                }

                Bone bone;
                bone.name = node.attr("name").cast<std::string>();
                bone.index = static_cast<int>(bone_idx);
                bone.parent_index = parent_bone_idx;

                // Copy inverse bind matrix
                for (int i = 0; i < 4; ++i) {
                    for (int j = 0; j < 4; ++j) {
                        bone.inverse_bind_matrix[i * 4 + j] = ibm_buf(bone_idx, i, j);
                    }
                }

                // Copy bind pose from node
                py::array_t<double> trans = node.attr("translation").cast<py::array_t<double>>();
                py::array_t<double> rot = node.attr("rotation").cast<py::array_t<double>>();
                py::array_t<double> scale = node.attr("scale").cast<py::array_t<double>>();

                auto t_buf = trans.unchecked<1>();
                auto r_buf = rot.unchecked<1>();
                auto s_buf = scale.unchecked<1>();

                bone.bind_translation = {t_buf(0), t_buf(1), t_buf(2)};
                bone.bind_rotation = {r_buf(0), r_buf(1), r_buf(2), r_buf(3)};
                bone.bind_scale = {s_buf(0), s_buf(1), s_buf(2)};

                bones.push_back(std::move(bone));
            }

            return SkeletonData(std::move(bones));
        }, py::arg("skin"), py::arg("nodes"))
        .def("__repr__", [](const SkeletonData& sd) {
            return "<SkeletonData bones=" + std::to_string(sd.get_bone_count()) +
                   " roots=" + std::to_string(sd.root_bone_indices().size()) + ">";
        });

    // SkeletonInstance
    py::class_<SkeletonInstance>(m, "SkeletonInstance")
        .def(py::init<>())
        .def(py::init<SkeletonData*, std::vector<Entity*>, Entity*>(),
             py::arg("skeleton_data"),
             py::arg("bone_entities") = std::vector<Entity*>{},
             py::arg("skeleton_root_entity") = nullptr,
             py::keep_alive<1, 2>())  // instance keeps skeleton_data alive
        .def_property("skeleton_data",
            &SkeletonInstance::skeleton_data,
            &SkeletonInstance::set_skeleton_data,
            py::return_value_policy::reference)
        .def_property("bone_entities",
            [](const SkeletonInstance& si) {
                py::list result;
                for (Entity* e : si.bone_entities()) {
                    if (e) {
                        result.append(py::cast(e, py::return_value_policy::reference));
                    } else {
                        result.append(py::none());
                    }
                }
                return result;
            },
            [](SkeletonInstance& si, py::list entities) {
                std::vector<Entity*> vec;
                for (auto item : entities) {
                    if (item.is_none()) {
                        vec.push_back(nullptr);
                    } else {
                        vec.push_back(item.cast<Entity*>());
                    }
                }
                si.set_bone_entities(std::move(vec));
            })
        .def_property("skeleton_root",
            &SkeletonInstance::skeleton_root,
            &SkeletonInstance::set_skeleton_root,
            py::return_value_policy::reference)
        .def("get_bone_entity", &SkeletonInstance::get_bone_entity,
             py::arg("bone_index"), py::return_value_policy::reference)
        .def("get_bone_entity_by_name", &SkeletonInstance::get_bone_entity_by_name,
             py::arg("bone_name"), py::return_value_policy::reference)
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
