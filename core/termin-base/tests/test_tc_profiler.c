#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "guard_c.h"

#include <tc_profiler.h>

// Four distinct sections per branch, at a maximum depth of four. Names shared
// by different parents must remain independent; repeated calls under one
// parent must aggregate even after scratch storage has grown.
static void record_wide_profile(int branches, int repetitions) {
    for (int repeat = 0; repeat < repetitions; ++repeat) {
        tc_profiler_begin_section("Wide root");
        for (int branch = 0; branch < branches; ++branch) {
            char name[32];
            snprintf(name, sizeof(name), "branch-%d", branch);
            tc_profiler_begin_section(name);
            for (int call = 0; call < 2; ++call) {
                tc_profiler_begin_section("Shared");
                tc_profiler_begin_section("Leaf");
                tc_profiler_end_section();
                tc_profiler_end_section();
            }
            tc_profiler_begin_section("Sibling");
            tc_profiler_end_section();
            tc_profiler_end_section();
        }
        tc_profiler_end_section();
    }
}

static void check_wide_profile(const tc_frame_profile* frame, int branches, int repetitions) {
    GUARD_C_CHECK(frame != NULL);
    if (!frame)
        return;
    GUARD_C_CHECK(frame->section_count == 1 + branches * 4);
    GUARD_C_CHECK(frame->sections != NULL);
    if (frame->section_count != 1 + branches * 4 || !frame->sections)
        return;
    const tc_section_timing* root = &frame->sections[0];
    GUARD_C_CHECK(strcmp(root->name, "Wide root") == 0);
    GUARD_C_CHECK(root->parent_index == -1);
    GUARD_C_CHECK(root->next_sibling == -1);
    GUARD_C_CHECK(root->first_child == 1);
    GUARD_C_CHECK(root->call_count == repetitions);
    double root_children_ms = 0.0;
    for (int branch = 0; branch < branches; ++branch) {
        const int index = 1 + branch * 4;
        const tc_section_timing* parent = &frame->sections[index];
        const tc_section_timing* shared = &frame->sections[index + 1];
        const tc_section_timing* leaf = &frame->sections[index + 2];
        const tc_section_timing* sibling = &frame->sections[index + 3];
        char name[32];
        snprintf(name, sizeof(name), "branch-%d", branch);
        GUARD_C_CHECK(strcmp(parent->name, name) == 0);
        GUARD_C_CHECK(parent->parent_index == 0);
        GUARD_C_CHECK(parent->first_child == index + 1);
        GUARD_C_CHECK(parent->next_sibling == (branch + 1 < branches ? index + 4 : -1));
        GUARD_C_CHECK(parent->call_count == repetitions);
        GUARD_C_CHECK(strcmp(shared->name, "Shared") == 0);
        GUARD_C_CHECK(shared->parent_index == index);
        GUARD_C_CHECK(shared->first_child == index + 2);
        GUARD_C_CHECK(shared->next_sibling == index + 3);
        GUARD_C_CHECK(shared->call_count == repetitions * 2);
        GUARD_C_CHECK(strcmp(leaf->name, "Leaf") == 0);
        GUARD_C_CHECK(leaf->parent_index == index + 1);
        GUARD_C_CHECK(leaf->first_child == -1);
        GUARD_C_CHECK(leaf->next_sibling == -1);
        GUARD_C_CHECK(leaf->call_count == repetitions * 2);
        GUARD_C_CHECK(leaf->children_ms == 0.0);
        GUARD_C_CHECK(strcmp(sibling->name, "Sibling") == 0);
        GUARD_C_CHECK(sibling->parent_index == index);
        GUARD_C_CHECK(sibling->first_child == -1);
        GUARD_C_CHECK(sibling->next_sibling == -1);
        GUARD_C_CHECK(sibling->call_count == repetitions);
        GUARD_C_CHECK(sibling->children_ms == 0.0);
        GUARD_C_CHECK_NEAR_DOUBLE(shared->cpu_ms + sibling->cpu_ms, parent->children_ms, 1e-6);
        GUARD_C_CHECK_NEAR_DOUBLE(leaf->cpu_ms, shared->children_ms, 1e-6);
        root_children_ms += parent->cpu_ms;
    }
    GUARD_C_CHECK_NEAR_DOUBLE(root_children_ms, root->children_ms, 1e-6);
    for (int index = 0; index < frame->section_count; ++index) {
        const tc_section_timing* section = &frame->sections[index];
        GUARD_C_CHECK(isfinite(section->cpu_ms));
        GUARD_C_CHECK(isfinite(section->children_ms));
        GUARD_C_CHECK(section->cpu_ms >= 0.0);
        GUARD_C_CHECK(section->children_ms >= 0.0);
        GUARD_C_CHECK(section->cpu_ms + 1e-6 >= section->children_ms);
    }
}

