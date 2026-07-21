#pragma once

#include "termin/engine/termin_engine_api.hpp"
#include "termin/render/frame_graph_capture.hpp"
#include "termin/render/rendering_manager.hpp"

#include <cstddef>
#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace termin {

enum class FrameGraphDebuggerState {
    Unbound,
    Bound,
    WaitingFrame,
    Captured,
    Suspended,
    Error,
};

enum class FrameGraphDebuggerSuspendReason {
    None,
    TargetRemoved,
    PipelineUnavailable,
    TargetNotRenderable,
};

enum class FrameGraphDebuggerMode {
    BetweenPasses,
    InsidePass,
};

struct FrameGraphDebuggerPassInfo {
    size_t index = 0;
    std::string name;
    std::string type;
    bool enabled = true;
    bool passthrough = false;
    std::vector<std::string> reads;
    std::vector<std::string> writes;
    std::vector<std::string> internal_symbols;

    bool has_internal_symbols() const { return !internal_symbols.empty(); }
    std::string display_name() const {
        return name + (has_internal_symbols() ? " *" : "");
    }
};

// Native, editor-agnostic debugger state. RenderingManager must outlive this
// object. The debugger deliberately stores handle identities, never borrowed
// RenderPipeline/tc_pass pointers, and reconciles them by polling the manager.
class TERMIN_ENGINE_API FrameGraphDebugger : private RenderExecutionObserver {
public:
    explicit FrameGraphDebugger(RenderingManager& manager);
    ~FrameGraphDebugger() override;

    FrameGraphDebugger(const FrameGraphDebugger&) = delete;
    FrameGraphDebugger& operator=(const FrameGraphDebugger&) = delete;

    bool refresh();
    void finish_frame();

    bool select_target(const RenderExecutionTargetId& target);
    bool select_target_at(size_t index);
    void clear_selection();
    void request_resource(const std::string& resource);
    bool request_internal(size_t pass_index, const std::string& symbol);
    void set_paused(bool paused);
    void cancel_request();
    void connect();
    void disconnect();

    const std::vector<RenderExecutionTargetInfo>& targets() const { return targets_; }
    const RenderExecutionTargetInfo* selected_target() const;
    bool has_selection() const { return has_desired_target_; }
    FrameGraphDebuggerState state() const { return state_; }
    FrameGraphDebuggerSuspendReason suspend_reason() const { return suspend_reason_; }
    uint64_t revision() const { return revision_; }
    uint64_t request_generation() const { return request_generation_; }
    tc_pipeline_handle resolved_pipeline() const { return resolved_pipeline_; }

    FrameGraphCapture& capture() { return capture_; }
    const FrameGraphCapture& capture() const { return capture_; }
    FrameGraphCapture& depth_capture() { return depth_capture_; }
    const FrameGraphCapture& depth_capture() const { return depth_capture_; }
    FrameGraphPresenter& presenter() { return presenter_; }
    const FrameGraphPresenter& presenter() const { return presenter_; }
    tgfx::TextureHandle capture_tex() const { return capture_.capture_tex(); }
    tgfx::TextureHandle depth_capture_tex() const { return depth_capture_.capture_tex(); }
    const std::string& requested_resource() const { return capture_request_.resource; }
    bool paused() const { return capture_request_.paused; }
    FrameGraphCaptureRequestStatus capture_status() const {
        return capture_request_.status;
    }

    std::optional<size_t> selected_target_index() const;
    FrameGraphDebuggerMode mode() const { return mode_; }
    void set_mode(FrameGraphDebuggerMode mode);
    std::optional<size_t> selected_pass_index() const { return selected_pass_index_; }
    const std::string& selected_pass_name() const { return selected_pass_name_; }
    const std::string& selected_symbol() const { return selected_symbol_; }
    const std::string& selected_resource() const { return selected_resource_; }
    void set_selected_pass(std::optional<size_t> pass_index);
    void set_selected_symbol(const std::string& symbol);
    void set_selected_resource(const std::string& resource);
    int channel_mode() const { return channel_mode_; }
    void set_channel_mode(int mode) { channel_mode_ = mode; ++revision_; }
    bool highlight_hdr() const { return highlight_hdr_; }
    void set_highlight_hdr(bool enabled) { highlight_hdr_ = enabled; ++revision_; }

    std::vector<FrameGraphDebuggerPassInfo> passes() const;
    std::vector<FrameGraphDebuggerPassInfo> schedule() const;
    std::vector<std::string> resources() const;
    std::map<std::string, std::vector<std::string>> alias_groups() const;
    std::vector<std::string> symbols() const;
    std::string format_capture_info() const;
    std::string format_writer_pass() const;
    std::string format_pipeline_info() const;
    std::string format_pass_json() const;
    std::string format_pass_json_at(size_t pass_index) const;
    std::string format_timing() const;
    std::string format_render_stats() const;
    std::string analyze_hdr();

private:
    void collect_render_demands(
        std::vector<RenderExecutionTargetId>& demands
    ) const override;
    FrameGraphCaptureRequest* prepare_render_execution(
        const RenderExecutionInfo& execution
    ) override;
    void finish_render_execution(
        const RenderExecutionInfo& execution,
        FrameGraphCaptureRequest* request
    ) override;
    bool execution_matches_target(const RenderExecutionInfo& execution) const;
    tc_pass* selected_pass() const;
    void reconcile_selection();
    void begin_request();
    void reconnect_request();
    void sync_active_request_configuration();
    const RenderExecutionTargetInfo* find_target(const RenderExecutionTargetId& id) const;
    void invalidate_request();
    void set_connection_state(
        FrameGraphDebuggerState state,
        FrameGraphDebuggerSuspendReason reason,
        tc_pipeline_handle pipeline
    );

    RenderingManager* manager_ = nullptr;
    std::vector<RenderExecutionTargetInfo> targets_;
    RenderExecutionTargetId desired_target_;
    bool has_desired_target_ = false;
    bool connected_ = false;
    bool request_active_ = false;
    FrameGraphDebuggerState state_ = FrameGraphDebuggerState::Unbound;
    FrameGraphDebuggerSuspendReason suspend_reason_ = FrameGraphDebuggerSuspendReason::None;
    tc_pipeline_handle resolved_pipeline_ = TC_PIPELINE_HANDLE_INVALID;
    uint64_t revision_ = 0;
    uint64_t request_generation_ = 0;
    FrameGraphCapture capture_;
    FrameGraphCapture depth_capture_;
    FrameGraphPresenter presenter_;
    FrameGraphCaptureRequest capture_request_;
    FrameGraphDebuggerMode mode_ = FrameGraphDebuggerMode::InsidePass;
    std::optional<size_t> selected_pass_index_;
    std::string selected_pass_name_;
    std::string selected_symbol_;
    std::string selected_resource_;
    int channel_mode_ = 0;
    bool highlight_hdr_ = false;
};

} // namespace termin
