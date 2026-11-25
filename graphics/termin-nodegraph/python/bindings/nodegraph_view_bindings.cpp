#include "nodegraph_view_bindings.hpp"

#include <nanobind/stl/array.h>
#include <nanobind/stl/string.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string_view>

#include <termin/gui_native/python_widget_handle.hpp>
#include <termin/gui_native/scene_view.hpp>
#include <termin/nodegraph/view.hpp>

namespace nb = nanobind;
using namespace nb::literals;

namespace termin::nodegraph::python_bindings {
    namespace {
        using gui_native::TcDocument;
        using gui_native::python_bindings::WidgetHandle;

        nb::dict copy_socket(const Socket& socket) {
            nb::dict result;
            result["name"] = socket.name;
            result["socket_type"] = socket.type;
            result["multi"] = socket.multi;
            return result;
        }

        nb::list copy_sockets(const std::vector<Socket>& sockets) {
            nb::list result;
            for (const Socket& socket : sockets)
                result.append(copy_socket(socket));
            return result;
        }

        nb::dict copy_node(const Node& node) {
            nb::dict result;
            result["id"] = node.id;
            result["kind"] = node.kind;
            result["title"] = node.title;
            result["x"] = node.x;
            result["y"] = node.y;
            result["width"] = node.width;
            result["height"] = node.height;
            result["params"] = copy_value(node.params.get());
            result["data"] = copy_value(node.data.get());
            result["inputs"] = copy_sockets(node.inputs);
            result["outputs"] = copy_sockets(node.outputs);
            return result;
        }

        const char* direction_name(SocketDirection direction) {
            return direction == SocketDirection::Input ? "input" : "output";
        }

        ProjectionColor color(nb::handle value) {
            const auto rgba = nb::cast<std::array<float, 4>>(value);
            for (const float component : rgba) {
                if (!std::isfinite(component) || component < 0.0f || component > 1.0f)
                    throw nb::value_error("nodegraph colors require four finite sRGB components in [0, 1]");
            }
            return {rgba[0], rgba[1], rgba[2], rgba[3]};
        }

        ParameterEditorDescriptor parameter_descriptor(const nb::dict& value) {
            ParameterEditorDescriptor descriptor;
            descriptor.name = nb::cast<std::string>(value["name"]);
            descriptor.label = value.contains("label") ? nb::cast<std::string>(value["label"]) : descriptor.name;
            if (value.contains("kind")) {
                const auto kind = nb::cast<std::string>(value["kind"]);
                static constexpr std::pair<std::string_view, ParameterEditorKind> kinds[] = {
                    {"auto", ParameterEditorKind::Automatic},
                    {"bool", ParameterEditorKind::Boolean},
                    {"enum", ParameterEditorKind::Enumeration},
                    {"int", ParameterEditorKind::Integer},
                    {"float", ParameterEditorKind::FloatingPoint},
                    {"text", ParameterEditorKind::Text},
                };
                const auto match = std::ranges::find_if(kinds, [&](const auto& item) { return item.first == kind; });
                if (match == std::end(kinds))
                    throw nb::value_error("unknown nodegraph parameter editor kind");
                descriptor.kind = match->second;
            }
            if (value.contains("min"))
                descriptor.minimum = nb::cast<double>(value["min"]);
            if (value.contains("max"))
                descriptor.maximum = nb::cast<double>(value["max"]);
            descriptor.step = descriptor.kind == ParameterEditorKind::Integer ? 1.0 : 0.1;
            if (value.contains("step"))
                descriptor.step = nb::cast<double>(value["step"]);
            if (value.contains("decimals"))
                descriptor.decimals = nb::cast<int>(value["decimals"]);
            if (value.contains("style"))
                descriptor.style = nb::cast<tc_ui_style_override>(value["style"]);
            if (value.contains("choices")) {
                for (nb::handle choice : nb::cast<nb::iterable>(value["choices"])) {
                    const auto pair = nb::cast<std::array<std::string, 2>>(choice);
                    descriptor.choices.push_back({pair[0], pair[1]});
                }
            }
            return descriptor;
        }

