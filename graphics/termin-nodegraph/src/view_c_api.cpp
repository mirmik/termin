#include <termin/nodegraph/view_c_api.h>

#include "c_api_internal.hpp"

#include <algorithm>
#include <cstring>
#include <exception>
#include <memory>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <tcbase/tc_log.h>
#include <termin/nodegraph/view.hpp>

namespace ng = termin::nodegraph;

namespace {

    template <typename Handle> tc_nodegraph_entity_handle to_c(Handle handle) {
        return {handle.graph_id, handle.index, handle.generation};
    }

    ng::NodeHandle from_c(tc_nodegraph_node_handle handle) {
        return {handle.graph_id, handle.index, handle.generation};
    }

    tc_nodegraph_parameter_editor_kind to_c(ng::ParameterEditorKind kind) {
        switch (kind) {
        case ng::ParameterEditorKind::Automatic:
            return TC_NODEGRAPH_PARAMETER_AUTOMATIC;
        case ng::ParameterEditorKind::Boolean:
            return TC_NODEGRAPH_PARAMETER_BOOLEAN;
        case ng::ParameterEditorKind::Enumeration:
            return TC_NODEGRAPH_PARAMETER_ENUMERATION;
        case ng::ParameterEditorKind::Integer:
            return TC_NODEGRAPH_PARAMETER_INTEGER;
        case ng::ParameterEditorKind::FloatingPoint:
            return TC_NODEGRAPH_PARAMETER_FLOATING_POINT;
        case ng::ParameterEditorKind::Text:
            return TC_NODEGRAPH_PARAMETER_TEXT;
        }
        return TC_NODEGRAPH_PARAMETER_AUTOMATIC;
    }

    ng::ParameterEditorKind from_c(tc_nodegraph_parameter_editor_kind kind) {
        switch (kind) {
        case TC_NODEGRAPH_PARAMETER_BOOLEAN:
            return ng::ParameterEditorKind::Boolean;
        case TC_NODEGRAPH_PARAMETER_ENUMERATION:
            return ng::ParameterEditorKind::Enumeration;
        case TC_NODEGRAPH_PARAMETER_INTEGER:
            return ng::ParameterEditorKind::Integer;
        case TC_NODEGRAPH_PARAMETER_FLOATING_POINT:
            return ng::ParameterEditorKind::FloatingPoint;
        case TC_NODEGRAPH_PARAMETER_TEXT:
            return ng::ParameterEditorKind::Text;
        case TC_NODEGRAPH_PARAMETER_AUTOMATIC:
        default:
            return ng::ParameterEditorKind::Automatic;
        }
    }

    struct CallbackState {
        explicit CallbackState(const tc_nodegraph_view_config& source)
            : config(source) {}

        ~CallbackState() {
            if (config.destroy_userdata != nullptr) {
                try {
                    config.destroy_userdata(config.userdata);
                } catch (...) {
                    tc_log_error("NodeGraph view C API: userdata deleter threw an exception");
                }
            }
        }

        tc_nodegraph_view_config config{};
    };

    class CallbackPresentation final : public ng::DefaultPresentationPolicy {
    public:
        explicit CallbackPresentation(std::shared_ptr<CallbackState> state)
            : state_(std::move(state)) {}

