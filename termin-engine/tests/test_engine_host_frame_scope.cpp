#include "guard_main.h"

#include <stdexcept>
#include <string>
#include <utility>

#include <termin/engine/engine_core.hpp>

extern "C" {
#include "tc_profiler.h"
}

namespace {

    class CaptureFixture {
    public:
        explicit CaptureFixture(bool profile_sections)
            : capture(tc_profiler_capture_create(8)) {
            if (!capture) {
                throw std::runtime_error("failed to create profiler capture fixture");
            }
            tc_profiler_capture_set_profiling(capture, profile_sections);
            tc_profiler_capture_set_active(capture, true);
        }

        ~CaptureFixture() {
            tc_profiler_capture_destroy(capture);
            tc_profiler_clear_history();
        }

        tc_profiler_capture* capture = nullptr;
    };

    termin::EngineHostFrameCadence cadence(double start_ms, double interval_ms) {
        return termin::EngineHostFrameCadence{
            start_ms,
            interval_ms,
            16.0,
            1.5,
            0,
        };
    }

} // namespace

TEST_CASE("Host frame scope completes external cadence and section data") {
    CaptureFixture fixture(true);

    {
        termin::EngineHostFrameScope frame(cadence(100.0, 16.5));
        REQUIRE(frame.active());
        tc_profiler_begin_section("Android Host");
        tc_profiler_end_section();
    }

    REQUIRE_EQ(tc_profiler_capture_count(fixture.capture), 1);
    const tc_frame_profile* completed = tc_profiler_capture_at(fixture.capture, 0);
    REQUIRE(completed != nullptr);
    CHECK_EQ(completed->start_time_ms, 100.0);
    CHECK_EQ(completed->interval_ms, 16.5);
    CHECK_EQ(completed->target_interval_ms, 16.0);
    CHECK_EQ(completed->deadline_lateness_ms, 1.5);
    CHECK(completed->sections_profiled);
    REQUIRE_EQ(completed->section_count, 1);
    CHECK_EQ(std::string(completed->sections[0].name), std::string("Android Host"));
}

TEST_CASE("Host frame scope transfers ownership when moved") {
    CaptureFixture fixture(false);

    {
        termin::EngineHostFrameScope first(cadence(200.0, 0.0));
        REQUIRE(first.active());
        termin::EngineHostFrameScope second(std::move(first));
        CHECK_FALSE(first.active());
        CHECK(second.active());
    }

    CHECK_EQ(tc_profiler_capture_count(fixture.capture), 1);
}

TEST_CASE("Nested host frame scope is inert and cannot close the outer frame") {
    CaptureFixture fixture(false);

    {
        termin::EngineHostFrameScope outer(cadence(300.0, 16.0));
        REQUIRE(outer.active());
        {
            termin::EngineHostFrameScope nested(cadence(301.0, 1.0));
            CHECK_FALSE(nested.active());
        }
        CHECK(tc_profiler_current_frame() != nullptr);
    }

    CHECK_EQ(tc_profiler_capture_count(fixture.capture), 1);
}

TEST_CASE("Standalone tick_and_render does not silently own a profiler frame") {
    CaptureFixture fixture(true);
    termin::EngineCore engine;

    (void)engine.tick_and_render(0.0);

    CHECK_EQ(tc_profiler_capture_count(fixture.capture), 0);
    CHECK(tc_profiler_current_frame() == nullptr);
}

GUARD_TEST_MAIN();
