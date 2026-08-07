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
              window_(windows_->create_window(termin::WindowConfig{"Termin Remote Profiler", 1180, 760})),
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
        }

        ~ProfilerApplication() {
            profiler_.close();
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

            auto& connection = builder.make<ui::HStack>("profiler-connection");
            connection.set_spacing(5.0f);
            auto& route_label = builder.make<ui::Label>("ADB/SSH forward");
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

            timeline_ = &builder.make<ui::FrameTimelineWidget>(controller.timeline_model());
            timeline_->set_window_size(180);
            timeline_->set_warning_ratio(static_cast<float>(controller.hitch_ratio()));
            root.add_fixed_child(*timeline_, 220.0f);

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
            toolbar.activated().connect(
                [this](ui::ToolBar&, std::size_t, ui::CommandId command, const ui::CommandData&) {
                    if (profiler_.profiler().activate(command)) {
                        sync_selection();
                    }
                });
            timeline_->selection_changed().connect([this](ui::FrameTimelineWidget&, std::int64_t frame) {
                if (!syncing_selection_) {
                    profiler_.profiler().select_frame(frame);
                }
            });
            section_table_->selection_changed().connect([this](ui::TreeTableWidget&, ui::TreeTableNodeId node) {
                profiler_.profiler().show_section_details(node);
            });
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

        std::unique_ptr<termin::WindowedGraphicsSession> graphics_;
        std::unique_ptr<termin::WindowManager> windows_;
        termin::WindowHandle window_;
        tc_ui_document_handle document_handle_{};
        ui::TcDocument document_;
        std::unique_ptr<ui::GuiWindowAdapter> adapter_;
        termin::profiler_app::RemoteProfilerSession profiler_;
        ui::TextInput* port_input_ = nullptr;
        ui::TextInput* token_input_ = nullptr;
        ui::FrameTimelineWidget* timeline_ = nullptr;
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
