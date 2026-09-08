#include <cassert>
#include <cstdint>
#include <string>

#include <termin/gui_native/checkbox.hpp>
#include <termin/gui_native/document_builder.hpp>
#include <termin/gui_native/label.hpp>
#include <termin/nodegraph/view_c_api.h>

namespace ui = termin::gui_native;

namespace {

    struct State {
        tc_nodegraph_handle graph = tc_nodegraph_handle_invalid();
        int presented = 0;
        int bodies_created = 0;
        int bodies_updated = 0;
        int renders = 0;
        int graph_changes = 0;
        int parameter_changes = 0;
        int contexts = 0;
        int destroyed = 0;
        tc_ui_style_override style{};
    };

    bool present_parameter(void* userdata,
                           tc_nodegraph_node_handle,
                           const char* name,
                           const tc_value* value,
                           tc_nodegraph_parameter_editor_desc* descriptor) {
        State& state = *static_cast<State*>(userdata);
        ++state.presented;
        assert(std::string(name) == "enabled");
        assert(value && value->type == TC_VALUE_BOOL);
        descriptor->label = "Enabled through C ABI";
        descriptor->kind = TC_NODEGRAPH_PARAMETER_BOOLEAN;
        descriptor->style = &state.style;
        return true;
    }

    bool create_body(void* userdata,
                     tc_ui_document_handle document,
                     tc_nodegraph_node_handle,
                     tc_widget_handle* out_widget,
                     tc_nodegraph_body_layout* out_layout) {
        State& state = *static_cast<State*>(userdata);
        ++state.bodies_created;
        ui::DocumentBuilder builder(ui::TcDocument{document});
        auto& label = builder.make<ui::Label>("C ABI body", 12.0f);
        *out_widget = label.handle();
        out_layout->height = 30.0f;
        return true;
    }

    void update_body(void* userdata, tc_nodegraph_node_handle, tc_widget_handle) {
        ++static_cast<State*>(userdata)->bodies_updated;
    }

    void request_render(void* userdata) {
        ++static_cast<State*>(userdata)->renders;
    }

    void graph_changed(void* userdata, std::uint64_t revision) {
        State& state = *static_cast<State*>(userdata);
        ++state.graph_changes;
        assert(revision == tc_nodegraph_revision(state.graph));
    }

    void parameter_changed(void* userdata, tc_nodegraph_node_handle, const char* name, const tc_value* value) {
        State& state = *static_cast<State*>(userdata);
        ++state.parameter_changes;
        assert(std::string(name) == "enabled");
        assert(value && value->type == TC_VALUE_BOOL && value->data.b);
        assert(tc_nodegraph_revision(state.graph) > 0);
    }

    void context_requested(void* userdata, float, float, const tc_nodegraph_semantic_ref* semantic) {
        State& state = *static_cast<State*>(userdata);
        ++state.contexts;
        assert(semantic && semantic->struct_size == sizeof(*semantic));
        assert(semantic->kind == TC_NODEGRAPH_SEMANTIC_NODE);
    }

    void destroy_userdata(void* userdata) {
        ++static_cast<State*>(userdata)->destroyed;
    }

} // namespace

int main() {
    State state;
    state.style.fields = TC_UI_STYLE_ACCENT;
    state.style.value.accent = {0.25f, 0.75f, 0.45f, 1.0f};
    state.graph = tc_nodegraph_create();
    assert(!tc_nodegraph_handle_is_invalid(state.graph));

    tc_value params = tc_value_dict_new();
    tc_value_dict_set(&params, "enabled", tc_value_bool(false));
    tc_nodegraph_node_desc descriptor{};
    descriptor.struct_size = sizeof(descriptor);
    descriptor.id = "node";
    descriptor.kind = "generic";
    descriptor.title = "Node";
    descriptor.width = 220.0f;
    descriptor.height = 120.0f;
    descriptor.params = &params;
    tc_nodegraph_node_handle node = tc_nodegraph_entity_handle_invalid();
    assert(tc_nodegraph_create_node(state.graph, &descriptor, &node) == TC_NODEGRAPH_OK);
    tc_value_free(&params);

    const tc_ui_document_handle document = tc_ui_document_create();
    assert(!tc_ui_document_handle_is_invalid(document));
    tc_nodegraph_view_config config{};
    config.struct_size = sizeof(config);
    config.userdata = &state;
    config.destroy_userdata = destroy_userdata;
    config.present_parameter = present_parameter;
    config.create_body = create_body;
    config.update_body = update_body;
    config.request_render = request_render;
    config.graph_changed = graph_changed;
    config.parameter_changed = parameter_changed;
    config.context_requested = context_requested;
    const tc_nodegraph_view_handle view = tc_nodegraph_view_create(document, state.graph, &config);
    assert(!tc_nodegraph_view_handle_is_invalid(view));
    assert(tc_nodegraph_view_is_valid(view));
    assert(state.presented == 1 && state.bodies_created == 1);

    const tc_widget_handle root = tc_nodegraph_view_root_widget(view);
    const tc_widget_handle parameter = tc_nodegraph_view_parameter_widget(view, node, "enabled");
    assert(!tc_widget_handle_is_invalid(root));
    assert(!tc_widget_handle_is_invalid(parameter));
    assert(tc_ui_document_add_root(document, root));
    tc_ui_document_layout_roots(document, {0.0f, 0.0f, 900.0f, 650.0f});

    tc_widget* raw = tc_ui_document_resolve_widget(document, parameter);
    assert(raw && raw->body);
    auto* checkbox = dynamic_cast<ui::Checkbox*>(static_cast<ui::Widget*>(raw->body));
    assert(checkbox);
    const std::uint64_t revision = tc_nodegraph_revision(state.graph);
    checkbox->set_checked(true);
    assert(tc_nodegraph_revision(state.graph) == revision + 1);
    assert(state.parameter_changes == 1 && state.graph_changes == 1);

    const tc_ui_pointer_event right_click{
        TC_UI_POINTER_DOWN, 510.0f, 330.0f, 1, 1, 0, 0.0f, 0.0f, TC_UI_POINTER_CANCEL_EXPLICIT};
    assert(tc_ui_document_dispatch_pointer_event(document, &right_click) == TC_UI_EVENT_HANDLED);
    assert(state.contexts == 1);

    assert(tc_nodegraph_move_node(state.graph, node, 20.0f, 30.0f) == TC_NODEGRAPH_OK);
    assert(tc_nodegraph_view_sync(view));
    assert(state.bodies_updated == 1);
    assert(!tc_ui_document_is_alive(document, parameter));
    assert(!tc_widget_handle_is_invalid(tc_nodegraph_view_parameter_widget(view, node, "enabled")));
    assert(!tc_nodegraph_view_sync(view));

    assert(tc_nodegraph_view_copy_last_error(view, nullptr, 0) == 1);
    tc_nodegraph_view_destroy(view);
    assert(!tc_nodegraph_view_is_valid(view));
    assert(!tc_ui_document_is_alive(document, root));
    assert(state.destroyed == 1);
    tc_nodegraph_destroy(state.graph);
    tc_ui_document_destroy(document);
    return 0;
}
