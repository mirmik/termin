#pragma once

#include <memory>

#include <termin/nodegraph/c_api.h>
#include <termin/nodegraph/graph.hpp>

namespace termin::nodegraph::detail {

    // Private bridge for sibling nodegraph libraries. The shared lease keeps
    // the graph alive without exposing its address through the public C ABI.
    TERMIN_NODEGRAPH_CORE_API std::shared_ptr<Graph> acquire_c_graph(tc_nodegraph_handle handle);

} // namespace termin::nodegraph::detail
