#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "termin/geom/mat44.hpp"
#include "termin/geom/quat.hpp"
#include "termin/geom/vec3.hpp"
#include "termin/inspect/tc_kind.hpp"
#include "termin/skeleton/skeleton_instance.hpp"
#include "termin/skeleton/tc_skeleton_handle.hpp"
#include <tcbase/tc_log.hpp>

namespace nb = nanobind;

namespace {
    [[noreturn]] void throw_bone_field_type_error(size_t bone_index, const char* field, const char* expected_type) {
        const std::string message =
            "skeleton bone " + std::to_string(bone_index) + " field '" + field + "' must be " + expected_type;
        throw nb::type_error(message.c_str());
    }

    template <typename T>
    T require_bone_field(const nb::dict& data, size_t bone_index, const char* field, const char* expected_type) {
        nb::handle value = data[field];
        if (!nb::isinstance<T>(value))
            throw_bone_field_type_error(bone_index, field, expected_type);
        return nb::cast<T>(value);
    }

    int32_t require_bone_parent_index(const nb::dict& data, size_t bone_index) {
        nb::handle value = data["parent_index"];
        if (!nb::isinstance<nb::int_>(value) || nb::isinstance<nb::bool_>(value))
            throw_bone_field_type_error(bone_index, "parent_index", "an integer");
        try {
            return nb::cast<int32_t>(value);
        } catch (const nb::cast_error&) {
            const std::string message = "skeleton bone " + std::to_string(bone_index) +
                                        " field 'parent_index' must fit the signed 32-bit range";
            throw nb::value_error(message.c_str());
        }
    }

    termin::TcSkeleton require_valid_skeleton(nb::handle value, const char* target) {
        if (!nb::isinstance<termin::TcSkeleton>(value)) {
            const std::string message = std::string(target) + " must be a TcSkeleton or None";
            throw nb::type_error(message.c_str());
        }
        termin::TcSkeleton skeleton = nb::cast<termin::TcSkeleton>(value);
        if (!skeleton.is_valid()) {
            const std::string message = std::string(target) + " must reference a live skeleton resource";
            throw nb::value_error(message.c_str());
        }
        return skeleton;
    }

