#pragma once

#include <functional>
#include <string>
#include <vector>

extern "C" {
#include "render/tc_display.h"
#include "render/tc_viewport.h"
}

namespace termin::rendering_manager_detail {

class RenderDisplayRegistry {
private:
    std::vector<tc_display*> displays_;
    std::vector<tc_display*> editor_displays_;

public:
    using DisplayFactory = std::function<tc_display*(const std::string& name)>;
    using DisplayRemovedCallback = std::function<void(tc_display*)>;
    using ViewportCleanupCallback = std::function<void(tc_viewport_handle)>;

    const std::vector<tc_display*>& displays() const { return displays_; }
    const std::vector<tc_display*>& editor_displays() const { return editor_displays_; }

    void add_display(tc_display* display);
    void remove_display(
        tc_display* display,
        const ViewportCleanupCallback& cleanup_viewport,
        const DisplayRemovedCallback& removed_callback
    );

    void add_editor_display(tc_display* display);
    void remove_editor_display(tc_display* display, const ViewportCleanupCallback& cleanup_viewport);

    bool try_auto_remove_display(
        tc_display* display,
        const ViewportCleanupCallback& cleanup_viewport,
        const DisplayRemovedCallback& removed_callback
    );

    tc_input_manager* display_input_endpoint(tc_display* display);

    tc_display* get_display_by_name(const std::string& name) const;
    tc_display* get_or_create_display(const std::string& name, const DisplayFactory& factory);

    void clear();

private:
    void cleanup_viewport_states(tc_display* display, const ViewportCleanupCallback& cleanup_viewport);

};

} // namespace termin::rendering_manager_detail
