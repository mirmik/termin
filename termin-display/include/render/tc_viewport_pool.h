#ifndef TC_VIEWPORT_POOL_H
#define TC_VIEWPORT_POOL_H

#include <tc_types.h>
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
} tc_viewport_handle;

#ifdef __cplusplus
    #define TC_VIEWPORT_HANDLE_INVALID (tc_viewport_handle{0xFFFFFFFF, 0})
#else
    #define TC_VIEWPORT_HANDLE_INVALID ((tc_viewport_handle){0xFFFFFFFF, 0})
#endif

static inline bool tc_viewport_handle_valid(tc_viewport_handle h) {
    return h.index != 0xFFFFFFFF;
}

static inline bool tc_viewport_handle_eq(tc_viewport_handle a, tc_viewport_handle b) {
    return a.index == b.index && a.generation == b.generation;
}

TERMIN_DISPLAY_API void tc_viewport_pool_init(void);
TERMIN_DISPLAY_API void tc_viewport_pool_shutdown(void);
TERMIN_DISPLAY_API tc_viewport_handle tc_viewport_pool_alloc(const char* name);
TERMIN_DISPLAY_API void tc_viewport_pool_free(tc_viewport_handle h);
TERMIN_DISPLAY_API bool tc_viewport_pool_alive(tc_viewport_handle h);
TERMIN_DISPLAY_API size_t tc_viewport_pool_count(void);

typedef bool (*tc_viewport_pool_iter_fn)(tc_viewport_handle h, void* user_data);

TERMIN_DISPLAY_API void tc_viewport_pool_foreach(tc_viewport_pool_iter_fn callback, void* user_data);

#ifdef __cplusplus
}
#endif

#endif
