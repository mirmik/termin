#pragma once

#if defined(_WIN32) || defined(__CYGWIN__)
#  ifdef TERMIN_ANDROID_EXPORTS
#    define TERMIN_ANDROID_API __declspec(dllexport)
#  else
#    define TERMIN_ANDROID_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_ANDROID_API __attribute__((visibility("default")))
#endif

