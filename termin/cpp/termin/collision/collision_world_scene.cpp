#include "collision_world.hpp"
#include "physics/tc_collision_world.h"
#include <termin/entity/component.hpp>
#include "termin/colliders/collider_component.hpp"
#include <termin/geom/ray3.hpp>
#include <termin/tc_scene.hpp>
#include "termin/tc_scene_render_ext.hpp"
#include <limits>

namespace termin::collision {

CollisionWorld* CollisionWorld::from_scene(tc_scene_handle scene) {
    return reinterpret_cast<CollisionWorld*>(tc_collision_world_get_scene(scene));
}

SceneRaycastHit CollisionWorld::raycast_scene(tc_scene_handle scene, const Ray3& ray) {
    struct Context {
        SceneRaycastHit* result;
        double best_dist;
        const Ray3* ray;
        Vec3 origin;
    };

    SceneRaycastHit result;
    Context ctx{&result, std::numeric_limits<double>::infinity(), &ray, ray.origin};

    tc_scene_foreach_component_of_type(scene, "ColliderComponent",
        [](tc_component* c, void* user_data) -> bool {
            auto* ctx = static_cast<Context*>(user_data);

            CxxComponent* cxx = CxxComponent::from_tc(c);
            if (!cxx) return true;

            auto* collider_comp = dynamic_cast<ColliderComponent*>(cxx);
            if (!collider_comp) return true;

            auto* attached = collider_comp->attached_collider();
            if (!attached) return true;

            colliders::RayHit hit = attached->closest_to_ray(*ctx->ray);
            if (!hit.hit()) return true;

            Vec3 p_ray = hit.point_on_ray;
            double d_ray = (p_ray - ctx->origin).norm();

            if (d_ray < ctx->best_dist) {
                ctx->best_dist = d_ray;
                ctx->result->entity = cxx->entity().handle();
                ctx->result->component = collider_comp;
                ctx->result->point_on_ray[0] = p_ray.x;
                ctx->result->point_on_ray[1] = p_ray.y;
                ctx->result->point_on_ray[2] = p_ray.z;
                ctx->result->point_on_collider[0] = hit.point_on_collider.x;
                ctx->result->point_on_collider[1] = hit.point_on_collider.y;
                ctx->result->point_on_collider[2] = hit.point_on_collider.z;
                ctx->result->distance = hit.distance;
            }
            return true;
        },
        &ctx
    );

    return result;
}

SceneRaycastHit CollisionWorld::closest_to_ray_scene(tc_scene_handle scene, const Ray3& ray) {
    struct Context {
        SceneRaycastHit* result;
        double best_dist;
        const Ray3* ray;
    };

    SceneRaycastHit result;
    Context ctx{&result, std::numeric_limits<double>::infinity(), &ray};

    tc_scene_foreach_component_of_type(scene, "ColliderComponent",
        [](tc_component* c, void* user_data) -> bool {
            auto* ctx = static_cast<Context*>(user_data);

            CxxComponent* cxx = CxxComponent::from_tc(c);
            if (!cxx) return true;

            auto* collider_comp = dynamic_cast<ColliderComponent*>(cxx);
            if (!collider_comp) return true;

            auto* attached = collider_comp->attached_collider();
            if (!attached) return true;

            colliders::RayHit hit = attached->closest_to_ray(*ctx->ray);

            if (hit.distance < ctx->best_dist) {
                ctx->best_dist = hit.distance;
                ctx->result->entity = cxx->entity().handle();
                ctx->result->component = collider_comp;
                ctx->result->point_on_ray[0] = hit.point_on_ray.x;
                ctx->result->point_on_ray[1] = hit.point_on_ray.y;
                ctx->result->point_on_ray[2] = hit.point_on_ray.z;
                ctx->result->point_on_collider[0] = hit.point_on_collider.x;
                ctx->result->point_on_collider[1] = hit.point_on_collider.y;
                ctx->result->point_on_collider[2] = hit.point_on_collider.z;
                ctx->result->distance = hit.distance;
            }
            return true;
        },
        &ctx
    );

    return result;
}

} // namespace termin::collision
