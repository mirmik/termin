// export.hpp - DLL export/import macros for cross-platform builds
#pragma once

#ifdef _WIN32
    #ifdef ENTITY_LIB_EXPORTS
        #define ENTITY_API __declspec(dllexport)
    #else
        #define ENTITY_API __declspec(dllimport)
    #endif
#else
    #define ENTITY_API __attribute__((visibility("default")))
#endif
