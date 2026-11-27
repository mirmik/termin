// Benchmark-only MuJoCo 3.15 sphere/box narrow phase using the Termin SDK.
// The Python driver owns the callback table in its single simulation process.
#include <mujoco/mujoco.h>
#include <termin/colliders/colliders.hpp>

#include <cstdint>

namespace {
    mjfCollision previous = nullptr;
    std::uint64_t queries = 0;
    std::uint64_t returned = 0;

    termin::Vec3 vector(const mjtNum* v) {
        return {v[0], v[1], v[2]};
    }

    int sphere_box(const mjModel* m, mjData* d, mjPreContact* c, int sphere, int box, mjtNum margin) {
        ++queries;
        termin::GeneralPose3 sphere_pose;
        sphere_pose.lin = vector(d->geom_xpos + 3 * sphere);
        termin::GeneralPose3 box_pose;
        box_pose.lin = vector(d->geom_xpos + 3 * box);
        mjtNum quat[4];
        mju_mat2Quat(quat, d->geom_xmat + 9 * box);
        box_pose.ang = {quat[1], quat[2], quat[3], quat[0]};
        const termin::colliders::SphereCollider foot(m->geom_size[3 * sphere], sphere_pose);
        const termin::colliders::BoxCollider surface(vector(m->geom_size + 3 * box), box_pose);
        const auto hit = foot.closest_to_collider(surface);
        if (hit.distance > margin) {
            return 0;
        }
        const auto midpoint = (hit.point_on_a + hit.point_on_b) * 0.5;
        *c = {};
        c->dist = hit.distance;
        for (int i = 0; i < 3; ++i) {
            c->pos[i] = midpoint[i];
            c->normal[i] = hit.normal[i];
        }
        ++returned;
        return 1;
    }
} // namespace

extern "C" int spider_install_termin_geometry() {
    if (mj_version() != mjVERSION_HEADER || previous) {
        return 0;
    }
    auto& slot = mjCOLLISIONFUNC[mjGEOM_SPHERE][mjGEOM_BOX];
    if (!slot) {
        return 0;
    }
    previous = slot;
    queries = returned = 0;
    slot = sphere_box;
    return 1;
}

extern "C" void spider_restore_geometry(std::uint64_t* calls, std::uint64_t* hits) {
    mjCOLLISIONFUNC[mjGEOM_SPHERE][mjGEOM_BOX] = previous;
    previous = nullptr;
    *calls = queries;
    *hits = returned;
}
