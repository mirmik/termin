#pragma once

#include <core/tc_scene_pool.h>

namespace termin::web {
    // The entry scene currently attached to the browser render host.
    tc_scene_handle active_scene();
} // namespace termin::web