        struct PythonCallbacks {
            nb::object owner;
            nb::object view_owner;
            nb::dict functions;
            unsigned depth = 0;

            struct Dispatch {
                PythonCallbacks& state;
                explicit Dispatch(PythonCallbacks& callbacks) : state(callbacks) { ++state.depth; }
                ~Dispatch() { --state.depth; }
            };

            bool has(const char* name) const { return functions.contains(name); }

            template<typename... Args>
            nb::object call(const char* name, Args&&... args) {
                return functions[name](std::forward<Args>(args)...);
            }

            void clear() {
                nb::gil_scoped_acquire gil;
                functions.clear();
                owner.reset();
                view_owner.reset();
            }
        };

        class PythonPresentation final : public DefaultPresentationPolicy {
        public:
            explicit PythonPresentation(std::shared_ptr<PythonCallbacks> state) : state_(std::move(state)) {}

            NodePalette node_palette(const Node& node) const override {
                auto palette = DefaultPresentationPolicy::node_palette(node);
                nb::gil_scoped_acquire gil;
                if (!state_->has("node_palette"))
                    return palette;
                PythonCallbacks::Dispatch dispatch(*state_);
                const auto result = state_->call("node_palette", copy_node(node));
                if (result.is_none())
                    return palette;
                const auto options = nb::cast<nb::dict>(result);
                if (options.contains("body"))
                    palette.body = color(options["body"]);
                if (options.contains("title"))
                    palette.title = color(options["title"]);
                if (options.contains("border"))
                    palette.border = color(options["border"]);
                if (options.contains("text"))
                    palette.text = color(options["text"]);
                return palette;
            }

            ProjectionColor socket_color(const Node& node, const Socket& socket, SocketDirection direction) const override {
                nb::gil_scoped_acquire gil;
                if (state_->has("socket_color")) {
                    PythonCallbacks::Dispatch dispatch(*state_);
                    const auto result = state_->call("socket_color", copy_node(node), copy_socket(socket), direction_name(direction));
                    if (!result.is_none())
                        return color(result);
                }
                return DefaultPresentationPolicy::socket_color(node, socket, direction);
            }

            std::string socket_label(const Node& node, const Socket& socket, SocketDirection direction) const override {
                nb::gil_scoped_acquire gil;
                if (state_->has("socket_label")) {
                    PythonCallbacks::Dispatch dispatch(*state_);
                    const auto result = state_->call("socket_label", copy_node(node), copy_socket(socket), direction_name(direction));
                    if (!result.is_none())
                        return nb::cast<std::string>(result);
                }
                return DefaultPresentationPolicy::socket_label(node, socket, direction);
            }

            std::vector<ParameterEditorDescriptor> parameter_editors(const Node& node) const override {
                nb::gil_scoped_acquire gil;
                if (state_->has("parameter_editors")) {
                    PythonCallbacks::Dispatch dispatch(*state_);
                    const auto result = state_->call("parameter_editors", copy_node(node));
                    if (!result.is_none()) {
                        std::vector<ParameterEditorDescriptor> descriptors;
                        for (nb::handle value : nb::cast<nb::iterable>(result))
                            descriptors.push_back(parameter_descriptor(nb::cast<nb::dict>(value)));
                        return descriptors;
                    }
                }
                return DefaultPresentationPolicy::parameter_editors(node);
            }

        private:
            std::shared_ptr<PythonCallbacks> state_;
        };

        struct BodyUpdate {
            std::shared_ptr<PythonCallbacks> state;
            nb::object callback;

            BodyUpdate(std::shared_ptr<PythonCallbacks> callbacks, nb::object update)
                : state(std::move(callbacks)), callback(std::move(update)) {}

            ~BodyUpdate() {
                nb::gil_scoped_acquire gil;
                callback.reset();
            }

