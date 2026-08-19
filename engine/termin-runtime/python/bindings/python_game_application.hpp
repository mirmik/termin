#pragma once

#include <nanobind/nanobind.h>

#if defined(_WIN32)
#if defined(TERMIN_RUNTIME_PYTHON_EXPORTS)
#define TERMIN_RUNTIME_PYTHON_API __declspec(dllexport)
#else
#define TERMIN_RUNTIME_PYTHON_API __declspec(dllimport)
#endif
#else
#define TERMIN_RUNTIME_PYTHON_API __attribute__((visibility("default")))
#endif

namespace termin::runtime::python {

    TERMIN_RUNTIME_PYTHON_API void bind_game_application(nanobind::module_& module);

} // namespace termin::runtime::python
