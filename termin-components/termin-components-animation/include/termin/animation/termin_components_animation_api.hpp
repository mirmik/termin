#pragma once

#if defined(_WIN32)
#  if defined(TERMIN_COMPONENTS_ANIMATION_EXPORTS)
#    define TERMIN_COMPONENTS_ANIMATION_API __declspec(dllexport)
#  else
#    define TERMIN_COMPONENTS_ANIMATION_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_COMPONENTS_ANIMATION_API __attribute__((visibility("default")))
#endif

