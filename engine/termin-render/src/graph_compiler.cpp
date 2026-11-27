#include "termin/render/graph_compiler.hpp"
#include "termin/render/render_pipeline.hpp"
#include <algorithm>
#include <cstdlib>
#include <deque>
#include <optional>
#include <tcbase/tc_log.hpp>
#include <tcbase/tc_trent_json.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin/render/graph_alias_pass.hpp>
#include <termin/render/graph_node_def.hpp>
#include <termin/render/resource_spec.hpp>
#include <termin/render/tc_pass.hpp>
#include <trent/json.h>
#include <unordered_map>
#include <unordered_set>

extern "C" {
#include "inspect/tc_inspect_pass_adapter.h"
#include "render/tc_pass.h"
#include "render/tc_pipeline_template_registry.h"
#include "tc_value.h"
}

#include "tc_inspect_cpp.hpp"

using termin::CxxFramePass;
using termin::RenderPipeline;
using termin::ResourceSpec;
using termin::TcPassRef;
using termin::TcPipelineTemplate;
using termin::TextureFilter;

namespace tc {

    static std::optional<int> trent_int_value(const nos::trent& value) {
        if (value.is_numer()) {
            return static_cast<int>(value.as_numer());
        }
        if (!value.is_string()) {
            return std::nullopt;
        }

        const std::string str = value.as_string();
        if (str.empty()) {
            return std::nullopt;
        }

        char* end = nullptr;
        long parsed = std::strtol(str.c_str(), &end, 10);
        if (!end || *end != '\0') {
            return std::nullopt;
        }
        return static_cast<int>(parsed);
    }

    static std::optional<bool> trent_bool_value(const nos::trent& value) {
        if (value.is_bool()) {
            return value.as_bool();
        }
        if (value.is_numer()) {
            return value.as_numer() != 0.0;
        }
        if (!value.is_string()) {
            return std::nullopt;
        }

        const std::string str = value.as_string();
        if (str == "true" || str == "True" || str == "1") {
            return true;
        }
        if (str == "false" || str == "False" || str == "0" || str.empty()) {
            return false;
        }
        return std::nullopt;
    }

    static bool set_pass_property(TcPassRef& pass_ref, const std::string& field_name, const nos::trent& value);

    // ============================================================================
    // Helper: check if node is a pass (pass, effect, or any non-resource type)
    // ============================================================================

    static bool is_pass_node(const NodeData& node) {
        const termin::GraphNodeDef* def = termin::graph_node_def_find(node.node_type);
        if (def) {
            return def->executable;
        }
        return true;
    }

    static bool is_external_resource_name(const std::string& name) {
        return name == "RT_COLOR" || name == "RT_DEPTH" || name == "DISPLAY";
    }

    static bool is_attachment_texture_type(const std::string& type) {
        return type == "color_texture" || type == "depth_texture" || type == "multiview_color_texture" ||
               type == "multiview_depth_texture";
    }

    static bool is_direct_target_resource_type(const std::string& type) {
        return type == "shadow" || type == "shadow_map_array";
    }

    static bool is_graph_alias_node(const NodeData& node) {
        return node.node_type == "render_target_input" || node.node_type == "fbo_split" ||
               node.node_type == "fbo_join" || node.node_type == "multiview_fbo_split" ||
               node.node_type == "multiview_fbo_join" || node.node_type == "external_xr_multiview_fbo";
    }

    static bool graph_compiler_is_target_socket_name(const std::string& name) {
        return name.size() > 7 && name.substr(name.size() - 7) == "_target";
    }

    static std::string graph_compiler_resource_type_for_node(const NodeData& node) {
        if (node.params.contains("resource_type") && node.params["resource_type"].is_string()) {
            return node.params["resource_type"].as_string();
        }
        if (node.pass_class == "Color Texture") {
            return "color_texture";
        }
        if (node.pass_class == "Depth Texture") {
            return "depth_texture";
        }
        if (node.pass_class == "Shadow Maps") {
            return "shadow_map_array";
        }
        if (node.pass_class == "Multiview Color Texture")
            return "multiview_color_texture";
        if (node.pass_class == "Multiview Depth Texture")
            return "multiview_depth_texture";
        if (node.pass_class == "Multiview FBO")
            return "multiview_fbo";
        return "fbo";
    }

    static std::string default_resource_name(const NodeData& node, int node_index, const std::string& resource_type) {
        if (!node.name.empty()) {
            return node.name;
        }
        if (resource_type == "color_texture") {
            return "color_texture_" + std::to_string(node_index);
        }
        if (resource_type == "depth_texture") {
            return "depth_texture_" + std::to_string(node_index);
        }
        if (resource_type == "shadow_map_array") {
            return "shadow_maps_" + std::to_string(node_index);
        }
        return "fbo_" + std::to_string(node_index);
    }

    static std::string generated_input_name(const NodeData& node, int node_index, const std::string& socket_name) {
        std::string node_name = node.name.empty() ? node.pass_class : node.name;
        if (node_name.empty()) {
            node_name = node.node_type;
        }
        return "empty_" + node_name + "_" + std::to_string(node_index) + "_" + socket_name;
    }

    static std::optional<std::string>
    socket_type_for(const NodeData& node, const std::string& socket_name, bool input) {
        const std::vector<SocketData>& sockets = input ? node.inputs : node.outputs;
        for (const auto& socket : sockets) {
            if (socket.name == socket_name) {
                return socket.socket_type;
            }
        }
        return std::nullopt;
    }

    bool graph_socket_type_assignable(const std::string& source_type, const std::string& target_type) {
        if (source_type == target_type) {
            return true;
        }

        // The XR swapchain is externally owned, but its attachment shape is the
        // same as a regular layered multiview FBO. Pass inputs that only require
        // that attachment shape may consume it; the reverse conversion would
        // incorrectly erase the external-ownership requirement.
        return source_type == "external_xr_multiview_fbo" && target_type == "multiview_fbo";
    }

