#pragma once

// @file physics.hpp
// @brief Единый include для модуля физики.

#include <string_view>

#include <termin/physics/contact_solver.hpp>
#include <termin/physics/physics_world.hpp>
#include <termin/physics/rigid_body.hpp>
#include <termin/physics/termin_physics_api.hpp>

namespace termin::physics {

TERMIN_PHYSICS_API std::string_view termin_physics_version();

} // namespace termin::physics
