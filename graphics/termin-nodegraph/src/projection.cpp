#include <termin/nodegraph/projection.hpp>

#include <algorithm>
#include <cmath>
#include <exception>
#include <utility>
#include <vector>

#include <geom/tc_affine2.h>
#include <tcbase/tc_log.hpp>
#include <termin_visual_scene/tc_builtin_items2d.h>
#include <termin_visual_scene/tc_visual_scene_item2d.h>

namespace termin::nodegraph {
    namespace {

        constexpr float title_height = 26.0f;
        constexpr float socket_row_height = 20.0f;
        constexpr float socket_hit_radius = 12.0f;
        constexpr float edge_hit_radius_px = 8.0f;
        constexpr float edge_width = 2.6f;
        constexpr float selected_edge_width = 5.0f;
        constexpr int bezier_steps = 32;

        bool same_item(tc_graphic_item_handle lhs, tc_graphic_item_handle rhs) {
            return lhs.scene_id == rhs.scene_id && lhs.index == rhs.index && lhs.generation == rhs.generation;
        }

        bool finite_point(float x, float y) {
            return std::isfinite(x) && std::isfinite(y);
        }

        tc_visual_color4f visual_color(ProjectionColor value) {
            return {value.r, value.g, value.b, value.a};
        }

        tc_visual_fill_paint2d fill(ProjectionColor color) {
            return {visual_color(color), TC_VISUAL_FILL_RULE_NON_ZERO};
        }

        tc_visual_stroke_paint2d stroke(ProjectionColor color, float width) {
            return {
                visual_color(color),
                width,
                TC_VISUAL_STROKE_JOIN_ROUND,
                TC_VISUAL_STROKE_CAP_ROUND,
                4.0f,
                nullptr,
                0,
                0.0f,
            };
        }

        tc_visual_path2d_view path_view(const std::vector<tc_visual_path_verb2d>& verbs,
                                        const std::vector<tc_vec2f>& points) {
            return {verbs.data(), verbs.size(), points.data(), points.size()};
        }

        tc_graphic_item_handle invalid_item() {
            return tc_graphic_item_handle_invalid();
        }

        SemanticRef node_semantic(NodeHandle handle) {
            SemanticRef result;
            result.kind = SemanticKind::Node;
            result.node = handle;
            return result;
        }

        SemanticRef group_semantic(GroupHandle handle) {
            SemanticRef result;
            result.kind = SemanticKind::Group;
            result.group = handle;
            return result;
        }

        SemanticRef edge_semantic(EdgeHandle handle) {
            SemanticRef result;
            result.kind = SemanticKind::Edge;
            result.edge = handle;
            return result;
        }

        SemanticRef socket_semantic(SocketRef socket) {
            SemanticRef result;
            result.kind = SemanticKind::Socket;
            result.node = socket.node;
            result.socket = std::move(socket);
            return result;
        }

        float point_segment_distance_sq(float px, float py, tc_vec2f start, tc_vec2f end) {
            const float dx = end.x - start.x;
            const float dy = end.y - start.y;
            const float length_sq = dx * dx + dy * dy;
            if (length_sq <= 0.000001f) {
                const float x = px - start.x;
                const float y = py - start.y;
                return x * x + y * y;
            }
            const float projection = std::clamp(((px - start.x) * dx + (py - start.y) * dy) / length_sq, 0.0f, 1.0f);
            const float x = px - (start.x + projection * dx);
            const float y = py - (start.y + projection * dy);
            return x * x + y * y;
        }

        std::vector<tc_vec2f> bezier_samples(tc_vec2f start, tc_vec2f end) {
            const float control_span = std::max(40.0f, std::abs(end.x - start.x) * 0.45f);
            const tc_vec2f control_a{start.x + control_span, start.y};
            const tc_vec2f control_b{end.x - control_span, end.y};
            std::vector<tc_vec2f> result;
            result.reserve(bezier_steps + 1);
            for (int index = 0; index <= bezier_steps; ++index) {
                const float t = static_cast<float>(index) / static_cast<float>(bezier_steps);
                const float mt = 1.0f - t;
                result.push_back({
                    mt * mt * mt * start.x + 3.0f * mt * mt * t * control_a.x + 3.0f * mt * t * t * control_b.x +
                        t * t * t * end.x,
                    mt * mt * mt * start.y + 3.0f * mt * mt * t * control_a.y + 3.0f * mt * t * t * control_b.y +
                        t * t * t * end.y,
                });
            }
            return result;
        }

        std::vector<tc_vec2f> bezier_path_points(tc_vec2f start, tc_vec2f end) {
            const float control_span = std::max(40.0f, std::abs(end.x - start.x) * 0.45f);
            return {
                start,
                {start.x + control_span, start.y},
                {end.x - control_span, end.y},
                end,
            };
        }

