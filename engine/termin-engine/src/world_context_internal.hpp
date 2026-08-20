#pragma once

#include <termin/engine/world_context.h>

namespace termin {
    namespace engine_detail {

        tc_world_context* create_world_context(tc_world_controller_instance* controller) noexcept;
        void invalidate_world_context(tc_world_context* context) noexcept;
        bool bind_world_context_scene(tc_world_context* context, tc_scene_handle scene) noexcept;
        bool unbind_world_context_scene(tc_world_context* context, tc_scene_handle scene) noexcept;
        tc_scene_handle take_world_context_primary_request(tc_world_context* context) noexcept;
        bool publish_world_context_primary_scene(tc_world_context* context,
                                                 tc_scene_handle scene) noexcept;
        void clear_world_context_scene_references(tc_world_context* context,
                                                  tc_scene_handle scene) noexcept;

    } // namespace engine_detail
} // namespace termin
