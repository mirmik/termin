#include <cassert>
#include <cmath>
#include <memory>
#include <string>

#include <termin/gui_native/checkbox.hpp>
#include <termin/gui_native/combo_box.hpp>
#include <termin/gui_native/document_builder.hpp>
#include <termin/gui_native/label.hpp>
#include <termin/gui_native/scene_view.hpp>
#include <termin/gui_native/spin_box.hpp>
#include <termin/gui_native/text_input.hpp>
#include <termin/nodegraph/view.hpp>
#include <termin_visual_scene/scene2d.hpp>

namespace ng = termin::nodegraph;
namespace ui = termin::gui_native;

namespace {

    template <typename T> T* widget_body(ui::TcDocument document, tc_widget_handle handle) {
        tc_widget* widget = tc_ui_document_resolve_widget(document.handle(), handle);
        if (widget == nullptr || widget->body == nullptr)
            return nullptr;
        return dynamic_cast<T*>(static_cast<ui::Widget*>(widget->body));
    }

    ng::NodeDescriptor editable_node(std::string id) {
        ng::NodeDescriptor node;
        node.id = std::move(id);
        node.kind = "generic.editable";
        node.title = "Editable";
        node.x = -120.0f;
        node.y = -80.0f;
        node.width = 240.0f;
        node.height = 120.0f;
        node.params["enabled"] = false;
        node.params["mode"] = "fast";
        node.params["count"] = std::int64_t{2};
        node.params["gain"] = 0.5;
        node.params["caption"] = "original";
        node.data["param_specs"] = tc::trent::dict();
        node.data["param_specs"]["enabled"]["kind"] = "bool";
        node.data["param_specs"]["enabled"]["label"] = "Enabled";
        node.data["param_specs"]["mode"]["kind"] = "enum";
        node.data["param_specs"]["mode"]["label"] = "Mode";
        node.data["param_specs"]["mode"]["items"] = tc::trent::list();
        node.data["param_specs"]["mode"]["items"].push_back("fast");
        node.data["param_specs"]["mode"]["items"].push_back("quality");
        node.data["param_specs"]["count"]["kind"] = "int";
        node.data["param_specs"]["count"]["min"] = std::int64_t{0};
        node.data["param_specs"]["count"]["max"] = std::int64_t{10};
        node.data["param_specs"]["gain"]["kind"] = "float";
        node.data["param_specs"]["gain"]["min"] = 0.0;
        node.data["param_specs"]["gain"]["max"] = 2.0;
        node.data["param_specs"]["gain"]["step"] = 0.25;
        node.data["param_specs"]["caption"]["kind"] = "text";
        return node;
    }

    class StyledPresentation final : public ng::DefaultPresentationPolicy {
    public:
        std::vector<ng::ParameterEditorDescriptor> parameter_editors(const ng::Node& node) const override {
            auto descriptors = DefaultPresentationPolicy::parameter_editors(node);
            for (auto& descriptor : descriptors) {
                if (descriptor.name != "enabled")
                    continue;
                tc_ui_style_override style{};
                style.fields = TC_UI_STYLE_ACCENT;
                style.value.accent = {0.2f, 0.8f, 0.4f, 1.0f};
                descriptor.style = style;
            }
            return descriptors;
        }
    };

} // namespace

