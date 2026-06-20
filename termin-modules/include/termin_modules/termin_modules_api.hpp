#pragma once

#if defined(_WIN32)
#  if defined(TERMIN_MODULES_EXPORTS)
#    define TERMIN_MODULES_API __declspec(dllexport)
#  else
#    define TERMIN_MODULES_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_MODULES_API __attribute__((visibility("default")))
#endif

