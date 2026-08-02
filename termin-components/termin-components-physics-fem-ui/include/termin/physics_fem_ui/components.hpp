#pragma once

#include <string>

#include <termin/entity/component.hpp>

namespace termin
{

    class ENTITY_API FEMPhysicsHudComponent final : public CxxComponent
    {
    public:
        std::string world_entity_name = "FEM Physics World";
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

        void refresh();
    };

} // namespace termin
