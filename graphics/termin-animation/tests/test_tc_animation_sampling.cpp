#include "guard_main.h"

#include <cmath>
#include <cstddef>
#include <cstring>
#include <limits>
#include <type_traits>

#include <geom/tc_quat.h>
#include <resources/tc_animation.h>
#include <resources/tc_animation_registry.h>
#include <tcbase/tc_log.h>
#include <termin/animation/tc_animation_handle.hpp>

static_assert(std::is_same_v<decltype(tc_keyframe_vec3{}.value), tc_vec3>);
static_assert(std::is_same_v<decltype(tc_keyframe_quat{}.value), tc_quat>);
static_assert(std::is_same_v<decltype(tc_channel_sample{}.translation), tc_vec3>);
static_assert(std::is_same_v<decltype(tc_channel_sample{}.rotation), tc_quat>);
static_assert(std::is_same_v<decltype(tc_animation_track{}.values.vec3_values), tc_vec3*>);
static_assert(std::is_same_v<decltype(tc_animation_track{}.values.rotation_values), tc_quat*>);
static_assert(std::is_same_v<decltype(tc_animation_cubic_rotation_key{}.in_tangent), tc_vec4>);
static_assert(std::is_same_v<decltype(tc_animation_cubic_rotation_key{}.value), tc_quat>);
static_assert(std::is_same_v<decltype(tc_animation_track_sample_result{}.value.translation), tc_vec3>);
static_assert(std::is_same_v<decltype(tc_animation_track_sample_result{}.value.rotation), tc_quat>);
static_assert(sizeof(tc_keyframe_vec3) == sizeof(double) * 4);
static_assert(offsetof(tc_keyframe_vec3, value) == sizeof(double));
static_assert(sizeof(tc_keyframe_quat) == sizeof(double) * 5);
static_assert(offsetof(tc_keyframe_quat, value) == sizeof(double));
static_assert(sizeof(tc_channel_sample) == sizeof(double) * 9);
static_assert(offsetof(tc_channel_sample, translation) == 0);
static_assert(offsetof(tc_channel_sample, rotation) == sizeof(double) * 3);
static_assert(offsetof(tc_channel_sample, scale) == sizeof(double) * 7);
static_assert(offsetof(tc_channel_sample, has_translation) == sizeof(double) * 8);

namespace {

    int error_log_count = 0;

    void capture_log(tc_log_level level, const char*) {
        if (level == TC_LOG_ERROR) {
            ++error_log_count;
        }
    }

    struct LogCapture {
        LogCapture() {
            error_log_count = 0;
            tc_log_set_callback(capture_log);
        }

        ~LogCapture() {
            tc_log_set_callback(nullptr);
        }
    };

    bool equivalent_rotation(tc_quat lhs, tc_quat rhs, double tolerance = 1.0e-12) {
        tc_quat lhs_normalized;
        tc_quat rhs_normalized;
        return tc_quat_try_normalized(lhs, 1.0e-12, &lhs_normalized) &&
               tc_quat_try_normalized(rhs, 1.0e-12, &rhs_normalized) &&
               std::abs(tc_quat_dot(lhs_normalized, rhs_normalized)) >= 1.0 - tolerance;
    }

    tc_animation_track rotation_track(double* times,
                                      tc_quat* values,
                                      tc_animation_interpolation interpolation) {
        tc_animation_track track{};
        track.path = TC_ANIMATION_PATH_ROTATION;
        track.interpolation = static_cast<uint8_t>(interpolation);
        track.key_count = 2;
        track.times = times;
        track.values.rotation_values = values;
        return track;
    }

} // namespace