    static void bind_pass_target(const NodeData& node, const SocketData& inp, ResourceNaming& result) {
        std::string base_name = inp.name.substr(0, inp.name.size() - 7);
        auto& sockets = result.socket_names[node.id];
        const std::string& target_res = sockets.at(inp.name);

        auto output_it = sockets.find(base_name);
        if (output_it == sockets.end() || output_it->second.empty()) {
            std::string output_res = node.pass_class.empty()
                                         ? node.id + "_" + base_name
                                         : node.pass_class + "_" + node.id + "_" + base_name;
            sockets[base_name] = output_res;
            output_it = sockets.find(base_name);
        }

        const std::string output_res = output_it->second;
        auto output_type = socket_type_for(node, base_name, false);
        std::string resolved_output_type = output_type.has_value() ? *output_type : inp.socket_type;
        if (resolved_output_type == "fbo" && inp.socket_type != "fbo") {
            resolved_output_type = inp.socket_type;
        }
        result.resource_types[output_res] = resolved_output_type;

        if (output_res != target_res && is_direct_target_resource_type(resolved_output_type)) {
            sockets[base_name] = target_res;
            result.resource_types[target_res] = resolved_output_type;
            result.resource_types.erase(output_res);
            return;
        }

        auto target_view_it = result.resource_views.find(target_res);
        if (target_view_it != result.resource_views.end()) {
            if (output_res != target_res) {
                result.resource_views[output_res] = target_view_it->second;
            }
            return;
        }

        if (is_external_resource_name(target_res)) {
            if (resolved_output_type == "fbo" || resolved_output_type == "external_color") {
                result.fbo_compositions[output_res] = termin::FboComposition{target_res, target_res};
            } else if (resolved_output_type == "depth_texture") {
                result.resource_views[output_res] = termin::ResourceView{
                    target_res,
                    termin::AttachmentKind::Depth,
                };
            } else {
                result.resource_views[output_res] = termin::ResourceView{
                    target_res,
                    termin::AttachmentKind::Color,
                };
            }
            return;
        }

        if (output_res != target_res) {
            if (resolved_output_type == "depth_texture") {
                result.resource_views[output_res] = termin::ResourceView{
                    target_res,
                    termin::AttachmentKind::Depth,
                };
            } else if (resolved_output_type == "color_texture") {
                result.resource_views[output_res] = termin::ResourceView{
                    target_res,
                    termin::AttachmentKind::Color,
                };
            } else if (!is_attachment_texture_type(resolved_output_type)) {
                result.fbo_compositions[output_res] = termin::FboComposition{target_res, target_res};
            }
        }
    }

    static void validate_connection_types(const GraphData& graph) {
        for (const auto& conn : graph.connections) {
            const NodeData* from_node = graph.get_node(conn.from_node_id);
            const NodeData* to_node = graph.get_node(conn.to_node_id);
            if (!from_node || !to_node) {
                throw GraphCompileError("Connection references missing node");
            }

            auto from_type = socket_type_for(*from_node, conn.from_socket, false);
            auto to_type = socket_type_for(*to_node, conn.to_socket, true);
            if (!from_type || !to_type) {
                throw GraphCompileError("Connection references missing socket: " + conn.from_node_id + "." +
                                        conn.from_socket + " -> " + conn.to_node_id + "." + conn.to_socket);
            }

            if (!graph_socket_type_assignable(*from_type, *to_type)) {
                throw GraphCompileError("Invalid resource connection type: " + conn.from_node_id + "." +
                                        conn.from_socket + " (" + *from_type + ") -> " + conn.to_node_id + "." +
                                        conn.to_socket + " (" + *to_type + ")");
            }
        }
    }

    // ============================================================================
    // Topological Sort (Kahn's algorithm)
    // ============================================================================

    struct GraphTraversal {
        std::vector<size_t> order;
        std::vector<std::vector<const ConnectionData*>> incoming;
    };

    static GraphTraversal build_graph_traversal(const GraphData& graph) {
        GraphTraversal traversal;
        traversal.incoming.resize(graph.nodes.size());
        std::unordered_map<std::string, size_t> indices;
        for (size_t i = 0; i < graph.nodes.size(); ++i)
            indices.emplace(graph.nodes[i].id, i);

        std::vector<std::vector<size_t>> dependents(graph.nodes.size());
        for (const ConnectionData& edge : graph.connections) {
            auto source = indices.find(edge.from_node_id);
            auto target = indices.find(edge.to_node_id);
            if (source == indices.end() || target == indices.end())
                throw GraphCompileError("Connection references missing node");
            dependents[source->second].push_back(target->second);
            traversal.incoming[target->second].push_back(&edge);
        }

        std::vector<size_t> remaining;
        std::deque<size_t> ready;
        for (size_t i = 0; i < graph.nodes.size(); ++i) {
            remaining.push_back(traversal.incoming[i].size());
            if (remaining.back() == 0)
                ready.push_back(i);
        }

        traversal.order.reserve(graph.nodes.size());
        while (!ready.empty()) {
            size_t index = ready.front();
            ready.pop_front();
            traversal.order.push_back(index);
            for (size_t dependent : dependents[index]) {
                if (--remaining[dependent] == 0)
                    ready.push_back(dependent);
            }
        }
        if (traversal.order.size() != graph.nodes.size())
            throw GraphCompileError("Graph has cycles");
        return traversal;
    }

    std::vector<NodeData*> topological_sort(GraphData& graph) {
        const auto traversal = build_graph_traversal(graph);
        std::vector<NodeData*> sorted;
        sorted.reserve(graph.nodes.size());
        for (size_t index : traversal.order)
            sorted.push_back(&graph.nodes[index]);
        return sorted;
    }

