#include "termin/android/bootstrap.h"

#include <mutex>
#include <memory>
#include <string>
#include <stdexcept>
#include <cstdarg>
#include <cstdint>
#include <cmath>
#include <fstream>
#include <vector>

#ifdef __ANDROID__
#include <android/log.h>
#endif

#include <tcbase/tc_log.h>
#include <tgfx2/tc_shader_bridge.hpp>

#ifdef __ANDROID__
#ifndef VK_USE_PLATFORM_ANDROID_KHR
#define VK_USE_PLATFORM_ANDROID_KHR
#endif
#include <vulkan/vulkan.h>
#include <vulkan/vulkan_android.h>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/i_command_list.hpp>
#include <tgfx2/vulkan/vulkan_render_device.hpp>
#include <tgfx2/vulkan/vulkan_swapchain.hpp>
#endif

namespace {

struct AndroidBootstrapState {
    std::string app_data_dir;
    std::string asset_root;
    std::string native_lib_dir;
    ANativeWindow* window = nullptr;
    int32_t surface_width = 0;
    int32_t surface_height = 0;
    bool initialized = false;
#ifdef __ANDROID__
    std::unique_ptr<tgfx::VulkanRenderDevice> smoke_device;
    tgfx::ShaderHandle smoke_vertex_shader;
    tgfx::ShaderHandle smoke_fragment_shader;
    tgfx::PipelineHandle smoke_pipeline;
    tgfx::BufferHandle smoke_vertex_buffer;
    tgfx::BufferHandle smoke_index_buffer;
    tgfx::TextureHandle smoke_render_target;
    tgfx::TextureHandle smoke_depth_target;
    uint32_t smoke_width = 0;
    uint32_t smoke_height = 0;
    uint32_t smoke_frame = 0;
    bool smoke_create_failed = false;
#endif
};

std::mutex g_state_mutex;
AndroidBootstrapState g_state;

#ifdef __ANDROID__
constexpr const char* kAndroidLogTag = "TerminAndroid";

void android_log_info(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    __android_log_vprint(ANDROID_LOG_INFO, kAndroidLogTag, fmt, args);
    va_end(args);
}

void android_log_error(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    __android_log_vprint(ANDROID_LOG_ERROR, kAndroidLogTag, fmt, args);
    va_end(args);
}
#else
void android_log_info(const char*, ...) {}
void android_log_error(const char*, ...) {}
#endif

#ifdef __ANDROID__
void reset_smoke_resources_locked() {
    g_state.smoke_vertex_shader = {};
    g_state.smoke_fragment_shader = {};
    g_state.smoke_pipeline = {};
    g_state.smoke_vertex_buffer = {};
    g_state.smoke_index_buffer = {};
    g_state.smoke_render_target = {};
    g_state.smoke_depth_target = {};
}

void destroy_smoke_resources_locked() {
    if (!g_state.smoke_device) {
        reset_smoke_resources_locked();
        return;
    }

    auto& device = *g_state.smoke_device;
    if (g_state.smoke_pipeline) {
        device.destroy(g_state.smoke_pipeline);
    }
    if (g_state.smoke_index_buffer) {
        device.destroy(g_state.smoke_index_buffer);
    }
    if (g_state.smoke_vertex_buffer) {
        device.destroy(g_state.smoke_vertex_buffer);
    }
    if (g_state.smoke_render_target) {
        device.destroy(g_state.smoke_render_target);
    }
    if (g_state.smoke_depth_target) {
        device.destroy(g_state.smoke_depth_target);
    }
    if (g_state.smoke_fragment_shader) {
        device.destroy(g_state.smoke_fragment_shader);
    }
    if (g_state.smoke_vertex_shader) {
        device.destroy(g_state.smoke_vertex_shader);
    }
    reset_smoke_resources_locked();
}

std::vector<uint8_t> read_asset_file_locked(const char* relative_path) {
    std::string path = g_state.asset_root;
    if (!path.empty() && path.back() != '/') {
        path.push_back('/');
    }
    path += relative_path;

    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("failed to open asset file: " + path);
    }
    in.seekg(0, std::ios::end);
    std::streamoff size = in.tellg();
    if (size <= 0) {
        throw std::runtime_error("asset file is empty: " + path);
    }
    in.seekg(0, std::ios::beg);