    void bind_tc_skeleton(nb::module_& m) {
        nb::class_<termin::TcSkeleton>(m, "TcSkeleton")
            .def(nb::init<>())
            .def_prop_ro("is_valid", &termin::TcSkeleton::is_valid)
            .def_prop_ro("uuid", [](const termin::TcSkeleton& s) { return std::string(s.uuid()); })
            .def_prop_ro("name", [](const termin::TcSkeleton& s) { return std::string(s.name()); })
            .def_prop_ro("version", &termin::TcSkeleton::version)
            .def_prop_ro("is_loaded", &termin::TcSkeleton::is_loaded)
            .def_prop_ro("bone_count", &termin::TcSkeleton::bone_count)
            .def_prop_ro("root_count", &termin::TcSkeleton::root_count)
            .def("find_bone", &termin::TcSkeleton::find_bone, nb::arg("bone_name"))
            .def("ensure_loaded", &termin::TcSkeleton::ensure_loaded)
            .def_prop_ro("bones",
                         [](const termin::TcSkeleton& self) {
                             nb::list result;
                             const tc_skeleton* skeleton = self.get();
                             if (!skeleton)
                                 return result;
                             for (size_t i = 0; i < skeleton->bone_count; ++i) {
                                 const tc_bone& bone = skeleton->bones[i];
                                 nb::dict data;
                                 data["name"] = bone.name;
                                 data["parent_index"] = bone.parent_index;
                                 data["inverse_bind_matrix"] = termin::Mat44::from_tc_mat44(bone.inverse_bind_matrix);
                                 data["bind_translation"] = bone.bind_translation;
                                 data["bind_rotation"] = bone.bind_rotation;
                                 data["bind_scale"] = bone.bind_scale;
                                 result.append(std::move(data));
                             }
                             return result;
                         })
            .def(
                "set_bones",
                [](termin::TcSkeleton& self, nb::list bone_data) {
                    struct PendingBone {
                        std::string name;
                        int32_t parent_index = -1;
                        termin::Mat44 inverse_bind = termin::Mat44::identity();
                        termin::Vec3 translation = termin::Vec3::zero();
                        termin::Quat rotation = termin::Quat::identity();
                        termin::Vec3 scale{1.0, 1.0, 1.0};
                    };

                    std::vector<PendingBone> pending;
                    pending.reserve(nb::len(bone_data));
                    for (size_t i = 0; i < nb::len(bone_data); ++i) {
                        nb::handle item = bone_data[i];
                        if (!nb::isinstance<nb::dict>(item))
                            throw_bone_field_type_error(i, "payload", "a dict");
                        nb::dict data = nb::borrow<nb::dict>(item);
                        const char* required[] = {"name",
                                                  "parent_index",
                                                  "inverse_bind_matrix",
                                                  "bind_translation",
                                                  "bind_rotation",
                                                  "bind_scale"};
                        for (const char* field : required) {
                            if (!data.contains(field))
                                throw std::invalid_argument(std::string("skeleton bone is missing '") + field + "'");
                        }
                        PendingBone bone;
                        if (!nb::isinstance<nb::str>(data["name"]))
                            throw_bone_field_type_error(i, "name", "a string");
                        bone.name = nb::cast<std::string>(data["name"]);
                        bone.parent_index = require_bone_parent_index(data, i);
                        bone.inverse_bind = require_bone_field<termin::Mat44>(data, i, "inverse_bind_matrix", "Mat44");
                        bone.translation = require_bone_field<termin::Vec3>(data, i, "bind_translation", "Vec3");
                        bone.rotation = require_bone_field<termin::Quat>(data, i, "bind_rotation", "Quat");
                        bone.scale = require_bone_field<termin::Vec3>(data, i, "bind_scale", "Vec3");
                        pending.push_back(std::move(bone));
                    }

                    std::vector<tc_skeleton_bone_desc> descriptors;
                    descriptors.reserve(pending.size());
                    for (PendingBone& bone : pending) {
                        descriptors.push_back({bone.name.c_str(),
                                               bone.parent_index,
                                               bone.inverse_bind.to_tc_mat44(),
                                               bone.translation,
                                               bone.rotation,
                                               bone.scale});
                    }
                    if (!self.replace_bones(descriptors.data(), descriptors.size()))
                        throw std::runtime_error("skeleton replacement failed; previous payload was preserved");
                },
                nb::arg("bones"))
            .def_static("from_uuid", &termin::TcSkeleton::from_uuid, nb::arg("uuid"))
            .def_static("get_or_create", &termin::TcSkeleton::get_or_create, nb::arg("uuid"))
            .def_static("create", &termin::TcSkeleton::create, nb::arg("name") = "", nb::arg("uuid_hint") = "")
            .def("serialize",
                 [](const termin::TcSkeleton& s) {
                     nb::dict d;
                     if (!s.is_valid()) {
                         d["type"] = "none";
                         return d;
                     }
                     d["uuid"] = std::string(s.uuid());
                     d["name"] = std::string(s.name());
                     d["type"] = "uuid";
                     return d;
                 })
            .def_static(
                "deserialize",
                [](nb::dict data) {
                    if (!data.contains("uuid")) {
                        return termin::TcSkeleton();
                    }
                    std::string uuid = nb::cast<std::string>(data["uuid"]);
                    return termin::TcSkeleton::from_uuid(uuid);
                },
                nb::arg("data"))
            .def("__repr__", [](const termin::TcSkeleton& s) {
                if (!s.is_valid())
                    return std::string("<TcSkeleton invalid>");
                return "<TcSkeleton '" + std::string(s.name()) + "' bones=" + std::to_string(s.bone_count()) + ">";
            });
    }

