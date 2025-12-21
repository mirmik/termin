#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>

#include "termin/collision/collision.hpp"

namespace py = pybind11;
using namespace termin;
using namespace termin::geom;
using namespace termin::collision;
using namespace termin::colliders;

PYBIND11_MODULE(_collision_native, m) {
    m.doc() = "Native C++ collision detection module for termin";

    // Import dependencies
    py::module_::import("termin.geombase._geom_native");
    py::module_::import("termin.colliders._colliders_native");

    // ==================== ContactID ====================

    py::class_<ContactID>(m, "ContactID")
        .def(py::init<>())
        .def_readwrite("feature_a", &ContactID::feature_a)
        .def_readwrite("feature_b", &ContactID::feature_b)
        .def("__eq__", &ContactID::operator==)
        .def("__ne__", &ContactID::operator!=);

    // ==================== ContactPoint ====================

    py::class_<ContactPoint>(m, "ContactPoint")
        .def(py::init<>())
        .def_readwrite("position", &ContactPoint::position)
        .def_readwrite("local_a", &ContactPoint::local_a)
        .def_readwrite("local_b", &ContactPoint::local_b)
        .def_readwrite("penetration", &ContactPoint::penetration)
        .def_readwrite("id", &ContactPoint::id)
        .def_readwrite("normal_impulse", &ContactPoint::normal_impulse)
        .def_readwrite("tangent1_impulse", &ContactPoint::tangent1_impulse)
        .def_readwrite("tangent2_impulse", &ContactPoint::tangent2_impulse);

    // ==================== ContactManifold ====================

    py::class_<ContactManifold>(m, "ContactManifold")
        .def(py::init<>())
        .def_readonly_static("MAX_POINTS", &ContactManifold::MAX_POINTS)
        .def_readwrite("collider_a", &ContactManifold::collider_a)
        .def_readwrite("collider_b", &ContactManifold::collider_b)
        .def_readwrite("normal", &ContactManifold::normal)
        .def_readwrite("point_count", &ContactManifold::point_count)
        .def_readwrite("body_a", &ContactManifold::body_a)
        .def_readwrite("body_b", &ContactManifold::body_b)
        .def("add_point", &ContactManifold::add_point, py::arg("point"))
        .def("clear", &ContactManifold::clear)
        .def("same_pair", &ContactManifold::same_pair, py::arg("other"))
        .def("pair_key", &ContactManifold::pair_key)
        .def("get_points", [](const ContactManifold& m) {
            std::vector<ContactPoint> result;
            for (int i = 0; i < m.point_count; ++i) {
                result.push_back(m.points[i]);
            }
            return result;
        });

    // ==================== RayHit (collision namespace version) ====================

    py::class_<collision::RayHit>(m, "RayHit")
        .def(py::init<>())
        .def_readwrite("collider", &collision::RayHit::collider)
        .def_readwrite("point", &collision::RayHit::point)
        .def_readwrite("normal", &collision::RayHit::normal)
        .def_readwrite("distance", &collision::RayHit::distance)
        .def("hit", &collision::RayHit::hit);

    // ==================== ColliderPair ====================

    py::class_<ColliderPair>(m, "ColliderPair")
        .def(py::init<>())
        .def_readwrite("a", &ColliderPair::a)
        .def_readwrite("b", &ColliderPair::b)
        .def("__eq__", &ColliderPair::operator==);

    // ==================== BVH ====================

    py::class_<BVH>(m, "BVH")
        .def(py::init<>())
        .def("insert", &BVH::insert, py::arg("collider"), py::arg("aabb"))
        .def("remove", &BVH::remove, py::arg("collider"))
        .def("update", &BVH::update, py::arg("collider"), py::arg("new_aabb"))
        .def("query_aabb", [](const BVH& bvh, const AABB& aabb) {
            std::vector<Collider*> result;
            bvh.query_aabb(aabb, [&](Collider* c) {
                result.push_back(c);
            });
            return result;
        }, py::arg("aabb"))
        .def("query_ray", [](const BVH& bvh, const Ray3& ray) {
            std::vector<std::tuple<Collider*, double, double>> result;
            bvh.query_ray(ray, [&](Collider* c, double t_min, double t_max) {
                result.push_back({c, t_min, t_max});
            });
            return result;
        }, py::arg("ray"))
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

    py::class_<CollisionWorld>(m, "CollisionWorld")
        .def(py::init<>())
        .def("add", &CollisionWorld::add, py::arg("collider"),
             py::keep_alive<1, 2>())  // Keep collider alive while in world
        .def("remove", &CollisionWorld::remove, py::arg("collider"))
        .def("update_pose", &CollisionWorld::update_pose, py::arg("collider"))
        .def("update_all", &CollisionWorld::update_all)
        .def("contains", &CollisionWorld::contains, py::arg("collider"))
        .def("size", &CollisionWorld::size)
        .def("detect_contacts", &CollisionWorld::detect_contacts)
        .def("query_aabb", &CollisionWorld::query_aabb, py::arg("aabb"))
        .def("raycast", &CollisionWorld::raycast, py::arg("ray"))
        .def("raycast_closest", &CollisionWorld::raycast_closest, py::arg("ray"))
        .def_property_readonly("bvh", [](const CollisionWorld& w) -> const BVH& {
            return w.bvh();
        }, py::return_value_policy::reference_internal);

    // ==================== AABB (if not already exposed) ====================

    // Check if AABB is already exposed in geombase, if not expose it here
    try {
        py::module_::import("termin.geombase._geom_native").attr("AABB");
    } catch (...) {
        py::class_<AABB>(m, "AABB")
            .def(py::init<>())
            .def(py::init<const Vec3&, const Vec3&>(),
                 py::arg("min_point"), py::arg("max_point"))
            .def_readwrite("min_point", &AABB::min_point)
            .def_readwrite("max_point", &AABB::max_point)
            .def("extend", &AABB::extend, py::arg("point"))
            .def("intersects", &AABB::intersects, py::arg("other"))
            .def("contains", &AABB::contains, py::arg("point"))
            .def("merge", &AABB::merge, py::arg("other"))
            .def("center", &AABB::center)
            .def("size", &AABB::size)
            .def("half_size", &AABB::half_size)
            .def("surface_area", &AABB::surface_area)
            .def("volume", &AABB::volume);
    }
}
