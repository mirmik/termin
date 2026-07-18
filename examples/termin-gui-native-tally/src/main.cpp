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

#include <SDL2/SDL.h>

#include <termin/gui_native/document_builder.hpp>
#include <termin/gui_native/draw_list_renderer.hpp>
#include <termin/gui_native/widgets.hpp>
#include <termin/platform/sdl_backend_window.hpp>

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

uint32_t translate_modifiers(SDL_Keymod modifiers) {
  uint32_t result = 0;
  if ((modifiers & KMOD_SHIFT) != 0) {
    result |= TC_UI_MOD_SHIFT;
  }
  if ((modifiers & KMOD_CTRL) != 0) {
    result |= TC_UI_MOD_CTRL;
  }
  if ((modifiers & KMOD_ALT) != 0) {
    result |= TC_UI_MOD_ALT;
  }
  if ((modifiers & KMOD_GUI) != 0) {
    result |= TC_UI_MOD_SUPER;
  }
  return result;
}

int32_t translate_pointer_button(uint8_t button) {
  switch (button) {
  case SDL_BUTTON_LEFT:
    return ui::pointer_button_value(ui::PointerButton::Left);
  case SDL_BUTTON_RIGHT:
    return ui::pointer_button_value(ui::PointerButton::Right);
  case SDL_BUTTON_MIDDLE:
    return ui::pointer_button_value(ui::PointerButton::Middle);
  default:
    return -1;
  }
}

int32_t translate_key(SDL_Keycode key) {
  if (key >= SDLK_a && key <= SDLK_z) {
    return TC_UI_KEY_A + static_cast<int32_t>(key - SDLK_a);
  }
  if (key >= SDLK_0 && key <= SDLK_9) {
    return TC_UI_KEY_0 + static_cast<int32_t>(key - SDLK_0);
  }
  switch (key) {
  case SDLK_TAB:
    return TC_UI_KEY_TAB;
  case SDLK_RETURN:
  case SDLK_KP_ENTER:
    return TC_UI_KEY_ENTER;
  case SDLK_SPACE:
    return TC_UI_KEY_SPACE;
  case SDLK_ESCAPE:
    return TC_UI_KEY_ESCAPE;
  case SDLK_BACKSPACE:
    return TC_UI_KEY_BACKSPACE;
  case SDLK_DELETE:
    return TC_UI_KEY_DELETE;
  case SDLK_RIGHT:
    return TC_UI_KEY_RIGHT;
  case SDLK_LEFT:
    return TC_UI_KEY_LEFT;
  case SDLK_DOWN:
    return TC_UI_KEY_DOWN_ARROW;
  case SDLK_UP:
    return TC_UI_KEY_UP_ARROW;
  case SDLK_HOME:
    return TC_UI_KEY_HOME;
  case SDLK_END:
    return TC_UI_KEY_END;
  default:
    return TC_UI_KEY_UNKNOWN;
  }
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
      : window_(std::string(kApplicationName), 420, 260),
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
    SDL_StartTextInput();
  }

  ~TallyApplication() {
    SDL_StopTextInput();
    renderer_.release_gpu();
    if (color_target_) {
      device_.destroy(color_target_);
    }
  }

  TallyApplication(const TallyApplication &) = delete;
  TallyApplication &operator=(const TallyApplication &) = delete;

  int run(std::optional<size_t> frame_limit) {
    size_t rendered_frames = 0;
    while (!window_.should_close() &&
           (!frame_limit.has_value() || rendered_frames < *frame_limit)) {
      dispatch_events();
      const auto [width, height] = window_.framebuffer_size();
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
      window_.present(color_target_);
      ++rendered_frames;
    }
    device_.wait_idle();
    return 0;
  }

