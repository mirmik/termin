#pragma once

#include <string>
#include <vector>

#include <termin/entity/component.hpp>

namespace termin
{

    class ENTITY_API FEMPhysicsHudComponent final : public CxxComponent
    {
    public:
        std::string world_entity_name = "FEM Physics World";
        // Optional. When set, a co-located servo diagnostic row named
        // "servo_value" is updated in addition to aggregate world telemetry.
        std::string servo_entity_name;
        std::string plot_widget_name = "servo_plot";
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
        std::vector<double> plot_time_;
        std::vector<double> plot_coordinate_;
        std::vector<double> plot_target_;

        void refresh();
    };

} // namespace termin
