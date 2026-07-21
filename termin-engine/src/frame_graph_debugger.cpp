#include "termin/render/frame_graph_debugger.hpp"
#include "termin/render/frame_pass.hpp"
#include "termin/render/tc_pass.hpp"
#include "tgfx2/pixel_format_utils.hpp"
#include "tcbase/tc_value_trent.hpp"
#include "tcbase/trent/json.h"

extern "C" {
#include "inspect/tc_inspect.h"
#include "render/tc_frame_graph.h"
#include "render/tc_pipeline_pool.h"
}

#include <algorithm>
#include <cstdlib>
#include <iomanip>
#include <set>
#include <sstream>

namespace termin {

namespace {

using PassStringGetter = size_t (*)(tc_pass*, const char**, size_t);

std::vector<std::string> collect_pass_strings(
    tc_pass* pass,
    PassStringGetter getter
) {
    const size_t count = getter(pass, nullptr, 0);
    std::vector<const char*> raw(count, nullptr);
    if (count) getter(pass, raw.data(), raw.size());
    std::vector<std::string> result;
    result.reserve(count);
    for (const char* value : raw) {
        if (value) result.emplace_back(value);
    }
    std::sort(result.begin(), result.end());
    return result;
}

FrameGraphDebuggerPassInfo make_pass_info(
    const RenderPipeline& pipeline,
    tc_pass* pass
) {
    FrameGraphDebuggerPassInfo result;
    for (size_t index = 0; index < pipeline.pass_count(); ++index) {
        if (pipeline.get_pass_at(index) == pass) {
            result.index = index;
            break;
        }
    }
    result.name = pass && pass->pass_name ? pass->pass_name : "UnnamedPass";
    result.type = pass ? tc_pass_type_name(pass) : "BrokenPass_NullPtr";
    result.enabled = pass ? pass->enabled : false;
    result.passthrough = pass ? pass->passthrough : false;
    if (pass) {
        result.reads = collect_pass_strings(pass, tc_pass_get_reads);
        result.writes = collect_pass_strings(pass, tc_pass_get_writes);
        if (result.type != "ShadowPass" && result.name != "ShadowPass") {
            result.internal_symbols = collect_pass_strings(
                pass, tc_pass_get_internal_symbols);
        }
    }
    return result;
}

bool contains(const std::vector<std::string>& values, const std::string& value) {
    return std::find(values.begin(), values.end(), value) != values.end();
}

std::string serialize_pass_json(tc_pass* pass) {
    if (!pass) return "<error: pass is unavailable>";
    TcPassRef ref(pass);
    void* object = ref.object_ptr();
    if (!object) return "<error: pass has no inspectable object>";
    tc_value value = tc_inspect_serialize(object, tc_pass_type_name(pass));
    if (value.type == TC_VALUE_NIL) return "<error: pass serialization failed>";
    std::string result = nos::json::dump(tc::tc_value_to_trent(value), 2);
    tc_value_free(&value);
    return result;
}

} // namespace

FrameGraphDebugger::FrameGraphDebugger(RenderingManager& manager)
    : manager_(&manager) {
    capture_request_.capture = &capture_;
    capture_request_.depth_capture = &depth_capture_;
    manager_->add_render_execution_observer(*this);
    refresh();
}

FrameGraphDebugger::~FrameGraphDebugger() {
    if (manager_) manager_->remove_render_execution_observer(*this);
}

bool FrameGraphDebugger::refresh() {
    std::vector<RenderExecutionTargetInfo> next = manager_->execution_targets();
    bool changed = next != targets_;
    bool pipeline_rebound = false;
    targets_ = std::move(next);

    if (!has_desired_target_ && !targets_.empty()) {
        desired_target_ = targets_.front().id;
        has_desired_target_ = true;
        changed = true;
    }

    if (!has_desired_target_) {
        if (state_ != FrameGraphDebuggerState::Unbound
                || suspend_reason_ != FrameGraphDebuggerSuspendReason::None
                || tc_pipeline_handle_valid(resolved_pipeline_)) {
            state_ = FrameGraphDebuggerState::Unbound;
            suspend_reason_ = FrameGraphDebuggerSuspendReason::None;
            resolved_pipeline_ = TC_PIPELINE_HANDLE_INVALID;
            changed = true;
        }
    } else {
        const RenderExecutionTargetInfo* target = find_target(desired_target_);
        if (!target) {
            const bool binding_changed = tc_pipeline_handle_valid(resolved_pipeline_)
                || state_ != FrameGraphDebuggerState::Suspended
                || suspend_reason_ != FrameGraphDebuggerSuspendReason::TargetRemoved;
            if (binding_changed) {
                invalidate_request();
                set_connection_state(
                    FrameGraphDebuggerState::Suspended,
                    FrameGraphDebuggerSuspendReason::TargetRemoved,
                    TC_PIPELINE_HANDLE_INVALID);
                changed = true;
            }
        } else if (!tc_pipeline_pool_alive(target->pipeline)) {
            const bool binding_changed = tc_pipeline_handle_valid(resolved_pipeline_)
                || state_ != FrameGraphDebuggerState::Suspended
                || suspend_reason_ != FrameGraphDebuggerSuspendReason::PipelineUnavailable;
            if (binding_changed) {
                invalidate_request();
                set_connection_state(
                    FrameGraphDebuggerState::Suspended,
                    FrameGraphDebuggerSuspendReason::PipelineUnavailable,
                    TC_PIPELINE_HANDLE_INVALID);
                changed = true;
            }
        } else if (!target->renderable) {
            const bool pipeline_changed = !tc_pipeline_handle_eq(
                resolved_pipeline_, target->pipeline);
            const bool binding_changed = pipeline_changed
                || state_ != FrameGraphDebuggerState::Suspended
                || suspend_reason_ != FrameGraphDebuggerSuspendReason::TargetNotRenderable;
            if (binding_changed) {
                if (pipeline_changed) invalidate_request();
                set_connection_state(
                    FrameGraphDebuggerState::Suspended,
                    FrameGraphDebuggerSuspendReason::TargetNotRenderable,
                    target->pipeline);
                changed = true;
            }
        } else {
            const bool pipeline_changed = !tc_pipeline_handle_eq(
                resolved_pipeline_, target->pipeline);
            if (pipeline_changed) {
                invalidate_request();
                pipeline_rebound = true;
            }
            const FrameGraphDebuggerState next_state = request_active_
                ? FrameGraphDebuggerState::WaitingFrame
                : FrameGraphDebuggerState::Bound;
            if (pipeline_changed || state_ == FrameGraphDebuggerState::Suspended
                    || state_ == FrameGraphDebuggerState::Unbound
                    || suspend_reason_ != FrameGraphDebuggerSuspendReason::None) {
                set_connection_state(
                    next_state,
                    FrameGraphDebuggerSuspendReason::None,
                    target->pipeline);
                changed = true;
            }
        }
    }

    reconcile_selection();
    if (pipeline_rebound && request_active_) {
        sync_active_request_configuration();
    }

    if (changed) ++revision_;
    return changed;
}

void FrameGraphDebugger::finish_frame() {
    refresh();
    if (!request_active_ || state_ == FrameGraphDebuggerState::Suspended) return;
    // Resource requests complete synchronously in RenderingManager's
    // execution callback. The frame tick remains for inside-pass capture.
    if (!capture_request_.resource.empty()) return;
    const FrameGraphDebuggerState next = capture_.has_capture()
        ? FrameGraphDebuggerState::Captured
        : FrameGraphDebuggerState::WaitingFrame;
    if (state_ != next) {
        state_ = next;
        ++revision_;
    }
}

bool FrameGraphDebugger::select_target(const RenderExecutionTargetId& target) {
    const RenderExecutionTargetId desired = target;
    desired_target_ = desired;
    has_desired_target_ = true;
    refresh();
    return find_target(desired) != nullptr;
}

bool FrameGraphDebugger::select_target_at(size_t index) {
    refresh();
    if (index >= targets_.size()) return false;
    const RenderExecutionTargetId target = targets_[index].id;
    return select_target(target);
}

void FrameGraphDebugger::clear_selection() {
    if (!has_desired_target_ && state_ == FrameGraphDebuggerState::Unbound) return;
    has_desired_target_ = false;
    request_active_ = false;
    invalidate_request();
    set_connection_state(
        FrameGraphDebuggerState::Unbound,
        FrameGraphDebuggerSuspendReason::None,
        TC_PIPELINE_HANDLE_INVALID);
    ++revision_;
}

void FrameGraphDebugger::begin_request() {
    request_active_ = true;
    invalidate_request();
    refresh();
    if (state_ == FrameGraphDebuggerState::Bound
            || state_ == FrameGraphDebuggerState::Captured) {
        state_ = FrameGraphDebuggerState::WaitingFrame;
        ++revision_;
    }
}

void FrameGraphDebugger::request_resource(const std::string& resource) {
    mode_ = FrameGraphDebuggerMode::BetweenPasses;
    selected_resource_ = resource;
    capture_request_.kind = FrameGraphCaptureRequestKind::Resource;
    capture_request_.resource = resource;
    capture_request_.pass_index = static_cast<size_t>(-1);
    capture_request_.internal_symbol.clear();
    begin_request();
}

bool FrameGraphDebugger::request_internal(
    size_t pass_index,
    const std::string& symbol
) {
    RenderPipeline pipeline(resolved_pipeline_);
    if (!pipeline.is_valid() || pass_index >= pipeline.pass_count()
            || symbol.empty()) {
        return false;
    }
    const FrameGraphDebuggerPassInfo info = make_pass_info(
        pipeline, pipeline.get_pass_at(pass_index));
    if (!contains(info.internal_symbols, symbol)) return false;
    mode_ = FrameGraphDebuggerMode::InsidePass;
    capture_request_.kind = FrameGraphCaptureRequestKind::InternalSymbol;
    capture_request_.resource.clear();
    capture_request_.pass_index = pass_index;
    capture_request_.internal_symbol = symbol;
    begin_request();
    return true;
}

void FrameGraphDebugger::set_paused(bool paused) {
    if (capture_request_.paused == paused) return;
    capture_request_.paused = paused;
    if (!paused && request_active_) {
        invalidate_request();
        state_ = FrameGraphDebuggerState::WaitingFrame;
    }
    ++revision_;
}

void FrameGraphDebugger::cancel_request() {
    if (!request_active_) return;
    request_active_ = false;
    invalidate_request();
    refresh();
    if (state_ == FrameGraphDebuggerState::WaitingFrame
            || state_ == FrameGraphDebuggerState::Captured) {
        state_ = FrameGraphDebuggerState::Bound;
        ++revision_;
    }
}

void FrameGraphDebugger::connect() {
    connected_ = true;
    refresh();
    // Opening a debugger session is an explicit request to attach to what is
    // live now.  Preserve an exact missing target while the session is merely
    // refreshing, but do not carry that stale identity into a newly connected
    // UI session when another live target is available.
    if (!selected_target_index() && !targets_.empty()) {
        select_target_at(0);
    }
    reconnect_request();
}

void FrameGraphDebugger::disconnect() {
    connected_ = false;
    cancel_request();
}

FrameGraphCaptureRequest* FrameGraphDebugger::prepare_render_execution(
    const RenderExecutionInfo& execution
) {
    refresh();
    const bool request_configured =
        (capture_request_.kind == FrameGraphCaptureRequestKind::Resource
            && !capture_request_.resource.empty())
        || (capture_request_.kind == FrameGraphCaptureRequestKind::InternalSymbol
            && capture_request_.pass_index != static_cast<size_t>(-1)
            && !capture_request_.internal_symbol.empty());
    if (!request_active_ || !request_configured || capture_request_.paused
            || state_ == FrameGraphDebuggerState::Suspended
            || !execution_matches_target(execution)) {
        return nullptr;
    }
    capture_request_.generation = request_generation_;
    capture_request_.status = FrameGraphCaptureRequestStatus::Pending;
    return &capture_request_;
}

void FrameGraphDebugger::collect_render_demands(
    std::vector<RenderExecutionTargetId>& demands
) const {
    if ((!connected_ && !request_active_)
            || capture_request_.paused
            || !has_desired_target_) {
        return;
    }
    demands.push_back(desired_target_);
}

std::optional<size_t> FrameGraphDebugger::selected_target_index() const {
    if (!has_desired_target_) return std::nullopt;
    for (size_t index = 0; index < targets_.size(); ++index) {
        if (targets_[index].id == desired_target_) return index;
    }
    return std::nullopt;
}

void FrameGraphDebugger::set_mode(FrameGraphDebuggerMode mode) {
    if (mode_ == mode) return;
    mode_ = mode;
    reconnect_request();
    ++revision_;
}

void FrameGraphDebugger::set_selected_pass(std::optional<size_t> pass_index) {
    selected_pass_index_.reset();
    selected_pass_name_.clear();
    selected_symbol_.clear();
    RenderPipeline pipeline(resolved_pipeline_);
    if (pass_index && pipeline.is_valid() && *pass_index < pipeline.pass_count()) {
        selected_pass_index_ = *pass_index;
        tc_pass* pass = pipeline.get_pass_at(*pass_index);
        selected_pass_name_ = pass && pass->pass_name ? pass->pass_name : "";
        const std::vector<std::string> available = symbols();
        if (!available.empty()) selected_symbol_ = available.back();
    }
    reconnect_request();
    ++revision_;
}

void FrameGraphDebugger::set_selected_symbol(const std::string& symbol) {
    if (selected_symbol_ == symbol) return;
    const std::vector<std::string> available = symbols();
    selected_symbol_ = contains(available, symbol) ? symbol : std::string{};
    reconnect_request();
    ++revision_;
}

void FrameGraphDebugger::set_selected_resource(const std::string& resource) {
    if (selected_resource_ == resource) return;
    selected_resource_ = resource;
    reconnect_request();
    ++revision_;
}

tc_pass* FrameGraphDebugger::selected_pass() const {
    if (!selected_pass_index_) return nullptr;
    RenderPipeline pipeline(resolved_pipeline_);
    return pipeline.is_valid() && *selected_pass_index_ < pipeline.pass_count()
        ? pipeline.get_pass_at(*selected_pass_index_) : nullptr;
}

void FrameGraphDebugger::reconcile_selection() {
    if (!selected_pass_index_) return;
    tc_pass* pass = selected_pass();
    if (!pass) {
        selected_pass_index_.reset();
        selected_pass_name_.clear();
        selected_symbol_.clear();
        return;
    }
    selected_pass_name_ = pass->pass_name ? pass->pass_name : "";
    const std::vector<std::string> available = symbols();
    if (!contains(available, selected_symbol_)) {
        selected_symbol_ = available.empty() ? std::string{} : available.back();
    }
}

void FrameGraphDebugger::reconnect_request() {
    cancel_request();
    if (!has_desired_target_) return;
    if (mode_ == FrameGraphDebuggerMode::BetweenPasses) {
        if (!selected_resource_.empty()) request_resource(selected_resource_);
        return;
    }
    if (selected_pass_index_ && !selected_symbol_.empty()) {
        request_internal(*selected_pass_index_, selected_symbol_);
    }
}

void FrameGraphDebugger::sync_active_request_configuration() {
    if (mode_ == FrameGraphDebuggerMode::BetweenPasses) {
        if (selected_resource_.empty()) {
            request_active_ = false;
            state_ = FrameGraphDebuggerState::Bound;
            return;
        }
        capture_request_.kind = FrameGraphCaptureRequestKind::Resource;
        capture_request_.resource = selected_resource_;
        capture_request_.pass_index = static_cast<size_t>(-1);
        capture_request_.internal_symbol.clear();
        return;
    }

    if (!selected_pass_index_ || selected_symbol_.empty()) {
        request_active_ = false;
        state_ = FrameGraphDebuggerState::Bound;
        return;
    }
    capture_request_.kind = FrameGraphCaptureRequestKind::InternalSymbol;
    capture_request_.resource.clear();
    capture_request_.pass_index = *selected_pass_index_;
    capture_request_.internal_symbol = selected_symbol_;
}

std::vector<FrameGraphDebuggerPassInfo> FrameGraphDebugger::passes() const {
    RenderPipeline pipeline(resolved_pipeline_);
    std::vector<FrameGraphDebuggerPassInfo> result;
    if (!pipeline.is_valid()) return result;
    result.reserve(pipeline.pass_count());
    for (size_t index = 0; index < pipeline.pass_count(); ++index) {
        tc_pass* pass = pipeline.get_pass_at(index);
        if (!pass) continue;
        result.push_back(make_pass_info(pipeline, pass));
    }
    return result;
}

std::vector<FrameGraphDebuggerPassInfo> FrameGraphDebugger::schedule() const {
    RenderPipeline pipeline(resolved_pipeline_);
    std::vector<FrameGraphDebuggerPassInfo> result;
    if (!pipeline.is_valid()) return result;
    tc_frame_graph* graph = tc_pipeline_get_frame_graph(pipeline.handle());
    if (!graph || tc_frame_graph_get_error(graph) != TC_FG_OK) return result;
    const size_t count = tc_frame_graph_schedule_count(graph);
    result.reserve(count);
    for (size_t index = 0; index < count; ++index) {
        tc_pass* pass = tc_frame_graph_schedule_at(graph, index);
        if (pass) result.push_back(make_pass_info(pipeline, pass));
    }
    return result;
}

std::vector<std::string> FrameGraphDebugger::resources() const {
    const std::vector<FrameGraphDebuggerPassInfo> ordered = schedule();
    std::set<std::string> written;
    for (const auto& pass : ordered) {
        written.insert(pass.writes.begin(), pass.writes.end());
    }
    written.erase("DISPLAY");

    std::vector<std::string> result;
    std::set<std::string> seen;
    for (const auto& pass : ordered) {
        for (const std::string& read : pass.reads) {
            if (read != "DISPLAY" && !written.count(read) && seen.insert(read).second) {
                result.push_back(read);
            }
        }
    }
    for (const auto& pass : ordered) {
        for (const std::string& write : pass.writes) {
            if (write != "DISPLAY" && seen.insert(write).second) {
                result.push_back(write);
            }
        }
    }
    if (!result.empty()) return result;

    RenderPipeline pipeline(resolved_pipeline_);
    if (!pipeline.is_valid()) return result;
    for (const ResourceSpec& spec : pipeline.collect_specs()) {
        if (spec.resource != "DISPLAY" && seen.insert(spec.resource).second) {
            result.push_back(spec.resource);
        }
    }
    std::sort(result.begin(), result.end());
    return result;
}

std::map<std::string, std::vector<std::string>>
FrameGraphDebugger::alias_groups() const {
    std::map<std::string, std::vector<std::string>> result;
    RenderPipeline pipeline(resolved_pipeline_);
    if (!pipeline.is_valid()) return result;
    tc_frame_graph* graph = tc_pipeline_get_frame_graph(pipeline.handle());
    if (!graph || tc_frame_graph_get_error(graph) != TC_FG_OK) return result;
    const size_t canonical_count = tc_frame_graph_get_canonical_resources(
        graph, nullptr, 0);
    std::vector<const char*> canonical(canonical_count, nullptr);
    if (canonical_count) {
        tc_frame_graph_get_canonical_resources(
            graph, canonical.data(), canonical.size());
    }
    for (const char* name : canonical) {
        if (!name) continue;
        const size_t count = tc_frame_graph_get_alias_group(graph, name, nullptr, 0);
        std::vector<const char*> raw(count, nullptr);
        if (count) tc_frame_graph_get_alias_group(graph, name, raw.data(), raw.size());
        std::vector<std::string>& group = result[name];
        for (const char* alias : raw) {
            if (alias) group.emplace_back(alias);
        }
        std::sort(group.begin(), group.end());
    }
    return result;
}

std::vector<std::string> FrameGraphDebugger::symbols() const {
    tc_pass* pass = selected_pass();
    return pass
        ? collect_pass_strings(pass, tc_pass_get_internal_symbols)
        : std::vector<std::string>{};
}

std::string FrameGraphDebugger::format_capture_info() const {
    if (!capture_.has_capture()) {
        return "Resource '" + selected_resource_ + "': capture not received";
    }
    std::ostringstream out;
    out << "<b>" << selected_resource_ << "</b> | Type: "
        << (capture_.is_depth() ? "depth_texture" : "color_texture")
        << " | Size: " << capture_.width() << "x" << capture_.height()
        << " | fmt=" << tgfx::pixel_format_name(capture_.format())
        << " | MSAA=off";
    return out.str();
}

std::string FrameGraphDebugger::format_writer_pass() const {
    if (selected_resource_.empty()) return {};
    for (const auto& pass : schedule()) {
        if (contains(pass.writes, selected_resource_)) return "<- " + pass.name;
    }
    return "(read-only)";
}

std::string FrameGraphDebugger::format_pipeline_info() const {
    const auto ordered = schedule();
    if (ordered.empty()) return "<i>Pipeline is empty</i>";
    std::ostringstream out;
    out << "<pre>";
    bool first = true;
    for (const auto& pass : ordered) {
        if (!first) out << "<br>";
        first = false;
        const bool writer = !selected_resource_.empty()
            && contains(pass.writes, selected_resource_);
        if (writer) out << "<span style='color: #50fa7b; font-weight: bold;'>* ";
        out << pass.name << ": {";
        for (size_t i = 0; i < pass.reads.size(); ++i) {
            if (i) out << ", ";
            out << pass.reads[i];
        }
        if (pass.reads.empty()) out << "empty";
        out << "} -&gt; {";
        for (size_t i = 0; i < pass.writes.size(); ++i) {
            if (i) out << ", ";
            out << pass.writes[i];
        }
        if (pass.writes.empty()) out << "empty";
        out << "}";
        if (writer) out << "</span>";
    }
    const auto aliases = alias_groups();
    for (const auto& [canonical, group] : aliases) {
        if (group.size() <= 1) continue;
        out << "<br>" << canonical << ": ";
        for (size_t i = 0; i < group.size(); ++i) {
            if (i) out << ", ";
            out << group[i];
        }
    }
    out << "</pre>";
    return out.str();
}

std::string FrameGraphDebugger::format_pass_json() const {
    tc_pass* pass = selected_pass();
    if (!pass) return selected_pass_index_ ? "<no pipeline>" : std::string{};
    return serialize_pass_json(pass);
}

std::string FrameGraphDebugger::format_pass_json_at(size_t pass_index) const {
    RenderPipeline pipeline(resolved_pipeline_);
    if (!pipeline.is_valid() || pass_index >= pipeline.pass_count()) {
        return "<error: pass is unavailable>";
    }
    return serialize_pass_json(pipeline.get_pass_at(pass_index));
}

std::string FrameGraphDebugger::format_timing() const {
    tc_pass* pass = selected_pass();
    if (!pass || selected_symbol_.empty() || pass->kind != TC_NATIVE_PASS) return {};
    CxxFramePass* native = CxxFramePass::from_tc(pass);
    if (!native) return {};
    for (const InternalSymbolTiming& timing : native->get_internal_symbols_with_timing()) {
        if (timing.name != selected_symbol_) continue;
        std::ostringstream out;
        out << std::fixed << std::setprecision(3)
            << "CPU: " << timing.cpu_time_ms << "ms | GPU: ";
        if (timing.gpu_time_ms >= 0.0) out << timing.gpu_time_ms << "ms";
        else out << "pending...";
        return out.str();
    }
    return "Timing: no data";
}

std::string FrameGraphDebugger::format_render_stats() const {
    size_t pipeline_count = 0;
    std::vector<std::string> scene_names;
    std::vector<std::string> pipeline_names;
    for (tc_scene_handle scene : manager_->attached_scenes()) {
        const char* name = tc_scene_get_name(scene);
        scene_names.emplace_back(name ? name : "<unnamed>");
        std::vector<std::string> names = manager_->get_pipeline_names(scene);
        pipeline_count += names.size();
        pipeline_names.insert(pipeline_names.end(), names.begin(), names.end());
    }
    size_t unmanaged = 0;
    auto count_unmanaged = [&](const std::vector<tc_display_handle>& displays) {
        for (tc_display_handle display : displays) {
            for (size_t index = 0; index < tc_display_get_viewport_count(display); ++index) {
                tc_viewport_handle viewport = tc_display_get_viewport_at_index(display, index);
                const char* managed = tc_viewport_get_managed_by(viewport);
                if (!managed || managed[0] == '\0') ++unmanaged;
            }
        }
    };
    count_unmanaged(manager_->displays());
    count_unmanaged(manager_->editor_displays());
    RenderPipelineCacheStats cache;
    if (const RenderEngine* engine = manager_->render_engine_if_created()) {
        cache = engine->pipeline_cache_stats();
    }
    std::ostringstream out;
    out << "Scenes: " << manager_->attached_scenes().size()
        << " | Pipelines: " << pipeline_count
        << " | Unmanaged: " << unmanaged
        << " | PipelineCache: hit=" << cache.hit_count
        << " miss=" << cache.miss_count
        << " create=" << cache.create_pipeline_count
        << " cached=" << cache.cached_pipeline_count
        << " layouts=" << cache.unique_vertex_layout_signature_count;
    return out.str();
}

std::string FrameGraphDebugger::analyze_hdr() {
    if (!capture_.has_capture()) return "No capture available";
    if (capture_.is_depth()) return "HDR stats unavailable for depth texture";
    RenderEngine* engine = manager_->render_engine();
    if (!engine || !engine->tgfx2_device()) return "No tgfx2 device";
    HDRStats stats = presenter_.compute_hdr_stats(
        engine->tgfx2_device(), capture_.capture_tex());
    std::ostringstream out;
    out << std::fixed << std::setprecision(3)
        << "<b>R:</b> " << stats.min_r << " - " << stats.max_r
        << " (avg: " << stats.avg_r << ")<br>"
        << "<b>G:</b> " << stats.min_g << " - " << stats.max_g
        << " (avg: " << stats.avg_g << ")<br>"
        << "<b>B:</b> " << stats.min_b << " - " << stats.max_b
        << " (avg: " << stats.avg_b << ")<br>"
        << "<b>Max:</b> " << stats.max_value << "<br>"
        << "<b>HDR pixels:</b> " << stats.hdr_pixel_count
        << " (" << std::setprecision(2) << stats.hdr_percent << "%)";
    return out.str();
}

void FrameGraphDebugger::finish_render_execution(
    const RenderExecutionInfo& execution,
    FrameGraphCaptureRequest* request
) {
    if (request != &capture_request_ || !execution_matches_target(execution)
            || request->generation != request_generation_) {
        return;
    }
    const FrameGraphDebuggerState next =
        request->status == FrameGraphCaptureRequestStatus::Captured
        ? FrameGraphDebuggerState::Captured
        : FrameGraphDebuggerState::Error;
    if (state_ != next) {
        state_ = next;
        ++revision_;
    }
}

bool FrameGraphDebugger::execution_matches_target(
    const RenderExecutionInfo& execution
) const {
    if (!has_desired_target_
            || !tc_pipeline_handle_eq(execution.pipeline, resolved_pipeline_)) {
        return false;
    }
    for (const RenderExecutionTargetId& target : execution.targets) {
        if (target == desired_target_) return true;
    }
    return false;
}

const RenderExecutionTargetInfo* FrameGraphDebugger::selected_target() const {
    return has_desired_target_ ? find_target(desired_target_) : nullptr;
}

const RenderExecutionTargetInfo* FrameGraphDebugger::find_target(
    const RenderExecutionTargetId& id
) const {
    for (const RenderExecutionTargetInfo& target : targets_) {
        if (target.id == id) return &target;
    }
    return nullptr;
}

void FrameGraphDebugger::invalidate_request() {
    ++request_generation_;
    capture_request_.generation = request_generation_;
    capture_request_.status = FrameGraphCaptureRequestStatus::Pending;
    capture_.reset_capture();
    depth_capture_.reset_capture();
}

void FrameGraphDebugger::set_connection_state(
    FrameGraphDebuggerState state,
    FrameGraphDebuggerSuspendReason reason,
    tc_pipeline_handle pipeline
) {
    state_ = state;
    suspend_reason_ = reason;
    resolved_pipeline_ = pipeline;
}

} // namespace termin
