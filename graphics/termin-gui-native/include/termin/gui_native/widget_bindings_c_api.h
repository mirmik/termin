#pragma once

#include <termin/gui_native/tc_ui_document.h>
#include <termin_visual_scene/tc_visual_scene.h>

#ifdef __cplusplus
extern "C" {
#endif

/* A non-owning reference to a widget in a specific native document. The
 * document owns the widget, including while it has no parent. Operations
 * belong to the document's owning thread. */
typedef struct tc_widget_ref {
    tc_ui_document_handle document;
    tc_widget_handle handle;
} tc_widget_ref;

typedef enum tc_ui_box_orientation {
    TC_UI_BOX_HORIZONTAL = 0,
    TC_UI_BOX_VERTICAL = 1,
} tc_ui_box_orientation;

typedef enum tc_ui_box_child_policy {
    TC_UI_BOX_CHILD_FIXED = 0,
    TC_UI_BOX_CHILD_PREFERRED = 1,
    TC_UI_BOX_CHILD_FLEX = 2,
    TC_UI_BOX_CHILD_STRETCH = 3,
} tc_ui_box_child_policy;

/* Construct and adopt native widgets. Attach the resulting
 * widget to a parent or add it as a document root to make it visible. */
TERMIN_GUI_NATIVE_API tc_widget_ref tc_ui_box_create(tc_ui_document_handle document, tc_ui_box_orientation orientation);
TERMIN_GUI_NATIVE_API tc_widget_ref tc_ui_button_create(tc_ui_document_handle document, const char* text);
TERMIN_GUI_NATIVE_API tc_widget_ref tc_ui_label_create(tc_ui_document_handle document, const char* text);
/* Borrows the scene. Destroy the view before destroying the scene. */
TERMIN_GUI_NATIVE_API tc_widget_ref tc_ui_scene_view_create(tc_ui_document_handle document,
                                                            tc_visual_scene_handle scene);

TERMIN_GUI_NATIVE_API bool tc_ui_widget_ref_is_alive(tc_widget_ref widget);
/* Widget bounds in document logical units. */
TERMIN_GUI_NATIVE_API bool tc_ui_widget_ref_get_bounds(tc_widget_ref widget, tc_ui_rect* out_bounds);
TERMIN_GUI_NATIVE_API bool tc_ui_widget_ref_get_visible(tc_widget_ref widget, bool* out_visible);
TERMIN_GUI_NATIVE_API bool tc_ui_widget_ref_set_visible(tc_widget_ref widget, bool visible);
TERMIN_GUI_NATIVE_API bool tc_ui_widget_ref_get_enabled(tc_widget_ref widget, bool* out_enabled);
TERMIN_GUI_NATIVE_API bool tc_ui_widget_ref_set_enabled(tc_widget_ref widget, bool enabled);
TERMIN_GUI_NATIVE_API bool tc_ui_widget_ref_remove_child(tc_widget_ref parent, tc_widget_ref child);
/* Invalidates the widget and its descendants. */
TERMIN_GUI_NATIVE_API bool tc_ui_widget_ref_destroy(tc_widget_ref widget);

/* Extent in logical units for Fixed, weight for Flex. Both references must
 * belong to the same document. */
TERMIN_GUI_NATIVE_API bool
tc_ui_box_add_child(tc_widget_ref box, tc_widget_ref child, tc_ui_box_child_policy policy, float value);
TERMIN_GUI_NATIVE_API bool tc_ui_box_set_spacing(tc_widget_ref box, float spacing);
TERMIN_GUI_NATIVE_API bool tc_ui_button_set_text(tc_widget_ref button, const char* text);
TERMIN_GUI_NATIVE_API bool tc_ui_label_set_text(tc_widget_ref label, const char* text);

typedef void (*tc_ui_widget_callback_destroy_fn)(void* userdata);
typedef void (*tc_ui_button_clicked_fn)(void* userdata);
typedef bool (*tc_ui_scene_view_pointer_fn)(void* userdata,
                                            float world_x,
                                            float world_y,
                                            const tc_ui_pointer_event* event);

/*
 * Callback registrations consume the supplied userdata on every outcome.
 * A non-null destroy callback is called exactly once after the connection
 * can no longer invoke its callback, including rejection, removal and
 * document teardown. Use a null destroy callback for caller-owned userdata.
 * Destroy callbacks must not throw or reenter widget or document APIs.
 * Input callbacks run synchronously during native event dispatch, including
 * synthesized pointer cancellation. They must not throw, recursively dispatch
 * input, change the widget tree, or destroy the document. Event pointers are
 * valid only for the duration of an input callback.
 */
TERMIN_GUI_NATIVE_API size_t tc_ui_button_connect_clicked(tc_widget_ref button,
                                                          tc_ui_button_clicked_fn callback,
                                                          void* userdata,
                                                          tc_ui_widget_callback_destroy_fn destroy);
TERMIN_GUI_NATIVE_API bool tc_ui_button_disconnect_clicked(tc_widget_ref button, size_t connection);
/* A null callback clears the existing handler. */
TERMIN_GUI_NATIVE_API bool tc_ui_scene_view_set_pointer_handler(tc_widget_ref view,
                                                                tc_ui_scene_view_pointer_fn callback,
                                                                void* userdata,
                                                                tc_ui_widget_callback_destroy_fn destroy);
/* Enable built-in wheel zoom and middle-button pan. Enabled by default. */
TERMIN_GUI_NATIVE_API bool tc_ui_scene_view_set_navigation_enabled(tc_widget_ref view, bool enabled);
TERMIN_GUI_NATIVE_API bool tc_ui_scene_view_set_grid_visible(tc_widget_ref view, bool visible);

#ifdef __cplusplus
}
#endif