    std::vector<uint8_t> bytes(static_cast<size_t>(size));
    in.read(reinterpret_cast<char*>(bytes.data()), size);
    if (!in) {
        throw std::runtime_error("failed to read asset file: " + path);
    }
    android_log_info("smoke: loaded shader asset '%s' bytes=%zu", path.c_str(), bytes.size());
    return bytes;
}

struct Mat4 {
    float v[16] = {};
};

Mat4 mat4_identity() {
    Mat4 out;
    out.v[0] = 1.0f;
    out.v[5] = 1.0f;
    out.v[10] = 1.0f;
    out.v[15] = 1.0f;
    return out;
}

Mat4 mat4_mul(const Mat4& a, const Mat4& b) {
    Mat4 out;
    for (int col = 0; col < 4; ++col) {
        for (int row = 0; row < 4; ++row) {
            float sum = 0.0f;
            for (int k = 0; k < 4; ++k) {
                sum += a.v[k * 4 + row] * b.v[col * 4 + k];
            }
            out.v[col * 4 + row] = sum;
        }
    }
    return out;
}

Mat4 mat4_translation(float x, float y, float z) {
    Mat4 out = mat4_identity();
    out.v[12] = x;
    out.v[13] = y;
    out.v[14] = z;
    return out;
}

Mat4 mat4_rotation_x(float radians) {
    Mat4 out = mat4_identity();
    float c = std::cos(radians);
    float s = std::sin(radians);
    out.v[5] = c;
    out.v[6] = s;
    out.v[9] = -s;
    out.v[10] = c;
    return out;
}

Mat4 mat4_rotation_y(float radians) {
    Mat4 out = mat4_identity();
    float c = std::cos(radians);
    float s = std::sin(radians);
    out.v[0] = c;
    out.v[2] = -s;
    out.v[8] = s;
    out.v[10] = c;
    return out;
}

Mat4 mat4_perspective(float fovy_radians, float aspect, float near_z, float far_z) {
    Mat4 out;
    float f = 1.0f / std::tan(fovy_radians * 0.5f);
    out.v[0] = f / aspect;
    out.v[5] = -f;
    out.v[10] = far_z / (near_z - far_z);
    out.v[11] = -1.0f;
    out.v[14] = (far_z * near_z) / (near_z - far_z);
    return out;
}

Mat4 smoke_mvp_locked() {
    constexpr float kPi = 3.14159265358979323846f;
    float aspect = 1.0f;
    if (g_state.smoke_height != 0) {
        aspect = static_cast<float>(g_state.smoke_width) / static_cast<float>(g_state.smoke_height);
    }
    float t = static_cast<float>(g_state.smoke_frame) * 0.22f;
    Mat4 projection = mat4_perspective(55.0f * kPi / 180.0f, aspect, 0.1f, 20.0f);
    Mat4 view = mat4_translation(0.0f, 0.0f, -3.0f);
    Mat4 model = mat4_mul(mat4_rotation_y(t), mat4_rotation_x(t * 0.67f));
    return mat4_mul(projection, mat4_mul(view, model));
}

