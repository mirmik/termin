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
    registry.unregister_owner(owner);
    registry.unregister_owner(other_owner);
    registry.set_registration_owner("");

    termin::NavMeshBakeVisitor visitor =
        [](termin::Entity,
           termin::CxxComponent*,
           const termin::NavMeshBakeContext&,
           termin::NavMeshBakeInput&) {};

    registry.set_registration_owner(owner);
    if (!registry.register_geometry_visitor(owned_type, visitor)) {
        return fail("owned visitor registration failed");
    }
    if (registry.geometry_visitor_owner(owned_type) != owner) {
        return fail("owned visitor did not capture registration owner");
    }

    registry.set_registration_owner(other_owner);
    if (registry.register_geometry_visitor(owned_type, visitor)) {
        return fail("cross-owner visitor replacement succeeded");
    }
    if (registry.geometry_visitor_owner(owned_type) != owner) {
        return fail("cross-owner replacement changed original owner");
    }

    registry.set_registration_owner("");
    if (!registry.register_geometry_visitor(unowned_type, visitor)) {
        return fail("unowned visitor registration failed");
    }
    if (!registry.geometry_visitor(unowned_type)) {
        return fail("unowned visitor lookup failed");
    }

    if (registry.unregister_owner(owner) != 1) {
        return fail("owner cleanup did not remove exactly one visitor");
    }
    if (registry.geometry_visitor(owned_type)) {
        return fail("owner cleanup left owned visitor registered");
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