            void invoke(const Node& node) const {
                nb::gil_scoped_acquire gil;
                PythonCallbacks::Dispatch dispatch(*state);
                callback(copy_node(node));
            }
        };

        std::optional<NodeBodyContent> body_content(const std::shared_ptr<PythonCallbacks>& state,
                                                    TcDocument document, const Node& node) {
            nb::gil_scoped_acquire gil;
            PythonCallbacks::Dispatch dispatch(*state);
            auto result = state->call("body_content", document, copy_node(node));
            if (result.is_none())
                return std::nullopt;
            const auto tuple = nb::cast<nb::tuple>(result);
            if (tuple.size() != 3)
                throw nb::value_error("expected body handle, layout and optional update callback");
            const auto layout = nb::cast<std::array<float, 6>>(tuple[1]);
            NodeBodyContent content{
                nb::cast<WidgetHandle>(tuple[0]).handle,
                {layout[0], layout[1], layout[2], layout[3], layout[4], layout[5]},
                {}};
            if (!tuple[2].is_none()) {
                auto update = std::make_shared<BodyUpdate>(state, nb::borrow<nb::object>(tuple[2]));
                content.update = [update = std::move(update)](const Node& current) { update->invoke(current); };
            }
            return content;
        }

        nb::dict context_event(Graph& graph, float x, float y, const std::optional<SemanticHit>& hit) {
            nb::dict event;
            event["kind"] = "background";
            event["world_x"] = x;
            event["world_y"] = y;
            if (!hit)
                return event;
            const auto& ref = hit->semantic;
            if (ref.kind == SemanticKind::Node || ref.kind == SemanticKind::Socket) {
                const auto node = graph.node(ref.kind == SemanticKind::Socket ? ref.socket.node : ref.node);
                if (node) {
                    event["node_id"] = node->id;
                    event["kind"] = ref.kind == SemanticKind::Socket ? "socket" : "node";
                    if (ref.kind == SemanticKind::Socket) {
                        event["socket_name"] = ref.socket.name;
                        event["socket_direction"] = direction_name(ref.socket.direction);
                    }
                }
            } else if (ref.kind == SemanticKind::Edge) {
                if (const auto edge = graph.edge(ref.edge)) {
                    event["kind"] = "edge";
                    event["edge_id"] = edge->id;
                }
            } else if (ref.kind == SemanticKind::Group) {
                if (const auto group = graph.group(ref.group)) {
                    event["kind"] = "group";
                    event["group_id"] = group->id;
                }
            }
            return event;
        }

        class PythonView final {
        public:
            PythonView(TcDocument document, nb::object graph, const nb::dict& callbacks, nb::object self)
                : state_(std::make_shared<PythonCallbacks>()) {
                state_->owner = std::move(graph);
                state_->functions.update(callbacks);
                NodeGraphView::BodyContentProvider provider;
                if (state_->has("body_content"))
                    provider = [state = state_](TcDocument doc, const Node& node) { return body_content(state, doc, node); };
                const bool has_policy = state_->has("node_palette") || state_->has("socket_color") ||
                                        state_->has("socket_label") || state_->has("parameter_editors");
                view_ = std::make_unique<NodeGraphView>(
                    document, &unwrap_graph(state_->owner),
                    has_policy ? std::make_shared<PythonPresentation>(state_) : nullptr, std::move(provider));
                auto state = state_;
                view_->set_closed_callback([state] { state->clear(); });
                if (state->has("request_render"))
                    view_->set_request_render_callback([state] {
                        nb::gil_scoped_acquire gil;
                        PythonCallbacks::Dispatch dispatch(*state);
                        state->call("request_render");
                    });
                if (state->has("graph_changed"))
                    view_->set_graph_changed_callback([state](std::uint64_t revision) {
                        nb::gil_scoped_acquire gil;
                        PythonCallbacks::Dispatch dispatch(*state);
                        state->call("graph_changed", revision);
                    });
                if (state->has("parameter_changed"))
                    view_->set_parameter_changed_callback([state](const Node& node, const std::string& name, tc::trent_view value) {
                        nb::gil_scoped_acquire gil;
                        PythonCallbacks::Dispatch dispatch(*state);
                        state->call("parameter_changed", copy_node(node), name, copy_value(*value.raw()));
                    });
                if (state->has("context"))
                    view_->set_context_requested_callback([this, state](float x, float y, std::optional<SemanticHit> hit) {
                        nb::gil_scoped_acquire gil;
                        PythonCallbacks::Dispatch dispatch(*state);
                        state->call("context", context_event(*view_->graph(), x, y, hit));
                    });

                // Document-owned widgets can dispatch even after Python drops
                // its last reference. Release this hold after native teardown.
                state_->view_owner = std::move(self);
            }

