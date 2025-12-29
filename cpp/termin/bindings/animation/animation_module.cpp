#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "termin/animation/animation.hpp"
#include "termin/assets/handles.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "../../../../core_c/include/tc_kind.hpp"

namespace py = pybind11;
using namespace termin;
using namespace termin::animation;

// Helper: numpy array (3,) -> Vec3
static Vec3 numpy_to_vec3(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return Vec3{buf(0), buf(1), buf(2)};
}

// Helper: Vec3 -> numpy array (3,)
static py::array_t<double> vec3_to_numpy(const Vec3& v) {
    auto result = py::array_t<double>(3);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v.x;
    buf(1) = v.y;
    buf(2) = v.z;
    return result;
}

// Helper: numpy array (4,) -> Quat
static Quat numpy_to_quat(py::array_t<double> arr) {
    auto buf = arr.unchecked<1>();
    return Quat{buf(0), buf(1), buf(2), buf(3)};
}

// Helper: Quat -> numpy array (4,)
static py::array_t<double> quat_to_numpy(const Quat& q) {
    auto result = py::array_t<double>(4);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = q.x;
    buf(1) = q.y;
    buf(2) = q.z;
    buf(3) = q.w;
    return result;
}

void bind_animation_keyframe(py::module_& m) {
    py::class_<AnimationKeyframe>(m, "AnimationKeyframe")
        .def(py::init<>())
        .def(py::init<double>(), py::arg("time"))
        .def(py::init([](double time, py::object translation, py::object rotation, py::object scale) {
            AnimationKeyframe kf(time);
            if (!translation.is_none()) {
                kf.translation = numpy_to_vec3(py::array_t<double>::ensure(translation));
            }
            if (!rotation.is_none()) {
                kf.rotation = numpy_to_quat(py::array_t<double>::ensure(rotation));
            }
            if (!scale.is_none()) {
                kf.scale = scale.cast<double>();
            }
            return kf;
        }), py::arg("time"), py::arg("translation") = py::none(), py::arg("rotation") = py::none(), py::arg("scale") = py::none())
        .def_readwrite("time", &AnimationKeyframe::time)
        .def_property("translation",
            [](const AnimationKeyframe& kf) -> py::object {
                if (kf.translation) {
                    return vec3_to_numpy(*kf.translation);
                }
                return py::none();
            },
            [](AnimationKeyframe& kf, py::object val) {
                if (val.is_none()) {
                    kf.translation = std::nullopt;
                } else {
                    kf.translation = numpy_to_vec3(py::array_t<double>::ensure(val));
                }
            })
        .def_property("rotation",
            [](const AnimationKeyframe& kf) -> py::object {
                if (kf.rotation) {
                    return quat_to_numpy(*kf.rotation);
                }
                return py::none();
            },
            [](AnimationKeyframe& kf, py::object val) {
                if (val.is_none()) {
                    kf.rotation = std::nullopt;
                } else {
                    kf.rotation = numpy_to_quat(py::array_t<double>::ensure(val));
                }
            })
        .def_property("scale",
            [](const AnimationKeyframe& kf) -> py::object {
                if (kf.scale) {
                    return py::float_(*kf.scale);
                }
                return py::none();
            },
            [](AnimationKeyframe& kf, py::object val) {
                if (val.is_none()) {
                    kf.scale = std::nullopt;
                } else {
                    kf.scale = val.cast<double>();
                }
            });
}

void bind_animation_channel_sample(py::module_& m) {
    py::class_<AnimationChannelSample>(m, "AnimationChannelSample")
        .def(py::init<>())
        .def_property_readonly("translation",
            [](const AnimationChannelSample& s) -> py::object {
                if (s.translation) {
                    return vec3_to_numpy(*s.translation);
                }
                return py::none();
            })
        .def_property_readonly("rotation",
            [](const AnimationChannelSample& s) -> py::object {
                if (s.rotation) {
                    return quat_to_numpy(*s.rotation);
                }
                return py::none();
            })
        .def_property_readonly("scale",
            [](const AnimationChannelSample& s) -> py::object {
                if (s.scale) {
                    return py::float_(*s.scale);
                }
                return py::none();
            })
        .def("__getitem__", [](const AnimationChannelSample& s, int i) -> py::object {
            switch (i) {
                case 0:
                    if (s.translation) return vec3_to_numpy(*s.translation);
                    return py::none();
                case 1:
                    if (s.rotation) return quat_to_numpy(*s.rotation);
                    return py::none();
                case 2:
                    if (s.scale) return py::float_(*s.scale);
                    return py::none();
                default:
                    throw py::index_error("Index out of range");
            }
        })
        .def("__len__", [](const AnimationChannelSample&) { return 3; });
}

