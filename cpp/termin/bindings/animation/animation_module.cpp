#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/vector.h>

#include "termin/animation/animation.hpp"
#include "termin/assets/handles.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "../../../../core_c/include/tc_kind.hpp"
#include "tc_log.hpp"

namespace nb = nanobind;
using namespace termin;
using namespace termin::animation;

// Helper: numpy array (3,) -> Vec3
static Vec3 numpy_to_vec3(nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
    const double* data = arr.data();
    return Vec3{data[0], data[1], data[2]};
}

// Helper: Vec3 -> numpy array (3,)
static nb::object vec3_to_numpy(const Vec3& v) {
    double* buf = new double[3];
    buf[0] = v.x;
    buf[1] = v.y;
    buf[2] = v.z;
    nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<double*>(p); });
    size_t shape[1] = {3};
    return nb::cast(nb::ndarray<nb::numpy, double>(buf, 1, shape, owner));
}

// Helper: numpy array (4,) -> Quat
static Quat numpy_to_quat(nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
    const double* data = arr.data();
    return Quat{data[0], data[1], data[2], data[3]};
}

// Helper: Quat -> numpy array (4,)
static nb::object quat_to_numpy(const Quat& q) {
    double* buf = new double[4];
    buf[0] = q.x;
    buf[1] = q.y;
    buf[2] = q.z;
    buf[3] = q.w;
    nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<double*>(p); });
    size_t shape[1] = {4};
    return nb::cast(nb::ndarray<nb::numpy, double>(buf, 1, shape, owner));
}

void bind_animation_keyframe(nb::module_& m) {
    nb::class_<AnimationKeyframe>(m, "AnimationKeyframe")
        .def(nb::init<>())
        .def(nb::init<double>(), nb::arg("time"))
        .def("__init__", [](AnimationKeyframe* self, double time, nb::object translation, nb::object rotation, nb::object scale) {
            new (self) AnimationKeyframe(time);
            if (!translation.is_none()) {
                self->translation = numpy_to_vec3(nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(translation));
            }
            if (!rotation.is_none()) {
                self->rotation = numpy_to_quat(nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(rotation));
            }
            if (!scale.is_none()) {
                self->scale = nb::cast<double>(scale);
            }
        }, nb::arg("time"), nb::arg("translation") = nb::none(), nb::arg("rotation") = nb::none(), nb::arg("scale") = nb::none())
        .def_rw("time", &AnimationKeyframe::time)
        .def_prop_rw("translation",
            [](const AnimationKeyframe& kf) -> nb::object {
                if (kf.translation) {
                    return vec3_to_numpy(*kf.translation);
                }
                return nb::none();
            },
            [](AnimationKeyframe& kf, nb::object val) {
                if (val.is_none()) {
                    kf.translation = std::nullopt;
                } else {
                    kf.translation = numpy_to_vec3(nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(val));
                }
            })
        .def_prop_rw("rotation",
            [](const AnimationKeyframe& kf) -> nb::object {
                if (kf.rotation) {
                    return quat_to_numpy(*kf.rotation);
                }
                return nb::none();
            },
            [](AnimationKeyframe& kf, nb::object val) {
                if (val.is_none()) {
                    kf.rotation = std::nullopt;
                } else {
                    kf.rotation = numpy_to_quat(nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(val));
                }
            })
        .def_prop_rw("scale",
            [](const AnimationKeyframe& kf) -> nb::object {
                if (kf.scale) {
                    return nb::float_(*kf.scale);
                }
                return nb::none();
            },
            [](AnimationKeyframe& kf, nb::object val) {
                if (val.is_none()) {
                    kf.scale = std::nullopt;
                } else {
                    kf.scale = nb::cast<double>(val);
                }
            });
}

void bind_animation_channel_sample(nb::module_& m) {
    nb::class_<AnimationChannelSample>(m, "AnimationChannelSample")
        .def(nb::init<>())
        .def_prop_ro("translation",
            [](const AnimationChannelSample& s) -> nb::object {
                if (s.translation) {
                    return vec3_to_numpy(*s.translation);
                }
                return nb::none();
            })
        .def_prop_ro("rotation",
            [](const AnimationChannelSample& s) -> nb::object {
                if (s.rotation) {
                    return quat_to_numpy(*s.rotation);
                }
                return nb::none();
            })
        .def_prop_ro("scale",
            [](const AnimationChannelSample& s) -> nb::object {
                if (s.scale) {
                    return nb::float_(*s.scale);
                }
                return nb::none();
            })
        .def("__getitem__", [](const AnimationChannelSample& s, int i) -> nb::object {
            switch (i) {
                case 0:
                    if (s.translation) return vec3_to_numpy(*s.translation);
                    return nb::none();
                case 1:
                    if (s.rotation) return quat_to_numpy(*s.rotation);
                    return nb::none();
                case 2:
                    if (s.scale) return nb::float_(*s.scale);
                    return nb::none();
                default:
                    throw nb::index_error("Index out of range");
            }
        })
        .def("__len__", [](const AnimationChannelSample&) { return 3; });
}

