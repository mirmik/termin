#include "termin/editor/frame_graph_debugger_view.hpp"
#include "termin/editor/frame_graph_debugger_source.hpp"
#include "termin/editor/remote_frame_graph_debugger_source.hpp"

#include <algorithm>
#include <charconv>
#include <sstream>
#include <stdexcept>
#include <utility>

#include <tcbase/tc_log.h>

#include <termin/gui_native/box_layout.hpp>
#include <termin/gui_native/button.hpp>
#include <termin/gui_native/canvas.hpp>
#include <termin/gui_native/checkbox.hpp>
#include <termin/gui_native/combo_box.hpp>
#include <termin/gui_native/document_builder.hpp>
#include <termin/gui_native/label.hpp>
#include <termin/gui_native/rich_text_model.hpp>
#include <termin/gui_native/rich_text_view.hpp>
#include <termin/gui_native/status_bar.hpp>
#include <termin/gui_native/text_area.hpp>
#include <termin/gui_native/text_input.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>

namespace termin {

namespace {

using gui_native::BoxLayout;
using gui_native::Button;
using gui_native::Canvas;
using gui_native::Checkbox;
using gui_native::ComboBox;
using gui_native::DocumentBuilder;
using gui_native::EdgeInsets;
using gui_native::Label;
using gui_native::Orientation;
using gui_native::RichTextModel;
using gui_native::RichTextView;
using gui_native::StatusBar;
using gui_native::TextArea;
using gui_native::TextInput;
using gui_native::Widget;

BoxLayout& labeled_row(
    DocumentBuilder& builder,
    std::string stable_id,
    std::string label,
    Widget& control
) {
    auto& row = builder.make<BoxLayout>(Orientation::Horizontal, stable_id.c_str());
    row.set_stable_id(std::move(stable_id));
    row.set_spacing(4.0f);
    auto& caption = builder.make<Label>(std::move(label));
    row.add_fixed_child(caption, 82.0f);
    row.add_stretch_child(control);
    return row;
}

const char* state_name(FrameGraphDebuggerState state) {
    switch (state) {
    case FrameGraphDebuggerState::Unbound: return "Unbound";
    case FrameGraphDebuggerState::Bound: return "Bound";
    case FrameGraphDebuggerState::WaitingFrame: return "Waiting for frame";
    case FrameGraphDebuggerState::Captured: return "Captured";
    case FrameGraphDebuggerState::Suspended: return "Suspended";
    case FrameGraphDebuggerState::Error: return "Error";
    }
    return "Unknown";
}

const char* suspend_reason_name(FrameGraphDebuggerSuspendReason reason) {
    switch (reason) {
    case FrameGraphDebuggerSuspendReason::None: return "none";
    case FrameGraphDebuggerSuspendReason::TargetRemoved: return "target removed";
    case FrameGraphDebuggerSuspendReason::PipelineUnavailable: return "pipeline unavailable";
    case FrameGraphDebuggerSuspendReason::TargetNotRenderable: return "target not renderable";
    }
    return "unknown";
}

tgfx::TextureHandle create_preview_target(
    tgfx::IRenderDevice& device,
    uint32_t width,
    uint32_t height
) {
    tgfx::TextureDesc description;
    description.width = width;
    description.height = height;
    description.format = tgfx::PixelFormat::RGBA8_UNorm;
    description.usage = tgfx::TextureUsage::Sampled |
                        tgfx::TextureUsage::ColorAttachment |
                        tgfx::TextureUsage::CopySrc |
                        tgfx::TextureUsage::CopyDst;
    return device.create_texture(description);
}

} // namespace

FrameGraphDebuggerView::FrameGraphDebuggerView(
    gui_native::TcDocument document,
    FrameGraphDebugger& debugger,
    std::function<void()> request_render
) : FrameGraphDebuggerView(
        document,
        make_local_frame_graph_debugger_source(debugger),
        std::move(request_render)) {}

FrameGraphDebuggerView::FrameGraphDebuggerView(
    gui_native::TcDocument document,
    std::shared_ptr<IFrameGraphDebuggerSource> source,
    std::function<void()> request_render
) : document_(document),
    source_(std::move(source)),
    local_source_(source_),
    request_render_(std::move(request_render)) {
    if (!document_.valid()) {
        throw std::invalid_argument("FrameGraphDebuggerView requires a valid TcDocument");
    }
    if (!source_) {
        throw std::invalid_argument("FrameGraphDebuggerView requires a source");
    }
    build();
}

FrameGraphDebuggerView::~FrameGraphDebuggerView() {
    try {
        close();
    } catch (const std::exception& error) {
        tc_log_error("[framegraph-debugger-view] cleanup failed: %s", error.what());
    } catch (...) {
        tc_log_error("[framegraph-debugger-view] cleanup failed with unknown exception");
    }
}

void FrameGraphDebuggerView::build() {
    DocumentBuilder builder(document_);
    root_ = &builder.make_root<BoxLayout>(
        Orientation::Vertical, "native-framegraph-debugger");
    root_->set_stable_id("editor.framegraph-debugger");
    root_->set_padding(EdgeInsets{5.0f, 5.0f, 5.0f, 5.0f});
    root_->set_spacing(5.0f);
    root_->set_preferred_size(tc_ui_size{1180.0f, 760.0f});

    auto& top = builder.make<BoxLayout>(Orientation::Horizontal, "framegraph-top");
    top.set_stable_id("editor.framegraph.top");
    top.set_spacing(8.0f);
    auto& settings = builder.make<BoxLayout>(
        Orientation::Vertical, "framegraph-settings");
    settings.set_stable_id("editor.framegraph.settings");
    settings.set_spacing(4.0f);

    auto& remote_controls = builder.make<BoxLayout>(
        Orientation::Horizontal, "framegraph-remote-controls");
    remote_controls.set_stable_id("editor.framegraph.remote-controls");
    remote_controls.set_spacing(4.0f);
    remote_port_input_ = &builder.make<TextInput>();
    remote_port_input_->set_stable_id("editor.framegraph.remote-port");
    remote_port_input_->set_placeholder("Port");
    remote_token_input_ = &builder.make<TextInput>();
    remote_token_input_->set_stable_id("editor.framegraph.remote-token");
    remote_token_input_->set_placeholder("Per-launch token");
    auto& connect_remote_button = builder.make<Button>("Connect");
    connect_remote_button.set_stable_id("editor.framegraph.remote-connect");
    auto& disconnect_remote_button = builder.make<Button>("Disconnect");
    disconnect_remote_button.set_stable_id(
        "editor.framegraph.remote-disconnect");
    auto& use_local_button = builder.make<Button>("Use Local");
    use_local_button.set_stable_id("editor.framegraph.use-local");
    remote_controls.add_fixed_child(*remote_port_input_, 70.0f);
    remote_controls.add_stretch_child(*remote_token_input_);
    remote_controls.add_fixed_child(connect_remote_button, 82.0f);
    remote_controls.add_fixed_child(disconnect_remote_button, 92.0f);
    remote_controls.add_fixed_child(use_local_button, 82.0f);
    settings.add_fixed_child(remote_controls, 30.0f);

    target_combo_ = &builder.make<ComboBox>();
    target_combo_->set_stable_id("editor.framegraph.target");
    settings.add_fixed_child(
        labeled_row(builder, "editor.framegraph.target-row", "Target:", *target_combo_),
        30.0f);

    mode_combo_ = &builder.make<ComboBox>();
    mode_combo_->set_stable_id("editor.framegraph.mode");
    mode_combo_->add_item("Passes");
    mode_combo_->add_item("Resources");
    settings.add_fixed_child(
        labeled_row(builder, "editor.framegraph.mode-row", "Mode:", *mode_combo_),
        30.0f);

    inside_panel_ = &builder.make<BoxLayout>(
        Orientation::Vertical, "framegraph-inside-panel");
    inside_panel_->set_stable_id("editor.framegraph.inside");
    inside_panel_->set_spacing(4.0f);
    pass_combo_ = &builder.make<ComboBox>();
    pass_combo_->set_stable_id("editor.framegraph.pass");
    inside_panel_->add_fixed_child(
        labeled_row(builder, "editor.framegraph.pass-row", "Pass:", *pass_combo_),
        30.0f);
    symbol_combo_ = &builder.make<ComboBox>();
    symbol_combo_->set_stable_id("editor.framegraph.symbol");
    inside_panel_->add_fixed_child(
        labeled_row(builder, "editor.framegraph.symbol-row", "Symbol:", *symbol_combo_),
        30.0f);
    pass_json_ = &builder.make<TextArea>();
    pass_json_->set_stable_id("editor.framegraph.pass-json");
    inside_panel_->add_stretch_child(*pass_json_);
    settings.add_stretch_child(*inside_panel_);

    between_panel_ = &builder.make<BoxLayout>(
        Orientation::Vertical, "framegraph-between-panel");
    between_panel_->set_stable_id("editor.framegraph.between");
    between_panel_->set_spacing(4.0f);
    resource_combo_ = &builder.make<ComboBox>();
    resource_combo_->set_stable_id("editor.framegraph.resource");
    between_panel_->add_fixed_child(
        labeled_row(builder, "editor.framegraph.resource-row", "Resource:", *resource_combo_),
        30.0f);

    hdr_check_ = &builder.make<Checkbox>(false);
    hdr_check_->set_stable_id("editor.framegraph.highlight-hdr");
    auto& analyze = builder.make<Button>("Analyze HDR");
    analyze.set_stable_id("editor.framegraph.analyze-hdr");
    auto& hdr_row = builder.make<BoxLayout>(
        Orientation::Horizontal, "framegraph-hdr-row");
    hdr_row.set_stable_id("editor.framegraph.hdr-row");
    hdr_row.set_spacing(4.0f);
    hdr_row.add_stretch_child(*hdr_check_);
    hdr_row.add_fixed_child(analyze, 110.0f);
    between_panel_->add_fixed_child(hdr_row, 30.0f);
    hdr_model_ = std::make_shared<RichTextModel>();
    auto& hdr_view = builder.make<RichTextView>(hdr_model_);
    hdr_view.set_stable_id("editor.framegraph.hdr-results");
    between_panel_->add_stretch_child(hdr_view);
    between_panel_->set_visible(false);
    settings.add_stretch_child(*between_panel_);

    auto& controls = builder.make<BoxLayout>(
        Orientation::Horizontal, "framegraph-controls");
    controls.set_stable_id("editor.framegraph.controls");
    controls.set_spacing(4.0f);
    pause_check_ = &builder.make<Checkbox>(false);
    pause_check_->set_stable_id("editor.framegraph.pause");
    controls.add_fixed_child(*pause_check_, 90.0f);
    channel_combo_ = &builder.make<ComboBox>();
    channel_combo_->set_stable_id("editor.framegraph.channel");
    for (const char* channel : {"RGBA", "R", "G", "B", "A"}) {
        channel_combo_->add_item(channel);
    }
    controls.add_stretch_child(*channel_combo_);
    auto& refresh_stats = builder.make<Button>("Refresh Stats");
    refresh_stats.set_stable_id("editor.framegraph.refresh-stats");
    controls.add_fixed_child(refresh_stats, 110.0f);
    settings.add_fixed_child(controls, 30.0f);
    top.add_fixed_child(settings, 520.0f);

    pipeline_model_ = std::make_shared<RichTextModel>();
    auto& pipeline_view = builder.make<RichTextView>(pipeline_model_);
    pipeline_view.set_stable_id("editor.framegraph.pipeline");
    pipeline_view.set_word_wrap(false);
    pipeline_view.set_placeholder("No pipeline");
    top.add_stretch_child(pipeline_view);
    root_->add_fixed_child(top, 350.0f);

    fbo_model_ = std::make_shared<RichTextModel>();
    auto& fbo_view = builder.make<RichTextView>(fbo_model_);
    fbo_view.set_stable_id("editor.framegraph.capture-info");
    root_->add_fixed_child(fbo_view, 42.0f);

    auto& previews = builder.make<BoxLayout>(
        Orientation::Horizontal, "framegraph-previews");
    previews.set_stable_id("editor.framegraph.previews");
    previews.set_spacing(8.0f);

    auto make_preview = [&](const char* prefix, bool depth) -> Preview {
        auto& panel = builder.make<BoxLayout>(
            Orientation::Vertical, (std::string(prefix) + "-panel").c_str());
        panel.set_stable_id(std::string("editor.framegraph.") + prefix + "-panel");
        panel.set_spacing(4.0f);
        auto& canvas = builder.make<Canvas>();
        canvas.set_stable_id(std::string("editor.framegraph.") + prefix + "-canvas");
        panel.add_stretch_child(canvas);
        auto& view_controls = builder.make<BoxLayout>(
            Orientation::Horizontal, (std::string(prefix) + "-view-controls").c_str());
        view_controls.set_stable_id(
            std::string("editor.framegraph.") + prefix + "-controls");
        view_controls.set_spacing(4.0f);
        auto& fit = builder.make<Button>("Fit");
        fit.set_stable_id(std::string("editor.framegraph.") + prefix + "-fit");
        auto& actual = builder.make<Button>("1:1");
        actual.set_stable_id(std::string("editor.framegraph.") + prefix + "-actual");
        auto& sampling = builder.make<ComboBox>();
        sampling.set_stable_id(
            std::string("editor.framegraph.") + prefix + "-sampling");
        sampling.add_item("Linear");
        sampling.add_item("Nearest");
        sampling.set_selected_index(0);
        view_controls.add_fixed_child(fit, 64.0f);
        view_controls.add_fixed_child(actual, 64.0f);
        view_controls.add_fixed_child(sampling, 92.0f);
        Button* refresh = nullptr;
        if (depth) {
            refresh = &builder.make<Button>("Refresh Depth");
            refresh->set_stable_id("editor.framegraph.depth-refresh");
            view_controls.add_stretch_child(*refresh);
        }
        panel.add_fixed_child(view_controls, 30.0f);
        auto& status = builder.make<StatusBar>(
            "Source: — | Zoom: Fit (100%) | Pixel: —");
        status.set_stable_id(std::string("editor.framegraph.") + prefix + "-status");
        panel.add_fixed_child(status, 24.0f);
        if (depth) {
            depth_read_status_ = &builder.make<StatusBar>("No depth capture");
            depth_read_status_->set_stable_id("editor.framegraph.depth-read-status");
            panel.add_fixed_child(*depth_read_status_, 24.0f);
        }

        Preview preview;
        preview.canvas = &canvas;
        preview.sampling_combo = &sampling;
        preview.status = &status;
        preview.force_depth = depth;
        Preview* destination = depth ? &depth_preview_ : &main_preview_;
        fit.clicked().connect([this, destination](Button&) {
            destination->canvas->fit_in_view();
            refresh_preview_status(*destination);
            request_render();
        });
        actual.clicked().connect([this, destination](Button&) {
            const tc_ui_rect bounds = destination->canvas->bounds();
            destination->canvas->set_zoom(
                1.0f,
                tc_ui_point{
                    bounds.x + bounds.width * 0.5f,
                    bounds.y + bounds.height * 0.5f,
                });
            refresh_preview_status(*destination);
            request_render();
        });
        sampling.changed().connect(
            [this, destination](ComboBox&, int index, const std::string&) {
                if (index < 0) return;
                destination->canvas->set_texture_sampling(
                    index == 1
                        ? TC_UI_TEXTURE_SAMPLING_NEAREST
                        : TC_UI_TEXTURE_SAMPLING_LINEAR);
                request_render();
            });
        canvas.zoom_changed().connect([this, destination](Canvas&, float) {
            refresh_preview_status(*destination);
            request_render();
        });
        canvas.pointer_input().connect(
            [this, destination](Canvas&, tc_ui_point point, const tc_ui_pointer_event&) {
                if (point.x >= 0.0f && point.y >= 0.0f &&
                    point.x < static_cast<float>(destination->width) &&
                    point.y < static_cast<float>(destination->height)) {
                    destination->has_cursor = true;
                    destination->cursor_x = static_cast<int>(point.x);
                    destination->cursor_y = static_cast<int>(point.y);
                } else {
                    destination->has_cursor = false;
                }
                refresh_preview_status(*destination);
                request_render();
            });
        if (refresh) {
            refresh->clicked().connect([this](Button&) {
                if (!preview_device_) {
                    depth_read_status_->set_text("No active graphics device");
                } else {
                    refresh_depth(*preview_device_);
                }
                request_render();
            });
        }
        if (depth) {
            previews.add_fixed_child(panel, 320.0f);
        } else {
            previews.add_stretch_child(panel);
        }
        return preview;
    };

    main_preview_ = make_preview("main", false);
    depth_preview_ = make_preview("depth", true);
    root_->add_stretch_child(previews);

    state_status_ = &builder.make<StatusBar>("Unbound");
    state_status_->set_stable_id("editor.framegraph.state");
    root_->add_fixed_child(*state_status_, 24.0f);
    stats_bar_ = &builder.make<StatusBar>("Render stats");
    stats_bar_->set_stable_id("editor.framegraph.stats");
    root_->add_fixed_child(*stats_bar_, 24.0f);
    timing_bar_ = &builder.make<StatusBar>("Timing: no selection");
    timing_bar_->set_stable_id("editor.framegraph.timing");
    root_->add_fixed_child(*timing_bar_, 24.0f);

    target_combo_->changed().connect([this](ComboBox&, int index, const std::string&) {
        if (updating_ || index < 0) return;
        const auto snapshot = source_->snapshot();
        if (static_cast<size_t>(index) >= snapshot->targets.size() ||
            !source_->select_target(snapshot->targets[static_cast<size_t>(index)].id)) {
            tc_log_error(
                "[framegraph-debugger-view] failed to select target at index %d", index);
            return;
        }
        select_initial_values();
        refresh_lists();
        refresh_selection();
        refresh_info();
    });
    mode_combo_->changed().connect([this](ComboBox&, int index, const std::string&) {
        if (!updating_) {
            source_->set_mode(index == 0
                ? FrameGraphDebuggerMode::InsidePass
                : FrameGraphDebuggerMode::BetweenPasses);
            refresh_selection();
            refresh_lists();
            refresh_info();
        }
    });
    pass_combo_->changed().connect([this](ComboBox&, int index, const std::string&) {
        if (!updating_ && index >= 0 && static_cast<size_t>(index) < pass_indices_.size()) {
            const auto snapshot = source_->snapshot();
            if (static_cast<size_t>(index) < snapshot->passes.size()) {
                source_->select_pass(snapshot->passes[static_cast<size_t>(index)].id);
            }
            refresh_lists();
            refresh_info();
        }
    });
    symbol_combo_->changed().connect([this](ComboBox&, int, const std::string& text) {
        if (!updating_) {
            source_->set_selected_symbol(text);
            refresh_info();
        }
    });
    resource_combo_->changed().connect([this](ComboBox&, int, const std::string& text) {
        if (!updating_ && !text.empty()) {
            source_->set_selected_resource(text);
            refresh_info();
        }
    });
    channel_combo_->changed().connect([this](ComboBox&, int index, const std::string&) {
        if (!updating_) {
            source_->set_channel_mode(index);
            request_render();
        }
    });
    pause_check_->changed().connect([this](Checkbox&, bool checked) {
        if (!updating_) {
            source_->set_paused(checked);
            refresh_info();
        }
    });
    hdr_check_->changed().connect([this](Checkbox&, bool checked) {
        if (!updating_) {
            source_->set_highlight_hdr(checked);
            request_render();
        }
    });
    analyze.clicked().connect([this](Button&) {
        hdr_model_->set_html(source_->analyze_hdr());
        request_render();
    });
    refresh_stats.clicked().connect([this](Button&) {
        refresh_info();
    });
    connect_remote_button.clicked().connect([this](Button&) {
        const std::string& port_text = remote_port_input_->text();
        unsigned port = 0;
        const auto parsed = std::from_chars(
            port_text.data(), port_text.data() + port_text.size(), port);
        if (parsed.ec != std::errc{} ||
            parsed.ptr != port_text.data() + port_text.size() ||
            port == 0 || port > 65535) {
            state_status_->set_text("Remote: invalid loopback port");
            tc_log_error(
                "[framegraph-debugger-view] invalid remote port '%s'",
                port_text.c_str());
            request_render();
            return;
        }
        connect_remote(
            static_cast<std::uint16_t>(port), remote_token_input_->text());
    });
    disconnect_remote_button.clicked().connect([this](Button&) {
        disconnect_remote();
    });
    use_local_button.clicked().connect([this](Button&) { use_local(); });
}

bool FrameGraphDebuggerView::activate() {
    require_open();
    if (active_) return false;
    active_ = true;
    source_->connect();
    source_->refresh();
    select_initial_values();
    refresh_lists();
    refresh_selection();
    refresh_info();
    return true;
}

void FrameGraphDebuggerView::deactivate() {
    if (!active_) return;
    active_ = false;
    source_->disconnect();
    release_previews();
}

bool FrameGraphDebuggerView::update() {
    require_open();
    if (!active_) return false;
    source_->finish_frame();
    source_->refresh();
    select_initial_values();
    refresh_lists();
    refresh_selection();
    refresh_info();
    return true;
}

bool FrameGraphDebuggerView::show_resource(const std::string& resource) {
    require_open();
    const auto snapshot = source_->snapshot();
    const auto& resources = snapshot->resources;
    if (std::find(resources.begin(), resources.end(), resource) == resources.end()) {
        tc_log_error(
            "[framegraph-debugger-view] cannot select missing resource '%s'",
            resource.c_str());
        return false;
    }
    source_->set_mode(FrameGraphDebuggerMode::BetweenPasses);
    source_->set_selected_resource(resource);
    refresh_lists();
    refresh_selection();
    refresh_info();
    return true;
}

bool FrameGraphDebuggerView::connect_remote(
    std::uint16_t port,
    std::string authentication_token
) {
    require_open();
    if (port == 0 || authentication_token.empty()) {
        tc_log_error(
            "[framegraph-debugger-view] remote port and token are required");
        return false;
    }
    auto remote = std::make_shared<RemoteFrameGraphDebuggerSource>();
    RemoteFrameGraphConnectionConfig config;
    config.port = port;
    config.authentication_token = std::move(authentication_token);
    if (!remote->connect(std::move(config))) {
        tc_log_error(
            "[framegraph-debugger-view] failed to start remote source");
        return false;
    }
    remote_source_ = std::move(remote);
    switch_source(remote_source_, false);
    return true;
}

void FrameGraphDebuggerView::disconnect_remote() {
    require_open();
    if (!remote_source_) return;
    remote_source_->disconnect();
    if (using_remote()) {
        refresh_lists();
        refresh_selection();
        refresh_info();
    }
}

bool FrameGraphDebuggerView::use_local() {
    require_open();
    if (!local_source_ || source_ == local_source_) return false;
    if (remote_source_) remote_source_->disconnect();
    switch_source(local_source_, active_);
    return true;
}

bool FrameGraphDebuggerView::using_remote() const {
    return remote_source_ && source_ == remote_source_;
}

std::shared_ptr<const FrameGraphDebuggerSnapshot>
FrameGraphDebuggerView::source_snapshot() const {
    return source_->snapshot();
}

void FrameGraphDebuggerView::switch_source(
    std::shared_ptr<IFrameGraphDebuggerSource> source,
    bool connect_source
) {
    if (!source || source == source_) return;
    source_->disconnect();
    release_previews();
    source_ = std::move(source);
    if (active_ && connect_source) source_->connect();
    source_->refresh();
    select_initial_values();
    refresh_lists();
    refresh_selection();
    refresh_info();
}

void FrameGraphDebuggerView::select_initial_values() {
    auto snapshot = source_->snapshot();
    if (!snapshot->selected_target_id && !snapshot->targets.empty() &&
        !source_->select_target(snapshot->targets.front().id)) {
        tc_log_error(
            "[framegraph-debugger-view] failed to select initial target '%s'",
            snapshot->targets.front().label.c_str());
    }
    snapshot = source_->snapshot();
    if (!snapshot->selected_pass_id && !snapshot->passes.empty()) {
        source_->select_pass(snapshot->passes.front().id);
    }
    snapshot = source_->snapshot();
    if (snapshot->selected_resource.empty() && !snapshot->resources.empty()) {
        source_->set_selected_resource(snapshot->resources.front());
    }
}

void FrameGraphDebuggerView::refresh_lists() {
    const auto snapshot = source_->snapshot();
    updating_ = true;
    target_combo_->clear_items();
    int selected_target = -1;
    for (size_t index = 0; index < snapshot->targets.size(); ++index) {
        const auto& target = snapshot->targets[index];
        target_combo_->add_item(target.label);
        if (snapshot->selected_target_id == target.id) {
            selected_target = static_cast<int>(index);
        }
    }
    target_combo_->set_selected_index(selected_target);

    resource_combo_->clear_items();
    int resource_index = -1;
    for (size_t index = 0; index < snapshot->resources.size(); ++index) {
        resource_combo_->add_item(snapshot->resources[index]);
        if (snapshot->resources[index] == snapshot->selected_resource) {
            resource_index = static_cast<int>(index);
        }
    }
    resource_combo_->set_selected_index(resource_index);

    pass_combo_->clear_items();
    pass_indices_.clear();
    int selected_pass = -1;
    for (size_t row = 0; row < snapshot->passes.size(); ++row) {
        pass_combo_->add_item(snapshot->passes[row].display_name());
        pass_indices_.push_back(snapshot->passes[row].authored_index);
        if (snapshot->selected_pass_id == snapshot->passes[row].id) {
            selected_pass = static_cast<int>(row);
        }
    }
    pass_combo_->set_selected_index(selected_pass);

    symbol_combo_->clear_items();
    int symbol_index = -1;
    for (size_t index = 0; index < snapshot->symbols.size(); ++index) {
        symbol_combo_->add_item(snapshot->symbols[index]);
        if (snapshot->symbols[index] == snapshot->selected_symbol) {
            symbol_index = static_cast<int>(index);
        }
    }
    symbol_combo_->set_selected_index(symbol_index);
    updating_ = false;
    request_render();
}

void FrameGraphDebuggerView::refresh_selection() {
    const auto snapshot = source_->snapshot();
    updating_ = true;
    mode_combo_->set_selected_index(
        snapshot->mode == FrameGraphDebuggerMode::InsidePass ? 0 : 1);
    channel_combo_->set_selected_index(snapshot->channel_mode);
    pause_check_->set_checked(snapshot->paused);
    hdr_check_->set_checked(snapshot->highlight_hdr);
    inside_panel_->set_visible(snapshot->mode == FrameGraphDebuggerMode::InsidePass);
    between_panel_->set_visible(snapshot->mode == FrameGraphDebuggerMode::BetweenPasses);
    updating_ = false;
    request_render();
}

void FrameGraphDebuggerView::refresh_info() {
    const auto snapshot = source_->snapshot();
    fbo_model_->set_html(snapshot->capture_info);
    pipeline_model_->set_html(snapshot->pipeline_info);
    pass_json_->set_text(snapshot->pass_json);
    stats_bar_->set_text(snapshot->render_stats);
    const std::string& timing = snapshot->timing;
    timing_bar_->set_text(timing.empty() ? "Timing: no selection" : timing);
    std::string state;
    if (snapshot->source_kind == FrameGraphDebuggerSourceKind::Remote) {
        state = snapshot->source_label + " | ";
    }
    state += state_name(snapshot->state);
    if (snapshot->source_kind == FrameGraphDebuggerSourceKind::Remote &&
        snapshot->stale) {
        state += " [STALE]";
    }
    if (snapshot->state == FrameGraphDebuggerState::Suspended) {
        state += ": ";
        state += suspend_reason_name(snapshot->suspend_reason);
    } else if (!snapshot->status_detail.empty()) {
        state += ": ";
        state += snapshot->status_detail;
    }
    if (snapshot->dropped_messages != 0) {
        state += " | dropped=";
        state += std::to_string(snapshot->dropped_messages);
    }
    state_status_->set_text(std::move(state));
    request_render();
}

bool FrameGraphDebuggerView::render_previews(tgfx::RenderContext2& context) {
    require_open();
    if (!active_) return false;
    preview_device_ = &context.device();
    const bool main_ready = render_preview(context, main_preview_);
    const bool depth_ready = render_preview(context, depth_preview_);
    return main_ready || depth_ready;
}

bool FrameGraphDebuggerView::render_preview(
    tgfx::RenderContext2& context,
    Preview& preview
) {
    const auto snapshot = source_->snapshot();
    const auto& image = preview.force_depth
        ? snapshot->depth_image
        : snapshot->main_image;
    if (!image.available || image.width == 0 || image.height == 0) {
        if (preview.ready) preview.canvas->clear_texture();
        preview.ready = false;
        preview.has_cursor = false;
        refresh_preview_status(preview);
        return false;
    }

    const uint32_t width = image.width;
    const uint32_t height = image.height;
    if (!preview.target || preview.width != width || preview.height != height) {
        release_preview(preview);
        preview_device_ = &context.device();
        preview.target = create_preview_target(context.device(), width, height);
        if (!preview.target) {
            tc_log_error(
                "[framegraph-debugger-view] failed to create %ux%u preview target",
                width, height);
            return false;
        }
        preview.width = width;
        preview.height = height;
        preview.canvas->set_texture(
            preview.target.id,
            tc_ui_size{static_cast<float>(width), static_cast<float>(height)});
    }

    const bool rendered = source_->render_image(
        context,
        preview.target,
        preview.force_depth
            ? FrameGraphDebuggerImageKind::Depth
            : FrameGraphDebuggerImageKind::Main,
        width,
        height,
        preview.force_depth ? 5 : snapshot->channel_mode,
        preview.force_depth ? false : snapshot->highlight_hdr);
    if (!rendered) {
        tc_log_error("[framegraph-debugger-view] source failed to render preview");
        return false;
    }
    const bool changed = !preview.ready;
    preview.ready = true;
    refresh_preview_status(preview);
    if (changed) request_render();
    return true;
}

std::string FrameGraphDebuggerView::refresh_depth(tgfx::IRenderDevice& device) {
    require_open();
    const auto snapshot = source_->snapshot();
    std::string text;
    if (!snapshot->depth_image.available) {
        text = "No depth capture";
    } else {
        int width = 0;
        int height = 0;
        const auto pixels = source_->read_depth_normalized(
            device, &width, &height);
        text = pixels.empty()
            ? "No depth data"
            : "Depth: " + std::to_string(width) + "x" +
              std::to_string(height) + " read OK";
    }
    depth_read_status_->set_text(text);
    request_render();
    return text;
}

void FrameGraphDebuggerView::refresh_preview_status(Preview& preview) {
    std::ostringstream text;
    text << "Source: ";
    if (preview.width > 0 && preview.height > 0) {
        text << preview.width << "x" << preview.height;
    } else {
        text << "—";
    }
    text << " | Zoom: ";
    if (preview.canvas->fit_mode()) {
        text << "Fit (" << static_cast<int>(preview.canvas->zoom() * 100.0f) << "%)";
    } else {
        text << static_cast<int>(preview.canvas->zoom() * 100.0f) << "%";
    }
    text << " | Pixel: ";
    if (preview.has_cursor) {
        text << preview.cursor_x << ", " << preview.cursor_y;
    } else {
        text << "—";
    }
    preview.status->set_text(text.str());
}

void FrameGraphDebuggerView::release_preview(Preview& preview) {
    if (preview.canvas && preview.ready) {
        preview.canvas->clear_texture();
    }
    if (preview.target && preview_device_) {
        preview_device_->destroy(preview.target);
    }
    preview.target = {};
    preview.width = 0;
    preview.height = 0;
    preview.ready = false;
    preview.has_cursor = false;
    if (preview.canvas && preview.status) refresh_preview_status(preview);
}

void FrameGraphDebuggerView::release_previews() {
    release_preview(main_preview_);
    release_preview(depth_preview_);
    preview_device_ = nullptr;
}

void FrameGraphDebuggerView::close() {
    if (closed_) return;
    deactivate();
    source_->close();
    if (remote_source_ && remote_source_ != source_) remote_source_->close();
    if (local_source_ && local_source_ != source_) local_source_->close();
    closed_ = true;
    if (document_.valid() && root_ &&
        tc_ui_document_is_alive(document_.handle(), root_->handle())) {
        if (!tc_ui_document_destroy_widget_recursive(document_.handle(), root_->handle())) {
            tc_log_error("[framegraph-debugger-view] failed to destroy widget tree");
        }
    }
    root_ = nullptr;
}

void FrameGraphDebuggerView::request_render() {
    if (request_render_) request_render_();
}

void FrameGraphDebuggerView::require_open() const {
    if (closed_) throw std::logic_error("FrameGraphDebuggerView is closed");
    if (!document_.valid()) {
        throw std::logic_error("FrameGraphDebuggerView document is no longer valid");
    }
}

tc_widget_handle FrameGraphDebuggerView::root_handle() const {
    return root_ ? root_->handle() : tc_widget_handle_invalid();
}

gui_native::Widget* FrameGraphDebuggerView::root_widget() const {
    return root_;
}

} // namespace termin
