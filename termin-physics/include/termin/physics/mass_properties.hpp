#pragma once

#include <string>

#include <termin/colliders/collider_primitive.hpp>
#include <termin/geom/spatial_inertia3.hpp>
#include <termin/physics/termin_physics_api.hpp>

namespace termin::physics {

    // Compute the canonical spatial inertia for a collider after applying the
    // owning entity's positive decomposed scale. The collider's own local offset,
    // rotation and scale are included exactly as AttachedCollider includes them.
    //
    // Returns false and fills diagnostic for unsupported or degenerate geometry.
    TERMIN_PHYSICS_API bool try_compute_mass_properties(const colliders::ColliderPrimitive& collider,
                                                        const Vec3& entity_scale,
                                                        double mass,
                                                        SpatialInertia3& result,
                                                        std::string& diagnostic);

} // namespace termin::physics
