#pragma once

#if defined(_WIN32) || defined(__CYGWIN__)
    #ifdef TERMIN_AUDIO_EXPORTS
        #define TERMIN_AUDIO_API __declspec(dllexport)
    #else
        #define TERMIN_AUDIO_API __declspec(dllimport)
    #endif
#else
    #define TERMIN_AUDIO_API __attribute__((visibility("default")))
#endif
