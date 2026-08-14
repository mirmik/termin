#pragma once

#if defined(_WIN32) || defined(__CYGWIN__)
#if defined(TERMIN_PHYSICS_QOPT_EXPORTS)
#define TERMIN_PHYSICS_QOPT_API __declspec(dllexport)
#else
#define TERMIN_PHYSICS_QOPT_API __declspec(dllimport)
#endif
#else
#define TERMIN_PHYSICS_QOPT_API __attribute__((visibility("default")))
#endif
