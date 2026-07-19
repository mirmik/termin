#include <termin/xr/xr_origin_component.hpp>

#include <cstdio>
#include <cstdlib>

#include <tc_inspect_cpp.hpp>
#include <termin/entity/component_registry.hpp>

namespace termin {

namespace {

void register_xr_origin_reference_space_field(tc::InspectFacetBuilder& builder);
void register_xr_origin_reference_alignment_field(tc::InspectFacetBuilder& builder);
void register_xr_origin_layer_mask_field(tc::InspectFacetBuilder& builder);

} // namespace

XrOriginComponent::XrOriginComponent()
    : CxxComponent("XrOriginComponent")
{}

void XrOriginComponent::register_type() {
    auto descriptor = ComponentTypeDescriptorBuilder::native<XrOriginComponent>(
        "XrOriginComponent", "termin-components-render", "CxxComponent");
    descriptor.category("Rendering");
    auto& inspect = descriptor.inspect();
    if (!inspect.find_field("XrOriginComponent", "near_clip")) {
        inspect.add<XrOriginComponent, double>(
            "XrOriginComponent",
            &XrOriginComponent::near_clip,
            "near_clip",
            "Near Clip",
            "double"
        );
    }
    if (!inspect.find_field("XrOriginComponent", "far_clip")) {
        inspect.add<XrOriginComponent, double>(
            "XrOriginComponent",
            &XrOriginComponent::far_clip,
            "far_clip",
            "Far Clip",
            "double"
        );
    }
    register_xr_origin_reference_space_field(inspect);
    register_xr_origin_reference_alignment_field(inspect);
    register_xr_origin_layer_mask_field(inspect);
    (void)descriptor.commit();
}

std::string XrOriginComponent::get_reference_space_str() const {
    switch (reference_space) {
        case XrReferenceSpace::Stage: return "stage";
        case XrReferenceSpace::Local: return "local";
    }
    return "local";
}

void XrOriginComponent::set_reference_space_str(const std::string& value) {
    if (value == "stage") {
        reference_space = XrReferenceSpace::Stage;
        return;
    }
    reference_space = XrReferenceSpace::Local;
}

std::string XrOriginComponent::get_reference_alignment_str() const {
    switch (reference_alignment) {
        case XrReferenceAlignment::StageAxes: return "stage_axes";
        case XrReferenceAlignment::InitialHeadYaw: return "initial_head_yaw";
    }
    return "initial_head_yaw";
}

void XrOriginComponent::set_reference_alignment_str(const std::string& value) {
    if (value == "stage_axes") {
        reference_alignment = XrReferenceAlignment::StageAxes;
        return;
    }
    reference_alignment = XrReferenceAlignment::InitialHeadYaw;
}

namespace {

void register_xr_origin_reference_space_field(tc::InspectFacetBuilder& builder) {
        tc::InspectFieldInfo info;
        info.type_name = "XrOriginComponent";
        info.path = "reference_space";
        info.label = "Reference Space";
        info.kind = "string";
        info.choices.push_back({"local", "Local"});
        info.choices.push_back({"stage", "Stage"});
        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<XrOriginComponent*>(obj);
            return tc_value_string(c->get_reference_space_str().c_str());
        };
        info.setter = [](void* obj, tc_value value, void*) -> bool {
            auto* c = static_cast<XrOriginComponent*>(obj);
            if (value.type == TC_VALUE_STRING && value.data.s) {
                c->set_reference_space_str(value.data.s);
                return true;
            }
            return false;
        };
        (void)builder.add_field(std::move(info));
}

void register_xr_origin_reference_alignment_field(tc::InspectFacetBuilder& builder) {
        tc::InspectFieldInfo info;
        info.type_name = "XrOriginComponent";
        info.path = "reference_alignment";
        info.label = "Reference Alignment";
        info.kind = "string";
        info.choices.push_back({"initial_head_yaw", "Initial Head Yaw"});
        info.choices.push_back({"stage_axes", "Stage Axes"});
        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<XrOriginComponent*>(obj);
            return tc_value_string(c->get_reference_alignment_str().c_str());
        };
        info.setter = [](void* obj, tc_value value, void*) -> bool {
            auto* c = static_cast<XrOriginComponent*>(obj);
            if (value.type == TC_VALUE_STRING && value.data.s) {
                c->set_reference_alignment_str(value.data.s);
                return true;
            }
            return false;
        };
        (void)builder.add_field(std::move(info));
}

void register_xr_origin_layer_mask_field(tc::InspectFacetBuilder& builder) {
        tc::InspectFieldInfo info;
        info.type_name = "XrOriginComponent";
        info.path = "layer_mask";
        info.label = "Layers";
        info.kind = "layer_mask";
        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<XrOriginComponent*>(obj);
            char buf[32];
            snprintf(buf, sizeof(buf), "0x%llx", (unsigned long long)c->layer_mask);
            return tc_value_string(buf);
        };
        info.setter = [](void* obj, tc_value value, void*) -> bool {
            auto* c = static_cast<XrOriginComponent*>(obj);
            if (value.type == TC_VALUE_STRING && value.data.s) {
                c->layer_mask = strtoull(value.data.s, nullptr, 0);
                return true;
            }
            if (value.type == TC_VALUE_INT) {
                c->layer_mask = static_cast<uint64_t>(value.data.i);
                return true;
            }
            return false;
        };
        (void)builder.add_field(std::move(info));
}

} // namespace

} // namespace termin