        const std::vector<tc_visual_path_verb2d>& bezier_verbs() {
            static const std::vector<tc_visual_path_verb2d> value{
                TC_VISUAL_PATH_MOVE_TO,
                TC_VISUAL_PATH_CUBIC_TO,
            };
            return value;
        }

    } // namespace

    struct NodeGraphProjection::Impl {
        struct SocketVisual {
            SocketRef socket;
            tc_graphic_item_handle item = invalid_item();
        };

        struct NodeVisual {
            NodeHandle node;
            tc_graphic_item_handle item = invalid_item();
            std::vector<SocketVisual> sockets;
        };

        struct GroupVisual {
            GroupHandle group;
            tc_graphic_item_handle item = invalid_item();
        };

        struct EdgeVisual {
            EdgeHandle edge;
            tc_graphic_item_handle item = invalid_item();
        };

        struct DragState {
            SemanticRef semantic;
            float start_world_x = 0.0f;
            float start_world_y = 0.0f;
            float start_x = 0.0f;
            float start_y = 0.0f;
        };

        Graph* graph = nullptr;
        std::shared_ptr<const PresentationPolicy> policy;
        tc_visual_scene_handle scene = tc_visual_scene_handle_invalid();
        std::uint64_t projected_revision = 0;
        bool is_closed = false;
        std::vector<NodeVisual> nodes;
        std::vector<GroupVisual> groups;
        std::vector<EdgeVisual> edges;
        std::optional<SemanticRef> selected;
        std::optional<PendingConnection> pending;
        std::optional<DragState> drag;
        RequestRenderCallback request_render;
        GraphChangedCallback graph_changed;
        ContextRequestedCallback context_requested;

        explicit Impl(Graph* source_graph, std::shared_ptr<const PresentationPolicy> source_policy)
            : graph(source_graph),
              policy(std::move(source_policy)),
              scene(tc_visual_scene_create()) {
            if (!policy)
                policy = std::make_shared<DefaultPresentationPolicy>();
            if (!tc_visual_scene_is_valid(scene)) {
                tc::Log::error("[termin-nodegraph/ui] failed to create visual scene");
                is_closed = true;
            }
        }

        ~Impl() {
            close();
        }

        void close() noexcept {
            if (is_closed)
                return;
            if (tc_visual_scene_is_valid(scene)) {
                tc_visual_scene_clear(scene);
                tc_visual_scene_destroy(scene);
            }
            scene = tc_visual_scene_handle_invalid();
            graph = nullptr;
            nodes.clear();
            groups.clear();
            edges.clear();
            selected.reset();
            pending.reset();
            drag.reset();
            request_render = {};
            graph_changed = {};
            context_requested = {};
            projected_revision = 0;
            is_closed = true;
        }

        void notify_render() const noexcept {
            if (!request_render)
                return;
            try {
                request_render();
            } catch (const std::exception& error) {
                tc::Log::error(error, "[termin-nodegraph/ui] request-render callback failed");
            } catch (...) {
                tc::Log::error("[termin-nodegraph/ui] request-render callback failed: unknown exception");
            }
        }

        void notify_graph_changed() const noexcept {
            if (!graph_changed || graph == nullptr)
                return;
            try {
                graph_changed(graph->revision());
            } catch (const std::exception& error) {
                tc::Log::error(error, "[termin-nodegraph/ui] graph-changed callback failed");
            } catch (...) {
                tc::Log::error("[termin-nodegraph/ui] graph-changed callback failed: unknown exception");
            }
        }

        bool valid_item(tc_graphic_item_handle item) const {
            return tc_visual_scene_item_is_valid(scene, item);
        }

        NodeVisual* find_node_visual(NodeHandle handle) {
            const auto found = std::find_if(
                nodes.begin(), nodes.end(), [handle](const NodeVisual& value) { return value.node == handle; });
            return found == nodes.end() ? nullptr : &*found;
        }

        const NodeVisual* find_node_visual(NodeHandle handle) const {
            const auto found = std::find_if(
                nodes.begin(), nodes.end(), [handle](const NodeVisual& value) { return value.node == handle; });
            return found == nodes.end() ? nullptr : &*found;
        }

        GroupVisual* find_group_visual(GroupHandle handle) {
            const auto found = std::find_if(
                groups.begin(), groups.end(), [handle](const GroupVisual& value) { return value.group == handle; });
            return found == groups.end() ? nullptr : &*found;
        }

        const GroupVisual* find_group_visual(GroupHandle handle) const {
            const auto found = std::find_if(
                groups.begin(), groups.end(), [handle](const GroupVisual& value) { return value.group == handle; });
            return found == groups.end() ? nullptr : &*found;
        }