void bind_animation_channel(nb::module_& m) {
    nb::class_<AnimationChannel>(m, "AnimationChannel")
        .def(nb::init<>())
        .def("__init__", [](AnimationChannel* self, nb::list tr_keys, nb::list rot_keys, nb::list sc_keys) {
            std::vector<AnimationKeyframe> tr, rot, sc;

            for (auto item : tr_keys) {
                nb::tuple tuple = nb::cast<nb::tuple>(item);
                double time = nb::cast<double>(tuple[0]);
                auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(tuple[1]);
                AnimationKeyframe kf(time);
                kf.translation = numpy_to_vec3(arr);
                tr.push_back(kf);
            }

            for (auto item : rot_keys) {
                nb::tuple tuple = nb::cast<nb::tuple>(item);
                double time = nb::cast<double>(tuple[0]);
                auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(tuple[1]);
                AnimationKeyframe kf(time);
                kf.rotation = numpy_to_quat(arr);
                rot.push_back(kf);
            }

            for (auto item : sc_keys) {
                nb::tuple tuple = nb::cast<nb::tuple>(item);
                double time = nb::cast<double>(tuple[0]);
                double scale = nb::cast<double>(tuple[1]);
                AnimationKeyframe kf(time);
                kf.scale = scale;
                sc.push_back(kf);
            }

            new (self) AnimationChannel(std::move(tr), std::move(rot), std::move(sc));
        }, nb::arg("translation_keys"), nb::arg("rotation_keys"), nb::arg("scale_keys"))
        .def_ro("duration", &AnimationChannel::duration)
        .def_prop_ro("translation_keys", [](const AnimationChannel& ch) {
            nb::list result;
            for (const auto& kf : ch.translation_keys) {
                result.append(kf);
            }
            return result;
        })
        .def_prop_ro("rotation_keys", [](const AnimationChannel& ch) {
            nb::list result;
            for (const auto& kf : ch.rotation_keys) {
                result.append(kf);
            }
            return result;
        })
        .def_prop_ro("scale_keys", [](const AnimationChannel& ch) {
            nb::list result;
            for (const auto& kf : ch.scale_keys) {
                result.append(kf);
            }
            return result;
        })
        .def("sample", &AnimationChannel::sample, nb::arg("t_ticks"))
        .def("serialize", [](const AnimationChannel& ch) -> nb::dict {
            nb::dict result;
            nb::list tr_list, rot_list, sc_list;
            for (const auto& kf : ch.translation_keys) {
                tr_list.append(nb::make_tuple(kf.time, vec3_to_numpy(*kf.translation)));
            }
            for (const auto& kf : ch.rotation_keys) {
                rot_list.append(nb::make_tuple(kf.time, quat_to_numpy(*kf.rotation)));
            }
            for (const auto& kf : ch.scale_keys) {
                sc_list.append(nb::make_tuple(kf.time, *kf.scale));
            }
            result["translation"] = tr_list;
            result["rotation"] = rot_list;
            result["scale"] = sc_list;
            return result;
        });
}

