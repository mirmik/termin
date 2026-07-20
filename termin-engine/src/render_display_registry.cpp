#include "render_display_registry.hpp"

#include <algorithm>

namespace termin::rendering_manager_detail {

void RenderDisplayRegistry::add_display(tc_display_handle display) {
    if (!tc_display_alive(display)) return;

    auto it = std::find(displays_.begin(), displays_.end(), display);
    if (it != displays_.end()) return;

    displays_.push_back(display);
}

void RenderDisplayRegistry::remove_display(
    tc_display_handle display,
    const ViewportCleanupCallback& cleanup_viewport,
    const DisplayRemovedCallback& removed_callback
) {
    if (!tc_display_alive(display)) return;

    auto it = std::find(displays_.begin(), displays_.end(), display);
    bool is_editor = false;
    if (it == displays_.end()) {
        it = std::find(editor_displays_.begin(), editor_displays_.end(), display);
        if (it == editor_displays_.end()) return;
        is_editor = true;
    }

    cleanup_viewport_states(display, cleanup_viewport);

    if (is_editor) {
        editor_displays_.erase(it);
    } else {
        displays_.erase(it);
    }

    if (removed_callback) {
        removed_callback(display);
    }
}

void RenderDisplayRegistry::add_editor_display(tc_display_handle display) {
    if (!tc_display_alive(display)) return;

    auto it = std::find(editor_displays_.begin(), editor_displays_.end(), display);
    if (it != editor_displays_.end()) return;

    editor_displays_.push_back(display);
}

void RenderDisplayRegistry::remove_editor_display(
    tc_display_handle display,
    const ViewportCleanupCallback& cleanup_viewport
) {
    if (!tc_display_alive(display)) return;

    auto it = std::find(editor_displays_.begin(), editor_displays_.end(), display);
    if (it == editor_displays_.end()) return;

    cleanup_viewport_states(display, cleanup_viewport);
    editor_displays_.erase(it);
}

bool RenderDisplayRegistry::try_auto_remove_display(
    tc_display_handle display,
    const ViewportCleanupCallback& cleanup_viewport,
    const DisplayRemovedCallback& removed_callback
) {
    if (!tc_display_alive(display)) return false;
    if (!tc_display_get_auto_remove_when_empty(display)) return false;
    if (tc_display_get_viewport_count(display) > 0) return false;

    remove_display(display, cleanup_viewport, removed_callback);
    return true;
}

tc_input_manager* RenderDisplayRegistry::display_input_endpoint(tc_display_handle display) {
    return tc_display_get_input_manager(display);
}

tc_display_handle RenderDisplayRegistry::get_display_by_name(const std::string& name) const {
    for (tc_display_handle d : displays_) {
        const char* dname = tc_display_get_name(d);
        if (dname && name == dname) {
            return d;
        }
    }
    for (tc_display_handle d : editor_displays_) {
        const char* dname = tc_display_get_name(d);
        if (dname && name == dname) {
            return d;
        }
    }
    return TC_DISPLAY_HANDLE_INVALID;
}

tc_display_handle RenderDisplayRegistry::get_or_create_display(
    const std::string& name,
    const DisplayFactory& factory
) {
    tc_display_handle display = get_display_by_name(name);
    if (tc_display_alive(display)) {
        return display;
    }

    if (factory) {
        display = factory(name);
        if (tc_display_alive(display)) {
            add_display(display);
            return display;
        }
    }

    return TC_DISPLAY_HANDLE_INVALID;
}

void RenderDisplayRegistry::clear() {
    displays_.clear();
    editor_displays_.clear();
}

void RenderDisplayRegistry::cleanup_viewport_states(
    tc_display_handle display,
    const ViewportCleanupCallback& cleanup_viewport
) {
    if (!cleanup_viewport) return;

    tc_viewport_handle vp = tc_display_get_first_viewport(display);
    while (tc_viewport_handle_valid(vp)) {
        cleanup_viewport(vp);
        vp = tc_viewport_get_display_next(vp);
    }
}

} // namespace termin::rendering_manager_detail