bool create_smoke_mesh_resources_locked() {
    if (!g_state.smoke_device) {
        android_log_error("smoke: cannot create mesh resources without Vulkan device");
        tc_log_error("termin_android_smoke: cannot create mesh resources without Vulkan device");
        return false;
    }
    if (g_state.smoke_width == 0 || g_state.smoke_height == 0) {
        android_log_error("smoke: cannot create mesh resources for empty swapchain");
        tc_log_error("termin_android_smoke: cannot create mesh resources for empty swapchain");
        return false;
    }

    auto& device = *g_state.smoke_device;

    tgfx::ShaderDesc vs_desc;
    vs_desc.stage = tgfx::ShaderStage::Vertex;
    vs_desc.debug_name = "android_smoke_cube_vs";
    vs_desc.bytecode = read_asset_file_locked("shaders/android_smoke_cube.vert.spv");
    g_state.smoke_vertex_shader = device.create_shader(vs_desc);

    tgfx::ShaderDesc fs_desc;
    fs_desc.stage = tgfx::ShaderStage::Fragment;
    fs_desc.debug_name = "android_smoke_cube_fs";
    fs_desc.bytecode = read_asset_file_locked("shaders/android_smoke_cube.frag.spv");
    g_state.smoke_fragment_shader = device.create_shader(fs_desc);

    tgfx::TextureDesc rt_desc;
    rt_desc.width = g_state.smoke_width;
    rt_desc.height = g_state.smoke_height;
    rt_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
    rt_desc.usage = tgfx::TextureUsage::ColorAttachment |
                    tgfx::TextureUsage::CopySrc |
                    tgfx::TextureUsage::Sampled;
    g_state.smoke_render_target = device.create_texture(rt_desc);

    tgfx::TextureDesc depth_desc;
    depth_desc.width = g_state.smoke_width;
    depth_desc.height = g_state.smoke_height;
    depth_desc.format = tgfx::PixelFormat::D32F;
    depth_desc.usage = tgfx::TextureUsage::DepthStencilAttachment;
    g_state.smoke_depth_target = device.create_texture(depth_desc);

    tgfx::PipelineDesc pipeline_desc;
    pipeline_desc.vertex_shader = g_state.smoke_vertex_shader;
    pipeline_desc.fragment_shader = g_state.smoke_fragment_shader;
    pipeline_desc.topology = tgfx::PrimitiveTopology::TriangleList;
    pipeline_desc.depth_stencil.depth_test = true;
    pipeline_desc.depth_stencil.depth_write = true;
    pipeline_desc.depth_stencil.depth_compare = tgfx::CompareOp::Less;
    pipeline_desc.raster.cull = tgfx::CullMode::None;
    pipeline_desc.color_formats = {tgfx::PixelFormat::RGBA8_UNorm};
    pipeline_desc.depth_format = tgfx::PixelFormat::D32F;

    tgfx::VertexBufferLayout layout;
    layout.stride = 6 * sizeof(float);
    layout.attributes = {
        {0, tgfx::VertexFormat::Float3, 0},
        {1, tgfx::VertexFormat::Float3, 3 * sizeof(float)},
    };
    pipeline_desc.vertex_layouts.push_back(layout);
    g_state.smoke_pipeline = device.create_pipeline(pipeline_desc);

    const float vertices[] = {
        -0.55f, -0.55f, -0.55f,  0.95f, 0.10f, 0.10f,
         0.55f, -0.55f, -0.55f,  0.95f, 0.70f, 0.10f,
         0.55f,  0.55f, -0.55f,  0.95f, 0.95f, 0.10f,
        -0.55f,  0.55f, -0.55f,  0.15f, 0.85f, 0.20f,
        -0.55f, -0.55f,  0.55f,  0.10f, 0.70f, 0.95f,
         0.55f, -0.55f,  0.55f,  0.25f, 0.25f, 1.00f,
         0.55f,  0.55f,  0.55f,  0.90f, 0.20f, 0.95f,
        -0.55f,  0.55f,  0.55f,  0.80f, 0.80f, 1.00f,
    };
    tgfx::BufferDesc vb_desc;
    vb_desc.size = sizeof(vertices);
    vb_desc.usage = tgfx::BufferUsage::Vertex;
    vb_desc.cpu_visible = true;
    g_state.smoke_vertex_buffer = device.create_buffer(vb_desc);
    device.upload_buffer(
        g_state.smoke_vertex_buffer,
        {reinterpret_cast<const uint8_t*>(vertices), sizeof(vertices)}
    );

    const uint32_t indices[] = {
        4, 5, 6,  4, 6, 7,
        1, 0, 3,  1, 3, 2,
        0, 4, 7,  0, 7, 3,
        5, 1, 2,  5, 2, 6,
        3, 7, 6,  3, 6, 2,
        0, 1, 5,  0, 5, 4,
    };
    tgfx::BufferDesc ib_desc;
    ib_desc.size = sizeof(indices);
    ib_desc.usage = tgfx::BufferUsage::Index;
    ib_desc.cpu_visible = true;
    g_state.smoke_index_buffer = device.create_buffer(ib_desc);
    device.upload_buffer(
        g_state.smoke_index_buffer,
        {reinterpret_cast<const uint8_t*>(indices), sizeof(indices)}
    );

    android_log_info(
        "smoke: cube resources created rt=%ux%u vs=%u fs=%u pipeline=%u vb=%u ib=%u",
        g_state.smoke_width,
        g_state.smoke_height,
        g_state.smoke_vertex_shader.id,
        g_state.smoke_fragment_shader.id,
        g_state.smoke_pipeline.id,
        g_state.smoke_vertex_buffer.id,
        g_state.smoke_index_buffer.id
    );
    tc_log_info(
        "termin_android_smoke: cube resources created rt=%ux%u pipeline=%u",
        g_state.smoke_width,
        g_state.smoke_height,
        g_state.smoke_pipeline.id
    );
    return true;
}
#endif

