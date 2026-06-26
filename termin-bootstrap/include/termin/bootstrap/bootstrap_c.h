// bootstrap_c.h - C lifecycle entry points for Termin runtime registries.
#ifndef TERMIN_BOOTSTRAP_BOOTSTRAP_C_H
#define TERMIN_BOOTSTRAP_BOOTSTRAP_C_H

#ifdef _WIN32
    #ifdef TERMIN_BOOTSTRAP_EXPORTS
        #define TERMIN_BOOTSTRAP_C_API __declspec(dllexport)
    #else
        #define TERMIN_BOOTSTRAP_C_API __declspec(dllimport)
    #endif
#else
    #define TERMIN_BOOTSTRAP_C_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

TERMIN_BOOTSTRAP_C_API void tc_init(void);
TERMIN_BOOTSTRAP_C_API void tc_shutdown(void);

#ifdef __cplusplus
}
#endif

#endif // TERMIN_BOOTSTRAP_BOOTSTRAP_C_H
