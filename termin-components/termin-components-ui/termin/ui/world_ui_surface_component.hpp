#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include <termin/entity/component.hpp>
#include <termin/export.hpp>

extern "C" {
#include <termin/input/tc_world_pointer_surface.h>
}

namespace termin {

class ENTITY_API WorldUiSurfaceComponent final : public CxxComponent {
public:
    std::string ui_entity_uuid;
    double local_width = 1.0;
    double local_height = 1.0;
    bool two_sided = false;

    WorldUiSurfaceComponent();

    static void register_type();

    bool project_ray(
        const tc_world_pointer_ray& ray,
        tc_world_pointer_hit& out_hit);
    bool dispatch_pointer(const tc_world_pointer_event& event);

    void on_removed() override;
    void on_destroy() override;
    void on_scene_inactive() override;

private:
    std::optional<std::uint64_t> last_pointer_id_;
    bool logged_missing_ui_ = false;
    bool logged_invalid_transform_ = false;

    class UIComponent* resolve_ui_component();
    void cancel_last_pointer();
};

} // namespace termin
