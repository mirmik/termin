#pragma once

// Graph compiler - compiles GraphData to RenderPipeline.
// Port of Python termin/nodegraph/graph_compiler.py

#include "graph_data.hpp"
#include "render_pipeline.hpp"
#include <stdexcept>
#include <unordered_map>
#include <vector>

namespace tc {

class GraphCompileError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

// Resource naming result
struct ResourceNaming {
    // node_id -> {socket_name -> resource_name}
    std::unordered_map<std::string, std::unordered_map<std::string, std::string>> socket_names;
    // resource_name -> socket_type
    std::unordered_map<std::string, std::string> resource_types;
    // resource_name -> [alias_names]
    std::unordered_map<std::string, std::vector<std::string>> target_aliases;
};

// Topological sort using Kahn's algorithm
// Returns sorted node pointers. Throws GraphCompileError if cycles detected.
std::vector<NodeData*> topological_sort(GraphData& graph);

// Assign resource names to all sockets
ResourceNaming assign_resource_names(const GraphData& graph);

// Build mapping: node_id -> viewport_name
std::unordered_map<std::string, std::string> build_node_viewport_map(
    const std::vector<NodeData>& nodes,
    const std::vector<ViewportFrameData>& frames
);

// Find viewport frame containing a node by position
const ViewportFrameData* find_containing_frame(
    const NodeData& node,
    const std::vector<ViewportFrameData>& frames
);

// Main compilation functions
termin::RenderPipeline* compile_graph(GraphData& graph);
termin::RenderPipeline* compile_graph(const nos::trent& graph_trent);
termin::RenderPipeline* compile_graph(const std::string& json_str);

} // namespace tc
