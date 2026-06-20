#pragma once

#if defined(_WIN32)
#  if defined(TERMIN_NAVMESH_COMPONENTS_EXPORTS)
#    define TERMIN_NAVMESH_COMPONENTS_API __declspec(dllexport)
#  else
#    define TERMIN_NAVMESH_COMPONENTS_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_NAVMESH_COMPONENTS_API __attribute__((visibility("default")))
#endif

