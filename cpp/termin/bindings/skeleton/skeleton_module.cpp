#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/array.h>
#include <nanobind/ndarray.h>
#include <iostream>

#include "termin/skeleton/bone.hpp"
#include "termin/skeleton/skeleton_data.hpp"
#include "termin/skeleton/skeleton_instance.hpp"
#include "termin/render/skeleton_controller.hpp"
#include "termin/entity/entity.hpp"
#include "termin/assets/handles.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "../../../../core_c/include/tc_kind.hpp"
#include "tc_log.hpp"

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
        .def_static("from_direct", &termin::SkeletonHandle::from_direct, nb::arg("skeleton"),
            nb::rv_policy::reference)
        .def_static("deserialize", &termin::SkeletonHandle::deserialize, nb::arg("data"))
        .def_rw("_direct", &termin::SkeletonHandle::_direct)
        .def_rw("asset", &termin::SkeletonHandle::asset)
        .def_prop_ro("is_valid", &termin::SkeletonHandle::is_valid)
        .def_prop_ro("is_direct", &termin::SkeletonHandle::is_direct)
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
            // Try SkeletonData*
            if (nb::isinstance<termin::SkeletonData>(value)) {
                auto* skel_data = nb::cast<termin::SkeletonData*>(value);
                return nb::cast(termin::SkeletonHandle::from_direct(skel_data));
            }
            // Try SkeletonAsset (has 'resource' attribute)
            if (nb::hasattr(value, "resource")) {
                return nb::cast(termin::SkeletonHandle::from_asset(value));
            }
            // Nothing worked
            nb::str type_str = nb::borrow<nb::str>(value.type().attr("__name__"));
            std::string type_name = nb::cast<std::string>(type_str);
            tc::Log::error("skeleton_handle convert failed: cannot convert %s to SkeletonHandle", type_name.c_str());
            return nb::cast(termin::SkeletonHandle());
        })
    );
}

