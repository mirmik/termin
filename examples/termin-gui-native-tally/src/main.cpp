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
#include <termin/gui_native/draw_list_renderer.hpp>
#include <termin/gui_native/window_input.hpp>
#include <termin/gui_native/widgets.hpp>
#include <termin/platform/backend_window.hpp>

#include <tgfx2/descriptors.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

namespace fs = std::filesystem;
namespace ui = termin::gui_native;

namespace {

constexpr std::string_view kApplicationName = "Termin Tally";

bool is_file(const fs::path &path) {
  std::error_code error;
  return fs::is_regular_file(path, error);
}

std::vector<fs::path> path_entries() {
  const char *value = std::getenv("PATH");
  if (!value) {
    return {};
  }

  std::vector<fs::path> result;
#ifdef _WIN32
  constexpr char separator = ';';
#else
  constexpr char separator = ':';
#endif
  std::string text(value);
  size_t begin = 0;
  while (begin <= text.size()) {
    const size_t end = text.find(separator, begin);
    const std::string entry = text.substr(
        begin, end == std::string::npos ? std::string::npos : end - begin);
    if (!entry.empty()) {
      result.emplace_back(entry);
    }
    if (end == std::string::npos) {
      break;
    }
    begin = end + 1;
  }
  return result;
}

fs::path platform_executable(fs::path path) {
#ifdef _WIN32
  if (path.extension().empty()) {
    path += ".exe";
  }
#endif
  return path;
}

fs::path resolve_executable(const char *environment_name, const char *name,
                            const fs::path &configured_hint = {}) {
  std::vector<fs::path> candidates;
  if (const char *configured = std::getenv(environment_name)) {
    candidates.emplace_back(configured);
  }
  if (!configured_hint.empty()) {
    candidates.push_back(configured_hint);
  }
  if (const char *sdk = std::getenv("TERMIN_SDK")) {
    candidates.emplace_back(fs::path(sdk) / "bin" / name);
  }
  candidates.emplace_back(fs::path(TERMIN_TALLY_SDK_HINT) / "bin" / name);
  for (const fs::path &directory : path_entries()) {
    candidates.emplace_back(directory / name);
  }

  for (fs::path candidate : candidates) {
    candidate = platform_executable(std::move(candidate));
    if (is_file(candidate)) {
      return fs::absolute(candidate);
    }
  }
  return {};
}

void set_environment(const char *name, const fs::path &value) {
#ifdef _WIN32
  if (_putenv_s(name, value.string().c_str()) != 0) {
    throw std::runtime_error(
        std::string("failed to set environment variable ") + name);
  }
#else
  if (setenv(name, value.string().c_str(), 1) != 0) {
    throw std::runtime_error(
        std::string("failed to set environment variable ") + name);
  }
#endif
}

void configure_shader_runtime() {
  const fs::path shaderc =
      resolve_executable("TERMIN_SHADERC", "termin_shaderc");
#ifdef TERMIN_TALLY_SLANGC_HINT
  const fs::path slangc =
      resolve_executable("TERMIN_SLANGC", "slangc", TERMIN_TALLY_SLANGC_HINT);
#else
  const fs::path slangc = resolve_executable("TERMIN_SLANGC", "slangc");
#endif
  if (shaderc.empty()) {
    throw std::runtime_error(
        "termin_shaderc was not found; set TERMIN_SDK or TERMIN_SHADERC");
  }
  if (slangc.empty()) {
    throw std::runtime_error(
        "slangc was not found; set TERMIN_SLANGC or add it to PATH");
  }

  const fs::path cache_root =
      fs::temp_directory_path() / "termin-tally" / "shader-cache";
  const fs::path artifact_root =
      fs::temp_directory_path() / "termin-tally" / "shaders";
  std::error_code error;
  fs::create_directories(cache_root, error);
  if (error) {
    throw std::runtime_error("failed to create shader cache: " +
                             error.message());
  }
  fs::create_directories(artifact_root, error);
  if (error) {
    throw std::runtime_error("failed to create shader artifacts: " +
                             error.message());
  }

  set_environment("TERMIN_SLANGC", slangc);
  termin::tgfx2_set_shader_compiler_path(shaderc.string().c_str());
  termin::tgfx2_set_shader_cache_root(cache_root.string().c_str());
  termin::tgfx2_set_shader_artifact_root(artifact_root.string().c_str());
  termin::tgfx2_set_shader_dev_compile_enabled(true);
}

fs::path resolve_font() {
  std::vector<fs::path> candidates;
  if (const char *configured = std::getenv("TERMIN_UI_FONT")) {
    candidates.emplace_back(configured);
  }
  if (const char *sdk = std::getenv("TERMIN_SDK")) {
    candidates.emplace_back(fs::path(sdk) / "share" / "termin" / "fonts" /
                            "DroidSans.ttf");
  }
  candidates.emplace_back(fs::path(TERMIN_TALLY_SDK_HINT) / "share" / "termin" /
                          "fonts" / "DroidSans.ttf");
  for (const fs::path &candidate : candidates) {
    if (is_file(candidate)) {
      return fs::absolute(candidate);
    }
  }
  throw std::runtime_error(
      "UI font was not found; set TERMIN_SDK or TERMIN_UI_FONT");
}

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

tgfx::TextureHandle create_color_target(tgfx::IRenderDevice &device, int width,
                                        int height) {
  tgfx::TextureDesc description;
  description.width = static_cast<uint32_t>(width);
  description.height = static_cast<uint32_t>(height);
  description.format = tgfx::PixelFormat::RGBA8_UNorm;
  description.usage = tgfx::TextureUsage::Sampled |
                      tgfx::TextureUsage::ColorAttachment |
                      tgfx::TextureUsage::CopySrc;
  return device.create_texture(description);
}

struct DrawListDeleter {
  void operator()(tc_ui_draw_list *draw_list) const {
    tc_ui_draw_list_destroy(draw_list);
  }
};

struct PaintContextDeleter {
  void operator()(tc_ui_paint_context *paint_context) const {
    tc_ui_paint_context_destroy(paint_context);
  }
};

using DrawListPtr = std::unique_ptr<tc_ui_draw_list, DrawListDeleter>;
using PaintContextPtr =
    std::unique_ptr<tc_ui_paint_context, PaintContextDeleter>;

class TallyApplication {
public:
  TallyApplication()
      : window_(termin::create_native_window(
            termin::WindowConfig{std::string(kApplicationName), 420, 260})),
        device_(checked_device()), context_(checked_context()),
        draw_list_(tc_ui_draw_list_create()),
        paint_context_(tc_ui_paint_context_create(draw_list_.get())) {
    if (!draw_list_ || !paint_context_) {
      throw std::runtime_error("failed to create native UI paint state");
    }
    if (!renderer_.set_default_font_path(resolve_font().string(), 16)) {
      throw std::runtime_error("failed to initialize native UI font");
    }
    renderer_.bind_text_measurer(document_.get());
    build_interface();
    window_->set_text_input_enabled(true);
  }

