#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/vector.h>

#include "termin/animation/tc_animation_handle.hpp"
#include "termin/geom/quat.hpp"
#include "termin/geom/vec3.hpp"
#include "termin/inspect/tc_kind.hpp"
#include <stdexcept>
#include <tcbase/tc_log.hpp>

namespace nb = nanobind;
using namespace termin;
using namespace termin::animation;

namespace {

void validate_publication_strings(const std::string& name, const std::string& uuid) {
    if (name.find('\0') != std::string::npos || uuid.find('\0') != std::string::npos)
        throw std::invalid_argument("animation name and UUID must not contain NUL");
}

tc_animation_path animation_path_from_string(const std::string& value) {
    if (value == "translation")
        return TC_ANIMATION_PATH_TRANSLATION;
    if (value == "rotation")
        return TC_ANIMATION_PATH_ROTATION;
    if (value == "scale")
        return TC_ANIMATION_PATH_SCALE;
    if (value == "weights")
        return TC_ANIMATION_PATH_WEIGHTS;
    throw std::invalid_argument("unsupported animation path: " + value);
}

const char* animation_path_name(tc_animation_path value) {
    switch (value) {
    case TC_ANIMATION_PATH_TRANSLATION:
        return "translation";
    case TC_ANIMATION_PATH_ROTATION:
        return "rotation";
    case TC_ANIMATION_PATH_SCALE:
        return "scale";
    case TC_ANIMATION_PATH_WEIGHTS:
        return "weights";
    }
    return "invalid";
}

tc_animation_interpolation animation_interpolation_from_string(const std::string& value) {
    if (value == "linear")
        return TC_ANIMATION_INTERPOLATION_LINEAR;
    if (value == "step")
        return TC_ANIMATION_INTERPOLATION_STEP;
    if (value == "cubic_spline")
        return TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE;
    throw std::invalid_argument("unsupported animation interpolation: " + value);
}

const char* animation_interpolation_name(tc_animation_interpolation value) {
    switch (value) {
    case TC_ANIMATION_INTERPOLATION_LINEAR:
        return "linear";
    case TC_ANIMATION_INTERPOLATION_STEP:
        return "step";
    case TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE:
        return "cubic_spline";
    }
    return "invalid";
}

std::vector<double> doubles_from_sequence(nb::handle value, const char* field) {
    nb::sequence sequence;
    try {
        sequence = nb::cast<nb::sequence>(value);
    } catch (const nb::cast_error&) {
        throw std::invalid_argument(std::string("animation track '") + field + "' must be a sequence");
    }
    std::vector<double> result;
    result.reserve(nb::len(sequence));
    for (size_t i = 0; i < nb::len(sequence); ++i)
        result.push_back(nb::cast<double>(sequence[i]));
    return result;
}

nb::tuple animation_keyframe_tuple(nb::handle value, const char* field) {
    nb::tuple frame;
    try {
        frame = nb::cast<nb::tuple>(value);
    } catch (const nb::cast_error&) {
        throw std::invalid_argument(std::string("animation channel '") + field +
                                    "' entries must be (time, value) tuples");
    }
    if (nb::len(frame) != 2) {
        throw std::invalid_argument(std::string("animation channel '") + field +
                                    "' entries must contain exactly time and value");
    }
    return frame;
}

void append_vec3(nb::list& values, tc_vec3 value) {
    values.append(value.x);
    values.append(value.y);
    values.append(value.z);
}

void append_vec4(nb::list& values, tc_vec4 value) {
    values.append(value.x);
    values.append(value.y);
    values.append(value.z);
    values.append(value.w);
}

void append_quat(nb::list& values, tc_quat value) {
    values.append(value.x);
    values.append(value.y);
    values.append(value.z);
    values.append(value.w);
}

uint32_t animation_track_components(const tc_animation_track& track) {
    if (track.path == TC_ANIMATION_PATH_ROTATION)
        return 4;
    if (track.path == TC_ANIMATION_PATH_TRANSLATION || track.path == TC_ANIMATION_PATH_SCALE)
        return 3;
    if (track.path == TC_ANIMATION_PATH_WEIGHTS)
        return track.values.weights.component_count;
    throw std::runtime_error("owned animation track has an invalid path discriminator");
}

nb::dict animation_track_to_dict(const tc_animation_track& track) {
    nb::dict result;
    result["target_node_index"] = track.target_node_index;
    result["path"] = animation_path_name((tc_animation_path)track.path);
    result["interpolation"] = animation_interpolation_name((tc_animation_interpolation)track.interpolation);
    const uint32_t components = animation_track_components(track);
    result["components"] = components;
    nb::list times;
    for (size_t i = 0; i < track.key_count; ++i)
        times.append(track.times[i]);
    nb::list values;
    if (track.path == TC_ANIMATION_PATH_WEIGHTS) {
        const size_t multiplier = track.interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE ? 3u : 1u;
        if (components == 0 || track.key_count > SIZE_MAX / components ||
            track.key_count * components > SIZE_MAX / multiplier) {
            throw std::runtime_error("owned morph-weight track has an overflowing layout");
        }
        const size_t value_count = track.key_count * components * multiplier;
        if (!track.values.weights.values)
            throw std::runtime_error("owned morph-weight track has no value storage");
        for (size_t i = 0; i < value_count; ++i)
            values.append(track.values.weights.values[i]);
    } else if (track.interpolation == TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE) {
        if (track.path == TC_ANIMATION_PATH_ROTATION) {
            if (!track.values.cubic_rotation_keys)
                throw std::runtime_error("owned cubic rotation track has no key storage");
            for (size_t i = 0; i < track.key_count; ++i) {
                const tc_animation_cubic_rotation_key& key = track.values.cubic_rotation_keys[i];
                append_vec4(values, key.in_tangent);
                append_quat(values, key.value);
                append_vec4(values, key.out_tangent);
            }
        } else {
            if (!track.values.cubic_vec3_keys)
                throw std::runtime_error("owned cubic vec3 track has no key storage");
            for (size_t i = 0; i < track.key_count; ++i) {
                const tc_animation_cubic_vec3_key& key = track.values.cubic_vec3_keys[i];
                append_vec3(values, key.in_tangent);
                append_vec3(values, key.value);
                append_vec3(values, key.out_tangent);
            }
        }
    } else if (track.path == TC_ANIMATION_PATH_ROTATION) {
        if (!track.values.rotation_values)
            throw std::runtime_error("owned rotation track has no value storage");
        for (size_t i = 0; i < track.key_count; ++i)
            append_quat(values, track.values.rotation_values[i]);
    } else {
        if (!track.values.vec3_values)
            throw std::runtime_error("owned vec3 track has no value storage");
        for (size_t i = 0; i < track.key_count; ++i)
            append_vec3(values, track.values.vec3_values[i]);
    }
    result["times"] = std::move(times);
    result["values"] = std::move(values);
    return result;
}

struct ParsedTracks {
    struct Track {
        tc_animation_track_desc desc{};
        std::vector<double> times;
        std::vector<double> values;
    };
    std::vector<Track> storage;
    std::vector<tc_animation_track_desc> descriptors;

