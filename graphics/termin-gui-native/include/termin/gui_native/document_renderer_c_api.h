#pragma once

#include <termin/gui_native/document_renderer_export.h>
#include <termin/gui_native/tc_ui_document.h>

#ifdef __cplusplus
extern "C" {
#endif

TC_DEFINE_HANDLE(tc_document_renderer_handle)

typedef bool (*tc_document_set_text_input_fn)(void* userdata, bool enabled);
/* Return UTF-8 byte count including NUL. NULL/0 is a size query; 0 is failure.
 * Copy callbacks must terminate the string whenever capacity is nonzero. */
typedef size_t (*tc_document_copy_clipboard_fn)(void* userdata, char* buffer, size_t capacity);
typedef bool (*tc_document_set_clipboard_fn)(void* userdata, const char* text, size_t byte_length);
typedef bool (*tc_document_set_cursor_fn)(void* userdata, tc_ui_cursor_intent cursor);

typedef struct tc_document_renderer_config {
    size_t struct_size;
    const char* font_path;
    int32_t font_size;
    int32_t width;
    int32_t height;
    float density_scale;
    void* userdata;
    tc_document_set_text_input_fn set_text_input;
    tc_document_copy_clipboard_fn copy_clipboard;
    tc_document_set_clipboard_fn set_clipboard;
    tc_document_set_cursor_fn set_cursor;
} tc_document_renderer_config;

/* Borrows a live tgfx::GraphicsHost pointer and document; both must outlive the
 * renderer. One renderer per document. This bridge creates no graphics domain,
 * window, application loop or Python runtime. Config strings are copied during
 * create. Callback function pointers/userdata must remain alive through destroy.
 * All calls, including destroy, belong to the thread calling create. Callbacks
 * are synchronous and must not throw or destroy/reenter the renderer.
 * Destroy the renderer before destroying its document or graphics host.
 * Creation errors are written to the native log. */
TERMIN_GUI_NATIVE_RENDERER_API tc_document_renderer_handle tc_document_renderer_create(
    tc_ui_document_handle document, void* graphics_host, const tc_document_renderer_config* config);
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_destroy(tc_document_renderer_handle renderer);
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_is_valid(tc_document_renderer_handle renderer);
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_set_metrics(
    tc_document_renderer_handle renderer, int32_t width, int32_t height, float density_scale);
/* Returns a borrowed RGBA16F DisplayLinear texture ID, valid on the borrowed
 * graphics device until resize/next render/destroy. Presentation must apply the
 * normal DisplayLinear -> output transfer (e.g. the D3DImage presenter). */
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_render(
    tc_document_renderer_handle renderer, uint32_t* out_texture);
/* Pointer positions are document logical units (physical pixels / density).
 * Wheel values are logical scroll steps, matching tc_ui_pointer_event. */
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_dispatch_pointer(
    tc_document_renderer_handle renderer, const tc_ui_pointer_event* event, tc_ui_event_result* out_result);
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_dispatch_key(
    tc_document_renderer_handle renderer, const tc_ui_key_event* event, tc_ui_event_result* out_result);
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_dispatch_text(
    tc_document_renderer_handle renderer, const char* utf8, tc_ui_event_result* out_result);
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_cancel_interaction(
    tc_document_renderer_handle renderer, tc_ui_pointer_cancel_reason reason);
/* Losing host focus cancels capture and clears native focus. Gaining focus
 * enables text input; individual widgets acquire focus through native routing. */
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_set_focus(
    tc_document_renderer_handle renderer, bool focused);
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_has_pointer_capture(
    tc_document_renderer_handle renderer);
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_request_repaint(tc_document_renderer_handle renderer);
TERMIN_GUI_NATIVE_RENDERER_API bool tc_document_renderer_repaint_requested(tc_document_renderer_handle renderer);
/* Required UTF-8 buffer size includes trailing NUL; NULL/0 queries the size.
 * Invalid/stale handles produce a diagnostic string rather than a borrowed
 * error pointer. Error storage is per-renderer, never thread_local. */
TERMIN_GUI_NATIVE_RENDERER_API size_t tc_document_renderer_copy_last_error(
    tc_document_renderer_handle renderer, char* buffer, size_t capacity);

#ifdef __cplusplus
}
#endif
