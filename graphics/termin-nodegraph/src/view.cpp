#include <termin/nodegraph/view.hpp>

#include <algorithm>
#include <cmath>
#include <exception>
#include <map>
#include <set>
#include <stdexcept>
#include <utility>
#include <vector>

#include <tcbase/input_enums.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/gui_native/checkbox.hpp>
#include <termin/gui_native/combo_box.hpp>
#include <termin/gui_native/document_builder.hpp>
#include <termin/gui_native/scene_view.hpp>
#include <termin/gui_native/spin_box.hpp>
#include <termin/gui_native/text_input.hpp>

namespace termin::nodegraph {
    namespace {

        bool valid_layout(const NodeBodyLayout& layout, float node_width) {
            return std::isfinite(layout.height) && layout.height > 0.0f && std::isfinite(layout.inset_left) &&
                   layout.inset_left >= 0.0f && std::isfinite(layout.inset_right) && layout.inset_right >= 0.0f &&
                   std::isfinite(layout.inset_top) && layout.inset_top >= 0.0f && std::isfinite(layout.inset_bottom) &&
                   layout.inset_bottom >= 0.0f && std::isfinite(layout.gap_before) && layout.gap_before >= 0.0f &&
                   layout.inset_left + layout.inset_right < node_width;
        }

        ParameterEditorKind resolved_kind(ParameterEditorKind kind, tc::trent_view value) {
            if (kind != ParameterEditorKind::Automatic)
                return kind;
            if (value.is_bool())
                return ParameterEditorKind::Boolean;
            if (value.is_integer())
                return ParameterEditorKind::Integer;
            if (value.is_numer())
                return ParameterEditorKind::FloatingPoint;
            return ParameterEditorKind::Text;
        }

        std::string text_value(tc::trent_view value) {
            if (value.is_string())
                return value.as_string();
            if (value.is_bool())
                return value.as_bool() ? "true" : "false";
            if (value.is_integer())
                return std::to_string(value.as_integer());
            if (value.is_numer())
                return std::to_string(value.as_numer());
            return {};
        }

        PointerPhase pointer_phase(tc_ui_pointer_event_type type) {
            switch (type) {
            case TC_UI_POINTER_DOWN:
                return PointerPhase::Down;
            case TC_UI_POINTER_UP:
                return PointerPhase::Up;
            case TC_UI_POINTER_CANCEL:
                return PointerPhase::Cancel;
            case TC_UI_POINTER_MOVE:
            case TC_UI_POINTER_WHEEL:
            case TC_UI_POINTER_ENTER:
            case TC_UI_POINTER_LEAVE:
                return PointerPhase::Move;
            }
            return PointerPhase::Move;
        }

        PointerButton pointer_button(int button) {
            if (button == tcbase::mouse_button_value(tcbase::MouseButton::LEFT))
                return PointerButton::Left;
            if (button == tcbase::mouse_button_value(tcbase::MouseButton::RIGHT))
                return PointerButton::Right;
            if (button == tcbase::mouse_button_value(tcbase::MouseButton::MIDDLE))
                return PointerButton::Middle;
            return PointerButton::None;
        }

    } // namespace

    struct NodeGraphView::Impl {
        struct ParameterWidget {
            NodeHandle node;
            std::string node_id;
            std::string name;
            tc_widget_handle widget = tc_widget_handle_invalid();
        };

        struct BodyWidget {
            NodeHandle node;
            std::string node_id;
            NodeBodyContent content;
        };

        gui_native::TcDocument document;
        std::shared_ptr<const PresentationPolicy> presentation;
        BodyContentProvider body_content_provider;
        NodeGraphProjection projection;
        gui_native::SceneView* view = nullptr;
        std::vector<ParameterWidget> parameter_widgets;
        std::map<std::string, BodyWidget> body_widgets;
        RequestRenderCallback request_render_callback;
        GraphChangedCallback graph_changed_callback;
        ParameterChangedCallback parameter_changed_callback;
        ContextRequestedCallback context_requested_callback;
        bool is_closed = false;

