#pragma once

#include <string>
#include <vector>

#include <termin/entity/component.hpp>

namespace termin {

    class ENTITY_API FEMPhysicsHudComponent final : public CxxComponent {
    public:
        std::string world_entity_name = "FEM Physics World";
        // Optional. When set, a co-located servo diagnostic row named
        // "servo_value" is updated in addition to aggregate world telemetry.
        std::string servo_entity_name;
        // Optional articulation root and checkbox used to enable or disable
        // every descendant servo as one UI control.
        std::string servo_group_root_entity_name;
        std::string servo_group_checkbox_name = "servo_group_enabled";
        // Optional. When set, a co-located FEM rigid body is reported through
        // the "body_value" label using its world pose and local spatial speed.
        std::string tracked_body_entity_name;
        std::string plot_widget_name = "servo_plot";
        std::string effort_plot_widget_name = "servo_effort_plot";
        std::string contact_gap_plot_widget_name = "contact_gap_plot";
        std::string contact_reaction_plot_widget_name = "contact_reaction_plot";
        double plot_history = 30.0;
        double refresh_interval = 0.1;

        FEMPhysicsHudComponent();
        ~FEMPhysicsHudComponent() override = default;

        static void register_type();

        void start() override;
        void update(float dt) override;
        void on_destroy() override;

    private:
        double refresh_accumulator_ = 0.0;
        bool binding_error_reported_ = false;
        bool servo_group_state_known_ = false;
        bool servo_group_enabled_ = true;
        std::vector<double> plot_time_;
        std::vector<double> plot_coordinate_;
        std::vector<double> plot_target_;
        std::vector<double> plot_position_effort_;
        std::vector<double> plot_integral_effort_;
        std::vector<double> plot_velocity_effort_;
        std::vector<double> plot_commanded_effort_;
        std::vector<double> plot_applied_effort_;
        std::vector<double> contact_plot_time_;
        std::vector<double> contact_plot_gap_;
        std::vector<double> contact_plot_reaction_;

        void refresh();
    };

} // namespace termin
