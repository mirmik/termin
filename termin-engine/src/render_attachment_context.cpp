#include "termin/render/render_attachment_context.hpp"

#include "termin/render/render_topology.hpp"

#include <stdexcept>

extern "C" {
#include <tcbase/tc_log.h>
#include "render/tc_render_target.h"
}

namespace termin {

struct RenderAttachmentContext::State {
    RenderTopology* topology = nullptr;
    tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
    bool active = false;
};

RenderAttachmentContext::RenderAttachmentContext(
    RenderTopology& topology,
    tc_scene_handle scene
) : state_(std::make_shared<State>()) {
    state_->topology = &topology;
    state_->scene = scene;
    state_->active = true;
    invalidates_on_destruction_ = true;
}

RenderAttachmentContext::RenderAttachmentContext(const RenderAttachmentContext& other)
    : state_(other.state_), invalidates_on_destruction_(false) {
}

RenderAttachmentContext& RenderAttachmentContext::operator=(
    const RenderAttachmentContext& other
) {
    if (this == &other) return *this;
    if (invalidates_on_destruction_) invalidate();
    state_ = other.state_;
    invalidates_on_destruction_ = false;
    return *this;
}

RenderAttachmentContext::~RenderAttachmentContext() {
    if (invalidates_on_destruction_) invalidate();
}

void RenderAttachmentContext::invalidate() {
    if (state_) state_->active = false;
}

bool RenderAttachmentContext::valid() const {
    return state_ && state_->active && state_->topology != nullptr
        && tc_scene_handle_valid(state_->scene);
}

const RenderAttachmentContext::State& RenderAttachmentContext::require_active() const {
    if (!valid()) {
        tc_log(TC_LOG_ERROR, "[RenderAttachmentContext] Used outside lifecycle callback");
        throw std::logic_error("RenderAttachmentContext is no longer active");
    }
    return *state_;
}

tc_scene_handle RenderAttachmentContext::scene() const {
    return require_active().scene;
}

std::vector<tc_render_target_handle> RenderAttachmentContext::render_targets() const {
    const State& state = require_active();
    const auto& targets = state.topology->render_targets(state.scene);
    return {targets.begin(), targets.end()};
}

tc_render_target_handle RenderAttachmentContext::find_render_target(
    const std::string& name
) const {
    const State& state = require_active();
    return state.topology->find_render_target(state.scene, name);
}

tc_render_target_handle RenderAttachmentContext::find_camera_target(
    const tc_component* camera
) const {
    if (camera == nullptr) return TC_RENDER_TARGET_HANDLE_INVALID;
    for (tc_render_target_handle target : render_targets()) {
        if (tc_render_target_handle_valid(target)
                && tc_render_target_get_camera(target) == camera) {
            return target;
        }
    }
    return TC_RENDER_TARGET_HANDLE_INVALID;
}

tc_pipeline_handle RenderAttachmentContext::get_pipeline(const std::string& name) const {
    const State& state = require_active();
    return state.topology->get_pipeline(state.scene, name);
}

} // namespace termin

namespace {

const termin::RenderAttachmentContext* context_from_c(
    const tc_render_attachment_context* context
) {
    return reinterpret_cast<const termin::RenderAttachmentContext*>(context);
}

} // namespace

extern "C" {

bool tc_render_attachment_context_valid(const tc_render_attachment_context* context) {
    const auto* typed = context_from_c(context);
    return typed != nullptr && typed->valid();
}

tc_scene_handle tc_render_attachment_context_scene(const tc_render_attachment_context* context) {
    const auto* typed = context_from_c(context);
    return typed && typed->valid() ? typed->scene() : TC_SCENE_HANDLE_INVALID;
}

size_t tc_render_attachment_context_render_target_count(
    const tc_render_attachment_context* context
) {
    const auto* typed = context_from_c(context);
    return typed && typed->valid() ? typed->render_targets().size() : 0;
}

tc_render_target_handle tc_render_attachment_context_render_target_at(
    const tc_render_attachment_context* context,
    size_t index
) {
    const auto* typed = context_from_c(context);
    if (!typed || !typed->valid()) return TC_RENDER_TARGET_HANDLE_INVALID;
    const auto targets = typed->render_targets();
    return index < targets.size() ? targets[index] : TC_RENDER_TARGET_HANDLE_INVALID;
}

tc_render_target_handle tc_render_attachment_context_find_render_target(
    const tc_render_attachment_context* context,
    const char* name
) {
    const auto* typed = context_from_c(context);
    if (!typed || !typed->valid() || !name) return TC_RENDER_TARGET_HANDLE_INVALID;
    return typed->find_render_target(name);
}

tc_render_target_handle tc_render_attachment_context_find_camera_target(
    const tc_render_attachment_context* context,
    const tc_component* camera
) {
    const auto* typed = context_from_c(context);
    if (!typed || !typed->valid()) return TC_RENDER_TARGET_HANDLE_INVALID;
    return typed->find_camera_target(camera);
}

tc_pipeline_handle tc_render_attachment_context_get_pipeline(
    const tc_render_attachment_context* context,
    const char* name
) {
    const auto* typed = context_from_c(context);
    if (!typed || !typed->valid() || !name) return TC_PIPELINE_HANDLE_INVALID;
    return typed->get_pipeline(name);
}

} // extern "C"
