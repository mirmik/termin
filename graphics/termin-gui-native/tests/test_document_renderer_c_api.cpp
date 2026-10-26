#include <termin/gui_native/document_renderer_c_api.h>
#include <termin/gui_native/tc_document.hpp>
#include <termin/gui_native/text_input.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/graphics_host.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/shader_artifact_resolver.hpp>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include <thread>

namespace {

void check(bool condition, const char* message) {
    if (!condition)
        throw std::runtime_error(message);
}

struct Services {
    bool text_input = false;
    std::string clipboard = "UTF-8: \xD0\xBC\xD0\xB8\xD1\x80";
    tc_ui_cursor_intent cursor = TC_UI_CURSOR_DEFAULT;
    tc_document_renderer_handle renderer = tc_document_renderer_handle_invalid();
    bool attempted_reentry = false;

    static bool set_text_input(void* userdata, bool enabled) {
        auto& self = *static_cast<Services*>(userdata);
        self.text_input = enabled;
        if (!enabled && tc_document_renderer_is_valid(self.renderer)) {
            // Destruction invokes this callback before retirement. Reentry must
            // be rejected without destroying a renderer whose call is active.
            self.attempted_reentry = !tc_document_renderer_destroy(self.renderer);
        }
        return true;
    }
    static size_t copy_clipboard(void* userdata, char* buffer, size_t capacity) {
        const auto& text = static_cast<Services*>(userdata)->clipboard;
        if (buffer && capacity) {
            const size_t length = std::min(text.size(), capacity - 1);
            std::memcpy(buffer, text.data(), length);
            buffer[length] = '\0';
        }
        return text.size() + 1;
    }
    static bool set_clipboard(void* userdata, const char* text, size_t length) {
        static_cast<Services*>(userdata)->clipboard.assign(text, length);
        return true;
    }
    static bool set_cursor(void* userdata, tc_ui_cursor_intent cursor) {
        static_cast<Services*>(userdata)->cursor = cursor;
        return true;
    }
};

} // namespace

