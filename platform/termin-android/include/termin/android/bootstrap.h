#pragma once

#include <stdint.h>

#include "tc_input_event.h"
#include "termin/android/termin_android_api.h"

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
    // Explicit development gate for the process-global native profiler.
    // Ordinary packaged applications leave this disabled.
    int32_t enable_profiler;
    // Remote transport is a separate development-only gate so cadence-only
    // capture does not pay for the legacy process-global section profiler.
    int32_t enable_remote_profiler;
    uint16_t remote_profiler_port;
    const char* remote_profiler_token;
    // Process-scoped remote framegraph listener. The listener can outlive a
    // surface, but its render-thread debugger is attached only while an
    // EngineCore/RenderingManager session exists.
    int32_t enable_remote_framegraph;
    uint16_t remote_framegraph_port;
    const char* remote_framegraph_token;
} termin_android_config;

typedef struct termin_android_presentation_metrics {
    float density_scale;
    float font_scale;
    float safe_inset_left;
    float safe_inset_top;
    float safe_inset_right;
    float safe_inset_bottom;
} termin_android_presentation_metrics;

TERMIN_ANDROID_API int termin_android_initialize(const termin_android_config* config);
TERMIN_ANDROID_API void termin_android_shutdown(void);

TERMIN_ANDROID_API void termin_android_set_shader_artifact_root(const char* root);
TERMIN_ANDROID_API const char* termin_android_get_shader_artifact_root(void);

TERMIN_ANDROID_API void termin_android_on_surface_created(ANativeWindow* window);
TERMIN_ANDROID_API void termin_android_on_surface_changed(int32_t width, int32_t height);
TERMIN_ANDROID_API void termin_android_on_surface_destroyed(void);
TERMIN_ANDROID_API void termin_android_on_pause(void);
TERMIN_ANDROID_API void termin_android_on_resume(void);
TERMIN_ANDROID_API void
termin_android_on_presentation_metrics_changed(const termin_android_presentation_metrics* metrics);
TERMIN_ANDROID_API void
termin_android_on_pointer(uint64_t pointer_id, int32_t device, int32_t phase, float x, float y, float pressure);
TERMIN_ANDROID_API int termin_android_render_frame(int64_t frame_time_nanos);
TERMIN_ANDROID_API int termin_android_smoke_render(int64_t frame_time_nanos);

TERMIN_ANDROID_API ANativeWindow* termin_android_native_window(void);
TERMIN_ANDROID_API int32_t termin_android_surface_width(void);
TERMIN_ANDROID_API int32_t termin_android_surface_height(void);

#ifdef __cplusplus
}
#endif