TEST_CASE("bulk rotation sampling normalizes endpoints and follows the shortest path") {
    double times[2] = {0.0, 2.0};
    const double half_sqrt2 = std::sqrt(0.5);
    tc_quat values[2] = {{0.0, 0.0, 0.0, 2.0},
                         {0.0, 0.0, -3.0 * half_sqrt2, -3.0 * half_sqrt2}};
    const tc_quat original_values[2] = {values[0], values[1]};
    tc_animation_track track = rotation_track(times, values, TC_ANIMATION_INTERPOLATION_LINEAR);

    tc_animation_track_sample_result sample{};
    REQUIRE(tc_animation_track_sample(&track, 1.0, &sample));
    CHECK(sample.path == TC_ANIMATION_PATH_ROTATION);
    const tc_quat expected_midpoint = tc_quat_from_euler(tc_vec3{0.0, 0.0, 3.14159265358979323846 / 4.0});
    CHECK(equivalent_rotation(sample.value.rotation, expected_midpoint));
    CHECK(std::abs(tc_quat_norm(sample.value.rotation) - 1.0) <= 1.0e-12);
    CHECK(std::memcmp(values, original_values, sizeof(values)) == 0);

    track.interpolation = TC_ANIMATION_INTERPOLATION_STEP;
    REQUIRE(tc_animation_track_sample(&track, 1.5, &sample));
    CHECK(equivalent_rotation(sample.value.rotation, tc_quat_identity()));
    REQUIRE(tc_animation_track_sample(&track, 2.0, &sample));
    CHECK(equivalent_rotation(sample.value.rotation, tc_quat{0.0, 0.0, half_sqrt2, half_sqrt2}));
}

TEST_CASE("bulk rotation sampling rejects invalid keys and interpolation transactionally") {
    double times[2] = {0.0, 1.0};
    tc_quat values[2] = {{0.0, 0.0, 0.0, 0.0}, {0.0, 0.0, 0.0, 1.0}};
    tc_animation_track track = rotation_track(times, values, TC_ANIMATION_INTERPOLATION_LINEAR);
    tc_animation_track_sample_result sample{};
    unsigned char sentinel[sizeof(sample)];
    std::memset(sentinel, 0xA5, sizeof(sentinel));

    std::memcpy(&sample, sentinel, sizeof(sample));
    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_track_sample(&track, 0.5, &sample));
        CHECK(error_log_count > 0);
    }
    CHECK(std::memcmp(&sample, sentinel, sizeof(sample)) == 0);

    values[0].w = 1.0;
    values[1].x = std::numeric_limits<double>::quiet_NaN();
    std::memcpy(&sample, sentinel, sizeof(sample));
    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_track_sample(&track, 0.5, &sample));
        CHECK(error_log_count > 0);
    }
    CHECK(std::memcmp(&sample, sentinel, sizeof(sample)) == 0);

    values[1].x = 0.0;
    track.interpolation = 99;
    std::memcpy(&sample, sentinel, sizeof(sample));
    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_track_sample(&track, 0.5, &sample));
        CHECK(error_log_count > 0);
    }
    CHECK(std::memcmp(&sample, sentinel, sizeof(sample)) == 0);
}

TEST_CASE("typed channel sampling is normalized and transactional") {
    const double half_sqrt2 = std::sqrt(0.5);
    tc_keyframe_vec3 translation_keys[2] = {
        {0.0, {0.0, 0.0, 0.0}},
        {2.0, {2.0, 4.0, 6.0}},
    };
    tc_keyframe_quat rotation_keys[2] = {
        {0.0, {0.0, 0.0, 0.0, 2.0}},
        {2.0, {0.0, 0.0, -3.0 * half_sqrt2, -3.0 * half_sqrt2}},
    };
    tc_animation_channel channel{};
    tc_animation_channel_init(&channel);
    channel.translation_keys = translation_keys;
    channel.translation_count = 2;
    channel.rotation_keys = rotation_keys;
    channel.rotation_count = 2;

    tc_channel_sample sample{};
    REQUIRE(tc_animation_channel_sample(&channel, 1.0, &sample));
    CHECK(sample.has_translation == 1);
    CHECK(sample.translation.x == guard::Approx(1.0));
    CHECK(sample.translation.y == guard::Approx(2.0));
    CHECK(sample.translation.z == guard::Approx(3.0));
    CHECK(sample.has_rotation == 1);
    CHECK(equivalent_rotation(sample.rotation,
                              tc_quat_from_euler(tc_vec3{0.0, 0.0, 3.14159265358979323846 / 4.0})));

    rotation_keys[0].value = {0.0, 0.0, 0.0, 0.0};
    unsigned char sentinel[sizeof(sample)];
    std::memset(sentinel, 0xA5, sizeof(sentinel));
    std::memcpy(&sample, sentinel, sizeof(sample));
    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_channel_sample(&channel, 0.5, &sample));
        CHECK(error_log_count > 0);
    }
    CHECK(std::memcmp(&sample, sentinel, sizeof(sample)) == 0);
}