  ~TallyApplication() {
    window_->set_text_input_enabled(false);
    renderer_.release_gpu();
    if (color_target_) {
      device_.destroy(color_target_);
    }
  }

  TallyApplication(const TallyApplication &) = delete;
  TallyApplication &operator=(const TallyApplication &) = delete;

  int run(std::optional<size_t> frame_limit) {
    size_t rendered_frames = 0;
    while (!window_->should_close() &&
           (!frame_limit.has_value() || rendered_frames < *frame_limit)) {
      dispatch_events();
      const auto [width, height] = window_->framebuffer_size();
      if (width <= 0 || height <= 0) {
        continue;
      }
      ensure_color_target(width, height);

      tc_ui_draw_list_clear(draw_list_.get());
      document_.layout_roots(tc_ui_rect{0.0f, 0.0f, static_cast<float>(width),
                                        static_cast<float>(height)});
      document_.paint_roots(paint_context_.get());

      context_.begin_frame();
      constexpr float clear_color[4] = {0.025f, 0.03f, 0.04f, 1.0f};
      context_.begin_pass(color_target_, tgfx::TextureHandle{}, clear_color,
                          1.0f, false);
      renderer_.render(context_, draw_list_.get(), width, height);
      context_.end_pass();
      context_.end_frame();
      window_->present(color_target_);
      ++rendered_frames;
    }
    device_.wait_idle();
    return 0;
  }

private:
  tgfx::IRenderDevice &checked_device() {
    tgfx::IRenderDevice *device = window_->device();
    if (!device) {
      throw std::runtime_error("window did not provide a render device");
    }
    return *device;
  }

  tgfx::RenderContext2 &checked_context() {
    tgfx::RenderContext2 *context = window_->context();
    if (!context) {
      throw std::runtime_error("window did not provide a render context");
    }
    return *context;
  }

  void build_interface() {
    ui::DocumentBuilder builder(document_);
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
    window_->set_title(std::string(kApplicationName) + " - " + value);
  }

  void ensure_color_target(int width, int height) {
    if (color_target_ && width == target_width_ && height == target_height_) {
      return;
    }
    if (color_target_) {
      device_.destroy(color_target_);
    }
    color_target_ = create_color_target(device_, width, height);
    if (!color_target_) {
      throw std::runtime_error("failed to create native UI color target");
    }
    target_width_ = width;
    target_height_ = height;
  }

  void dispatch_events() {
    termin::WindowEvent event;
    while (window_->poll_event(event)) {
      ui::dispatch_window_event(document_, event);
    }
  }

  termin::BackendWindowPtr window_;
  tgfx::IRenderDevice &device_;
  tgfx::RenderContext2 &context_;
  ui::Document document_;
  ui::UiDrawListRenderer renderer_;
  DrawListPtr draw_list_;
  PaintContextPtr paint_context_;
  tgfx::TextureHandle color_target_{};
  int target_width_ = 0;
  int target_height_ = 0;
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
    configure_shader_runtime();
    TallyApplication application;
    return application.run(frame_limit);
  } catch (const std::exception &error) {
    std::fprintf(stderr, "termin_tally failed: %s\n", error.what());
    return is_missing_window_system(error.what()) ? 77 : 1;
  }
}
