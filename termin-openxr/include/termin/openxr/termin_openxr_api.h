#pragma once

#if defined(_WIN32) || defined(__CYGWIN__)
#  if defined(TERMIN_OPENXR_EXPORTS)
#    define TERMIN_OPENXR_API __declspec(dllexport)
#  else
#    define TERMIN_OPENXR_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_OPENXR_API __attribute__((visibility("default")))
#endif
