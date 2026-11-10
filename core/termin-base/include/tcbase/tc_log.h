#ifndef TC_LOG_H
#define TC_LOG_H

// Shared logging system for all termin libraries.

#include "tcbase_api.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    TC_LOG_DEBUG = 0,
    TC_LOG_INFO = 1,
    TC_LOG_WARN = 2,
    TC_LOG_ERROR = 3
} tc_log_level;

// Callback for log interception (e.g. for editor console)
typedef void (*tc_log_callback)(tc_log_level level, const char* message);

enum {
    TC_LOG_MESSAGE_CAPACITY = 4096
};

typedef struct {
    tc_log_level level;
    char message[TC_LOG_MESSAGE_CAPACITY];
} tc_log_record;

// Set callback for log interception
TCBASE_API void tc_log_set_callback(tc_log_callback callback);

// Set minimum log level
TCBASE_API void tc_log_set_level(tc_log_level min_level);

// Start a process-wide bounded capture queue. Starting again replaces and
// clears the previous queue. Producers may log from any thread; consumers pull
// complete records. An optional wake notification does no record presentation.
TCBASE_API int tc_log_capture_start(size_t capacity);

// Stop capture and discard all queued records. stderr and the optional callback
// remain active.
TCBASE_API void tc_log_capture_stop(void);

// Drain up to record_capacity oldest records. The returned dropped count covers
// records evicted by overflow since the previous drain.
TCBASE_API size_t tc_log_capture_drain(tc_log_record* records, size_t record_capacity, uint64_t* dropped_count);

// Non-consuming readiness, including records left by a bounded drain.
TCBASE_API size_t tc_log_capture_pending(void);

// Notify once when capture becomes nonempty. Called on the producer thread,
// after publication and without the capture lock. The callback must only wake
// the consumer: it must not drain, log, or change capture notification ownership.
// Passing NULL unsubscribes and waits for any in-flight callback to finish, so
// user_data can then be destroyed. Serialize installation/removal on the owner
// thread. capture_stop also unsubscribes. stderr/log interception is unaffected.
typedef void (*tc_log_capture_wakeup)(void* user_data);
TCBASE_API void tc_log_capture_set_wakeup(tc_log_capture_wakeup callback, void* user_data);

// Log with specified level (printf-style)
TCBASE_API void tc_log(tc_log_level level, const char* format, ...);

TCBASE_API void tc_log_debug(const char* format, ...);
TCBASE_API void tc_log_info(const char* format, ...);
TCBASE_API void tc_log_warn(const char* format, ...);
TCBASE_API void tc_log_error(const char* format, ...);

#ifdef __cplusplus
}
#endif

#endif // TC_LOG_H
