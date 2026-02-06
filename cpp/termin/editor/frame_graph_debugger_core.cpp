#include "frame_graph_debugger_core.hpp"
#include "termin/render/frame_pass.hpp"

extern "C" {
#include "tc_log.h"
}

#include <algorithm>
#include <cmath>

namespace termin {

// ============================================================
// FrameGraphCapture
// ============================================================

void FrameGraphCapture::capture(CxxFramePass* caller, FramebufferHandle* src, GraphicsBackend* graphics) {
    if (!should_capture(caller)) {
        return;
    }
    capture_direct(src, graphics);
}

void FrameGraphCapture::capture_direct(FramebufferHandle* src, GraphicsBackend* graphics) {
    if (!src || !graphics) {
        return;
    }
    ensure_capture_fbo(src, graphics);
    if (!capture_fbo_) {
        return;
    }
    do_blit(src, graphics);
    captured_ = true;
}

void FrameGraphCapture::ensure_capture_fbo(FramebufferHandle* src, GraphicsBackend* graphics) {
    int w = src->get_width();
    int h = src->get_height();
    std::string fmt = src->get_format();

    if (capture_fbo_ && fbo_w_ == w && fbo_h_ == h && fbo_format_ == fmt) {
        return;
    }

    // Recreate: always non-MSAA (samples=1), copy format from source
    capture_fbo_ = graphics->create_framebuffer(w, h, 1, fmt);
    fbo_w_ = w;
    fbo_h_ = h;
    fbo_format_ = fmt;
}

void FrameGraphCapture::do_blit(FramebufferHandle* src, GraphicsBackend* graphics) {
    int w = src->get_width();
    int h = src->get_height();

    // blit_framebuffer handles MSAA resolve automatically when
    // src is MSAA and dst is non-MSAA
    graphics->blit_framebuffer(
        src, capture_fbo_.get(),
        0, 0, w, h,
        0, 0, w, h,
        true,  // blit_color
        true   // blit_depth
    );
}

// ============================================================
// FrameGraphPresenter
// ============================================================

void FrameGraphPresenter::ensure_shader() {
    if (shader_ready_) {
        return;
    }

    const char* vert_src = R"(
        #version 330 core
        layout(location = 0) in vec2 a_pos;
        layout(location = 1) in vec2 a_uv;
        out vec2 v_uv;
        void main() {
            v_uv = a_uv;
            gl_Position = vec4(a_pos, 0.0, 1.0);
        }
    )";

    const char* frag_src = R"(
        #version 330 core
        in vec2 v_uv;
        uniform sampler2D u_tex;
        uniform int u_channel;  // 0=RGB, 1=R, 2=G, 3=B, 4=A
        uniform int u_highlight_hdr;  // 1=highlight pixels > 1.0
        out vec4 FragColor;
        void main() {
            vec4 c = texture(u_tex, v_uv);
            vec3 result;

            if (u_channel == 1) {
                result = vec3(c.r);
            } else if (u_channel == 2) {
                result = vec3(c.g);
            } else if (u_channel == 3) {
                result = vec3(c.b);
            } else if (u_channel == 4) {
                result = vec3(c.a);
            } else {
                result = c.rgb;
            }

            // HDR highlight: show pixels > 1.0 with magenta overlay
            if (u_highlight_hdr == 1) {
                float maxVal = max(max(c.r, c.g), c.b);
                if (maxVal > 1.0) {
                    float intensity = clamp((maxVal - 1.0) / 2.0, 0.0, 1.0);
                    result = mix(result, vec3(1.0, 0.0, 1.0), 0.5 + intensity * 0.5);
                }
            }

            FragColor = vec4(result, 1.0);
        }
    )";

    shader_ = TcShader::from_sources(vert_src, frag_src, "", "FrameGraphDebuggerPresenter");
    shader_ready_ = shader_.is_valid();
    if (!shader_ready_) {
        tc::Log::error("FrameGraphPresenter: failed to create shader");
    }
}

void FrameGraphPresenter::render(
    GraphicsBackend* graphics,
    FramebufferHandle* capture_fbo,
    int dst_w, int dst_h,
    int channel_mode,
    bool highlight_hdr
) {
    if (!graphics || !capture_fbo) {
        return;
    }

    ensure_shader();
    if (!shader_ready_) {
        return;
    }

    GPUTextureHandle* tex = capture_fbo->color_texture();
    if (!tex) {
        return;
    }

    graphics->set_viewport(0, 0, dst_w, dst_h);
    graphics->clear_color(0.1f, 0.1f, 0.1f, 1.0f);

    graphics->set_depth_test(false);
    graphics->set_depth_mask(false);

    shader_.use();
    shader_.set_uniform_int("u_tex", 0);
    shader_.set_uniform_int("u_channel", channel_mode);
    shader_.set_uniform_int("u_highlight_hdr", highlight_hdr ? 1 : 0);

    tex->bind(0);
    graphics->draw_ui_textured_quad();

    graphics->set_depth_test(true);
    graphics->set_depth_mask(true);
}

