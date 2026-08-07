#include "termin/editor/frame_graph_debugger_source.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>
#include <utility>

#include <tcbase/tc_log.h>
#include <termin/geom/rect2.hpp>
#include <termin/render/frame_graph_capture.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>

namespace termin {

std::string FrameGraphDebuggerPassSnapshot::display_name() const {
    return name + (internal_symbols.empty() ? "" : " *");
}

namespace {

std::uint64_t local_id(std::size_t index) {
    if (index == std::numeric_limits<std::uint64_t>::max()) {
        throw std::overflow_error("framegraph debugger local identity overflow");
    }
    return static_cast<std::uint64_t>(index) + 1;
}

std::optional<std::size_t> local_index(std::uint64_t id) {
    if (id == 0 || id - 1 > std::numeric_limits<std::size_t>::max()) {
        return std::nullopt;
    }
    return static_cast<std::size_t>(id - 1);
}

FrameGraphDebuggerImageSnapshot project_image(
    const FrameGraphCapture& capture,
    std::uint64_t generation
) {
    FrameGraphDebuggerImageSnapshot result;
    result.available = capture.has_capture() && capture.capture_tex() &&
        capture.width() > 0 && capture.height() > 0;
    if (!result.available) return result;
    result.width = static_cast<std::uint32_t>(capture.width());
    result.height = static_cast<std::uint32_t>(capture.height());
    result.format = capture.format();
    result.depth = capture.is_depth();
    result.generation = generation;
    return result;
}

class LocalFrameGraphDebuggerSource final : public IFrameGraphDebuggerSource {
public:
    explicit LocalFrameGraphDebuggerSource(FrameGraphDebugger& debugger)
        : debugger_(&debugger) {
        rebuild_snapshot();
    }

    ~LocalFrameGraphDebuggerSource() override { close(); }

    std::shared_ptr<const FrameGraphDebuggerSnapshot> snapshot() const override {
        return snapshot_;
    }

    bool refresh() override {
        if (!debugger_) return false;
        const bool changed = debugger_->refresh();
        rebuild_snapshot();
        return changed;
    }

    void finish_frame() override {
        if (!debugger_) return;
        debugger_->finish_frame();
        ++image_generation_;
        rebuild_snapshot();
    }

    void connect() override {
        if (!debugger_) return;
        debugger_->connect();
        rebuild_snapshot();
    }

    void disconnect() override {
        if (!debugger_) return;
        debugger_->disconnect();
        rebuild_snapshot();
    }

    void close() override {
        if (!debugger_) return;
        debugger_->disconnect();
        debugger_ = nullptr;
        auto closed = std::make_shared<FrameGraphDebuggerSnapshot>(*snapshot_);
        ++closed->revision;
        closed->state = FrameGraphDebuggerState::Unbound;
        closed->connected = false;
        closed->stale = true;
        closed->status_detail = "local source closed";
        closed->main_image = {};
        closed->depth_image = {};
        snapshot_ = std::move(closed);
    }

    bool select_target(std::uint64_t target_id) override {
        if (!debugger_) return false;
        const auto index = local_index(target_id);
        if (!index || *index >= debugger_->targets().size()) {
            tc_log_error(
                "[framegraph-debugger-source] invalid local target id %llu",
                static_cast<unsigned long long>(target_id));
            return false;
        }
        const bool selected = debugger_->select_target_at(*index);
        rebuild_snapshot();
        return selected;
    }

    bool select_pass(std::optional<std::uint64_t> pass_id) override {
        if (!debugger_) return false;
        if (!pass_id) {
            debugger_->set_selected_pass(std::nullopt);
            rebuild_snapshot();
            return true;
        }
        const auto index = local_index(*pass_id);
        const auto passes = debugger_->passes();
        if (!index) {
            tc_log_error(
                "[framegraph-debugger-source] invalid local pass id %llu",
                static_cast<unsigned long long>(*pass_id));
            return false;
        }
        const auto found = std::find_if(
            passes.begin(), passes.end(), [index](const auto& pass) {
                return pass.index == *index;
            });
        if (found == passes.end()) {
            tc_log_error(
                "[framegraph-debugger-source] missing local pass id %llu",
                static_cast<unsigned long long>(*pass_id));
            return false;
        }
        debugger_->set_selected_pass(found->index);
        rebuild_snapshot();
        return true;
    }

    void set_mode(FrameGraphDebuggerMode mode) override {
        if (!debugger_) return;
        debugger_->set_mode(mode);
        rebuild_snapshot();
    }

    void set_selected_symbol(const std::string& symbol) override {
        if (!debugger_) return;
        debugger_->set_selected_symbol(symbol);
        rebuild_snapshot();
    }

    void set_selected_resource(const std::string& resource) override {
        if (!debugger_) return;
        debugger_->set_selected_resource(resource);
        rebuild_snapshot();
    }

