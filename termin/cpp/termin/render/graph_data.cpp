#include "graph_data.hpp"
#include <tcbase/tc_log.hpp>
#include <trent/json.h>

namespace tc {

NodeData* GraphData::get_node(const std::string& id) {
    for (auto& node : nodes) {
        if (node.id == id) {
            return &node;
        }
    }
    return nullptr;
}

const NodeData* GraphData::get_node(const std::string& id) const {
    for (const auto& node : nodes) {
        if (node.id == id) {
            return &node;
        }
    }
    return nullptr;
}

// Socket definitions for known pass classes
static const std::unordered_map<std::string, PassSocketInfo> g_pass_socket_info = {
    {"ColorPass", {
        {{"input_res", "fbo"}, {"shadow_res", "shadow"}},  // inputs
        {{"output_res", "fbo"}}  // outputs
    }},
    {"DepthPass", {
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}}
    }},
    {"NormalPass", {
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}}
    }},
    {"IdPass", {
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}}
    }},
    {"ShadowPass", {
        {},  // no inputs
        {{"output_res", "shadow"}}
    }},
    {"SkyBoxPass", {
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}}
    }},
    {"BloomPass", {
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}}
    }},
    {"TonemapPass", {
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}}
    }},
    {"MaterialPass", {
        {},  // dynamic inputs
        {{"output_res", "fbo"}}
    }},
    {"ResolvePass", {
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}}
    }},
    {"PresentToScreenPass", {
        {{"input_res", "fbo"}},
        {}  // no outputs
    }},
    {"ColliderGizmoPass", {
        {{"input_res", "fbo"}},
        {{"output_res", "fbo"}}
    }},
};

PassSocketInfo get_pass_sockets(const std::string& class_name) {
    auto it = g_pass_socket_info.find(class_name);
    if (it != g_pass_socket_info.end()) {
        return it->second;
    }
    // Default: single input/output FBO
    return {{{"input_res", "fbo"}}, {{"output_res", "fbo"}}};
}

GraphData GraphData::from_trent(const nos::trent& t) {
    GraphData graph;

    // Parse nodes
    if (t.contains("nodes") && t["nodes"].is_list()) {
        const auto& nodes_list = t["nodes"].as_list();
        for (size_t i = 0; i < nodes_list.size(); ++i) {
            const auto& node_t = nodes_list[i];
            NodeData node;

            node.id = std::to_string(i);  // Use index as ID

            // "type" is the pass class name (e.g., "ColorPass")
            if (node_t.contains("type") && node_t["type"].is_string()) {
                node.pass_class = node_t["type"].as_string();
            }

            // "node_type" is the category: "pass", "resource", "output"
            if (node_t.contains("node_type") && node_t["node_type"].is_string()) {
                node.node_type = node_t["node_type"].as_string();
            } else {
                node.node_type = "pass";  // Default
            }

            // Instance name
            if (node_t.contains("name") && node_t["name"].is_string()) {
                node.name = node_t["name"].as_string();
            }

            // Parameters
            if (node_t.contains("params") && node_t["params"].is_dict()) {
                node.params = node_t["params"];
            }

            // Position
            if (node_t.contains("x") && node_t["x"].is_numer()) {
                node.x = static_cast<float>(node_t["x"].as_numer());
            }
            if (node_t.contains("y") && node_t["y"].is_numer()) {
                node.y = static_cast<float>(node_t["y"].as_numer());
            }

            // Get sockets from pass class registry
            // Check for pass-like nodes (pass, effect, or any non-resource/non-output type)
            bool is_pass = (node.node_type != "resource" && node.node_type != "output");
            if (is_pass && !node.pass_class.empty()) {
                auto sockets = get_pass_sockets(node.pass_class);
                for (const auto& [name, type] : sockets.inputs) {
                    node.inputs.push_back({name, type, true});
                }
                for (const auto& [name, type] : sockets.outputs) {
                    node.outputs.push_back({name, type, false});
                    // Add corresponding _target input for output sockets
                    std::string target_name = name + "_target";
                    node.inputs.push_back({target_name, type, true});
                }

                // Add dynamic inputs from serialized data
                if (node_t.contains("dynamic_inputs") && node_t["dynamic_inputs"].is_list()) {
                    for (const auto& dyn : node_t["dynamic_inputs"].as_list()) {
                        if (dyn.is_list() && dyn.as_list().size() >= 2) {
                            std::string dyn_name = dyn[0].as_string();
                            std::string dyn_type = dyn[1].as_string();
                            // Check if not already in inputs
                            bool found = false;
                            for (const auto& inp : node.inputs) {
                                if (inp.name == dyn_name) {
                                    found = true;
                                    break;
                                }
                            }
                            if (!found) {
                                node.inputs.push_back({dyn_name, dyn_type, true});
                            }
                        }
                    }
                }
            } else if (node.node_type == "resource") {
                // Resource nodes have single output named "fbo"
                node.outputs.push_back({"fbo", "fbo", false});
            }

            graph.nodes.push_back(std::move(node));
        }
    }

    // Parse connections
    if (t.contains("connections") && t["connections"].is_list()) {
        for (const auto& conn_t : t["connections"].as_list()) {
            ConnectionData conn;

            if (conn_t.contains("from_node")) {
                if (conn_t["from_node"].is_numer()) {
                    conn.from_node_id = std::to_string(static_cast<int>(conn_t["from_node"].as_numer()));
                } else if (conn_t["from_node"].is_string()) {
                    conn.from_node_id = conn_t["from_node"].as_string();
                }
            }
            if (conn_t.contains("from_socket") && conn_t["from_socket"].is_string()) {
                conn.from_socket = conn_t["from_socket"].as_string();
            }
            if (conn_t.contains("to_node")) {
                if (conn_t["to_node"].is_numer()) {
                    conn.to_node_id = std::to_string(static_cast<int>(conn_t["to_node"].as_numer()));
                } else if (conn_t["to_node"].is_string()) {
                    conn.to_node_id = conn_t["to_node"].as_string();
                }
            }
            if (conn_t.contains("to_socket") && conn_t["to_socket"].is_string()) {
                conn.to_socket = conn_t["to_socket"].as_string();
            }

            graph.connections.push_back(std::move(conn));
        }
    }

    // Parse viewport frames
    if (t.contains("viewport_frames") && t["viewport_frames"].is_list()) {
        for (const auto& vf_t : t["viewport_frames"].as_list()) {
            ViewportFrameData vf;

            if (vf_t.contains("viewport_name") && vf_t["viewport_name"].is_string()) {
                vf.viewport_name = vf_t["viewport_name"].as_string();
            }
            if (vf_t.contains("x") && vf_t["x"].is_numer()) {
                vf.x = static_cast<float>(vf_t["x"].as_numer());
            }
            if (vf_t.contains("y") && vf_t["y"].is_numer()) {
                vf.y = static_cast<float>(vf_t["y"].as_numer());
            }
            if (vf_t.contains("width") && vf_t["width"].is_numer()) {
                vf.width = static_cast<float>(vf_t["width"].as_numer());
            }
            if (vf_t.contains("height") && vf_t["height"].is_numer()) {
                vf.height = static_cast<float>(vf_t["height"].as_numer());
            }

            graph.viewport_frames.push_back(std::move(vf));
        }
    }

    return graph;
}

} // namespace tc