HDRStats FrameGraphPresenter::compute_hdr_stats(GraphicsBackend* graphics, FramebufferHandle* fbo) {
    HDRStats stats{};

    if (!graphics || !fbo) {
        return stats;
    }

    int w = fbo->get_width();
    int h = fbo->get_height();
    int total = w * h;

    if (total <= 0) {
        return stats;
    }

    // Read color buffer as floats (RGBA)
    std::vector<float> pixels(total * 4);
    if (!graphics->read_color_buffer_float(fbo, pixels.data())) {
        tc::Log::error("FrameGraphPresenter: read_color_buffer_float failed");
        return stats;
    }

    stats.total_pixels = total;

    // Initialize with first pixel
    float r0 = pixels[0], g0 = pixels[1], b0 = pixels[2];
    stats.min_r = r0; stats.max_r = r0; stats.avg_r = 0;
    stats.min_g = g0; stats.max_g = g0; stats.avg_g = 0;
    stats.min_b = b0; stats.max_b = b0; stats.avg_b = 0;

    double sum_r = 0, sum_g = 0, sum_b = 0;
    int hdr_count = 0;
    float max_val = 0;

    for (int i = 0; i < total; ++i) {
        float r = pixels[i * 4 + 0];
        float g = pixels[i * 4 + 1];
        float b = pixels[i * 4 + 2];

        if (r < stats.min_r) stats.min_r = r;
        if (r > stats.max_r) stats.max_r = r;
        if (g < stats.min_g) stats.min_g = g;
        if (g > stats.max_g) stats.max_g = g;
        if (b < stats.min_b) stats.min_b = b;
        if (b > stats.max_b) stats.max_b = b;

        sum_r += r;
        sum_g += g;
        sum_b += b;

        float mx = std::max({r, g, b});
        if (mx > max_val) max_val = mx;
        if (mx > 1.0f) ++hdr_count;
    }

    stats.avg_r = static_cast<float>(sum_r / total);
    stats.avg_g = static_cast<float>(sum_g / total);
    stats.avg_b = static_cast<float>(sum_b / total);
    stats.hdr_pixel_count = hdr_count;
    stats.hdr_percent = (total > 0) ? (static_cast<float>(hdr_count) / total * 100.0f) : 0.0f;
    stats.max_value = max_val;

    return stats;
}

std::vector<uint8_t> FrameGraphPresenter::read_depth_normalized(
    GraphicsBackend* graphics, FramebufferHandle* fbo,
    int* out_w, int* out_h
) {
    if (out_w) *out_w = 0;
    if (out_h) *out_h = 0;

    if (!graphics || !fbo) {
        return {};
    }

    int w = fbo->get_width();
    int h = fbo->get_height();
    int total = w * h;

    if (total <= 0) {
        return {};
    }

    std::vector<float> depth(total);
    if (!graphics->read_depth_buffer(fbo, depth.data())) {
        tc::Log::error("FrameGraphPresenter: read_depth_buffer failed");
        return {};
    }

    // Find min/max (ignoring NaN/Inf)
    float d_min = 1.0f, d_max = 0.0f;
    for (int i = 0; i < total; ++i) {
        float d = depth[i];
        if (std::isnan(d) || std::isinf(d)) continue;
        if (d < d_min) d_min = d;
        if (d > d_max) d_max = d;
    }

    float range = d_max - d_min;
    std::vector<uint8_t> result(total);

    for (int i = 0; i < total; ++i) {
        float d = depth[i];
        if (std::isnan(d) || std::isinf(d)) {
            result[i] = 0;
            continue;
        }
        float norm = (range > 0.0f) ? ((d - d_min) / range) : d;
        // Invert: close=white, far=black
        norm = 1.0f - norm;
        int val = static_cast<int>(norm * 255.0f);
        result[i] = static_cast<uint8_t>(std::clamp(val, 0, 255));
    }

    if (out_w) *out_w = w;
    if (out_h) *out_h = h;
    return result;
}

FBOInfo FrameGraphPresenter::get_fbo_info(FramebufferHandle* fbo) {
    FBOInfo info;
    if (!fbo) {
        info.type_name = "null";
        return info;
    }

    info.type_name = "FramebufferHandle";
    info.width = fbo->get_width();
    info.height = fbo->get_height();
    info.samples = fbo->get_samples();
    info.is_msaa = fbo->is_msaa();
    info.format = fbo->get_format();
    info.fbo_id = fbo->get_fbo_id();
    info.gl_format = fbo->get_actual_gl_format();
    info.gl_width = fbo->get_actual_gl_width();
    info.gl_height = fbo->get_actual_gl_height();
    info.gl_samples = fbo->get_actual_gl_samples();
    info.filter = fbo->get_filter();
    info.gl_filter = fbo->get_actual_gl_filter();

    return info;
}

} // namespace termin