    explicit ParsedTracks(nb::list data) {
        storage.reserve(nb::len(data));
        for (size_t i = 0; i < nb::len(data); ++i) {
            const nb::dict item = nb::cast<nb::dict>(data[i]);
            const char* required[] = {"target_node_index", "path", "interpolation", "components", "times", "values"};
            for (const char* field : required) {
                if (!item.contains(field))
                    throw std::invalid_argument(std::string("animation track is missing '") + field + "'");
            }
            Track track;
            track.desc.target_node_index = nb::cast<int32_t>(item["target_node_index"]);
            track.desc.path = animation_path_from_string(nb::cast<std::string>(item["path"]));
            track.desc.interpolation = animation_interpolation_from_string(nb::cast<std::string>(item["interpolation"]));
            track.desc.components = nb::cast<uint32_t>(item["components"]);
            track.times = doubles_from_sequence(item["times"], "times");
            track.values = doubles_from_sequence(item["values"], "values");
            storage.push_back(std::move(track));
        }
        descriptors.reserve(storage.size());
        for (Track& track : storage) {
            track.desc.key_count = track.times.size();
            track.desc.value_count = track.values.size();
            track.desc.times = track.times.data();
            track.desc.values = track.values.data();
            descriptors.push_back(track.desc);
        }
    }
};

struct ParsedChannels {
    struct Channel {
        std::string name;
        std::vector<tc_keyframe_vec3> translation;
        std::vector<tc_keyframe_quat> rotation;
        std::vector<tc_keyframe_scalar> scale;
    };
    std::vector<Channel> storage;
    std::vector<tc_animation_channel_desc> descriptors;