        Impl(gui_native::TcDocument owner_document,
             Graph* graph,
             std::shared_ptr<const PresentationPolicy> owner_presentation,
             BodyContentProvider provider)
            : document(owner_document),
              presentation(std::move(owner_presentation)),
              body_content_provider(std::move(provider)),
              projection(graph, presentation, true) {
            if (!presentation)
                presentation = std::make_shared<DefaultPresentationPolicy>();
        }

        ~Impl() {
            close();
        }

        bool open() const {
            return !is_closed && document.valid() && view != nullptr && !projection.closed();
        }

        void initialize() {
            if (!document.valid() || projection.graph() == nullptr)
                throw std::invalid_argument("NodeGraphView requires a valid document and graph");
            try {
                gui_native::DocumentBuilder builder(document);
                view = &builder.make<gui_native::SceneView>(termin::visual::TcVisualScene{projection.scene()});
                view->set_stable_id("nodegraph.native-view");
                view->set_preferred_size({900.0f, 650.0f});
                view->set_scene_colors(
                    {0.09f, 0.10f, 0.12f, 1.0f}, {0.15f, 0.16f, 0.20f, 1.0f}, {0.24f, 0.27f, 0.34f, 1.0f});
                view->set_offset({500.0f, 320.0f});
                projection.set_body_layout_provider([this](const Node& node) -> std::optional<NodeBodyLayout> {
                    const auto found = body_widgets.find(node.id);
                    return found == body_widgets.end() ? std::nullopt : std::optional(found->second.content.layout);
                });
                projection.set_request_render_callback([this] { request_render(); });
                projection.set_graph_changed_callback(
                    [this](std::uint64_t revision) { notify_graph_changed(revision); });
                projection.set_context_requested_callback([this](float x, float y, std::optional<SemanticHit> hit) {
                    if (context_requested_callback)
                        context_requested_callback(x, y, std::move(hit));
                });
                view->set_pointer_handler([this](gui_native::SceneView&,
                                                 tc_ui_point world,
                                                 const tc_ui_pointer_event& event) { return pointer(world, event); });
                view->set_key_handler(
                    [this](gui_native::SceneView&, const tc_ui_key_event& event) { return key(event); });
                if (!rebuild())
                    throw std::runtime_error("failed to build native nodegraph view");
            } catch (...) {
                close();
                throw;
            }
        }

        void request_render() const noexcept {
            if (view)
                view->invalidate_scene();
            if (!request_render_callback)
                return;
            try {
                request_render_callback();
            } catch (const std::exception& error) {
                tc::Log::error(error, "[termin-nodegraph/view] request-render callback failed");
            } catch (...) {
                tc::Log::error("[termin-nodegraph/view] request-render callback failed: unknown exception");
            }
        }

        void notify_graph_changed(std::uint64_t revision) const noexcept {
            if (!graph_changed_callback)
                return;
            try {
                graph_changed_callback(revision);
            } catch (const std::exception& error) {
                tc::Log::error(error, "[termin-nodegraph/view] graph-changed callback failed");
            } catch (...) {
                tc::Log::error("[termin-nodegraph/view] graph-changed callback failed: unknown exception");
            }
        }

        void notify_parameter_changed(const Node& node, const std::string& name, tc::trent_view value) const noexcept {
            if (!parameter_changed_callback)
                return;
            try {
                parameter_changed_callback(node, name, value);
            } catch (const std::exception& error) {
                tc::Log::error(error, "[termin-nodegraph/view] parameter-changed callback failed");
            } catch (...) {
                tc::Log::error("[termin-nodegraph/view] parameter-changed callback failed: unknown exception");
            }
        }

        void clear_portals() {
            if (view)
                view->clear_widget_portals();
        }

        void destroy_parameter_widgets() {
            for (const ParameterWidget& entry : parameter_widgets) {
                if (document.valid() && tc_ui_document_is_alive(document.handle(), entry.widget) &&
                    !tc_ui_document_destroy_widget_recursive(document.handle(), entry.widget)) {
                    tc::Log::error("[termin-nodegraph/view] failed to destroy parameter widget '%s.%s'",
                                   entry.node_id.c_str(),
                                   entry.name.c_str());
                }
            }
            parameter_widgets.clear();
        }

