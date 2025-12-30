#include <nanobind/nanobind.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/string.h>

#include "termin/collision/collision.hpp"

namespace nb = nanobind;
using namespace termin;
using namespace termin::collision;
using namespace termin::colliders;

NB_MODULE(_collision_native, m) {
    m.doc() = "Native C++ collision detection module for termin";

    // Import dependencies
    nb::module_::import_("termin.geombase._geom_native");
    nb::module_::import_("termin.colliders._colliders_native");

    // ==================== ContactID ====================

    nb::class_<ContactID>(m, "ContactID")
        .def(nb::init<>())
        .def_rw("feature_a", &ContactID::feature_a)
        .def_rw("feature_b", &ContactID::feature_b)
        .def("__eq__", &ContactID::operator==)
        .def("__ne__", &ContactID::operator!=);

    // ==================== ContactPoint ====================

    nb::class_<ContactPoint>(m, "ContactPoint")
        .def(nb::init<>())
        .def_rw("position", &ContactPoint::position)
        .def_rw("local_a", &ContactPoint::local_a)
        .def_rw("local_b", &ContactPoint::local_b)
        .def_rw("penetration", &ContactPoint::penetration)
        .def_rw("id", &ContactPoint::id)
        .def_rw("normal_impulse", &ContactPoint::normal_impulse)
        .def_rw("tangent1_impulse", &ContactPoint::tangent1_impulse)
        .def_rw("tangent2_impulse", &ContactPoint::tangent2_impulse);

    // ==================== ContactManifold ====================

    nb::class_<ContactManifold>(m, "ContactManifold")
        .def(nb::init<>())
        .def_ro_static("MAX_POINTS", &ContactManifold::MAX_POINTS)
        .def_rw("collider_a", &ContactManifold::collider_a)
        .def_rw("collider_b", &ContactManifold::collider_b)
        .def_rw("normal", &ContactManifold::normal)
        .def_rw("point_count", &ContactManifold::point_count)
        .def_rw("body_a", &ContactManifold::body_a)
        .def_rw("body_b", &ContactManifold::body_b)
        .def("add_point", &ContactManifold::add_point, nb::arg("point"))
        .def("clear", &ContactManifold::clear)
        .def("same_pair", &ContactManifold::same_pair, nb::arg("other"))
        .def("pair_key", &ContactManifold::pair_key)
        .def("get_points", [](const ContactManifold& m) {
            std::vector<ContactPoint> result;
            for (int i = 0; i < m.point_count; ++i) {
                result.push_back(m.points[i]);
            }
            return result;
        });

    // ==================== RayHit (collision namespace version) ====================

    nb::class_<collision::RayHit>(m, "RayHit")
        .def(nb::init<>())
        .def_rw("collider", &collision::RayHit::collider)
        .def_rw("point", &collision::RayHit::point)
        .def_rw("normal", &collision::RayHit::normal)
        .def_rw("distance", &collision::RayHit::distance)
        .def("hit", &collision::RayHit::hit);

    // ==================== ColliderPair ====================

    nb::class_<ColliderPair>(m, "ColliderPair")
        .def(nb::init<>())
        .def_rw("a", &ColliderPair::a)
        .def_rw("b", &ColliderPair::b)
        .def("__eq__", &ColliderPair::operator==);

    // ==================== BVH ====================

    nb::class_<BVH>(m, "BVH")
        .def(nb::init<>())
        .def("insert", &BVH::insert, nb::arg("collider"), nb::arg("aabb"))
        .def("remove", &BVH::remove, nb::arg("collider"))
        .def("update", &BVH::update, nb::arg("collider"), nb::arg("new_aabb"))
        .def("query_aabb", [](const BVH& bvh, const AABB& aabb) {
            std::vector<Collider*> result;
            bvh.query_aabb(aabb, [&](Collider* c) {
                result.push_back(c);
            });
            return result;
        }, nb::arg("aabb"))
        .def("query_ray", [](const BVH& bvh, const Ray3& ray) {
            std::vector<std::tuple<Collider*, double, double>> result;
            bvh.query_ray(ray, [&](Collider* c, double t_min, double t_max) {
                result.push_back({c, t_min, t_max});
            });
            return result;
        }, nb::arg("ray"))
        .def("query_all_pairs", [](const BVH& bvh) {
            std::vector<std::pair<Collider*, Collider*>> result;
            bvh.query_all_pairs([&](Collider* a, Collider* b) {
                result.push_back({a, b});
            });
            return result;
        })
        .def("root", &BVH::root)
        .def("node_count", [](const BVH& b) { return b.node_count(); })
        .def("empty", &BVH::empty)
        .def("compute_height", [](const BVH& b) { return b.compute_height(); })
        .def("validate", &BVH::validate);

    // ==================== CollisionWorld ====================

    nb::class_<CollisionWorld>(m, "CollisionWorld")
        .def(nb::init<>())
        .def("add", &CollisionWorld::add, nb::arg("collider"),
             nb::keep_alive<1, 2>())  // Keep collider alive while in world
        .def("remove", &CollisionWorld::remove, nb::arg("collider"))
        .def("update_pose", &CollisionWorld::update_pose, nb::arg("collider"))
        .def("update_all", &CollisionWorld::update_all)
        .def("contains", &CollisionWorld::contains, nb::arg("collider"))
        .def("size", &CollisionWorld::size)
        .def("detect_contacts", &CollisionWorld::detect_contacts)
        .def("query_aabb", &CollisionWorld::query_aabb, nb::arg("aabb"))
        .def("raycast", &CollisionWorld::raycast, nb::arg("ray"))
        .def("raycast_closest", &CollisionWorld::raycast_closest, nb::arg("ray"))
        .def_prop_ro("bvh", [](const CollisionWorld& w) -> const BVH& {
            return w.bvh();
        }, nb::rv_policy::reference_internal);

    // ==================== AABB (if not already exposed) ====================

    // Check if AABB is already exposed in geombase, if not expose it here
    try {
        nb::module_::import_("termin.geombase._geom_native").attr("AABB");
    } catch (...) {
        nb::class_<AABB>(m, "AABB")
            .def(nb::init<>())
            .def(nb::init<const Vec3&, const Vec3&>(),
                 nb::arg("min_point"), nb::arg("max_point"))
            .def_rw("min_point", &AABB::min_point)
            .def_rw("max_point", &AABB::max_point)
            .def("extend", &AABB::extend, nb::arg("point"))
            .def("intersects", &AABB::intersects, nb::arg("other"))
            .def("contains", &AABB::contains, nb::arg("point"))
            .def("merge", &AABB::merge, nb::arg("other"))
            .def("center", &AABB::center)
            .def("size", &AABB::size)
            .def("half_size", &AABB::half_size)
            .def("surface_area", &AABB::surface_area)
            .def("volume", &AABB::volume);
    }
}