void bind_animation_channel(py::module_& m) {
    py::class_<AnimationChannel>(m, "AnimationChannel")
        .def(py::init<>())
        .def(py::init([](py::list tr_keys, py::list rot_keys, py::list sc_keys) {
            std::vector<AnimationKeyframe> tr, rot, sc;

            for (auto item : tr_keys) {
                auto tuple = item.cast<py::tuple>();
                double time = tuple[0].cast<double>();
                auto arr = py::array_t<double>::ensure(tuple[1]);
                AnimationKeyframe kf(time);
                kf.translation = numpy_to_vec3(arr);
                tr.push_back(kf);
            }

            for (auto item : rot_keys) {
                auto tuple = item.cast<py::tuple>();
                double time = tuple[0].cast<double>();
                auto arr = py::array_t<double>::ensure(tuple[1]);
                AnimationKeyframe kf(time);
                kf.rotation = numpy_to_quat(arr);
                rot.push_back(kf);
            }

            for (auto item : sc_keys) {
                auto tuple = item.cast<py::tuple>();
                double time = tuple[0].cast<double>();
                double scale = tuple[1].cast<double>();
                AnimationKeyframe kf(time);
                kf.scale = scale;
                sc.push_back(kf);
            }

            return AnimationChannel(std::move(tr), std::move(rot), std::move(sc));
        }), py::arg("translation_keys"), py::arg("rotation_keys"), py::arg("scale_keys"))
        .def_readonly("duration", &AnimationChannel::duration)
        .def_property_readonly("translation_keys", [](const AnimationChannel& ch) {
            py::list result;
            for (const auto& kf : ch.translation_keys) {
                result.append(kf);
            }
            return result;
        })
        .def_property_readonly("rotation_keys", [](const AnimationChannel& ch) {
            py::list result;
            for (const auto& kf : ch.rotation_keys) {
                result.append(kf);
            }
            return result;
        })
        .def_property_readonly("scale_keys", [](const AnimationChannel& ch) {
            py::list result;
            for (const auto& kf : ch.scale_keys) {
                result.append(kf);
            }
            return result;
        })
        .def("sample", &AnimationChannel::sample, py::arg("t_ticks"))
        .def("serialize", [](const AnimationChannel& ch) -> py::dict {
            py::dict result;
            py::list tr_list, rot_list, sc_list;
            for (const auto& kf : ch.translation_keys) {
                tr_list.append(py::make_tuple(kf.time, vec3_to_numpy(*kf.translation)));
            }
            for (const auto& kf : ch.rotation_keys) {
                rot_list.append(py::make_tuple(kf.time, quat_to_numpy(*kf.rotation)));
            }
            for (const auto& kf : ch.scale_keys) {
                sc_list.append(py::make_tuple(kf.time, *kf.scale));
            }
            result["translation"] = tr_list;
            result["rotation"] = rot_list;
            result["scale"] = sc_list;
            return result;
        });
}

