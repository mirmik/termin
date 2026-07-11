#include <termin/navmesh/off_mesh_link_component.hpp>

#include <tc_inspect_cpp.hpp>

#include <limits>

namespace termin {

void OffMeshLinkComponent::register_type() {
    register_component_type<OffMeshLinkComponent>("OffMeshLinkComponent", "Component");
    ComponentRegistry::instance().set_category("OffMeshLinkComponent", "Navigation");
    tc::register_inspect_field(
        &OffMeshLinkComponent::enabled,
        "OffMeshLinkComponent",
        "enabled",
        "Enabled",
        "bool"
    );
    tc::register_inspect_field_choices(
        &OffMeshLinkComponent::link_type,
        "OffMeshLinkComponent",
        "link_type",
        "Type",
        "enum",
        {
            {"0", "Generic"},
            {"1", "JumpDown"},
            {"2", "Jump"},
            {"3", "Climb"},
        }
    );
    tc::register_inspect_field(
        &OffMeshLinkComponent::agent_type,
        "OffMeshLinkComponent",
        "agent_type",
        "Agent Type",
        "string"
    );
    tc::register_inspect_field(
        &OffMeshLinkComponent::area_id,
        "OffMeshLinkComponent",
        "area_id",
        "Area",
        "navmesh_area"
    );
    tc::register_inspect_field(
        &OffMeshLinkComponent::stable_user_id,
        "OffMeshLinkComponent",
        "stable_user_id",
        "Stable User Id",
        "uint32",
        0.0,
        static_cast<double>(std::numeric_limits<unsigned int>::max()),
        1.0
    );
    tc::register_inspect_field(
        &OffMeshLinkComponent::start_local,
        "OffMeshLinkComponent",
        "start_local",
        "Start Local",
        "vec3"
    );
    tc::register_inspect_field(
        &OffMeshLinkComponent::end_local,
        "OffMeshLinkComponent",
        "end_local",
        "End Local",
        "vec3"
    );
    tc::register_inspect_field(
        &OffMeshLinkComponent::radius,
        "OffMeshLinkComponent",
        "radius",
        "Radius",
        "double",
        0.01,
        10.0,
        0.01
    );
    tc::register_inspect_field(
        &OffMeshLinkComponent::bidirectional,
        "OffMeshLinkComponent",
        "bidirectional",
        "Bidirectional",
        "bool"
    );
    tc::register_inspect_button_method(
        "OffMeshLinkComponent",
        "center_btn",
        "Center Entity",
        &OffMeshLinkComponent::center_entity
    );
}

} // namespace termin