TEST_CASE("channel sample initialization covers the complete ABI object representation") {
    tc_channel_sample sample;
    std::memset(&sample, 0xA5, sizeof(sample));
    tc_channel_sample_init(&sample);

    CHECK(sample._pad[0] == 0);
    CHECK(sample._pad[1] == 0);
    CHECK(sample._pad[2] == 0);
    CHECK(sample._pad[3] == 0);
    CHECK(sample._pad[4] == 0);
}

TEST_CASE("typed channel sampling rejects a non-finite single-key timeline transactionally") {
    tc_keyframe_vec3 translation_key = {
        std::numeric_limits<double>::quiet_NaN(),
        {1.0, 2.0, 3.0},
    };
    tc_animation_channel channel{};
    tc_animation_channel_init(&channel);
    channel.translation_keys = &translation_key;
    channel.translation_count = 1;

    tc_channel_sample sample{};
    unsigned char sentinel[sizeof(sample)];
    std::memset(sentinel, 0xA5, sizeof(sentinel));
    std::memcpy(&sample, sentinel, sizeof(sample));
    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_channel_sample(&channel, 0.0, &sample));
        CHECK(error_log_count > 0);
    }
    CHECK(std::memcmp(&sample, sentinel, sizeof(sample)) == 0);
}

TEST_CASE("animation sampling leaves invalid channels empty and keeps topology count") {
    tc_keyframe_quat good_key = {0.0, {0.0, 0.0, 0.0, 2.0}};
    tc_keyframe_quat bad_key = {0.0, {0.0, 0.0, 0.0, 0.0}};
    tc_animation_channel channels[2]{};
    tc_animation_channel_init(&channels[0]);
    tc_animation_channel_init(&channels[1]);
    channels[0].rotation_keys = &good_key;
    channels[0].rotation_count = 1;
    channels[1].rotation_keys = &bad_key;
    channels[1].rotation_count = 1;
    tc_animation animation{};
    animation.channels = channels;
    animation.channel_count = 2;
    animation.tps = 1.0;

    tc_channel_sample samples[2];
    std::memset(samples, 0xA5, sizeof(samples));
    {
        LogCapture capture;
        CHECK(tc_animation_sample(&animation, 0.0, samples) == 2);
        CHECK(error_log_count > 0);
    }
    CHECK(samples[0].has_rotation == 1);
    CHECK(equivalent_rotation(samples[0].rotation, tc_quat_identity()));
    CHECK(samples[1].has_translation == 0);
    CHECK(samples[1].has_rotation == 0);
    CHECK(samples[1].has_scale == 0);
}