void destroy_smoke_renderer_locked() {
#ifdef __ANDROID__
    if (g_state.smoke_device) {
        android_log_info("smoke: destroy renderer");
        try {
            destroy_smoke_resources_locked();
            g_state.smoke_device->wait_idle();
        } catch (const std::exception& e) {
            android_log_error("smoke: destroy failed: %s", e.what());
            tc_log_error("termin_android_smoke: destroy failed: %s", e.what());
        }
    }
    g_state.smoke_device.reset();
    reset_smoke_resources_locked();
    g_state.smoke_width = 0;
    g_state.smoke_height = 0;
    g_state.smoke_frame = 0;
#endif
}

void release_window_locked() {
    destroy_smoke_renderer_locked();
#ifdef __ANDROID__
    if (g_state.window) {
        ANativeWindow_release(g_state.window);
    }
#endif
    g_state.window = nullptr;
    g_state.surface_width = 0;
    g_state.surface_height = 0;
#ifdef __ANDROID__
    g_state.smoke_create_failed = false;
#endif
}

#ifdef __ANDROID__
bool create_smoke_renderer_locked() {
    if (g_state.smoke_create_failed) {
        android_log_info("smoke: create skipped after earlier failure on this surface");
        return false;
    }
    if (!g_state.window) {
        android_log_error("smoke: cannot create renderer without ANativeWindow");
        tc_log_error("termin_android_smoke: cannot create renderer without ANativeWindow");
        return false;
    }
    if (g_state.surface_width <= 0 || g_state.surface_height <= 0) {
        android_log_error(
            "smoke: invalid surface size %dx%d",
            static_cast<int>(g_state.surface_width),
            static_cast<int>(g_state.surface_height)
        );
        tc_log_error(
            "termin_android_smoke: invalid surface size %dx%d",
            static_cast<int>(g_state.surface_width),
            static_cast<int>(g_state.surface_height)
        );
        return false;
    }

    destroy_smoke_renderer_locked();

    try {
        android_log_info(
            "smoke: create Vulkan renderer for surface=%p size=%dx%d",
            static_cast<void*>(g_state.window),
            static_cast<int>(g_state.surface_width),
            static_cast<int>(g_state.surface_height)
        );
        tgfx::VulkanDeviceCreateInfo info{};
        info.enable_validation = false;
        info.instance_extensions = {
            VK_KHR_SURFACE_EXTENSION_NAME,
            VK_KHR_ANDROID_SURFACE_EXTENSION_NAME,
        };
        info.swapchain_width = static_cast<uint32_t>(g_state.surface_width);
        info.swapchain_height = static_cast<uint32_t>(g_state.surface_height);
        ANativeWindow* window = g_state.window;
        info.surface_factory = [window](VkInstance instance) -> VkSurfaceKHR {
            VkAndroidSurfaceCreateInfoKHR ci{};
            ci.sType = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
            ci.window = window;
            VkSurfaceKHR surface = VK_NULL_HANDLE;
            VkResult result = vkCreateAndroidSurfaceKHR(instance, &ci, nullptr, &surface);
            if (result != VK_SUCCESS) {
                android_log_error(
                    "smoke: vkCreateAndroidSurfaceKHR failed result=%d",
                    static_cast<int>(result)
                );
                tc_log_error(
                    "termin_android_smoke: vkCreateAndroidSurfaceKHR failed result=%d",
                    static_cast<int>(result)
                );
                return VK_NULL_HANDLE;
            }
            return surface;
        };

        g_state.smoke_device = std::make_unique<tgfx::VulkanRenderDevice>(info);

        g_state.smoke_width = g_state.smoke_device->swapchain()->width();
        g_state.smoke_height = g_state.smoke_device->swapchain()->height();

        android_log_info(
            "smoke: Vulkan renderer created swapchain=%ux%u images=%u",
            g_state.smoke_width,
            g_state.smoke_height,
            g_state.smoke_device->swapchain()->image_count()
        );
        tc_log_info(
            "termin_android_smoke: Vulkan renderer created swapchain=%ux%u images=%u",
            g_state.smoke_width,
            g_state.smoke_height,
            g_state.smoke_device->swapchain()->image_count()
        );
        if (!create_smoke_mesh_resources_locked()) {
            throw std::runtime_error("failed to create smoke mesh resources");
        }
        return true;
    } catch (const std::exception& e) {
        android_log_error("smoke: create failed: %s", e.what());
        tc_log_error("termin_android_smoke: create failed: %s", e.what());
        destroy_smoke_renderer_locked();
        g_state.smoke_create_failed = true;
        return false;
    }
}

