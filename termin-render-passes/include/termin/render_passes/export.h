#pragma once

#ifdef _WIN32
#  ifdef TERMIN_RENDER_PASSES_EXPORTS
#    define TERMIN_RENDER_PASSES_API __declspec(dllexport)
#  else
#    define TERMIN_RENDER_PASSES_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_RENDER_PASSES_API __attribute__((visibility("default")))
#endif
