#pragma once

#if defined(_WIN32)
#  if defined(TERMIN_QOPT_EXPORTS)
#    define TERMIN_QOPT_API __declspec(dllexport)
#  else
#    define TERMIN_QOPT_API __declspec(dllimport)
#  endif
#else
#  define TERMIN_QOPT_API __attribute__((visibility("default")))
#endif
