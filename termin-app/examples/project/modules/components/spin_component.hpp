#pragma once

#include <cstdio>
#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/geom/geom.hpp>

namespace game {

class SpinComponent : public termin::CxxComponent {
public:
    float speed = 90.0f;  // degrees per second

    INSPECT_FIELD(SpinComponent, speed, "Speed", "float", -360.0, 360.0, 1.0)

    SpinComponent() {}

    void update(float dt) override;
};

REGISTER_COMPONENT(SpinComponent, Component);

} // namespace game