void bind_animation_clip(nb::module_& m) {
    nb::class_<AnimationClip>(m, "AnimationClip")
        .def(nb::init<>())
        .def("__init__", [](AnimationClip* self,
                         std::string name,
                         nb::dict channels_dict,
                         double tps,
                         bool loop) {
            std::unordered_map<std::string, AnimationChannel> channels;

            for (auto item : channels_dict) {
                std::string channel_name = nb::cast<std::string>(item.first);
                AnimationChannel channel = nb::cast<AnimationChannel>(item.second);
                channels[channel_name] = std::move(channel);
            }

            new (self) AnimationClip(std::move(name), std::move(channels), tps, loop);
        }, nb::arg("name"), nb::arg("channels"), nb::arg("tps"), nb::arg("loop") = true)
        .def_rw("name", &AnimationClip::name)
        .def_rw("tps", &AnimationClip::tps)
        .def_rw("duration", &AnimationClip::duration)
        .def_rw("loop", &AnimationClip::loop)
        .def_prop_ro("channels",
            [](const AnimationClip& clip) {
                nb::dict result;
                for (const auto& [name, channel] : clip.channels) {
                    result[nb::str(name.c_str())] = channel;
                }
                return result;
            })
        .def("sample", &AnimationClip::sample, nb::arg("t_seconds"))
        .def("sample_dict", [](const AnimationClip& clip, double t_seconds) -> nb::dict {
            auto samples = clip.sample(t_seconds);
            nb::dict result;
            for (const auto& [name, sample] : samples) {
                nb::object tr = sample.translation ? vec3_to_numpy(*sample.translation) : nb::none();
                nb::object rot = sample.rotation ? quat_to_numpy(*sample.rotation) : nb::none();
                nb::object sc = sample.scale ? nb::cast(nb::float_(*sample.scale)) : nb::none();
                result[nb::str(name.c_str())] = nb::make_tuple(tr, rot, sc);
            }
            return result;
        }, nb::arg("t_seconds"))
        .def("serialize", [](const AnimationClip& clip) -> nb::dict {
            nb::dict result;
            result["name"] = clip.name;
            result["tps"] = clip.tps;
            result["loop"] = clip.loop;
            nb::dict channels_dict;
            for (const auto& [name, ch] : clip.channels) {
                nb::dict ch_data;
                nb::list tr_list, rot_list, sc_list;
                for (const auto& kf : ch.translation_keys) {
                    tr_list.append(nb::make_tuple(kf.time, vec3_to_numpy(*kf.translation)));
                }
                for (const auto& kf : ch.rotation_keys) {
                    rot_list.append(nb::make_tuple(kf.time, quat_to_numpy(*kf.rotation)));
                }
                for (const auto& kf : ch.scale_keys) {
                    sc_list.append(nb::make_tuple(kf.time, *kf.scale));
                }
                ch_data["translation"] = tr_list;
                ch_data["rotation"] = rot_list;
                ch_data["scale"] = sc_list;
                channels_dict[nb::str(name.c_str())] = ch_data;
            }
            result["channels"] = channels_dict;
            return result;
        });
}

void bind_animation_clip_handle(nb::module_& m) {
    nb::class_<AnimationClipHandle>(m, "AnimationClipHandle")
        .def(nb::init<>())
        .def("__init__", [](AnimationClipHandle* self, nb::object asset) {
            new (self) AnimationClipHandle(asset);
        }, nb::arg("asset"))
        .def_static("from_name", &AnimationClipHandle::from_name, nb::arg("name"))
        .def_static("from_asset", &AnimationClipHandle::from_asset, nb::arg("asset"))
        .def_static("from_direct", &AnimationClipHandle::from_direct, nb::arg("clip"),
            nb::rv_policy::reference)
        .def_static("from_uuid", &AnimationClipHandle::from_uuid, nb::arg("uuid"))
        .def_static("deserialize", &AnimationClipHandle::deserialize, nb::arg("data"))
        .def_rw("_direct", &AnimationClipHandle::_direct)
        .def_rw("asset", &AnimationClipHandle::asset)
        .def_prop_ro("is_valid", &AnimationClipHandle::is_valid)
        .def_prop_ro("is_direct", &AnimationClipHandle::is_direct)
        .def_prop_ro("name", &AnimationClipHandle::name)
        .def_prop_ro("clip", &AnimationClipHandle::clip, nb::rv_policy::reference)
        .def("get", &AnimationClipHandle::get, nb::rv_policy::reference)
        .def("get_asset", [](const AnimationClipHandle& self) { return self.asset; })
        .def("serialize", &AnimationClipHandle::serialize);
}

