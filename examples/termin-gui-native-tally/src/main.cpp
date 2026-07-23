#include <charconv>
#include <cstdio>
#include <cstring>
#include <exception>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <system_error>

#include <termin/gui_native/application_host.hpp>
#include <termin/gui_native/document_builder.hpp>
#include <termin/gui_native/widgets.hpp>

namespace ui = termin::gui_native;

namespace {

constexpr std::string_view kApplicationName = "Termin Tally";

std::optional<size_t> parse_frame_limit(int argc, char **argv) {
  if (argc == 1) {
    return std::nullopt;
  }
  if (argc != 3 || std::string_view(argv[1]) != "--frames") {
    throw std::runtime_error("usage: termin_tally [--frames COUNT]");
  }
  size_t result = 0;
  const std::string_view value(argv[2]);
  const auto parsed =
      std::from_chars(value.data(), value.data() + value.size(), result);
  if (parsed.ec != std::errc{} || parsed.ptr != value.data() + value.size() ||
      result == 0) {
    throw std::runtime_error("--frames expects a positive integer");
  }
  return result;
}

ui::StandaloneGuiApplicationConfig make_host_config() {
  ui::StandaloneGuiApplicationConfig config;
  config.gui.window = termin::WindowConfig{std::string(kApplicationName), 420, 260};
  config.gui.font_size = 16;
  config.gui.clear_color = {0.025f, 0.03f, 0.04f, 1.0f};
  return config;
}

class TallyApplication {
public:
  TallyApplication() : application_(make_host_config()) {
    build_interface();
  }

  TallyApplication(const TallyApplication &) = delete;
  TallyApplication &operator=(const TallyApplication &) = delete;

  int run(std::optional<size_t> frame_limit) {
    auto &host = application_.window_host();
    while (!host.should_close() &&
           (!frame_limit.has_value() ||
            host.rendered_frame_count() < *frame_limit)) {
      if (!host.tick()) {
        break;
      }
    }
    host.wait_idle();
    return 0;
  }

private:
  void build_interface() {
    ui::DocumentBuilder builder(application_.document());
    auto &root = builder.make_root<ui::VStack>("tally-root");
    auto &title = builder.make<ui::Label>("A tiny native tally", 18.0f);
    count_label_ = &builder.make<ui::Label>("0", 44.0f);
    auto &upper_space = builder.make<ui::Spacer>(tc_ui_size{0.0f, 0.0f});
    auto &lower_space = builder.make<ui::Spacer>(tc_ui_size{0.0f, 0.0f});
    auto &actions = builder.make<ui::HStack>("tally-actions");
    auto &reset = builder.make<ui::Button>("Reset");
    auto &increment = builder.make<ui::Button>("Add one");

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

    reset.clicked().connect([this](ui::Button &) {
      count_ = 0;
      refresh_count();
    });
    increment.clicked().connect([this](ui::Button &) {
      ++count_;
      refresh_count();
    });
  }

  void refresh_count() {
    const std::string value = std::to_string(count_);
    count_label_->set_text(value);
    application_.window_host().window().set_title(
        std::string(kApplicationName) + " - " + value);
  }

  ui::StandaloneGuiApplication application_;
  int count_ = 0;
  ui::Label *count_label_ = nullptr;
};

bool is_missing_window_system(const char *message) {
  return message &&
         (std::strstr(message, "No available video device") ||
          std::strstr(message,
                      "Vulkan support is either not configured in SDL") ||
          std::strstr(message, "Could not initialize OpenGL") ||
          std::strstr(message, "DISPLAY"));
}

} // namespace

int main(int argc, char **argv) {
  try {
    const std::optional<size_t> frame_limit = parse_frame_limit(argc, argv);
    TallyApplication application;
    return application.run(frame_limit);
  } catch (const std::exception &error) {
    std::fprintf(stderr, "termin_tally failed: %s\n", error.what());
    return is_missing_window_system(error.what()) ? 77 : 1;
  }
}