        std::vector<ng::ParameterEditorDescriptor> parameter_editors(const ng::Node& node) const override {
            std::vector<ng::ParameterEditorDescriptor> result = DefaultPresentationPolicy::parameter_editors(node);
            if (state_->config.present_parameter == nullptr)
                return result;
            for (ng::ParameterEditorDescriptor& descriptor : result) {
                const tc::trent_view value = node.params.view().get(descriptor.name);
                std::vector<tc_nodegraph_parameter_choice> choices;
                choices.reserve(descriptor.choices.size());
                for (const ng::ParameterChoice& choice : descriptor.choices)
                    choices.push_back({choice.value.c_str(), choice.label.c_str()});
                tc_nodegraph_parameter_editor_desc encoded{
                    sizeof(tc_nodegraph_parameter_editor_desc),
                    descriptor.name.c_str(),
                    descriptor.label.c_str(),
                    to_c(descriptor.kind),
                    descriptor.minimum,
                    descriptor.maximum,
                    descriptor.step,
                    descriptor.decimals,
                    choices.data(),
                    choices.size(),
                    descriptor.style ? &*descriptor.style : nullptr,
                };
                if (!state_->config.present_parameter(
                        state_->config.userdata, to_c(node.handle), descriptor.name.c_str(), value.raw(), &encoded)) {
                    continue;
                }
                if (encoded.struct_size < sizeof(tc_nodegraph_parameter_editor_desc)) {
                    tc_log_error("NodeGraph view C API: parameter presenter returned an incompatible descriptor");
                    continue;
                }
                descriptor.name = encoded.name ? encoded.name : descriptor.name;
                descriptor.label = encoded.label ? encoded.label : descriptor.name;
                descriptor.kind = from_c(encoded.kind);
                descriptor.minimum = encoded.minimum;
                descriptor.maximum = encoded.maximum;
                descriptor.step = encoded.step;
                descriptor.decimals = encoded.decimals;
                descriptor.choices.clear();
                if (encoded.choice_count > 0 && encoded.choices == nullptr)
                    throw std::invalid_argument("parameter presenter returned a null choice array");
                for (std::size_t index = 0; index < encoded.choice_count; ++index) {
                    const tc_nodegraph_parameter_choice& choice = encoded.choices[index];
                    const std::string choice_value = choice.value ? choice.value : "";
                    descriptor.choices.push_back(
                        {choice_value, choice.label ? std::string(choice.label) : choice_value});
                }
                descriptor.style = encoded.style ? std::optional(*encoded.style) : std::nullopt;
            }
            return result;
        }

    private:
        std::shared_ptr<CallbackState> state_;
    };

    tc_nodegraph_semantic_ref semantic_to_c(const ng::SemanticRef& value) {
        tc_nodegraph_semantic_ref result{
            sizeof(tc_nodegraph_semantic_ref),
            TC_NODEGRAPH_SEMANTIC_NONE,
            tc_nodegraph_entity_handle_invalid(),
            tc_nodegraph_entity_handle_invalid(),
            tc_nodegraph_entity_handle_invalid(),
            nullptr,
            false,
        };
        switch (value.kind) {
        case ng::SemanticKind::Node:
            result.kind = TC_NODEGRAPH_SEMANTIC_NODE;
            result.node = to_c(value.node);
            break;
        case ng::SemanticKind::Group:
            result.kind = TC_NODEGRAPH_SEMANTIC_GROUP;
            result.group = to_c(value.group);
            break;
        case ng::SemanticKind::Edge:
            result.kind = TC_NODEGRAPH_SEMANTIC_EDGE;
            result.edge = to_c(value.edge);
            break;
        case ng::SemanticKind::Socket:
            result.kind = TC_NODEGRAPH_SEMANTIC_SOCKET;
            result.node = to_c(value.socket.node);
            result.socket_name = value.socket.name.c_str();
            result.socket_is_output = value.socket.direction == ng::SocketDirection::Output;
            break;
        case ng::SemanticKind::None:
            break;
        }
        return result;
    }

    struct ViewEntry {
        std::shared_ptr<ng::Graph> graph;
        std::shared_ptr<CallbackState> callbacks;
        std::unique_ptr<ng::NodeGraphView> view;
        std::string last_error;
    };

    struct ViewSlot {
        std::shared_ptr<ViewEntry> entry;
        std::uint32_t generation = 1;
    };

    std::mutex view_mutex;
    std::vector<ViewSlot> view_slots;
    std::vector<std::uint32_t> free_view_slots;

    std::shared_ptr<ViewEntry> acquire_view(tc_nodegraph_view_handle handle) {
        std::lock_guard lock(view_mutex);
        if (tc_nodegraph_view_handle_is_invalid(handle) || handle.index >= view_slots.size())
            return {};
        const ViewSlot& slot = view_slots[handle.index];
        return slot.entry && slot.generation == handle.generation ? slot.entry : nullptr;
    }

