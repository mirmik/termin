#include "render_state_store.hpp"

namespace termin::rendering_manager_detail {

uint64_t RenderStateStore::viewport_key(tc_viewport_handle h) {
    return (static_cast<uint64_t>(h.index) << 32) | h.generation;
}

uint64_t RenderStateStore::render_target_key(tc_render_target_handle h) {
    return (static_cast<uint64_t>(h.index) << 32) | h.generation;
}

ViewportRenderState* RenderStateStore::get_viewport_state(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport)) return nullptr;
    uint64_t key = viewport_key(viewport);
    auto it = viewport_states_.find(key);
    return (it != viewport_states_.end()) ? it->second.get() : nullptr;
}

ViewportRenderState* RenderStateStore::get_or_create_viewport_state(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport)) return nullptr;
    uint64_t key = viewport_key(viewport);
    auto& state = viewport_states_[key];
    if (!state) {
        state = std::make_unique<ViewportRenderState>();
    }
    return state.get();
}

void RenderStateStore::remove_viewport_state(tc_viewport_handle viewport) {
    if (!tc_viewport_handle_valid(viewport)) return;
    uint64_t key = viewport_key(viewport);
    auto it = viewport_states_.find(key);
    if (it == viewport_states_.end()) return;
    it->second->clear_all();
    viewport_states_.erase(it);
}

ViewportRenderState* RenderStateStore::get_render_target_state(tc_render_target_handle rt) {
    if (!tc_render_target_handle_valid(rt)) return nullptr;
    uint64_t key = render_target_key(rt);
    auto it = render_target_states_.find(key);
    return it != render_target_states_.end() ? it->second.get() : nullptr;
}

ViewportRenderState* RenderStateStore::get_or_create_render_target_state(tc_render_target_handle rt) {
    if (!tc_render_target_handle_valid(rt)) return nullptr;
    uint64_t key = render_target_key(rt);
    auto it = render_target_states_.find(key);
    if (it != render_target_states_.end()) return it->second.get();
    auto& state = render_target_states_[key];
    state = std::make_unique<ViewportRenderState>();
    return state.get();
}

void RenderStateStore::remove_render_target_state(tc_render_target_handle rt) {
    if (!tc_render_target_handle_valid(rt)) return;
    uint64_t key = render_target_key(rt);
    auto it = render_target_states_.find(key);
    if (it == render_target_states_.end()) return;
    it->second->clear_all();
    render_target_states_.erase(it);
}

void RenderStateStore::clear_all() {
    for (auto& pair : viewport_states_) {
        pair.second->clear_all();
    }
    viewport_states_.clear();

    for (auto& pair : render_target_states_) {
        pair.second->clear_all();
    }
    render_target_states_.clear();
}

} // namespace termin::rendering_manager_detail
