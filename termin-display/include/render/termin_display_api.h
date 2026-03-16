#ifndef TERMIN_DISPLAY_API_H
#define TERMIN_DISPLAY_API_H

#ifdef _WIN32
    #ifdef TERMIN_DISPLAY_EXPORTS
        #define TERMIN_DISPLAY_API __declspec(dllexport)
    #else
        #define TERMIN_DISPLAY_API __declspec(dllimport)
    #endif
#else
    #define TERMIN_DISPLAY_API
#endif

#endif // TERMIN_DISPLAY_API_H