    std::size_t copy_string(const std::string& value, char* buffer, std::size_t capacity) {
        const std::size_t required = value.size() + 1;
        if (buffer != nullptr && capacity > 0) {
            const std::size_t copied = std::min(value.size(), capacity - 1);
            std::memcpy(buffer, value.data(), copied);
            buffer[copied] = '\0';
        }
        return required;
    }

    template <typename Result, typename Function>
    Result access_view(tc_nodegraph_view_handle handle, Result fallback, Function&& function) {
        std::shared_ptr<ViewEntry> entry = acquire_view(handle);
        if (!entry) {
            tc_log_error("NodeGraph view C API: invalid view handle");
            return fallback;
        }
        try {
            return function(*entry);
        } catch (const std::exception& error) {
            entry->last_error = error.what();
            tc_log_error("NodeGraph view C API: %s", entry->last_error.c_str());
        } catch (...) {
            entry->last_error = "unknown internal exception";
            tc_log_error("NodeGraph view C API: %s", entry->last_error.c_str());
        }
        return fallback;
    }

} // namespace

extern "C" {

tc_nodegraph_view_handle tc_nodegraph_view_create(tc_ui_document_handle document,
                                                  tc_nodegraph_handle graph_handle,
                                                  const tc_nodegraph_view_config* config) {
    if (!tc_ui_document_is_valid(document) || !tc_nodegraph_is_valid(graph_handle) ||
        (config != nullptr && config->struct_size < sizeof(tc_nodegraph_view_config))) {
        tc_log_error("NodeGraph view C API: invalid document, graph or config");
        if (config != nullptr && config->struct_size >= sizeof(tc_nodegraph_view_config) &&
            config->destroy_userdata != nullptr) {
            try {
                config->destroy_userdata(config->userdata);
            } catch (...) {
                tc_log_error("NodeGraph view C API: userdata deleter threw after rejected creation");
            }
        }
        return tc_nodegraph_view_handle_invalid();
    }
    try {
        tc_nodegraph_view_config copied{};
        copied.struct_size = sizeof(tc_nodegraph_view_config);
        if (config != nullptr)
            copied = *config;
        const auto callback_state = std::make_shared<CallbackState>(copied);
        auto entry = std::make_shared<ViewEntry>();
        entry->callbacks = callback_state;
        entry->graph = ng::detail::acquire_c_graph(graph_handle);
        if (!entry->graph)
            throw std::runtime_error("failed to acquire graph storage");
        auto presentation = std::make_shared<CallbackPresentation>(entry->callbacks);
        ng::NodeGraphView::BodyContentProvider body_provider;
        if (copied.create_body != nullptr) {
            const std::shared_ptr<CallbackState> state = entry->callbacks;
            body_provider = [state](termin::gui_native::TcDocument owner_document,
                                    const ng::Node& node) -> std::optional<ng::NodeBodyContent> {
                tc_widget_handle widget = tc_widget_handle_invalid();
                tc_nodegraph_body_layout layout{sizeof(tc_nodegraph_body_layout), 0.0f, 8.0f, 8.0f, 8.0f, 8.0f, 7.0f};
                if (!state->config.create_body(
                        state->config.userdata, owner_document.handle(), to_c(node.handle), &widget, &layout)) {
                    return std::nullopt;
                }
                if (layout.struct_size < sizeof(tc_nodegraph_body_layout))
                    throw std::invalid_argument("body provider returned an incompatible layout");
                ng::NodeBodyContent content;
                content.widget = widget;
                content.layout = {layout.height,
                                  layout.inset_left,
                                  layout.inset_right,
                                  layout.inset_top,
                                  layout.inset_bottom,
                                  layout.gap_before};
                if (state->config.update_body != nullptr) {
                    content.update = [state, widget](const ng::Node& updated) {
                        state->config.update_body(state->config.userdata, to_c(updated.handle), widget);
                    };
                }
                return content;
            };
        }
        entry->view = std::make_unique<ng::NodeGraphView>(
            termin::gui_native::TcDocument{document}, entry->graph.get(), presentation, std::move(body_provider));
        entry->view->set_request_render_callback([state = entry->callbacks] {
            if (state->config.request_render != nullptr)
                state->config.request_render(state->config.userdata);
        });
        entry->view->set_graph_changed_callback([state = entry->callbacks](std::uint64_t revision) {
            if (state->config.graph_changed != nullptr)
                state->config.graph_changed(state->config.userdata, revision);
        });
        entry->view->set_parameter_changed_callback([state = entry->callbacks](const ng::Node& node,
                                                                               const std::string& name,
                                                                               tc::trent_view value) {
            if (state->config.parameter_changed != nullptr)
                state->config.parameter_changed(state->config.userdata, to_c(node.handle), name.c_str(), value.raw());
        });
        entry->view->set_context_requested_callback(
            [state = entry->callbacks](float x, float y, std::optional<ng::SemanticHit> hit) {
                if (state->config.context_requested == nullptr)
                    return;
                const std::optional<tc_nodegraph_semantic_ref> semantic =
                    hit ? std::optional(semantic_to_c(hit->semantic)) : std::nullopt;
                state->config.context_requested(state->config.userdata, x, y, semantic ? &*semantic : nullptr);
            });

        std::lock_guard lock(view_mutex);
        std::uint32_t index;
        if (free_view_slots.empty()) {
            index = static_cast<std::uint32_t>(view_slots.size());
            view_slots.push_back({});
        } else {
            index = free_view_slots.back();
            free_view_slots.pop_back();
        }
        ViewSlot& slot = view_slots[index];
        slot.entry = std::move(entry);
        return {index, slot.generation};
    } catch (const std::exception& error) {
        tc_log_error("NodeGraph view C API: view creation failed: %s", error.what());
    } catch (...) {
        tc_log_error("NodeGraph view C API: view creation failed: unknown exception");
    }
    return tc_nodegraph_view_handle_invalid();
}

void tc_nodegraph_view_destroy(tc_nodegraph_view_handle view) {
    std::shared_ptr<ViewEntry> retired;
    {
        std::lock_guard lock(view_mutex);
        if (tc_nodegraph_view_handle_is_invalid(view) || view.index >= view_slots.size()) {
            tc_log_error("NodeGraph view C API: cannot destroy invalid view handle");
            return;
        }
        ViewSlot& slot = view_slots[view.index];
        if (!slot.entry || slot.generation != view.generation) {
            tc_log_error("NodeGraph view C API: cannot destroy stale view handle");
            return;
        }
        retired = std::move(slot.entry);
        ++slot.generation;
        if (slot.generation == 0)
            slot.generation = 1;
        free_view_slots.push_back(view.index);
    }
    retired->view->close();
}

bool tc_nodegraph_view_is_valid(tc_nodegraph_view_handle view) {
    const std::shared_ptr<ViewEntry> entry = acquire_view(view);
    return entry && entry->view && !entry->view->closed();
}

tc_widget_handle tc_nodegraph_view_root_widget(tc_nodegraph_view_handle view) {
    return access_view(view, tc_widget_handle_invalid(), [](ViewEntry& entry) { return entry.view->root_widget(); });
}

bool tc_nodegraph_view_rebuild(tc_nodegraph_view_handle view) {
    return access_view(view, false, [](ViewEntry& entry) { return entry.view->rebuild(); });
}

bool tc_nodegraph_view_sync(tc_nodegraph_view_handle view) {
    return access_view(view, false, [](ViewEntry& entry) { return entry.view->sync(); });
}

tc_widget_handle
tc_nodegraph_view_parameter_widget(tc_nodegraph_view_handle view, tc_nodegraph_node_handle node, const char* name) {
    return access_view(view, tc_widget_handle_invalid(), [&](ViewEntry& entry) {
        if (name == nullptr)
            throw std::invalid_argument("parameter name is null");
        return entry.view->parameter_widget(from_c(node), name);
    });
}

size_t tc_nodegraph_view_copy_last_error(tc_nodegraph_view_handle view, char* buffer, size_t capacity) {
    const std::shared_ptr<ViewEntry> entry = acquire_view(view);
    return entry ? copy_string(entry->last_error, buffer, capacity) : 0;
}

} // extern "C"
