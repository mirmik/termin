#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/array.h>
#include <nanobind/ndarray.h>

#include "termin/skeleton/bone.hpp"
#include "termin/skeleton/skeleton_data.hpp"
#include "termin/assets/handles.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "../../../../core_c/include/tc_kind.hpp"

namespace nb = nanobind;

namespace {

// Helper: numpy (4,4) -> std::array<double, 16>
std::array<double, 16> numpy_to_mat4(nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
    double* ptr = arr.data();
    std::array<double, 16> result;
    for (int i = 0; i < 16; ++i) {
        result[i] = ptr[i];
    }
    return result;
}

// Helper: std::array<double, 16> -> numpy (4,4)
nb::object mat4_to_numpy(const std::array<double, 16>& m) {
    double* data = new double[16];
    for (int i = 0; i < 16; ++i) {
        data[i] = m[i];
    }
    nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
    size_t shape[2] = {4, 4};
    return nb::cast(nb::ndarray<nb::numpy, double, nb::shape<4, 4>>(data, 2, shape, owner));
}

// Helper: numpy (3,) -> std::array<double, 3>
std::array<double, 3> numpy_to_vec3(nb::object obj) {
    try {
        auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(obj);
        double* ptr = arr.data();
        return {ptr[0], ptr[1], ptr[2]};
    } catch (...) {}
    nb::sequence seq = nb::cast<nb::sequence>(obj);
    return {nb::cast<double>(seq[0]), nb::cast<double>(seq[1]), nb::cast<double>(seq[2])};
}

// Helper: std::array<double, 3> -> numpy (3,)
nb::object vec3_to_numpy(const std::array<double, 3>& v) {
    double* data = new double[3]{v[0], v[1], v[2]};
    nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
    return nb::cast(nb::ndarray<nb::numpy, double, nb::shape<3>>(data, {3}, owner));
}

// Helper: numpy (4,) -> std::array<double, 4>
std::array<double, 4> numpy_to_vec4(nb::object obj) {
    try {
        auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(obj);
        double* ptr = arr.data();
        return {ptr[0], ptr[1], ptr[2], ptr[3]};
    } catch (...) {}
    nb::sequence seq = nb::cast<nb::sequence>(obj);
    return {nb::cast<double>(seq[0]), nb::cast<double>(seq[1]),
            nb::cast<double>(seq[2]), nb::cast<double>(seq[3])};
}

// Helper: std::array<double, 4> -> numpy (4,)
nb::object vec4_to_numpy(const std::array<double, 4>& v) {
    double* data = new double[4]{v[0], v[1], v[2], v[3]};
    nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
    return nb::cast(nb::ndarray<nb::numpy, double, nb::shape<4>>(data, {4}, owner));
}

void bind_bone(nb::module_& m) {
    nb::class_<termin::Bone>(m, "Bone")
        .def(nb::init<>())
        .def(nb::init<const std::string&, int, int>(),
             nb::arg("name"), nb::arg("index"), nb::arg("parent_index"))
        .def_rw("name", &termin::Bone::name)
        .def_rw("index", &termin::Bone::index)
        .def_rw("parent_index", &termin::Bone::parent_index)
        .def_prop_rw("inverse_bind_matrix",
            [](const termin::Bone& b) { return mat4_to_numpy(b.inverse_bind_matrix); },
            [](termin::Bone& b, nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) { b.inverse_bind_matrix = numpy_to_mat4(arr); })
        .def_prop_rw("bind_translation",
            [](const termin::Bone& b) { return vec3_to_numpy(b.bind_translation); },
            [](termin::Bone& b, nb::object v) { b.bind_translation = numpy_to_vec3(v); })
        .def_prop_rw("bind_rotation",
            [](const termin::Bone& b) { return vec4_to_numpy(b.bind_rotation); },
            [](termin::Bone& b, nb::object v) { b.bind_rotation = numpy_to_vec4(v); })
        .def_prop_rw("bind_scale",
            [](const termin::Bone& b) { return vec3_to_numpy(b.bind_scale); },
            [](termin::Bone& b, nb::object v) { b.bind_scale = numpy_to_vec3(v); })
        .def_prop_ro("is_root", &termin::Bone::is_root)
        .def("serialize", [](const termin::Bone& b) {
            nb::dict d;
            d["name"] = b.name;
            d["index"] = b.index;
            d["parent_index"] = b.parent_index;
            d["inverse_bind_matrix"] = mat4_to_numpy(b.inverse_bind_matrix).attr("tolist")();
            d["bind_translation"] = vec3_to_numpy(b.bind_translation).attr("tolist")();
            d["bind_rotation"] = vec4_to_numpy(b.bind_rotation).attr("tolist")();
            d["bind_scale"] = vec3_to_numpy(b.bind_scale).attr("tolist")();
            return d;
        })
        .def_static("deserialize", [](nb::dict data) {
            termin::Bone bone;
            bone.name = nb::cast<std::string>(data["name"]);
            bone.index = nb::cast<int>(data["index"]);
            bone.parent_index = nb::cast<int>(data["parent_index"]);

            nb::list ibm_list = nb::cast<nb::list>(data["inverse_bind_matrix"]);
            for (int i = 0; i < 4; ++i) {
                nb::list row = nb::cast<nb::list>(ibm_list[i]);
                for (int j = 0; j < 4; ++j) {
                    bone.inverse_bind_matrix[i * 4 + j] = nb::cast<double>(row[j]);
                }
            }

            if (data.contains("bind_translation")) {
                nb::list t = nb::cast<nb::list>(data["bind_translation"]);
                bone.bind_translation = {nb::cast<double>(t[0]), nb::cast<double>(t[1]), nb::cast<double>(t[2])};
            }
            if (data.contains("bind_rotation")) {
                nb::list r = nb::cast<nb::list>(data["bind_rotation"]);
                bone.bind_rotation = {nb::cast<double>(r[0]), nb::cast<double>(r[1]),
                                      nb::cast<double>(r[2]), nb::cast<double>(r[3])};
            }
            if (data.contains("bind_scale")) {
                nb::list s = nb::cast<nb::list>(data["bind_scale"]);
                bone.bind_scale = {nb::cast<double>(s[0]), nb::cast<double>(s[1]), nb::cast<double>(s[2])};
            }

            return bone;
        }, nb::arg("data"))
        .def("__repr__", [](const termin::Bone& b) {
            std::string parent_str = b.is_root() ? "root" : "parent=" + std::to_string(b.parent_index);
            return "<Bone " + std::to_string(b.index) + ": '" + b.name + "' (" + parent_str + ")>";
        });
}

void bind_skeleton_data(nb::module_& m) {
    nb::class_<termin::SkeletonData>(m, "SkeletonData")
        .def(nb::init<>())
        .def(nb::init<std::vector<termin::Bone>>(), nb::arg("bones"))
        .def(nb::init<std::vector<termin::Bone>, std::vector<int>>(),
             nb::arg("bones"), nb::arg("root_bone_indices"))
        .def_prop_ro("bones", [](const termin::SkeletonData& sd) {
            return sd.bones();
        }, nb::rv_policy::reference_internal)
        .def("get_bone_count", &termin::SkeletonData::get_bone_count)
        .def("get_bone_by_name", [](const termin::SkeletonData& sd, const std::string& name) -> nb::object {
            const termin::Bone* bone = sd.get_bone_by_name(name);
            if (bone) return nb::cast(*bone);
            return nb::none();
        }, nb::arg("name"))
        .def("get_bone_index", &termin::SkeletonData::get_bone_index, nb::arg("name"))
        .def_prop_ro("root_bone_indices", &termin::SkeletonData::root_bone_indices)
        .def("add_bone", &termin::SkeletonData::add_bone, nb::arg("bone"))
        .def("rebuild_maps", &termin::SkeletonData::rebuild_maps)
        .def("serialize", [](const termin::SkeletonData& sd) {
            nb::dict d;
            nb::list bones_list;
            for (const auto& bone : sd.bones()) {
                nb::dict bd;
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
        .def_static("deserialize", [](nb::dict data) {
            std::vector<termin::Bone> bones;
            nb::list bones_list = nb::cast<nb::list>(data["bones"]);

            for (auto item : bones_list) {
                nb::dict bd = nb::cast<nb::dict>(item);
                termin::Bone bone;
                bone.name = nb::cast<std::string>(bd["name"]);
                bone.index = nb::cast<int>(bd["index"]);
                bone.parent_index = nb::cast<int>(bd["parent_index"]);

                nb::list ibm_list = nb::cast<nb::list>(bd["inverse_bind_matrix"]);
                for (int i = 0; i < 4; ++i) {
                    nb::list row = nb::cast<nb::list>(ibm_list[i]);
                    for (int j = 0; j < 4; ++j) {
                        bone.inverse_bind_matrix[i * 4 + j] = nb::cast<double>(row[j]);
                    }
                }

                if (bd.contains("bind_translation")) {
                    nb::list t = nb::cast<nb::list>(bd["bind_translation"]);
                    bone.bind_translation = {nb::cast<double>(t[0]), nb::cast<double>(t[1]), nb::cast<double>(t[2])};
                }
                if (bd.contains("bind_rotation")) {
                    nb::list r = nb::cast<nb::list>(bd["bind_rotation"]);
                    bone.bind_rotation = {nb::cast<double>(r[0]), nb::cast<double>(r[1]),
                                          nb::cast<double>(r[2]), nb::cast<double>(r[3])};
                }
                if (bd.contains("bind_scale")) {
                    nb::list s = nb::cast<nb::list>(bd["bind_scale"]);
                    bone.bind_scale = {nb::cast<double>(s[0]), nb::cast<double>(s[1]), nb::cast<double>(s[2])};
                }

                bones.push_back(std::move(bone));
            }

            std::vector<int> root_indices;
            if (data.contains("root_bone_indices") && !data["root_bone_indices"].is_none()) {
                root_indices = nb::cast<std::vector<int>>(data["root_bone_indices"]);
                return termin::SkeletonData(std::move(bones), std::move(root_indices));
            }
            return termin::SkeletonData(std::move(bones));
        }, nb::arg("data"))
        .def_static("from_glb_skin", [](nb::object skin, nb::list nodes) {
            std::vector<termin::Bone> bones;

            nb::list joint_indices = nb::cast<nb::list>(skin.attr("joint_node_indices"));
            auto inv_bind_matrices = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(skin.attr("inverse_bind_matrices"));
            double* ibm_ptr = inv_bind_matrices.data();

            size_t num_joints = nb::len(joint_indices);

            for (size_t bone_idx = 0; bone_idx < num_joints; ++bone_idx) {
                int node_idx = nb::cast<int>(joint_indices[bone_idx]);
                nb::object node = nodes[node_idx];

                int parent_bone_idx = -1;
                for (size_t other_bone_idx = 0; other_bone_idx < num_joints; ++other_bone_idx) {
                    int other_node_idx = nb::cast<int>(joint_indices[other_bone_idx]);
                    nb::object other_node = nodes[other_node_idx];
                    nb::list children = nb::cast<nb::list>(other_node.attr("children"));
                    for (auto child : children) {
                        if (nb::cast<int>(child) == node_idx) {
                            parent_bone_idx = static_cast<int>(other_bone_idx);
                            break;
                        }
                    }
                    if (parent_bone_idx >= 0) break;
                }

                termin::Bone bone;
                bone.name = nb::cast<std::string>(node.attr("name"));
                bone.index = static_cast<int>(bone_idx);
                bone.parent_index = parent_bone_idx;

                // Copy inverse bind matrix (4x4 stored per bone)
                for (int i = 0; i < 16; ++i) {
                    bone.inverse_bind_matrix[i] = ibm_ptr[bone_idx * 16 + i];
                }

                auto trans = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(node.attr("translation"));
                auto rot = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(node.attr("rotation"));
                auto scale = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(node.attr("scale"));

                double* t_ptr = trans.data();
                double* r_ptr = rot.data();
                double* s_ptr = scale.data();

                bone.bind_translation = {t_ptr[0], t_ptr[1], t_ptr[2]};
                bone.bind_rotation = {r_ptr[0], r_ptr[1], r_ptr[2], r_ptr[3]};
                bone.bind_scale = {s_ptr[0], s_ptr[1], s_ptr[2]};

                bones.push_back(std::move(bone));
            }

            return termin::SkeletonData(std::move(bones));
        }, nb::arg("skin"), nb::arg("nodes"))
        .def("__repr__", [](const termin::SkeletonData& sd) {
            return "<SkeletonData bones=" + std::to_string(sd.get_bone_count()) +
                   " roots=" + std::to_string(sd.root_bone_indices().size()) + ">";
        });
}

void bind_skeleton_handle(nb::module_& m) {
    nb::class_<termin::SkeletonHandle>(m, "SkeletonHandle")
        .def(nb::init<>())
        .def("__init__", [](termin::SkeletonHandle* self, nb::object asset) {
            new (self) termin::SkeletonHandle(asset);
        }, nb::arg("asset"))
        .def_static("from_name", &termin::SkeletonHandle::from_name, nb::arg("name"))
        .def_static("from_asset", &termin::SkeletonHandle::from_asset, nb::arg("asset"))
        .def_static("deserialize", &termin::SkeletonHandle::deserialize, nb::arg("data"))
        .def_rw("asset", &termin::SkeletonHandle::asset)
        .def_prop_ro("is_valid", &termin::SkeletonHandle::is_valid)
        .def_prop_ro("name", &termin::SkeletonHandle::name)
        .def("get", &termin::SkeletonHandle::get, nb::rv_policy::reference)
        .def("get_asset", [](const termin::SkeletonHandle& self) { return self.asset; })
        .def("serialize", &termin::SkeletonHandle::serialize);
}

void register_skeleton_kind() {
    // C++ handler for C++ fields
    tc::register_cpp_handle_kind<termin::SkeletonHandle>("skeleton_handle");

    // Python handler for Python fields
    tc::KindRegistry::instance().register_python(
        "skeleton_handle",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            termin::SkeletonHandle handle = nb::cast<termin::SkeletonHandle>(obj);
            return handle.serialize();
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            if (!nb::isinstance<nb::dict>(data)) {
                return nb::cast(termin::SkeletonHandle());
            }
            nb::dict d = nb::cast<nb::dict>(data);
            return nb::cast(termin::SkeletonHandle::deserialize(d));
        }),
        // convert
        nb::cpp_function([](nb::object value) -> nb::object {
            if (value.is_none()) {
                return nb::cast(termin::SkeletonHandle());
            }
            if (nb::isinstance<termin::SkeletonHandle>(value)) {
                return value;
            }
            // Convert from SkeletonData* to SkeletonHandle
            try {
                auto* skel_data = nb::cast<termin::SkeletonData*>(value);
                if (skel_data != nullptr) {
                    nb::object skel_asset_module = nb::module_::import_("termin.assets.skeleton_asset");
                    nb::object SkeletonAsset = skel_asset_module.attr("SkeletonAsset");
                    nb::object asset = SkeletonAsset.attr("from_skeleton_data")(value, nb::arg("name") = "skeleton");

                    nb::object rm_module = nb::module_::import_("termin.assets.resources");
                    nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
                    rm.attr("register_skeleton")(nb::arg("name") = "skeleton", nb::arg("skeleton") = value);

                    return nb::cast(termin::SkeletonHandle::from_asset(asset));
                }
            } catch (const nb::cast_error&) {}

            // Try SkeletonAsset
            try {
                return nb::cast(termin::SkeletonHandle::from_asset(value));
            } catch (const nb::python_error&) {}
            return value;
        })
    );
}

} // anonymous namespace

NB_MODULE(_skeleton_native, m) {
    m.doc() = "Native C++ skeleton module (Bone, SkeletonData, SkeletonHandle)";

    // Bind types
    bind_bone(m);
    bind_skeleton_data(m);
    bind_skeleton_handle(m);

    // Register skeleton kind handler for InspectRegistry
    register_skeleton_kind();
}