TEST_CASE("bulk publication owns typed values and normalizes linear and step rotations") {
    tc_animation animation{};
    animation.tps = 1.0;
    animation.header.version = 7;
    double times[2] = {0.0, 1.0};
    double translation_values[6] = {1.0, 2.0, 3.0, 4.0, 5.0, 6.0};
    double rotation_values[8] = {0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 3.0, 3.0};
    double step_rotation_values[8] = {0.0, 2.0, 0.0, 0.0, 4.0, 0.0, 0.0, 0.0};
    const double source_rotations[8] = {0.0, 0.0, 0.0, 2.0, 0.0, 0.0, 3.0, 3.0};
    const tc_animation_track_desc tracks[3] = {
        {2, TC_ANIMATION_PATH_TRANSLATION, TC_ANIMATION_INTERPOLATION_LINEAR, 3, 2, 6, times, translation_values},
        {2, TC_ANIMATION_PATH_ROTATION, TC_ANIMATION_INTERPOLATION_LINEAR, 4, 2, 8, times, rotation_values},
        {3, TC_ANIMATION_PATH_ROTATION, TC_ANIMATION_INTERPOLATION_STEP, 4, 2, 8, times, step_rotation_values},
    };

    REQUIRE(tc_animation_replace_tracks(&animation, tracks, 3));
    REQUIRE(animation.track_count == 3);
    CHECK((animation.tracks[0].values.vec3_values[0] == tc_vec3{1.0, 2.0, 3.0}));
    CHECK((animation.tracks[0].values.vec3_values[1] == tc_vec3{4.0, 5.0, 6.0}));
    CHECK(equivalent_rotation(animation.tracks[1].values.rotation_values[0], tc_quat_identity()));
    CHECK(std::abs(tc_quat_norm(animation.tracks[1].values.rotation_values[1]) - 1.0) <= 1.0e-12);
    CHECK(std::abs(tc_quat_norm(animation.tracks[2].values.rotation_values[0]) - 1.0) <= 1.0e-12);
    CHECK(std::abs(tc_quat_norm(animation.tracks[2].values.rotation_values[1]) - 1.0) <= 1.0e-12);
    CHECK(std::memcmp(rotation_values, source_rotations, sizeof(rotation_values)) == 0);

    const uint32_t version = animation.header.version;
    double invalid_rotation[8] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0};
    const tc_animation_track_desc invalid = {
        2, TC_ANIMATION_PATH_ROTATION, TC_ANIMATION_INTERPOLATION_LINEAR, 4, 2, 8, times, invalid_rotation};
    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_replace_tracks(&animation, &invalid, 1));
        CHECK(error_log_count > 0);
    }
    CHECK(animation.header.version == version);
    CHECK(animation.track_count == 3);
    CHECK((animation.tracks[0].values.vec3_values[1] == tc_vec3{4.0, 5.0, 6.0}));

    REQUIRE(tc_animation_replace_tracks(&animation, nullptr, 0));
}

TEST_CASE("cubic rotation publication normalizes values but preserves vec4 derivatives") {
    tc_animation animation{};
    animation.tps = 1.0;
    animation.header.version = 11;
    double times[2] = {0.0, 2.0};
    const double half_sqrt2 = std::sqrt(0.5);
    double values[24] = {
        0.0, 0.0, 0.0, 0.0, // key 0 in tangent: zero is valid
        0.0, 0.0, 0.0, 2.0, // key 0 value
        1.0, 2.0, 3.0, 4.0, // key 0 out tangent
        -4.0, -3.0, -2.0, -1.0, // key 1 in tangent
        0.0, 0.0, 3.0 * half_sqrt2, 3.0 * half_sqrt2, // key 1 value
        0.0, 0.0, 0.0, 0.0, // key 1 out tangent
    };
    double source_values[24];
    std::memcpy(source_values, values, sizeof(values));
    const tc_animation_track_desc descriptor = {
        5, TC_ANIMATION_PATH_ROTATION, TC_ANIMATION_INTERPOLATION_CUBIC_SPLINE, 4, 2, 24, times, values};

    REQUIRE(tc_animation_replace_tracks(&animation, &descriptor, 1));
    REQUIRE(animation.track_count == 1);
    const tc_animation_cubic_rotation_key* keys = animation.tracks[0].values.cubic_rotation_keys;
    REQUIRE(keys != nullptr);
    CHECK(keys[0].in_tangent == tc_vec4::zero());
    CHECK(equivalent_rotation(keys[0].value, tc_quat_identity()));
    CHECK((keys[0].out_tangent == tc_vec4{1.0, 2.0, 3.0, 4.0}));
    CHECK((keys[1].in_tangent == tc_vec4{-4.0, -3.0, -2.0, -1.0}));
    CHECK(std::abs(tc_quat_norm(keys[1].value) - 1.0) <= 1.0e-12);
    CHECK(keys[1].out_tangent == tc_vec4::zero());
    CHECK(std::memcmp(values, source_values, sizeof(values)) == 0);

    const uint32_t version = animation.header.version;
    values[4] = 0.0;
    values[5] = 0.0;
    values[6] = 0.0;
    values[7] = 0.0;
    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_replace_tracks(&animation, &descriptor, 1));
        CHECK(error_log_count > 0);
    }
    CHECK(animation.header.version == version);
    CHECK((animation.tracks[0].values.cubic_rotation_keys[0].out_tangent == tc_vec4{1.0, 2.0, 3.0, 4.0}));

    std::memcpy(values, source_values, sizeof(values));
    values[0] = std::numeric_limits<double>::infinity();
    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_replace_tracks(&animation, &descriptor, 1));
        CHECK(error_log_count > 0);
    }
    CHECK(animation.header.version == version);
    CHECK(animation.track_count == 1);

    REQUIRE(tc_animation_replace_tracks(&animation, nullptr, 0));
}

