#pragma once

#include "bvh.hpp"
#include "contact_manifold.hpp"
#include "core/tc_entity_pool.h"
#include "core/tc_scene.h"
#include "physics/tc_collision_world.h"
#include "termin/colliders/attached_collider.hpp"
#include "termin/colliders/colliders.hpp"
#include "termin_collision/termin_collision.h"
#include <array>
#include <vector>

namespace termin {
namespace collision {

using colliders::Collider;

struct RaycastQuery {
  uint64_t layer_mask = ~uint64_t{0};
};

enum class BroadPhaseMode {
  BVH = 0,
  Naive = 1,
};

class TERMIN_COLLISION_API CollisionWorld {
private:
  BVH bvh_;
  BroadPhaseMode broad_phase_mode_ = BroadPhaseMode::BVH;
  tc_scene_handle scene_ = TC_SCENE_HANDLE_INVALID;
  std::vector<Collider *> colliders_;

public:
  CollisionWorld() = default;

  static CollisionWorld *from_scene(tc_scene_handle scene);
  void set_scene(tc_scene_handle scene);
  void add(Collider *collider);
  void remove(Collider *collider);
  void update_pose(Collider *collider);
  void update_all();
  bool contains(Collider *collider) const;
  size_t size() const;
  void set_broad_phase_mode(BroadPhaseMode mode);
  BroadPhaseMode broad_phase_mode() const;
  std::vector<ContactManifold> detect_contacts();

private:
  void test_contact_pair(Collider *a, Collider *b,
                         std::vector<ContactManifold> &manifolds);

  struct ClipVertex {
    Vec3 position;
  };
  struct ClipPlane {
    Vec3 normal;
    double distance;
    double signed_distance(const Vec3 &p) const;
  };

  static std::array<Vec3, 4> get_face_vertices(const Vec3 &center,
                                               const std::array<Vec3, 3> &axes,
                                               const Vec3 &half_size,
                                               int face_index);
  static Vec3 get_face_normal(const std::array<Vec3, 3> &axes, int face_index);
  static int find_reference_face(const std::array<Vec3, 3> &axes,
                                 const Vec3 &direction);
  static int find_incident_face(const std::array<Vec3, 3> &axes,
                                const Vec3 &direction);
  static std::array<ClipPlane, 4>
  build_clip_planes(const std::array<Vec3, 4> &face_verts,
                    const Vec3 &face_normal);
  static Vec3 intersect_edge_plane(const Vec3 &a, const Vec3 &b,
                                   const ClipPlane &plane);
  static std::vector<Vec3>
  sutherland_hodgman_clip(const std::array<Vec3, 4> &subject,
                          const std::array<ClipPlane, 4> &clip_planes);
  void generate_box_box_contacts(Collider *a, Collider *b,
                                 const ColliderHit &hit,
                                 ContactManifold &manifold);

public:
  std::vector<Collider *> query_aabb(const AABB &aabb) const;
  std::vector<RayHit> raycast(const Ray3 &ray) const;
  std::vector<RayHit> raycast(const Ray3 &ray, const RaycastQuery &query) const;
  RayHit raycast_closest(const Ray3 &ray) const;
  RayHit raycast_closest(const Ray3 &ray, const RaycastQuery &query) const;
  const BVH &bvh() const;
  const std::vector<Collider *> &colliders() const;

private:
  bool accepts_raycast_collider(Collider *collider,
                                const RaycastQuery &query) const;
};

} // namespace collision
} // namespace termin
