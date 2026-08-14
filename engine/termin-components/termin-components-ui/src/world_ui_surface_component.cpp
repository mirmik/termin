#include <termin/ui/world_ui_surface_component.hpp>

#include <cmath>
#include <exception>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.h>
#include <termin/entity/component_registry.hpp>
#include <termin/tc_scene.hpp>
#include <termin/ui/ui_component.hpp>

namespace termin {
    namespace {

        WorldUiSurfaceComponent* resolve_surface(tc_component* component) {
            if (!component)
                return nullptr;
            CxxComponent* base = CxxComponent::from_tc(component);
            WorldUiSurfaceComponent* surface = dynamic_cast<WorldUiSurfaceComponent*>(base);
            if (!surface) {
                tc_log_error("[WorldUiSurfaceComponent] world-pointer capability attached "
                             "to the wrong component type");
            }
            return surface;
        }

        bool
        project_surface_ray(tc_component* component, const tc_world_pointer_ray* ray, tc_world_pointer_hit* out_hit) {
            WorldUiSurfaceComponent* surface = resolve_surface(component);
            return surface && ray && out_hit && surface->project_ray(*ray, *out_hit);
        }

        bool dispatch_surface_pointer(tc_component* component, const tc_world_pointer_event* event) {
            WorldUiSurfaceComponent* surface = resolve_surface(component);
            return surface && event && surface->dispatch_pointer(*event);
        }

        const tc_world_pointer_surface_vtable kWorldUiSurfaceVtable = {
            .project_ray = project_surface_ray,
            .dispatch_pointer = dispatch_surface_pointer,
        };

    } // namespace

    WorldUiSurfaceComponent::WorldUiSurfaceComponent()
        : CxxComponent("WorldUiSurfaceComponent") {
        if (!tc_world_pointer_surface_capability_attach(&_c, &kWorldUiSurfaceVtable, this)) {
            tc_log_error("[WorldUiSurfaceComponent] failed to attach world-pointer "
                         "surface capability");
        }
    }

    void WorldUiSurfaceComponent::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<WorldUiSurfaceComponent>(
            "WorldUiSurfaceComponent", "termin-components-ui", "CxxComponent");
        descriptor.category("UI");
        descriptor.capability(tc_world_pointer_surface_capability_id());
        auto& inspect = descriptor.inspect();
        inspect.add<WorldUiSurfaceComponent, std::string>("WorldUiSurfaceComponent",
                                                          &WorldUiSurfaceComponent::ui_entity_uuid,
                                                          "ui_entity_uuid",
                                                          "UI Entity UUID",
                                                          "string");
        inspect.add<WorldUiSurfaceComponent, double>(
            "WorldUiSurfaceComponent", &WorldUiSurfaceComponent::local_width, "local_width", "Local Width", "double");
        inspect.add<WorldUiSurfaceComponent, double>("WorldUiSurfaceComponent",
                                                     &WorldUiSurfaceComponent::local_height,
                                                     "local_height",
                                                     "Local Height",
                                                     "double");
        inspect.add<WorldUiSurfaceComponent, bool>(
            "WorldUiSurfaceComponent", &WorldUiSurfaceComponent::two_sided, "two_sided", "Two Sided", "bool");
        (void)descriptor.commit();
    }

    bool WorldUiSurfaceComponent::project_ray(const tc_world_pointer_ray& ray, tc_world_pointer_hit& out_hit) {
        if (!entity().valid() || local_width <= 0.0 || local_height <= 0.0 || ray.max_distance <= 0.0) {
            return false;
        }

        try {
            const GeneralTransform3 transform = entity().transform();
            const Vec3 local_origin = transform.transform_point_inverse({ray.origin_x, ray.origin_y, ray.origin_z});
            const Vec3 local_direction =
                transform.transform_vector_inverse({ray.direction_x, ray.direction_y, ray.direction_z});
            constexpr double parallel_epsilon = 1.0e-10;
            if (std::abs(local_direction.z) <= parallel_epsilon)
                return false;
            if (!two_sided && local_direction.z >= -parallel_epsilon)
                return false;

            const double distance = -local_origin.z / local_direction.z;
            if (distance < 0.0 || distance > ray.max_distance)
                return false;

            const Vec3 local_hit = local_origin + local_direction * distance;
            out_hit.distance = distance;
            out_hit.u = local_hit.x / local_width + 0.5;
            out_hit.v = 0.5 - local_hit.y / local_height;
            out_hit.inside = out_hit.u >= 0.0 && out_hit.u <= 1.0 && out_hit.v >= 0.0 && out_hit.v <= 1.0;
            logged_invalid_transform_ = false;
            return true;
        } catch (const std::exception& error) {
            if (!logged_invalid_transform_) {
                tc_log_error(
                    "[WorldUiSurfaceComponent] cannot project ray onto '%s': %s", entity().name(), error.what());
                logged_invalid_transform_ = true;
            }
            return false;
        }
    }

    UIComponent* WorldUiSurfaceComponent::resolve_ui_component() {
        if (!entity().valid())
            return nullptr;
        Entity target = ui_entity_uuid.empty() ? entity() : entity().scene().get_entity(ui_entity_uuid);
        UIComponent* ui = target.valid() ? target.get_component<UIComponent>() : nullptr;
        if (!ui) {
            if (!logged_missing_ui_) {
                tc_log_error("[WorldUiSurfaceComponent] surface '%s' cannot resolve "
                             "UIComponent on entity uuid='%s'",
                             entity().name(),
                             ui_entity_uuid.empty() ? entity().uuid() : ui_entity_uuid.c_str());
                logged_missing_ui_ = true;
            }
            return nullptr;
        }
        logged_missing_ui_ = false;
        return ui;
    }

    bool WorldUiSurfaceComponent::dispatch_pointer(const tc_world_pointer_event& event) {
        UIComponent* ui = resolve_ui_component();
        if (!ui)
            return false;
        const bool handled = ui->dispatch_world_pointer(event);
        if (event.phase == TC_WORLD_POINTER_UP || event.phase == TC_WORLD_POINTER_LEAVE ||
            event.phase == TC_WORLD_POINTER_CANCEL) {
            last_pointer_id_.reset();
        } else {
            last_pointer_id_ = event.pointer_id;
        }
        return handled;
    }

    void WorldUiSurfaceComponent::cancel_last_pointer() {
        if (!last_pointer_id_)
            return;
        UIComponent* ui = resolve_ui_component();
        if (ui) {
            tc_world_pointer_event event{};
            event.pointer_id = *last_pointer_id_;
            event.phase = TC_WORLD_POINTER_CANCEL;
            ui->dispatch_world_pointer(event);
        }
        last_pointer_id_.reset();
    }

    void WorldUiSurfaceComponent::on_removed() {
        cancel_last_pointer();
    }
    void WorldUiSurfaceComponent::on_destroy() {
        cancel_last_pointer();
    }
    void WorldUiSurfaceComponent::on_scene_inactive() {
        cancel_last_pointer();
    }

} // namespace termin
