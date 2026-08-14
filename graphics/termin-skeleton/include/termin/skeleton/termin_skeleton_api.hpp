#pragma once

#if defined(TERMIN_SKELETON_STATIC)
#define TERMIN_SKELETON_API
#elif defined(_WIN32) || defined(__CYGWIN__)
#ifdef TERMIN_SKELETON_EXPORTS
#define TERMIN_SKELETON_API __declspec(dllexport)
#else
#define TERMIN_SKELETON_API __declspec(dllimport)
#endif
#else
#define TERMIN_SKELETON_API
#endif
