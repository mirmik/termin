#include <array>

#include "guard_main.h"

extern "C" {
#include <termin/audio/tc_audio_clip.h>
#include <termin/audio/tc_audio_clip_registry.h>
#include <termin/audio/tc_audio_engine.h>
#include <termin/audio/tc_audio_runtime.h>
}

TEST_CASE("audio clip registry rejects stale handles across slot reuse and rebootstrap") {
    tc_audio_runtime_init();

    const tc_audio_clip_handle first = tc_audio_clip_create("audio-first");
    REQUIRE(tc_audio_clip_is_valid(first));
    REQUIRE(tc_audio_clip_destroy(first));

    const tc_audio_clip_handle replacement = tc_audio_clip_create("audio-replacement");
    REQUIRE(tc_audio_clip_is_valid(replacement));
    CHECK_FALSE(tc_audio_clip_handle_eq(first, replacement));
    CHECK_FALSE(tc_audio_clip_is_valid(first));

    tc_audio_runtime_shutdown();
    CHECK_FALSE(tc_audio_clip_is_valid(replacement));

    tc_audio_runtime_init();
    const tc_audio_clip_handle after_rebootstrap = tc_audio_clip_create("audio-rebootstrap");
    REQUIRE(tc_audio_clip_is_valid(after_rebootstrap));
    CHECK_FALSE(tc_audio_clip_handle_eq(replacement, after_rebootstrap));
    CHECK_FALSE(tc_audio_clip_is_valid(replacement));
    REQUIRE(tc_audio_clip_destroy(after_rebootstrap));
    tc_audio_runtime_shutdown();
}

TEST_CASE("audio voices reference canonical PCM clips and render without a device") {
    tc_audio_runtime_init();
    tc_audio_engine_config config = tc_audio_engine_config_default();
    config.no_device = true;
    REQUIRE(tc_audio_engine_init(&config));

    const tc_audio_clip_handle handle = tc_audio_clip_declare(
        "audio-offline",
        "offline",
        nullptr
    );
    REQUIRE(tc_audio_clip_is_valid(handle));
    tc_audio_clip* clip = tc_audio_clip_get(handle);
    REQUIRE(clip != nullptr);
    tc_audio_clip_add_ref(clip);

    std::array<float, 256> mono_frames{};
    mono_frames.fill(0.25f);
    REQUIRE(tc_audio_clip_set_pcm(
        handle,
        mono_frames.data(),
        mono_frames.size(),
        48000,
        1,
        TC_AUDIO_SAMPLE_FORMAT_F32
    ));
    CHECK(tc_audio_clip_duration_ms(handle) == 5);

    const tc_audio_voice_handle voice = tc_audio_voice_create(handle);
    REQUIRE(tc_audio_voice_is_valid(voice));
    tc_audio_voice_set_spatialization(voice, false);
    tc_audio_voice_set_volume(voice, 0.5f);
    REQUIRE(tc_audio_voice_start(voice));
    CHECK_FALSE(tc_audio_clip_unload(handle));

    std::array<float, 128 * 2> output{};
    REQUIRE(tc_audio_engine_render(output.data(), 128));
    bool has_signal = false;
    for (float sample : output) {
        if (sample != 0.0f) {
            has_signal = true;
            break;
        }
    }
    CHECK(has_signal);

    REQUIRE(tc_audio_voice_destroy(voice));
    REQUIRE(tc_audio_clip_unload(handle));
    REQUIRE(tc_audio_clip_release(clip));
    CHECK_FALSE(tc_audio_clip_is_valid(handle));
    tc_audio_runtime_shutdown();
}

TEST_CASE("Ogg Vorbis clips decode into canonical PCM and render offline") {
    tc_audio_runtime_init();
    tc_audio_engine_config config = tc_audio_engine_config_default();
    config.no_device = true;
    REQUIRE(tc_audio_engine_init(&config));

    const tc_audio_clip_handle clip_handle = tc_audio_clip_declare(
        "audio-ogg-fixture",
        "Ogg fixture",
        TERMIN_AUDIO_TEST_OGG_PATH
    );
    REQUIRE(tc_audio_clip_is_valid(clip_handle));
    REQUIRE(tc_audio_clip_ensure_loaded(clip_handle));

    const tc_audio_clip* clip = tc_audio_clip_get(clip_handle);
    REQUIRE(clip != nullptr);
    CHECK(clip->header.is_loaded != 0);
    CHECK(clip->sample_format == TC_AUDIO_SAMPLE_FORMAT_F32);
    CHECK(clip->sample_rate == 8000);
    CHECK(clip->channels == 1);
    CHECK(clip->frame_count == 400);

    const tc_audio_voice_handle voice = tc_audio_voice_create(clip_handle);
    REQUIRE(tc_audio_voice_is_valid(voice));
    tc_audio_voice_set_spatialization(voice, false);
    REQUIRE(tc_audio_voice_start(voice));

    std::array<float, 512 * 2> output{};
    REQUIRE(tc_audio_engine_render(output.data(), 512));
    bool has_signal = false;
    for (float sample : output) {
        if (sample != 0.0f) {
            has_signal = true;
            break;
        }
    }
    CHECK(has_signal);

    REQUIRE(tc_audio_voice_destroy(voice));
    CHECK_FALSE(tc_audio_clip_is_valid(clip_handle));
    tc_audio_engine_shutdown();
    tc_audio_runtime_shutdown();
}

TEST_CASE("malformed Ogg fails without publishing loaded PCM") {
    tc_audio_runtime_init();
    const tc_audio_clip_handle clip_handle = tc_audio_clip_declare(
        "audio-malformed-ogg",
        "Malformed Ogg",
        TERMIN_AUDIO_TEST_MALFORMED_OGG_PATH
    );
    REQUIRE(tc_audio_clip_is_valid(clip_handle));
    CHECK_FALSE(tc_audio_clip_ensure_loaded(clip_handle));

    const tc_audio_clip* clip = tc_audio_clip_get(clip_handle);
    REQUIRE(clip != nullptr);
    CHECK(clip->header.is_loaded == 0);
    CHECK(clip->pcm_frames == nullptr);
    CHECK(clip->frame_count == 0);
    CHECK(clip->sample_rate == 0);
    CHECK(clip->channels == 0);

    REQUIRE(tc_audio_clip_destroy(clip_handle));
    tc_audio_runtime_shutdown();
}

GUARD_TEST_MAIN();
