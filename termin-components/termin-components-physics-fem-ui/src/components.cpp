#include <termin/physics_fem_ui/components.hpp>

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <sstream>
#include <string_view>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/gui_native/label.hpp>
#include <termin/physics_fem/components.hpp>
#include <termin/tc_scene.hpp>
#include <termin/ui/ui_component.hpp>

namespace termin
{
    namespace
    {

        constexpr const char* module_owner = "termin-components-physics-fem-ui";

        tc_widget* find_named_widget(tc_widget* widget, std::string_view name)
        {
            if (widget == nullptr)
            {
                return nullptr;
            }
            const char* widget_name = tc_widget_name(widget);
            if (widget_name != nullptr && widget_name == name)
            {
                return widget;
            }
            const std::size_t child_count = tc_widget_child_count(widget);
            for (std::size_t index = 0; index < child_count; ++index)
            {
                if (tc_widget* found = find_named_widget(
                        tc_widget_child_at(widget, index), name))
                {
                    return found;
                }
            }
            return nullptr;
        }

        tc_widget* find_named_widget(gui_native::TcDocument document,
                                     std::string_view name)
        {
            const std::size_t root_count =
                tc_ui_document_root_count(document.handle());
            for (std::size_t index = 0; index < root_count; ++index)
            {
                tc_widget* root = tc_ui_document_resolve_widget(
                    document.handle(),
                    tc_ui_document_root_at(document.handle(), index));
                if (tc_widget* found = find_named_widget(root, name))
                {
                    return found;
                }
            }
            return nullptr;
        }

        gui_native::Label* find_label(gui_native::TcDocument document,
                                      std::string_view name)
        {
            tc_widget* widget = find_named_widget(document, name);
            if (widget == nullptr ||
                widget->native_language != TC_LANGUAGE_CXX ||
                widget->body == nullptr)
            {
                return nullptr;
            }
            return dynamic_cast<gui_native::Label*>(
                static_cast<gui_native::Widget*>(widget->body));
        }

        std::string format_energy(double energy)
        {
            std::ostringstream stream;
            stream << std::fixed << std::setprecision(3) << energy << " J";
            return stream.str();
        }

        std::string format_energy_change(double current, double initial)
        {
            const double change = current - initial;
            const double relative =
                100.0 * change / std::max(1.0, std::abs(initial));
            std::ostringstream stream;
            stream << std::showpos << std::fixed << std::setprecision(3)
                   << change << " J  (" << std::setprecision(4) << relative
                   << " %)";
            return stream.str();
        }

        std::string format_simulation(const FEMPhysicsTelemetry& telemetry)
        {
            std::ostringstream stream;
            stream << std::fixed << std::setprecision(2)
                   << telemetry.simulated_time << " s   ·   "
                   << telemetry.successful_steps << " steps";
            return stream.str();
        }

        std::string format_topology(const FEMPhysicsTelemetry& telemetry)
        {
            std::ostringstream stream;
            stream << "QP multibody   ·   " << telemetry.body_count
                   << " bodies   ·   " << telemetry.joint_count
                   << " constraints   ·   " << telemetry.articulation_count
                   << " articulations / " << telemetry.reduced_dof_count
                   << " reduced DOF";
            return stream.str();
        }

        std::string format_motors(const FEMPhysicsTelemetry& telemetry)
        {
            std::ostringstream stream;
            stream << telemetry.motor_count << " motors   ·   " << std::fixed
                   << std::setprecision(2) << telemetry.motor_effort_linf
                   << " N·m/N max   ·   " << telemetry.motor_power
                   << " W   ·   " << telemetry.motor_work << " J";
            return stream.str();
        }

        std::string format_servo(const FEMJointServoComponent& servo,
                                 const FEMArticulationMotorComponent& motor)
        {
            if (!servo.initialized() || !motor.initialized())
            {
                return "servo waiting for solver";
            }
            const double error = servo.position_error();
            const double coordinate = servo.target_coordinate - error;
            std::ostringstream stream;
            stream << std::fixed << std::setprecision(2) << "q " << coordinate
                   << " / " << servo.target_coordinate << "   ·   error "
                   << std::showpos << error << std::noshowpos << "   ·   I "
                   << servo.integral_effort() << "   ·   effort "
                   << motor.applied_effort() << " / " << motor.maximum_effort
                   << "   ·   " << motor.power() << " W   ·   "
                   << (motor.saturated() ? "SATURATED" : "tracking");
            return stream.str();
        }

        bool set_label(gui_native::TcDocument document,
                       std::string_view name,
                       std::string text)
        {
            gui_native::Label* label = find_label(document, name);
            if (label == nullptr)
            {
                return false;
            }
            label->set_text(std::move(text));
            return true;
        }

    } // namespace

    FEMPhysicsHudComponent::FEMPhysicsHudComponent()
        : CxxComponent("FEMPhysicsHudComponent")
    {
        set_has_update(true);
    }