        void destroy_body_widget(BodyWidget& entry) {
            const tc_widget_handle widget = entry.content.widget;
            if (document.valid() && tc_ui_document_is_alive(document.handle(), widget) &&
                !tc_ui_document_destroy_widget_recursive(document.handle(), widget)) {
                tc::Log::error("[termin-nodegraph/view] failed to destroy body widget for '%s'", entry.node_id.c_str());
            }
        }

        void destroy_body_widgets() {
            for (auto& [id, entry] : body_widgets) {
                (void)id;
                destroy_body_widget(entry);
            }
            body_widgets.clear();
        }

        bool validate_body(const Node& node, const NodeBodyContent& content) const {
            if (tc_widget_handle_is_invalid(content.widget) || !valid_layout(content.layout, node.width) ||
                !document.valid() || !tc_ui_document_is_alive(document.handle(), content.widget)) {
                tc::Log::error("[termin-nodegraph/view] body provider returned invalid content for '%s'",
                               node.id.c_str());
                return false;
            }
            const tc_widget* widget = tc_ui_document_resolve_widget_const(document.handle(), content.widget);
            if (widget == nullptr || !tc_ui_document_handle_eq(widget->document, document.handle()) ||
                widget->parent != nullptr) {
                tc::Log::error("[termin-nodegraph/view] body widget for '%s' must be parentless in the owning document",
                               node.id.c_str());
                return false;
            }
            return true;
        }

        bool prepare_body_widgets() {
            Graph* graph = projection.graph();
            if (graph == nullptr)
                return false;
            std::set<std::string> live_ids;
            std::set<std::pair<std::uint32_t, std::uint32_t>> claimed;
            for (const Node& node : graph->nodes()) {
                live_ids.insert(node.id);
                auto found = body_widgets.find(node.id);
                if (found != body_widgets.end()) {
                    if (!validate_body(node, found->second.content))
                        return false;
                    found->second.node = node.handle;
                    claimed.insert({found->second.content.widget.index, found->second.content.widget.generation});
                    if (found->second.content.update) {
                        try {
                            found->second.content.update(node);
                        } catch (const std::exception& error) {
                            tc::Log::error(
                                error, "[termin-nodegraph/view] body update failed for '%s'", node.id.c_str());
                            return false;
                        } catch (...) {
                            tc::Log::error("[termin-nodegraph/view] body update failed for '%s': unknown exception",
                                           node.id.c_str());
                            return false;
                        }
                    }
                    continue;
                }
                if (!body_content_provider)
                    continue;
                std::optional<NodeBodyContent> content;
                try {
                    content = body_content_provider(document, node);
                } catch (const std::exception& error) {
                    tc::Log::error(error, "[termin-nodegraph/view] body provider failed for '%s'", node.id.c_str());
                    return false;
                } catch (...) {
                    tc::Log::error("[termin-nodegraph/view] body provider failed for '%s': unknown exception",
                                   node.id.c_str());
                    return false;
                }
                if (!content)
                    continue;
                if (!validate_body(node, *content)) {
                    if (document.valid() && tc_ui_document_is_alive(document.handle(), content->widget))
                        tc_ui_document_destroy_widget_recursive(document.handle(), content->widget);
                    return false;
                }
                const auto widget_key = std::pair{content->widget.index, content->widget.generation};
                if (!claimed.insert(widget_key).second) {
                    tc::Log::error("[termin-nodegraph/view] body provider reused a widget for '%s'", node.id.c_str());
                    return false;
                }
                body_widgets.emplace(node.id, BodyWidget{node.handle, node.id, std::move(*content)});
            }
            for (auto iterator = body_widgets.begin(); iterator != body_widgets.end();) {
                if (live_ids.contains(iterator->first)) {
                    ++iterator;
                    continue;
                }
                destroy_body_widget(iterator->second);
                iterator = body_widgets.erase(iterator);
            }
            return true;
        }

