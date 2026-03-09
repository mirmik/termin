#pragma once

// Graph data structures for render pipeline compilation.
// These are pure data structures parsed from JSON.

#include <string>
#include <vector>
#include <unordered_map>
#include <trent/trent.h>

namespace tc {

struct SocketData {
    std::string name;
    std::string socket_type;  // "fbo", "shadow", "texture"
    bool is_input = false;
};

struct NodeData {
    std::string id;
    std::string node_type;    // "pass", "resource", "output"
    std::string pass_class;   // e.g. "ColorPass", "DepthPass"
    std::string name;         // Instance name
    nos::trent params;        // Heterogeneous parameters as trent dict
    std::vector<SocketData> inputs;
    std::vector<SocketData> outputs;
    float x = 0;
    float y = 0;
};

struct ConnectionData {
    std::string from_node_id;
    std::string from_socket;
    std::string to_node_id;
    std::string to_socket;
};

struct ViewportFrameData {
    std::string viewport_name;
    float x = 0;
    float y = 0;
    float width = 400;
    float height = 300;
};

struct GraphData {
    std::vector<NodeData> nodes;
    std::vector<ConnectionData> connections;
    std::vector<ViewportFrameData> viewport_frames;

    // Find node by ID (returns nullptr if not found)
    NodeData* get_node(const std::string& id);
    const NodeData* get_node(const std::string& id) const;

    // Parse from trent (JSON-parsed data)
    static GraphData from_trent(const nos::trent& t);
};

// Get socket info for a pass class from registry
struct PassSocketInfo {
    std::vector<std::pair<std::string, std::string>> inputs;   // [(name, type)]
    std::vector<std::pair<std::string, std::string>> outputs;  // [(name, type)]
};

PassSocketInfo get_pass_sockets(const std::string& class_name);

} // namespace tc
