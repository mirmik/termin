#include <termin/navmesh/off_mesh_link_component.hpp>

#include <tc_inspect_cpp.hpp>

#include <limits>

namespace termin {

void OffMeshLinkComponent::register_type() {
    auto descriptor = ComponentTypeDescriptorBuilder::native<OffMeshLinkComponent>(
        "OffMeshLinkComponent", "termin-navmesh", "Component");
    descriptor.category("Navigation");
    tc::stage_inspect_field(descriptor.inspect(),
        &OffMeshLinkComponent::enabled,
        "OffMeshLinkComponent",
        "enabled",
        "Enabled",
        "bool"
    );
    tc::stage_inspect_field_choices(descriptor.inspect(),
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
    tc::stage_inspect_field(descriptor.inspect(),
        &OffMeshLinkComponent::agent_type,
        "OffMeshLinkComponent",
        "agent_type",
        "Agent Type",
        "string"
    );
    tc::stage_inspect_field(descriptor.inspect(),
        &OffMeshLinkComponent::area_id,
        "OffMeshLinkComponent",
        "area_id",
        "Area",
        "navmesh_area"
    );
    tc::stage_inspect_field(descriptor.inspect(),
        &OffMeshLinkComponent::stable_user_id,
        "OffMeshLinkComponent",
        "stable_user_id",
        "Stable User Id",
        "uint32",
        0.0,
        static_cast<double>(std::numeric_limits<unsigned int>::max()),
        1.0
    );
    tc::stage_inspect_field(descriptor.inspect(),
        &OffMeshLinkComponent::start_local,
        "OffMeshLinkComponent",
        "start_local",
        "Start Local",
        "vec3"
    );
    tc::stage_inspect_field(descriptor.inspect(),
        &OffMeshLinkComponent::end_local,
        "OffMeshLinkComponent",
        "end_local",
        "End Local",
        "vec3"
    );
    tc::stage_inspect_field(descriptor.inspect(),
        &OffMeshLinkComponent::radius,
        "OffMeshLinkComponent",
        "radius",
        "Radius",
        "double",
        0.01,
        10.0,
        0.01
    );
    tc::stage_inspect_field(descriptor.inspect(),
        &OffMeshLinkComponent::bidirectional,
        "OffMeshLinkComponent",
        "bidirectional",
        "Bidirectional",
        "bool"
    );
    tc::stage_inspect_button_method<OffMeshLinkComponent>(
        descriptor.inspect(),
        "center_btn",
        "Center Entity",
        &OffMeshLinkComponent::center_entity
    );
    (void)descriptor.commit();
}

} // namespace termin