int main() {
    const tc_ui_document_handle document_handle = tc_ui_document_create();
    assert(!tc_ui_document_handle_is_invalid(document_handle));
    ui::TcDocument document{document_handle};

    ng::Graph graph;
    const auto created = graph.create_node(editable_node("node"));
    assert(created);

    int body_created = 0;
    int body_updated = 0;
    ng::NodeGraphView view(document,
                           &graph,
                           std::make_shared<StyledPresentation>(),
                           [&](ui::TcDocument owner, const ng::Node&) -> std::optional<ng::NodeBodyContent> {
                               ++body_created;
                               ui::DocumentBuilder builder(owner);
                               auto& label = builder.make<ui::Label>("Embedded body", 12.0f);
                               label.set_stable_id("nodegraph.body");
                               ng::NodeBodyContent content;
                               content.widget = label.handle();
                               content.layout.height = 32.0f;
                               content.update = [&](const ng::Node&) {
                                   ++body_updated;
                               };
                               return content;
                           });
    assert(!view.closed());
    assert(body_created == 1);
    assert(view.graph() == &graph);
    assert(!tc_widget_handle_is_invalid(view.root_widget()));
    assert(document.add_root(*view.scene_view()));
    document.layout_roots({0.0f, 0.0f, 900.0f, 650.0f});
    assert(view.projection()->node_visual_height(created.value) > 120.0f);

    const tc_widget_handle enabled_handle = view.parameter_widget(created.value, "enabled");
    const tc_widget_handle mode_handle = view.parameter_widget(created.value, "mode");
    const tc_widget_handle count_handle = view.parameter_widget(created.value, "count");
    const tc_widget_handle gain_handle = view.parameter_widget(created.value, "gain");
    const tc_widget_handle caption_handle = view.parameter_widget(created.value, "caption");
    const tc_widget_handle body_handle = view.body_widget(created.value);
    assert(!tc_widget_handle_is_invalid(enabled_handle));
    assert(!tc_widget_handle_is_invalid(mode_handle));
    assert(!tc_widget_handle_is_invalid(count_handle));
    assert(!tc_widget_handle_is_invalid(gain_handle));
    assert(!tc_widget_handle_is_invalid(caption_handle));
    assert(!tc_widget_handle_is_invalid(body_handle));
    const auto presented = view.projection()->parameter_editors(created.value);
    assert(presented.size() == 5);
    assert(presented.front().name == "enabled" && presented.front().label == "Enabled");

    tc_widget* enabled_raw = tc_ui_document_resolve_widget(document_handle, enabled_handle);
    assert(enabled_raw && enabled_raw->parent == view.scene_view()->c_widget());
    assert((tc_widget_style_override(enabled_raw).fields & TC_UI_STYLE_ACCENT) != 0);
    view.scene_view()->set_zoom(1.7f, {450.0f, 325.0f});
    view.scene_view()->set_offset({420.0f, 260.0f});
    document.layout_roots({0.0f, 0.0f, 900.0f, 650.0f});
    assert(std::fabs(tc_widget_subtree_transform(enabled_raw).scale - 1.7f) < 1.0e-5f);

    int parameter_changes = 0;
    int graph_changes = 0;
    std::uint64_t observed_revision = 0;
    std::string observed_name;
    view.set_parameter_changed_callback([&](const ng::Node& node, const std::string& name, tc::trent_view value) {
        ++parameter_changes;
        observed_revision = graph.revision();
        observed_name = name;
        assert(node.params.view().get(name).raw_type() == value.raw_type());
    });
    view.set_graph_changed_callback([&](std::uint64_t revision) {
        ++graph_changes;
        assert(revision == graph.revision());
    });

    std::uint64_t revision = graph.revision();
    widget_body<ui::Checkbox>(document, enabled_handle)->set_checked(true);
    assert(graph.revision() == ++revision);
    assert(graph.node(created.value)->params.view().get("enabled").as_bool());

    auto* mode = widget_body<ui::ComboBox>(document, mode_handle);
    assert(mode->item_count() == 2 && mode->selected_text() == "fast");
    mode->set_selected_index(1);
    assert(graph.revision() == ++revision);
    assert(graph.node(created.value)->params.view().get("mode").as_string() == "quality");

    auto* count = widget_body<ui::SpinBox>(document, count_handle);
    assert(count->min_value() == 0.0f && count->max_value() == 10.0f && count->step() == 1.0f &&
           count->decimals() == 0);
    count->set_value(7.0f);
    assert(graph.revision() == ++revision);
    assert(graph.node(created.value)->params.view().get("count").as_integer() == 7);

    auto* gain = widget_body<ui::SpinBox>(document, gain_handle);
    assert(gain->min_value() == 0.0f && gain->max_value() == 2.0f && gain->step() == 0.25f && gain->decimals() == 3);
    gain->set_value(1.25f);
    assert(graph.revision() == ++revision);
    assert(std::fabs(graph.node(created.value)->params.view().get("gain").as_numer() - 1.25) < 1.0e-6);

    auto* caption = widget_body<ui::TextInput>(document, caption_handle);
    caption->submitted().emit(*caption, "changed");
    assert(graph.revision() == ++revision);
    assert(graph.node(created.value)->params.view().get("caption").as_string() == "changed");
    assert(parameter_changes == 5 && graph_changes == 5);
    assert(observed_revision == graph.revision() && observed_name == "caption");
    assert(view.projection()->projected_revision() == graph.revision());

    int contexts = 0;
    view.set_context_requested_callback([&](float, float, std::optional<ng::SemanticHit> hit) {
        ++contexts;
        assert(hit && hit->semantic.kind == ng::SemanticKind::Node);
    });
    assert(view.projection()->pointer(
        {ng::PointerPhase::Down, ng::PointerButton::Right, -100.0f, -70.0f, view.scene_view()->zoom()}));
    assert(contexts == 1);

    const tc_widget_handle old_enabled = enabled_handle;
    assert(graph.move_node(created.value, 30.0f, 40.0f));
    assert(view.sync());
    assert(body_updated == 1);
    assert(!tc_ui_document_is_alive(document_handle, old_enabled));
    assert(!tc_widget_handle_is_invalid(view.parameter_widget(created.value, "enabled")));
    assert(view.body_widget(created.value).index == body_handle.index);

    ng::Graph replacement;
    const auto replacement_node = replacement.create_node(editable_node("replacement"));
    assert(replacement_node);
    const tc_widget_handle old_body = body_handle;
    assert(view.set_graph(&replacement));
    assert(!tc_ui_document_is_alive(document_handle, old_body));
    assert(body_created == 2);
    assert(!tc_widget_handle_is_invalid(view.body_widget(replacement_node.value)));

    const tc_widget_handle root = view.root_widget();
    const tc_widget_handle replacement_param = view.parameter_widget(replacement_node.value, "enabled");
    const tc_widget_handle replacement_body = view.body_widget(replacement_node.value);
    const tc_visual_scene_handle scene = view.projection()->scene();
    view.close();
    assert(view.closed());
    assert(!tc_ui_document_is_alive(document_handle, root));
    assert(!tc_ui_document_is_alive(document_handle, replacement_param));
    assert(!tc_ui_document_is_alive(document_handle, replacement_body));
    assert(!termin::visual::TcVisualScene{scene}.valid());
    view.close();
    tc_ui_document_destroy(document_handle);
    return 0;
}
