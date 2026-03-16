#pragma once

#if defined(_WIN32) || defined(__CYGWIN__)
#  ifdef TERMIN_ENGINE_EXPORTS
#    define TERMIN_ENGINE_API __declspec(dllexport)
#  else
#    define TERMIN_ENGINE_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_ENGINE_API
#endif