    void FEMPhysicsHudComponent::register_type()
    {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<FEMPhysicsHudComponent>(
                "FEMPhysicsHudComponent", module_owner, "Component");
        descriptor.category("Physics");
        auto& inspect = descriptor.inspect();
        tc::stage_inspect_field(inspect,
                                &FEMPhysicsHudComponent::world_entity_name,
                                "FEMPhysicsHudComponent",
                                "world_entity_name",
                                "World Entity",
                                "string");
        tc::stage_inspect_field(inspect,
                                &FEMPhysicsHudComponent::servo_entity_name,
                                "FEMPhysicsHudComponent",
                                "servo_entity_name",
                                "Servo Entity",
                                "string");
        tc::stage_inspect_field(inspect,
                                &FEMPhysicsHudComponent::refresh_interval,
                                "FEMPhysicsHudComponent",
                                "refresh_interval",
                                "Refresh Interval",
                                "double",
                                0.016,
                                10.0,
                                0.01);
        (void)descriptor.commit();
    }

    void FEMPhysicsHudComponent::start()
    {
        CxxComponent::start();
        refresh_accumulator_ = 0.0;
        binding_error_reported_ = false;
        refresh();
    }

    void FEMPhysicsHudComponent::update(float dt)
    {
        if (!enabled())
        {
            return;
        }
        if (!std::isfinite(dt) || dt < 0.0f)
        {
            tc::Log::error("[FEMPhysicsHudComponent] invalid frame dt=%g",
                           static_cast<double>(dt));
            return;
        }
        const double interval = std::max(refresh_interval, 0.016);
        refresh_accumulator_ += static_cast<double>(dt);
        if (refresh_accumulator_ < interval)
        {
            return;
        }
        refresh_accumulator_ = std::fmod(refresh_accumulator_, interval);
        refresh();
    }

    void FEMPhysicsHudComponent::on_destroy()
    {
        refresh_accumulator_ = 0.0;
        binding_error_reported_ = false;
        CxxComponent::on_destroy();
    }

    void FEMPhysicsHudComponent::refresh()
    {
        Entity owner = entity();
        TcSceneRef scene = owner.valid() ? owner.scene() : TcSceneRef{};
        UIComponent* ui =
            owner.valid() ? owner.get_component<UIComponent>() : nullptr;
        Entity world_entity = scene.valid()
                                  ? scene.find_entity_by_name(world_entity_name)
                                  : Entity{};
        FEMPhysicsWorldComponent* world =
            world_entity.valid()
                ? world_entity.get_component<FEMPhysicsWorldComponent>()
                : nullptr;
        const gui_native::TcDocument document =
            ui != nullptr ? ui->document() : gui_native::TcDocument{};

        if (world == nullptr || !document.valid())
        {
            if (!binding_error_reported_)
            {
                tc::Log::error(
                    "[FEMPhysicsHudComponent] requires a UIComponent on its "
                    "entity and FEMPhysicsWorldComponent on entity '%s'",
                    world_entity_name.c_str());
                binding_error_reported_ = true;
            }
            return;
        }

        const FEMPhysicsTelemetry telemetry = world->telemetry();
        const bool complete =
            set_label(document,
                      "energy_value",
                      telemetry.initialized
                          ? format_energy(telemetry.total_energy)
                          : "waiting for solver") &&
            set_label(document,
                      "energy_change",
                      telemetry.initialized
                          ? format_energy_change(telemetry.total_energy,
                                                 telemetry.initial_total_energy)
                          : "Δ from start") &&
            set_label(
                document, "simulation_value", format_simulation(telemetry)) &&
            set_label(document, "topology_value", format_topology(telemetry));
        if (find_label(document, "motor_value") != nullptr)
        {
            (void)set_label(document, "motor_value", format_motors(telemetry));
        }
        if (!servo_entity_name.empty() &&
            find_label(document, "servo_value") != nullptr)
        {
            Entity servo_entity = scene.find_entity_by_name(servo_entity_name);
            FEMJointServoComponent* servo =
                servo_entity.valid()
                    ? servo_entity.get_component<FEMJointServoComponent>()
                    : nullptr;
            FEMArticulationMotorComponent* motor =
                servo_entity.valid()
                    ? servo_entity
                          .get_component<FEMArticulationMotorComponent>()
                    : nullptr;
            if (servo == nullptr || motor == nullptr)
            {
                if (!binding_error_reported_)
                {
                    tc::Log::error(
                        "[FEMPhysicsHudComponent] entity '%s' has no "
                        "FEMJointServoComponent and "
                        "FEMArticulationMotorComponent pair",
                        servo_entity_name.c_str());
                    binding_error_reported_ = true;
                }
                return;
            }
            (void)set_label(
                document, "servo_value", format_servo(*servo, *motor));
        }
        if (!complete && !binding_error_reported_)
        {
            tc::Log::error(
                "[FEMPhysicsHudComponent] HUD layout does not contain all "
                "required Label widgets");
            binding_error_reported_ = true;
            return;
        }
        binding_error_reported_ = false;
    }

} // namespace termin