TEST_CASE("typed vec3 and legacy scalar sampling cover opposite full-range endpoints") {
    const double largest = std::numeric_limits<double>::max();
    double times[2] = {0.0, 2.0};
    double values[6] = {-largest, largest, -largest, largest, -largest, largest};
    const tc_animation_track_desc descriptors[2] = {
        {0, TC_ANIMATION_PATH_TRANSLATION, TC_ANIMATION_INTERPOLATION_LINEAR, 3, 2, 6, times, values},
        {0, TC_ANIMATION_PATH_SCALE, TC_ANIMATION_INTERPOLATION_LINEAR, 3, 2, 6, times, values},
    };
    tc_animation animation{};
    animation.tps = 1.0;
    REQUIRE(tc_animation_replace_tracks(&animation, descriptors, 2));

    tc_animation_track_sample_result sample{};
    REQUIRE(tc_animation_track_sample(&animation.tracks[0], 1.0, &sample));
    CHECK(sample.path == TC_ANIMATION_PATH_TRANSLATION);
    CHECK(sample.value.translation == tc_vec3::zero());
    REQUIRE(tc_animation_track_sample(&animation.tracks[1], 1.0, &sample));
    CHECK(sample.path == TC_ANIMATION_PATH_SCALE);
    CHECK(sample.value.scale == tc_vec3::zero());
    REQUIRE(tc_animation_track_sample(&animation.tracks[0], 0.0, &sample));
    CHECK((sample.value.translation == tc_vec3{-largest, largest, -largest}));

    tc_keyframe_scalar scalar_keys[2] = {{0.0, -largest}, {2.0, largest}};
    tc_animation_channel channel{};
    tc_animation_channel_init(&channel);
    channel.scale_keys = scalar_keys;
    channel.scale_count = 2;
    tc_channel_sample channel_sample{};
    REQUIRE(tc_animation_channel_sample(&channel, 1.0, &channel_sample));
    CHECK(channel_sample.has_scale == 1);
    CHECK(channel_sample.scale == 0.0);

    REQUIRE(tc_animation_replace_tracks(&animation, nullptr, 0));
}