    explicit ParsedChannels(nb::list data) {
        try {
            storage.reserve(nb::len(data));
            for (size_t i = 0; i < nb::len(data); ++i) {
                const nb::dict item = nb::cast<nb::dict>(data[i]);
                Channel channel;
                if (item.contains("target_name"))
                    channel.name = nb::cast<std::string>(item["target_name"]);
                if (channel.name.find('\0') != std::string::npos)
                    throw std::invalid_argument("animation target name must not contain NUL");
                if (item.contains("translation_keys")) {
                    const nb::list keys = nb::cast<nb::list>(item["translation_keys"]);
                    for (size_t key = 0; key < nb::len(keys); ++key) {
                        const nb::tuple frame = animation_keyframe_tuple(keys[key], "translation_keys");
                        channel.translation.push_back({nb::cast<double>(frame[0]), nb::cast<Vec3>(frame[1])});
                    }
                }
                if (item.contains("rotation_keys")) {
                    const nb::list keys = nb::cast<nb::list>(item["rotation_keys"]);
                    for (size_t key = 0; key < nb::len(keys); ++key) {
                        const nb::tuple frame = animation_keyframe_tuple(keys[key], "rotation_keys");
                        channel.rotation.push_back({nb::cast<double>(frame[0]), nb::cast<Quat>(frame[1])});
                    }
                }
                if (item.contains("scale_keys")) {
                    const nb::list keys = nb::cast<nb::list>(item["scale_keys"]);
                    for (size_t key = 0; key < nb::len(keys); ++key) {
                        const nb::tuple frame = animation_keyframe_tuple(keys[key], "scale_keys");
                        channel.scale.push_back({nb::cast<double>(frame[0]), nb::cast<double>(frame[1])});
                    }
                }
                storage.push_back(std::move(channel));
            }
            descriptors.reserve(storage.size());
            for (const Channel& channel : storage) {
                descriptors.push_back({channel.name.c_str(), channel.translation.data(), channel.translation.size(),
                                       channel.rotation.data(), channel.rotation.size(),
                                       channel.scale.data(), channel.scale.size()});
            }
        } catch (const nb::cast_error& error) {
            tc::Log::error("TcAnimationClip: failed to parse channels: %s", error.what());
            throw nb::type_error("animation channels contain a value of the wrong type");
        } catch (const std::exception& error) {
            tc::Log::error("TcAnimationClip: failed to parse channels: %s", error.what());
            throw;
        }
    }
};

nb::dict animation_channel_to_dict(const tc_animation_channel& channel) {
    nb::dict result;
    result["target_name"] = std::string(channel.target_name);
    nb::list translation, rotation, scale;
    for (size_t i = 0; i < channel.translation_count; ++i) {
        const auto& key = channel.translation_keys[i];
        translation.append(nb::make_tuple(key.time, nb::make_tuple(key.value.x, key.value.y, key.value.z)));
    }
    for (size_t i = 0; i < channel.rotation_count; ++i) {
        const auto& key = channel.rotation_keys[i];
        rotation.append(nb::make_tuple(key.time, nb::make_tuple(key.value.x, key.value.y, key.value.z, key.value.w)));
    }
    for (size_t i = 0; i < channel.scale_count; ++i) {
        const auto& key = channel.scale_keys[i];
        scale.append(nb::make_tuple(key.time, key.value));
    }
    result["translation_keys"] = std::move(translation);
    result["rotation_keys"] = std::move(rotation);
    result["scale_keys"] = std::move(scale);
    return result;
}

} // namespace

