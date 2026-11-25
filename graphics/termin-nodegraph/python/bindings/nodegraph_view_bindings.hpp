#pragma once

#include <nanobind/nanobind.h>
#include <termin/nodegraph/graph.hpp>

namespace termin::nodegraph::python_bindings {
    Graph& unwrap_graph(nanobind::handle owner);
    nanobind::object copy_value(const tc_value& value);
    void bind_view(nanobind::module_& module);
}
