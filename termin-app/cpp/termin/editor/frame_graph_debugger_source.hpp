#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include <termin/render/frame_graph_debugger.hpp>
#include <tgfx2/enums.hpp>
#include <tgfx2/handles.hpp>

namespace tgfx {
class IRenderDevice;
class RenderContext2;
}

namespace termin {

struct FrameGraphDebuggerTargetSnapshot {
    std::uint64_t id = 0;
    std::string label;
    bool renderable = false;
};

struct FrameGraphDebuggerPassSnapshot {
    std::uint64_t id = 0;
    std::size_t authored_index = 0;
    std::string name;
    std::string type;
    bool enabled = true;
    bool passthrough = false;
    std::vector<std::string> reads;
    std::vector<std::string> writes;
    std::vector<std::string> internal_symbols;

    std::string display_name() const;
};

enum class FrameGraphDebuggerImageKind {
    Main,
    Depth,
};

// The image descriptor deliberately contains no transport identity or remote
// GPU handle. A source may use an in-process capture or a locally uploaded
// network image, but it must make that distinction invisible to the view.
struct FrameGraphDebuggerImageSnapshot {
    bool available = false;
    std::uint32_t width = 0;
    std::uint32_t height = 0;
    tgfx::PixelFormat format = tgfx::PixelFormat::Undefined;
    bool depth = false;
    std::uint64_t generation = 0;
};

struct FrameGraphDebuggerSnapshot {
    std::uint64_t revision = 0;
    FrameGraphDebuggerState state = FrameGraphDebuggerState::Unbound;
    FrameGraphDebuggerSuspendReason suspend_reason =
        FrameGraphDebuggerSuspendReason::None;
    std::string status_detail;

    std::vector<FrameGraphDebuggerTargetSnapshot> targets;
    std::optional<std::uint64_t> selected_target_id;
    std::vector<FrameGraphDebuggerPassSnapshot> passes;
    std::optional<std::uint64_t> selected_pass_id;
    std::vector<std::string> resources;
    std::vector<std::string> symbols;
    FrameGraphDebuggerMode mode = FrameGraphDebuggerMode::InsidePass;
    std::string selected_symbol;
    std::string selected_resource;
    int channel_mode = 0;
    bool paused = false;
    bool highlight_hdr = false;

    std::string capture_info;
    std::string pipeline_info;
    std::string pass_json;
    std::string render_stats;
    std::string timing;
    FrameGraphDebuggerImageSnapshot main_image;
    FrameGraphDebuggerImageSnapshot depth_image;
};

class IFrameGraphDebuggerSource {
public:
    virtual ~IFrameGraphDebuggerSource() = default;

    virtual std::shared_ptr<const FrameGraphDebuggerSnapshot> snapshot() const = 0;
    virtual bool refresh() = 0;
    virtual void finish_frame() = 0;
    virtual void connect() = 0;
    virtual void disconnect() = 0;
    virtual void close() = 0;

    virtual bool select_target(std::uint64_t target_id) = 0;
    virtual bool select_pass(std::optional<std::uint64_t> pass_id) = 0;
    virtual void set_mode(FrameGraphDebuggerMode mode) = 0;
    virtual void set_selected_symbol(const std::string& symbol) = 0;
    virtual void set_selected_resource(const std::string& resource) = 0;
    virtual void set_channel_mode(int mode) = 0;
    virtual void set_paused(bool paused) = 0;
    virtual void set_highlight_hdr(bool enabled) = 0;
    virtual std::string analyze_hdr() = 0;

    virtual bool render_image(
        tgfx::RenderContext2& context,
        tgfx::TextureHandle target,
        FrameGraphDebuggerImageKind kind,
        std::uint32_t width,
        std::uint32_t height,
        int channel_mode,
        bool highlight_hdr) = 0;
    virtual std::vector<std::uint8_t> read_depth_normalized(
        tgfx::IRenderDevice& device,
        int* width,
        int* height) = 0;
};

std::shared_ptr<IFrameGraphDebuggerSource>
make_local_frame_graph_debugger_source(FrameGraphDebugger& debugger);

} // namespace termin