GUARD_C_TEST(test_profiler_preserves_thousands_of_shallow_sections_and_reuses_storage) {
    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    tc_profiler_begin_frame();
    record_wide_profile(500, 2);
    const tc_frame_profile* current = tc_profiler_current_frame();
    check_wide_profile(current, 500, 2);
    tc_section_timing* scratch = current->sections;
    tc_profiler_end_frame();
    const tc_frame_profile* first = tc_profiler_history_at(0);
    check_wide_profile(first, 500, 2);
    GUARD_C_CHECK(first->sections != scratch);

    tc_profiler_begin_frame();
    record_wide_profile(3, 1);
    current = tc_profiler_current_frame();
    check_wide_profile(current, 3, 1);
    GUARD_C_CHECK(current->sections == scratch);
    tc_profiler_end_frame();
    check_wide_profile(first, 500, 2);

    tc_profiler_clear_history();
    tc_profiler_begin_frame();
    record_wide_profile(500, 1);
    current = tc_profiler_current_frame();
    check_wide_profile(current, 500, 1);
    GUARD_C_CHECK(current->sections == scratch);
    tc_profiler_end_frame();
    check_wide_profile(tc_profiler_history_at(0), 500, 1);
    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    return 0;
}

GUARD_C_TEST(test_profiler_large_captures_own_independent_copies_across_growth_and_clear) {
    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    tc_profiler_capture* paused = tc_profiler_capture_create(2);
    tc_profiler_capture* rolling = tc_profiler_capture_create(3);
    GUARD_C_REQUIRE(paused != NULL);
    GUARD_C_REQUIRE(rolling != NULL);
    tc_profiler_capture_set_active(paused, true);
    tc_profiler_capture_set_active(rolling, true);
    tc_profiler_begin_frame();
    record_wide_profile(500, 2);
    const int original_number = tc_profiler_current_frame()->frame_number;
    tc_section_timing* scratch = tc_profiler_current_frame()->sections;
    tc_profiler_end_frame();
    const tc_frame_profile* original = tc_profiler_capture_at(paused, 0);
    const tc_frame_profile* rolling_original = tc_profiler_capture_at(rolling, 0);
    check_wide_profile(original, 500, 2);
    check_wide_profile(rolling_original, 500, 2);
    GUARD_C_REQUIRE(original->section_count == 2001);
    GUARD_C_CHECK(original->sections != scratch);
    GUARD_C_CHECK(original->sections != rolling_original->sections);
    GUARD_C_CHECK(original->sections != tc_profiler_history_at(0)->sections);
    const size_t snapshot_size = sizeof(tc_section_timing) * (size_t)original->section_count;
    tc_section_timing* snapshot = malloc(snapshot_size);
    GUARD_C_REQUIRE(snapshot != NULL);
    memcpy(snapshot, original->sections, snapshot_size);
    tc_profiler_capture_set_active(paused, false);

    // This frame crosses several allocation growth boundaries while parents
    // are open. Neither a paused nor an active capture may alias scratch.
    tc_profiler_begin_frame();
    record_wide_profile(3000, 1);
    scratch = tc_profiler_current_frame()->sections;
    tc_profiler_end_frame();
    check_wide_profile(tc_profiler_capture_at(rolling, 1), 3000, 1);
    GUARD_C_CHECK(memcmp(snapshot, original->sections, snapshot_size) == 0);
    GUARD_C_CHECK(memcmp(snapshot, rolling_original->sections, snapshot_size) == 0);
    tc_profiler_clear_history();
    GUARD_C_CHECK(memcmp(snapshot, original->sections, snapshot_size) == 0);
    GUARD_C_CHECK(memcmp(snapshot, rolling_original->sections, snapshot_size) == 0);

    tc_profiler_begin_frame();
    record_wide_profile(2, 1);
    GUARD_C_CHECK(tc_profiler_current_frame()->sections == scratch);
    tc_profiler_end_frame();
    GUARD_C_CHECK(memcmp(snapshot, rolling_original->sections, snapshot_size) == 0);
    tc_profiler_begin_frame();
    record_wide_profile(500, 1);
    GUARD_C_CHECK(tc_profiler_current_frame()->sections == scratch);
    tc_profiler_end_frame();
    GUARD_C_CHECK(tc_profiler_capture_count(rolling) == 3);
    GUARD_C_CHECK(tc_profiler_capture_overwritten_count(rolling) == 1);
    GUARD_C_CHECK(tc_profiler_capture_find(rolling, original_number) == NULL);
    check_wide_profile(tc_profiler_capture_at(rolling, 0), 3000, 1);
    check_wide_profile(tc_profiler_capture_at(rolling, 1), 2, 1);
    check_wide_profile(tc_profiler_capture_at(rolling, 2), 500, 1);
    tc_profiler_capture_clear(rolling);
    GUARD_C_CHECK(tc_profiler_capture_count(rolling) == 0);
    GUARD_C_CHECK(tc_profiler_capture_count(paused) == 1);
    GUARD_C_CHECK(memcmp(snapshot, original->sections, snapshot_size) == 0);
    free(snapshot);
    tc_profiler_capture_destroy(rolling);
    tc_profiler_capture_destroy(paused);
    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    return 0;
}

