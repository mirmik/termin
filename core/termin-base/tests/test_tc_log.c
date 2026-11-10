#include <tcbase/tc_log.h>

#include "guard_c.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

static int g_callback_count = 0;
static tc_log_level g_callback_level = TC_LOG_DEBUG;
static char g_callback_message[TC_LOG_MESSAGE_CAPACITY];
static size_t g_wake_pending = 0;
static int g_wake_count = 0;

static void wake_capture(void* user_data) {
    int* count = (int*)user_data;
    ++*count;
    g_wake_pending = tc_log_capture_pending();
}

static void capture_callback(tc_log_level level, const char* message) {
    g_callback_count += 1;
    g_callback_level = level;
    snprintf(g_callback_message, sizeof(g_callback_message), "%s", message ? message : "");
}

static void reset_logging(void) {
    tc_log_capture_stop();
    tc_log_set_callback(NULL);
    tc_log_set_level(TC_LOG_DEBUG);
    g_callback_count = 0;
    g_callback_level = TC_LOG_DEBUG;
    g_callback_message[0] = '\0';
}

GUARD_C_TEST(test_capture_preserves_callback_and_drops_oldest) {
    reset_logging();
    tc_log_set_callback(capture_callback);
    GUARD_C_CHECK(tc_log_capture_start(2));

    tc_log_info("first");
    tc_log_warn("second");
    tc_log_error("third");

    GUARD_C_CHECK(g_callback_count == 3);
    GUARD_C_CHECK(g_callback_level == TC_LOG_ERROR);
    GUARD_C_CHECK(strcmp(g_callback_message, "third") == 0);

    tc_log_record records[2];
    uint64_t dropped = 0;
    size_t count = tc_log_capture_drain(records, 2, &dropped);
    GUARD_C_CHECK(count == 2);
    GUARD_C_CHECK(dropped == 1);
    GUARD_C_CHECK(records[0].level == TC_LOG_WARN);
    GUARD_C_CHECK(strcmp(records[0].message, "second") == 0);
    GUARD_C_CHECK(records[1].level == TC_LOG_ERROR);
    GUARD_C_CHECK(strcmp(records[1].message, "third") == 0);

    dropped = 9;
    count = tc_log_capture_drain(records, 2, &dropped);
    GUARD_C_CHECK(count == 0);
    GUARD_C_CHECK(dropped == 0);
    reset_logging();
    return 0;
}

GUARD_C_TEST(test_stop_disables_capture_only) {
    reset_logging();
    tc_log_set_callback(capture_callback);
    GUARD_C_CHECK(tc_log_capture_start(1));
    tc_log_capture_stop();

    tc_log_info("after stop");

    tc_log_record record;
    uint64_t dropped = 0;
    GUARD_C_CHECK(tc_log_capture_drain(&record, 1, &dropped) == 0);
    GUARD_C_CHECK(dropped == 0);
    GUARD_C_CHECK(g_callback_count == 1);
    GUARD_C_CHECK(strcmp(g_callback_message, "after stop") == 0);
    reset_logging();
    return 0;
}

GUARD_C_TEST(test_capture_wakeup_tracks_empty_to_nonempty_and_backlog) {
    reset_logging();
    g_wake_count = 0;
    GUARD_C_CHECK(tc_log_capture_start(4));
    tc_log_info("before subscribe");
    tc_log_capture_set_wakeup(wake_capture, &g_wake_count);
    GUARD_C_CHECK(g_wake_count == 1);
    GUARD_C_CHECK(g_wake_pending == 1);
    tc_log_info("second");
    GUARD_C_CHECK(g_wake_count == 1);
    tc_log_record record;
    GUARD_C_CHECK(tc_log_capture_drain(&record, 1, NULL) == 1);
    GUARD_C_CHECK(tc_log_capture_pending() == 1);
    GUARD_C_CHECK(tc_log_capture_drain(&record, 1, NULL) == 1);
    GUARD_C_CHECK(tc_log_capture_pending() == 0);
    tc_log_info("another burst");
    GUARD_C_CHECK(g_wake_count == 2);
    tc_log_capture_stop();
    GUARD_C_CHECK(tc_log_capture_start(1));
    tc_log_info("stopped callback is not retained");
    GUARD_C_CHECK(g_wake_count == 2);
    reset_logging();
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_capture_preserves_callback_and_drops_oldest);
    GUARD_C_RUN(test_stop_disables_capture_only);
    GUARD_C_RUN(test_capture_wakeup_tracks_empty_to_nonempty_and_backlog);
    return GUARD_C_END();
}
