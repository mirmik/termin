#pragma once

// Export/import macros for render_lib DLL on Windows
#ifdef _WIN32
    #ifdef RENDER_LIB_EXPORTS
        #define RENDER_API __declspec(dllexport)
    #else
        #define RENDER_API __declspec(dllimport)
    #endif
#else
    #define RENDER_API
#endif
