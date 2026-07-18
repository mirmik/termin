#include "guard_main.h"

#include "termin/editor/frame_profiler_controller.hpp"

#include <tc_profiler.h>
#include <termin/engine/engine_core.hpp>

TEST_CASE("Frame profiler controller keeps capture data and projections native") {
    termin::EngineCore engine;
    termin::FrameProfilerController controller(engine, 3, 1.25);
    controller.start_capture();
    CHECK(controller.capturing());
    CHECK(tc_profiler_frame_capture_enabled());
    CHECK(!controller.profiling());
    CHECK(!tc_profiler_enabled());

    for (int index = 0; index < 4; ++index) {
        if (index == 1) controller.set_profiling(true);
        const tc_profiler_frame_info info{
            1000.0 + index * 16.0,
            16.0 + index * 4.0,
            16.0,
            index * 4.0,
            index == 3 ? 1 : 0,
        };
        tc_profiler_begin_frame_with_info(&info);
        tc_profiler_begin_section("Render");
        tc_profiler_begin_section("Opaque");
        tc_profiler_end_section();
        tc_profiler_end_section();
        tc_profiler_end_frame();
    }

    CHECK(controller.update());
    CHECK(controller.timeline_model()->samples().size() == 3);
    CHECK(controller.section_model()->size() == 2);
    CHECK(controller.selected_frame_number() >= 0);
    CHECK(controller.summary_model()->text().find("3 frames") != std::string::npos);
    CHECK(controller.status_model()->text().find("overwritten: 1") != std::string::npos);

    const int selected = controller.selected_frame_number();
    CHECK(controller.select_frame(selected - 1));
    CHECK(!controller.follow_latest());
    controller.clear();
    CHECK(controller.timeline_model()->samples().empty());
    CHECK(controller.section_model()->empty());
    CHECK(controller.capturing());

    controller.close();
    CHECK(!tc_profiler_enabled());
    CHECK(!tc_profiler_frame_capture_enabled());
}

TEST_CASE("Native capture and legacy profiler enable requests compose") {
    termin::EngineCore engine;
    termin::FrameProfilerController controller(engine, 4, 1.25);
    tc_profiler_set_enabled(true);
    controller.start_capture();
    CHECK(controller.summary_model()->text().find("profiling external") !=
          std::string::npos);
    controller.set_profiling(true);
    controller.pause();
    CHECK(tc_profiler_enabled());
    tc_profiler_set_enabled(false);
    CHECK(!tc_profiler_enabled());
    CHECK(!tc_profiler_frame_capture_enabled());
}