void bind_deserialize_functions(nb::module_& m) {
    m.def("deserialize_channel", [](nb::dict data) -> AnimationChannel {
        std::vector<AnimationKeyframe> tr, rot, sc;

        for (auto item : nb::cast<nb::list>(data["translation"])) {
            auto t = nb::cast<nb::tuple>(item);
            AnimationKeyframe kf(nb::cast<double>(t[0]));
            kf.translation = numpy_to_vec3(nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(t[1]));
            tr.push_back(kf);
        }
        for (auto item : nb::cast<nb::list>(data["rotation"])) {
            auto t = nb::cast<nb::tuple>(item);
            AnimationKeyframe kf(nb::cast<double>(t[0]));
            kf.rotation = numpy_to_quat(nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(t[1]));
            rot.push_back(kf);
        }
        for (auto item : nb::cast<nb::list>(data["scale"])) {
            auto t = nb::cast<nb::tuple>(item);
            AnimationKeyframe kf(nb::cast<double>(t[0]));
            kf.scale = nb::cast<double>(t[1]);
            sc.push_back(kf);
        }
        return AnimationChannel(std::move(tr), std::move(rot), std::move(sc));
    }, nb::arg("data"));

    m.def("deserialize_clip", [](nb::dict data) -> AnimationClip {
        std::string name = nb::cast<std::string>(data["name"]);
        double tps = nb::cast<double>(data["tps"]);
        bool loop = nb::cast<bool>(data["loop"]);

        std::unordered_map<std::string, AnimationChannel> channels;
        for (auto item : nb::cast<nb::dict>(data["channels"])) {
            std::string ch_name = nb::cast<std::string>(item.first);
            nb::dict ch_data = nb::cast<nb::dict>(item.second);

            std::vector<AnimationKeyframe> tr, rot, sc;
            for (auto kf_item : nb::cast<nb::list>(ch_data["translation"])) {
                auto t = nb::cast<nb::tuple>(kf_item);
                AnimationKeyframe kf(nb::cast<double>(t[0]));
                kf.translation = numpy_to_vec3(nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(t[1]));
                tr.push_back(kf);
            }
            for (auto kf_item : nb::cast<nb::list>(ch_data["rotation"])) {
                auto t = nb::cast<nb::tuple>(kf_item);
                AnimationKeyframe kf(nb::cast<double>(t[0]));
                kf.rotation = numpy_to_quat(nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(t[1]));
                rot.push_back(kf);
            }
            for (auto kf_item : nb::cast<nb::list>(ch_data["scale"])) {
                auto t = nb::cast<nb::tuple>(kf_item);
                AnimationKeyframe kf(nb::cast<double>(t[0]));
                kf.scale = nb::cast<double>(t[1]);
                sc.push_back(kf);
            }
            channels[ch_name] = AnimationChannel(std::move(tr), std::move(rot), std::move(sc));
        }
        return AnimationClip(std::move(name), std::move(channels), tps, loop);
    }, nb::arg("data"));
}

void register_animation_kind_handlers() {
    // C++ handler for C++ fields
    tc::register_cpp_handle_kind<AnimationClipHandle>("animation_clip_handle");

    // Python handler for Python fields
    tc::KindRegistry::instance().register_python(
        "animation_clip_handle",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            AnimationClipHandle handle = nb::cast<AnimationClipHandle>(obj);
            return handle.serialize();
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            // Handle UUID string (legacy format)
            if (nb::isinstance<nb::str>(data)) {
                return nb::cast(AnimationClipHandle::from_uuid(nb::cast<std::string>(data)));
            }
            // Handle dict format
            if (nb::isinstance<nb::dict>(data)) {
                nb::dict d = nb::cast<nb::dict>(data);
                return nb::cast(AnimationClipHandle::deserialize(d));
            }
            return nb::cast(AnimationClipHandle());
        }),
        // convert
        nb::cpp_function([](nb::object value) -> nb::object {
            if (value.is_none()) {
                return nb::cast(AnimationClipHandle());
            }
            if (nb::isinstance<AnimationClipHandle>(value)) {
                return value;
            }
            // Try AnimationClip*
            if (nb::isinstance<AnimationClip>(value)) {
                auto* clip = nb::cast<AnimationClip*>(value);
                return nb::cast(AnimationClipHandle::from_direct(clip));
            }
            // Try AnimationClipAsset (has 'resource' attribute)
            if (nb::hasattr(value, "resource")) {
                return nb::cast(AnimationClipHandle::from_asset(value));
            }
            // Nothing worked
            nb::str type_str = nb::borrow<nb::str>(value.type().attr("__name__"));
            std::string type_name = nb::cast<std::string>(type_str);
            tc::Log::error("animation_clip_handle convert failed: cannot convert %s to AnimationClipHandle", type_name.c_str());
            return nb::cast(AnimationClipHandle());
        })
    );
}

NB_MODULE(_animation_native, m) {
    m.doc() = "Native C++ animation module for termin";

    bind_animation_keyframe(m);
    bind_animation_channel_sample(m);
    bind_animation_channel(m);
    bind_animation_clip(m);
    bind_animation_clip_handle(m);
    bind_deserialize_functions(m);

    // Register kind handlers for serialization
    register_animation_kind_handlers();
}
