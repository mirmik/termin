#include <termin/navmesh/navmesh_bake_source.hpp>

#include <iostream>
#include <string>

namespace {

int fail(const std::string& message) {
    std::cerr << "FAIL: " << message << "\n";
    return 1;
}

} // namespace

int main() {
    auto& registry = termin::NavMeshBakeVisitorRegistry::instance();

    const std::string previous_owner = registry.registration_owner();
    const std::string owned_type = "NavMeshBakeVisitorRegistryOwnedProbe";
    const std::string unowned_type = "NavMeshBakeVisitorRegistryUnownedProbe";
    const std::string owner = "navmesh_bake_visitor_registry_test";
    const std::string other_owner = "navmesh_bake_visitor_registry_other";

    registry.unregister_geometry_visitor(owned_type);
    registry.unregister_geometry_visitor(unowned_type);
    registry.unregister_link_visitor(owned_type);
    registry.unregister_linear_visitor(owned_type);
    registry.unregister_owner(owner);
    registry.unregister_owner(other_owner);
    registry.set_registration_owner("");

    bool linear_visitor_called = false;
    termin::NavMeshBakeVisitor visitor =
        [](termin::Entity,
           termin::CxxComponent*,
           const termin::NavMeshBakeContext&,
           termin::NavMeshBakeInput&) {};
    termin::NavMeshBakeVisitor linear_visitor =
        [&linear_visitor_called](termin::Entity entity,
                                 termin::CxxComponent*,
                                 const termin::NavMeshBakeContext&,
                                 termin::NavMeshBakeInput& input) {
            linear_visitor_called = true;

            termin::NavMeshLinearPathSegmentRecord first;
            first.end[0] = 1.0f;
            first.user_id = termin::stable_navmesh_source_user_id(entity, "linear:first");
            first.debug_name = "first";
            const int first_index = input.add_linear_segment(first);

            termin::NavMeshLinearPathSegmentRecord second;
            second.start[0] = 1.0f;
            second.end[0] = 2.0f;
            second.user_id = termin::stable_navmesh_source_user_id(entity, "linear:second");
            second.debug_name = "second";
            const int second_index = input.add_linear_segment(second);

            termin::NavMeshLinearPathLinkRecord link;
            link.from_segment = first_index;
            link.to_segment = second_index;
            link.from_t = 65535;
            link.to_t = 0;
            link.debug_name = "first-to-second";
            input.add_linear_link(link);

            termin::NavMeshLinearPathLinkRecord invalid_link;
            invalid_link.from_segment = second_index;
            invalid_link.to_segment = second_index + 10;
            invalid_link.debug_name = "invalid";
            input.add_linear_link(invalid_link);
        };

    registry.set_registration_owner(owner);
    if (!registry.register_geometry_visitor(owned_type, visitor)) {
        return fail("owned visitor registration failed");
    }
    if (!registry.register_linear_visitor(owned_type, linear_visitor)) {
        return fail("owned linear visitor registration failed");
    }
    if (registry.geometry_visitor_owner(owned_type) != owner) {
        return fail("owned visitor did not capture registration owner");
    }
    if (registry.linear_visitor_owner(owned_type) != owner) {
        return fail("owned linear visitor did not capture registration owner");
    }

    registry.set_registration_owner(other_owner);
    if (registry.register_geometry_visitor(owned_type, visitor)) {
        return fail("cross-owner visitor replacement succeeded");
    }
    if (registry.register_linear_visitor(owned_type, visitor)) {
        return fail("cross-owner linear visitor replacement succeeded");
    }
    if (registry.geometry_visitor_owner(owned_type) != owner) {
        return fail("cross-owner replacement changed original owner");
    }
    if (registry.linear_visitor_owner(owned_type) != owner) {
        return fail("cross-owner linear replacement changed original owner");
    }

    registry.set_registration_owner("");
    if (!registry.register_geometry_visitor(unowned_type, visitor)) {
        return fail("unowned visitor registration failed");
    }
    if (!registry.geometry_visitor(unowned_type)) {
        return fail("unowned visitor lookup failed");
    }

    termin::CxxComponent component(owned_type.c_str());
    termin::NavMeshBakeInput input;
    if (registry.visit_component(termin::Entity(), &component, owned_type.c_str(), termin::NavMeshBakeContext(), input) != 2) {
        return fail("visit_component did not dispatch geometry and linear visitors");
    }
    if (!linear_visitor_called) {
        return fail("linear visitor was not called");
    }
    if (input.linear_segment_count() != 2) {
        return fail("linear visitor did not add two segments");
    }
    if (input.linear_link_count() != 1) {
        return fail("linear visitor did not add exactly one valid link");
    }

    if (registry.unregister_owner(owner) != 2) {
        return fail("owner cleanup did not remove exactly two visitors");
    }
    if (registry.geometry_visitor(owned_type)) {
        return fail("owner cleanup left owned visitor registered");
    }
    if (registry.linear_visitor(owned_type)) {
        return fail("owner cleanup left owned linear visitor registered");
    }
    if (!registry.geometry_visitor(unowned_type)) {
        return fail("owner cleanup removed unowned visitor");
    }
    if (registry.unregister_owner(owner) != 0) {
        return fail("owner cleanup is not idempotent");
    }

    registry.unregister_geometry_visitor(unowned_type);
    registry.set_registration_owner(previous_owner);
    return 0;
}