        EdgeVisual* find_edge_visual(EdgeHandle handle) {
            const auto found = std::find_if(
                edges.begin(), edges.end(), [handle](const EdgeVisual& value) { return value.edge == handle; });
            return found == edges.end() ? nullptr : &*found;
        }

        const EdgeVisual* find_edge_visual(EdgeHandle handle) const {
            const auto found = std::find_if(
                edges.begin(), edges.end(), [handle](const EdgeVisual& value) { return value.edge == handle; });
            return found == edges.end() ? nullptr : &*found;
        }

        const SocketVisual* find_socket_visual(const SocketRef& socket) const {
            const NodeVisual* node = find_node_visual(socket.node);
            if (node == nullptr)
                return nullptr;
            const auto found = std::find_if(node->sockets.begin(), node->sockets.end(), [&](const SocketVisual& value) {
                return value.socket == socket;
            });
            return found == node->sockets.end() ? nullptr : &*found;
        }

        std::optional<tc_vec2f> socket_position(const SocketRef& ref) const {
            if (graph == nullptr)
                return std::nullopt;
            const std::optional<Node> node = graph->node(ref.node);
            if (!node)
                return std::nullopt;
            const auto& sockets = ref.direction == SocketDirection::Output ? node->outputs : node->inputs;
            for (std::size_t index = 0; index < sockets.size(); ++index) {
                if (sockets[index].name == ref.name) {
                    return tc_vec2f{
                        node->x + (ref.direction == SocketDirection::Output ? node->width : 0.0f),
                        node->y + title_height + socket_row_height * (static_cast<float>(index) + 0.5f),
                    };
                }
            }
            return std::nullopt;
        }

        std::optional<std::pair<tc_vec2f, tc_vec2f>> edge_endpoints(const Edge& edge) const {
            const auto start = socket_position({edge.source_node, edge.source_socket, SocketDirection::Output});
            const auto end = socket_position({edge.destination_node, edge.destination_socket, SocketDirection::Input});
            if (!start || !end)
                return std::nullopt;
            return std::pair{*start, *end};
        }

        ProjectionColor socket_color(const Node& node, const Socket& socket, SocketDirection direction) const {
            try {
                return policy->socket_color(node, socket, direction);
            } catch (const std::exception& error) {
                tc::Log::error(error, "[termin-nodegraph/ui] socket presentation policy failed");
            } catch (...) {
                tc::Log::error("[termin-nodegraph/ui] socket presentation policy failed: unknown exception");
            }
            return {0.68f, 0.68f, 0.70f, 1.0f};
        }

        NodePalette node_palette(const Node& node) const {
            try {
                return policy->node_palette(node);
            } catch (const std::exception& error) {
                tc::Log::error(error, "[termin-nodegraph/ui] node presentation policy failed");
            } catch (...) {
                tc::Log::error("[termin-nodegraph/ui] node presentation policy failed: unknown exception");
            }
            return DefaultPresentationPolicy{}.node_palette(node);
        }

        ProjectionColor edge_color(const Edge& edge) const {
            if (graph == nullptr)
                return {0.68f, 0.68f, 0.70f, 1.0f};
            const std::optional<Node> node = graph->node(edge.source_node);
            if (!node)
                return {0.68f, 0.68f, 0.70f, 1.0f};
            const auto found = std::find_if(node->outputs.begin(), node->outputs.end(), [&](const Socket& socket) {
                return socket.name == edge.source_socket;
            });
            return found == node->outputs.end() ? ProjectionColor{0.68f, 0.68f, 0.70f, 1.0f}
                                                : socket_color(*node, *found, SocketDirection::Output);
        }

        bool edge_selected(EdgeHandle handle) const {
            return selected && selected->kind == SemanticKind::Edge && selected->edge == handle;
        }

        bool update_edge(const Edge& edge) {
            EdgeVisual* visual = find_edge_visual(edge.handle);
            const auto endpoints = edge_endpoints(edge);
            if (visual == nullptr || !endpoints)
                return false;
            const auto points = bezier_path_points(endpoints->first, endpoints->second);
            const ProjectionColor color =
                edge_selected(edge.handle) ? ProjectionColor{1.0f, 0.82f, 0.30f, 1.0f} : edge_color(edge);
            const auto paint = stroke(color, edge_selected(edge.handle) ? selected_edge_width : edge_width);
            if (!tc_visual_path_item2d_set(scene, visual->item, path_view(bezier_verbs(), points), nullptr, &paint)) {
                tc::Log::error("[termin-nodegraph/ui] failed to update edge visual");
                return false;
            }
            tc_visual_scene_item_set_z_order(scene, visual->item, edge_selected(edge.handle) ? -8 : -10);
            return true;
        }

        void refresh_edges(NodeHandle moved = {}) {
            if (graph == nullptr)
                return;
            for (const Edge& edge : graph->edges()) {
                if (moved.valid() && edge.source_node != moved && edge.destination_node != moved)
                    continue;
                update_edge(edge);
            }
        }

