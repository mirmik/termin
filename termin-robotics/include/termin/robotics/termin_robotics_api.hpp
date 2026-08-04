#pragma once

#if defined(_WIN32) || defined(__CYGWIN__)
#if defined(TERMIN_ROBOTICS_EXPORTS)
#define TERMIN_ROBOTICS_API __declspec(dllexport)
#else
#define TERMIN_ROBOTICS_API __declspec(dllimport)
#endif
#else
#define TERMIN_ROBOTICS_API __attribute__((visibility("default")))
#endif
