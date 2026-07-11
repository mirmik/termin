#pragma once

#include "termin/render/viewport_render_state.hpp"

#include <cstdint>
#include <functional>
#include <memory>
#include <unordered_map>

extern "C" {
#include "render/tc_render_target.h"
#include "render/tc_viewport.h"
}

namespace termin::rendering_manager_detail {

class RenderStateStore {
private:
    std::unordered_map<uint64_t, std::unique_ptr<ViewportRenderState>> viewport_states_;
    std::unordered_map<uint64_t, std::unique_ptr<ViewportRenderState>> render_target_states_;

public:
    using MakeCurrent = std::function<void()>;

    ViewportRenderState* get_viewport_state(tc_viewport_handle viewport);
    ViewportRenderState* get_or_create_viewport_state(tc_viewport_handle viewport);
    void remove_viewport_state(tc_viewport_handle viewport, const MakeCurrent& make_current);

    ViewportRenderState* get_render_target_state(tc_render_target_handle rt);
    ViewportRenderState* get_or_create_render_target_state(tc_render_target_handle rt);
    void remove_render_target_state(tc_render_target_handle rt, const MakeCurrent& make_current);

    void clear_all(const MakeCurrent& make_current);

private:
    static uint64_t viewport_key(tc_viewport_handle h);
    static uint64_t render_target_key(tc_render_target_handle h);

};

} // namespace termin::rendering_manager_detail
