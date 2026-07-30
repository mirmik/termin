#include <termin/gui_native/native_widget.hpp>
#include <termin/render/execute_context.hpp>
#include <termin/render/ui_widget_pass.hpp>
#include <termin/tc_scene.hpp>

#include <tgfx2/descriptors.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/pipeline_cache.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <memory>
#include <span>
#include <string>
#include <system_error>
#include <vector>

#include <termin/ui/tc_scene_ui_document_capability.h>

namespace {

constexpr std::uint32_t kWidth = 48;
constexpr std::uint32_t kHeight = 32;

bool existing_file(const std::filesystem::path& path) {
    std::error_code error;
    return std::filesystem::is_regular_file(path, error);
}

void configure_shader_artifacts(
    const char* argv0,
    const std::filesystem::path& root
) {
    std::vector<std::filesystem::path> candidates;
    if (const char* configured = std::getenv("TERMIN_SHADERC")) {
        if (configured[0] != '\0') {
            candidates.emplace_back(configured);
        }
    }
    if (argv0 && argv0[0] != '\0') {
        std::error_code error;
        const std::filesystem::path executable_directory =
            std::filesystem::absolute(argv0, error).parent_path();
        if (!error) {
            candidates.push_back(
                executable_directory / "termin_shaderc");
        }
    }
    if (const char* sdk = std::getenv("TERMIN_SDK")) {
        if (sdk[0] != '\0') {
            candidates.push_back(
                std::filesystem::path(sdk) / "bin" / "termin_shaderc");
        }
    }
    candidates.push_back(
        std::filesystem::current_path() / "sdk" / "bin" /
        "termin_shaderc");
    for (const auto& candidate : candidates) {
        if (existing_file(candidate)) {
            termin::tgfx2_set_shader_compiler_path(
                candidate.string().c_str());
            break;
        }
    }
    termin::tgfx2_set_shader_artifact_root(root.string().c_str());
    termin::tgfx2_set_shader_cache_root(
        (root / ".cache").string().c_str());
    termin::tgfx2_set_shader_dev_compile_enabled(true);
}

struct ScopedTempDirectory {
    std::filesystem::path path;

    ~ScopedTempDirectory() {
        std::error_code error;
        std::filesystem::remove_all(path, error);
    }
};

class RedCornerWidget final
    : public termin::gui_native::NativeWidget {
public:
    void paint(
        tc_ui_document_handle,
        tc_ui_paint_context* painter
    ) override {
        tc_ui_painter_fill_rect(
            painter,
            tc_ui_rect{
                0.0f,
                0.0f,
                static_cast<float>(kWidth),
                static_cast<float>(kHeight)},
            tc_ui_color{0.0f, 0.0f, 0.0f, 0.0f});
        tc_ui_painter_fill_rect(
            painter,
            tc_ui_rect{0.0f, 0.0f, 12.0f, 12.0f},
            tc_ui_color{0.9f, 0.05f, 0.05f, 1.0f});
    }
};

struct ProbeDocument {
    tc_ui_document_handle handle = tc_ui_document_create();
    termin::gui_native::TcDocument document{handle};

    ProbeDocument() {
        const tc_widget_handle root =
            document.adopt(new RedCornerWidget());
        if (tc_widget_handle_is_invalid(root) ||
            !tc_ui_document_add_root(handle, root)) {
            throw std::runtime_error(
                "failed to create UIWidgetPass probe document");
        }
    }

    ~ProbeDocument() {
        if (tc_ui_document_is_valid(handle)) {
            tc_ui_document_destroy(handle);
        }
    }
};

class ProbeUiComponent final : public termin::CxxComponent {
public:
    explicit ProbeUiComponent(
        termin::gui_native::TcDocument document
    ) : CxxComponent("ProbeUiComponent"),
        document_(document) {
        if (!tc_scene_ui_document_capability_attach(
                tc_component_ptr(), &kVtable, this)) {
            throw std::runtime_error(
                "failed to attach probe scene UI capability");
        }
    }

private:
    static bool get_snapshot(
        tc_component* component,
        tc_scene_ui_document_snapshot* out_snapshot
    ) {
        auto* base = termin::CxxComponent::from_tc(component);
        auto* self = dynamic_cast<ProbeUiComponent*>(base);
        if (!self || !out_snapshot) {
            return false;
        }
        out_snapshot->document = self->document_.handle();
        out_snapshot->priority = 10;
        return self->document_.valid();
    }

