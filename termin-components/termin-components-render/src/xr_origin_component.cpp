#include <termin/xr/xr_origin_component.hpp>

#include <cstdio>
#include <cstdlib>

#include <tc_inspect_cpp.hpp>
#include <termin/entity/component_registry.hpp>

namespace termin {

XrOriginComponent::XrOriginComponent()
    : CxxComponent("XrOriginComponent")
{}

void XrOriginComponent::register_type() {
    auto& component_registry = ComponentRegistry::instance();
    if (!component_registry.has("XrOriginComponent")) {
        component_registry.register_native(
            "XrOriginComponent",
            &CxxComponentFactoryData<XrOriginComponent>::create,
            nullptr,
            "Component"
        );
    }

    auto& inspect = tc::InspectRegistry::instance();
    inspect.set_type_parent("XrOriginComponent", "Component");
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

REGISTER_COMPONENT(XrOriginComponent, CxxComponent);

static struct _XrOriginReferenceSpaceFieldRegistrar {
    _XrOriginReferenceSpaceFieldRegistrar() {
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
        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<XrOriginComponent*>(obj);
            if (value.type == TC_VALUE_STRING && value.data.s) {
                c->set_reference_space_str(value.data.s);
            }
        };
        tc::InspectRegistry::instance().add_field_with_choices("XrOriginComponent", std::move(info));
    }
} _xr_origin_reference_space_registrar;

static struct _XrOriginLayerMaskFieldRegistrar {
    _XrOriginLayerMaskFieldRegistrar() {
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
        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<XrOriginComponent*>(obj);
            if (value.type == TC_VALUE_STRING && value.data.s) {
                c->layer_mask = strtoull(value.data.s, nullptr, 0);
                return;
            }
            if (value.type == TC_VALUE_INT) {
                c->layer_mask = static_cast<uint64_t>(value.data.i);
            }
        };
        tc::InspectRegistry::instance().add_field_with_choices("XrOriginComponent", std::move(info));
    }
} _xr_origin_layer_mask_registrar;

} // namespace termin