        bool update_pending_item() {
            if (!pending)
                return true;
            const auto start = socket_position(pending->start);
            if (!start)
                return false;
            const auto points = bezier_path_points(*start, {pending->world_x, pending->world_y});
            const auto paint = stroke({0.9f, 0.86f, 0.55f, 1.0f}, 2.0f);
            if (valid_item(pending->preview_item)) {
                return tc_visual_path_item2d_set(
                    scene, pending->preview_item, path_view(bezier_verbs(), points), nullptr, &paint);
            }
            pending->preview_item =
                tc_visual_path_item2d_create(scene, invalid_item(), path_view(bezier_verbs(), points), nullptr, &paint);
            if (!valid_item(pending->preview_item)) {
                tc::Log::error("[termin-nodegraph/ui] failed to create connection preview");
                return false;
            }
            tc_visual_scene_item_set_z_order(scene, pending->preview_item, -9);
            return true;
        }

        void clear_pending() {
            if (pending && valid_item(pending->preview_item))
                tc_visual_scene_destroy_item(scene, pending->preview_item);
            pending.reset();
        }

        void set_selection(std::optional<SemanticRef> next) {
            const std::optional<SemanticRef> previous = selected;
            if (previous == next)
                return;
            selected = std::move(next);
            if (previous && previous->kind == SemanticKind::Edge && graph != nullptr) {
                if (const auto edge = graph->edge(previous->edge))
                    update_edge(*edge);
            }
            if (selected && selected->kind == SemanticKind::Edge && graph != nullptr) {
                if (const auto edge = graph->edge(selected->edge))
                    update_edge(*edge);
            }
            notify_render();
        }

        bool start_drag(const SemanticRef& semantic, float world_x, float world_y) {
            DragState value;
            value.semantic = semantic;
            value.start_world_x = world_x;
            value.start_world_y = world_y;
            if (semantic.kind == SemanticKind::Node && graph != nullptr) {
                const auto node = graph->node(semantic.node);
                if (!node)
                    return false;
                value.start_x = node->x;
                value.start_y = node->y;
            } else if (semantic.kind == SemanticKind::Group && graph != nullptr) {
                const auto group = graph->group(semantic.group);
                if (!group)
                    return false;
                value.start_x = group->x;
                value.start_y = group->y;
            } else {
                return false;
            }
            drag = value;
            return true;
        }

        bool move_drag(float world_x, float world_y) {
            if (!drag || graph == nullptr)
                return false;
            const float x = drag->start_x + world_x - drag->start_world_x;
            const float y = drag->start_y + world_y - drag->start_world_y;
            if (drag->semantic.kind == SemanticKind::Node) {
                const auto result = graph->move_node(drag->semantic.node, x, y);
                if (!result) {
                    tc::Log::error("[termin-nodegraph/ui] node drag failed: %s", result.message.c_str());
                    return false;
                }
                NodeVisual* visual = find_node_visual(drag->semantic.node);
                if (visual == nullptr ||
                    !tc_visual_scene_item_set_transform(scene, visual->item, tc_affine2f_translation(x, y))) {
                    tc::Log::error("[termin-nodegraph/ui] failed to update dragged node visual");
                    return false;
                }
                refresh_edges(drag->semantic.node);
            } else if (drag->semantic.kind == SemanticKind::Group) {
                const auto result = graph->move_group(drag->semantic.group, x, y);
                if (!result) {
                    tc::Log::error("[termin-nodegraph/ui] group drag failed: %s", result.message.c_str());
                    return false;
                }
                GroupVisual* visual = find_group_visual(drag->semantic.group);
                if (visual == nullptr ||
                    !tc_visual_scene_item_set_transform(scene, visual->item, tc_affine2f_translation(x, y))) {
                    tc::Log::error("[termin-nodegraph/ui] failed to update dragged group visual");
                    return false;
                }
            } else {
                return false;
            }
            projected_revision = graph->revision();
            notify_graph_changed();
            notify_render();
            return true;
        }
    };

    bool SemanticRef::valid() const {
        switch (kind) {
        case SemanticKind::Node:
            return node.valid();
        case SemanticKind::Group:
            return group.valid();
        case SemanticKind::Edge:
            return edge.valid();
        case SemanticKind::Socket:
            return socket.valid();
        case SemanticKind::None:
            return false;
        }
        return false;
    }

    NodeGraphProjection::NodeGraphProjection(Graph* graph, std::shared_ptr<const PresentationPolicy> policy)
        : impl_(std::make_unique<Impl>(graph, std::move(policy))) {
        if (!impl_->is_closed)
            rebuild();
    }

