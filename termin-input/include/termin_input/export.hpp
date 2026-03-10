#pragma once

#ifdef _WIN32
    #ifdef TERMIN_INPUT_EXPORTS
        #define TERMIN_INPUT_API __declspec(dllexport)
    #else
        #define TERMIN_INPUT_API __declspec(dllimport)
    #endif
#else
    #define TERMIN_INPUT_API __attribute__((visibility("default")))
#endif
