#ifndef TC_DISPLAY_POOL_H
#define TC_DISPLAY_POOL_H

#include "render/termin_display_api.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t index;
    uint32_t generation;
} tc_display_handle;

#ifdef __cplusplus
    #define TC_DISPLAY_HANDLE_INVALID (tc_display_handle{0xFFFFFFFFu, 0u})
#else
    #define TC_DISPLAY_HANDLE_INVALID ((tc_display_handle){0xFFFFFFFFu, 0u})
#endif

static inline bool tc_display_handle_valid(tc_display_handle h) {
    return h.index != 0xFFFFFFFFu;
}

static inline bool tc_display_handle_eq(tc_display_handle a, tc_display_handle b) {
    return a.index == b.index && a.generation == b.generation;
}

TERMIN_DISPLAY_API void tc_display_pool_init(void);
TERMIN_DISPLAY_API void tc_display_pool_shutdown(void);
TERMIN_DISPLAY_API bool tc_display_alive(tc_display_handle handle);
TERMIN_DISPLAY_API size_t tc_display_pool_count(void);

#ifdef __cplusplus
}

static inline bool operator==(tc_display_handle a, tc_display_handle b) {
    return tc_display_handle_eq(a, b);
}

static inline bool operator!=(tc_display_handle a, tc_display_handle b) {
    return !tc_display_handle_eq(a, b);
}
#endif

#endif