TEST_CASE("channel replacement is transactional and becomes the authoritative payload") {
    tc_animation_init();
    {
        termin::animation::TcAnimationClip clip =
            termin::animation::TcAnimationClip::create("replacement", "animation-channel-replacement");
        REQUIRE(clip.is_valid());

        double track_times[2] = {0.0, 1.0};
        double track_values[6] = {0.0, 0.0, 0.0, 2.0, 4.0, 6.0};
        const tc_animation_track_desc track_desc = {
            3,
            TC_ANIMATION_PATH_TRANSLATION,
            TC_ANIMATION_INTERPOLATION_LINEAR,
            3,
            2,
            6,
            track_times,
            track_values,
        };
        REQUIRE(clip.replace_tracks(&track_desc, 1));

        tc_animation_track_sample_result track_sample{};
        REQUIRE(tc_animation_track_sample(clip.get_track(0), 0.5, &track_sample));
        CHECK(track_sample.path == TC_ANIMATION_PATH_TRANSLATION);
        CHECK(track_sample.value.translation.x == guard::Approx(1.0));
        CHECK(track_sample.value.translation.y == guard::Approx(2.0));
        CHECK(track_sample.value.translation.z == guard::Approx(3.0));

        const uint32_t version = clip.version();
        double invalid_rotation_values[8] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0};
        const tc_animation_track_desc invalid_track_desc = {
            3,
            TC_ANIMATION_PATH_ROTATION,
            TC_ANIMATION_INTERPOLATION_LINEAR,
            4,
            2,
            8,
            track_times,
            invalid_rotation_values,
        };
        {
            LogCapture capture;
            CHECK_FALSE(clip.replace_tracks(&invalid_track_desc, 1));
            CHECK(error_log_count > 0);
        }
        CHECK(clip.version() == version);
        CHECK(clip.channel_count() == 0);
        CHECK(clip.track_count() == 1);
        REQUIRE(tc_animation_track_sample(clip.get_track(0), 0.5, &track_sample));
        CHECK(track_sample.value.translation.y == guard::Approx(2.0));

        const tc_keyframe_quat invalid_rotation = {0.0, {0.0, 0.0, 0.0, 0.0}};
        const tc_animation_channel_desc invalid_channel = {
            "Broken",
            nullptr,
            0,
            &invalid_rotation,
            1,
            nullptr,
            0,
        };
        {
            LogCapture capture;
            CHECK_FALSE(tc_animation_replace_channels(clip.get(), &invalid_channel, 1));
            CHECK(error_log_count > 0);
        }
        CHECK(clip.version() == version);
        CHECK(clip.channel_count() == 0);
        CHECK(clip.track_count() == 1);

        const tc_keyframe_quat valid_rotation = {0.0, {0.0, 0.0, 0.0, 2.0}};
        const tc_animation_channel_desc valid_channel = {
            "Root",
            nullptr,
            0,
            &valid_rotation,
            1,
            nullptr,
            0,
        };
        REQUIRE(tc_animation_replace_channels(clip.get(), &valid_channel, 1));
        CHECK(clip.channel_count() == 1);
        CHECK(clip.track_count() == 0);

        const uint32_t channel_version = clip.version();
        {
            LogCapture capture;
            CHECK_FALSE(tc_animation_replace_channels(clip.get(), &invalid_channel, 1));
            CHECK(error_log_count > 0);
        }
        CHECK(clip.version() == channel_version);
        CHECK(clip.channel_count() == 1);
        CHECK(clip.track_count() == 0);
        tc_channel_sample channel_sample{};
        REQUIRE(tc_animation_channel_sample(clip.get_channel(0), 0.0, &channel_sample));
        CHECK(channel_sample.has_rotation == 1);
        CHECK(equivalent_rotation(channel_sample.rotation, tc_quat_identity()));
    }
    tc_animation_shutdown();
}

TEST_CASE("bulk replacement rejects byte-size overflow before reading descriptors") {
    double dummy = 0.0;
    const size_t huge_key_count = std::numeric_limits<size_t>::max() / sizeof(double) + 1;
    const tc_animation_track_desc descriptor = {
        0,
        TC_ANIMATION_PATH_TRANSLATION,
        TC_ANIMATION_INTERPOLATION_LINEAR,
        3,
        huge_key_count,
        huge_key_count * 3,
        &dummy,
        &dummy,
    };
    tc_animation animation{};
    animation.header.version = 17;

    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_replace_tracks(&animation, &descriptor, 1));
        CHECK(error_log_count > 0);
    }
    CHECK(animation.header.version == 17);
    CHECK(animation.channels == nullptr);
    CHECK(animation.tracks == nullptr);
}

TEST_CASE("standalone samplers reject impossible key storage transactionally") {
    double dummy_value = 0.0;
    tc_vec3 dummy_vector = {1.0, 2.0, 3.0};
    const size_t huge_double_count = std::numeric_limits<size_t>::max() / sizeof(double) + 1;
    tc_animation_track track{};
    track.path = TC_ANIMATION_PATH_TRANSLATION;
    track.interpolation = TC_ANIMATION_INTERPOLATION_STEP;
    track.key_count = huge_double_count;
    track.times = &dummy_value;
    track.values.vec3_values = &dummy_vector;

    tc_animation_track_sample_result track_output{};
    unsigned char track_sentinel[sizeof(track_output)];
    std::memset(track_sentinel, 0xA5, sizeof(track_sentinel));
    std::memcpy(&track_output, track_sentinel, sizeof(track_output));
    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_track_sample(&track, 0.0, &track_output));
        CHECK(error_log_count > 0);
    }
    CHECK(std::memcmp(&track_output, track_sentinel, sizeof(track_output)) == 0);

    tc_keyframe_vec3 dummy_key = {0.0, {1.0, 2.0, 3.0}};
    tc_animation_channel channel{};
    tc_animation_channel_init(&channel);
    channel.translation_keys = &dummy_key;
    channel.translation_count = std::numeric_limits<size_t>::max() / sizeof(tc_keyframe_vec3) + 1;

    tc_channel_sample channel_output;
    unsigned char channel_sentinel[sizeof(channel_output)];
    std::memset(channel_sentinel, 0xA5, sizeof(channel_sentinel));
    std::memcpy(&channel_output, channel_sentinel, sizeof(channel_output));
    {
        LogCapture capture;
        CHECK_FALSE(tc_animation_channel_sample(&channel, 0.0, &channel_output));
        CHECK(error_log_count > 0);
    }
    CHECK(std::memcmp(&channel_output, channel_sentinel, sizeof(channel_output)) == 0);
}

