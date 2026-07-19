#include <tc_inspect_cpp.hpp>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/render/frame_pass.hpp>
#include <termin_modules/native_module_abi.h>

namespace {

class HotReloadNativeProbeComponent : public termin::CxxComponent {
public:
    int value = 0;

    HotReloadNativeProbeComponent()
        : termin::CxxComponent("HotReloadNativeProbeComponent") {}
};

class HotReloadNativeProbePass : public termin::CxxFramePass {
public:
    int exposure = 0;

    static void register_type();

    HotReloadNativeProbePass() {
        link_to_type_registry("HotReloadNativeProbePass");
    }

    std::set<const char*> compute_reads() const override { return {"source"}; }
    std::set<const char*> compute_writes() const override { return {"output"}; }
    std::vector<termin::ResourceSpec> get_resource_specs() const override {
        return {termin::ResourceSpec("output", "color_texture")};
    }
};

void HotReloadNativeProbePass::register_type() {
    const char* owner = tc_runtime_type_registry_get_registration_owner();
    auto descriptor = termin::FramePassTypeDescriptorBuilder::native<HotReloadNativeProbePass>(
        "HotReloadNativeProbePass", owner, "CxxFramePass");
    (void)descriptor.inspect().add<HotReloadNativeProbePass, int>(
        &HotReloadNativeProbePass::exposure,
        tc::InspectFieldSpec{
            "HotReloadNativeProbePass", "exposure", "Exposure", "int"});
    (void)descriptor.commit();
}

} // namespace

int32_t native_probe_init(
    const termin_native_module_host_v1*,
    termin_native_module_error*
) {
    HotReloadNativeProbePass::register_type();
    TC_MODULE_REGISTER_COMPONENT(HotReloadNativeProbeComponent, CxxComponent);
    TC_MODULE_INSPECT_FIELD(
        HotReloadNativeProbeComponent,
        value,
        "Value",
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