    void register_tc_skeleton_kind() {
        static bool registered = false;
        if (registered) {
            return;
        }

        // C++ handler for tc_skeleton kind
        tc::KindRegistry::instance().register_cpp(
            "tc_skeleton",
            // serialize: std::any(TcSkeleton) → tc_value
            [](const std::any& value) -> tc_value {
                const termin::TcSkeleton& s = std::any_cast<const termin::TcSkeleton&>(value);
                tc_value result = tc_value_dict_new();
                if (s.is_valid()) {
                    tc_value_dict_set(&result, "uuid", tc_value_string(s.uuid()));
                    tc_value_dict_set(&result, "name", tc_value_string(s.name()));
                }
                return result;
            },
            // deserialize: tc_value, scene → std::any(TcSkeleton)
            [](const tc_value* v, void*) -> std::any {
                if (!v || v->type != TC_VALUE_DICT)
                    return termin::TcSkeleton();
                tc_value* uuid_val = tc_value_dict_get(const_cast<tc_value*>(v), "uuid");
                if (!uuid_val || uuid_val->type != TC_VALUE_STRING || !uuid_val->data.s) {
                    return termin::TcSkeleton();
                }
                std::string uuid = uuid_val->data.s;
                termin::TcSkeleton skel = termin::TcSkeleton::from_uuid(uuid);
                if (!skel.is_valid()) {
                    tc_value* name_val = tc_value_dict_get(const_cast<tc_value*>(v), "name");
                    std::string name =
                        (name_val && name_val->type == TC_VALUE_STRING && name_val->data.s) ? name_val->data.s : "";
                    tc::Log::warn(
                        "tc_skeleton deserialize: skeleton not found, uuid=%s name=%s", uuid.c_str(), name.c_str());
                } else {
                    skel.ensure_loaded();
                }
                return skel;
            });

        nb::module_ skeleton_module = nb::module_::import_("termin.skeleton._skeleton_native");
        tc::KindRegistry::instance().register_type(skeleton_module.attr("TcSkeleton"), "tc_skeleton");

        // Python handler for tc_skeleton kind
        tc::KindRegistry::instance().register_python("tc_skeleton",
                                                     // serialize
                                                     nb::cpp_function([](nb::object obj) -> nb::object {
                                                         termin::TcSkeleton skel = nb::cast<termin::TcSkeleton>(obj);
                                                         nb::dict d;
                                                         if (skel.is_valid()) {
                                                             d["uuid"] = nb::str(skel.uuid());
                                                             d["name"] = nb::str(skel.name());
                                                         }
                                                         return d;
                                                     }),
                                                     // deserialize
                                                     nb::cpp_function([](nb::object data) -> nb::object {
                                                         if (!nb::isinstance<nb::dict>(data)) {
                                                             return nb::cast(termin::TcSkeleton());
                                                         }
                                                         nb::dict d = nb::cast<nb::dict>(data);
                                                         if (!d.contains("uuid")) {
                                                             return nb::cast(termin::TcSkeleton());
                                                         }
                                                         std::string uuid = nb::cast<std::string>(d["uuid"]);
                                                         return nb::cast(termin::TcSkeleton::from_uuid(uuid));
                                                     }));

        registered = true;
    }

