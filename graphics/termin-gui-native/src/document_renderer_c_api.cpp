#include <termin/gui_native/document_renderer_c_api.h>
#include <termin/gui_native/document_renderer.hpp>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#include <tcbase/tc_log.h>
#include <tgfx2/graphics_host.hpp>

namespace {

namespace gui = termin::gui_native;

struct BridgeSink final : gui::DocumentFrameSink {
    int width;
    int height;
    float density;
    tgfx::TextureHandle texture{};

    BridgeSink(int width, int height, float density) : width(width), height(height), density(density) {}
    std::pair<int, int> framebuffer_size() const override { return {width, height}; }
    float content_scale() const override { return density; }
    tgfx::TextureEncoding destination_encoding() const override { return tgfx::TextureEncoding::Linear; }
    void publish_display_linear_frame(tgfx::TextureHandle frame) override { texture = frame; }
};

struct BridgePlatform final : gui::DocumentPlatformServices {
    tc_document_renderer_config config;

    explicit BridgePlatform(const tc_document_renderer_config& config) : config(config) {}
    bool set_text_input_enabled(bool enabled) override {
        return !config.set_text_input || config.set_text_input(config.userdata, enabled);
    }
    std::string clipboard_text() const override {
        if (!config.copy_clipboard)
            return {};
        const size_t required = config.copy_clipboard(config.userdata, nullptr, 0);
        if (required == 0)
            throw std::runtime_error("clipboard size query failed");
        std::vector<char> buffer(required, '\0');
        const size_t copied = config.copy_clipboard(config.userdata, buffer.data(), buffer.size());
        if (copied == 0 || copied > buffer.size() || buffer[copied - 1] != '\0')
            throw std::runtime_error("clipboard copy returned an invalid UTF-8 buffer length");
        return std::string(buffer.data(), copied - 1);
    }
    bool set_clipboard_text(const std::string& text) override {
        if (!config.set_clipboard) {
            tc_log_error("[document-renderer-c-api] clipboard write callback is not configured");
            return false;
        }
        return config.set_clipboard(config.userdata, text.c_str(), text.size());
    }
    bool set_cursor(tc_ui_cursor_intent cursor) override {
        return !config.set_cursor || config.set_cursor(config.userdata, cursor);
    }
};

struct Entry {
    tc_ui_document_handle document;
    std::thread::id owner = std::this_thread::get_id();
    BridgeSink sink;
    BridgePlatform platform;
    std::unique_ptr<gui::DocumentRenderer> renderer;
    std::string last_error;
    bool in_call = false;

    Entry(tc_ui_document_handle document, const tc_document_renderer_config& config)
        : document(document), sink(config.width, config.height, config.density_scale), platform(config) {}
};

struct Slot {
    std::shared_ptr<Entry> entry;
    uint32_t generation = 1;
};

std::mutex registry_mutex;
std::vector<Slot> slots;

std::shared_ptr<Entry> acquire(tc_document_renderer_handle handle) {
    std::lock_guard lock(registry_mutex);
    if (tc_document_renderer_handle_is_invalid(handle) || handle.index >= slots.size())
        return {};
    const Slot& slot = slots[handle.index];
    return slot.generation == handle.generation ? slot.entry : nullptr;
}

size_t copy_string(const std::string& value, char* buffer, size_t capacity) {
    if (buffer && capacity) {
        const size_t count = std::min(value.size(), capacity - 1);
        std::memcpy(buffer, value.data(), count);
        buffer[count] = '\0';
    }
    return value.size() + 1;
}

void record_error(Entry& entry, const char* error) {
    entry.last_error = error;
    tc_log_error("[document-renderer-c-api] %s", error);
}

bool validate_metrics(int32_t width, int32_t height, float density) {
    return width > 0 && height > 0 && std::isfinite(density) && density > 0;
}

struct CallGuard {
    Entry& entry;
    explicit CallGuard(Entry& entry) : entry(entry) { entry.in_call = true; }
    ~CallGuard() { entry.in_call = false; }
};

template <typename Function>
bool access(tc_document_renderer_handle handle, Function&& function) {
    const auto entry = acquire(handle);
    if (!entry) {
        tc_log_error("[document-renderer-c-api] invalid or stale renderer handle");
        return false;
    }
    if (entry->owner != std::this_thread::get_id()) {
        tc_log_error("[document-renderer-c-api] renderer call must run on its creating thread");
        return false;
    }
    if (entry->in_call) {
        record_error(*entry, "renderer calls cannot reenter from a synchronous callback");
        return false;
    }
    const CallGuard guard(*entry);
    try {
        if (!tc_ui_document_is_valid(entry->document))
            throw std::logic_error("borrowed document was destroyed before its renderer");
        return function(*entry);
    } catch (const std::exception& error) {
        record_error(*entry, error.what());
    } catch (...) {
        record_error(*entry, "unknown native exception");
    }
    return false;
}

} // namespace