private:
  tgfx::IRenderDevice &checked_device() {
    tgfx::IRenderDevice *device = window_.device();
    if (!device) {
      throw std::runtime_error("window did not provide a render device");
    }
    return *device;
  }

  tgfx::RenderContext2 &checked_context() {
    tgfx::RenderContext2 *context = window_.context();
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
    SDL_SetWindowTitle(window_.sdl_window(),
                       (std::string(kApplicationName) + " - " + value).c_str());
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

  std::pair<float, float> to_framebuffer(float x, float y) const {
    int window_width = 0;
    int window_height = 0;
    SDL_GetWindowSize(window_.sdl_window(), &window_width, &window_height);
    const auto [framebuffer_width, framebuffer_height] =
        window_.framebuffer_size();
    if (window_width <= 0 || window_height <= 0) {
      return {x, y};
    }
    return {x * static_cast<float>(framebuffer_width) /
                static_cast<float>(window_width),
            y * static_cast<float>(framebuffer_height) /
                static_cast<float>(window_height)};
  }

  bool event_belongs_to_window(uint32_t event_window_id) const {
    return event_window_id == 0 ||
           event_window_id == SDL_GetWindowID(window_.sdl_window());
  }

  void dispatch_pointer(tc_ui_pointer_event_type type, float x, float y,
                        int32_t button, uint32_t clicks, float wheel_x = 0.0f,
                        float wheel_y = 0.0f) {
    const auto [framebuffer_x, framebuffer_y] = to_framebuffer(x, y);
    const tc_ui_pointer_event event{
        type,
        framebuffer_x,
        framebuffer_y,
        button,
        clicks,
        static_cast<int32_t>(translate_modifiers(SDL_GetModState())),
        wheel_x,
        wheel_y};
    document_.dispatch_pointer_event(event);
  }

  void dispatch_events() {
    SDL_Event event;
    while (window_.poll_event(event)) {
      if (event.type == SDL_QUIT) {
        window_.set_should_close(true);
        continue;
      }
      if (event.type == SDL_WINDOWEVENT &&
          event.window.event == SDL_WINDOWEVENT_CLOSE &&
          event_belongs_to_window(event.window.windowID)) {
        window_.set_should_close(true);
        continue;
      }

      switch (event.type) {
      case SDL_MOUSEMOTION:
        if (event_belongs_to_window(event.motion.windowID)) {
          dispatch_pointer(TC_UI_POINTER_MOVE,
                           static_cast<float>(event.motion.x),
                           static_cast<float>(event.motion.y), -1, 0);
        }
        break;
      case SDL_MOUSEBUTTONDOWN:
      case SDL_MOUSEBUTTONUP:
        if (event_belongs_to_window(event.button.windowID)) {
          dispatch_pointer(event.type == SDL_MOUSEBUTTONDOWN
                               ? TC_UI_POINTER_DOWN
                               : TC_UI_POINTER_UP,
                           static_cast<float>(event.button.x),
                           static_cast<float>(event.button.y),
                           translate_pointer_button(event.button.button),
                           event.button.clicks);
        }
        break;
      case SDL_MOUSEWHEEL:
        if (event_belongs_to_window(event.wheel.windowID)) {
          int x = 0;
          int y = 0;
          SDL_GetMouseState(&x, &y);
          dispatch_pointer(TC_UI_POINTER_WHEEL, static_cast<float>(x),
                           static_cast<float>(y), -1, 0,
                           static_cast<float>(event.wheel.x),
                           static_cast<float>(event.wheel.y));
        }
        break;
      case SDL_KEYDOWN:
      case SDL_KEYUP:
        if (event_belongs_to_window(event.key.windowID)) {
          const tc_ui_key_event key_event{
              event.type == SDL_KEYDOWN ? TC_UI_KEY_DOWN : TC_UI_KEY_UP,
              translate_key(event.key.keysym.sym),
              static_cast<int32_t>(event.key.keysym.scancode),
              static_cast<int32_t>(translate_modifiers(
                  static_cast<SDL_Keymod>(event.key.keysym.mod))),
              event.key.repeat != 0};
          document_.dispatch_key_event(key_event);
        }
        break;
      case SDL_TEXTINPUT:
        if (event_belongs_to_window(event.text.windowID)) {
          document_.dispatch_text_event(tc_ui_text_event{event.text.text});
        }
        break;
      default:
        break;
      }
    }
  }

  termin::SDLBackendWindow window_;
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