    NodeGraphProjection::~NodeGraphProjection() = default;
    NodeGraphProjection::NodeGraphProjection(NodeGraphProjection&&) noexcept = default;
    NodeGraphProjection& NodeGraphProjection::operator=(NodeGraphProjection&&) noexcept = default;

    void NodeGraphProjection::close() noexcept {
        if (impl_)
            impl_->close();
    }

    bool NodeGraphProjection::closed() const {
        return !impl_ || impl_->is_closed;
    }

    tc_visual_scene_handle NodeGraphProjection::scene() const {
        return impl_ ? impl_->scene : tc_visual_scene_handle_invalid();
    }

    Graph* NodeGraphProjection::graph() const {
        return impl_ ? impl_->graph : nullptr;
    }

    std::uint64_t NodeGraphProjection::projected_revision() const {
        return impl_ ? impl_->projected_revision : 0;
    }

    bool NodeGraphProjection::set_graph(Graph* graph) {
        if (closed()) {
            tc::Log::error("[termin-nodegraph/ui] cannot replace graph on a closed projection");
            return false;
        }
        impl_->clear_pending();
        impl_->drag.reset();
        impl_->selected.reset();
        impl_->graph = graph;
        impl_->projected_revision = 0;
        return rebuild();
    }

    bool NodeGraphProjection::rebuild() {
        if (closed()) {
            tc::Log::error("[termin-nodegraph/ui] cannot rebuild a closed projection");
            return false;
        }

        impl_->clear_pending();
        impl_->drag.reset();
        impl_->selected.reset();
        tc_visual_scene_clear(impl_->scene);
        impl_->nodes.clear();
        impl_->groups.clear();
        impl_->edges.clear();

        const auto fail = [&](const char* message) {
            tc::Log::error("[termin-nodegraph/ui] rebuild failed: %s", message);
            tc_visual_scene_clear(impl_->scene);
            impl_->nodes.clear();
            impl_->groups.clear();
            impl_->edges.clear();
            impl_->projected_revision = 0;
            return false;
        };

        if (impl_->graph == nullptr) {
            impl_->projected_revision = 0;
            impl_->notify_render();
            return true;
        }

        for (const Group& group : impl_->graph->groups()) {
            const ProjectionColor body{0.16f, 0.20f, 0.30f, 0.20f};
            const ProjectionColor border{0.28f, 0.40f, 0.62f, 0.90f};
            const auto body_fill = fill(body);
            const auto body_stroke = stroke(border, 1.5f);
            const tc_graphic_item_handle item = tc_visual_rect_item2d_create(
                impl_->scene, invalid_item(), {0.0f, 0.0f, group.width, group.height}, body_fill, &body_stroke);
            if (!impl_->valid_item(item))
                return fail("cannot create group item");
            if (!tc_visual_scene_item_set_transform(impl_->scene, item, tc_affine2f_translation(group.x, group.y)))
                return fail("cannot position group item");
            tc_visual_scene_item_set_z_order(impl_->scene, item, -20);

            const tc_visual_text_desc2d label_desc{
                .text = group.title.c_str(),
                .font_uri = "ui://default-font",
                .origin = {8.0f, 18.0f},
                .size_px = 12.0f,
                .color = visual_color({0.92f, 0.94f, 0.98f, 1.0f}),
                .anchor = TC_VISUAL_TEXT_ANCHOR_LEFT,
                .layout_bounds = {8.0f, 4.0f, std::max(1.0f, group.width - 16.0f), 18.0f},
                .has_coverage_gamma = false,
                .coverage_gamma = 0.0f,
            };
            if (!impl_->valid_item(tc_visual_text_item2d_create(impl_->scene, item, &label_desc)))
                return fail("cannot create group label");
            impl_->groups.push_back({group.handle, item});
        }

        const std::vector<tc_visual_path_verb2d> diamond_verbs{
            TC_VISUAL_PATH_MOVE_TO,
            TC_VISUAL_PATH_LINE_TO,
            TC_VISUAL_PATH_LINE_TO,
            TC_VISUAL_PATH_LINE_TO,
            TC_VISUAL_PATH_CLOSE,
        };
        for (const Node& node : impl_->graph->nodes()) {
            const float required_height =
                title_height +
                socket_row_height * static_cast<float>(std::max(node.inputs.size(), node.outputs.size())) + 12.0f;
            const float height = std::max(node.height, required_height);
            const NodePalette palette = impl_->node_palette(node);
            const auto body_fill = fill(palette.body);
            const auto body_stroke = stroke(palette.border, 1.5f);
            const tc_graphic_item_handle item = tc_visual_rect_item2d_create(
                impl_->scene, invalid_item(), {0.0f, 0.0f, node.width, height}, body_fill, &body_stroke);
            if (!impl_->valid_item(item))
                return fail("cannot create node item");
            if (!tc_visual_scene_item_set_transform(impl_->scene, item, tc_affine2f_translation(node.x, node.y)))
                return fail("cannot position node item");

            const auto title_fill = fill(palette.title);
            if (!impl_->valid_item(tc_visual_rect_item2d_create(
                    impl_->scene, item, {0.0f, 0.0f, node.width, title_height}, title_fill, nullptr)))
                return fail("cannot create node title background");
            const tc_visual_text_desc2d title_desc{
                .text = node.title.c_str(),
                .font_uri = "ui://default-font",
                .origin = {8.0f, 18.0f},
                .size_px = 13.0f,
                .color = visual_color(palette.text),
                .anchor = TC_VISUAL_TEXT_ANCHOR_LEFT,
                .layout_bounds = {8.0f, 3.0f, std::max(1.0f, node.width - 16.0f), 20.0f},
                .has_coverage_gamma = false,
                .coverage_gamma = 0.0f,
            };
            if (!impl_->valid_item(tc_visual_text_item2d_create(impl_->scene, item, &title_desc)))
                return fail("cannot create node title");

            Impl::NodeVisual visual{node.handle, item, {}};
            const auto append_sockets = [&](const std::vector<Socket>& sockets, SocketDirection direction) {
                for (std::size_t index = 0; index < sockets.size(); ++index) {
                    const Socket& socket = sockets[index];
                    const float x = direction == SocketDirection::Output ? node.width : 0.0f;
                    const float y = title_height + socket_row_height * (static_cast<float>(index) + 0.5f);
                    const std::vector<tc_vec2f> diamond_points{
                        {x, y - 5.0f},
                        {x + 5.0f, y},
                        {x, y + 5.0f},
                        {x - 5.0f, y},
                    };
                    const auto marker_fill = fill(impl_->socket_color(node, socket, direction));
                    const tc_graphic_item_handle marker = tc_visual_path_item2d_create(
                        impl_->scene, item, path_view(diamond_verbs, diamond_points), &marker_fill, nullptr);
                    if (!impl_->valid_item(marker))
                        return false;
                    const bool output = direction == SocketDirection::Output;
                    const float label_x = output ? node.width - 8.0f : 8.0f;
                    const tc_visual_text_desc2d socket_desc{
                        .text = socket.name.c_str(),
                        .font_uri = "ui://default-font",
                        .origin = {label_x, y + 4.0f},
                        .size_px = 11.0f,
                        .color = visual_color(palette.text),
                        .anchor = output ? TC_VISUAL_TEXT_ANCHOR_RIGHT : TC_VISUAL_TEXT_ANCHOR_LEFT,
                        .layout_bounds = output ? tc_bounds2f{node.width * 0.52f, y - 8.0f, node.width - 8.0f, y + 8.0f}
                                                : tc_bounds2f{8.0f, y - 8.0f, node.width * 0.48f, y + 8.0f},
                        .has_coverage_gamma = false,
                        .coverage_gamma = 0.0f,
                    };
                    if (!impl_->valid_item(tc_visual_text_item2d_create(impl_->scene, item, &socket_desc)))
                        return false;
                    visual.sockets.push_back({SocketRef{node.handle, socket.name, direction}, marker});
                }
                return true;
            };
            if (!append_sockets(node.inputs, SocketDirection::Input) ||
                !append_sockets(node.outputs, SocketDirection::Output))
                return fail("cannot create node socket visuals");
            impl_->nodes.push_back(std::move(visual));
        }

        for (const Edge& edge : impl_->graph->edges()) {
            const auto endpoints = impl_->edge_endpoints(edge);
            if (!endpoints)
                return fail("edge endpoint is missing");
            const auto points = bezier_path_points(endpoints->first, endpoints->second);
            const auto edge_stroke = stroke(impl_->edge_color(edge), edge_width);
            const tc_graphic_item_handle item = tc_visual_path_item2d_create(
                impl_->scene, invalid_item(), path_view(bezier_verbs(), points), nullptr, &edge_stroke);
            if (!impl_->valid_item(item))
                return fail("cannot create edge item");
            tc_visual_scene_item_set_z_order(impl_->scene, item, -10);
            impl_->edges.push_back({edge.handle, item});
        }

        impl_->projected_revision = impl_->graph->revision();
        impl_->notify_render();
        return true;
    }

