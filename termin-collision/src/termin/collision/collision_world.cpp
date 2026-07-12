#include "termin/collision/collision_world.hpp"

#include <algorithm>
#include <limits>

namespace termin::collision {

CollisionWorld *CollisionWorld::from_scene(tc_scene_handle scene) {
    return reinterpret_cast<CollisionWorld *>(tc_collision_world_get_scene(scene));
}

void CollisionWorld::set_scene(tc_scene_handle scene) { scene_ = scene; }

void CollisionWorld::add(Collider *collider) {
    if (!collider || contains(collider))
        return;
    colliders_.push_back(collider);
    bvh_.insert(collider, collider->aabb());
}

void CollisionWorld::remove(Collider *collider) {
    if (!collider)
        return;
    auto it = std::find(colliders_.begin(), colliders_.end(), collider);
    if (it == colliders_.end())
        return;
    bvh_.remove(collider);
    colliders_.erase(it);
}

void CollisionWorld::update_pose(Collider *collider) {
    if (!collider || !contains(collider))
        return;
    bvh_.update(collider, collider->aabb());
}

void CollisionWorld::update_all() {
    for (auto *collider : colliders_)
        bvh_.update(collider, collider->aabb());
}

bool CollisionWorld::contains(Collider *collider) const {
    return std::find(colliders_.begin(), colliders_.end(), collider) != colliders_.end();
}

size_t CollisionWorld::size() const { return colliders_.size(); }

void CollisionWorld::set_broad_phase_mode(BroadPhaseMode mode) { broad_phase_mode_ = mode; }

BroadPhaseMode CollisionWorld::broad_phase_mode() const { return broad_phase_mode_; }

std::vector<ContactManifold> CollisionWorld::detect_contacts() {
    std::vector<ContactManifold> manifolds;
    if (broad_phase_mode_ == BroadPhaseMode::Naive) {
        for (size_t i = 0; i < colliders_.size(); ++i) {
            for (size_t j = i + 1; j < colliders_.size(); ++j) {
                Collider *a = colliders_[i];
                Collider *b = colliders_[j];
                if (a->aabb().intersects(b->aabb()))
                    test_contact_pair(a, b, manifolds);
            }
        }
    } else {
        bvh_.query_all_pairs([&](Collider *a, Collider *b) { test_contact_pair(a, b, manifolds); });
    }
    return manifolds;
}

void CollisionWorld::test_contact_pair(Collider *a, Collider *b,
                                       std::vector<ContactManifold> &manifolds) {
    ColliderHit hit = a->closest_to_collider(*b);
    if (!hit.colliding())
        return;
    ContactManifold manifold;
    manifold.collider_a = a;
    manifold.collider_b = b;
    manifold.normal = hit.normal;
    if (a->type() == colliders::ColliderType::Box && b->type() == colliders::ColliderType::Box) {
        generate_box_box_contacts(a, b, hit, manifold);
    } else {
        ContactPoint point;
        point.position = (hit.point_on_a + hit.point_on_b) * 0.5;
        point.local_a = hit.point_on_a;
        point.local_b = hit.point_on_b;
        point.penetration = hit.distance;
        manifold.add_point(point);
    }
    manifolds.push_back(manifold);
}

double CollisionWorld::ClipPlane::signed_distance(const Vec3 &p) const {
    return normal.dot(p) + distance;
}

std::array<Vec3, 4> CollisionWorld::get_face_vertices(const Vec3 &center,
                                                      const std::array<Vec3, 3> &axes,
                                                      const Vec3 &half_size, int face_index) {
    std::array<Vec3, 4> verts;
    double hx = half_size.x, hy = half_size.y, hz = half_size.z;
    Vec3 ax = axes[0], ay = axes[1], az = axes[2];
    switch (face_index) {
    case 0:
        verts[0] = center + ax * hx - ay * hy - az * hz;
        verts[1] = center + ax * hx + ay * hy - az * hz;
        verts[2] = center + ax * hx + ay * hy + az * hz;
        verts[3] = center + ax * hx - ay * hy + az * hz;
        break;
    case 1:
        verts[0] = center - ax * hx + ay * hy - az * hz;
        verts[1] = center - ax * hx - ay * hy - az * hz;
        verts[2] = center - ax * hx - ay * hy + az * hz;
        verts[3] = center - ax * hx + ay * hy + az * hz;
        break;
    case 2:
        verts[0] = center + ax * hx + ay * hy - az * hz;
        verts[1] = center - ax * hx + ay * hy - az * hz;
        verts[2] = center - ax * hx + ay * hy + az * hz;
        verts[3] = center + ax * hx + ay * hy + az * hz;
        break;
    case 3:
        verts[0] = center - ax * hx - ay * hy - az * hz;
        verts[1] = center + ax * hx - ay * hy - az * hz;
        verts[2] = center + ax * hx - ay * hy + az * hz;
        verts[3] = center - ax * hx - ay * hy + az * hz;
        break;
    case 4:
        verts[0] = center - ax * hx - ay * hy + az * hz;
        verts[1] = center + ax * hx - ay * hy + az * hz;
        verts[2] = center + ax * hx + ay * hy + az * hz;
        verts[3] = center - ax * hx + ay * hy + az * hz;
        break;
    case 5:
        verts[0] = center - ax * hx + ay * hy - az * hz;
        verts[1] = center + ax * hx + ay * hy - az * hz;
        verts[2] = center + ax * hx - ay * hy - az * hz;
        verts[3] = center - ax * hx - ay * hy - az * hz;
        break;
    }
    return verts;
}

Vec3 CollisionWorld::get_face_normal(const std::array<Vec3, 3> &axes, int face_index) {
    switch (face_index) {
    case 0:
        return axes[0];
    case 1:
        return axes[0] * (-1.0);
    case 2:
        return axes[1];
    case 3:
        return axes[1] * (-1.0);
    case 4:
        return axes[2];
    case 5:
        return axes[2] * (-1.0);
    }
    return Vec3(0, 0, 1);
}

int CollisionWorld::find_reference_face(const std::array<Vec3, 3> &axes, const Vec3 &direction) {
    int best_face = 0;
    double best_dot = -std::numeric_limits<double>::infinity();
    for (int i = 0; i < 6; ++i) {
        double d = get_face_normal(axes, i).dot(direction);
        if (d > best_dot) {
            best_dot = d;
            best_face = i;
        }
    }
    return best_face;
}

int CollisionWorld::find_incident_face(const std::array<Vec3, 3> &axes, const Vec3 &direction) {
    int best_face = 0;
    double best_dot = std::numeric_limits<double>::infinity();
    for (int i = 0; i < 6; ++i) {
        double d = get_face_normal(axes, i).dot(direction);
        if (d < best_dot) {
            best_dot = d;
            best_face = i;
        }
    }
    return best_face;
}

std::array<CollisionWorld::ClipPlane, 4>
CollisionWorld::build_clip_planes(const std::array<Vec3, 4> &face_verts, const Vec3 &face_normal) {
    std::array<ClipPlane, 4> planes;
    for (int i = 0; i < 4; ++i) {
        Vec3 v0 = face_verts[i];
        Vec3 edge = face_verts[(i + 1) % 4] - v0;
        Vec3 plane_normal = edge.cross(face_normal).normalized();
        planes[i].normal = plane_normal;
        planes[i].distance = -plane_normal.dot(v0);
    }
    return planes;
}

Vec3 CollisionWorld::intersect_edge_plane(const Vec3 &a, const Vec3 &b, const ClipPlane &plane) {
    double da = plane.signed_distance(a);
    double db = plane.signed_distance(b);
    return a + (b - a) * (da / (da - db));
}

std::vector<Vec3>
CollisionWorld::sutherland_hodgman_clip(const std::array<Vec3, 4> &subject,
                                        const std::array<ClipPlane, 4> &clip_planes) {
    std::vector<Vec3> output(subject.begin(), subject.end());
    for (const auto &plane : clip_planes) {
        if (output.empty())
            break;
        std::vector<Vec3> input = std::move(output);
        output.clear();
        for (size_t i = 0; i < input.size(); ++i) {
            const Vec3 &a = input[i];
            const Vec3 &b = input[(i + 1) % input.size()];
            double da = plane.signed_distance(a), db = plane.signed_distance(b);
            bool a_inside = da <= 0, b_inside = db <= 0;
            if (a_inside && b_inside)
                output.push_back(b);
            else if (a_inside && !b_inside)
                output.push_back(intersect_edge_plane(a, b, plane));
            else if (!a_inside && b_inside) {
                output.push_back(intersect_edge_plane(a, b, plane));
                output.push_back(b);
            }
        }
    }
    return output;
}

void CollisionWorld::generate_box_box_contacts(Collider *a, Collider *b, const ColliderHit &hit,
                                               ContactManifold &manifold) {
    const colliders::BoxCollider *box_a = nullptr;
    const colliders::BoxCollider *box_b = nullptr;
    GeneralPose3 transform_a, transform_b;
    if (auto *attached_a = dynamic_cast<colliders::AttachedCollider *>(a)) {
        box_a = dynamic_cast<const colliders::BoxCollider *>(attached_a->collider());
        transform_a = attached_a->world_transform();
    } else {
        box_a = dynamic_cast<const colliders::BoxCollider *>(a);
        if (box_a)
            transform_a = box_a->transform;
    }
    if (auto *attached_b = dynamic_cast<colliders::AttachedCollider *>(b)) {
        box_b = dynamic_cast<const colliders::BoxCollider *>(attached_b->collider());
        transform_b = attached_b->world_transform();
    } else {
        box_b = dynamic_cast<const colliders::BoxCollider *>(b);
        if (box_b)
            transform_b = box_b->transform;
    }
    auto add_fallback = [&]() {
        ContactPoint point;
        point.position = (hit.point_on_a + hit.point_on_b) * 0.5;
        point.local_a = hit.point_on_a;
        point.local_b = hit.point_on_b;
        point.penetration = hit.distance;
        manifold.add_point(point);
    };
    if (!box_a || !box_b) {
        add_fallback();
        return;
    }
    colliders::BoxCollider world_box_a(box_a->half_size, transform_a);
    colliders::BoxCollider world_box_b(box_b->half_size, transform_b);
    Vec3 center_a = world_box_a.center(), center_b = world_box_b.center();
    auto axes_a = world_box_a.get_axes_world(), axes_b = world_box_b.get_axes_world();
    Vec3 half_a = world_box_a.effective_half_size(), half_b = world_box_b.effective_half_size();
    Vec3 normal = hit.normal;
    int ref_face_idx = find_reference_face(axes_a, normal);
    Vec3 ref_normal = get_face_normal(axes_a, ref_face_idx);
    int inc_face_idx = find_incident_face(axes_b, ref_normal);
    auto ref_verts = get_face_vertices(center_a, axes_a, half_a, ref_face_idx);
    auto inc_verts = get_face_vertices(center_b, axes_b, half_b, inc_face_idx);
    auto clip_planes = build_clip_planes(ref_verts, ref_normal);
    auto clipped = sutherland_hodgman_clip(inc_verts, clip_planes);
    ClipPlane ref_plane{ref_normal, -ref_normal.dot(ref_verts[0])};
    int points_added = 0;
    for (const auto &p : clipped) {
        double depth = ref_plane.signed_distance(p);
        if (depth < 0) {
            ContactPoint cp;
            cp.position = p;
            cp.local_b = p;
            cp.local_a = p - ref_normal * depth;
            cp.penetration = depth;
            if (manifold.add_point(cp))
                ++points_added;
            if (points_added >= ContactManifold::MAX_POINTS)
                break;
        }
    }
    if (points_added == 0)
        add_fallback();
}

std::vector<Collider *> CollisionWorld::query_aabb(const AABB &aabb) const {
    std::vector<Collider *> result;
    bvh_.query_aabb(aabb, [&](Collider *c) { result.push_back(c); });
    return result;
}

std::vector<RayHit> CollisionWorld::raycast(const Ray3 &ray) const {
    return raycast(ray, RaycastQuery{});
}

std::vector<RayHit> CollisionWorld::raycast(const Ray3 &ray, const RaycastQuery &query) const {
    std::vector<RayHit> hits;
    bvh_.query_ray(ray, [&](Collider *collider, double, double) {
        if (!accepts_raycast_collider(collider, query))
            return;
        colliders::RayHit collider_hit = collider->closest_to_ray(ray);
        if (!collider_hit.hit())
            return;
        RayHit hit;
        hit.collider = collider;
        hit.point = collider_hit.point_on_ray;
        Vec3 center = collider->center();
        hit.normal = (hit.point - center).normalized();
        hit.distance = (hit.point - ray.origin).norm();
        hits.push_back(hit);
    });
    std::sort(hits.begin(), hits.end(),
              [](const RayHit &a, const RayHit &b) { return a.distance < b.distance; });
    return hits;
}

RayHit CollisionWorld::raycast_closest(const Ray3 &ray) const {
    return raycast_closest(ray, RaycastQuery{});
}

RayHit CollisionWorld::raycast_closest(const Ray3 &ray, const RaycastQuery &query) const {
    auto hits = raycast(ray, query);
    return hits.empty() ? RayHit{} : hits[0];
}

const BVH &CollisionWorld::bvh() const { return bvh_; }
const std::vector<Collider *> &CollisionWorld::colliders() const { return colliders_; }

bool CollisionWorld::accepts_raycast_collider(Collider *collider, const RaycastQuery &query) const {
    if (query.layer_mask == ~uint64_t{0} || !tc_scene_handle_valid(scene_))
        return true;
    auto *attached = dynamic_cast<colliders::AttachedCollider *>(collider);
    if (!attached)
        return true;
    tc_entity_id entity_id = attached->owner_entity_id();
    if (!tc_entity_id_valid(entity_id))
        return true;
    tc_entity_pool *pool = tc_scene_entity_pool(scene_);
    if (!pool)
        return true;
    uint64_t layer = tc_entity_pool_layer(pool, entity_id);
    if (layer >= 64)
        return false;
    return (query.layer_mask & (uint64_t{1} << layer)) != 0;
}

} // namespace termin::collision