void bind_animation_clip(py::module_& m) {
    py::class_<AnimationClip>(m, "AnimationClip")
        .def(py::init<>())
        .def(py::init([](std::string name,
                         py::dict channels_dict,
                         double tps,
                         bool loop) {
            std::unordered_map<std::string, AnimationChannel> channels;

            for (auto item : channels_dict) {
                std::string channel_name = item.first.cast<std::string>();
                AnimationChannel channel = item.second.cast<AnimationChannel>();
                channels[channel_name] = std::move(channel);
            }

            return AnimationClip(std::move(name), std::move(channels), tps, loop);
        }), py::arg("name"), py::arg("channels"), py::arg("tps"), py::arg("loop") = true)
        .def_readwrite("name", &AnimationClip::name)
        .def_readwrite("tps", &AnimationClip::tps)
        .def_readwrite("duration", &AnimationClip::duration)
        .def_readwrite("loop", &AnimationClip::loop)
        .def_property_readonly("channels",
            [](const AnimationClip& clip) {
                py::dict result;
                for (const auto& [name, channel] : clip.channels) {
                    result[py::str(name)] = channel;
                }
                return result;
            })
        .def("sample", &AnimationClip::sample, py::arg("t_seconds"))
        .def("sample_dict", [](const AnimationClip& clip, double t_seconds) -> py::dict {
            auto samples = clip.sample(t_seconds);
            py::dict result;
            for (const auto& [name, sample] : samples) {
                py::object tr = sample.translation ? py::object(vec3_to_numpy(*sample.translation)) : py::none();
                py::object rot = sample.rotation ? py::object(quat_to_numpy(*sample.rotation)) : py::none();
                py::object sc = sample.scale ? py::object(py::float_(*sample.scale)) : py::none();
                result[py::str(name)] = py::make_tuple(tr, rot, sc);
            }
            return result;
        }, py::arg("t_seconds"))
        .def("serialize", [](const AnimationClip& clip) -> py::dict {
            py::dict result;
            result["name"] = clip.name;
            result["tps"] = clip.tps;
            result["loop"] = clip.loop;
            py::dict channels_dict;
            for (const auto& [name, ch] : clip.channels) {
                py::dict ch_data;
                py::list tr_list, rot_list, sc_list;
                for (const auto& kf : ch.translation_keys) {
                    tr_list.append(py::make_tuple(kf.time, vec3_to_numpy(*kf.translation)));
                }
                for (const auto& kf : ch.rotation_keys) {
                    rot_list.append(py::make_tuple(kf.time, quat_to_numpy(*kf.rotation)));
                }
                for (const auto& kf : ch.scale_keys) {
                    sc_list.append(py::make_tuple(kf.time, *kf.scale));
                }
                ch_data["translation"] = tr_list;
                ch_data["rotation"] = rot_list;
                ch_data["scale"] = sc_list;
                channels_dict[py::str(name)] = ch_data;
            }
            result["channels"] = channels_dict;
            return result;
        });
}

void bind_animation_clip_handle(py::module_& m) {
    py::class_<AnimationClipHandle>(m, "AnimationClipHandle")
        .def(py::init<>())
        .def(py::init<py::object>(), py::arg("asset"))
        .def_static("from_name", &AnimationClipHandle::from_name, py::arg("name"))
        .def_static("from_asset", &AnimationClipHandle::from_asset, py::arg("asset"))
        .def_static("from_uuid", &AnimationClipHandle::from_uuid, py::arg("uuid"))
        .def_static("deserialize", &AnimationClipHandle::deserialize, py::arg("data"))
        .def_readwrite("asset", &AnimationClipHandle::asset)
        .def_property_readonly("is_valid", &AnimationClipHandle::is_valid)
        .def_property_readonly("name", &AnimationClipHandle::name)
        .def_property_readonly("clip", &AnimationClipHandle::clip,
            py::return_value_policy::reference)
        .def("get", &AnimationClipHandle::get, py::return_value_policy::reference)
        .def("get_asset", [](const AnimationClipHandle& self) { return self.asset; })
        .def("serialize", &AnimationClipHandle::serialize);
}