GUARD_C_TEST(test_profiler_bounds_deeply_nested_sections) {
    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    tc_profiler_begin_frame();

    for (int i = 0; i < 32; ++i) {
        char name[32];
        snprintf(name, sizeof(name), "nested-%d", i);
        tc_profiler_begin_section(name);
    }
    for (int i = 0; i < 32; ++i) {
        tc_profiler_end_section();
    }
    tc_profiler_end_frame();

    tc_frame_profile* frame = tc_profiler_history_at(0);
    GUARD_C_REQUIRE(frame != NULL);
    GUARD_C_CHECK(frame->section_count == TC_PROFILER_MAX_DEPTH);
    for (int i = 0; i < TC_PROFILER_MAX_DEPTH; ++i) {
        GUARD_C_CHECK(frame->sections[i].call_count == 1);
        GUARD_C_CHECK(frame->sections[i].parent_index == i - 1);
    }

    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    return 0;
}

GUARD_C_TEST(test_profiler_preserves_raw_frame_timing_and_excludes_open_frame) {
    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    const tc_profiler_frame_info info = {
        1000.0,
        17.25,
        16.0,
        1.25,
        0,
    };
    tc_profiler_begin_frame_with_info(&info);
    tc_frame_profile* current = tc_profiler_current_frame();
    GUARD_C_REQUIRE(current != NULL);
    const int frame_number = current->frame_number;
    GUARD_C_CHECK(current->start_time_ms == 1000.0);
    GUARD_C_CHECK(current->interval_ms == 17.25);
    GUARD_C_CHECK(current->target_interval_ms == 16.0);
    GUARD_C_CHECK(current->deadline_lateness_ms == 1.25);

    tc_profiler_history_range open_range;
    GUARD_C_REQUIRE(tc_profiler_history_after(frame_number - 1, &open_range));
    GUARD_C_CHECK(open_range.count == 0);

    tc_profiler_end_frame();
    tc_frame_profile* complete = tc_profiler_history_at(0);
    GUARD_C_REQUIRE(complete != NULL);
    GUARD_C_CHECK(complete->active_ms >= 0.0);
    GUARD_C_CHECK(complete->active_ms == complete->total_ms);

    tc_profiler_history_range complete_range;
    GUARD_C_REQUIRE(tc_profiler_history_after(frame_number - 1, &complete_range));
    GUARD_C_CHECK(complete_range.first_index == 0);
    GUARD_C_CHECK(complete_range.count == 1);
    GUARD_C_CHECK(complete_range.dropped_count == 0);
    GUARD_C_CHECK(complete_range.oldest_frame_number == frame_number);
    GUARD_C_CHECK(complete_range.newest_frame_number == frame_number);

    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    return 0;
}

GUARD_C_TEST(test_profiler_history_cursor_reports_ring_overwrite) {
    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    int first_frame_number = -1;
    for (int index = 0; index < 125; ++index) {
        tc_profiler_begin_frame();
        tc_frame_profile* current = tc_profiler_current_frame();
        GUARD_C_REQUIRE(current != NULL);
        if (index == 0)
            first_frame_number = current->frame_number;
        tc_profiler_end_frame();
    }

    tc_profiler_history_range range;
    GUARD_C_REQUIRE(tc_profiler_history_after(first_frame_number - 1, &range));
    GUARD_C_CHECK(range.count == 120);
    GUARD_C_CHECK(range.dropped_count == 5);
    GUARD_C_CHECK(range.oldest_frame_number == first_frame_number + 5);
    GUARD_C_CHECK(range.newest_frame_number == first_frame_number + 124);

    tc_profiler_history_range tail;
    GUARD_C_REQUIRE(tc_profiler_history_after(first_frame_number + 120, &tail));
    GUARD_C_CHECK(tail.count == 4);
    GUARD_C_CHECK(tail.dropped_count == 0);
    GUARD_C_CHECK(tc_profiler_history_at(tail.first_index)->frame_number == first_frame_number + 121);

    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    return 0;
}