void bind_tc_animation_clip(nb::module_& m) {
    nb::class_<tc_animation>(m, "TcAnimationData")
        .def_prop_rw(
            "is_loaded",
            [](const tc_animation& a) { return a.header.is_loaded != 0; },
            [](tc_animation& a, bool loaded) { a.header.is_loaded = loaded ? 1 : 0; })
        .def_prop_ro("uuid", [](const tc_animation& a) { return std::string(a.header.uuid); })
        .def_prop_ro("name", [](const tc_animation& a) { return a.header.name ? std::string(a.header.name) : ""; })
        .def_prop_ro("channel_count", [](const tc_animation& a) { return a.channel_count; })
        .def_prop_ro("duration", [](const tc_animation& a) { return a.duration; });

    nb::class_<TcAnimationClip>(m, "TcAnimationClip")
        .def(nb::init<>())
        .def_static("from_uuid", &TcAnimationClip::from_uuid, nb::arg("uuid"))
        .def_static("get_or_create", &TcAnimationClip::get_or_create, nb::arg("uuid"))
        .def_static("create", &TcAnimationClip::create, nb::arg("name") = "", nb::arg("uuid_hint") = "")
        .def_static("publish_tracks", [](const std::string& name, const std::string& uuid,
                                         double tps, bool loop, nb::list tracks) {
            try {
                validate_publication_strings(name, uuid);
                const ParsedTracks parsed(tracks);
                const auto handle = tc_animation_publish_tracks(uuid.c_str(), name.c_str(), tps, loop,
                                                                 parsed.descriptors.data(), parsed.descriptors.size());
                if (tc_animation_handle_is_invalid(handle))
                    throw std::invalid_argument("animation track publication failed; previous clip was preserved");
                return TcAnimationClip(handle);
            } catch (const std::exception& error) {
                tc::Log::error("TcAnimationClip::publish_tracks: %s", error.what());
                throw;
            }
        }, nb::arg("name"), nb::arg("uuid"), nb::arg("tps"), nb::arg("loop"), nb::arg("tracks"))
        .def_static("publish_channels", [](const std::string& name, const std::string& uuid,
                                           double tps, bool loop, nb::list channels) {
            try {
                validate_publication_strings(name, uuid);
                const ParsedChannels parsed(channels);
                const auto handle = tc_animation_publish_channels(uuid.c_str(), name.c_str(), tps, loop,
                                                                   parsed.descriptors.data(), parsed.descriptors.size());
                if (tc_animation_handle_is_invalid(handle))
                    throw std::invalid_argument("animation channel publication failed; previous clip was preserved");
                return TcAnimationClip(handle);
            } catch (const std::exception& error) {
                tc::Log::error("TcAnimationClip::publish_channels: %s", error.what());
                throw;
            }
        }, nb::arg("name"), nb::arg("uuid"), nb::arg("tps"), nb::arg("loop"), nb::arg("channels"))
        .def_prop_ro("is_valid", &TcAnimationClip::is_valid)
        .def_prop_ro("uuid", &TcAnimationClip::uuid)
        .def_prop_ro("name", &TcAnimationClip::name)
        .def_prop_ro("version", &TcAnimationClip::version)
        .def_prop_ro("duration", &TcAnimationClip::duration)
        .def_prop_ro("tps", &TcAnimationClip::tps)
        .def_prop_ro("channel_count", &TcAnimationClip::channel_count)
        .def_prop_ro("track_count", &TcAnimationClip::track_count)
        .def_prop_ro("loop", &TcAnimationClip::loop)
        .def(
            "set_tps",
            [](TcAnimationClip& self, double value) {
                if (!self.set_tps(value)) {
                    throw std::invalid_argument("animation ticks per second must be finite and positive");
                }
            },
            nb::arg("value"))
        .def("set_loop", &TcAnimationClip::set_loop, nb::arg("value"))
        .def("ensure_loaded", &TcAnimationClip::ensure_loaded)
        .def("recompute_duration", &TcAnimationClip::recompute_duration)
        .def("find_channel", &TcAnimationClip::find_channel, nb::arg("target_name"))
        .def_prop_ro("channels", [](const TcAnimationClip& self) {
            nb::list result;
            const tc_animation* animation = self.get();
            if (animation) {
                for (size_t i = 0; i < animation->channel_count; ++i)
                    result.append(animation_channel_to_dict(animation->channels[i]));
            }
            return result;
        })
        .def_prop_ro(
            "tracks",
            [](const TcAnimationClip& self) {
                nb::list result;
                tc_animation* animation = self.get();
                if (!animation)
                    return result;
                for (size_t i = 0; i < animation->track_count; ++i)
                    result.append(animation_track_to_dict(animation->tracks[i]));
                return result;
            })
        .def(
            "set_tracks",
            [](TcAnimationClip& self, nb::list track_data) {
                const ParsedTracks parsed(track_data);
                if (!self.replace_tracks(parsed.descriptors.data(), parsed.descriptors.size()))
                    throw std::runtime_error("animation track replacement failed; previous payload was preserved");
            },
            nb::arg("tracks"))
        .def(
            "sample_track",
            [](const TcAnimationClip& self, size_t track_index, double t_seconds) -> nb::object {
                const tc_animation_track* track = self.get_track(track_index);
                if (!track)
                    throw std::out_of_range("animation track index is out of range");
                const double t_ticks = t_seconds * self.tps();
                tc_animation_track_sample_result sample{};
                if (!tc_animation_track_sample(track, t_ticks, &sample))
                    throw std::runtime_error("animation track sampling is unsupported for this path/interpolation");
                if (sample.path == TC_ANIMATION_PATH_ROTATION)
                    return nb::cast(sample.value.rotation);
                if (sample.path == TC_ANIMATION_PATH_TRANSLATION)
                    return nb::cast(sample.value.translation);
                if (sample.path == TC_ANIMATION_PATH_SCALE)
                    return nb::cast(sample.value.scale);
                throw std::runtime_error("animation sampler returned an invalid path discriminator");
            },
            nb::arg("track_index"),
            nb::arg("t_seconds"))
        .def(
            "sample",
            [](const TcAnimationClip& self, double t_seconds) {
                // Return list of dicts with sample data
                tc_animation* anim = self.get();
                if (!anim || anim->channel_count == 0) {
                    return nb::list();
                }

                std::vector<tc_channel_sample> samples(anim->channel_count);
                std::vector<std::string> names;
                names.reserve(anim->channel_count);
                for (size_t i = 0; i < anim->channel_count; ++i) {
                    names.emplace_back(anim->channels[i].target_name);
                }
                const size_t count = tc_animation_sample(anim, t_seconds, samples.data());

                nb::list result;
                for (size_t i = 0; i < count; i++) {
                    nb::dict ch_dict;
                    ch_dict["target_name"] = names[i];

                    const tc_channel_sample& s = samples[i];
                    if (s.has_translation) {
                        nb::list tr;
                        tr.append(s.translation.x);
                        tr.append(s.translation.y);
                        tr.append(s.translation.z);
                        ch_dict["translation"] = tr;
                    } else {
                        ch_dict["translation"] = nb::none();
                    }

                    if (s.has_rotation) {
                        nb::list rot;
                        rot.append(s.rotation.x);
                        rot.append(s.rotation.y);
                        rot.append(s.rotation.z);
                        rot.append(s.rotation.w);
                        ch_dict["rotation"] = rot;
                    } else {
                        ch_dict["rotation"] = nb::none();
                    }

                    if (s.has_scale) {
                        ch_dict["scale"] = s.scale;
                    } else {
                        ch_dict["scale"] = nb::none();
                    }

                    result.append(ch_dict);
                }
                return result;
            },
            nb::arg("t_seconds"))
        .def("serialize",
             [](const TcAnimationClip& self) {
                 nb::dict d;
                 if (!self.is_valid()) {
                     d["type"] = "none";
                     return d;
                 }
                 d["uuid"] = self.uuid();
                 d["name"] = self.name();
                 d["type"] = "uuid";
                 return d;
             })
        // Set channels from Python data
        // channels_data: list of dicts with:
        //   - target_name: str
        //   - translation_keys: list of (time, Vec3)
        //   - rotation_keys: list of (time, Quat)
        //   - scale_keys: list of (time, value)
        .def(
            "set_channels",
            [](TcAnimationClip& self, nb::list channels_data) {
                tc_animation* anim = self.get();
                if (!anim) {
                    tc::Log::error("TcAnimationClip::set_channels: invalid clip");
                    throw std::runtime_error("cannot set channels on an invalid animation clip");
                }

                const ParsedChannels parsed(channels_data);
                if (!tc_animation_replace_channels(self.get(), parsed.descriptors.data(), parsed.descriptors.size())) {
                    throw std::runtime_error("animation channel replacement failed; previous payload was preserved");
                }
            },
            nb::arg("channels_data"));
}

