#include <termin/physics_fem/components.hpp>

#include <algorithm>
#include <cstdint>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include <components/collider_component.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/collision/collision_world.hpp>
#include <termin/tc_scene.hpp>

namespace termin
{
    bool FEMPhysicsWorldComponent::refresh_contacts()
    {
        if (contacts_ == nullptr)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] contact contribution is missing");
            return false;
        }

        Entity owner_entity = entity();
        const TcSceneRef scene = owner_entity.scene();
        collision::CollisionWorld* collision_world =
            collision::CollisionWorld::from_scene(scene.handle());
        if (collision_world == nullptr)
        {
            return contacts_->set_contacts({}) ==
                   qopt::Contact3DDiagnostic::None;
        }

        enum class EndpointKind
        {
            Ignored,
            Static,
            RigidBody,
            ArticulationLink,
        };
        struct EndpointOwner
        {
            EndpointKind kind = EndpointKind::Ignored;
            Entity entity;
            qopt::RigidBody3DContribution* body = nullptr;
            qopt::Articulation3DContribution* articulation = nullptr;
            std::size_t link_index = 0;
        };
        struct ArticulationBinding
        {
            qopt::Articulation3DContribution* articulation = nullptr;
            std::size_t link_index = 0;
        };

        std::unordered_map<FEMRigidBodyComponent*, ArticulationBinding>
            articulation_bindings;
        for (FEMArticulationComponent* articulation : articulations_)
        {
            if (articulation == nullptr ||
                articulation->articulation_ == nullptr)
            {
                continue;
            }
            for (std::size_t link_index = 0;
                 link_index < articulation->bodies_.size();
                 ++link_index)
            {
                FEMRigidBodyComponent* body = articulation->bodies_[link_index];
                if (body == nullptr ||
                    !articulation_bindings
                         .emplace(body,
                                  ArticulationBinding{
                                      articulation->articulation_, link_index})
                         .second)
                {
                    tc::Log::error(
                        "[FEMPhysicsWorldComponent] ambiguous articulation "
                        "contact ownership");
                    return false;
                }
            }
        }

        const auto warn_once = [this](const void* collider,
                                      const char* message,
                                      const char* entity_name)
        {
            if (std::find(warned_contact_colliders_.begin(),
                          warned_contact_colliders_.end(),
                          collider) != warned_contact_colliders_.end())
            {
                return;
            }
            warned_contact_colliders_.push_back(collider);
            tc::Log::error("[FEMPhysicsWorldComponent] %s for collider on '%s'",
                           message,
                           entity_name != nullptr ? entity_name : "<invalid>");
        };

        std::unordered_map<colliders::Collider*, EndpointOwner> endpoint_owners;
        for (Entity candidate : scene.get_all_entities())
        {
            ColliderComponent* collider_component =
                candidate.get_component<ColliderComponent>();
            if (collider_component == nullptr ||
                collider_component->attached_collider() == nullptr)
            {
                continue;
            }

            colliders::Collider* collider =
                collider_component->attached_collider();
            EndpointOwner endpoint;
            endpoint.entity = candidate;
            const std::uint64_t layer = candidate.layer();
            const bool selected_layer =
                layer < 64 &&
                (collision_layer_mask & (std::uint64_t{1} << layer)) != 0;
            if (!candidate.enabled() || !collider_component->enabled() ||
                !selected_layer)
            {
                endpoint_owners.emplace(collider, endpoint);
                continue;
            }

            FEMRigidBodyComponent* body =
                candidate.get_component<FEMRigidBodyComponent>();
            if (body == nullptr || !body->enabled())
            {
                endpoint.kind = EndpointKind::Static;
                endpoint_owners.emplace(collider, endpoint);
                continue;
            }
            if (body->world_ != this)
            {
                warn_once(collider,
                          "enabled FEM body is not registered in this world",
                          candidate.name());
                endpoint_owners.emplace(collider, endpoint);
                continue;
            }

            const auto articulation_binding = articulation_bindings.find(body);
            const bool owns_maximal_body = body->body_ != nullptr;
            const bool owns_articulation_link =
                articulation_binding != articulation_bindings.end();
            if (owns_maximal_body == owns_articulation_link)
            {
                warn_once(collider,
                          "dynamic collider has ambiguous or missing endpoint "
                          "ownership",
                          candidate.name());
                endpoint_owners.emplace(collider, endpoint);
                continue;
            }
            if (owns_maximal_body)
            {
                endpoint.kind = EndpointKind::RigidBody;
                endpoint.body = body->body_;
            }
            else
            {
                endpoint.kind = EndpointKind::ArticulationLink;
                endpoint.articulation =
                    articulation_binding->second.articulation;
                endpoint.link_index = articulation_binding->second.link_index;
            }
            endpoint_owners.emplace(collider, endpoint);
        }

        collision_world->update_all();
        const std::vector<collision::ContactPatch> patches =
            collision_world->detect_contacts();
        std::vector<qopt::Contact3D> contacts;
        std::unordered_set<std::uint64_t> contact_keys;

        const auto same_dynamic_endpoint =
            [](const EndpointOwner& a, const EndpointOwner& b)
        {
            if (a.kind != b.kind)
            {
                return false;
            }
            if (a.kind == EndpointKind::RigidBody)
            {
                return a.body == b.body;
            }
            if (a.kind == EndpointKind::ArticulationLink)
            {
                return a.articulation == b.articulation &&
                       a.link_index == b.link_index;
            }
            return false;
        };
        const auto adjacent_articulation_links =
            [this](const EndpointOwner& a, const EndpointOwner& b)
        {
            if (adjacent_link_collision_enabled ||
                a.kind != EndpointKind::ArticulationLink ||
                b.kind != EndpointKind::ArticulationLink ||
                a.articulation != b.articulation || a.articulation == nullptr)
            {
                return false;
            }
            const auto& links = a.articulation->links();
            if (a.link_index >= links.size() || b.link_index >= links.size())
            {
                return false;
            }
            return links[a.link_index].parent_link == b.link_index ||
                   links[b.link_index].parent_link == a.link_index;
        };
        const auto connected_maximal_bodies =
            [this](const EndpointOwner& a, const EndpointOwner& b)
        {
            if (adjacent_link_collision_enabled ||
                a.kind != EndpointKind::RigidBody ||
                b.kind != EndpointKind::RigidBody)
            {
                return false;
            }
            for (const FEMRevoluteJointComponent* joint : revolute_joints_)
            {
                if (joint != nullptr &&
                    ((joint->body_a_ == a.body && joint->body_b_ == b.body) ||
                     (joint->body_a_ == b.body && joint->body_b_ == a.body)))
                {
                    return true;
                }
            }
            return false;
        };
        const auto make_endpoint =
            [](const EndpointOwner& endpoint, const Vec3& point_world)
        {
            switch (endpoint.kind)
            {
            case EndpointKind::Static:
                return qopt::ContactEndpoint3D::static_world(point_world);
            case EndpointKind::RigidBody:
                return qopt::ContactEndpoint3D::rigid_body(
                    *endpoint.body,
                    endpoint.body->state().pose.inverse_transform_point(
                        point_world));
            case EndpointKind::ArticulationLink:
                return qopt::ContactEndpoint3D::articulation_link(
                    *endpoint.articulation,
                    endpoint.link_index,
                    endpoint.articulation
                        ->link_poses_world()[endpoint.link_index]
                        .inverse_transform_point(point_world));
            case EndpointKind::Ignored:
                return qopt::ContactEndpoint3D{};
            }
            return qopt::ContactEndpoint3D{};
        };

        for (const collision::ContactPatch& patch : patches)
        {
            const auto owner_a = endpoint_owners.find(patch.collider_a);
            const auto owner_b = endpoint_owners.find(patch.collider_b);
            if (owner_a == endpoint_owners.end() ||
                owner_b == endpoint_owners.end())
            {
                const void* unmapped = owner_a == endpoint_owners.end()
                                           ? patch.collider_a
                                           : patch.collider_b;
                warn_once(unmapped,
                          "CollisionWorld returned an unmapped collider",
                          "<no ColliderComponent>");
                continue;
            }
            const EndpointOwner& a = owner_a->second;
            const EndpointOwner& b = owner_b->second;
            if (a.kind == EndpointKind::Ignored ||
                b.kind == EndpointKind::Ignored ||
                (a.kind == EndpointKind::Static &&
                 b.kind == EndpointKind::Static) ||
                same_dynamic_endpoint(a, b) ||
                adjacent_articulation_links(a, b) ||
                connected_maximal_bodies(a, b))
            {
                continue;
            }

            for (std::size_t point_index = 0; point_index < patch.points.size();
                 ++point_index)
            {
                const collision::ContactCandidate& point =
                    patch.points[point_index];
                std::uint64_t key =
                    patch.pair_key() ^
                    (0x9e3779b97f4a7c15ULL + point_index +
                     (patch.pair_key() << 6U) + (patch.pair_key() >> 2U));
                while (!contact_keys.insert(key).second)
                {
                    ++key;
                }
                contacts.push_back({
                    .key = key,
                    .endpoint_a = make_endpoint(a, point.point_on_a_world),
                    .endpoint_b = make_endpoint(b, point.point_on_b_world),
                    .normal_from_a_to_b_world = patch.normal_world,
                    .signed_gap = point.signed_gap,
                });
            }
        }

        const qopt::Contact3DDiagnostic diagnostic =
            contacts_->set_contacts(std::move(contacts));
        if (diagnostic != qopt::Contact3DDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] scene contact conversion failed: "
                "%s",
                qopt::contact3d_diagnostic_name(diagnostic).data());
            return false;
        }
        return true;
    }

} // namespace termin
