#include <termin/physics_fem/components.hpp>

#include <algorithm>
#include <cstdint>
#include <functional>
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
    namespace
    {
        std::uint64_t nonzero_key(std::uint64_t key) noexcept
        {
            return key != 0 ? key : 0x9e3779b97f4a7c15ULL;
        }

        std::uint64_t combine_key(std::uint64_t seed,
                                  std::uint64_t value) noexcept
        {
            return nonzero_key(seed ^ (value + 0x9e3779b97f4a7c15ULL +
                                       (seed << 6U) + (seed >> 2U)));
        }
    } // namespace

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
            ArticulationBase,
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
            bool base = false;
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
            if (articulation->base_body_ != nullptr &&
                !articulation_bindings
                     .emplace(articulation->base_body_,
                              ArticulationBinding{
                                  .articulation = articulation->articulation_,
                                  .base = true,
                              })
                     .second)
            {
                tc::Log::error(
                    "[FEMPhysicsWorldComponent] ambiguous floating-base "
                    "contact ownership");
                return false;
            }
            for (std::size_t link_index = 0;
                 link_index < articulation->bodies_.size();
                 ++link_index)
            {
                FEMRigidBodyComponent* body = articulation->bodies_[link_index];
                if (body == nullptr ||
                    !articulation_bindings
                         .emplace(
                             body,
                             ArticulationBinding{
                                 .articulation = articulation->articulation_,
                                 .link_index = link_index,
                             })
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
                endpoint.kind = articulation_binding->second.base
                                    ? EndpointKind::ArticulationBase
                                    : EndpointKind::ArticulationLink;
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
            if (a.kind == EndpointKind::ArticulationBase)
            {
                return a.articulation == b.articulation;
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
            const bool a_articulation =
                a.kind == EndpointKind::ArticulationBase ||
                a.kind == EndpointKind::ArticulationLink;
            const bool b_articulation =
                b.kind == EndpointKind::ArticulationBase ||
                b.kind == EndpointKind::ArticulationLink;
            if (adjacent_link_collision_enabled || !a_articulation ||
                !b_articulation || a.articulation != b.articulation ||
                a.articulation == nullptr)
            {
                return false;
            }
            if (a.kind == EndpointKind::ArticulationBase ||
                b.kind == EndpointKind::ArticulationBase)
            {
                const EndpointOwner& link =
                    a.kind == EndpointKind::ArticulationLink ? a : b;
                const auto& links = a.articulation->links();
                return link.kind == EndpointKind::ArticulationLink &&
                       link.link_index < links.size() &&
                       links[link.link_index].parent_link ==
                           qopt::articulation_root_frame;
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
            case EndpointKind::ArticulationBase:
                return qopt::ContactEndpoint3D::articulation_base(
                    *endpoint.articulation,
                    endpoint.articulation->floating_base()
                        ->pose_world.inverse_transform_point(point_world));
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

        std::vector<std::pair<colliders::Collider*, const EndpointOwner*>>
            live_endpoints;
        live_endpoints.reserve(endpoint_owners.size());
        for (const auto& [collider, endpoint] : endpoint_owners)
        {
            live_endpoints.emplace_back(collider, &endpoint);
        }
        std::sort(
            live_endpoints.begin(),
            live_endpoints.end(),
            [](const auto& a, const auto& b)
            { return std::less<colliders::Collider*>{}(a.first, b.first); });
        std::vector<std::uint64_t> live_groups;
        for (std::size_t first = 0; first < live_endpoints.size(); ++first)
        {
            const EndpointOwner& a = *live_endpoints[first].second;
            for (std::size_t second = first + 1; second < live_endpoints.size();
                 ++second)
            {
                const EndpointOwner& b = *live_endpoints[second].second;
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
                collision::ContactPatch pair;
                pair.collider_a = live_endpoints[first].first;
                pair.collider_b = live_endpoints[second].first;
                live_groups.push_back(nonzero_key(pair.pair_key()));
            }
        }

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
                const std::uint64_t group_key = nonzero_key(patch.pair_key());
                std::uint32_t feature_a = point.features.feature_a;
                std::uint32_t feature_b = point.features.feature_b;
                if (std::less<colliders::Collider*>{}(patch.collider_b,
                                                      patch.collider_a))
                {
                    std::swap(feature_a, feature_b);
                }
                std::uint64_t feature_key = (std::uint64_t{feature_a} << 32U) |
                                            std::uint64_t{feature_b};
                if (feature_a ==
                        collision::ContactFeaturePair::INVALID_FEATURE &&
                    feature_b == collision::ContactFeaturePair::INVALID_FEATURE)
                {
                    feature_key = point_index;
                }
                std::uint64_t key = combine_key(group_key, feature_key);
                while (!contact_keys.insert(key).second)
                {
                    ++key;
                }
                contacts.push_back({
                    .key = key,
                    .group_key = group_key,
                    .endpoint_a = make_endpoint(a, point.point_on_a_world),
                    .endpoint_b = make_endpoint(b, point.point_on_b_world),
                    .normal_from_a_to_b_world = patch.normal_world,
                    .signed_gap = point.signed_gap,
                    .friction_coefficient = contact_friction_coefficient,
                });
            }
        }

        const qopt::Contact3DDiagnostic diagnostic = contacts_->set_contacts(
            std::move(contacts), std::move(live_groups));
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
