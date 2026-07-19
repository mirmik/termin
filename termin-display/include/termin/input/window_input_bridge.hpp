#pragma once

#include "render/termin_display_api.h"

struct tc_display;

namespace termin {

class BackendWindow;
struct WindowEvent;

TERMIN_DISPLAY_API void dispatch_window_input_event(
    tc_display* display,
    const WindowEvent& event);

TERMIN_DISPLAY_API void attach_window_input_display(
    BackendWindow& window,
    tc_display* display);

} // namespace termin