TEST_CASE("TcAnimationClip sample_into rejects undersized output before writing") {
    tc_animation_init();
    {
        termin::animation::TcAnimationClip clip =
            termin::animation::TcAnimationClip::create("capacity", "animation-capacity-regression");
        REQUIRE(clip.is_valid());
        const tc_animation_channel_desc channels[2] = {
            {"First", nullptr, 0, nullptr, 0, nullptr, 0},
            {"Second", nullptr, 0, nullptr, 0, nullptr, 0},
        };
        REQUIRE(tc_animation_replace_channels(clip.get(), channels, 2));

        tc_channel_sample output[2];
        unsigned char sentinel[sizeof(output)];
        std::memset(sentinel, 0xA5, sizeof(sentinel));
        std::memcpy(output, sentinel, sizeof(output));
        {
            LogCapture capture;
            CHECK(clip.sample_into(0.0, output, 1) == 0);
            CHECK(error_log_count > 0);
        }
        CHECK(std::memcmp(output, sentinel, sizeof(output)) == 0);
    }
    tc_animation_shutdown();
}

TEST_CASE("TcAnimationClip set_tps validates input and recomputes active payload duration") {
    tc_animation_init();
    {
        termin::animation::TcAnimationClip clip =
            termin::animation::TcAnimationClip::create("tps", "animation-tps-regression");
        REQUIRE(clip.is_valid());

        const tc_keyframe_vec3 channel_key = {60.0, {1.0, 2.0, 3.0}};
        const tc_animation_channel_desc channel = {
            "Root",
            &channel_key,
            1,
            nullptr,
            0,
            nullptr,
            0,
        };
        REQUIRE(tc_animation_replace_channels(clip.get(), &channel, 1));
        CHECK(clip.duration() == guard::Approx(2.0));
        REQUIRE(clip.set_tps(20.0));
        CHECK(clip.tps() == guard::Approx(20.0));
        CHECK(clip.duration() == guard::Approx(3.0));

        double track_times[2] = {0.0, 100.0};
        double track_values[6] = {0.0, 0.0, 0.0, 1.0, 2.0, 3.0};
        const tc_animation_track_desc track = {
            0,
            TC_ANIMATION_PATH_TRANSLATION,
            TC_ANIMATION_INTERPOLATION_LINEAR,
            3,
            2,
            6,
            track_times,
            track_values,
        };
        REQUIRE(clip.replace_tracks(&track, 1));
        CHECK(clip.duration() == guard::Approx(5.0));
        REQUIRE(clip.set_tps(25.0));
        CHECK(clip.duration() == guard::Approx(4.0));

        const double tps = clip.tps();
        const double duration = clip.duration();
        {
            LogCapture capture;
            CHECK_FALSE(clip.set_tps(0.0));
            CHECK_FALSE(clip.set_tps(std::numeric_limits<double>::quiet_NaN()));
            CHECK_FALSE(clip.set_tps(std::numeric_limits<double>::infinity()));
            CHECK(error_log_count == 3);
        }
        CHECK(clip.tps() == tps);
        CHECK(clip.duration() == duration);
    }
    tc_animation_shutdown();
}

GUARD_TEST_MAIN();