            bool closed() const { return view_->closed(); }
            WidgetHandle root_handle() const { return {view_->root_widget()}; }

            WidgetHandle parameter_handle(const std::string& id, const std::string& name) const {
                const auto node = view_->graph() ? view_->graph()->find_node(id) : std::nullopt;
                return {node ? view_->parameter_widget(*node, name) : tc_widget_handle_invalid()};
            }

            WidgetHandle body_handle(const std::string& id) const {
                const auto node = view_->graph() ? view_->graph()->find_node(id) : std::nullopt;
                return {node ? view_->body_widget(*node) : tc_widget_handle_invalid()};
            }

            nb::tuple world_to_screen(float x, float y) const {
                const auto result = scene().world_to_screen({x, y});
                return nb::make_tuple(result.x, result.y);
            }

            nb::tuple screen_to_world(float x, float y) const {
                const auto result = scene().screen_to_world({x, y});
                return nb::make_tuple(result.x, result.y);
            }

            void check_mutation() const {
                if (state_->depth)
                    throw std::runtime_error("defer nodegraph view changes until the Python callback returns");
                if (closed())
                    throw std::runtime_error("nodegraph view is closed");
            }

            void set_graph(nb::object graph) {
                check_mutation();
                Graph& next = unwrap_graph(graph);
                try {
                    if (!view_->set_graph(&next))
                        throw std::runtime_error("failed to replace the native nodegraph");
                    state_->owner = std::move(graph);
                } catch (...) {
                    view_->close();
                    throw;
                }
            }

            bool rebuild() { check_mutation(); return view_->rebuild(); }
            bool sync() { check_mutation(); return view_->sync(); }
            void close() {
                if (!closed()) {
                    check_mutation();
                    view_->close();
                }
            }

        private:
            const gui_native::SceneView& scene() const {
                if (closed())
                    throw std::runtime_error("nodegraph view is closed");
                return *view_->scene_view();
            }

            std::shared_ptr<PythonCallbacks> state_;
            std::unique_ptr<NodeGraphView> view_;
        };

    }

    void bind_view(nb::module_& module) {
        nb::class_<PythonView>(module, "NativeNodeGraphView")
            .def("__init__", [](nb::pointer_and_handle<PythonView> self,
                                TcDocument document, nb::object graph, const nb::dict& callbacks) {
                new (self.p) PythonView(document, std::move(graph), callbacks, nb::borrow<nb::object>(self.h));
            }, "document"_a, "graph"_a, "callbacks"_a)
            .def_prop_ro("closed", &PythonView::closed)
            .def_prop_ro("root_handle", &PythonView::root_handle)
            .def("parameter_handle", &PythonView::parameter_handle)
            .def("body_handle", &PythonView::body_handle)
            .def("world_to_screen", &PythonView::world_to_screen)
            .def("screen_to_world", &PythonView::screen_to_world)
            .def("check_mutation", &PythonView::check_mutation)
            .def("set_graph", &PythonView::set_graph)
            .def("rebuild", &PythonView::rebuild)
            .def("sync", &PythonView::sync)
            .def("close", &PythonView::close);
    }
}
