#include <tc_inspect_cpp.hpp>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin_modules/native_module_abi.h>

namespace {

class HotReloadNativeProbeComponent : public termin::CxxComponent {
public:
    HotReloadNativeProbeComponent()
        : termin::CxxComponent("HotReloadNativeProbeComponent") {}

    int value = 0;
};

class HotReloadNativeProbePass : public termin::CxxFramePass {
public:
    int exposure = 0;

    HotReloadNativeProbePass() {
        link_to_type_registry("HotReloadNativeProbePass");
    }

    std::set<const char*> compute_reads() const override { return {"source"}; }
    std::set<const char*> compute_writes() const override { return {"output"}; }
    std::vector<termin::ResourceSpec> get_resource_specs() const override {
        return {termin::ResourceSpec("output", "color_texture")};
    }
};

TC_REGISTER_FRAME_PASS_DERIVED(HotReloadNativeProbePass, CxxFramePass);

class EngineHeaderSideEffectProbe {
public:
    int value = 0;
};

class EngineHeaderSideEffectComponentProbe : public termin::CxxComponent {
public:
    EngineHeaderSideEffectComponentProbe()
        : termin::CxxComponent("EngineOwnedProbeComponent") {}
};

static termin::ComponentRegistrar<EngineHeaderSideEffectComponentProbe>
    engine_header_side_effect_component_registrar("EngineOwnedProbeComponent", "CxxComponent");

struct EngineHeaderSideEffectInspectRegistration {
    EngineHeaderSideEffectInspectRegistration() {
        tc::InspectRegistry::instance().add<EngineHeaderSideEffectProbe, int>(
            "EngineOwnedProbeType",
            &EngineHeaderSideEffectProbe::value,
            "value",
            "Value From Module Header Side Effect",
            "int"
        );
    }
};

static EngineHeaderSideEffectInspectRegistration engine_header_side_effect_inspect_registration;

} // namespace

int32_t native_probe_init(
    const termin_native_module_host_v1*,
    termin_native_module_error*
) {
    TC_MODULE_REGISTER_COMPONENT(HotReloadNativeProbeComponent, CxxComponent);
    TC_MODULE_INSPECT_FIELD(
        HotReloadNativeProbeComponent,
        value,
        "Value",
        "int"
    );
    TC_MODULE_INSPECT_FIELD(
        HotReloadNativeProbePass,
        exposure,
        "Exposure",
        "int"
    );
    return 0;
}

int32_t native_probe_shutdown(
    const termin_native_module_host_v1*,
    termin_native_module_error*
) {
    // Intentionally do not unregister anything here. The integration test
    // verifies module-owner cleanup before dlclose/FreeLibrary.
    return 0;
}

TERMIN_NATIVE_MODULE_DESCRIPTOR_V1(
    "native_probe",
    "1.0.0",
    "termin-engine-native-probe",
    TERMIN_NATIVE_MODULE_CAP_COMPONENTS |
        TERMIN_NATIVE_MODULE_CAP_FRAME_PASSES |
        TERMIN_NATIVE_MODULE_CAP_INSPECT_TYPES,
    native_probe_init,
    native_probe_shutdown
);
