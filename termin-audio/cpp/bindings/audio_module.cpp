#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <termin/audio/tc_audio_clip.hpp>
#include <termin/audio/tc_audio_engine.h>
#include <termin/audio/tc_audio_runtime.h>
#include <termin/audio/tc_audio_voice.hpp>

namespace nb = nanobind;
using termin::audio::TcAudioClip;
using termin::audio::TcAudioVoice;

NB_MODULE(_audio_native, module) {
    tc_audio_runtime_init();

    nb::class_<TcAudioClip>(module, "TcAudioClip")
        .def(nb::init<>())
        .def_prop_ro("is_valid", &TcAudioClip::is_valid)
        .def_prop_ro("is_loaded", &TcAudioClip::is_loaded)
        .def_prop_ro("uuid", &TcAudioClip::uuid)
        .def_prop_ro("name", &TcAudioClip::name)
        .def_prop_ro("source_path", &TcAudioClip::source_path)
        .def_prop_ro("version", &TcAudioClip::version)
        .def_prop_ro("frame_count", &TcAudioClip::frame_count)
        .def_prop_ro("sample_rate", &TcAudioClip::sample_rate)
        .def_prop_ro("channels", &TcAudioClip::channels)
        .def_prop_ro("duration", &TcAudioClip::duration)
        .def_prop_ro("duration_ms", &TcAudioClip::duration_ms)
        .def("load_file", &TcAudioClip::load_file, nb::arg("path") = "")
        .def("ensure_loaded", &TcAudioClip::ensure_loaded)
        .def("unload", &TcAudioClip::unload)
        .def("set_name", &TcAudioClip::set_name, nb::arg("name"))
        .def("set_source_path", &TcAudioClip::set_source_path, nb::arg("source_path"))
        .def_static("from_uuid", &TcAudioClip::from_uuid, nb::arg("uuid"))
        .def_static(
            "declare",
            &TcAudioClip::declare,
            nb::arg("uuid"),
            nb::arg("name") = "",
            nb::arg("source_path") = ""
        )
        .def("serialize", [](const TcAudioClip& clip) {
            nb::dict result;
            if (!clip.is_valid()) {
                result["type"] = "none";
                return result;
            }
            result["type"] = "uuid";
            result["uuid"] = clip.uuid();
            result["name"] = clip.name();
            return result;
        })
        .def_static("deserialize", [](nb::dict data) {
            if (!data.contains("uuid")) return TcAudioClip();
            return TcAudioClip::from_uuid(nb::cast<std::string>(data["uuid"]));
        }, nb::arg("data"))
        .def("__repr__", [](const TcAudioClip& clip) {
            if (!clip.is_valid()) return std::string("<TcAudioClip invalid>");
            return "<TcAudioClip '" + clip.name() + "' uuid='" + clip.uuid() + "'>";
        });

    nb::class_<TcAudioVoice>(module, "TcAudioVoice")
        .def(nb::init<>())
        .def_prop_ro("is_valid", &TcAudioVoice::is_valid)
        .def_prop_ro("is_playing", &TcAudioVoice::is_playing)
        .def_prop_ro("is_paused", &TcAudioVoice::is_paused)
        .def("start", &TcAudioVoice::start)
        .def("stop", &TcAudioVoice::stop, nb::arg("fade_out_ms") = 0)
        .def("pause", &TcAudioVoice::pause)
        .def("resume", &TcAudioVoice::resume)
        .def("destroy", &TcAudioVoice::destroy)
        .def_prop_rw(
            "looping",
            [](const TcAudioVoice& voice) { return tc_audio_voice_is_looping(voice.handle); },
            [](TcAudioVoice& voice, bool value) { tc_audio_voice_set_looping(voice.handle, value); }
        )
        .def_prop_rw(
            "volume",
            [](const TcAudioVoice& voice) { return tc_audio_voice_get_volume(voice.handle); },
            [](TcAudioVoice& voice, float value) { tc_audio_voice_set_volume(voice.handle, value); }
        )
        .def_prop_rw(
            "pitch",
            [](const TcAudioVoice& voice) { return tc_audio_voice_get_pitch(voice.handle); },
            [](TcAudioVoice& voice, float value) { tc_audio_voice_set_pitch(voice.handle, value); }
        )
        .def("set_spatialization", [](TcAudioVoice& voice, bool enabled) {
            tc_audio_voice_set_spatialization(voice.handle, enabled);
        }, nb::arg("enabled"))
        .def("set_position", [](TcAudioVoice& voice, float x, float y, float z) {
            tc_audio_voice_set_position(voice.handle, x, y, z);
        }, nb::arg("x"), nb::arg("y"), nb::arg("z"))
        .def("get_position", [](const TcAudioVoice& voice) {
            float x = 0.0f;
            float y = 0.0f;
            float z = 0.0f;
            tc_audio_voice_get_position(voice.handle, &x, &y, &z);
            return nb::make_tuple(x, y, z);
        })
        .def("set_velocity", [](TcAudioVoice& voice, float x, float y, float z) {
            tc_audio_voice_set_velocity(voice.handle, x, y, z);
        }, nb::arg("x"), nb::arg("y"), nb::arg("z"))
        .def("set_distance_range", [](TcAudioVoice& voice, float minimum, float maximum) {
            tc_audio_voice_set_distance_range(voice.handle, minimum, maximum);
        }, nb::arg("minimum"), nb::arg("maximum"))
        .def_static("create", &TcAudioVoice::create, nb::arg("clip"));

    module.def("engine_initialize", [](bool no_device, uint32_t sample_rate, uint16_t channels) {
        tc_audio_engine_config config = tc_audio_engine_config_default();
        config.no_device = no_device;
        config.sample_rate = sample_rate;
        config.channels = channels;
        return tc_audio_engine_init(&config);
    }, nb::arg("no_device") = false, nb::arg("sample_rate") = 48000, nb::arg("channels") = 2);
    module.def("engine_shutdown", &tc_audio_engine_shutdown);
    module.def("engine_is_initialized", &tc_audio_engine_is_initialized);
    module.def("engine_has_device", &tc_audio_engine_has_device);
    module.def("engine_sample_rate", &tc_audio_engine_sample_rate);
    module.def("engine_channels", &tc_audio_engine_channels);
    module.def("engine_set_master_volume", &tc_audio_engine_set_master_volume, nb::arg("volume"));
    module.def("engine_get_master_volume", &tc_audio_engine_get_master_volume);
    module.def("engine_set_listener_position", &tc_audio_engine_set_listener_position);
    module.def("engine_get_listener_position", []() {
        float x = 0.0f;
        float y = 0.0f;
        float z = 0.0f;
        tc_audio_engine_get_listener_position(&x, &y, &z);
        return nb::make_tuple(x, y, z);
    });
    module.def("engine_set_listener_direction", &tc_audio_engine_set_listener_direction);
    module.def("engine_set_listener_velocity", &tc_audio_engine_set_listener_velocity);
    module.def("voice_count", &tc_audio_voice_count);
    module.def("voice_capacity", &tc_audio_voice_capacity);
    module.def("voice_is_playing_at", [](size_t index) {
        return tc_audio_voice_is_playing(tc_audio_voice_at(index));
    });
    module.def("voice_is_paused_at", [](size_t index) {
        return tc_audio_voice_is_paused(tc_audio_voice_at(index));
    });
    module.def("voice_volume_at", [](size_t index) {
        return tc_audio_voice_get_volume(tc_audio_voice_at(index));
    });
    module.def("voice_position_at", [](size_t index) {
        float x = 0.0f;
        float y = 0.0f;
        float z = 0.0f;
        tc_audio_voice_get_position(tc_audio_voice_at(index), &x, &y, &z);
        return nb::make_tuple(x, y, z);
    });
}
