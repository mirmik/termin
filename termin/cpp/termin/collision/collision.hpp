#pragma once

/**
 * @file collision.hpp
 * @brief Unified collision detection system.
 *
 * This module provides:
 * - BVH for broad-phase collision detection
 * - CollisionWorld for managing colliders and detecting contacts
 * - ContactManifold for unified contact representation
 *
 * Usage:
 *   CollisionWorld world;
 *   world.add(collider1);
 *   world.add(collider2);
 *
 *   // After moving objects:
 *   world.update_pose(collider1);
 *
 *   // Detect all contacts:
 *   auto manifolds = world.detect_contacts();
 *
 *   // Raycast:
 *   auto hit = world.raycast_closest(ray);
 */

#include "bvh.hpp"
#include "contact_manifold.hpp"
#include "collision_world.hpp"