void bind_skeleton_instance(nb::module_& m) {
    nb::class_<termin::SkeletonInstance>(m, "SkeletonInstance")
        .def(nb::init<>())
        .def_prop_rw("skeleton_data",
            &termin::SkeletonInstance::skeleton_data,
            &termin::SkeletonInstance::set_skeleton_data,
            nb::rv_policy::reference)
        .def_prop_rw("bone_entities",
            [](const termin::SkeletonInstance& si) {
                nb::list result;
                for (const termin::Entity& e : si.bone_entities()) {
                    if (e.valid()) {
                        result.append(nb::cast(e));
                    } else {
                        result.append(nb::none());
                    }
                }
                return result;
            },
            [](termin::SkeletonInstance& si, nb::list entities) {
                std::vector<termin::Entity> vec;
                for (auto item : entities) {
                    if (!item.is_none()) {
                        vec.push_back(nb::cast<termin::Entity>(item));
                    }
                }
                si.set_bone_entities(std::move(vec));
            })
        .def_prop_rw("skeleton_root",
            [](const termin::SkeletonInstance& si) -> nb::object {
                termin::Entity root = si.skeleton_root();
                if (root.valid()) return nb::cast(root);
                return nb::none();
            },
            [](termin::SkeletonInstance& si, nb::object root_obj) {
                if (root_obj.is_none()) {
                    si.set_skeleton_root(termin::Entity());
                } else {
                    si.set_skeleton_root(nb::cast<termin::Entity>(root_obj));
                }
            })
        .def("get_bone_entity", [](const termin::SkeletonInstance& si, int index) -> nb::object {
            termin::Entity e = si.get_bone_entity(index);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("bone_index"))
        .def("get_bone_entity_by_name", [](const termin::SkeletonInstance& si, const std::string& name) -> nb::object {
            termin::Entity e = si.get_bone_entity_by_name(name);
            if (e.valid()) return nb::cast(e);
            return nb::none();
        }, nb::arg("bone_name"))
        .def("set_bone_transform", [](termin::SkeletonInstance& si,
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
                t_arr = numpy_to_vec3(translation);
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
                    s_arr = numpy_to_vec3(scale);
                }
                s_ptr = s_arr.data();
            }
            si.set_bone_transform(bone_index, t_ptr, r_ptr, s_ptr);
        }, nb::arg("bone_index"),
           nb::arg("translation") = nb::none(),
           nb::arg("rotation") = nb::none(),
           nb::arg("scale") = nb::none())
        .def("set_bone_transform_by_name", [](termin::SkeletonInstance& si,
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
                t_arr = numpy_to_vec3(translation);
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
                    s_arr = numpy_to_vec3(scale);
                }
                s_ptr = s_arr.data();
            }
            si.set_bone_transform_by_name(bone_name, t_ptr, r_ptr, s_ptr);
        }, nb::arg("bone_name"),
           nb::arg("translation") = nb::none(),
           nb::arg("rotation") = nb::none(),
           nb::arg("scale") = nb::none())
        .def("update", &termin::SkeletonInstance::update)
        .def("get_bone_matrices", [](termin::SkeletonInstance& si) {
            si.update();
            int n = si.bone_count();
            float* buf = new float[n * 16];
            for (int i = 0; i < n; ++i) {
                const termin::Mat44& m = si.get_bone_matrix(i);
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
        .def("bone_count", &termin::SkeletonInstance::bone_count)
        .def("get_bone_world_matrix", [](const termin::SkeletonInstance& si, int bone_index) {
            termin::Mat44 m = si.get_bone_world_matrix(bone_index);
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
        .def("__repr__", [](const termin::SkeletonInstance& si) {
            bool has_entities = !si.bone_entities().empty();
            return "<SkeletonInstance bones=" + std::to_string(si.bone_count()) +
                   " has_entities=" + (has_entities ? "True" : "False") + ">";
        });
}

void bind_skeleton_controller(nb::module_& m) {
    nb::class_<termin::SkeletonController, termin::Component>(m, "SkeletonController")
        .def(nb::init<>())
        .def("__init__", [](termin::SkeletonController* self, nb::object skeleton_arg, nb::list bone_entities_list) {
            new (self) termin::SkeletonController();

            // Handle skeleton argument: SkeletonHandle, SkeletonAsset, or SkeletonData*
            if (!skeleton_arg.is_none()) {
                if (nb::isinstance<termin::SkeletonHandle>(skeleton_arg)) {
                    self->skeleton = nb::cast<termin::SkeletonHandle>(skeleton_arg);
                } else if (nb::hasattr(skeleton_arg, "resource")) {
                    self->skeleton = termin::SkeletonHandle::from_asset(skeleton_arg);
                } else {
                    auto skel_data = nb::cast<termin::SkeletonData*>(skeleton_arg);
                    if (skel_data != nullptr) {
                        nb::object rm_module = nb::module_::import_("termin.assets.resources");
                        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
                        nb::object asset = rm.attr("get_or_create_skeleton_asset")(nb::arg("name") = "skeleton");
                        asset.attr("skeleton_data") = skeleton_arg;
                        self->skeleton = termin::SkeletonHandle::from_asset(asset);
                    }
                }
            }

            std::vector<termin::Entity> entities;
            for (auto item : bone_entities_list) {
                if (!item.is_none()) {
                    entities.push_back(nb::cast<termin::Entity>(item));
                }
            }
            self->set_bone_entities(std::move(entities));
        },
            nb::arg("skeleton") = nb::none(),
            nb::arg("bone_entities") = nb::list())
        .def_rw("skeleton", &termin::SkeletonController::skeleton)
        .def_prop_rw("skeleton_data",
            &termin::SkeletonController::skeleton_data,
            [](termin::SkeletonController& self, nb::object skel_arg) {
                if (skel_arg.is_none()) {
                    self.skeleton = termin::SkeletonHandle();
                    return;
                }
                if (nb::isinstance<termin::SkeletonHandle>(skel_arg)) {
                    self.set_skeleton(nb::cast<termin::SkeletonHandle>(skel_arg));
                } else if (nb::hasattr(skel_arg, "resource")) {
                    self.set_skeleton(termin::SkeletonHandle::from_asset(skel_arg));
                } else {
                    auto skel_data = nb::cast<termin::SkeletonData*>(skel_arg);
                    if (skel_data != nullptr) {
                        nb::object rm_module = nb::module_::import_("termin.assets.resources");
                        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
                        nb::object asset = rm.attr("get_or_create_skeleton_asset")(nb::arg("name") = "skeleton");
                        asset.attr("skeleton_data") = skel_arg;
                        self.set_skeleton(termin::SkeletonHandle::from_asset(asset));
                    }
                }
            },
            nb::rv_policy::reference)
        .def_prop_rw("bone_entities",
            [](const termin::SkeletonController& self) {
                nb::list result;
                for (const auto& e : self.bone_entities) {
                    if (e.valid()) {
                        result.append(nb::cast(e));
                    } else {
                        result.append(nb::none());
                    }
                }
                return result;
            },
            [](termin::SkeletonController& self, nb::list entities) {
                std::vector<termin::Entity> vec;
                for (auto item : entities) {
                    if (!item.is_none()) {
                        vec.push_back(nb::cast<termin::Entity>(item));
                    }
                }
                self.set_bone_entities(std::move(vec));
            })
        .def_prop_ro("skeleton_instance",
            &termin::SkeletonController::skeleton_instance,
            nb::rv_policy::reference)
        .def("set_skeleton", &termin::SkeletonController::set_skeleton)
        .def("set_bone_entities", [](termin::SkeletonController& self, nb::list entities) {
            std::vector<termin::Entity> vec;
            for (auto item : entities) {
                if (!item.is_none()) {
                    vec.push_back(nb::cast<termin::Entity>(item));
                }
            }
            self.set_bone_entities(std::move(vec));
        })
        .def("invalidate_instance", &termin::SkeletonController::invalidate_instance);
}

} // anonymous namespace

NB_MODULE(_skeleton_native, m) {
    m.doc() = "Native C++ skeleton module (Bone, SkeletonData, SkeletonInstance, SkeletonController)";

    // Import _entity_native for Component type (SkeletonController inherits from it)
    nb::module_::import_("termin.entity._entity_native");

    // Bind types
    bind_bone(m);
    bind_skeleton_data(m);
    bind_skeleton_handle(m);
    bind_skeleton_instance(m);
    bind_skeleton_controller(m);

    // Register skeleton kind handler for InspectRegistry
    register_skeleton_kind();
}