        gui_native::Widget*
        create_parameter_widget(const Node& node, const ParameterEditorDescriptor& descriptor, tc::trent_view value) {
            gui_native::DocumentBuilder builder(document);
            gui_native::Widget* widget = nullptr;
            const ParameterEditorKind kind = resolved_kind(descriptor.kind, value);
            if (kind == ParameterEditorKind::Boolean) {
                auto& control = builder.make<gui_native::Checkbox>(value.as_bool());
                control.changed().connect(
                    [this, node_handle = node.handle, name = descriptor.name](gui_native::Checkbox&, bool checked) {
                        set_parameter(node_handle, name, tc::trent(checked));
                    });
                widget = &control;
            } else if (kind == ParameterEditorKind::Enumeration) {
                auto& control = builder.make<gui_native::ComboBox>();
                std::vector<std::string> values;
                int selected = -1;
                const std::string current = value.as_string();
                for (const ParameterChoice& choice : descriptor.choices) {
                    values.push_back(choice.value);
                    control.add_item(choice.label);
                    if (choice.value == current)
                        selected = static_cast<int>(values.size()) - 1;
                }
                if (selected < 0 && !current.empty()) {
                    values.push_back(current);
                    control.add_item(current);
                    selected = static_cast<int>(values.size()) - 1;
                }
                control.set_selected_index(selected);
                control.changed().connect(
                    [this, node_handle = node.handle, name = descriptor.name, values = std::move(values)](
                        gui_native::ComboBox&, int index, const std::string& text) {
                        const std::string next = index >= 0 && index < static_cast<int>(values.size())
                                                     ? values[static_cast<std::size_t>(index)]
                                                     : text;
                        set_parameter(node_handle, name, tc::trent(next));
                    });
                widget = &control;
            } else if (kind == ParameterEditorKind::Integer || kind == ParameterEditorKind::FloatingPoint) {
                auto& control = builder.make<gui_native::SpinBox>(static_cast<float>(value.as_numer()));
                control.set_range(static_cast<float>(descriptor.minimum), static_cast<float>(descriptor.maximum));
                control.set_step(static_cast<float>(descriptor.step));
                control.set_decimals(kind == ParameterEditorKind::Integer ? 0 : descriptor.decimals);
                control.changed().connect([this, node_handle = node.handle, name = descriptor.name, kind](
                                              gui_native::SpinBox&, float number) {
                    if (kind == ParameterEditorKind::Integer)
                        set_parameter(node_handle, name, tc::trent(static_cast<std::int64_t>(std::llround(number))));
                    else
                        set_parameter(node_handle, name, tc::trent(static_cast<double>(number)));
                });
                widget = &control;
            } else {
                auto& control = builder.make<gui_native::TextInput>(text_value(value));
                control.submitted().connect([this, node_handle = node.handle, name = descriptor.name](
                                                gui_native::TextInput&, const std::string& text) {
                    set_parameter(node_handle, name, tc::trent(text));
                });
                widget = &control;
            }
            widget->set_stable_id("nodegraph.param." + node.id + "." + descriptor.name);
            if (descriptor.style && !widget->set_style_override(*descriptor.style)) {
                tc::Log::error("[termin-nodegraph/view] failed to apply style for parameter '%s.%s'",
                               node.id.c_str(),
                               descriptor.name.c_str());
                tc_ui_document_destroy_widget_recursive(document.handle(), widget->handle());
                return nullptr;
            }
            return widget;
        }

        bool attach_portals() {
            Graph* graph = projection.graph();
            if (graph == nullptr || view == nullptr)
                return false;
            for (const Node& node : graph->nodes()) {
                for (const ParameterEditorDescriptor& descriptor : projection.parameter_editors(node.handle)) {
                    const tc::trent_view value = node.params.view().get(descriptor.name);
                    gui_native::Widget* widget = create_parameter_widget(node, descriptor, value);
                    if (widget == nullptr)
                        return false;
                    const tc_graphic_item_handle anchor = projection.parameter_item(node.handle, descriptor.name);
                    if (tc_graphic_item_handle_is_invalid(anchor) ||
                        !view->set_widget_portal(anchor, widget->handle())) {
                        tc::Log::error("[termin-nodegraph/view] failed to attach parameter portal '%s.%s'",
                                       node.id.c_str(),
                                       descriptor.name.c_str());
                        tc_ui_document_destroy_widget_recursive(document.handle(), widget->handle());
                        return false;
                    }
                    parameter_widgets.push_back({node.handle, node.id, descriptor.name, widget->handle()});
                }
                const auto body = body_widgets.find(node.id);
                if (body == body_widgets.end())
                    continue;
                const tc_graphic_item_handle anchor = projection.body_item(node.handle);
                if (tc_graphic_item_handle_is_invalid(anchor) ||
                    !view->set_widget_portal(anchor, body->second.content.widget)) {
                    tc::Log::error("[termin-nodegraph/view] failed to attach body portal '%s'", node.id.c_str());
                    return false;
                }
            }
            request_render();
            return true;
        }

