#pragma once

#if defined(_WIN32)
#  if defined(TERMIN_PREFAB_EXPORTS)
#    define TERMIN_PREFAB_API __declspec(dllexport)
#  else
#    define TERMIN_PREFAB_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_PREFAB_API __attribute__((visibility("default")))
#endif