    void set_channel_mode(int mode) override {
        if (!debugger_) return;
        debugger_->set_channel_mode(mode);
        rebuild_snapshot();
    }

    void set_paused(bool paused) override {
        if (!debugger_) return;
        debugger_->set_paused(paused);
        rebuild_snapshot();
    }

    void set_highlight_hdr(bool enabled) override {
        if (!debugger_) return;
        debugger_->set_highlight_hdr(enabled);
        rebuild_snapshot();
    }

    std::string analyze_hdr() override {
        if (!debugger_) return "Source closed";
        const std::string result = debugger_->analyze_hdr();
        rebuild_snapshot();
        return result;
    }

    bool render_image(
        tgfx::RenderContext2& context,
        tgfx::TextureHandle target,
        FrameGraphDebuggerImageKind kind,
        std::uint32_t width,
        std::uint32_t height,
        int channel_mode,
        bool highlight_hdr
    ) override {
        if (!debugger_ || !target || width == 0 || height == 0) return false;
        const FrameGraphCapture& capture = kind == FrameGraphDebuggerImageKind::Depth
            ? debugger_->depth_capture()
            : debugger_->capture();
        if (!capture.has_capture() || !capture.capture_tex()) return false;
        FrameGraphPresenterDraw draw;
        draw.capture_tex = capture.capture_tex();
        draw.dst_rect = Rect2i{
            0, 0, static_cast<int>(width), static_cast<int>(height)};
        draw.options.channel_mode = channel_mode;
        draw.options.highlight_hdr = highlight_hdr;
        debugger_->presenter().render(&context, target, draw);
        return true;
    }

    std::vector<std::uint8_t> read_depth_normalized(
        tgfx::IRenderDevice& device,
        int* width,
        int* height
    ) override {
        if (!debugger_) return {};
        const FrameGraphCapture& capture = debugger_->depth_capture();
        if (!capture.has_capture() || !capture.capture_tex()) return {};
        return debugger_->presenter().read_depth_normalized(
            &device, capture.capture_tex(), width, height);
    }

private:
    void rebuild_snapshot() {
        auto next = std::make_shared<FrameGraphDebuggerSnapshot>();
        if (!debugger_) {
            next->status_detail = "local source closed";
            snapshot_ = std::move(next);
            return;
        }
        next->revision = debugger_->revision();
        next->graph_revision = debugger_->revision();
        next->source_kind = FrameGraphDebuggerSourceKind::Local;
        next->source_label = "Local";
        next->connected = true;
        next->state = debugger_->state();
        next->suspend_reason = debugger_->suspend_reason();
        next->targets.reserve(debugger_->targets().size());
        for (std::size_t index = 0; index < debugger_->targets().size(); ++index) {
            const auto& target = debugger_->targets()[index];
            next->targets.push_back({local_id(index), target.label, target.renderable});
        }
        if (const auto selected = debugger_->selected_target_index()) {
            next->selected_target_id = local_id(*selected);
        }
        const auto passes = debugger_->passes();
        next->passes.reserve(passes.size());
        for (const auto& pass : passes) {
            next->passes.push_back({
                local_id(pass.index), pass.index, pass.name, pass.type,
                pass.enabled, pass.passthrough, pass.reads, pass.writes,
                pass.internal_symbols});
        }
        if (const auto selected = debugger_->selected_pass_index()) {
            next->selected_pass_id = local_id(*selected);
        }
        next->resources = debugger_->resources();
        next->symbols = debugger_->symbols();
        next->mode = debugger_->mode();
        next->selected_symbol = debugger_->selected_symbol();
        next->selected_resource = debugger_->selected_resource();
        next->channel_mode = debugger_->channel_mode();
        next->paused = debugger_->paused();
        next->highlight_hdr = debugger_->highlight_hdr();
        next->capture_info = debugger_->format_capture_info();
        next->pipeline_info = debugger_->format_pipeline_info();
        next->pass_json = debugger_->format_pass_json();
        next->render_stats = debugger_->format_render_stats();
        next->timing = debugger_->format_timing();
        next->main_image = project_image(
            debugger_->capture(), image_generation_);
        next->depth_image = project_image(
            debugger_->depth_capture(), image_generation_);
        snapshot_ = std::move(next);
    }

    FrameGraphDebugger* debugger_ = nullptr;
    std::shared_ptr<const FrameGraphDebuggerSnapshot> snapshot_;
    std::uint64_t image_generation_ = 0;
};

} // namespace

std::shared_ptr<IFrameGraphDebuggerSource>
make_local_frame_graph_debugger_source(FrameGraphDebugger& debugger) {
    return std::make_shared<LocalFrameGraphDebuggerSource>(debugger);
}

} // namespace termin
