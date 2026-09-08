#include <cassert>
#include <memory>
#include <string>
#include <vector>

#include <termin/nodegraph/projection.hpp>
#include <termin_visual_scene/scene2d.hpp>

#include "projection_test_support.hpp"

namespace ng = termin::nodegraph;
namespace ngt = termin::nodegraph::test;

namespace {

    class RecordingPolicy final : public ng::PresentationPolicy {
    public:
        ng::NodePalette node_palette(const ng::Node& node) const override {
            node_kinds.push_back(node.kind);
            return {
                {0.11f, 0.12f, 0.13f, 1.0f},
                {0.21f, 0.22f, 0.23f, 1.0f},
                {0.31f, 0.32f, 0.33f, 1.0f},
                {0.91f, 0.92f, 0.93f, 1.0f},
            };
        }

        ng::ProjectionColor
        socket_color(const ng::Node&, const ng::Socket& socket, ng::SocketDirection direction) const override {
            socket_types.push_back(socket.type);
            directions.push_back(direction);
            return direction == ng::SocketDirection::Input ? ng::ProjectionColor{0.4f, 0.5f, 0.6f, 1.0f}
                                                           : ng::ProjectionColor{0.7f, 0.8f, 0.9f, 1.0f};
        }

        mutable std::vector<std::string> node_kinds;
        mutable std::vector<std::string> socket_types;
        mutable std::vector<ng::SocketDirection> directions;
    };

    bool has(const std::vector<std::string>& values, const std::string& value) {
        for (const std::string& candidate : values) {
            if (candidate == value) {
                return true;
            }
        }
        return false;
    }

} // namespace

int main() {
    ng::Graph graph;
    auto source = graph.create_node(ngt::node("source", "arbitrary.producer", 10.0f, 40.0f, {}, "spectral-field"));
    auto sink = graph.create_node(ngt::node("sink", "unregistered.consumer", 410.0f, 40.0f, "spectral-field"));
    auto group = graph.create_group({"group", "Generic group", -180.0f, -90.0f, 120.0f, 80.0f});
    assert(source && sink && group);
    auto edge = graph.connect(ngt::connect(source.value, sink.value, "edge"));
    assert(edge);

    auto policy = std::make_shared<RecordingPolicy>();
    ng::NodeGraphProjection projection(&graph, policy);
    assert(!projection.closed());
    assert(projection.graph() == &graph);
    assert(projection.projected_revision() == graph.revision());

    termin::visual::TcVisualScene scene{projection.scene()};
    assert(scene.valid());
    const auto source_item = projection.node_item(source.value);
    const auto sink_item = projection.node_item(sink.value);
    const auto group_item = projection.group_item(group.value);
    const auto edge_item = projection.edge_item(edge.value.edge);
    const auto source_socket_item = projection.socket_item(ngt::output(source.value));
    const auto sink_socket_item = projection.socket_item(ngt::input(sink.value));
    assert(ngt::valid_item(source_item) && ngt::valid_item(sink_item));
    assert(ngt::valid_item(group_item) && ngt::valid_item(edge_item));
    assert(ngt::valid_item(source_socket_item) && ngt::valid_item(sink_socket_item));
    assert(scene.contains(source_item) && scene.contains(sink_item));
    assert(scene.contains(group_item) && scene.contains(edge_item));
    assert(has(policy->node_kinds, "arbitrary.producer"));
    assert(has(policy->node_kinds, "unregistered.consumer"));
    assert(has(policy->socket_types, "spectral-field"));

    const auto source_node = graph.node(source.value);
    const auto sink_node = graph.node(sink.value);
    assert(source_node && sink_node);
    const auto source_socket = ngt::socket_position(*source_node, ng::SocketDirection::Output);
    const auto sink_socket = ngt::socket_position(*sink_node, ng::SocketDirection::Input);

    auto node_hit = projection.hit_test(source_node->x + 60.0f, source_node->y + 80.0f);
    assert(node_hit && node_hit->semantic.kind == ng::SemanticKind::Node);
    assert(node_hit->semantic.node == source.value);

    auto socket_hit = projection.hit_test(source_socket.first, source_socket.second);
    assert(socket_hit && socket_hit->semantic.kind == ng::SemanticKind::Socket);
    assert(socket_hit->semantic.socket == ngt::output(source.value));

    auto group_hit = projection.hit_test(-120.0f, -50.0f);
    assert(group_hit && group_hit->semantic.kind == ng::SemanticKind::Group);
    assert(group_hit->semantic.group == group.value);

    const float edge_mid_x = (source_socket.first + sink_socket.first) * 0.5f;
    auto edge_hit = projection.hit_test(edge_mid_x, source_socket.second);
    assert(edge_hit && edge_hit->semantic.kind == ng::SemanticKind::Edge);
    assert(edge_hit->semantic.edge == edge.value.edge);

    // External edits are synchronized by revision. A rebuild retires every old
    // scene handle and exposes the newly added generic node without requiring
    // the projection to know its kind.
    const auto old_source_item = source_item;
    auto external =
        graph.create_node(ngt::node("external", "plugin.runtime.node", 720.0f, -130.0f, "opaque-a", "opaque-b"));
    assert(external);
    assert(projection.sync());
    assert(projection.projected_revision() == graph.revision());
    assert(!scene.contains(old_source_item));
    const auto external_item = projection.node_item(external.value);
    assert(ngt::valid_item(external_item) && scene.contains(external_item));
    assert(has(policy->node_kinds, "plugin.runtime.node"));
    assert(has(policy->socket_types, "opaque-a"));
    assert(has(policy->socket_types, "opaque-b"));
    const auto stable_external_item = projection.node_item(external.value);
    assert(!projection.sync());
    assert(ngt::same_item(stable_external_item, projection.node_item(external.value)));

    assert(graph.move_node(external.value, 811.0f, -77.0f));
    const auto before_move_sync = external_item;
    assert(projection.sync());
    assert(!scene.contains(before_move_sync));
    assert(ngt::valid_item(projection.node_item(external.value)));

    // set_graph clears semantic state and retires handles from the previous
    // projection even though the visual-scene owner itself is reused.
    const auto source_after_sync = projection.node_item(source.value);
    const auto selected_node = graph.node(source.value);
    assert(selected_node);
    ngt::click(projection, selected_node->x + 50.0f, selected_node->y + 75.0f, 1.7f);
    assert(projection.selection() && projection.selection()->kind == ng::SemanticKind::Node);

    ng::Graph replacement;
    auto replacement_node = replacement.create_node(ngt::node("replacement", "other.graph.kind", -300.0f, 500.0f));
    assert(replacement_node);
    assert(projection.set_graph(&replacement));
    assert(projection.graph() == &replacement);
    assert(!projection.selection());
    assert(!scene.contains(source_after_sync));
    assert(ngt::valid_item(projection.node_item(replacement_node.value)));
    assert(tc_graphic_item_handle_is_invalid(projection.node_item(source.value)));

    const std::uint64_t graph_revision_before_close = replacement.revision();
    projection.close();
    assert(projection.closed());
    assert(!termin::visual::TcVisualScene{projection.scene()}.valid());
    projection.close();
    assert(projection.closed());

    // The caller owns the graph; retiring the projection cannot retire or
    // invalidate it.
    assert(replacement.move_node(replacement_node.value, 17.0f, 19.0f));
    assert(replacement.revision() == graph_revision_before_close + 1);
    assert(replacement.node(replacement_node.value)->x == 17.0f);

    return 0;
}