void bind_deserialize_functions(py::module_& m) {
    m.def("deserialize_channel", [](py::dict data) -> AnimationChannel {
        std::vector<AnimationKeyframe> tr, rot, sc;

        for (auto item : data["translation"].cast<py::list>()) {
            auto t = item.cast<py::tuple>();
            AnimationKeyframe kf(t[0].cast<double>());
            kf.translation = numpy_to_vec3(py::array_t<double>::ensure(t[1]));
            tr.push_back(kf);
        }
        for (auto item : data["rotation"].cast<py::list>()) {
            auto t = item.cast<py::tuple>();
            AnimationKeyframe kf(t[0].cast<double>());
            kf.rotation = numpy_to_quat(py::array_t<double>::ensure(t[1]));
            rot.push_back(kf);
        }
        for (auto item : data["scale"].cast<py::list>()) {
            auto t = item.cast<py::tuple>();
            AnimationKeyframe kf(t[0].cast<double>());
            kf.scale = t[1].cast<double>();
            sc.push_back(kf);
        }
        return AnimationChannel(std::move(tr), std::move(rot), std::move(sc));
    }, py::arg("data"));

    m.def("deserialize_clip", [](py::dict data) -> AnimationClip {
        std::string name = data["name"].cast<std::string>();
        double tps = data["tps"].cast<double>();
        bool loop = data["loop"].cast<bool>();

        std::unordered_map<std::string, AnimationChannel> channels;
        for (auto item : data["channels"].cast<py::dict>()) {
            std::string ch_name = item.first.cast<std::string>();
            py::dict ch_data = item.second.cast<py::dict>();

            std::vector<AnimationKeyframe> tr, rot, sc;
            for (auto kf_item : ch_data["translation"].cast<py::list>()) {
                auto t = kf_item.cast<py::tuple>();
                AnimationKeyframe kf(t[0].cast<double>());
                kf.translation = numpy_to_vec3(py::array_t<double>::ensure(t[1]));
                tr.push_back(kf);
            }
            for (auto kf_item : ch_data["rotation"].cast<py::list>()) {
                auto t = kf_item.cast<py::tuple>();
                AnimationKeyframe kf(t[0].cast<double>());
                kf.rotation = numpy_to_quat(py::array_t<double>::ensure(t[1]));
                rot.push_back(kf);
            }
            for (auto kf_item : ch_data["scale"].cast<py::list>()) {
                auto t = kf_item.cast<py::tuple>();
                AnimationKeyframe kf(t[0].cast<double>());
                kf.scale = t[1].cast<double>();
                sc.push_back(kf);
            }
            channels[ch_name] = AnimationChannel(std::move(tr), std::move(rot), std::move(sc));
        }
        return AnimationClip(std::move(name), std::move(channels), tps, loop);
    }, py::arg("data"));
}

void register_animation_kind_handlers() {
    // ===== animation_clip_handle kind =====
    // C++ handler for C++ fields
    tc::register_cpp_handle_kind<AnimationClipHandle>("animation_clip_handle");

    // Python handler for Python fields
    tc::KindRegistry::instance().register_python(
        "animation_clip_handle",
        // serialize
        py::cpp_function([](py::object obj) -> py::object {
            std::cout << "[animation_clip_handle.serialize] obj type: " << py::str(obj.get_type()) << std::endl;
            try {
                AnimationClipHandle handle = obj.cast<AnimationClipHandle>();
                std::cout << "[animation_clip_handle.serialize] handle.is_valid=" << handle.is_valid() << std::endl;
                auto result = handle.serialize();
                std::cout << "[animation_clip_handle.serialize] result: " << py::str(result) << std::endl;
                return result;
            } catch (const std::exception& e) {
                std::cout << "[animation_clip_handle.serialize] ERROR: " << e.what() << std::endl;
                return py::none();
            }
        }),
        // deserialize
        py::cpp_function([](py::object data) -> py::object {
            // Handle UUID string (legacy format)
            if (py::isinstance<py::str>(data)) {
                return py::cast(AnimationClipHandle::from_uuid(data.cast<std::string>()));
            }
            // Handle dict format
            if (py::isinstance<py::dict>(data)) {
                py::dict d = data.cast<py::dict>();
                return py::cast(AnimationClipHandle::deserialize(d));
            }
            return py::cast(AnimationClipHandle());
        }),
        // convert
        py::cpp_function([](py::object value) -> py::object {
            if (value.is_none()) {
                return py::cast(AnimationClipHandle());
            }
            if (py::isinstance<AnimationClipHandle>(value)) {
                return value;
            }
            return value;
        })
    );
    // list[animation_clip_handle] is auto-generated by InspectRegistry
}

PYBIND11_MODULE(_animation_native, m) {
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
