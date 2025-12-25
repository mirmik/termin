#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>

#include "termin/skeleton/bone.hpp"
#include "termin/skeleton/skeleton_data.hpp"
#include "termin/assets/handles.hpp"
#include "termin/inspect/inspect_registry.hpp"

namespace py = pybind11;

namespace {

// Helper: numpy (4,4) -> std::array<double, 16>
std::array<double, 16> numpy_to_mat4(py::array_t<double> arr) {
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
py::array_t<double> mat4_to_numpy(const std::array<double, 16>& m) {
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
std::array<double, 3> numpy_to_vec3(py::object obj) {
    auto arr = py::array_t<double>::ensure(obj);
    if (arr && arr.size() >= 3) {
        auto buf = arr.unchecked<1>();
        return {buf(0), buf(1), buf(2)};
    }
    auto seq = obj.cast<py::sequence>();
    return {seq[0].cast<double>(), seq[1].cast<double>(), seq[2].cast<double>()};
}

// Helper: std::array<double, 3> -> numpy (3,)
py::array_t<double> vec3_to_numpy(const std::array<double, 3>& v) {
    auto result = py::array_t<double>(3);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v[0];
    buf(1) = v[1];
    buf(2) = v[2];
    return result;
}

// Helper: numpy (4,) -> std::array<double, 4>
std::array<double, 4> numpy_to_vec4(py::object obj) {
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
py::array_t<double> vec4_to_numpy(const std::array<double, 4>& v) {
    auto result = py::array_t<double>(4);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v[0];
    buf(1) = v[1];
    buf(2) = v[2];
    buf(3) = v[3];
    return result;
}

void bind_bone(py::module_& m) {
    py::class_<termin::Bone>(m, "Bone")
        .def(py::init<>())
        .def(py::init<const std::string&, int, int>(),
             py::arg("name"), py::arg("index"), py::arg("parent_index"))
        .def_readwrite("name", &termin::Bone::name)
        .def_readwrite("index", &termin::Bone::index)
        .def_readwrite("parent_index", &termin::Bone::parent_index)
        .def_property("inverse_bind_matrix",
            [](const termin::Bone& b) { return mat4_to_numpy(b.inverse_bind_matrix); },
            [](termin::Bone& b, py::array_t<double> arr) { b.inverse_bind_matrix = numpy_to_mat4(arr); })
        .def_property("bind_translation",
            [](const termin::Bone& b) { return vec3_to_numpy(b.bind_translation); },
            [](termin::Bone& b, py::object v) { b.bind_translation = numpy_to_vec3(v); })
        .def_property("bind_rotation",
            [](const termin::Bone& b) { return vec4_to_numpy(b.bind_rotation); },
            [](termin::Bone& b, py::object v) { b.bind_rotation = numpy_to_vec4(v); })
        .def_property("bind_scale",
            [](const termin::Bone& b) { return vec3_to_numpy(b.bind_scale); },
            [](termin::Bone& b, py::object v) { b.bind_scale = numpy_to_vec3(v); })
        .def_property_readonly("is_root", &termin::Bone::is_root)
        .def("serialize", [](const termin::Bone& b) {
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
            termin::Bone bone;
            bone.name = data["name"].cast<std::string>();
            bone.index = data["index"].cast<int>();
            bone.parent_index = data["parent_index"].cast<int>();

            py::list ibm_list = data["inverse_bind_matrix"].cast<py::list>();
            for (int i = 0; i < 4; ++i) {
                py::list row = ibm_list[i].cast<py::list>();
                for (int j = 0; j < 4; ++j) {
                    bone.inverse_bind_matrix[i * 4 + j] = row[j].cast<double>();
                }
            }

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
        .def("__repr__", [](const termin::Bone& b) {
            std::string parent_str = b.is_root() ? "root" : "parent=" + std::to_string(b.parent_index);
            return "<Bone " + std::to_string(b.index) + ": '" + b.name + "' (" + parent_str + ")>";
        });
}

void bind_skeleton_data(py::module_& m) {
    py::class_<termin::SkeletonData>(m, "SkeletonData")
        .def(py::init<>())
        .def(py::init<std::vector<termin::Bone>>(), py::arg("bones"))
        .def(py::init<std::vector<termin::Bone>, std::vector<int>>(),
             py::arg("bones"), py::arg("root_bone_indices"))
        .def_property_readonly("bones", [](const termin::SkeletonData& sd) {
            return sd.bones();
        }, py::return_value_policy::reference_internal)
        .def("get_bone_count", &termin::SkeletonData::get_bone_count)
        .def("get_bone_by_name", [](const termin::SkeletonData& sd, const std::string& name) -> py::object {
            const termin::Bone* bone = sd.get_bone_by_name(name);
            if (bone) return py::cast(*bone);
            return py::none();
        }, py::arg("name"))
        .def("get_bone_index", &termin::SkeletonData::get_bone_index, py::arg("name"))
        .def_property_readonly("root_bone_indices", &termin::SkeletonData::root_bone_indices)
        .def("add_bone", &termin::SkeletonData::add_bone, py::arg("bone"))
        .def("rebuild_maps", &termin::SkeletonData::rebuild_maps)
        .def("serialize", [](const termin::SkeletonData& sd) {
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
            std::vector<termin::Bone> bones;
            py::list bones_list = data["bones"].cast<py::list>();

            for (auto item : bones_list) {
                py::dict bd = item.cast<py::dict>();
                termin::Bone bone;
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
                return termin::SkeletonData(std::move(bones), std::move(root_indices));
            }
            return termin::SkeletonData(std::move(bones));
        }, py::arg("data"))
        .def_static("from_glb_skin", [](py::object skin, py::list nodes) {
            std::vector<termin::Bone> bones;

            py::list joint_indices = skin.attr("joint_node_indices").cast<py::list>();
            py::array_t<double> inv_bind_matrices = skin.attr("inverse_bind_matrices").cast<py::array_t<double>>();
            auto ibm_buf = inv_bind_matrices.unchecked<3>();

            size_t num_joints = joint_indices.size();

            for (size_t bone_idx = 0; bone_idx < num_joints; ++bone_idx) {
                int node_idx = joint_indices[bone_idx].cast<int>();
                py::object node = nodes[node_idx];

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

                termin::Bone bone;
                bone.name = node.attr("name").cast<std::string>();
                bone.index = static_cast<int>(bone_idx);
                bone.parent_index = parent_bone_idx;

                for (int i = 0; i < 4; ++i) {
                    for (int j = 0; j < 4; ++j) {
                        bone.inverse_bind_matrix[i * 4 + j] = ibm_buf(bone_idx, i, j);
                    }
                }

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

            return termin::SkeletonData(std::move(bones));
        }, py::arg("skin"), py::arg("nodes"))
        .def("__repr__", [](const termin::SkeletonData& sd) {
            return "<SkeletonData bones=" + std::to_string(sd.get_bone_count()) +
                   " roots=" + std::to_string(sd.root_bone_indices().size()) + ">";
        });
}

void bind_skeleton_handle(py::module_& m) {
    py::class_<termin::SkeletonHandle>(m, "SkeletonHandle")
        .def(py::init<>())
        .def(py::init<py::object>(), py::arg("asset"))
        .def_static("from_name", &termin::SkeletonHandle::from_name, py::arg("name"))
        .def_static("from_asset", &termin::SkeletonHandle::from_asset, py::arg("asset"))
        .def_static("deserialize", &termin::SkeletonHandle::deserialize, py::arg("data"))
        .def_readwrite("asset", &termin::SkeletonHandle::asset)
        .def_property_readonly("is_valid", &termin::SkeletonHandle::is_valid)
        .def_property_readonly("name", &termin::SkeletonHandle::name)
        .def("get", &termin::SkeletonHandle::get, py::return_value_policy::reference)
        .def("get_asset", [](const termin::SkeletonHandle& self) { return self.asset; })
        .def("serialize", &termin::SkeletonHandle::serialize);
}

void register_skeleton_kind() {
    auto& registry = termin::InspectRegistry::instance();

    registry.register_kind("skeleton", termin::KindHandler{
        // serialize
        [](py::object obj) -> nos::trent {
            if (py::hasattr(obj, "serialize")) {
                py::dict d = obj.attr("serialize")();
                return termin::InspectRegistry::py_dict_to_trent(d);
            }
            return nos::trent::nil();
        },
        // deserialize
        [](const nos::trent& t) -> py::object {
            if (!t.is_dict()) {
                return py::cast(termin::SkeletonHandle());
            }
            py::dict d = termin::InspectRegistry::trent_to_py_dict(t);
            return py::cast(termin::SkeletonHandle::deserialize(d));
        },
        // convert
        [](py::object value) -> py::object {
            if (value.is_none()) {
                return py::cast(termin::SkeletonHandle());
            }
            if (py::isinstance<termin::SkeletonHandle>(value)) {
                return value;
            }
            // Convert from SkeletonData* to SkeletonHandle
            try {
                auto* skel_data = value.cast<termin::SkeletonData*>();
                if (skel_data != nullptr) {
                    py::object skel_asset_module = py::module_::import("termin.assets.skeleton_asset");
                    py::object SkeletonAsset = skel_asset_module.attr("SkeletonAsset");
                    py::object asset = SkeletonAsset.attr("from_skeleton_data")(value, py::arg("name") = "skeleton");

                    py::object rm_module = py::module_::import("termin.assets.resources");
                    py::object rm = rm_module.attr("ResourceManager").attr("instance")();
                    rm.attr("register_skeleton")(py::arg("name") = "skeleton", py::arg("skeleton") = value);

                    return py::cast(termin::SkeletonHandle::from_asset(asset));
                }
            } catch (const py::cast_error&) {}

            // Try SkeletonAsset
            if (py::hasattr(value, "resource")) {
                return py::cast(termin::SkeletonHandle::from_asset(value));
            }
            return value;
        }
    });
}

} // anonymous namespace

PYBIND11_MODULE(_skeleton_native, m) {
    m.doc() = "Native C++ skeleton module (Bone, SkeletonData, SkeletonHandle)";

    // Bind types
    bind_bone(m);
    bind_skeleton_data(m);
    bind_skeleton_handle(m);

    // Register skeleton kind handler for InspectRegistry
    register_skeleton_kind();
}
