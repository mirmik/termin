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

    struct FEMPhysicsWorldComponent::ContactRefreshState
    {
        enum class EndpointKind
        {
            Ignored,
            Static,
            RigidBody,
            ArticulationBase,
            ArticulationUnit,
        };

        struct EndpointOwner
        {
            EndpointKind kind = EndpointKind::Ignored;
            physics_qopt::RigidBody3DContribution* body = nullptr;
            physics_qopt::Articulation3DDynamicsContribution* articulation =
                nullptr;
            std::size_t unit_index = 0;
        };

        struct ArticulationBinding
        {
            physics_qopt::Articulation3DDynamicsContribution* articulation =
                nullptr;
            std::size_t unit_index = 0;
            bool base = false;
        };

        using EndpointMap =
            std::unordered_map<colliders::Collider*, EndpointOwner>;

        explicit ContactRefreshState(bool allow_adjacent_unit_collision,
                                     double friction_coefficient)
            : allow_adjacent_unit_collision(allow_adjacent_unit_collision),
              friction_coefficient(friction_coefficient)
        {
        }

        [[nodiscard]] bool accepts_pair(const EndpointOwner& a,
                                        const EndpointOwner& b) const
        {
            if (a.kind == EndpointKind::Ignored ||
                b.kind == EndpointKind::Ignored)
            {
                return false;
            }
            if (a.kind == EndpointKind::Static &&
                b.kind == EndpointKind::Static)
            {
                return false;
            }
            return !is_same_dynamic_endpoint(a, b) &&
                   !are_adjacent_articulation_units(a, b) &&
                   !are_connected_maximal_bodies(a, b);
        }

        void collect_live_groups()
        {
            using LiveEndpoint =
                std::pair<colliders::Collider*, const EndpointOwner*>;
            std::vector<LiveEndpoint> live_endpoints;
            live_endpoints.reserve(endpoint_owners.size());
            for (const auto& [collider, endpoint] : endpoint_owners)
            {
                live_endpoints.emplace_back(collider, &endpoint);
            }
            std::sort(live_endpoints.begin(),
                      live_endpoints.end(),
                      [](const LiveEndpoint& a, const LiveEndpoint& b)
                      {
                          return std::less<colliders::Collider*>{}(a.first,
                                                                   b.first);
                      });

            for (std::size_t first = 0; first < live_endpoints.size(); ++first)
            {
                for (std::size_t second = first + 1;
                     second < live_endpoints.size();
                     ++second)
                {
                    if (!accepts_pair(*live_endpoints[first].second,
                                      *live_endpoints[second].second))
                    {
                        continue;
                    }
                    live_groups.push_back(
                        group_key(live_endpoints[first].first,
                                  live_endpoints[second].first));
                }
            }
        }

        void append_contacts(const collision::ContactPatch& patch,
                             const EndpointOwner& a,
                             const EndpointOwner& b)
        {
            if (!accepts_pair(a, b))
            {
                return;
            }

            const std::uint64_t patch_group_key = nonzero_key(patch.pair_key());
            for (std::size_t point_index = 0; point_index < patch.points.size();
                 ++point_index)
            {
                const collision::ContactCandidate& point =
                    patch.points[point_index];
                contacts.push_back({
                    .key = contact_key(
                        patch, point.features, point_index, patch_group_key),
                    .group_key = patch_group_key,
                    .endpoint_a = make_endpoint(a, point.point_on_a_world),
                    .endpoint_b = make_endpoint(b, point.point_on_b_world),
                    .normal_from_a_to_b_world = patch.normal_world,
                    .signed_gap = point.signed_gap,
                    .friction_coefficient = friction_coefficient,
                });
            }
        }

        std::unordered_map<FEMRigidBodyComponent*, ArticulationBinding>
            articulation_bindings;
        EndpointMap endpoint_owners;
        std::vector<std::pair<physics_qopt::RigidBody3DContribution*,
                              physics_qopt::RigidBody3DContribution*>>
            connected_maximal_body_pairs;
        std::vector<physics_qopt::Contact3D> contacts;
        std::vector<std::uint64_t> live_groups;

    private:
        [[nodiscard]] static bool
        is_same_dynamic_endpoint(const EndpointOwner& a, const EndpointOwner& b)
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
            if (a.kind == EndpointKind::ArticulationUnit)
            {
                return a.articulation == b.articulation &&
                       a.unit_index == b.unit_index;
            }
            return false;
        }

        [[nodiscard]] bool
        are_adjacent_articulation_units(const EndpointOwner& a,
                                        const EndpointOwner& b) const
        {
            const bool a_belongs_to_articulation =
                a.kind == EndpointKind::ArticulationBase ||
                a.kind == EndpointKind::ArticulationUnit;
            const bool b_belongs_to_articulation =
                b.kind == EndpointKind::ArticulationBase ||
                b.kind == EndpointKind::ArticulationUnit;
            if (allow_adjacent_unit_collision || !a_belongs_to_articulation ||
                !b_belongs_to_articulation ||
                a.articulation != b.articulation || a.articulation == nullptr)
            {
                return false;
            }

            const auto& links = a.articulation->units();
            if (a.kind == EndpointKind::ArticulationBase ||
                b.kind == EndpointKind::ArticulationBase)
            {
                const EndpointOwner& link =
                    a.kind == EndpointKind::ArticulationUnit ? a : b;
                return link.kind == EndpointKind::ArticulationUnit &&
                       link.unit_index < links.size() &&
                       links[link.unit_index].parent_unit ==
                           robotics::articulation_root_frame;
            }
            if (a.unit_index >= links.size() || b.unit_index >= links.size())
            {
                return false;
            }
            return links[a.unit_index].parent_unit == b.unit_index ||
                   links[b.unit_index].parent_unit == a.unit_index;
        }

        [[nodiscard]] bool
        are_connected_maximal_bodies(const EndpointOwner& a,
                                     const EndpointOwner& b) const
        {
            if (allow_adjacent_unit_collision ||
                a.kind != EndpointKind::RigidBody ||
                b.kind != EndpointKind::RigidBody)
            {
                return false;
            }
            return std::any_of(
                connected_maximal_body_pairs.begin(),
                connected_maximal_body_pairs.end(),
                [&a, &b](const auto& pair)
                {
                    return (pair.first == a.body && pair.second == b.body) ||
                           (pair.first == b.body && pair.second == a.body);
                });
        }

        [[nodiscard]] static physics_qopt::ContactEndpoint3D
        make_endpoint(const EndpointOwner& endpoint, const Vec3& point_world)
        {
            switch (endpoint.kind)
            {
            case EndpointKind::Static:
                return physics_qopt::ContactEndpoint3D::static_world(
                    point_world);
            case EndpointKind::RigidBody:
                return physics_qopt::ContactEndpoint3D::rigid_body(
                    *endpoint.body,
                    endpoint.body->state().pose.inverse_transform_point(
                        point_world));
            case EndpointKind::ArticulationBase:
                return physics_qopt::ContactEndpoint3D::articulation_base(
                    *endpoint.articulation,
                    endpoint.articulation->floating_base()
                        ->pose_world.inverse_transform_point(point_world));
            case EndpointKind::ArticulationUnit:
                return physics_qopt::ContactEndpoint3D::articulation_unit(
                    *endpoint.articulation,
                    endpoint.unit_index,
                    endpoint.articulation
                        ->unit_poses_world()[endpoint.unit_index]
                        .inverse_transform_point(point_world));
            case EndpointKind::Ignored:
                return physics_qopt::ContactEndpoint3D{};
            }
            return physics_qopt::ContactEndpoint3D{};
        }

        [[nodiscard]] static std::uint64_t
        group_key(colliders::Collider* collider_a,
                  colliders::Collider* collider_b)
        {
            collision::ContactPatch pair;
            pair.collider_a = collider_a;
            pair.collider_b = collider_b;
            return nonzero_key(pair.pair_key());
        }

        [[nodiscard]] std::uint64_t
        contact_key(const collision::ContactPatch& patch,
                    collision::ContactFeaturePair features,
                    std::size_t point_index,
                    std::uint64_t patch_group_key)
        {
            if (std::less<colliders::Collider*>{}(patch.collider_b,
                                                  patch.collider_a))
            {
                std::swap(features.feature_a, features.feature_b);
            }

            std::uint64_t feature_key =
                (std::uint64_t{features.feature_a} << 32U) |
                std::uint64_t{features.feature_b};
            if (features.feature_a ==
                    collision::ContactFeaturePair::INVALID_FEATURE &&
                features.feature_b ==
                    collision::ContactFeaturePair::INVALID_FEATURE)
            {
                feature_key = point_index;
            }

            std::uint64_t key = combine_key(patch_group_key, feature_key);
            while (!contact_keys.insert(key).second)
            {
                ++key;
            }
            return key;
        }

        bool allow_adjacent_unit_collision = false;
        double friction_coefficient = 0.0;
        std::unordered_set<std::uint64_t> contact_keys;
    };

    void FEMPhysicsWorldComponent::warn_contact_collider_once(
        const void* collider, const char* message, const char* entity_name)
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
    }

    bool FEMPhysicsWorldComponent::collect_contact_endpoints(
        const TcSceneRef& scene, ContactRefreshState& state)
    {
        for (FEMArticulationComponent* articulation : articulations_)
        {
            if (articulation == nullptr || articulation->dynamics_ == nullptr)
            {
                continue;
            }
            if (articulation->base_body_ != nullptr &&
                !state.articulation_bindings
                     .emplace(articulation->base_body_,
                              ContactRefreshState::ArticulationBinding{
                                  .articulation = articulation->dynamics_,
                                  .base = true,
                              })
                     .second)
            {
                tc::Log::error(
                    "[FEMPhysicsWorldComponent] ambiguous floating-base "
                    "contact ownership");
                return false;
            }
            for (std::size_t unit_index = 0;
                 unit_index < articulation->bodies_.size();
                 ++unit_index)
            {
                FEMRigidBodyComponent* body = articulation->bodies_[unit_index];
                if (body == nullptr)
                {
                    continue;
                }
                if (!state.articulation_bindings
                         .emplace(body,
                                  ContactRefreshState::ArticulationBinding{
                                      .articulation = articulation->dynamics_,
                                      .unit_index = unit_index,
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

        for (const FEMRevoluteJointComponent* joint : revolute_joints_)
        {
            if (joint != nullptr)
            {
                state.connected_maximal_body_pairs.emplace_back(joint->body_a_,
                                                                joint->body_b_);
            }
        }

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
            ContactRefreshState::EndpointOwner endpoint;
            const std::uint64_t layer = candidate.layer();
            const bool selected_layer =
                layer < 64 &&
                (collision_layer_mask & (std::uint64_t{1} << layer)) != 0;
            if (!candidate.enabled() || !collider_component->enabled() ||
                !selected_layer)
            {
                state.endpoint_owners.emplace(collider, endpoint);
                continue;
            }

            FEMRigidBodyComponent* body = nullptr;
            Entity body_entity = candidate;
            while (body_entity.valid() && body == nullptr)
            {
                body = body_entity.get_component<FEMRigidBodyComponent>();
                body_entity = body_entity.parent();
            }
            if (body == nullptr || !body->enabled())
            {
                endpoint.kind = ContactRefreshState::EndpointKind::Static;
                state.endpoint_owners.emplace(collider, endpoint);
                continue;
            }
            if (body->world_ != this)
            {
                warn_contact_collider_once(
                    collider,
                    "enabled FEM body is not registered in this world",
                    candidate.name());
                state.endpoint_owners.emplace(collider, endpoint);
                continue;
            }

            const auto articulation_binding =
                state.articulation_bindings.find(body);
            const bool owns_maximal_body = body->body_ != nullptr;
            const bool owns_articulation_unit =
                articulation_binding != state.articulation_bindings.end();
            if (owns_maximal_body == owns_articulation_unit)
            {
                warn_contact_collider_once(
                    collider,
                    "dynamic collider has ambiguous or missing endpoint "
                    "ownership",
                    candidate.name());
                state.endpoint_owners.emplace(collider, endpoint);
                continue;
            }
            if (owns_maximal_body)
            {
                endpoint.kind = ContactRefreshState::EndpointKind::RigidBody;
                endpoint.body = body->body_;
            }
            else
            {
                endpoint.kind =
                    articulation_binding->second.base
                        ? ContactRefreshState::EndpointKind::ArticulationBase
                        : ContactRefreshState::EndpointKind::ArticulationUnit;
                endpoint.articulation =
                    articulation_binding->second.articulation;
                endpoint.unit_index = articulation_binding->second.unit_index;
            }
            state.endpoint_owners.emplace(collider, endpoint);
        }
        return true;
    }

    bool FEMPhysicsWorldComponent::refresh_contacts()
    {
        if (contacts_ == nullptr)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] contact contribution is missing");
            return false;
        }

        const TcSceneRef scene = entity().scene();
        collision::CollisionWorld* collision_world =
            collision::CollisionWorld::from_scene(scene.handle());
        if (collision_world == nullptr)
        {
            return contacts_->set_contacts({}) ==
                   physics_qopt::Contact3DDiagnostic::None;
        }

        ContactRefreshState state{adjacent_unit_collision_enabled,
                                  contact_friction_coefficient};
        if (!collect_contact_endpoints(scene, state))
        {
            return false;
        }

        collision_world->update_all();
        const std::vector<collision::ContactPatch> patches =
            collision_world->detect_contacts();
        state.collect_live_groups();

        for (const collision::ContactPatch& patch : patches)
        {
            const auto owner_a = state.endpoint_owners.find(patch.collider_a);
            const auto owner_b = state.endpoint_owners.find(patch.collider_b);
            if (owner_a == state.endpoint_owners.end() ||
                owner_b == state.endpoint_owners.end())
            {
                const void* unmapped = owner_a == state.endpoint_owners.end()
                                           ? patch.collider_a
                                           : patch.collider_b;
                warn_contact_collider_once(
                    unmapped,
                    "CollisionWorld returned an unmapped collider",
                    "<no ColliderComponent>");
                continue;
            }
            state.append_contacts(patch, owner_a->second, owner_b->second);
        }

        const physics_qopt::Contact3DDiagnostic diagnostic =
            contacts_->set_contacts(std::move(state.contacts),
                                    std::move(state.live_groups));
        if (diagnostic != physics_qopt::Contact3DDiagnostic::None)
        {
            tc::Log::error(
                "[FEMPhysicsWorldComponent] scene contact conversion failed: "
                "%s",
                physics_qopt::contact3d_diagnostic_name(diagnostic).data());
            return false;
        }
        return true;
    }

} // namespace termin