    bool NodeGraphProjection::sync() {
        if (closed()) {
            tc::Log::error("[termin-nodegraph/ui] cannot synchronize a closed projection");
            return false;
        }
        const std::uint64_t revision = impl_->graph ? impl_->graph->revision() : 0;
        return revision == impl_->projected_revision ? false : rebuild();
    }

    std::optional<SemanticHit> NodeGraphProjection::hit_test(float world_x, float world_y, float zoom) const {
        if (closed() || impl_->graph == nullptr || !finite_point(world_x, world_y) || !std::isfinite(zoom) ||
            zoom <= 0.0f) {
            return std::nullopt;
        }

        const float socket_radius_sq = socket_hit_radius * socket_hit_radius;
        for (auto node_it = impl_->nodes.rbegin(); node_it != impl_->nodes.rend(); ++node_it) {
            for (auto socket_it = node_it->sockets.rbegin(); socket_it != node_it->sockets.rend(); ++socket_it) {
                const auto position = impl_->socket_position(socket_it->socket);
                if (!position)
                    continue;
                const float dx = world_x - position->x;
                const float dy = world_y - position->y;
                if (dx * dx + dy * dy <= socket_radius_sq)
                    return SemanticHit{socket_semantic(socket_it->socket), socket_it->item};
            }
        }

        for (auto visual = impl_->nodes.rbegin(); visual != impl_->nodes.rend(); ++visual) {
            const auto node = impl_->graph->node(visual->node);
            if (node && world_x >= node->x && world_y >= node->y && world_x <= node->x + node->width &&
                world_y <= node->y + std::max(node->height,
                                              title_height +
                                                  socket_row_height * static_cast<float>(std::max(
                                                                          node->inputs.size(), node->outputs.size())) +
                                                  12.0f)) {
                return SemanticHit{node_semantic(node->handle), visual->item};
            }
        }

        const float edge_tolerance_sq = (edge_hit_radius_px / zoom) * (edge_hit_radius_px / zoom);
        for (auto visual = impl_->edges.rbegin(); visual != impl_->edges.rend(); ++visual) {
            const auto edge = impl_->graph->edge(visual->edge);
            if (!edge)
                continue;
            const auto endpoints = impl_->edge_endpoints(*edge);
            if (!endpoints)
                continue;
            const auto samples = bezier_samples(endpoints->first, endpoints->second);
            for (std::size_t index = 1; index < samples.size(); ++index) {
                if (point_segment_distance_sq(world_x, world_y, samples[index - 1], samples[index]) <=
                    edge_tolerance_sq) {
                    return SemanticHit{edge_semantic(edge->handle), visual->item};
                }
            }
        }

        for (auto visual = impl_->groups.rbegin(); visual != impl_->groups.rend(); ++visual) {
            const auto group = impl_->graph->group(visual->group);
            if (group && world_x >= group->x && world_y >= group->y && world_x <= group->x + group->width &&
                world_y <= group->y + group->height) {
                return SemanticHit{group_semantic(group->handle), visual->item};
            }
        }
        return std::nullopt;
    }

