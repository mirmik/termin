#ifndef TC_INPUT_PLATFORM_SERVICES_H
#define TC_INPUT_PLATFORM_SERVICES_H

#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum tc_input_cursor {
    TC_INPUT_CURSOR_DEFAULT = 0,
    TC_INPUT_CURSOR_TEXT = 1,
    TC_INPUT_CURSOR_HAND = 2,
    TC_INPUT_CURSOR_CROSSHAIR = 3,
    TC_INPUT_CURSOR_MOVE = 4,
    TC_INPUT_CURSOR_RESIZE_HORIZONTAL = 5,
    TC_INPUT_CURSOR_RESIZE_VERTICAL = 6,
    TC_INPUT_CURSOR_RESIZE_NWSE = 7,
    TC_INPUT_CURSOR_RESIZE_NESW = 8
} tc_input_cursor;

// Optional platform operations borrowed for the lifetime of the attached
// display input endpoint. Hosts must dispatch focus loss and clear the
// services before destroying userdata.
// clipboard_text returns the required byte count excluding the terminator and
// writes a terminated prefix when buffer/capacity are provided.
typedef struct tc_input_platform_services {
    void* userdata;
    size_t (*clipboard_text)(void* userdata, char* buffer, size_t capacity);
    bool (*set_clipboard_text)(void* userdata, const char* text_utf8, size_t byte_length);
    void (*set_cursor)(void* userdata, tc_input_cursor cursor);
    void (*set_text_input_enabled)(void* userdata, bool enabled);
} tc_input_platform_services;

#ifdef __cplusplus
}
#endif

#endif