    static ResourceNaming assign_resource_names(const GraphData& graph, const GraphTraversal& traversal) {
        ResourceNaming result;
        for (size_t index : traversal.order) {
            const NodeData& node = graph.nodes[index];
            auto& sockets = result.socket_names[node.id];
            for (const ConnectionData* edge : traversal.incoming[index]) {
                const auto& source = result.socket_names.at(edge->from_node_id);
                auto output = source.find(edge->from_socket);
                if (output == source.end())
                    throw GraphCompileError("Unresolved output socket: " + edge->from_node_id + "." + edge->from_socket);
                sockets[edge->to_socket] = output->second;
            }

            if (is_pass_node(node)) {
                for (const auto& output : node.outputs) {
                    if (!sockets.contains(output.name)) {
                        std::string name = node.pass_class + "_" + std::to_string(index) + "_" + output.name;
                        sockets[output.name] = name;
                        result.resource_types[name] = output.socket_type;
                    }
                }
                for (const SocketData& input : node.inputs) {
                    if (graph_compiler_is_target_socket_name(input.name) && sockets.contains(input.name))
                        bind_pass_target(node, input, result);
                }
            }

            for (const SocketData& input : node.inputs) {
                if (graph_compiler_is_target_socket_name(input.name) || sockets.contains(input.name))
                    continue;
                std::string name = generated_input_name(node, index, input.name);
                sockets[input.name] = name;
                result.resource_types[name] = input.socket_type;
            }

            if (node.node_type == "resource") {
                std::string resource_type = graph_compiler_resource_type_for_node(node);
                std::string name = default_resource_name(node, index, resource_type);
                for (const auto& output : node.outputs) {
                    sockets[output.name] = name;
                    result.resource_types[name] = output.socket_type;
                }
            } else if (node.node_type == "external_rt") {
                std::string name;
                if (node.params.contains("slot") && node.params["slot"].is_string()) {
                    name = node.params["slot"].as_string();
                }
                if (name.empty()) {
                    name = node.name;
                }
                if (name.empty()) {
                    name = "unnamed";
                    tc::Log::warn("compile_graph: External RT node '%s' has empty slot/name; using '%s'",
                                  node.id.c_str(),
                                  name.c_str());
                }
                for (const auto& output : node.outputs) {
                    sockets[output.name] = name;
                    result.resource_types[name] = "external_color";
                    result.external_resources[name] = "external_texture";
                }
            } else if (node.node_type == "external_xr_multiview_fbo") {
                std::string name = "XR_MULTIVIEW_TARGET";
                if (node.params.contains("slot") && node.params["slot"].is_string() &&
                    !node.params["slot"].as_string().empty()) {
                    name = node.params["slot"].as_string();
                }
                sockets["fbo"] = name;
                result.resource_types[name] = "external_xr_multiview_fbo";
                result.external_resources[name] = "external_xr_multiview_fbo";
            } else if (node.node_type == "render_target_input") {
                for (const auto& output : node.outputs) {
                    if (output.name == "color") {
                        sockets[output.name] = "RT_COLOR";
                        result.resource_types["RT_COLOR"] = "external_color";
                        result.external_resources["RT_COLOR"] = "render_target_color";
                    }
                }
            } else if (node.node_type == "fbo_split" || node.node_type == "multiview_fbo_split") {
                const bool multiview = node.node_type == "multiview_fbo_split";
                const std::string& parent = sockets.at("fbo");
                std::string color_name = parent + ".color";
                std::string depth_name = parent + ".depth";

                sockets["color"] = color_name;
                sockets["depth"] = depth_name;
                result.resource_types[color_name] = multiview ? "multiview_color_texture" : "color_texture";
                result.resource_types[depth_name] = multiview ? "multiview_depth_texture" : "depth_texture";
                result.resource_views[color_name] = termin::ResourceView{
                    parent,
                    termin::AttachmentKind::Color,
                };
                result.resource_views[depth_name] = termin::ResourceView{
                    parent,
                    termin::AttachmentKind::Depth,
                };
            } else if (node.node_type == "fbo_join" || node.node_type == "multiview_fbo_join") {
                const bool multiview = node.node_type == "multiview_fbo_join";
                std::string output_name = node.name.empty() ? "fbo_join_" + std::to_string(index) : node.name;
                sockets["fbo"] = output_name;
                result.resource_types[output_name] = multiview ? "multiview_fbo" : "fbo";
                result.fbo_compositions[output_name] = termin::FboComposition{
                    sockets.at("color"),
                    sockets.at("depth"),
                };
            }
        }

        return result;
    }

    ResourceNaming assign_resource_names(const GraphData& graph) {
        return assign_resource_names(graph, build_graph_traversal(graph));
    }

    // ============================================================================
    // Graph alias marker passes
    // ============================================================================

    static std::string graph_alias_pass_name(const NodeData& node) {
        if (!node.name.empty()) {
            return node.name;
        }
        if (!node.pass_class.empty()) {
            return node.pass_class + "#" + node.id;
        }
        if (!node.node_type.empty()) {
            return node.node_type + "#" + node.id;
        }
        return "GraphAlias#" + node.id;
    }

    static void push_resource_if_present(std::vector<std::string>& resources,
                                         const std::unordered_map<std::string, std::string>& sockets,
                                         const std::string& socket_name) {
        auto it = sockets.find(socket_name);
        if (it == sockets.end() || it->second.empty()) {
            return;
        }
        resources.push_back(it->second);
    }

    static void
    push_alias_pair(std::vector<std::string>& aliases, const std::string& source, const std::string& target) {
        if (source.empty() || target.empty() || source == target) {
            return;
        }
        aliases.push_back(source);
        aliases.push_back(target);
    }