    bool NodeGraphProjection::pointer(const PointerInput& input) {
        if (closed()) {
            tc::Log::error("[termin-nodegraph/ui] cannot dispatch pointer input to a closed projection");
            return false;
        }
        if (input.phase == PointerPhase::Cancel) {
            const bool handled = impl_->pending.has_value() || impl_->drag.has_value();
            cancel();
            return handled;
        }
        if (!finite_point(input.world_x, input.world_y) || !std::isfinite(input.zoom) || input.zoom <= 0.0f) {
            tc::Log::error("[termin-nodegraph/ui] rejected non-finite pointer input or non-positive zoom");
            return false;
        }
        const std::uint64_t graph_revision = impl_->graph ? impl_->graph->revision() : 0;
        if (graph_revision != impl_->projected_revision && !rebuild())
            return false;

        if (input.phase == PointerPhase::Down && input.button == PointerButton::Right) {
            if (!impl_->context_requested)
                return false;
            const auto hit = hit_test(input.world_x, input.world_y, input.zoom);
            try {
                impl_->context_requested(input.world_x, input.world_y, hit);
            } catch (const std::exception& error) {
                tc::Log::error(error, "[termin-nodegraph/ui] context callback failed");
            } catch (...) {
                tc::Log::error("[termin-nodegraph/ui] context callback failed: unknown exception");
            }
            return true;
        }

        if (input.phase == PointerPhase::Down && input.button == PointerButton::Left) {
            const auto hit = hit_test(input.world_x, input.world_y, input.zoom);
            impl_->drag.reset();
            if (hit && hit->semantic.kind == SemanticKind::Socket) {
                impl_->clear_pending();
                impl_->pending = PendingConnection{
                    hit->semantic.socket,
                    input.world_x,
                    input.world_y,
                    invalid_item(),
                };
                if (!impl_->update_pending_item()) {
                    impl_->clear_pending();
                    return false;
                }
                impl_->notify_render();
                return true;
            }
            impl_->clear_pending();
            impl_->set_selection(hit ? std::optional(hit->semantic) : std::nullopt);
            if (hit && (hit->semantic.kind == SemanticKind::Node || hit->semantic.kind == SemanticKind::Group))
                impl_->start_drag(hit->semantic, input.world_x, input.world_y);
            return hit.has_value();
        }

        if (input.phase == PointerPhase::Move && impl_->pending) {
            impl_->pending->world_x = input.world_x;
            impl_->pending->world_y = input.world_y;
            if (!impl_->update_pending_item()) {
                tc::Log::error("[termin-nodegraph/ui] failed to update connection preview");
                impl_->clear_pending();
                return false;
            }
            impl_->notify_render();
            return true;
        }

        if (input.phase == PointerPhase::Move && impl_->drag)
            return impl_->move_drag(input.world_x, input.world_y);

        if (input.phase == PointerPhase::Up && input.button == PointerButton::Left && impl_->pending) {
            const SocketRef start = impl_->pending->start;
            const auto hit = hit_test(input.world_x, input.world_y, input.zoom);
            impl_->clear_pending();
            impl_->notify_render();
            if (!hit || hit->semantic.kind != SemanticKind::Socket)
                return true;
            const SocketRef target = hit->semantic.socket;
            if (start.node == target.node || start.direction == target.direction)
                return true;
            const SocketRef& source = start.direction == SocketDirection::Output ? start : target;
            const SocketRef& destination = start.direction == SocketDirection::Input ? start : target;
            const auto result = impl_->graph->connect({
                source.node,
                source.name,
                destination.node,
                destination.name,
                {},
            });
            if (!result) {
                tc::Log::error("[termin-nodegraph/ui] socket connection failed: %s", result.message.c_str());
                return true;
            }
            impl_->notify_graph_changed();
            return rebuild();
        }

        if (input.phase == PointerPhase::Up && input.button == PointerButton::Left && impl_->drag) {
            impl_->drag.reset();
            return true;
        }
        return false;
    }

