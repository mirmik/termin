#pragma once

#include <functional>
#include <memory>
#include <optional>
#include <string>

#include <termin/gui_native/tc_document.hpp>
#include <termin/nodegraph/projection.hpp>

namespace termin::gui_native {
    class SceneView;
}

namespace termin::nodegraph {

    struct NodeBodyContent {
        tc_widget_handle widget = tc_widget_handle_invalid();
        NodeBodyLayout layout;
        std::function<void(const Node& node)> update;
    };

    class TERMIN_NODEGRAPH_UI_API NodeGraphView final {
    public:
        using RequestRenderCallback = std::function<void()>;
        using GraphChangedCallback = std::function<void(std::uint64_t revision)>;
        using ParameterChangedCallback =
            std::function<void(const Node& node, const std::string& name, tc::trent_view value)>;
        using ContextRequestedCallback = NodeGraphProjection::ContextRequestedCallback;
        using BodyContentProvider =
            std::function<std::optional<NodeBodyContent>(gui_native::TcDocument document, const Node& node)>;

        NodeGraphView(gui_native::TcDocument document,
                      Graph* graph,
                      std::shared_ptr<const PresentationPolicy> presentation = {},
                      BodyContentProvider body_content_provider = {});
        ~NodeGraphView();

        NodeGraphView(const NodeGraphView&) = delete;
        NodeGraphView& operator=(const NodeGraphView&) = delete;
        NodeGraphView(NodeGraphView&&) noexcept;
        NodeGraphView& operator=(NodeGraphView&&) noexcept;

        void close() noexcept;
        bool closed() const;

        gui_native::TcDocument document() const;
        Graph* graph() const;
        tc_widget_handle root_widget() const;
        gui_native::SceneView* scene_view() const;
        NodeGraphProjection* projection() const;

        bool set_graph(Graph* graph);
        bool rebuild();
        bool sync();

        tc_widget_handle parameter_widget(NodeHandle node, const std::string& name) const;
        tc_widget_handle body_widget(NodeHandle node) const;

        void set_request_render_callback(RequestRenderCallback callback);
        void set_graph_changed_callback(GraphChangedCallback callback);
        void set_parameter_changed_callback(ParameterChangedCallback callback);
        void set_context_requested_callback(ContextRequestedCallback callback);

    private:
        struct Impl;
        std::unique_ptr<Impl> impl_;
    };

} // namespace termin::nodegraph
