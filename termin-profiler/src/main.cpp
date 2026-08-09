#include <algorithm>
#include <charconv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <filesystem>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>
#include <vector>

#include <termin/gui_native/document_builder.hpp>
#include <termin/gui_native/tc_ui_document.h>
#include <termin/gui_native/widgets.hpp>
#include <termin/gui_native/window_adapter.hpp>
#include <termin/platform/backend_window.hpp>
#include <termin/profiler_app/android_bridge.hpp>
#include <termin/profiler_app/session.hpp>
#include <termin/window/window_manager.hpp>

#include <tgfx2/standalone_shader_runtime.hpp>

namespace fs = std::filesystem;
namespace ui = termin::gui_native;

namespace {

    struct Options {
        std::optional<std::size_t> frame_limit;
    };

    Options parse_options(int argc, char** argv) {
        Options options;
        if (const char* configured = std::getenv("TERMIN_PROFILER_RENDER_COUNT"); configured && configured[0]) {
            std::size_t count = 0;
            const std::string_view value(configured);
            const auto parsed = std::from_chars(value.data(), value.data() + value.size(), count);
            if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size() || count == 0) {
                throw std::runtime_error("TERMIN_PROFILER_RENDER_COUNT expects a positive integer");
            }
            options.frame_limit = count;
        }
        for (int index = 1; index < argc; ++index) {
            const std::string_view argument(argv[index]);
            if (argument == "--help" || argument == "-h") {
                std::puts("Usage: termin_profiler [--render-count COUNT]");
                std::exit(0);
            }
            if (argument != "--render-count" || index + 1 >= argc) {
                throw std::runtime_error("usage: termin_profiler [--render-count COUNT]");
            }
            std::size_t count = 0;
            const std::string_view value(argv[++index]);
            const auto parsed = std::from_chars(value.data(), value.data() + value.size(), count);
            if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size() || count == 0) {
                throw std::runtime_error("--render-count expects a positive integer");
            }
            options.frame_limit = count;
        }
        return options;
    }

    std::string resolve_font_path(const char* executable) {
        if (const char* configured = std::getenv("TERMIN_UI_FONT"); configured && configured[0]) {
            return configured;
        }

        std::vector<fs::path> candidates;
        if (const char* sdk = std::getenv("TERMIN_SDK"); sdk && sdk[0]) {
            candidates.emplace_back(fs::path(sdk) / "share" / "termin" / "fonts" / "DroidSans.ttf");
        }
        std::error_code error;
        const fs::path executable_path = fs::absolute(executable ? executable : "termin_profiler", error);
        if (!error) {
            candidates.emplace_back(executable_path.parent_path().parent_path() / "share" / "termin" / "fonts" /
                                    "DroidSans.ttf");
            candidates.emplace_back(executable_path.parent_path().parent_path().parent_path() / "sdk" / "share" /
                                    "termin" / "fonts" / "DroidSans.ttf");
        }
        candidates.emplace_back(fs::path("sdk/share/termin/fonts/DroidSans.ttf"));
        candidates.emplace_back(fs::path("/usr/local/share/termin/fonts/DroidSans.ttf"));
        for (const fs::path& candidate : candidates) {
            if (fs::is_regular_file(candidate)) {
                return candidate.string();
            }
        }
        throw std::runtime_error("cannot find UI font; set TERMIN_UI_FONT or TERMIN_SDK");
    }

    class ProfilerApplication {
    public:
        explicit ProfilerApplication(const char* executable)
            : graphics_(termin::create_native_windowed_graphics()),
              windows_(std::make_unique<termin::WindowManager>(*graphics_)),
              window_(windows_->create_window(termin::WindowConfig{"Termin Remote Profiler", 1180, 860})),
              document_handle_(tc_ui_document_create()),
              document_(document_handle_) {
            if (!tgfx::configure_default_standalone_shader_runtime(graphics_->graphics(), "termin-profiler")) {
                throw std::runtime_error("standalone shader runtime configuration failed");
            }
            ui::DocumentRendererConfig renderer;
            renderer.font_path = resolve_font_path(executable);
            renderer.font_size = 15;
            renderer.clear_color = {0.025f, 0.03f, 0.04f, 1.0f};
            adapter_ = std::make_unique<ui::GuiWindowAdapter>(
                graphics_->graphics(), document_, renderer, windows_->window(window_));
            build_interface();
            android_bridge_.refresh_devices();
        }

        ~ProfilerApplication() {
            profiler_.close();
            android_bridge_.close();
            if (adapter_) {
                adapter_->wait_idle();
                adapter_->close();
                adapter_.reset();
            }
            if (document_.valid()) {
                tc_ui_document_destroy(document_.handle());
            }
            if (windows_) {
                windows_->close();
                windows_.reset();
            }
            if (graphics_) {
                graphics_->close();
            }
        }

        int run(std::optional<std::size_t> frame_limit) {
            while (!windows_->window(window_).should_close() &&
                   (!frame_limit || adapter_->renderer().rendered_frame_count() < *frame_limit)) {
                windows_->pump_events();
                adapter_->consume_events(windows_->take_events(window_));
                sync_android_bridge();
                if (profiler_.update()) {
                    sync_selection();
                }
                if (!adapter_->render_and_present()) {
                    break;
                }
            }
            adapter_->wait_idle();
            return 0;
        }

    private:
        void build_interface() {
            ui::DocumentBuilder builder(document_);
            auto& root = builder.make_root<ui::VStack>("standalone-profiler-root");
            root.set_padding({8.0f, 8.0f, 8.0f, 8.0f}).set_spacing(6.0f).set_background({0.025f, 0.03f, 0.04f, 1.0f});

            auto& android_target = builder.make<ui::HStack>("android-profiler-target");
            android_target.set_spacing(5.0f);
            auto& android_label = builder.make<ui::Label>("Android / Quest");
            device_combo_ = &builder.make<ui::ComboBox>();
            auto& refresh_devices = builder.make<ui::Button>("Refresh Devices");
            package_input_ = &builder.make<ui::TextInput>("org.termin.openxr");
            package_input_->set_placeholder("application id");
            activity_input_ = &builder.make<ui::TextInput>("android.app.NativeActivity");
            activity_input_->set_placeholder("activity class");
            android_target.add_fixed_child(android_label, 118.0f);
            android_target.add_stretch_child(*device_combo_);
            android_target.add_fixed_child(refresh_devices, 126.0f);
            android_target.add_stretch_child(*package_input_);
            android_target.add_stretch_child(*activity_input_);
            root.add_fixed_child(android_target, 34.0f);

            auto& android_actions = builder.make<ui::HStack>("android-profiler-actions");
            android_actions.set_spacing(5.0f);
            auto& android_hint = builder.make<ui::Label>(
                "Launches the app with profiling and creates a private ADB route automatically.");
            auto& connect_android = builder.make<ui::Button>("Connect Quest");
            auto& disconnect_android = builder.make<ui::Button>("Disconnect Quest");
            android_actions.add_stretch_child(android_hint);
            android_actions.add_fixed_child(connect_android, 112.0f);
            android_actions.add_fixed_child(disconnect_android, 128.0f);
            root.add_fixed_child(android_actions, 34.0f);

            android_status_model_ = std::make_shared<ui::RichTextModel>();
            android_status_model_->set_text(android_bridge_.snapshot().status);
            auto& android_status = builder.make<ui::RichTextView>(android_status_model_);
            android_status.set_show_scrollbar(false);
            root.add_fixed_child(android_status, 26.0f);

            auto& connection = builder.make<ui::HStack>("profiler-connection");
            connection.set_spacing(5.0f);
            auto& route_label = builder.make<ui::Label>("Manual (advanced)");
            auto& host_label = builder.make<ui::Label>("127.0.0.1");
            port_input_ = &builder.make<ui::TextInput>("46051");
            token_input_ = &builder.make<ui::TextInput>();
            token_input_->set_placeholder("per-launch token (not persisted)");
            auto& connect = builder.make<ui::Button>("Connect");
            auto& disconnect = builder.make<ui::Button>("Disconnect");
            connection.add_fixed_child(route_label, 126.0f);
            connection.add_fixed_child(host_label, 86.0f);
            connection.add_fixed_child(*port_input_, 78.0f);
            connection.add_stretch_child(*token_input_);
            connection.add_fixed_child(connect, 88.0f);
            connection.add_fixed_child(disconnect, 96.0f);
            root.add_fixed_child(connection, 34.0f);

            auto& connection_status = builder.make<ui::RichTextView>(profiler_.connection_model());
            connection_status.set_show_scrollbar(false);
            root.add_fixed_child(connection_status, 26.0f);

            termin::FrameProfilerController& controller = profiler_.profiler();
            auto& toolbar = builder.make<ui::ToolBar>(controller.command_model());
            root.add_fixed_child(toolbar, 34.0f);

            auto& summary = builder.make<ui::RichTextView>(controller.summary_model());
            summary.set_show_scrollbar(false);
            root.add_fixed_child(summary, 26.0f);

            gpu_summary_ = &builder.make<ui::RichTextView>(profiler_.gpu_summary_model());
            gpu_summary_->set_show_scrollbar(false);
            root.add_fixed_child(*gpu_summary_, 26.0f);

            timeline_legend_model_ = std::make_shared<ui::RichTextModel>();
            const auto legend_segment = [](std::string text, tc_ui_srgb_color color, bool bold, bool italic) {
                ui::RichTextStyle style;
                style.color = color;
                style.bold = bold;
                style.italic = italic;
                return ui::RichTextSegment{std::move(text), std::move(style)};
            };
            ui::RichTextLine timeline_legend_line;
            timeline_legend_line.push_back(
                legend_segment("Cadence interval", {0.35f, 0.67f, 0.83f, 1.0f}, true, false));
            timeline_legend_line.push_back(
                legend_segment("  |  Cadence hitch (not GPU)", {0.82f, 0.27f, 0.24f, 1.0f}, true, false));
            timeline_legend_line.push_back(legend_segment("  |  CPU active", {0.34f, 0.78f, 0.38f, 1.0f}, true, false));
            timeline_legend_line.push_back(
                legend_segment("  |  GPU duration", {0.72f, 0.42f, 0.95f, 1.0f}, true, false));
            timeline_legend_line.push_back(
                legend_segment("  |  GPU unavailable", {0.58f, 0.60f, 0.66f, 1.0f}, false, true));
            timeline_legend_model_->set_lines({std::move(timeline_legend_line)});
            auto& timeline_legend = builder.make<ui::RichTextView>(timeline_legend_model_);
            timeline_legend.set_show_scrollbar(false);
            root.add_fixed_child(timeline_legend, 26.0f);

            timeline_ = &builder.make<ui::FrameTimelineWidget>(controller.timeline_model());
            timeline_->set_window_size(180);
            timeline_->set_warning_ratio(static_cast<float>(controller.hitch_ratio()));
            root.add_fixed_child(*timeline_, 190.0f);

            gpu_timeline_ = &builder.make<ui::Canvas>();
            gpu_timeline_->set_paint_callback(
                [this](ui::Canvas& canvas, tc_ui_paint_context* context) { paint_gpu_timeline(canvas, context); });
            root.add_fixed_child(*gpu_timeline_, 92.0f);

            gpu_detail_ = &builder.make<ui::RichTextView>(profiler_.gpu_detail_model());
            gpu_detail_->set_show_scrollbar(false);
            root.add_fixed_child(*gpu_detail_, 26.0f);

            columns_ = std::make_shared<ui::TableColumnModel>();
            columns_->set_columns({
                {"section", "Section", ui::TableColumnPolicy::Stretch, 0.0f, 180.0f},
                {"inclusive", "Incl ms", ui::TableColumnPolicy::Fixed, 74.0f},
                {"self", "Self ms", ui::TableColumnPolicy::Fixed, 74.0f},
                {"percent", "% frame", ui::TableColumnPolicy::Fixed, 68.0f},
                {"coverage", "Child %", ui::TableColumnPolicy::Fixed, 66.0f},
                {"calls", "N", ui::TableColumnPolicy::Fixed, 42.0f},
            });
            expansion_ = std::make_shared<ui::TreeExpansionModel>();
            section_table_ = &builder.make<ui::TreeTableWidget>(controller.section_model(), columns_, expansion_);
            auto& detail = builder.make<ui::RichTextView>(controller.detail_model());
            auto& details = builder.make<ui::Splitter>(ui::Orientation::Horizontal, "profiler-details");
            details.set_first(*section_table_);
            details.set_second(detail);
            details.set_min_extents(420.0f, 240.0f).set_split_fraction(0.72f);
            root.add_stretch_child(details);

            auto& status = builder.make<ui::RichTextView>(controller.status_model());
            status.set_show_scrollbar(false);
            root.add_fixed_child(status, 28.0f);

            auto connect_action = [this]() {
                const bool started = profiler_.connect(port_input_->text(), token_input_->text());
                if (started) {
                    token_input_->set_text("");
                }
            };
            connect.clicked().connect([connect_action](ui::Button&) { connect_action(); });
            disconnect.clicked().connect([this](ui::Button&) { profiler_.disconnect(); });
            port_input_->submitted().connect(
                [connect_action](ui::TextInput&, const std::string&) { connect_action(); });
            token_input_->submitted().connect(
                [connect_action](ui::TextInput&, const std::string&) { connect_action(); });
            refresh_devices.clicked().connect([this](ui::Button&) { android_bridge_.refresh_devices(); });
            connect_android.clicked().connect([this](ui::Button&) {
                const int selected = device_combo_->selected_index();
                if (selected < 0 || static_cast<std::size_t>(selected) >= android_devices_.size()) {
                    android_status_model_->set_text("Select a ready Android device first.");
                    return;
                }
                termin::profiler_app::AndroidConnectRequest request;
                request.serial = android_devices_[static_cast<std::size_t>(selected)].serial;
                request.package_name = package_input_->text();
                request.activity_name = activity_input_->text();
                android_bridge_.connect(std::move(request));
            });
            disconnect_android.clicked().connect([this](ui::Button&) {
                profiler_.disconnect();
                android_bridge_.disconnect();
            });
            toolbar.activated().connect(
                [this](ui::ToolBar&, std::size_t, ui::CommandId command, const ui::CommandData&) {
                    if (profiler_.profiler().activate(command)) {
                        sync_selection();
                        profiler_.refresh_gpu_presentation();
                    }
                });
            timeline_->selection_changed().connect([this](ui::FrameTimelineWidget&, std::int64_t frame) {
                if (!syncing_selection_) {
                    profiler_.profiler().select_frame(frame);
                    profiler_.refresh_gpu_presentation();
                }
            });
            section_table_->selection_changed().connect([this](ui::TreeTableWidget&, ui::TreeTableNodeId node) {
                profiler_.profiler().show_section_details(node);
            });
        }

        void sync_android_bridge() {
            const termin::profiler_app::AndroidBridgeSnapshot snapshot = android_bridge_.snapshot();
            if (snapshot.revision != android_revision_) {
                android_revision_ = snapshot.revision;
                android_status_model_->set_text(snapshot.status);

                bool devices_changed = snapshot.devices.size() != android_devices_.size();
                if (!devices_changed) {
                    for (std::size_t index = 0; index < snapshot.devices.size(); ++index) {
                        if (snapshot.devices[index].serial != android_devices_[index].serial ||
                            snapshot.devices[index].state != android_devices_[index].state) {
                            devices_changed = true;
                            break;
                        }
                    }
                }
                if (devices_changed) {
                    std::string previous_serial;
                    const int previous = device_combo_->selected_index();
                    if (previous >= 0 && static_cast<std::size_t>(previous) < android_devices_.size()) {
                        previous_serial = android_devices_[static_cast<std::size_t>(previous)].serial;
                    }
                    android_devices_ = snapshot.devices;
                    device_combo_->clear_items();
                    int selected = -1;
                    for (std::size_t index = 0; index < android_devices_.size(); ++index) {
                        const auto& device = android_devices_[index];
                        std::string label = device.serial + "  [" + device.state + "]";
                        if (!device.description.empty()) {
                            label += "  " + device.description;
                        }
                        device_combo_->add_item(std::move(label));
                        if (device.serial == previous_serial || (selected < 0 && device.ready())) {
                            selected = static_cast<int>(index);
                        }
                    }
                    if (selected >= 0) {
                        device_combo_->set_selected_index(selected);
                    }
                }
            }

            if (auto pending = android_bridge_.take_pending_connection()) {
                profiler_.disconnect();
                if (!profiler_.connect(std::to_string(pending->host_port), std::move(pending->authentication_token))) {
                    android_status_model_->set_text(
                        "The Android route was created, but the profiler client could not start.");
                    android_bridge_.disconnect();
                }
            }
        }

        void sync_selection() {
            syncing_selection_ = true;
            const std::int64_t selected = profiler_.profiler().selected_frame_number();
            if (selected >= 0 && (!timeline_->selected_id() || *timeline_->selected_id() != selected)) {
                timeline_->select(selected);
            }
            timeline_->set_follow_latest(profiler_.profiler().follow_latest());
            syncing_selection_ = false;
        }

        void paint_gpu_timeline(ui::Canvas& canvas, tc_ui_paint_context* context) const {
            const tc_ui_rect rect = canvas.bounds();
            const float header_height = 24.0f;
            const tc_ui_rect graph{
                rect.x, rect.y + header_height, rect.width, std::max(0.0f, rect.height - header_height)};
            const auto [begin, end] = timeline_->visible_range();
            const auto& samples = timeline_->model()->samples();
            const auto snapshot = profiler_.snapshot();
            const auto frame_for = [&snapshot](std::int64_t frame_number) -> const termin::FrameProfilerFrame* {
                const auto found = std::lower_bound(snapshot->frames.begin(),
                                                    snapshot->frames.end(),
                                                    frame_number,
                                                    [](const termin::FrameProfilerFrame& frame, std::int64_t number) {
                                                        return frame.frame_number < number;
                                                    });
                return found != snapshot->frames.end() && found->frame_number == frame_number ? &*found : nullptr;
            };
            if (begin >= end || end > samples.size()) {
                tc_ui_painter_draw_text(context,
                                        "GPU duration: unavailable — no captured frames",
                                        {rect.x + 6.0f, rect.y + 18.0f},
                                        13.0f,
                                        {0.72f, 0.74f, 0.79f, 1.0f});
                tc_ui_painter_stroke_rect(context, rect, {0.22f, 0.24f, 0.29f, 1.0f}, 1.0f);
                return;
            }

            double largest_gpu = 0.0;
            double target = 0.0;
            for (std::size_t index = begin; index < end; ++index) {
                const auto* frame = frame_for(samples[index].stable_id);
                if (frame && frame->has_gpu_duration) {
                    largest_gpu = std::max(largest_gpu, frame->gpu_duration_ms);
                }
                target = std::max(target, static_cast<double>(samples[index].target_ms));
            }
            if (target <= 0.0) {
                target = 1000.0 / 60.0;
            }
            const double scale = std::max({largest_gpu, target, 0.001});
            const float slot_width = graph.width / static_cast<float>(end - begin);
            const float bar_width = std::max(0.5f, slot_width - std::min(1.0f, slot_width * 0.15f));
            const auto y_for = [&](double value) {
                return graph.y + graph.height -
                       static_cast<float>(std::min(value / scale, 1.0) * static_cast<double>(graph.height));
            };

            char label[160]{};
            std::snprintf(
                label, sizeof(label), "GPU duration (purple) | gray tick = unavailable | scale %.2f ms", scale);
            tc_ui_painter_draw_text(
                context, label, {rect.x + 6.0f, rect.y + 18.0f}, 13.0f, {0.84f, 0.85f, 0.89f, 1.0f});
            tc_ui_painter_draw_line(context,
                                    {graph.x, y_for(target)},
                                    {graph.x + graph.width, y_for(target)},
                                    {0.72f, 0.74f, 0.79f, 0.45f},
                                    1.0f);

            const std::optional<std::int64_t> selected = timeline_->selected_id();
            for (std::size_t index = begin; index < end; ++index) {
                const float x = graph.x + static_cast<float>(index - begin) * slot_width;
                const auto* frame = frame_for(samples[index].stable_id);
                if (frame && frame->has_gpu_duration) {
                    const float height = std::min(
                        graph.height,
                        static_cast<float>(frame->gpu_duration_ms / scale * static_cast<double>(graph.height)));
                    tc_ui_painter_fill_rect(
                        context, {x, graph.y + graph.height - height, bar_width, height}, {0.72f, 0.42f, 0.95f, 1.0f});
                } else {
                    const float y = graph.y + graph.height - 2.0f;
                    tc_ui_painter_draw_line(context, {x, y}, {x + bar_width, y}, {0.58f, 0.60f, 0.66f, 0.9f}, 2.0f);
                }
                if (selected && samples[index].stable_id == *selected) {
                    tc_ui_painter_stroke_rect(context,
                                              {x, graph.y, std::max(slot_width, 2.0f), graph.height},
                                              {0.95f, 0.78f, 0.30f, 1.0f},
                                              2.0f);
                }
            }
            tc_ui_painter_stroke_rect(context, rect, {0.22f, 0.24f, 0.29f, 1.0f}, 1.0f);
        }

        std::unique_ptr<termin::WindowedGraphicsSession> graphics_;
        std::unique_ptr<termin::WindowManager> windows_;
        termin::WindowHandle window_;
        tc_ui_document_handle document_handle_{};
        ui::TcDocument document_;
        std::unique_ptr<ui::GuiWindowAdapter> adapter_;
        termin::profiler_app::RemoteProfilerSession profiler_;
        termin::profiler_app::AndroidProfilerBridge android_bridge_;
        ui::ComboBox* device_combo_ = nullptr;
        ui::TextInput* package_input_ = nullptr;
        ui::TextInput* activity_input_ = nullptr;
        std::shared_ptr<ui::RichTextModel> android_status_model_;
        std::vector<termin::profiler_app::AndroidDevice> android_devices_;
        std::uint64_t android_revision_ = 0;
        ui::TextInput* port_input_ = nullptr;
        ui::TextInput* token_input_ = nullptr;
        ui::FrameTimelineWidget* timeline_ = nullptr;
        ui::Canvas* gpu_timeline_ = nullptr;
        ui::RichTextView* gpu_summary_ = nullptr;
        ui::RichTextView* gpu_detail_ = nullptr;
        std::shared_ptr<ui::RichTextModel> timeline_legend_model_;
        ui::TreeTableWidget* section_table_ = nullptr;
        std::shared_ptr<ui::TableColumnModel> columns_;
        std::shared_ptr<ui::TreeExpansionModel> expansion_;
        bool syncing_selection_ = false;
    };

    bool is_missing_window_system(const char* message) {
        return message && (std::strstr(message, "No available video device") ||
                           std::strstr(message, "Vulkan support is either not configured in SDL") ||
                           std::strstr(message, "Could not initialize OpenGL") || std::strstr(message, "DISPLAY"));
    }

} // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_options(argc, argv);
        ProfilerApplication application(argc > 0 ? argv[0] : nullptr);
        return application.run(options.frame_limit);
    } catch (const std::exception& error) {
        std::fprintf(stderr, "termin_profiler failed: %s\n", error.what());
        return is_missing_window_system(error.what()) ? 77 : 1;
    }
}