void register_animation_kind_handlers() {
    static bool registered = false;
    if (registered) {
        return;
    }

    // C++ handler for C++ fields
    tc::register_cpp_handle_kind<TcAnimationClip>("tc_animation_clip");

    nb::module_ animation_module = nb::module_::import_("termin.animation._animation_native");
    tc::KindRegistry::instance().register_type(animation_module.attr("TcAnimationClip"), "tc_animation_clip");

    // Python handler for Python fields
    tc::KindRegistry::instance().register_python(
        "tc_animation_clip",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            TcAnimationClip clip = nb::cast<TcAnimationClip>(obj);
            nb::dict d;
            if (!clip.is_valid()) {
                d["type"] = "none";
                return d;
            }
            d["uuid"] = clip.uuid();
            d["name"] = clip.name();
            d["type"] = "uuid";
            return d;
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            // Handle UUID string
            if (nb::isinstance<nb::str>(data)) {
                std::string uuid = nb::cast<std::string>(data);
                TcAnimationClip clip = TcAnimationClip::from_uuid(uuid);
                if (clip.is_valid()) {
                    clip.ensure_loaded();
                } else {
                    tc::Log::warn("tc_animation_clip deserialize: animation not found, uuid=%s", uuid.c_str());
                }
                return nb::cast(clip);
            }
            // Handle dict format
            if (nb::isinstance<nb::dict>(data)) {
                nb::dict d = nb::cast<nb::dict>(data);
                if (d.contains("uuid")) {
                    std::string uuid = nb::cast<std::string>(d["uuid"]);
                    TcAnimationClip clip = TcAnimationClip::from_uuid(uuid);
                    if (clip.is_valid()) {
                        clip.ensure_loaded();
                    } else {
                        tc::Log::warn("tc_animation_clip deserialize: animation not found, uuid=%s", uuid.c_str());
                    }
                    return nb::cast(clip);
                }
            }
            return nb::cast(TcAnimationClip());
        }));

    registered = true;
}

