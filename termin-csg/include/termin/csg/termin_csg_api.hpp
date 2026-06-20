#pragma once

#if defined(_WIN32)
#  if defined(TERMIN_CSG_EXPORTS)
#    define TERMIN_CSG_API __declspec(dllexport)
#  else
#    define TERMIN_CSG_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_CSG_API __attribute__((visibility("default")))
#endif