int main() {
    try {
        const auto invalid = tc_document_renderer_handle_invalid();
        check(!tc_document_renderer_is_valid(invalid), "invalid renderer was reported alive");
        char error[128]{};
        check(tc_document_renderer_copy_last_error(invalid, error, sizeof(error)) > 1,
              "invalid renderer did not return a copied diagnostic");
        check(std::strstr(error, "invalid") != nullptr, "invalid renderer diagnostic is missing");
        auto backend = tgfx::BackendType::Null;
        if (tgfx::backend_is_compiled(tgfx::BackendType::D3D11))
            backend = tgfx::BackendType::D3D11;
        else if (tgfx::backend_is_compiled(tgfx::BackendType::Vulkan))
            backend = tgfx::BackendType::Vulkan;
        if (backend == tgfx::BackendType::Null) {
            std::printf("document renderer C ABI test skipped: no headless GPU backend\n");
            return 77;
        }
        auto graphics = tgfx::GraphicsHost::create_isolated(backend);
        const char* artifact_root = std::getenv("TERMIN_SHADER_ARTIFACT_ROOT");
        graphics->configure_shader_artifacts(termin::ShaderArtifactResolver(
            artifact_root && artifact_root[0] ? artifact_root : TERMIN_GUI_NATIVE_TEST_ARTIFACT_ROOT, "", "", false));
        const auto document = tc_ui_document_create();
        Services services;
        const tc_document_renderer_config config{
            sizeof(tc_document_renderer_config), TERMIN_GUI_NATIVE_TEST_FONT, 14, 64, 48, 2.0f, &services,
            &Services::set_text_input, &Services::copy_clipboard, &Services::set_clipboard, &Services::set_cursor};
        services.renderer = tc_document_renderer_create(document, graphics.get(), &config);
        check(tc_document_renderer_is_valid(services.renderer), "renderer creation failed");
        check(services.text_input, "native renderer did not enable host text input");
        check(!tc_document_renderer_is_valid(tc_document_renderer_create(document, graphics.get(), &config)),
              "second renderer stole the document platform hooks");

        tc_ui_presentation_metrics metrics{};
        check(tc_ui_document_presentation_metrics(document, &metrics) && metrics.density_scale == 2.0f &&
                  metrics.physical_extent.width == 64 && metrics.physical_extent.height == 48,
              "initial presentation metrics were not synchronized");
        uint32_t texture = 0;
        // Render using installed precompiled artifacts, with no shader developer
        // tools or second application graphics domain.
        check(tc_document_renderer_render(services.renderer, &texture) && texture != 0,
              "renderer did not publish a texture from its borrowed device");
        const auto texture_desc = graphics->device().texture_desc(tgfx::TextureHandle{texture});
        check(texture_desc.format == tgfx::PixelFormat::RGBA16F && texture_desc.width == 64 && texture_desc.height == 48,
              "renderer output is not DisplayLinear RGBA16F on the borrowed device");
        check(!tc_document_renderer_repaint_requested(services.renderer), "completed frame remained dirty");
        check(!tc_document_renderer_set_metrics(services.renderer, 0, 40, 1.0f), "invalid metrics were accepted");
        check(tc_document_renderer_copy_last_error(services.renderer, error, sizeof(error)) > 1,
              "failed metrics update did not retain a diagnostic");
        check(tc_document_renderer_set_metrics(services.renderer, 100, 60, 1.25f) &&
                  tc_document_renderer_repaint_requested(services.renderer), "resize did not request a frame");
        check(tc_document_renderer_render(services.renderer, &texture), "render after resize failed");
        check(graphics->device().texture_desc(tgfx::TextureHandle{texture}).width == 100, "resized texture is stale");

        auto* input = new termin::gui_native::TextInput();
        termin::gui_native::TcDocument native_document(document);
        native_document.adopt(input);
        native_document.add_root(*input);
        native_document.layout_roots({0, 0, 80, 48});
        native_document.set_focus(*input);
        tc_ui_event_result result{};
        check(tc_document_renderer_dispatch_text(services.renderer, "value", &result) && input->text() == "value",
              "text event did not route through the native document");
        input->set_text("");
        const tc_ui_key_event paste{TC_UI_KEY_DOWN, TC_UI_KEY_V, 0, TC_UI_MOD_CTRL, false};
        check(tc_document_renderer_dispatch_key(services.renderer, &paste, &result) &&
                  input->text() == services.clipboard, "native paste did not copy UTF-8 clipboard data");
        check(tc_document_renderer_render(services.renderer, &texture), "native text-widget paint failed");
        const tc_ui_pointer_event pointer{TC_UI_POINTER_MOVE, 3, 3, 0, 0, 0, 0, 0, TC_UI_POINTER_CANCEL_EXPLICIT};
        check(tc_document_renderer_dispatch_pointer(services.renderer, &pointer, &result), "pointer dispatch failed");
        check(services.cursor == TC_UI_CURSOR_TEXT, "native cursor callback did not reach host");
        bool accepted_cross_thread = true;
        std::thread worker([&] {
            accepted_cross_thread = tc_document_renderer_set_metrics(services.renderer, 99, 99, 1.0f);
        });
        worker.join();
        check(!accepted_cross_thread, "renderer accepted cross-thread mutation");
        check(tc_document_renderer_set_focus(services.renderer, false) && !services.text_input &&
                  tc_widget_handle_is_invalid(tc_ui_document_focused_widget(document)), "host focus loss did not clear native focus");
        check(services.attempted_reentry, "renderer destruction was not protected against callback reentry");

        const auto stale = services.renderer;
        check(tc_document_renderer_destroy(stale), "renderer destruction failed");
        check(!tc_document_renderer_is_valid(stale) && tc_ui_document_is_valid(document) && !graphics->is_closed(),
              "renderer destruction released its borrowed document/graphics host");
        check(!tc_document_renderer_request_repaint(stale), "stale renderer handle was accepted");
        services.renderer = tc_document_renderer_create(document, graphics.get(), &config);
        check(tc_document_renderer_is_valid(services.renderer) &&
                  !tc_document_renderer_handle_eq(stale, services.renderer), "recreated renderer reused a stale generation");
        check(tc_document_renderer_destroy(services.renderer), "recreated renderer destruction failed");
        tc_ui_document_destroy(document);
        graphics->close();
        std::printf("document renderer C ABI tests passed\n");
        return 0;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "document renderer C ABI test failed: %s\n", error.what());
        return 1;
    }
}
