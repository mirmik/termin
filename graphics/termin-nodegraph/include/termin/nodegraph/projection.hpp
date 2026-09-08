#pragma once

#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include <termin/gui_native/tc_ui_document.h>
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

    enum class ParameterEditorKind {
        Automatic,
        Boolean,
        Enumeration,
        Integer,
        FloatingPoint,
        Text,
    };

    struct ParameterChoice {
        std::string value;
        std::string label;
    };

    struct ParameterEditorDescriptor {
        std::string name;
        std::string label;
        ParameterEditorKind kind = ParameterEditorKind::Automatic;
        double minimum = -1.0e9;
        double maximum = 1.0e9;
        double step = 0.1;
        int decimals = 3;
        std::vector<ParameterChoice> choices;
        std::optional<tc_ui_style_override> style;
    };

    struct NodeBodyLayout {
        float height = 0.0f;
        float inset_left = 8.0f;
        float inset_right = 8.0f;
        float inset_top = 8.0f;
        float inset_bottom = 8.0f;
        float gap_before = 7.0f;
    };

    class TERMIN_NODEGRAPH_UI_API PresentationPolicy {
    public:
        virtual ~PresentationPolicy() = default;
        virtual NodePalette node_palette(const Node& node) const = 0;
        virtual ProjectionColor
        socket_color(const Node& node, const Socket& socket, SocketDirection direction) const = 0;
        // The default implementation infers editor kinds from node.params and
        // honors the generic node.data["param_specs"] migration schema.
        virtual std::vector<ParameterEditorDescriptor> parameter_editors(const Node& node) const;
    };

    class TERMIN_NODEGRAPH_UI_API DefaultPresentationPolicy : public PresentationPolicy {
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
        using BodyLayoutProvider = std::function<std::optional<NodeBodyLayout>(const Node& node)>;

        explicit NodeGraphProjection(Graph* graph = nullptr,
                                     std::shared_ptr<const PresentationPolicy> policy = {},
                                     bool defer_rebuild = false);
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
        // Accept a revision produced by a value-only mutation that cannot
        // affect projected geometry. Structural callers must use rebuild().
        bool acknowledge_graph_revision();

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
        tc_graphic_item_handle parameter_item(NodeHandle node, const std::string& name) const;
        tc_graphic_item_handle body_item(NodeHandle node) const;
        float node_visual_height(NodeHandle node) const;
        std::vector<ParameterEditorDescriptor> parameter_editors(NodeHandle node) const;

        void set_request_render_callback(RequestRenderCallback callback);
        void set_graph_changed_callback(GraphChangedCallback callback);
        void set_context_requested_callback(ContextRequestedCallback callback);
        void set_body_layout_provider(BodyLayoutProvider provider);

    private:
        struct Impl;
        std::unique_ptr<Impl> impl_;
    };

} // namespace termin::nodegraph
