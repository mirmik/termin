#pragma once

#include "termin/render/graphics_backend.hpp"
#include "termin/render/handles.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "tc_log.hpp"

#include <string>
#include <vector>
#include <cmath>

namespace termin {

// Forward declarations
class CxxFramePass;

// HDR statistics
struct HDRStats {
    float min_r = 0, max_r = 0, avg_r = 0;
    float min_g = 0, max_g = 0, avg_g = 0;
    float min_b = 0, max_b = 0, avg_b = 0;
    int hdr_pixel_count = 0;
    int total_pixels = 0;
    float hdr_percent = 0;
    float max_value = 0;
};

// FBO metadata
struct FBOInfo {
    std::string type_name;
    int width = 0;
    int height = 0;
    int samples = 0;
    bool is_msaa = false;
    std::string format;
    uint32_t fbo_id = 0;
    std::string gl_format;
    int gl_width = 0;
    int gl_height = 0;
    int gl_samples = 0;
    std::string filter;
    std::string gl_filter;
};

// ============================================================
// FrameGraphCapture — capture FBO during render
// ============================================================

class FrameGraphCapture {
private:
    FramebufferHandlePtr capture_fbo_;
    int fbo_w_ = 0;
    int fbo_h_ = 0;
    std::string fbo_format_;
    bool captured_ = false;

    // Target pass — only this pass can capture
    CxxFramePass* target_pass_ = nullptr;

public:
    // Target management
    void set_target(CxxFramePass* pass) { target_pass_ = pass; }
    void clear_target() { target_pass_ = nullptr; }
    CxxFramePass* target() const { return target_pass_; }

    // Pass asks: "should I capture?"
    bool should_capture(CxxFramePass* caller) const {
        return caller && caller == target_pass_;
    }

    // Capture: checks should_capture, recreates FBO if needed, blits.
    // MSAA resolve automatic on blit (capture FBO always non-MSAA).
    void capture(CxxFramePass* caller, FramebufferHandle* src, GraphicsBackend* graphics);

    // Capture without caller check (for Python FrameDebuggerPass which uses tc_pass)
    void capture_direct(FramebufferHandle* src, GraphicsBackend* graphics);

    FramebufferHandle* capture_fbo() const { return capture_fbo_.get(); }
    bool has_capture() const { return captured_; }
    void reset_capture() { captured_ = false; }

private:
    // Ensure capture FBO matches source dimensions/format
    void ensure_capture_fbo(FramebufferHandle* src, GraphicsBackend* graphics);
    // Blit src -> capture_fbo
    void do_blit(FramebufferHandle* src, GraphicsBackend* graphics);
};

// ============================================================
// FrameGraphPresenter — display and analyze captured texture
// ============================================================

class FrameGraphPresenter {
private:
    TcShader shader_;
    bool shader_ready_ = false;

public:
    // Render capture_fbo into current bound framebuffer
    // (Python already did make_current)
    void render(
        GraphicsBackend* graphics,
        FramebufferHandle* capture_fbo,
        int dst_w, int dst_h,
        int channel_mode,      // 0=RGB, 1=R, 2=G, 3=B, 4=A
        bool highlight_hdr
    );

    // HDR statistics from capture_fbo
    HDRStats compute_hdr_stats(GraphicsBackend* graphics, FramebufferHandle* fbo);

    // Depth buffer: normalized uint8 array (h*w), ready for QImage
    // Returns empty vector on error. out_w and out_h are set to dimensions.
    std::vector<uint8_t> read_depth_normalized(
        GraphicsBackend* graphics, FramebufferHandle* fbo,
        int* out_w, int* out_h
    );

    // FBO metadata
    static FBOInfo get_fbo_info(FramebufferHandle* fbo);

private:
    void ensure_shader();
};

// ============================================================
// FrameGraphDebuggerCore — combines capture and presenter
// ============================================================

class FrameGraphDebuggerCore {
public:
    FrameGraphCapture capture;
    FrameGraphPresenter presenter;

    FramebufferHandle* capture_fbo() const { return capture.capture_fbo(); }
};

} // namespace termin
