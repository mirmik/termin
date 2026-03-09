// export.hpp - DLL export/import macros for termin-scene C++ wrappers
#pragma once

#ifdef _WIN32
    #ifdef TERMIN_SCENE_EXPORTS
        #define TERMIN_SCENE_API __declspec(dllexport)
    #else
        #define TERMIN_SCENE_API __declspec(dllimport)
    #endif
#else
    #define TERMIN_SCENE_API __attribute__((visibility("default")))
#endif

// Backward compat alias (entity_lib used ENTITY_API)
#define ENTITY_API TERMIN_SCENE_API