    bool NodeGraphProjection::delete_selection() {
        if (closed() || impl_->graph == nullptr || !impl_->selected)
            return false;
        const SemanticRef selected = *impl_->selected;
        Result<void> result;
        switch (selected.kind) {
        case SemanticKind::Node:
            result = impl_->graph->remove_node(selected.node);
            break;
        case SemanticKind::Group:
            result = impl_->graph->remove_group(selected.group);
            break;
        case SemanticKind::Edge:
            result = impl_->graph->remove_edge(selected.edge);
            break;
        case SemanticKind::Socket:
        case SemanticKind::None:
            return false;
        }
        if (!result) {
            tc::Log::error("[termin-nodegraph/ui] delete selection failed: %s", result.message.c_str());
            return false;
        }
        impl_->notify_graph_changed();
        return rebuild();
    }

    void NodeGraphProjection::cancel() {
        if (closed())
            return;
        const bool had_state = impl_->pending.has_value() || impl_->drag.has_value();
        impl_->clear_pending();
        impl_->drag.reset();
        if (had_state)
            impl_->notify_render();
    }

    std::optional<SemanticRef> NodeGraphProjection::selection() const {
        return impl_ ? impl_->selected : std::nullopt;
    }

    std::optional<PendingConnection> NodeGraphProjection::pending_connection() const {
        return impl_ ? impl_->pending : std::nullopt;
    }

    tc_graphic_item_handle NodeGraphProjection::node_item(NodeHandle node) const {
        if (!impl_)
            return invalid_item();
        const Impl::NodeVisual* visual = impl_->find_node_visual(node);
        return visual ? visual->item : invalid_item();
    }

    tc_graphic_item_handle NodeGraphProjection::group_item(GroupHandle group) const {
        if (!impl_)
            return invalid_item();
        const Impl::GroupVisual* visual = impl_->find_group_visual(group);
        return visual ? visual->item : invalid_item();
    }

    tc_graphic_item_handle NodeGraphProjection::edge_item(EdgeHandle edge) const {
        if (!impl_)
            return invalid_item();
        const Impl::EdgeVisual* visual = impl_->find_edge_visual(edge);
        return visual ? visual->item : invalid_item();
    }

    tc_graphic_item_handle NodeGraphProjection::socket_item(const SocketRef& socket) const {
        if (!impl_)
            return invalid_item();
        const Impl::SocketVisual* visual = impl_->find_socket_visual(socket);
        return visual ? visual->item : invalid_item();
    }

    void NodeGraphProjection::set_request_render_callback(RequestRenderCallback callback) {
        if (impl_)
            impl_->request_render = std::move(callback);
    }

    void NodeGraphProjection::set_graph_changed_callback(GraphChangedCallback callback) {
        if (impl_)
            impl_->graph_changed = std::move(callback);
    }

    void NodeGraphProjection::set_context_requested_callback(ContextRequestedCallback callback) {
        if (impl_)
            impl_->context_requested = std::move(callback);
    }

} // namespace termin::nodegraph
