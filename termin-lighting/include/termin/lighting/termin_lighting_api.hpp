#pragma once

#if defined(_WIN32)
#  ifdef TERMIN_LIGHTING_EXPORTS
#    define TERMIN_LIGHTING_API __declspec(dllexport)
#  else
#    define TERMIN_LIGHTING_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_LIGHTING_API
#endif