    static constexpr tc_scene_ui_document_vtable kVtable{
        .get_snapshot = get_snapshot,
    };
    termin::gui_native::TcDocument document_;
};

bool looks_green(const float pixel[4]) {
    return pixel[0] < 0.2f && pixel[1] > 0.65f &&
        pixel[2] < 0.2f && pixel[3] > 0.9f;
}

bool looks_red(const float pixel[4]) {
    return pixel[0] > 0.65f && pixel[1] < 0.2f &&
        pixel[2] < 0.2f && pixel[3] > 0.9f;
}

bool render_and_check(
    tgfx::IRenderDevice& device,
    tgfx::RenderContext2& render_context,
    termin::UIWidgetPass& pass,
    termin::TcSceneRef scene,
    tgfx::TextureHandle input,
    tgfx::TextureHandle output
) {
    const float green[]{0.05f, 0.8f, 0.1f, 1.0f};
    render_context.begin_frame();
    render_context.begin_pass(input, {}, green, 1.0f, false);
    render_context.end_pass();

    termin::ExecuteContext ctx;
    ctx.ctx2 = &render_context;
    ctx.scene = scene;
    ctx.render_rect = {0, 0, kWidth, kHeight};
    ctx.tex2_reads.emplace(pass.input_res, input);
    ctx.tex2_writes.emplace(pass.output_res, output);
    pass.execute(ctx);
    render_context.end_frame();
    device.wait_idle();

    float inside[4]{};
    float outside[4]{};
    return device.read_pixel_rgba8(output, 4, 4, inside) &&
        device.read_pixel_rgba8(output, 30, 20, outside) &&
        looks_red(inside) && looks_green(outside);
}

} // namespace

int main(int argc, char** argv) {
    const auto unique =
        std::chrono::steady_clock::now().time_since_epoch().count();
    const ScopedTempDirectory artifacts{
        std::filesystem::temp_directory_path() /
        ("termin-ui-widget-pass-smoke-" + std::to_string(unique))};
    configure_shader_artifacts(argc > 0 ? argv[0] : nullptr, artifacts.path);

    std::unique_ptr<tgfx::IRenderDevice> device;
    try {
        device = tgfx::create_device(tgfx::BackendType::Vulkan);
    } catch (const std::exception& error) {
        std::fprintf(
            stderr, "Failed to create Vulkan device: %s\n", error.what());
        return 1;
    }

    tgfx::TextureDesc description{};
    description.width = kWidth;
    description.height = kHeight;
    description.format = tgfx::PixelFormat::RGBA8_UNorm;
    description.usage =
        tgfx::TextureUsage::ColorAttachment |
        tgfx::TextureUsage::CopySrc |
        tgfx::TextureUsage::CopyDst;
    const tgfx::TextureHandle input =
        device->create_texture(description);
    const tgfx::TextureHandle output =
        device->create_texture(description);
    if (!input || !output) {
        std::fprintf(stderr, "Failed to create UIWidgetPass smoke textures\n");
        return 1;
    }

    ProbeDocument document;
    termin::TcSceneRef scene =
        termin::TcSceneRef::create("ui-widget-pass-pixel-smoke");
    termin::Entity entity = scene.create_entity("UI");
    entity.add_component(new ProbeUiComponent(document.document));

    tgfx::PipelineCache cache(*device);
    tgfx::RenderContext2 render_context(*device, cache);
    termin::UIWidgetPass pass("input", "output");
    const bool distinct_ok = render_and_check(
        *device, render_context, pass, scene, input, output);
    const bool inplace_ok = render_and_check(
        *device, render_context, pass, scene, input, input);

    pass.destroy();
    scene.destroy();
    device->destroy(output);
    device->destroy(input);

    if (!distinct_ok || !inplace_ok) {
        std::fprintf(
            stderr,
            "UIWidgetPass target-load smoke failed: distinct=%d inplace=%d\n",
            distinct_ok,
            inplace_ok);
        return 1;
    }
    return 0;
}
