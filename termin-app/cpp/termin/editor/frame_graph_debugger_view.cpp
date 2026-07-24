#include "termin/editor/frame_graph_debugger_view.hpp"

#include <algorithm>
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
#include <termin/render/frame_graph_debugger.hpp>
#include <termin/render/frame_graph_capture.hpp>
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
) : document_(document),
    debugger_(&debugger),
    request_render_(std::move(request_render)) {
    if (!document_.valid()) {
        throw std::invalid_argument("FrameGraphDebuggerView requires a valid TcDocument");
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
    root_->add_fixed_child(top, 320.0f);

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
        view_controls.add_fixed_child(fit, 64.0f);
        view_controls.add_fixed_child(actual, 64.0f);
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
        if (!debugger_->select_target_at(static_cast<size_t>(index))) {
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
            debugger_->set_mode(index == 0
                ? FrameGraphDebuggerMode::InsidePass
                : FrameGraphDebuggerMode::BetweenPasses);
            refresh_selection();
            refresh_lists();
            refresh_info();
        }
    });
    pass_combo_->changed().connect([this](ComboBox&, int index, const std::string&) {
        if (!updating_ && index >= 0 && static_cast<size_t>(index) < pass_indices_.size()) {
            debugger_->set_selected_pass(pass_indices_[static_cast<size_t>(index)]);
            refresh_lists();
            refresh_info();
        }
    });
    symbol_combo_->changed().connect([this](ComboBox&, int, const std::string& text) {
        if (!updating_) {
            debugger_->set_selected_symbol(text);
            refresh_info();
        }
    });
    resource_combo_->changed().connect([this](ComboBox&, int, const std::string& text) {
        if (!updating_ && !text.empty()) {
            debugger_->set_selected_resource(text);
            refresh_info();
        }
    });
    channel_combo_->changed().connect([this](ComboBox&, int index, const std::string&) {
        if (!updating_) {
            debugger_->set_channel_mode(index);
            request_render();
        }
    });
    pause_check_->changed().connect([this](Checkbox&, bool checked) {
        if (!updating_) {
            debugger_->set_paused(checked);
            refresh_info();
        }
    });
    hdr_check_->changed().connect([this](Checkbox&, bool checked) {
        if (!updating_) {
            debugger_->set_highlight_hdr(checked);
            request_render();
        }
    });
    analyze.clicked().connect([this](Button&) {
        hdr_model_->set_html(debugger_->analyze_hdr());
        request_render();
    });
    refresh_stats.clicked().connect([this](Button&) {
        refresh_info();
    });
}

bool FrameGraphDebuggerView::activate() {
    require_open();
    if (active_) return false;
    active_ = true;
    debugger_->refresh();
    select_initial_values();
    debugger_->connect();
    refresh_lists();
    refresh_selection();
    refresh_info();
    return true;
}

void FrameGraphDebuggerView::deactivate() {
    if (!active_) return;
    active_ = false;
    debugger_->disconnect();
    release_previews();
}

bool FrameGraphDebuggerView::update() {
    require_open();
    if (!active_) return false;
    debugger_->finish_frame();
    debugger_->refresh();
    refresh_lists();
    refresh_selection();
    refresh_info();
    return true;
}

bool FrameGraphDebuggerView::show_resource(const std::string& resource) {
    require_open();
    const std::vector<std::string> resources = debugger_->resources();
    if (std::find(resources.begin(), resources.end(), resource) == resources.end()) {
        tc_log_error(
            "[framegraph-debugger-view] cannot select missing resource '%s'",
            resource.c_str());
        return false;
    }
    debugger_->set_mode(FrameGraphDebuggerMode::BetweenPasses);
    debugger_->set_selected_resource(resource);
    refresh_lists();
    refresh_selection();
    refresh_info();
    return true;
}

void FrameGraphDebuggerView::select_initial_values() {
    const auto& targets = debugger_->targets();
    if (!debugger_->selected_target_index() && !targets.empty() &&
        !debugger_->select_target_at(0)) {
        tc_log_error(
            "[framegraph-debugger-view] failed to select initial target '%s'",
            targets.front().label.c_str());
    }
    const auto passes = debugger_->passes();
    if (!debugger_->selected_pass_index() && !passes.empty()) {
        debugger_->set_selected_pass(passes.front().index);
    }
    const auto resources = debugger_->resources();
    if (debugger_->selected_resource().empty() && !resources.empty()) {
        debugger_->set_selected_resource(resources.front());
    }
}