    static void add_graph_alias_pass(RenderPipeline* pipeline, const NodeData& node, const ResourceNaming& naming) {
        if (!pipeline) {
            return;
        }

        auto socket_map_it = naming.socket_names.find(node.id);
        if (socket_map_it == naming.socket_names.end()) {
            tc::Log::error("compile_graph: alias node '%s' has no resolved sockets", node.id.c_str());
            return;
        }

        const auto& sockets = socket_map_it->second;
        std::vector<std::string> reads;
        std::vector<std::string> writes;
        std::vector<std::string> aliases;

        if (node.node_type == "render_target_input" || node.node_type == "external_xr_multiview_fbo") {
            if (node.node_type == "external_xr_multiview_fbo") {
                push_resource_if_present(writes, sockets, "fbo");
            } else {
                push_resource_if_present(writes, sockets, "color");
            }
        } else if (node.node_type == "fbo_split" || node.node_type == "multiview_fbo_split") {
            push_resource_if_present(reads, sockets, "fbo");
            push_resource_if_present(writes, sockets, "color");
            push_resource_if_present(writes, sockets, "depth");
            auto fbo_it = sockets.find("fbo");
            auto color_it = sockets.find("color");
            auto depth_it = sockets.find("depth");
            if (fbo_it != sockets.end()) {
                if (color_it != sockets.end()) {
                    push_alias_pair(aliases, fbo_it->second, color_it->second);
                }
                if (depth_it != sockets.end()) {
                    push_alias_pair(aliases, fbo_it->second, depth_it->second);
                }
            }
        } else if (node.node_type == "fbo_join" || node.node_type == "multiview_fbo_join") {
            push_resource_if_present(reads, sockets, "color");
            push_resource_if_present(reads, sockets, "depth");
            push_resource_if_present(writes, sockets, "fbo");
            auto fbo_it = sockets.find("fbo");
            if (fbo_it != sockets.end()) {
                // assign_resource_names supplies both join inputs, including unconnected sockets.
                const auto color = naming.resource_views.find(sockets.at("color"));
                const auto depth = naming.resource_views.find(sockets.at("depth"));
                if (color != naming.resource_views.end() && depth != naming.resource_views.end() &&
                    color->second.parent == depth->second.parent &&
                    color->second.attachment == termin::AttachmentKind::Color &&
                    depth->second.attachment == termin::AttachmentKind::Depth) {
                    push_alias_pair(aliases, color->second.parent, fbo_it->second);
                }
            }
        } else {
            return;
        }

        if (reads.empty() && writes.empty()) {
            tc::Log::warn("compile_graph: alias node '%s' produced no read/write resources", node.id.c_str());
            return;
        }

        auto* pass = new termin::GraphAliasPass(
            std::move(reads), std::move(writes), std::move(aliases), graph_alias_pass_name(node));
        pipeline->add_pass(pass->tc_pass_ptr());
    }

    // ============================================================================
    // Viewport Frame Mapping
    // ============================================================================

    const ViewportFrameData* find_containing_frame(const NodeData& node, const std::vector<ViewportFrameData>& frames) {
        if (frames.empty()) {
            return nullptr;
        }

        float node_cx = node.x + 100.0f; // Approximate node center
        float node_cy = node.y + 50.0f;

        for (const auto& frame : frames) {
            if (frame.x <= node_cx && node_cx <= frame.x + frame.width && frame.y <= node_cy &&
                node_cy <= frame.y + frame.height) {
                return &frame;
            }
        }

        return nullptr;
    }

    std::unordered_map<std::string, std::string> build_node_viewport_map(const std::vector<NodeData>& nodes,
                                                                         const std::vector<ViewportFrameData>& frames) {
        std::unordered_map<std::string, std::string> result;

        for (const auto& node : nodes) {
            const auto* frame = find_containing_frame(node, frames);
            result[node.id] = frame ? frame->viewport_name : "";
        }

        return result;
    }


    // ============================================================================
    // Set pass property via TcPassRef
    // ============================================================================

    static bool set_pass_property(TcPassRef& pass_ref, const std::string& field_name, const nos::trent& value) {
        if (!pass_ref.valid())
            return false;

        tc::init_cpp_inspect_vtable();

        tc_value tc_val = trent_to_tc_value(value);
        bool result = pass_ref.set_field(field_name, tc_val);
        tc_value_free(&tc_val);
        if (!result) {
            tc::Log::warn(
                "compile_graph: failed to set field '%s.%s'", pass_ref.type_name().c_str(), field_name.c_str());
        }
        return result;
    }

    static bool
    set_pass_resource_socket(TcPassRef& pass_ref, const std::string& socket_name, const std::string& resource_name) {
        tc_pass* pass = pass_ref.ptr();
        if (pass && pass->kind == TC_NATIVE_PASS) {
            CxxFramePass* cxx_pass = CxxFramePass::from_tc(pass);
            if (cxx_pass && cxx_pass->set_graph_resource_input(socket_name, resource_name)) {
                return true;
            }
        }

        nos::trent res_name_trent(resource_name);
        tc_value tc_val = trent_to_tc_value(res_name_trent);
        bool field_set = pass_ref.set_field(socket_name, tc_val);
        tc_value_free(&tc_val);
        if (field_set) {
            return true;
        }

        return false;
    }

    // ============================================================================
    // Collect FBO nodes
    // ============================================================================

    static std::unordered_map<std::string, const NodeData*> collect_resource_nodes(const GraphData& graph) {
        std::unordered_map<std::string, const NodeData*> result;
        std::unordered_map<std::string, int> node_index;
        for (size_t i = 0; i < graph.nodes.size(); ++i) {
            node_index[graph.nodes[i].id] = static_cast<int>(i);
        }

        for (const auto& node : graph.nodes) {
            if (node.node_type == "resource") {
                std::string resource_type = graph_compiler_resource_type_for_node(node);
                std::string name = default_resource_name(node, node_index[node.id], resource_type);
                result[name] = &node;
            }
        }

        return result;
    }

    // ============================================================================
    // Infer ResourceSpec from FBO node
    // ============================================================================

