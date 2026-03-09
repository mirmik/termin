#pragma once

#ifdef _WIN32
    #if defined(TERMIN_SCENE_EXPORTS)
        #define TERMIN_SCENE_API __declspec(dllexport)
    #else
        #define TERMIN_SCENE_API __declspec(dllimport)
    #endif
#else
    #define TERMIN_SCENE_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

TERMIN_SCENE_API int termin_scene_version_int(void);
TERMIN_SCENE_API void termin_scene_runtime_init(void);
TERMIN_SCENE_API void termin_scene_runtime_shutdown(void);

#ifdef __cplusplus
}
#endif