int render_smoke_frame_locked() {
    if (!g_state.smoke_device) {
        if (!create_smoke_renderer_locked()) {
            return 0;
        }
    }
    if (!g_state.smoke_device || !g_state.smoke_device->swapchain()) {
        android_log_error("smoke: renderer is not ready");
        tc_log_error("termin_android_smoke: renderer is not ready");
        return 0;
    }

    try {
        auto& device = *g_state.smoke_device;
        auto cmd = device.create_command_list();
        cmd->begin();

        tgfx::RenderPassDesc pass;
        tgfx::ColorAttachmentDesc color_att;
        color_att.texture = g_state.smoke_render_target;
        color_att.load = tgfx::LoadOp::Clear;
        color_att.clear_color[0] = 0.015f;
        color_att.clear_color[1] = 0.020f;
        color_att.clear_color[2] = 0.035f;
        color_att.clear_color[3] = 1.0f;
        pass.colors.push_back(color_att);
        pass.depth.texture = g_state.smoke_depth_target;
        pass.depth.load = tgfx::LoadOp::Clear;
        pass.depth.clear_depth = 1.0f;
        pass.has_depth = true;

        cmd->begin_render_pass(pass);
        cmd->set_viewport(0, 0, static_cast<int>(g_state.smoke_width), static_cast<int>(g_state.smoke_height));
        cmd->set_scissor(0, 0, static_cast<int>(g_state.smoke_width), static_cast<int>(g_state.smoke_height));
        cmd->bind_pipeline(g_state.smoke_pipeline);
        Mat4 mvp = smoke_mvp_locked();
        cmd->set_push_constants(mvp.v, static_cast<uint32_t>(sizeof(mvp.v)));
        cmd->bind_vertex_buffer(0, g_state.smoke_vertex_buffer);
        cmd->bind_index_buffer(g_state.smoke_index_buffer, tgfx::IndexType::Uint32);
        cmd->draw_indexed(36);
        cmd->end_render_pass();

        cmd->end();
        device.submit(*cmd);

        bool recreate = device.swapchain()->compose_and_present(g_state.smoke_render_target);
        ++g_state.smoke_frame;
        android_log_info(
            "smoke: rendered cube frame=%u recreate=%d",
            g_state.smoke_frame,
            recreate ? 1 : 0
        );
        tc_log_info(
            "termin_android_smoke: rendered cube frame=%u recreate=%d",
            g_state.smoke_frame,
            recreate ? 1 : 0
        );
        if (recreate) {
            destroy_smoke_renderer_locked();
        }
        return 1;
    } catch (const std::exception& e) {
        android_log_error("smoke: render failed: %s", e.what());
        tc_log_error("termin_android_smoke: render failed: %s", e.what());
        destroy_smoke_renderer_locked();
        return 0;
    }
}
#endif

} // namespace