extern "C" {

tc_document_renderer_handle tc_document_renderer_create(
    tc_ui_document_handle document, void* graphics_host, const tc_document_renderer_config* config) {
    try {
        if (!tc_ui_document_is_valid(document) || !graphics_host || !config ||
            config->struct_size < sizeof(*config) || !config->font_path || !config->font_path[0] ||
            config->font_size <= 0 || !validate_metrics(config->width, config->height, config->density_scale))
            throw std::invalid_argument("create requires live document/graphics host, font and valid metrics/config");
        // A document has one set of native text/cursor/clipboard hooks. Reject
        // duplicate bindings rather than silently stealing another renderer's hooks.
        {
            std::lock_guard lock(registry_mutex);
            for (const Slot& slot : slots) {
                if (slot.entry && tc_ui_document_handle_eq(slot.entry->document, document))
                    throw std::invalid_argument("document is already bound to a C ABI renderer");
            }
        }
        auto entry = std::make_shared<Entry>(document, *config);
        gui::DocumentRendererConfig native_config;
        native_config.font_path = config->font_path;
        native_config.font_size = config->font_size;
        auto& graphics = *static_cast<tgfx::GraphicsHost*>(graphics_host);
        if (graphics.is_closed())
            throw std::invalid_argument("borrowed graphics host is closed");
        entry->renderer = std::make_unique<gui::DocumentRenderer>(
            graphics, gui::TcDocument(document), std::move(native_config), entry->sink, entry->platform);
        if (!entry->renderer->sync_presentation_metrics())
            throw std::runtime_error("failed to synchronize initial presentation metrics");
        std::lock_guard lock(registry_mutex);
        uint32_t index = 0;
        while (index < slots.size() && slots[index].entry)
            ++index;
        if (index == slots.size())
            slots.emplace_back();
        Slot& slot = slots[index];
        slot.entry = std::move(entry);
        return {index, slot.generation};
    } catch (const std::exception& error) {
        tc_log_error("[document-renderer-c-api] creation failed: %s", error.what());
    } catch (...) {
        tc_log_error("[document-renderer-c-api] creation failed: unknown native exception");
    }
    return tc_document_renderer_handle_invalid();
}

bool tc_document_renderer_destroy(tc_document_renderer_handle handle) {
    return access(handle, [&](Entry& entry) {
        entry.renderer->close();
        // Callback shutdown runs before retirement, under the reentrancy guard.
        std::lock_guard lock(registry_mutex);
        Slot& slot = slots[handle.index];
        slot.entry.reset();
        if (++slot.generation == 0)
            ++slot.generation;
        return true;
    });
}

bool tc_document_renderer_is_valid(tc_document_renderer_handle handle) {
    return static_cast<bool>(acquire(handle));
}

bool tc_document_renderer_set_metrics(tc_document_renderer_handle handle, int32_t width, int32_t height, float density) {
    return access(handle, [&](Entry& entry) {
        if (!validate_metrics(width, height, density))
            throw std::invalid_argument("framebuffer dimensions and density must be positive and finite");
        if (entry.sink.width == width && entry.sink.height == height && entry.sink.density == density)
            return true;
        entry.sink.width = width;
        entry.sink.height = height;
        entry.sink.density = density;
        entry.sink.texture = {};
        entry.renderer->sync_presentation_metrics();
        entry.renderer->request_repaint();
        return true;
    });
}

bool tc_document_renderer_render(tc_document_renderer_handle handle, uint32_t* out_texture) {
    if (out_texture)
        *out_texture = 0;
    return access(handle, [&](Entry& entry) {
        if (!out_texture)
            throw std::invalid_argument("render texture output is null");
        if (!entry.renderer->render_frame())
            throw std::runtime_error("native document renderer produced no frame");
        *out_texture = entry.sink.texture.id;
        return *out_texture != 0;
    });
}

bool tc_document_renderer_dispatch_pointer(
    tc_document_renderer_handle handle, const tc_ui_pointer_event* event, tc_ui_event_result* out_result) {
    if (out_result)
        *out_result = TC_UI_EVENT_IGNORED;
    return access(handle, [&](Entry& entry) {
        if (!event || !out_result || !std::isfinite(event->x) || !std::isfinite(event->y) ||
            !std::isfinite(event->wheel_x) || !std::isfinite(event->wheel_y))
            throw std::invalid_argument("pointer event/output must be non-null with finite coordinates");
        *out_result = entry.renderer->dispatch_pointer(*event);
        return true;
    });
}

bool tc_document_renderer_dispatch_key(
    tc_document_renderer_handle handle, const tc_ui_key_event* event, tc_ui_event_result* out_result) {
    if (out_result)
        *out_result = TC_UI_EVENT_IGNORED;
    return access(handle, [&](Entry& entry) {
        if (!event || !out_result)
            throw std::invalid_argument("key event/output is null");
        *out_result = entry.renderer->dispatch_key(*event);
        return true;
    });
}

bool tc_document_renderer_dispatch_text(
    tc_document_renderer_handle handle, const char* utf8, tc_ui_event_result* out_result) {
    if (out_result)
        *out_result = TC_UI_EVENT_IGNORED;
    return access(handle, [&](Entry& entry) {
        if (!utf8 || !out_result)
            throw std::invalid_argument("text event/output is null");
        *out_result = entry.renderer->dispatch_text(utf8);
        return true;
    });
}

bool tc_document_renderer_cancel_interaction(tc_document_renderer_handle handle, tc_ui_pointer_cancel_reason reason) {
    return access(handle, [&](Entry& entry) {
        tc_ui_document_cancel_pointer_interaction(entry.document, reason);
        entry.renderer->request_repaint();
        return true;
    });
}

bool tc_document_renderer_set_focus(tc_document_renderer_handle handle, bool focused) {
    return access(handle, [&](Entry& entry) {
        if (!focused) {
            tc_ui_document_cancel_pointer_interaction(entry.document, TC_UI_POINTER_CANCEL_WINDOW_FOCUS_LOST);
            const auto widget = tc_ui_document_focused_widget(entry.document);
            if (!tc_widget_handle_is_invalid(widget))
                tc_ui_document_clear_focus(entry.document, widget);
        }
        if (!entry.platform.set_text_input_enabled(focused))
            throw std::runtime_error("platform rejected host focus/text input update");
        entry.renderer->request_repaint();
        return true;
    });
}

bool tc_document_renderer_has_pointer_capture(tc_document_renderer_handle handle) {
    bool captured = false;
    access(handle, [&](Entry& entry) {
        // Native routing also retains a pressed handler without explicit capture.
        captured = !tc_widget_handle_is_invalid(tc_ui_document_pointer_capture(entry.document)) ||
                   !tc_widget_handle_is_invalid(tc_ui_document_pressed_widget(entry.document));
        return true;
    });
    return captured;
}

bool tc_document_renderer_request_repaint(tc_document_renderer_handle handle) {
    return access(handle, [](Entry& entry) {
        entry.renderer->request_repaint();
        return true;
    });
}

bool tc_document_renderer_repaint_requested(tc_document_renderer_handle handle) {
    bool requested = false;
    access(handle, [&](Entry& entry) {
        requested = entry.renderer->repaint_requested();
        return true;
    });
    return requested;
}

size_t tc_document_renderer_copy_last_error(tc_document_renderer_handle handle, char* buffer, size_t capacity) {
    const auto entry = acquire(handle);
    if (!entry)
        return copy_string("invalid or stale renderer handle", buffer, capacity);
    if (entry->owner != std::this_thread::get_id())
        return copy_string("renderer call must run on its creating thread", buffer, capacity);
    return copy_string(entry->last_error, buffer, capacity);
}

} // extern "C"