    static ResourceSpec infer_resource_spec(const std::string& resource_name,
                                            const std::string& resource_type,
                                            const std::unordered_map<std::string, const NodeData*>& resource_nodes) {
        ResourceSpec spec;
        spec.resource = resource_name;
        spec.resource_type = resource_type;
        if (resource_type.starts_with("multiview_")) {
            spec.array_layers = 2;
        }
        if (resource_type == "color_texture" || resource_type == "multiview_color_texture") {
            spec.format = "rgba8";
        } else if (resource_type == "depth_texture" || resource_type == "multiview_depth_texture") {
            spec.format = "depth32f";
        }

        auto it = resource_nodes.find(resource_name);
        if (it != resource_nodes.end()) {
            const NodeData* node = it->second;
            const auto& params = node->params;

            // Format
            if (params.contains("format") && params["format"].is_string()) {
                spec.format = params["format"].as_string();
            }

            // Samples
            if (params.contains("samples")) {
                if (auto samples = trent_int_value(params["samples"])) {
                    spec.samples = *samples;
                } else {
                    tc::Log::warn("compile_graph: resource '%s' has invalid samples value", resource_name.c_str());
                }
            }

            if (params.contains("array_layers")) {
                if (auto layers = trent_int_value(params["array_layers"]); layers && *layers > 0) {
                    spec.array_layers = *layers;
                } else {
                    tc::Log::warn("compile_graph: resource '%s' has invalid array_layers value", resource_name.c_str());
                }
            }

            if (params.contains("has_color")) {
                if (auto has_color = trent_bool_value(params["has_color"])) {
                    spec.has_color = *has_color;
                } else {
                    tc::Log::warn("compile_graph: resource '%s' has invalid has_color value", resource_name.c_str());
                }
            }
            if (params.contains("has_depth")) {
                if (auto has_depth = trent_bool_value(params["has_depth"])) {
                    spec.has_depth = *has_depth;
                } else {
                    tc::Log::warn("compile_graph: resource '%s' has invalid has_depth value", resource_name.c_str());
                }
            }
            // Filter
            if (params.contains("filter") && params["filter"].is_string()) {
                std::string filter_mode = params["filter"].as_string();
                spec.filter = (filter_mode == "nearest") ? TextureFilter::NEAREST : TextureFilter::LINEAR;
            }

            // Size
            if (params.contains("size_mode") && params["size_mode"].is_string() &&
                params["size_mode"].as_string() == "fixed") {
                int width = 0, height = 0;
                if (params.contains("width") && params["width"].is_numer()) {
                    width = static_cast<int>(params["width"].as_numer());
                }
                if (params.contains("height") && params["height"].is_numer()) {
                    height = static_cast<int>(params["height"].as_numer());
                }
                if (width > 0 && height > 0) {
                    spec.size = std::make_pair(width, height);
                }
            } else {
                // Scale
                if (params.contains("scale") && params["scale"].is_numer()) {
                    float scale_value = static_cast<float>(params["scale"].as_numer());
                    if (scale_value != 1.0f) {
                        spec.scale = scale_value;
                    }
                }
            }

            // Clear color
            if (params.contains("clear_color") && trent_bool_value(params["clear_color"]).value_or(false)) {
                double r = 0, g = 0, b = 0, a = 1;
                if (params.contains("clear_color_r") && params["clear_color_r"].is_numer()) {
                    r = params["clear_color_r"].as_numer();
                }
                if (params.contains("clear_color_g") && params["clear_color_g"].is_numer()) {
                    g = params["clear_color_g"].as_numer();
                }
                if (params.contains("clear_color_b") && params["clear_color_b"].is_numer()) {
                    b = params["clear_color_b"].as_numer();
                }
                if (params.contains("clear_color_a") && params["clear_color_a"].is_numer()) {
                    a = params["clear_color_a"].as_numer();
                }
                spec.clear_color = termin::LinearColor{static_cast<float>(r), static_cast<float>(g),
                                                       static_cast<float>(b), static_cast<float>(a)};
            }

            // Clear depth
            if (params.contains("clear_depth") && trent_bool_value(params["clear_depth"]).value_or(false)) {
                double depth_value = 1.0;
                if (params.contains("clear_depth_value") && params["clear_depth_value"].is_numer()) {
                    depth_value = params["clear_depth_value"].as_numer();
                }
                spec.clear_depth = static_cast<float>(depth_value);
            }

            if (resource_type == "depth_texture" && (!spec.format || spec.format == "rgba8")) {
                spec.format = "depth32f";
            }

            return spec;
        }

        // No explicit resource node found; keep the type/default format inferred
        // from graph sockets so RenderEngine allocates the right resource kind.
        return spec;
    }

    // ============================================================================
    // Main Compilation Function
    // ============================================================================

    namespace {

        struct CompiledPassStorage {
            std::string type_name;
            std::string name;
            std::string parameters;
            std::string viewport_name;
        };

        struct CompiledResourceStorage {
            std::string name;
            std::string resource_type;
            std::string format;
            std::string viewport_name;
        };

        struct CompiledDependencyStorage {
            uint32_t pass_index = 0;
            std::string resource;
            tc_pipeline_resource_access access = TC_PIPELINE_RESOURCE_READ;
        };

        struct CompiledResourceViewStorage {
            std::string name;
            std::string parent;
            tc_pipeline_attachment_kind attachment = TC_PIPELINE_ATTACHMENT_COLOR;
        };

        struct CompiledFboCompositionStorage {
            std::string name;
            std::string color;
            std::string depth;
        };

        void collect_dependencies(tc_pass* pass,
                                  uint32_t pass_index,
                                  size_t (*enumerate)(tc_pass*, const char**, size_t),
                                  tc_pipeline_resource_access access,
                                  std::vector<CompiledDependencyStorage>& output) {
            const size_t count = enumerate(pass, nullptr, 0);
            std::vector<const char*> names(count);
            const size_t actual = enumerate(pass, names.data(), names.size());
            if (actual != count) {
                tc::Log::error("compile_graph: pass '%s' changed dependency count during descriptor lowering",
                               pass && pass->pass_name ? pass->pass_name : "<unnamed>");
                return;
            }
            for (const char* name : names) {
                if (name && name[0])
                    output.push_back({pass_index, name, access});
            }
        }

    } // namespace

