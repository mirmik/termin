#include <cassert>

#include <termin/nodegraph/projection.hpp>
#include <termin_visual_scene/scene2d.hpp>

#include "projection_test_support.hpp"

namespace ng = termin::nodegraph;
namespace ngt = termin::nodegraph::test;

namespace {

    void drag(ng::NodeGraphProjection& projection, float start_x, float start_y, float end_x, float end_y, float zoom) {
        assert(ngt::pointer(projection, ng::PointerPhase::Down, start_x, start_y, zoom));
        assert(ngt::pointer(projection, ng::PointerPhase::Move, end_x, end_y, zoom));
        ngt::pointer(projection, ng::PointerPhase::Up, end_x, end_y, zoom);
    }

} // namespace

int main() {
    ng::Graph graph;
    auto source = graph.create_node(ngt::node("source", "kind.alpha", 1260.0f, -740.0f, {}, "quaternion"));
    auto sink = graph.create_node(ngt::node("sink", "kind.beta", 1710.0f, -740.0f, "quaternion"));
    auto connect_sink = graph.create_node(ngt::node("connect_sink", "kind.delta", 1710.0f, -580.0f, "quaternion"));
    auto mismatch = graph.create_node(ngt::node("mismatch", "kind.gamma", 1710.0f, -420.0f, "matrix-4x4"));
    auto group = graph.create_group({"frame", "Frame", 920.0f, -1010.0f, 250.0f, 170.0f});
    assert(source && sink && connect_sink && mismatch && group);
    auto original_edge = graph.connect(ngt::connect(source.value, sink.value, "original"));
    assert(original_edge);

    ng::NodeGraphProjection projection(&graph);
    termin::visual::TcVisualScene scene{projection.scene()};
    const auto node_handle = projection.node_item(source.value);
    const auto group_handle = projection.group_item(group.value);
    const auto edge_handle = projection.edge_item(original_edge.value.edge);
    assert(ngt::valid_item(node_handle) && ngt::valid_item(group_handle) && ngt::valid_item(edge_handle));
    const auto edge_bounds_before = scene.world_bounds(*scene.resolve(edge_handle));
    assert(edge_bounds_before);

    int graph_changed_count = 0;
    std::uint64_t callback_revision = 0;
    projection.set_graph_changed_callback([&](std::uint64_t revision) {
        ++graph_changed_count;
        callback_revision = revision;
    });

    // Projection-owned drags mutate graph coordinates in world space while
    // preserving retained graphic handles, even at non-unit zoom and large,
    // signed world coordinates. Connected edge geometry is updated in place.
    drag(projection, 1320.0f, -660.0f, 1361.5f, -687.25f, 2.35f);
    const auto moved_source = graph.node(source.value);
    assert(moved_source);
    assert(ngt::near(moved_source->x, 1301.5f));
    assert(ngt::near(moved_source->y, -767.25f));
    assert(ngt::same_item(node_handle, projection.node_item(source.value)));
    assert(ngt::same_item(edge_handle, projection.edge_item(original_edge.value.edge)));
    const auto edge_bounds_after = scene.world_bounds(*scene.resolve(edge_handle));
    assert(edge_bounds_after);
    assert(!ngt::near(edge_bounds_before->x0, edge_bounds_after->x0) ||
           !ngt::near(edge_bounds_before->y0, edge_bounds_after->y0) ||
           !ngt::near(edge_bounds_before->x1, edge_bounds_after->x1) ||
           !ngt::near(edge_bounds_before->y1, edge_bounds_after->y1));
    const auto moved_source_socket = ngt::socket_position(*moved_source, ng::SocketDirection::Output);
    const auto fixed_sink = graph.node(sink.value);
    assert(fixed_sink);
    const auto fixed_sink_socket = ngt::socket_position(*fixed_sink, ng::SocketDirection::Input);
    const auto moved_edge_hit = projection.hit_test((moved_source_socket.first + fixed_sink_socket.first) * 0.5f,
                                                    (moved_source_socket.second + fixed_sink_socket.second) * 0.5f);
    assert(moved_edge_hit && moved_edge_hit->semantic.kind == ng::SemanticKind::Edge);
    assert(moved_edge_hit->semantic.edge == original_edge.value.edge);
    assert(projection.projected_revision() == graph.revision());
    assert(graph_changed_count > 0 && callback_revision == graph.revision());

    drag(projection, 1010.0f, -940.0f, 974.0f, -891.0f, 0.43f);
    const auto moved_group = graph.group(group.value);
    assert(moved_group);
    assert(ngt::near(moved_group->x, 884.0f));
    assert(ngt::near(moved_group->y, -961.0f));
    assert(ngt::same_item(group_handle, projection.group_item(group.value)));

    // A socket gesture creates a graph edge when the model validator accepts
    // the arbitrary type. Both success and rejection clear the preview state.
    const auto source_socket = ngt::socket_position(*moved_source, ng::SocketDirection::Output);
    const auto sink_node = graph.node(connect_sink.value);
    const auto mismatch_node = graph.node(mismatch.value);
    assert(sink_node && mismatch_node);
    const auto sink_socket = ngt::socket_position(*sink_node, ng::SocketDirection::Input);
    const auto mismatch_socket = ngt::socket_position(*mismatch_node, ng::SocketDirection::Input);

    assert(ngt::pointer(projection, ng::PointerPhase::Down, source_socket.first, source_socket.second, 1.6f));
    assert(projection.pending_connection());
    assert(projection.pending_connection()->start == ngt::output(source.value));
    assert(
        ngt::pointer(projection, ng::PointerPhase::Move, sink_socket.first - 30.0f, sink_socket.second + 12.0f, 1.6f));
    assert(projection.pending_connection());
    ngt::pointer(projection, ng::PointerPhase::Up, sink_socket.first, sink_socket.second, 1.6f);
    assert(!projection.pending_connection());
    assert(graph.edges().size() == 2);

    const std::size_t edges_before_rejection = graph.edges().size();
    assert(ngt::pointer(projection, ng::PointerPhase::Down, source_socket.first, source_socket.second, 0.8f));
    assert(projection.pending_connection());
    ngt::pointer(projection, ng::PointerPhase::Up, mismatch_socket.first, mismatch_socket.second, 0.8f);
    assert(!projection.pending_connection());
    assert(graph.edges().size() == edges_before_rejection);

    // Cancel terminates a connection gesture.
    assert(ngt::pointer(projection, ng::PointerPhase::Down, source_socket.first, source_socket.second, 1.0f));
    assert(projection.pending_connection());
    assert(ngt::pointer(projection, ng::PointerPhase::Cancel, -999.0f, 888.0f, 1.0f));
    assert(!projection.pending_connection());

    // Cancel also releases drag ownership. Movement after cancellation must
    // not continue mutating the node.
    const auto cancel_start = graph.node(source.value);
    assert(cancel_start);
    assert(ngt::pointer(projection, ng::PointerPhase::Down, cancel_start->x + 70.0f, cancel_start->y + 80.0f, 1.25f));
    assert(ngt::pointer(projection, ng::PointerPhase::Move, cancel_start->x + 90.0f, cancel_start->y + 95.0f, 1.25f));
    const auto at_cancel = graph.node(source.value);
    assert(at_cancel);
    assert(ngt::pointer(projection, ng::PointerPhase::Cancel, at_cancel->x + 90.0f, at_cancel->y + 95.0f, 1.25f));
    ngt::pointer(projection, ng::PointerPhase::Move, at_cancel->x + 300.0f, at_cancel->y + 300.0f, 1.25f);
    const auto after_cancel_move = graph.node(source.value);
    assert(after_cancel_move);
    assert(ngt::near(after_cancel_move->x, at_cancel->x));
    assert(ngt::near(after_cancel_move->y, at_cancel->y));

    // Edge selection has a screen-space hit radius. At a distant zoom this
    // click is well outside the painted line in world units, but inside its
    // zoom-adjusted semantic target.
    ng::Graph edge_graph;
    auto edge_source = edge_graph.create_node(ngt::node("edge_source", "producer", 0.0f, 0.0f, {}, "token"));
    auto edge_sink = edge_graph.create_node(ngt::node("edge_sink", "consumer", 400.0f, 0.0f, "token"));
    assert(edge_source && edge_sink);
    auto wide_edge = edge_graph.connect(ngt::connect(edge_source.value, edge_sink.value, "wide"));
    assert(wide_edge);
    assert(projection.set_graph(&edge_graph));
    const auto edge_source_node = edge_graph.node(edge_source.value);
    const auto edge_sink_node = edge_graph.node(edge_sink.value);
    assert(edge_source_node && edge_sink_node);
    const auto edge_start = ngt::socket_position(*edge_source_node, ng::SocketDirection::Output);
    const auto edge_end = ngt::socket_position(*edge_sink_node, ng::SocketDirection::Input);
    const float wide_x = (edge_start.first + edge_end.first) * 0.5f;
    const float wide_y = edge_start.second + 20.0f;
    auto zoom_hit = projection.hit_test(wide_x, wide_y, 0.25f);
    assert(zoom_hit && zoom_hit->semantic.kind == ng::SemanticKind::Edge);
    assert(zoom_hit->semantic.edge == wide_edge.value.edge);
    ngt::click(projection, wide_x, wide_y, 0.25f);
    assert(projection.selection() && projection.selection()->kind == ng::SemanticKind::Edge);
    assert(projection.delete_selection());
    assert(edge_graph.edges().empty());
    assert(!projection.selection());

    // Deleting a selected node uses Graph's cascade semantics; deleting a
    // selected group removes only that retained group.
    auto cascade_edge = edge_graph.connect(ngt::connect(edge_source.value, edge_sink.value, "cascade"));
    auto delete_group = edge_graph.create_group({"delete_group", "Delete me", -300.0f, 100.0f, 150.0f, 100.0f});
    assert(cascade_edge && delete_group);
    assert(projection.sync());
    const auto delete_source_node = edge_graph.node(edge_source.value);
    assert(delete_source_node);
    ngt::click(projection, delete_source_node->x + 60.0f, delete_source_node->y + 80.0f);
    assert(projection.selection() && projection.selection()->kind == ng::SemanticKind::Node);
    assert(projection.delete_selection());
    assert(!edge_graph.node(edge_source.value));
    assert(edge_graph.edges().empty());

    ngt::click(projection, -250.0f, 150.0f);
    assert(projection.selection() && projection.selection()->kind == ng::SemanticKind::Group);
    assert(projection.delete_selection());
    assert(!edge_graph.group(delete_group.value));
    assert(edge_graph.node(edge_sink.value));

    return 0;
}
