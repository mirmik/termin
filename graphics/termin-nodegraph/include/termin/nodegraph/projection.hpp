#pragma once

#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>

#include <termin/nodegraph/graph.hpp>
#include <termin_visual_scene/tc_graphic_item.h>
#include <termin_visual_scene/tc_visual_scene.h>

namespace termin::nodegraph {

    enum class SocketDirection {
        Input,
        Output,
    };

    struct SocketRef {
        NodeHandle node;
        std::string name;
        SocketDirection direction = SocketDirection::Input;

        bool valid() const {
            return node.valid() && !name.empty();
        }

        auto operator<=>(const SocketRef&) const = default;
    };

    enum class SemanticKind {
        None,
        Node,
        Group,
        Edge,
        Socket,
    };

    struct SemanticRef {
        SemanticKind kind = SemanticKind::None;
        NodeHandle node;
        GroupHandle group;
        EdgeHandle edge;
        SocketRef socket;

        bool valid() const;
        auto operator<=>(const SemanticRef&) const = default;
    };

    struct SemanticHit {
        SemanticRef semantic;
        tc_graphic_item_handle item = tc_graphic_item_handle_invalid();
    };

    struct ProjectionColor {
        float r = 0.0f;
        float g = 0.0f;
        float b = 0.0f;
        float a = 1.0f;
    };

    struct NodePalette {
        ProjectionColor body;
        ProjectionColor title;
        ProjectionColor border;
        ProjectionColor text;
    };

    class TERMIN_NODEGRAPH_UI_API PresentationPolicy {
    public:
        virtual ~PresentationPolicy() = default;
        virtual NodePalette node_palette(const Node& node) const = 0;
        virtual ProjectionColor
        socket_color(const Node& node, const Socket& socket, SocketDirection direction) const = 0;
    };

    class TERMIN_NODEGRAPH_UI_API DefaultPresentationPolicy final : public PresentationPolicy {
    public:
        NodePalette node_palette(const Node& node) const override;
        ProjectionColor socket_color(const Node& node, const Socket& socket, SocketDirection direction) const override;
    };

    enum class PointerPhase {
        Down,
        Move,
        Up,
        Cancel,
    };

    enum class PointerButton {
        None,
        Left,
        Right,
        Middle,
    };

    struct PointerInput {
        PointerPhase phase = PointerPhase::Move;
        PointerButton button = PointerButton::None;
        float world_x = 0.0f;
        float world_y = 0.0f;
        // World-to-screen scale. Edge hit tolerance is divided by this value.
        float zoom = 1.0f;
    };

    struct PendingConnection {
        SocketRef start;
        float world_x = 0.0f;
        float world_y = 0.0f;
        tc_graphic_item_handle preview_item = tc_graphic_item_handle_invalid();
    };

    class TERMIN_NODEGRAPH_UI_API NodeGraphProjection final {
    public:
        using RequestRenderCallback = std::function<void()>;
        using GraphChangedCallback = std::function<void(std::uint64_t revision)>;
        using ContextRequestedCallback =
            std::function<void(float world_x, float world_y, std::optional<SemanticHit> hit)>;

        explicit NodeGraphProjection(Graph* graph = nullptr, std::shared_ptr<const PresentationPolicy> policy = {});
        ~NodeGraphProjection();

        NodeGraphProjection(const NodeGraphProjection&) = delete;
        NodeGraphProjection& operator=(const NodeGraphProjection&) = delete;
        NodeGraphProjection(NodeGraphProjection&&) noexcept;
        NodeGraphProjection& operator=(NodeGraphProjection&&) noexcept;

        void close() noexcept;
        bool closed() const;

        tc_visual_scene_handle scene() const;
        Graph* graph() const;
        std::uint64_t projected_revision() const;

        bool set_graph(Graph* graph);
        bool rebuild();
        bool sync();

        std::optional<SemanticHit> hit_test(float world_x, float world_y, float zoom = 1.0f) const;
        bool pointer(const PointerInput& input);
        bool delete_selection();
        void cancel();

        std::optional<SemanticRef> selection() const;
        std::optional<PendingConnection> pending_connection() const;

        tc_graphic_item_handle node_item(NodeHandle node) const;
        tc_graphic_item_handle group_item(GroupHandle group) const;
        tc_graphic_item_handle edge_item(EdgeHandle edge) const;
        tc_graphic_item_handle socket_item(const SocketRef& socket) const;

        void set_request_render_callback(RequestRenderCallback callback);
        void set_graph_changed_callback(GraphChangedCallback callback);
        void set_context_requested_callback(ContextRequestedCallback callback);

    private:
        struct Impl;
        std::unique_ptr<Impl> impl_;
    };

} // namespace termin::nodegraph