        bool rebuild() {
            if (!open()) {
                tc::Log::error("[termin-nodegraph/view] cannot rebuild a closed or invalid view");
                return false;
            }
            clear_portals();
            destroy_parameter_widgets();
            if (!prepare_body_widgets() || !projection.rebuild() || !attach_portals()) {
                clear_portals();
                destroy_parameter_widgets();
                return false;
            }
            return true;
        }

        bool refresh_after_projection_rebuild() {
            clear_portals();
            destroy_parameter_widgets();
            return prepare_body_widgets() && attach_portals();
        }

        bool set_parameter(NodeHandle node_handle, const std::string& name, tc::trent value) {
            Graph* graph = projection.graph();
            if (!open() || graph == nullptr)
                return false;
            const auto result = graph->set_node_param(node_handle, name, *value.raw());
            if (!result) {
                tc::Log::error("[termin-nodegraph/view] parameter mutation failed for '%s': %s",
                               name.c_str(),
                               result.message.c_str());
                return false;
            }
            projection.acknowledge_graph_revision();
            const auto node = graph->node(node_handle);
            if (!node) {
                tc::Log::error("[termin-nodegraph/view] parameter mutation lost its node snapshot");
                return false;
            }
            const tc::trent_view current = node->params.view().get(name);
            notify_parameter_changed(*node, name, current);
            notify_graph_changed(graph->revision());
            request_render();
            return true;
        }

        bool pointer(tc_ui_point world, const tc_ui_pointer_event& event) {
            if (!open() || event.type == TC_UI_POINTER_WHEEL || event.type == TC_UI_POINTER_ENTER ||
                event.type == TC_UI_POINTER_LEAVE)
                return false;
            if (projection.graph() && projection.graph()->revision() != projection.projected_revision() && !rebuild())
                return false;
            const bool completing_connection = event.type == TC_UI_POINTER_UP && projection.pending_connection();
            const std::uint64_t before = projection.graph() ? projection.graph()->revision() : 0;
            const bool handled = projection.pointer(
                {pointer_phase(event.type), pointer_button(event.button), world.x, world.y, view->zoom()});
            if (completing_connection && projection.graph() && projection.graph()->revision() != before &&
                !refresh_after_projection_rebuild()) {
                tc::Log::error("[termin-nodegraph/view] failed to restore portals after connecting nodes");
            }
            return handled;
        }

        bool key(const tc_ui_key_event& event) {
            if (!open() || event.type != TC_UI_KEY_DOWN || event.key != TC_UI_KEY_DELETE)
                return false;
            const std::uint64_t before = projection.graph() ? projection.graph()->revision() : 0;
            const bool removed = projection.delete_selection();
            if (removed && projection.graph() && projection.graph()->revision() != before &&
                !refresh_after_projection_rebuild()) {
                tc::Log::error("[termin-nodegraph/view] failed to restore portals after deleting selection");
            }
            return removed;
        }

        void close() noexcept {
            if (is_closed)
                return;
            is_closed = true;
            if (document.valid() && view && tc_ui_document_is_alive(document.handle(), view->handle())) {
                view->set_pointer_handler({});
                view->set_key_handler({});
                clear_portals();
                destroy_parameter_widgets();
                destroy_body_widgets();
                const tc_widget_handle root = view->handle();
                view = nullptr;
                if (!tc_ui_document_destroy_widget_recursive(document.handle(), root))
                    tc::Log::error("[termin-nodegraph/view] failed to destroy root widget");
            } else {
                view = nullptr;
                parameter_widgets.clear();
                body_widgets.clear();
            }
            projection.close();
            presentation.reset();
            body_content_provider = {};
            request_render_callback = {};
            graph_changed_callback = {};
            parameter_changed_callback = {};
            context_requested_callback = {};
        }
    };