GUARD_C_TEST(test_profiler_native_capture_owns_bounded_complete_frames) {
    tc_profiler_set_enabled(true);
    tc_profiler_clear_history();
    tc_profiler_capture* capture = tc_profiler_capture_create(3);
    GUARD_C_REQUIRE(capture != NULL);
    GUARD_C_CHECK(tc_profiler_capture_revision(capture) == 1);
    tc_profiler_capture_set_active(capture, true);

    int first_frame_number = -1;
    for (int index = 0; index < 4; ++index) {
        const tc_profiler_frame_info info = {
            1000.0 + index * 20.0,
            10.0 + index * 2.0,
            10.0,
            (double)index,
            index == 3 ? 1 : 0,
        };
        tc_profiler_begin_frame_with_info(&info);
        tc_frame_profile* current = tc_profiler_current_frame();
        GUARD_C_REQUIRE(current != NULL);
        if (index == 0)
            first_frame_number = current->frame_number;
        tc_profiler_begin_section("Root");
        tc_profiler_end_section();
        tc_profiler_end_frame();
    }

    GUARD_C_CHECK(tc_profiler_capture_count(capture) == 3);
    GUARD_C_CHECK(tc_profiler_capture_overwritten_count(capture) == 1);
    GUARD_C_CHECK(tc_profiler_capture_revision(capture) == 5);
    const tc_frame_profile* oldest = tc_profiler_capture_at(capture, 0);
    GUARD_C_REQUIRE(oldest != NULL);
    GUARD_C_CHECK(oldest->frame_number == first_frame_number + 1);
    GUARD_C_CHECK(oldest->section_count == 1);
    GUARD_C_CHECK(oldest->sections != NULL);
    GUARD_C_CHECK(strcmp(oldest->sections[0].name, "Root") == 0);
    GUARD_C_CHECK(tc_profiler_capture_find(capture, first_frame_number) == NULL);
    GUARD_C_CHECK(tc_profiler_capture_find(capture, first_frame_number + 3) != NULL);

    tc_profiler_history_range range;
    GUARD_C_REQUIRE(tc_profiler_capture_after(capture, first_frame_number - 1, &range));
    GUARD_C_CHECK(range.count == 3);
    GUARD_C_CHECK(range.dropped_count == 1);

    tc_profiler_frame_summary summary;
    GUARD_C_REQUIRE(tc_profiler_capture_summary_at(capture, 2, 1.25, &summary));
    GUARD_C_CHECK(summary.frame_number == first_frame_number + 3);
    GUARD_C_CHECK(summary.hitch);
    GUARD_C_CHECK(summary.has_pacing_gap);

    tc_profiler_statistics statistics;
    GUARD_C_REQUIRE(tc_profiler_capture_statistics(capture, -1, -1, 1.25, &statistics));
    GUARD_C_CHECK(statistics.frame_count == 3);
    GUARD_C_CHECK(statistics.max_interval_ms == 16.0);
    GUARD_C_CHECK(statistics.hitch_count == 2);
    GUARD_C_CHECK(statistics.overwritten_count == 1);

    tc_profiler_capture_set_active(capture, false);
    tc_profiler_begin_frame();
    tc_profiler_end_frame();
    GUARD_C_CHECK(tc_profiler_capture_count(capture) == 3);
    GUARD_C_CHECK(tc_profiler_capture_revision(capture) == 5);

    tc_profiler_capture_clear(capture);
    GUARD_C_CHECK(tc_profiler_capture_count(capture) == 0);
    GUARD_C_CHECK(tc_profiler_capture_overwritten_count(capture) == 0);
    GUARD_C_CHECK(tc_profiler_capture_revision(capture) == 6);
    tc_profiler_capture_destroy(capture);
    tc_profiler_clear_history();
    tc_profiler_set_enabled(false);
    return 0;
}