void FrameGraphDebuggerView::refresh_lists() {
    updating_ = true;
    target_combo_->clear_items();
    for (const auto& target : debugger_->targets()) {
        target_combo_->add_item(target.label);
    }
    target_combo_->set_selected_index(
        debugger_->selected_target_index()
            ? static_cast<int>(*debugger_->selected_target_index())
            : -1);

    resource_combo_->clear_items();
    const auto resources = debugger_->resources();
    int resource_index = -1;
    for (size_t index = 0; index < resources.size(); ++index) {
        resource_combo_->add_item(resources[index]);
        if (resources[index] == debugger_->selected_resource()) {
            resource_index = static_cast<int>(index);
        }
    }
    resource_combo_->set_selected_index(resource_index);

    pass_combo_->clear_items();
    pass_indices_.clear();
    int selected_pass = -1;
    const auto passes = debugger_->passes();
    for (size_t row = 0; row < passes.size(); ++row) {
        pass_combo_->add_item(passes[row].display_name());
        pass_indices_.push_back(passes[row].index);
        if (debugger_->selected_pass_index() == passes[row].index) {
            selected_pass = static_cast<int>(row);
        }
    }
    pass_combo_->set_selected_index(selected_pass);

    symbol_combo_->clear_items();
    const auto symbols = debugger_->symbols();
    int symbol_index = -1;
    for (size_t index = 0; index < symbols.size(); ++index) {
        symbol_combo_->add_item(symbols[index]);
        if (symbols[index] == debugger_->selected_symbol()) {
            symbol_index = static_cast<int>(index);
        }
    }
    symbol_combo_->set_selected_index(symbol_index);
    updating_ = false;
    request_render();
}

void FrameGraphDebuggerView::refresh_selection() {
    updating_ = true;
    mode_combo_->set_selected_index(
        debugger_->mode() == FrameGraphDebuggerMode::InsidePass ? 0 : 1);
    channel_combo_->set_selected_index(debugger_->channel_mode());
    pause_check_->set_checked(debugger_->paused());
    hdr_check_->set_checked(debugger_->highlight_hdr());
    inside_panel_->set_visible(debugger_->mode() == FrameGraphDebuggerMode::InsidePass);
    between_panel_->set_visible(debugger_->mode() == FrameGraphDebuggerMode::BetweenPasses);
    updating_ = false;
    request_render();
}

void FrameGraphDebuggerView::refresh_info() {
    fbo_model_->set_html(debugger_->format_capture_info());
    pipeline_model_->set_html(debugger_->format_pipeline_info());
    pass_json_->set_text(debugger_->format_pass_json());
    stats_bar_->set_text(debugger_->format_render_stats());
    const std::string timing = debugger_->format_timing();
    timing_bar_->set_text(timing.empty() ? "Timing: no selection" : timing);
    std::string state = state_name(debugger_->state());
    if (debugger_->state() == FrameGraphDebuggerState::Suspended) {
        state += ": ";
        state += suspend_reason_name(debugger_->suspend_reason());
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
    FrameGraphCapture& capture = preview.force_depth
        ? debugger_->depth_capture()
        : debugger_->capture();
    if (!capture.has_capture() || !capture.capture_tex() ||
        capture.width() <= 0 || capture.height() <= 0) {
        if (preview.ready) preview.canvas->clear_texture();
        preview.ready = false;
        preview.has_cursor = false;
        refresh_preview_status(preview);
        return false;
    }

    const uint32_t width = static_cast<uint32_t>(capture.width());
    const uint32_t height = static_cast<uint32_t>(capture.height());
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

    FrameGraphPresenterDraw draw;
    draw.capture_tex = capture.capture_tex();
    draw.dst_rect = Rect2i{0, 0, static_cast<int>(width), static_cast<int>(height)};
    draw.options.channel_mode = preview.force_depth ? 5 : debugger_->channel_mode();
    draw.options.highlight_hdr = preview.force_depth ? false : debugger_->highlight_hdr();
    debugger_->presenter().render(&context, preview.target, draw);
    const bool changed = !preview.ready;
    preview.ready = true;
    refresh_preview_status(preview);
    if (changed) request_render();
    return true;
}

std::string FrameGraphDebuggerView::refresh_depth(tgfx::IRenderDevice& device) {
    require_open();
    FrameGraphCapture& capture = debugger_->depth_capture();
    std::string text;
    if (!capture.has_capture() || !capture.capture_tex()) {
        text = "No depth capture";
    } else {
        int width = 0;
        int height = 0;
        const auto pixels = debugger_->presenter().read_depth_normalized(
            &device, capture.capture_tex(), &width, &height);
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