    NodeGraphView::NodeGraphView(gui_native::TcDocument document,
                                 Graph* graph,
                                 std::shared_ptr<const PresentationPolicy> presentation,
                                 BodyContentProvider body_content_provider)
        : impl_(std::make_unique<Impl>(document, graph, std::move(presentation), std::move(body_content_provider))) {
        impl_->initialize();
    }

    NodeGraphView::~NodeGraphView() = default;
    NodeGraphView::NodeGraphView(NodeGraphView&&) noexcept = default;
    NodeGraphView& NodeGraphView::operator=(NodeGraphView&&) noexcept = default;

    void NodeGraphView::close() noexcept {
        if (impl_)
            impl_->close();
    }

    bool NodeGraphView::closed() const {
        return !impl_ || impl_->is_closed;
    }

    gui_native::TcDocument NodeGraphView::document() const {
        return impl_ ? impl_->document : gui_native::TcDocument{};
    }

    Graph* NodeGraphView::graph() const {
        return impl_ ? impl_->projection.graph() : nullptr;
    }

    tc_widget_handle NodeGraphView::root_widget() const {
        return impl_ && impl_->view ? impl_->view->handle() : tc_widget_handle_invalid();
    }

    gui_native::SceneView* NodeGraphView::scene_view() const {
        return impl_ ? impl_->view : nullptr;
    }

    NodeGraphProjection* NodeGraphView::projection() const {
        return impl_ ? &impl_->projection : nullptr;
    }

    bool NodeGraphView::set_graph(Graph* graph) {
        if (closed() || graph == nullptr) {
            tc::Log::error("[termin-nodegraph/view] cannot install an invalid graph");
            return false;
        }
        impl_->clear_portals();
        impl_->destroy_parameter_widgets();
        impl_->destroy_body_widgets();
        if (!impl_->projection.set_graph(graph))
            return false;
        return impl_->rebuild();
    }

    bool NodeGraphView::rebuild() {
        return impl_ && impl_->rebuild();
    }

    bool NodeGraphView::sync() {
        if (closed() || graph() == nullptr)
            return false;
        if (graph()->revision() == impl_->projection.projected_revision())
            return false;
        return impl_->rebuild();
    }

    tc_widget_handle NodeGraphView::parameter_widget(NodeHandle node, const std::string& name) const {
        if (!impl_)
            return tc_widget_handle_invalid();
        const auto found =
            std::find_if(impl_->parameter_widgets.begin(),
                         impl_->parameter_widgets.end(),
                         [&](const Impl::ParameterWidget& entry) { return entry.node == node && entry.name == name; });
        return found == impl_->parameter_widgets.end() ? tc_widget_handle_invalid() : found->widget;
    }

    tc_widget_handle NodeGraphView::body_widget(NodeHandle node) const {
        if (!impl_ || impl_->projection.graph() == nullptr)
            return tc_widget_handle_invalid();
        const auto snapshot = impl_->projection.graph()->node(node);
        if (!snapshot)
            return tc_widget_handle_invalid();
        const auto found = impl_->body_widgets.find(snapshot->id);
        return found == impl_->body_widgets.end() ? tc_widget_handle_invalid() : found->second.content.widget;
    }

    void NodeGraphView::set_request_render_callback(RequestRenderCallback callback) {
        if (impl_)
            impl_->request_render_callback = std::move(callback);
    }

    void NodeGraphView::set_graph_changed_callback(GraphChangedCallback callback) {
        if (impl_)
            impl_->graph_changed_callback = std::move(callback);
    }

    void NodeGraphView::set_parameter_changed_callback(ParameterChangedCallback callback) {
        if (impl_)
            impl_->parameter_changed_callback = std::move(callback);
    }

    void NodeGraphView::set_context_requested_callback(ContextRequestedCallback callback) {
        if (impl_)
            impl_->context_requested_callback = std::move(callback);
    }

} // namespace termin::nodegraph