    bool publish_pipeline_template(RenderPipeline& instance,
                                   const TcPipelineTemplate& pipeline_template,
                                   const std::vector<std::string>& pass_parameters,
                                   const std::vector<PipelineTemplateTarget>& targets,
                                   tc_pipeline_execution_model execution_model) {
        std::vector<CompiledPassStorage> pass_storage;
        std::vector<tc_pipeline_template_pass_desc> pass_descs;
        pass_storage.reserve(instance.pass_count());
        pass_descs.reserve(instance.pass_count());
        std::vector<CompiledDependencyStorage> dependency_storage;

        for (uint32_t i = 0; i < instance.pass_count(); ++i) {
            tc_pass* pass = instance.get_pass_at(i);
            if (!pass)
                continue;
            CompiledPassStorage stored;
            stored.type_name = tc_pass_type_name(pass);
            stored.name = pass->pass_name ? pass->pass_name : stored.type_name;
            stored.viewport_name = pass->viewport_name ? pass->viewport_name : "";
            if (i < pass_parameters.size())
                stored.parameters = pass_parameters[i];
            pass_storage.push_back(std::move(stored));
            collect_dependencies(pass, i, tc_pass_get_reads, TC_PIPELINE_RESOURCE_READ, dependency_storage);
            collect_dependencies(pass, i, tc_pass_get_writes, TC_PIPELINE_RESOURCE_WRITE, dependency_storage);
        }
        for (const CompiledPassStorage& stored : pass_storage) {
            pass_descs.push_back({
                stored.type_name.c_str(),
                stored.name.c_str(),
                stored.parameters.empty() ? nullptr : stored.parameters.c_str(),
                stored.viewport_name.empty() ? nullptr : stored.viewport_name.c_str(),
            });
        }

        const std::vector<ResourceSpec> specs = instance.collect_specs();
        const termin::PipelineRenderCache& cache = instance.cache();
        std::vector<CompiledResourceStorage> resource_storage;
        std::vector<tc_pipeline_template_resource_desc> resource_descs;
        resource_storage.reserve(specs.size() + dependency_storage.size());
        std::unordered_map<std::string, size_t> resource_indices;
        for (const ResourceSpec& spec : specs) {
            if (spec.resource.empty() || resource_indices.contains(spec.resource))
                continue;
            // Pass defaults describe their input attachment requirements. They
            // must not allocate a second resource when graph lowering already
            // resolved that input to a view or a composed framebuffer.
            if (cache.resource_views.contains(spec.resource) ||
                cache.fbo_compositions.contains(spec.resource))
                continue;
            resource_indices[spec.resource] = resource_storage.size();
            resource_storage.push_back({
                spec.resource,
                spec.resource_type,
                spec.format.value_or(""),
                spec.viewport_name,
            });
        }
        const auto add_external_resource = [&](const std::string& name) {
            if (name.empty() || resource_indices.contains(name))
                return;
            resource_indices[name] = resource_storage.size();
            resource_storage.push_back({name, "external", "", ""});
        };
        for (const CompiledDependencyStorage& dependency : dependency_storage) {
            if (resource_indices.contains(dependency.resource))
                continue;
            if (cache.resource_views.contains(dependency.resource) ||
                cache.fbo_compositions.contains(dependency.resource)) {
                continue;
            }
            add_external_resource(dependency.resource);
        }
        resource_descs.reserve(resource_storage.size());
        for (const CompiledResourceStorage& stored : resource_storage) {
            const ResourceSpec* spec = nullptr;
            for (const ResourceSpec& candidate : specs) {
                if (candidate.resource == stored.name) {
                    spec = &candidate;
                    break;
                }
            }
            uint32_t flags = 0;
            uint32_t initialization_flags = 0;
            if (spec && spec->has_color) {
                flags |= TC_PIPELINE_RESOURCE_COLOR_PRESENT;
                if (*spec->has_color)
                    flags |= TC_PIPELINE_RESOURCE_COLOR_ENABLED;
            }
            if (spec && spec->has_depth) {
                flags |= TC_PIPELINE_RESOURCE_DEPTH_PRESENT;
                if (*spec->has_depth)
                    flags |= TC_PIPELINE_RESOURCE_DEPTH_ENABLED;
            }
            if (spec && spec->clear_color) {
                initialization_flags |= TC_PIPELINE_RESOURCE_CLEAR_COLOR_PRESENT;
            }
            if (spec && spec->clear_depth) {
                initialization_flags |= TC_PIPELINE_RESOURCE_CLEAR_DEPTH_PRESENT;
            }
            resource_descs.push_back({
                stored.name.c_str(),
                stored.resource_type.c_str(),
                stored.format.empty() ? nullptr : stored.format.c_str(),
                stored.viewport_name.empty() ? nullptr : stored.viewport_name.c_str(),
                spec && spec->size ? spec->size->first : 0,
                spec && spec->size ? spec->size->second : 0,
                spec ? spec->scale : 1.0f,
                spec ? static_cast<uint32_t>(spec->samples) : 1u,
                spec ? static_cast<uint32_t>(spec->array_layers) : 1u,
                flags,
                {spec && spec->clear_color ? spec->clear_color->r : 0.0f,
                 spec && spec->clear_color ? spec->clear_color->g : 0.0f,
                 spec && spec->clear_color ? spec->clear_color->b : 0.0f,
                 spec && spec->clear_color ? spec->clear_color->a : 0.0f},
                spec && spec->clear_depth ? *spec->clear_depth : 0.0f,
                initialization_flags,
            });
        }

        std::vector<tc_pipeline_template_dependency_desc> dependency_descs;
        dependency_descs.reserve(dependency_storage.size());
        for (const CompiledDependencyStorage& stored : dependency_storage) {
            dependency_descs.push_back({stored.pass_index, stored.resource.c_str(), stored.access});
        }

        std::vector<tc_pipeline_template_target_desc> target_descs;
        target_descs.reserve(targets.size());
        for (const PipelineTemplateTarget& stored : targets) {
            target_descs.push_back({
                stored.viewport_name.c_str(),
                stored.export_name.empty() ? nullptr : stored.export_name.c_str(),
                static_cast<tc_color_content>(stored.color_content),
                stored.width,
                stored.height,
            });
        }

        std::vector<CompiledResourceViewStorage> resource_view_storage;
        resource_view_storage.reserve(cache.resource_views.size());
        for (const auto& [name, view] : cache.resource_views) {
            resource_view_storage.push_back({
                name,
                view.parent,
                view.attachment == termin::AttachmentKind::Depth ? TC_PIPELINE_ATTACHMENT_DEPTH
                                                                 : TC_PIPELINE_ATTACHMENT_COLOR,
            });
        }
        std::sort(resource_view_storage.begin(), resource_view_storage.end(), [](const auto& lhs, const auto& rhs) {
            return lhs.name < rhs.name;
        });
        std::vector<tc_pipeline_template_resource_view_desc> resource_view_descs;
        resource_view_descs.reserve(resource_view_storage.size());
        for (const CompiledResourceViewStorage& stored : resource_view_storage) {
            resource_view_descs.push_back({
                stored.name.c_str(),
                stored.parent.c_str(),
                stored.attachment,
            });
        }

        std::vector<CompiledFboCompositionStorage> fbo_composition_storage;
        fbo_composition_storage.reserve(cache.fbo_compositions.size());
        for (const auto& [name, composition] : cache.fbo_compositions) {
            fbo_composition_storage.push_back({name, composition.color, composition.depth});
        }
        std::sort(fbo_composition_storage.begin(), fbo_composition_storage.end(), [](const auto& lhs, const auto& rhs) {
            return lhs.name < rhs.name;
        });
        std::vector<tc_pipeline_template_fbo_composition_desc> fbo_composition_descs;
        fbo_composition_descs.reserve(fbo_composition_storage.size());
        for (const CompiledFboCompositionStorage& stored : fbo_composition_storage) {
            fbo_composition_descs.push_back({
                stored.name.c_str(),
                stored.color.empty() ? nullptr : stored.color.c_str(),
                stored.depth.empty() ? nullptr : stored.depth.c_str(),
            });
        }

        tc_pipeline_template* template_data = pipeline_template.get();
        const std::string pipeline_name = instance.name();
        const tc_pipeline_template_payload_desc payload = {
            TC_PIPELINE_TEMPLATE_DESCRIPTOR_VERSION,
            execution_model,
            pipeline_name.c_str(),
            pass_descs.data(),
            static_cast<uint32_t>(pass_descs.size()),
            resource_descs.data(),
            static_cast<uint32_t>(resource_descs.size()),
            dependency_descs.data(),
            static_cast<uint32_t>(dependency_descs.size()),
            target_descs.data(),
            static_cast<uint32_t>(target_descs.size()),
            resource_view_descs.data(),
            static_cast<uint32_t>(resource_view_descs.size()),
            fbo_composition_descs.data(),
            static_cast<uint32_t>(fbo_composition_descs.size()),
        };
        if (!template_data || !tc_pipeline_template_set_payload(template_data, &payload)) {
            tc::Log::error("publish_pipeline_template: failed to publish canonical pipeline template");
            return false;
        }
        return true;
    }

