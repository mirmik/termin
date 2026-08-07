#include <charconv>
#include <cstdio>
#include <cstring>
#include <exception>
#include <filesystem>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>

#include <termin/gui_native/document_builder.hpp>
#include <termin/gui_native/tc_ui_document.h>
#include <termin/gui_native/widgets.hpp>
#include <termin/gui_native/window_adapter.hpp>
#include <termin/platform/backend_window.hpp>
#include <termin/window/window_manager.hpp>

namespace ui = termin::gui_native;

namespace {

    constexpr std::string_view kApplicationName = "Termin Tally";

    std::optional<size_t> parse_frame_limit(int argc, char** argv) {
        if (argc == 1) {
            return std::nullopt;
        }
        if (argc != 3 || std::string_view(argv[1]) != "--frames") {
            throw std::runtime_error("usage: termin_tally [--frames COUNT]");
        }
        size_t result = 0;
        const std::string_view value(argv[2]);
        const auto parsed = std::from_chars(value.data(), value.data() + value.size(), result);
        if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size() || result == 0) {
            throw std::runtime_error("--frames expects a positive integer");
        }
        return result;
    }

    std::string resolve_font_path() {
        if (const char* configured = std::getenv("TERMIN_UI_FONT"); configured && configured[0]) {
            return configured;
        }
        const std::filesystem::path sdk_root =
            std::getenv("TERMIN_SDK") ? std::getenv("TERMIN_SDK") : std::filesystem::path{};
        const std::filesystem::path candidates[] = {
            sdk_root / "share" / "termin" / "fonts" / "DroidSans.ttf",
            std::filesystem::path("sdk/share/termin/fonts/DroidSans.ttf"),
            std::filesystem::path("/usr/local/share/termin/fonts/DroidSans.ttf"),
        };
        for (const auto& candidate : candidates) {
            if (!candidate.empty() && std::filesystem::is_regular_file(candidate)) {
                return candidate.string();
            }
        }
        throw std::runtime_error("cannot find UI font; set TERMIN_UI_FONT or TERMIN_SDK");
    }

    class TallyApplication {
    public:
        TallyApplication()
            : session_(termin::create_native_windowed_graphics()),
              windows_(std::make_unique<termin::WindowManager>(*session_)),
              handle_(windows_->create_window(termin::WindowConfig{std::string(kApplicationName), 420, 260})),
              document_handle_(tc_ui_document_create()),
              document_(document_handle_),
              adapter_(std::make_unique<ui::GuiWindowAdapter>(
                  session_->graphics(),
                  document_,
                  ui::DocumentRendererConfig{resolve_font_path(), 16, {0.025f, 0.03f, 0.04f, 1.0f}, true},
                  windows_->window(handle_))) {
            build_interface();
        }

        ~TallyApplication() {
            if (adapter_) {
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
            if (session_) {
                session_->close();
            }
        }

        TallyApplication(const TallyApplication&) = delete;
        TallyApplication& operator=(const TallyApplication&) = delete;

        int run(std::optional<size_t> frame_limit) {
            while (!windows_->window(handle_).should_close() &&
                   (!frame_limit.has_value() || adapter_->renderer().rendered_frame_count() < *frame_limit)) {
                windows_->pump_events();
                adapter_->consume_events(windows_->take_events(handle_));
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
            auto& root = builder.make_root<ui::VStack>("tally-root");
            auto& title = builder.make<ui::Label>("A tiny native tally", 18.0f);
            count_label_ = &builder.make<ui::Label>("0", 44.0f);
            auto& upper_space = builder.make<ui::Spacer>(tc_ui_size{0.0f, 0.0f});
            auto& lower_space = builder.make<ui::Spacer>(tc_ui_size{0.0f, 0.0f});
            auto& actions = builder.make<ui::HStack>("tally-actions");
            auto& reset = builder.make<ui::Button>("Reset");
            auto& increment = builder.make<ui::Button>("Add one");

            root.set_padding(ui::EdgeInsets{28.0f, 24.0f, 28.0f, 24.0f})
                .set_spacing(12.0f)
                .set_background(ui::Color{0.055f, 0.065f, 0.085f, 1.0f});
            actions.set_spacing(12.0f);
            actions.add_flex_child(reset);
            actions.add_flex_child(increment);
            root.add_preferred_child(title);
            root.add_flex_child(upper_space);
            root.add_preferred_child(*count_label_);
            root.add_flex_child(lower_space);
            root.add_fixed_child(actions, 42.0f);

            reset.clicked().connect([this](ui::Button&) {
                count_ = 0;
                refresh_count();
            });
            increment.clicked().connect([this](ui::Button&) {
                ++count_;
                refresh_count();
            });
        }

        void refresh_count() {
            const std::string value = std::to_string(count_);
            count_label_->set_text(value);
            windows_->window(handle_).set_title(std::string(kApplicationName) + " - " + value);
        }

        std::unique_ptr<termin::WindowedGraphicsSession> session_;
        std::unique_ptr<termin::WindowManager> windows_;
        termin::WindowHandle handle_;
        tc_ui_document_handle document_handle_;
        ui::TcDocument document_;
        std::unique_ptr<ui::GuiWindowAdapter> adapter_;
        int count_ = 0;
        ui::Label* count_label_ = nullptr;
    };

    bool is_missing_window_system(const char* message) {
        return message && (std::strstr(message, "No available video device") ||
                           std::strstr(message, "Vulkan support is either not configured in SDL") ||
                           std::strstr(message, "Could not initialize OpenGL") || std::strstr(message, "DISPLAY"));
    }

} // namespace

int main(int argc, char** argv) {
    try {
        const std::optional<size_t> frame_limit = parse_frame_limit(argc, argv);
        TallyApplication application;
        return application.run(frame_limit);
    } catch (const std::exception& error) {
        std::fprintf(stderr, "termin_tally failed: %s\n", error.what());
        return is_missing_window_system(error.what()) ? 77 : 1;
    }
}
