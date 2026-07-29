#pragma once

#include <stdint.h>

#include "termin/android/termin_android_api.h"
#include "tc_input_event.h"

#ifdef __ANDROID__
#include <android/native_window.h>
#else
typedef struct ANativeWindow ANativeWindow;
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct termin_android_config {
    const char* app_data_dir;
    const char* asset_root;
    const char* native_lib_dir;
} termin_android_config;

TERMIN_ANDROID_API int termin_android_initialize(const termin_android_config* config);
TERMIN_ANDROID_API void termin_android_shutdown(void);

TERMIN_ANDROID_API void termin_android_set_shader_artifact_root(const char* root);
TERMIN_ANDROID_API const char* termin_android_get_shader_artifact_root(void);

TERMIN_ANDROID_API void termin_android_on_surface_created(ANativeWindow* window);
TERMIN_ANDROID_API void termin_android_on_surface_changed(int32_t width, int32_t height);
TERMIN_ANDROID_API void termin_android_on_surface_destroyed(void);
TERMIN_ANDROID_API void termin_android_on_pointer(
    uint64_t pointer_id,
    int32_t device,
    int32_t phase,
    float x,
    float y,
    float pressure);
TERMIN_ANDROID_API int termin_android_render_frame(int64_t frame_time_nanos);
TERMIN_ANDROID_API int termin_android_smoke_render(int64_t frame_time_nanos);

TERMIN_ANDROID_API ANativeWindow* termin_android_native_window(void);
TERMIN_ANDROID_API int32_t termin_android_surface_width(void);
TERMIN_ANDROID_API int32_t termin_android_surface_height(void);

#ifdef __cplusplus
}
#endif