    static RenderPipeline* compile_graph_impl(GraphData& graph, const TcPipelineTemplate* pipeline_template) {
        if (graph.execution_model != "single_view" && graph.execution_model != "xr_multiview") {
            throw GraphCompileError("invalid or missing pipeline execution_model");
        }
        validate_connection_types(graph);

        // 1. Topological sort
        const auto traversal = build_graph_traversal(graph);

        // 2. Assign resource names
        auto naming = assign_resource_names(graph, traversal);

        // 3. Build viewport map
        auto viewport_map = build_node_viewport_map(graph.nodes, graph.viewport_frames);

        // PipelineOutput is declarative metadata. It publishes an existing
        // resource and never materializes an OUTPUT resource or executable pass.
        std::vector<PipelineTemplateTarget> color_exports;
        std::unordered_set<std::string> export_viewports;
        for (size_t index = 0; index < graph.nodes.size(); ++index) {
            const NodeData& node = graph.nodes[index];
            if (node.node_type != "pipeline_output")
                continue;
            size_t incoming_count = 0;
            for (const ConnectionData* edge : traversal.incoming[index]) {
                if (edge->to_socket == "color")
                    ++incoming_count;
            }
            if (incoming_count != 1) {
                throw GraphCompileError("PipelineOutput '" + node.id +
                                        "' must have exactly one connected color input");
            }
            const auto node_sockets = naming.socket_names.find(node.id);
            if (node_sockets == naming.socket_names.end()) {
                throw GraphCompileError("PipelineOutput '" + node.id + "' has no resolved sockets");
            }
            const auto color = node_sockets->second.find("color");
            if (color == node_sockets->second.end() || color->second.empty()) {
                throw GraphCompileError("PipelineOutput '" + node.id + "' has no resolved color resource");
            }
            const std::string viewport_name = viewport_map[node.id];
            if (!export_viewports.insert(viewport_name).second) {
                throw GraphCompileError("multiple PipelineOutput nodes publish color for viewport '" +
                                        viewport_name + "'");
            }
            termin::ColorContent content = termin::ColorContent::DisplayLinear;
            if (node.params.contains("color_content") && node.params["color_content"].is_string()) {
                const std::string semantic = node.params["color_content"].as_string();
                if (semantic == "scene_linear")
                    content = termin::ColorContent::SceneLinear;
                else if (semantic == "display_linear")
                    content = termin::ColorContent::DisplayLinear;
                else if (semantic == "display_srgb")
                    content = termin::ColorContent::DisplaySRGB;
                else
                    throw GraphCompileError("PipelineOutput '" + node.id +
                                            "' has unsupported color_content '" + semantic + "'");
            }
            color_exports.push_back({viewport_name, color->second, content, 0, 0});
        }
        if (pipeline_template && color_exports.empty()) {
            tc::Log::warn("compile_graph: canonical pipeline publishes no PipelineOutput color export");
        }

        // 4. Collect explicit resource nodes for ResourceSpec inference
        auto resource_nodes = collect_resource_nodes(graph);

        // 5. Create pipeline
        // Always compile into an isolated candidate. Instantiating directly from
        // an existing resource would hydrate its previous pass plan and append
        // the candidate passes during hot reload.
        auto* pipeline = new RenderPipeline("compiled_graph");
        if (pipeline_template)
            pipeline->set_name(pipeline_template->name());
        pipeline->cache().resource_views = naming.resource_views;
        pipeline->cache().fbo_compositions = naming.fbo_compositions;
        for (const PipelineTemplateTarget& value : color_exports) {
            pipeline->set_color_export(value.export_name, value.color_content, value.viewport_name);
        }

        // 6. Add passes
        bool had_pass_nodes = false;
        for (size_t index : traversal.order) {
            const auto* node = &graph.nodes[index];
            if (!is_pass_node(*node)) {
                if (is_graph_alias_node(*node)) {
                    add_graph_alias_pass(pipeline, *node, naming);
                }
                continue;
            }
            had_pass_nodes = true;

            // Check if pass type is registered
            if (!tc_pass_registry_has(node->pass_class.c_str())) {
                tc::Log::error("compile_graph: Unknown pass class '%s'", node->pass_class.c_str());
                continue;
            }

            // Create pass via registry (works for both native C++ and Python passes)
            tc_pass* pass_ptr = tc_pass_registry_create(node->pass_class.c_str());
            if (!pass_ptr) {
                tc::Log::error("compile_graph: Failed to create pass '%s'", node->pass_class.c_str());
                continue;
            }

            // Wrap in TcPassRef for all operations
            TcPassRef pass_ref(pass_ptr);

            if (!pass_ref.object_ptr()) {
                tc::Log::error("compile_graph: Failed to get object pointer for '%s'", node->pass_class.c_str());
                tc_pass_delete_unowned(pass_ptr);
                continue;
            }

            // Set pass name from node name
            if (!node->name.empty()) {
                pass_ref.set_pass_name(node->name);
            }

            // Set viewport name via TcPassRef
            const std::string& viewport_name = viewport_map[node->id];
            if (!viewport_name.empty()) {
                pass_ref.set_viewport_name(viewport_name);
            }

            // Set resource names from sockets via TcPassRef
            auto& socket_map = naming.socket_names[node->id];

            // Set socket-based properties (input_res, output_res, shadow_res, etc.)
            for (const auto& [socket_name, resource_name] : socket_map) {
                nos::trent res_name_trent(resource_name);
                if (graph_compiler_is_target_socket_name(socket_name)) {
                    tc_value tc_val = trent_to_tc_value(res_name_trent);
                    pass_ref.set_field(socket_name, tc_val);
                    tc_value_free(&tc_val);
                } else {
                    if (!set_pass_resource_socket(pass_ref, socket_name, resource_name)) {
                        tc::Log::warn("compile_graph: failed to set resource socket '%s.%s'",
                                      pass_ref.type_name().c_str(),
                                      socket_name.c_str());
                    }
                }
            }

            // Set additional params from node
            if (node->params.is_dict()) {
                for (const auto& [key, value] : node->params.as_dict()) {
                    set_pass_property(pass_ref, key, value);
                }
            }

            if (!tc_pipeline_adopt_pass(pipeline->handle(), pass_ptr, pass_ptr->deleter)) {
                tc::Log::error("compile_graph: Failed to adopt pass '%s'", node->pass_class.c_str());
                tc_pass_delete_unowned(pass_ptr);
            }
        }

        if (pipeline->pass_count() == 0 && had_pass_nodes) {
            tc::Log::error("compile_graph: graph compiled to 0 passes from pass nodes (nodes=%zu, connections=%zu)",
                           graph.nodes.size(),
                           graph.connections.size());
        }

        // 8. Add ResourceSpecs for every concrete resource kind. This also
        // covers generated resources for unconnected inputs.
        std::unordered_set<std::string> live_resources;
        for (const auto& [node_id, sockets] : naming.socket_names) {
            (void)node_id;
            for (const auto& [socket_name, resource_name] : sockets) {
                (void)socket_name;
                live_resources.insert(resource_name);
            }
        }

        std::unordered_set<std::string> seen_resources;
        for (const auto& res_name : live_resources) {
            if (seen_resources.count(res_name)) {
                continue;
            }
            seen_resources.insert(res_name);
            auto type_it = naming.resource_types.find(res_name);
            if (type_it == naming.resource_types.end()) {
                tc::Log::warn("compile_graph: resource '%s' has no inferred type; skipping ResourceSpec",
                              res_name.c_str());
                continue;
            }
            const std::string& resource_type = type_it->second;
            if (resource_type == "shadow" || resource_type == "shadow_map_array") {
                continue;
            }
            if (naming.resource_views.find(res_name) != naming.resource_views.end()) {
                continue;
            }
            if (naming.fbo_compositions.find(res_name) != naming.fbo_compositions.end()) {
                continue;
            }
            if (is_external_resource_name(res_name) || naming.external_resources.contains(res_name) ||
                resource_type.starts_with("external")) {
                ResourceSpec spec;
                spec.resource = res_name;
                spec.resource_type = resource_type.starts_with("external") ? resource_type : "external";
                if (resource_type == "external_xr_multiview_fbo") {
                    spec.array_layers = 2;
                }
                pipeline->add_spec(spec);
                continue;
            }

            auto spec = infer_resource_spec(res_name, resource_type, resource_nodes);
            if (!spec.resource.empty()) {
                pipeline->add_spec(spec);
            }
        }

        if (pipeline_template) {
            tc::init_cpp_inspect_vtable();
            std::vector<std::string> pass_parameters;
            pass_parameters.reserve(pipeline->pass_count());
            for (uint32_t i = 0; i < pipeline->pass_count(); ++i) {
                TcPassRef pass(pipeline->get_pass_at(i));
                const auto fields =
                    tc::trent::adopt(tc_inspect_serialize(pass.object_ptr(), tc_pass_type_name(pass.ptr())));
                pass_parameters.push_back(tc::json::dump(fields));
            }
            const tc_pipeline_execution_model execution_model = graph.execution_model == "xr_multiview"
                                                                    ? TC_PIPELINE_EXECUTION_XR_MULTIVIEW
                                                                    : TC_PIPELINE_EXECUTION_SINGLE_VIEW;
            if (!publish_pipeline_template(
                    *pipeline, *pipeline_template, pass_parameters, color_exports, execution_model)) {
                pipeline->destroy();
                delete pipeline;
                throw GraphCompileError("failed to publish canonical pipeline template");
            }
            auto* published_instance = new RenderPipeline(*pipeline_template);
            pipeline->destroy();
            delete pipeline;
            return published_instance;
        }
        return pipeline;
    }

    RenderPipeline* compile_graph(GraphData& graph) {
        return compile_graph_impl(graph, nullptr);
    }

    RenderPipeline* compile_graph(GraphData& graph, const TcPipelineTemplate& pipeline_template) {
        if (!pipeline_template.is_valid()) {
            throw GraphCompileError("cannot compile graph into an invalid pipeline template");
        }
        return compile_graph_impl(graph, &pipeline_template);
    }

    RenderPipeline* compile_graph(const nos::trent& graph_trent) {
        GraphData graph = GraphData::from_trent(graph_trent);
        return compile_graph(graph);
    }

    RenderPipeline* compile_graph(const std::string& json_str) {
        nos::trent data = nos::json::parse(json_str);
        return compile_graph(data);
    }

    RenderPipeline* compile_graph(const std::string& json_str, const TcPipelineTemplate& pipeline_template) {
        nos::trent data = nos::json::parse(json_str);
        GraphData graph = GraphData::from_trent(data);
        return compile_graph(graph, pipeline_template);
    }

} // namespace tc