    void bind_skeleton_instance(nb::module_& m) {
        nb::class_<termin::SkeletonInstance>(m, "SkeletonInstance")
            .def(
                "__init__",
                [](termin::SkeletonInstance* self, nb::object skeleton) {
                    if (skeleton.is_none()) {
                        new (self) termin::SkeletonInstance();
                        return;
                    }
                    new (self) termin::SkeletonInstance(require_valid_skeleton(skeleton, "skeleton"));
                },
                nb::arg("skeleton").none() = nb::none())
            .def_prop_rw(
                "skeleton",
                [](const termin::SkeletonInstance& self) -> nb::object {
                    if (!self.skeleton_resource().has_handle())
                        return nb::none();
                    return nb::cast(self.skeleton());
                },
                [](termin::SkeletonInstance& self, nb::object skeleton) {
                    if (skeleton.is_none()) {
                        self.set_skeleton(termin::TcSkeleton());
                        return;
                    }
                    self.set_skeleton(require_valid_skeleton(skeleton, "SkeletonInstance.skeleton"));
                },
                nb::arg().none())
            .def("reset_to_bind_pose",
                 [](termin::SkeletonInstance& si) {
                     if (!si.reset_to_bind_pose())
                         throw std::runtime_error("cannot reset a SkeletonInstance whose resource handle is stale");
                 })
            .def(
                "set_bone_transform",
                [](termin::SkeletonInstance& si,
                   int bone_index,
                   std::optional<termin::Vec3> translation,
                   std::optional<termin::Quat> rotation,
                   std::optional<termin::Vec3> scale) {
                    if (!si.try_set_bone_transform(bone_index,
                                                   translation ? &*translation : nullptr,
                                                   rotation ? &*rotation : nullptr,
                                                   scale ? &*scale : nullptr)) {
                        throw nb::value_error(
                            "bone transform requires a valid index, finite vectors, and a finite non-zero rotation");
                    }
                },
                nb::arg("bone_index"),
                nb::arg("translation") = nb::none(),
                nb::arg("rotation") = nb::none(),
                nb::arg("scale") = nb::none())
            .def(
                "try_set_bone_transform",
                [](termin::SkeletonInstance& si,
                   int bone_index,
                   std::optional<termin::Vec3> translation,
                   std::optional<termin::Quat> rotation,
                   std::optional<termin::Vec3> scale) {
                    return si.try_set_bone_transform(bone_index,
                                                     translation ? &*translation : nullptr,
                                                     rotation ? &*rotation : nullptr,
                                                     scale ? &*scale : nullptr);
                },
                nb::arg("bone_index"),
                nb::arg("translation") = nb::none(),
                nb::arg("rotation") = nb::none(),
                nb::arg("scale") = nb::none())
            .def(
                "set_bone_transform_by_name",
                [](termin::SkeletonInstance& si,
                   const std::string& bone_name,
                   std::optional<termin::Vec3> translation,
                   std::optional<termin::Quat> rotation,
                   std::optional<termin::Vec3> scale) {
                    if (!si.try_set_bone_transform_by_name(bone_name,
                                                           translation ? &*translation : nullptr,
                                                           rotation ? &*rotation : nullptr,
                                                           scale ? &*scale : nullptr)) {
                        throw nb::value_error(
                            "bone transform requires a known bone, finite vectors, and a finite non-zero rotation");
                    }
                },
                nb::arg("bone_name"),
                nb::arg("translation") = nb::none(),
                nb::arg("rotation") = nb::none(),
                nb::arg("scale") = nb::none())
            .def(
                "try_set_bone_transform_by_name",
                [](termin::SkeletonInstance& si,
                   const std::string& bone_name,
                   std::optional<termin::Vec3> translation,
                   std::optional<termin::Quat> rotation,
                   std::optional<termin::Vec3> scale) {
                    return si.try_set_bone_transform_by_name(bone_name,
                                                             translation ? &*translation : nullptr,
                                                             rotation ? &*rotation : nullptr,
                                                             scale ? &*scale : nullptr);
                },
                nb::arg("bone_name"),
                nb::arg("translation") = nb::none(),
                nb::arg("rotation") = nb::none(),
                nb::arg("scale") = nb::none())
            .def("update",
                 [](termin::SkeletonInstance& si) {
                     if (!si.update())
                         throw std::runtime_error("cannot update a SkeletonInstance whose resource handle is stale");
                 })
            .def("get_bone_matrices",
                 [](termin::SkeletonInstance& si) {
                     if (!si.update())
                         throw std::runtime_error(
                             "cannot read matrices from a SkeletonInstance whose resource handle is stale");
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
            .def("bone_count",
                 [](termin::SkeletonInstance& si) {
                     if (!si.synchronize())
                         throw std::runtime_error(
                             "cannot read bone_count from a SkeletonInstance whose resource handle is stale");
                     return si.bone_count();
                 })
            .def(
                "get_bone_world_matrix",
                [](termin::SkeletonInstance& si, int bone_index) {
                    if (!si.synchronize())
                        throw std::runtime_error(
                            "cannot read matrices from a SkeletonInstance whose resource handle is stale");
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
                },
                nb::arg("bone_index"))
            .def("__repr__", [](termin::SkeletonInstance& si) {
                return "<SkeletonInstance bones=" + std::to_string(si.bone_count()) + ">";
            });
    }

} // anonymous namespace

NB_MODULE(_skeleton_native, m) {
    m.doc() = "Native C++ skeleton module (TcSkeleton, SkeletonInstance)";

    nb::module_::import_("tcbase._geom_native");

    // Bind types
    bind_tc_skeleton(m);
    bind_skeleton_instance(m);

    m.def("register_tc_skeleton_kind", &register_tc_skeleton_kind, "Register tc_skeleton kind handlers explicitly.");

    // Lazy loading API
    m.def(
        "tc_skeleton_declare",
        [](const std::string& uuid, const std::string& name) {
            tc_skeleton_handle h = tc_skeleton_declare(uuid.c_str(), name.empty() ? nullptr : name.c_str());
            return termin::TcSkeleton(h);
        },
        nb::arg("uuid"),
        nb::arg("name") = "",
        "Declare a skeleton that will be loaded lazily");

    m.def(
        "tc_skeleton_is_loaded",
        [](const termin::TcSkeleton& handle) { return handle.is_loaded(); },
        nb::arg("handle"),
        "Check if skeleton data is loaded");

    m.def("tc_skeleton_get_all_info", []() {
        nb::list result;
        size_t count = 0;
        tc_skeleton_info* infos = tc_skeleton_get_all_info(&count);
        for (size_t i = 0; i < count; ++i) {
            nb::dict info;
            info["handle"] = nb::make_tuple(infos[i].handle.index, infos[i].handle.generation);
            info["uuid"] = std::string(infos[i].uuid);
            info["name"] = infos[i].name ? std::string(infos[i].name) : "";
            info["ref_count"] = infos[i].ref_count;
            info["version"] = infos[i].version;
            info["bone_count"] = infos[i].bone_count;
            info["is_loaded"] = infos[i].is_loaded != 0;
            result.append(info);
        }
        free(infos);
        return result;
    });
}
