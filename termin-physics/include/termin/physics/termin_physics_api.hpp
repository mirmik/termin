#pragma once

#if defined(_WIN32)
#  if defined(TERMIN_PHYSICS_EXPORTS)
#    define TERMIN_PHYSICS_API __declspec(dllexport)
#  else
#    define TERMIN_PHYSICS_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_PHYSICS_API __attribute__((visibility("default")))
#endif