extern "C" int termin_android_initialize(const termin_android_config* config) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    if (!config) {
        android_log_error("initialize: config is NULL");
        tc_log_error("termin_android_initialize: config is NULL");
        return 0;
    }

    g_state.app_data_dir = config->app_data_dir ? config->app_data_dir : "";
    g_state.asset_root = config->asset_root ? config->asset_root : "";
    g_state.native_lib_dir = config->native_lib_dir ? config->native_lib_dir : "";
    g_state.initialized = true;

    if (!g_state.asset_root.empty()) {
        termin::tgfx2_set_shader_artifact_root(g_state.asset_root.c_str());
    }

    android_log_info(
        "initialize: app_data_dir='%s', asset_root='%s', native_lib_dir='%s'",
        g_state.app_data_dir.c_str(),
        g_state.asset_root.c_str(),
        g_state.native_lib_dir.c_str()
    );
    tc_log_info(
        "termin_android_initialize: app_data_dir='%s', asset_root='%s', native_lib_dir='%s'",
        g_state.app_data_dir.c_str(),
        g_state.asset_root.c_str(),
        g_state.native_lib_dir.c_str()
    );
    return 1;
}

extern "C" void termin_android_shutdown(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    g_state.app_data_dir.clear();
    g_state.asset_root.clear();
    g_state.native_lib_dir.clear();
    g_state.initialized = false;
    termin::tgfx2_set_shader_artifact_root(nullptr);
    android_log_info("shutdown");
    tc_log_info("termin_android_shutdown");
}

extern "C" void termin_android_set_shader_artifact_root(const char* root) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    g_state.asset_root = root ? root : "";
    termin::tgfx2_set_shader_artifact_root(g_state.asset_root.c_str());
    tc_log_info("termin_android_set_shader_artifact_root: '%s'", g_state.asset_root.c_str());
}

extern "C" const char* termin_android_get_shader_artifact_root(void) {
    return termin::tgfx2_get_shader_artifact_root();
}

extern "C" void termin_android_on_surface_created(ANativeWindow* window) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    if (!window) {
        android_log_error("surface_created: window is NULL");
        tc_log_error("termin_android_on_surface_created: window is NULL");
        return;
    }

#ifdef __ANDROID__
    ANativeWindow_acquire(window);
    g_state.surface_width = ANativeWindow_getWidth(window);
    g_state.surface_height = ANativeWindow_getHeight(window);
#endif
    g_state.window = window;
#ifdef __ANDROID__
    g_state.smoke_create_failed = false;
#endif
    android_log_info(
        "surface_created: window=%p size=%dx%d; waiting for surfaceChanged before render",
        static_cast<void*>(window),
        static_cast<int>(g_state.surface_width),
        static_cast<int>(g_state.surface_height)
    );
    tc_log_info(
        "termin_android_on_surface_created: window=%p size=%dx%d",
        static_cast<void*>(window),
        static_cast<int>(g_state.surface_width),
        static_cast<int>(g_state.surface_height)
    );
}

extern "C" void termin_android_on_surface_changed(int32_t width, int32_t height) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    bool size_changed = g_state.surface_width != width || g_state.surface_height != height;
    g_state.surface_width = width;
    g_state.surface_height = height;
    android_log_info(
        "surface_changed: size=%dx%d size_changed=%d",
        static_cast<int>(width),
        static_cast<int>(height),
        size_changed ? 1 : 0
    );
    tc_log_info(
        "termin_android_on_surface_changed: size=%dx%d",
        static_cast<int>(width),
        static_cast<int>(height)
    );
    if (size_changed) {
        destroy_smoke_renderer_locked();
    }
    render_smoke_frame_locked();
}

extern "C" void termin_android_on_surface_destroyed(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    release_window_locked();
    android_log_info("surface_destroyed");
    tc_log_info("termin_android_on_surface_destroyed");
}

extern "C" int termin_android_smoke_render(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
#ifdef __ANDROID__
    android_log_info("smoke_render requested");
    return render_smoke_frame_locked();
#else
    tc_log_error("termin_android_smoke_render: only supported on Android");
    return 0;
#endif
}

extern "C" ANativeWindow* termin_android_native_window(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.window;
}

extern "C" int32_t termin_android_surface_width(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.surface_width;
}

extern "C" int32_t termin_android_surface_height(void) {
    std::lock_guard<std::mutex> lock(g_state_mutex);
    return g_state.surface_height;
}
