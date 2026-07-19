#pragma once

#include "render/termin_display_api.h"

struct tc_input_manager;

namespace termin {

class BackendWindow;

TERMIN_DISPLAY_API void attach_window_input_manager(
    BackendWindow& window,
    tc_input_manager* input_manager);

} // namespace termin
