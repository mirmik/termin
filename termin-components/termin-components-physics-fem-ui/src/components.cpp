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

#ifdef TERMIN_PHYSICS_FEM_UI_HAS_TCPLOT
#include <tcplot/gui_native/plot2d.hpp>
#include <tcplot/styles.hpp>
#endif

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

#ifdef TERMIN_PHYSICS_FEM_UI_HAS_TCPLOT
        tcplot::gui_native::Plot2D* find_plot(gui_native::TcDocument document,
                                              std::string_view name)
        {
            tc_widget* widget = find_named_widget(document, name);
            if (widget == nullptr ||
                widget->native_language != TC_LANGUAGE_CXX ||
                widget->body == nullptr)
            {
                return nullptr;
            }
            return dynamic_cast<tcplot::gui_native::Plot2D*>(
                static_cast<gui_native::Widget*>(widget->body));
        }
#endif

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
                                &FEMPhysicsHudComponent::plot_widget_name,
                                "FEMPhysicsHudComponent",
                                "plot_widget_name",
                                "Plot Widget",
                                "string");
        tc::stage_inspect_field(
            inspect,
            &FEMPhysicsHudComponent::effort_plot_widget_name,
            "FEMPhysicsHudComponent",
            "effort_plot_widget_name",
            "Effort Plot Widget",
            "string");
        tc::stage_inspect_field(inspect,
                                &FEMPhysicsHudComponent::plot_history,
                                "FEMPhysicsHudComponent",
                                "plot_history",
                                "Plot History",
                                "double",
                                1.0,
                                600.0,
                                1.0);
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
        plot_time_.clear();
        plot_coordinate_.clear();
        plot_target_.clear();
        plot_position_effort_.clear();
        plot_integral_effort_.clear();
        plot_velocity_effort_.clear();
        plot_commanded_effort_.clear();
        plot_applied_effort_.clear();
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
        plot_time_.clear();
        plot_coordinate_.clear();
        plot_target_.clear();
        plot_position_effort_.clear();
        plot_integral_effort_.clear();
        plot_velocity_effort_.clear();
        plot_commanded_effort_.clear();
        plot_applied_effort_.clear();
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
        if (!servo_entity_name.empty())
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
            if (find_label(document, "servo_value") != nullptr)
            {
                (void)set_label(
                    document, "servo_value", format_servo(*servo, *motor));
            }
#ifdef TERMIN_PHYSICS_FEM_UI_HAS_TCPLOT
            tcplot::gui_native::Plot2D* coordinate_plot =
                find_plot(document, plot_widget_name);
            tcplot::gui_native::Plot2D* effort_plot =
                find_plot(document, effort_plot_widget_name);
            if ((coordinate_plot != nullptr || effort_plot != nullptr) &&
                telemetry.initialized && servo->initialized())
            {
                if (!plot_time_.empty() &&
                    telemetry.simulated_time < plot_time_.back())
                {
                    plot_time_.clear();
                    plot_coordinate_.clear();
                    plot_target_.clear();
                    plot_position_effort_.clear();
                    plot_integral_effort_.clear();
                    plot_velocity_effort_.clear();
                    plot_commanded_effort_.clear();
                    plot_applied_effort_.clear();
                }
                const double coordinate =
                    servo->target_coordinate - servo->position_error();
                plot_time_.push_back(telemetry.simulated_time);
                plot_coordinate_.push_back(coordinate);
                plot_target_.push_back(servo->target_coordinate);
                plot_position_effort_.push_back(servo->position_effort());
                plot_integral_effort_.push_back(servo->integral_effort());
                plot_velocity_effort_.push_back(servo->velocity_effort());
                plot_commanded_effort_.push_back(servo->commanded_effort());
                plot_applied_effort_.push_back(motor->applied_effort());

                const double first_time =
                    telemetry.simulated_time - std::max(plot_history, 1.0);
                const auto first = std::lower_bound(
                    plot_time_.begin(), plot_time_.end(), first_time);
                const std::size_t erase_count =
                    static_cast<std::size_t>(first - plot_time_.begin());
                if (erase_count > 0)
                {
                    plot_time_.erase(plot_time_.begin(), first);
                    plot_coordinate_.erase(plot_coordinate_.begin(),
                                           plot_coordinate_.begin() +
                                               erase_count);
                    plot_target_.erase(plot_target_.begin(),
                                       plot_target_.begin() + erase_count);
                    plot_position_effort_.erase(
                        plot_position_effort_.begin(),
                        plot_position_effort_.begin() + erase_count);
                    plot_integral_effort_.erase(
                        plot_integral_effort_.begin(),
                        plot_integral_effort_.begin() + erase_count);
                    plot_velocity_effort_.erase(
                        plot_velocity_effort_.begin(),
                        plot_velocity_effort_.begin() + erase_count);
                    plot_commanded_effort_.erase(
                        plot_commanded_effort_.begin(),
                        plot_commanded_effort_.begin() + erase_count);
                    plot_applied_effort_.erase(
                        plot_applied_effort_.begin(),
                        plot_applied_effort_.begin() + erase_count);
                }

                if (coordinate_plot != nullptr)
                {
                    if (coordinate_plot->line_count() != 2)
                    {
                        coordinate_plot->clear_lines();
                        coordinate_plot->add_line();
                        tcplot::PlotLineSeriesStyle2D target_style;
                        target_style.color = tcplot::styles::cycle_color(1);
                        target_style.line_style = tcplot::LineStyle::Dash;
                        coordinate_plot->add_line(target_style);
                    }
                    (void)coordinate_plot->set_line_data(
                        0, plot_time_, plot_coordinate_);
                    (void)coordinate_plot->set_line_data(
                        1, plot_time_, plot_target_);
                }
                if (effort_plot != nullptr)
                {
                    if (effort_plot->line_count() != 5)
                    {
                        effort_plot->clear_lines();
                        effort_plot->add_line();
                        effort_plot->add_line();
                        effort_plot->add_line();
                        tcplot::PlotLineSeriesStyle2D commanded_style;
                        commanded_style.color = tcplot::styles::cycle_color(4);
                        effort_plot->add_line(commanded_style);
                        tcplot::PlotLineSeriesStyle2D applied_style;
                        applied_style.color = tcplot::styles::cycle_color(3);
                        applied_style.line_style = tcplot::LineStyle::Dash;
                        effort_plot->add_line(applied_style);
                    }
                    (void)effort_plot->set_line_data(
                        0, plot_time_, plot_position_effort_);
                    (void)effort_plot->set_line_data(
                        1, plot_time_, plot_integral_effort_);
                    (void)effort_plot->set_line_data(
                        2, plot_time_, plot_velocity_effort_);
                    (void)effort_plot->set_line_data(
                        3, plot_time_, plot_commanded_effort_);
                    (void)effort_plot->set_line_data(
                        4, plot_time_, plot_applied_effort_);
                }
            }
#endif
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
