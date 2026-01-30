#ifndef TC_LOG_H
#define TC_LOG_H

// TC_LOG_API is dllexport when building termin_core (TC_EXPORTS) or entity_lib (ENTITY_LIB_EXPORTS)
#ifdef _WIN32
    #if defined(TC_EXPORTS) || defined(ENTITY_LIB_EXPORTS)
        #define TC_LOG_API __declspec(dllexport)
    #else
        #define TC_LOG_API __declspec(dllimport)
    #endif
#else
    #define TC_LOG_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    TC_LOG_DEBUG = 0,
    TC_LOG_INFO = 1,
    TC_LOG_WARN = 2,
    TC_LOG_ERROR = 3
} tc_log_level;

typedef void (*tc_log_callback)(tc_log_level level, const char* message);

// Set callback for log interception (editor console)
TC_LOG_API void tc_log_set_callback(tc_log_callback callback);

// Set minimum log level (default: TC_LOG_DEBUG)
TC_LOG_API void tc_log_set_level(tc_log_level min_level);

// Log functions
TC_LOG_API void tc_log(tc_log_level level, const char* format, ...);
TC_LOG_API void tc_log_debug(const char* format, ...);
TC_LOG_API void tc_log_info(const char* format, ...);
TC_LOG_API void tc_log_warn(const char* format, ...);
TC_LOG_API void tc_log_error(const char* format, ...);

#ifdef __cplusplus
}
#endif

#endif // TC_LOG_H