NB_MODULE(_animation_native, m) {
    m.doc() = "Native C++ animation module for termin";

    bind_tc_animation_clip(m);

    m.def(
        "tc_animation_declare",
        [](const std::string& uuid, const std::string& name) {
            tc_animation_handle h = tc_animation_declare(uuid.c_str(), name.empty() ? nullptr : name.c_str());
            return TcAnimationClip(h);
        },
        nb::arg("uuid"),
        nb::arg("name") = "",
        "Declare an animation that will be loaded lazily");

    m.def(
        "tc_animation_is_loaded",
        [](TcAnimationClip& handle) { return tc_animation_is_loaded(handle.handle); },
        nb::arg("handle"),
        "Check if animation data is loaded");

    m.def(
        "tc_animation_ensure_loaded",
        [](TcAnimationClip& handle) { return tc_animation_ensure_loaded(handle.handle); },
        nb::arg("handle"),
        "Ensure animation is loaded");

    m.def("tc_animation_get_all_info", []() {
        nb::list result;
        size_t count = 0;
        tc_animation_info* infos = tc_animation_get_all_info(&count);
        for (size_t i = 0; i < count; ++i) {
            nb::dict info;
            info["handle"] = nb::make_tuple(infos[i].handle.index, infos[i].handle.generation);
            info["uuid"] = std::string(infos[i].uuid);
            info["name"] = infos[i].name ? std::string(infos[i].name) : "";
            info["ref_count"] = infos[i].ref_count;
            info["version"] = infos[i].version;
            info["duration"] = infos[i].duration;
            info["channel_count"] = infos[i].channel_count;
            info["is_loaded"] = infos[i].is_loaded != 0;
            result.append(info);
        }
        free(infos);
        return result;
    });

    m.def("register_animation_kind_handlers",
          &register_animation_kind_handlers,
          "Register tc_animation_clip kind handlers explicitly.");
}
