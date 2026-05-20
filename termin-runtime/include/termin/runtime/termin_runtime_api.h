#pragma once

#if defined(_WIN32)
#  if defined(TERMIN_RUNTIME_EXPORTS)
#    define TERMIN_RUNTIME_API __declspec(dllexport)
#  else
#    define TERMIN_RUNTIME_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_RUNTIME_API __attribute__((visibility("default")))
#endif
