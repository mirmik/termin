// tc_component_python_bindings.hpp - TcComponent Python wrapper binding
#pragma once

namespace nanobind { class module_; }

namespace termin {
void bind_tc_component_python(nanobind::module_& m);
} // namespace termin