GUARD_C_TEST(test_capture_records_frame_timing_without_section_profiling) {
    tc_profiler_set_enabled(false);
    tc_profiler_clear_history();
    tc_profiler_capture* capture = tc_profiler_capture_create(4);
    GUARD_C_REQUIRE(capture != NULL);
    tc_profiler_capture_set_active(capture, true);

    GUARD_C_CHECK(tc_profiler_frame_capture_enabled());
    GUARD_C_CHECK(!tc_profiler_enabled());
    GUARD_C_CHECK(!tc_profiler_capture_profiling(capture));

    tc_profiler_begin_frame();
    GUARD_C_CHECK(!tc_profiler_enabled());
    tc_profiler_begin_section("not-recorded");
    tc_profiler_end_section();
    // Enabling section profiling during a frame takes effect on the next
    // frame, keeping already-open begin/end pairs balanced.
    tc_profiler_capture_set_profiling(capture, true);
    GUARD_C_CHECK(!tc_profiler_enabled());
    tc_profiler_end_frame();

    const tc_frame_profile* timing_only = tc_profiler_capture_at(capture, 0);
    GUARD_C_REQUIRE(timing_only != NULL);
    GUARD_C_CHECK(!timing_only->sections_profiled);
    GUARD_C_CHECK(timing_only->section_count == 0);
    GUARD_C_CHECK(timing_only->active_ms >= 0.0);

    tc_profiler_begin_frame();
    GUARD_C_CHECK(tc_profiler_enabled());
    tc_profiler_begin_section("recorded");
    // Disabling during an open frame is also deferred until its end.
    tc_profiler_capture_set_profiling(capture, false);
    GUARD_C_CHECK(tc_profiler_enabled());
    tc_profiler_end_section();
    tc_profiler_end_frame();

    const tc_frame_profile* profiled = tc_profiler_capture_at(capture, 1);
    GUARD_C_REQUIRE(profiled != NULL);
    GUARD_C_CHECK(profiled->sections_profiled);
    GUARD_C_CHECK(profiled->section_count == 1);
    GUARD_C_CHECK(strcmp(profiled->sections[0].name, "recorded") == 0);

    GUARD_C_CHECK(!tc_profiler_enabled());
    tc_profiler_capture_set_active(capture, false);
    GUARD_C_CHECK(!tc_profiler_frame_capture_enabled());
    tc_profiler_capture_destroy(capture);
    tc_profiler_clear_history();
    return 0;
}

GUARD_C_TEST(test_gpu_frame_timing_is_published_after_cpu_frame_close) {
    tc_profiler_set_enabled(false);
    tc_profiler_clear_history();
    tc_profiler_capture* capture = tc_profiler_capture_create(2);
    GUARD_C_REQUIRE(capture != NULL);
    tc_profiler_capture_set_active(capture, true);
    tc_profiler_begin_frame();
    tc_frame_profile* current = tc_profiler_current_frame();
    GUARD_C_REQUIRE(current != NULL);
    const int frame_number = current->frame_number;
    tc_profiler_end_frame();
    GUARD_C_CHECK(!tc_profiler_capture_at(capture, 0)->has_gpu_duration);
    GUARD_C_CHECK(tc_profiler_publish_gpu_frame_timing(frame_number, 2.5));
    const tc_frame_profile* completed = tc_profiler_capture_at(capture, 0);
    GUARD_C_REQUIRE(completed != NULL);
    GUARD_C_CHECK(completed->has_gpu_duration);
    GUARD_C_CHECK(completed->gpu_duration_ms == 2.5);
    GUARD_C_CHECK(tc_profiler_publish_gpu_frame_timing(frame_number, 1.25));
    completed = tc_profiler_capture_at(capture, 0);
    GUARD_C_REQUIRE(completed != NULL);
    GUARD_C_CHECK(completed->gpu_duration_ms == 3.75);
    GUARD_C_CHECK(!tc_profiler_publish_gpu_frame_timing(frame_number, -1.0));
    tc_profiler_capture_destroy(capture);
    tc_profiler_clear_history();
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_profiler_preserves_thousands_of_shallow_sections_and_reuses_storage);
    GUARD_C_RUN(test_profiler_large_captures_own_independent_copies_across_growth_and_clear);
    GUARD_C_RUN(test_profiler_bounds_deeply_nested_sections);
    GUARD_C_RUN(test_profiler_preserves_raw_frame_timing_and_excludes_open_frame);
    GUARD_C_RUN(test_profiler_history_cursor_reports_ring_overwrite);
    GUARD_C_RUN(test_profiler_native_capture_owns_bounded_complete_frames);
    GUARD_C_RUN(test_capture_records_frame_timing_without_section_profiling);
    GUARD_C_RUN(test_gpu_frame_timing_is_published_after_cpu_frame_close);
    return GUARD_C_END();
}
