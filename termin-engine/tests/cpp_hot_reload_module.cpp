#include <tc_inspect_cpp.hpp>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>

namespace {

class HotReloadNativeProbeComponent : public termin::CxxComponent {
public:
    HotReloadNativeProbeComponent()
        : termin::CxxComponent("HotReloadNativeProbeComponent") {}

    int value = 0;
};

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

#ifdef _WIN32
    #define TERMIN_TEST_MODULE_API __declspec(dllexport)
#else
    #define TERMIN_TEST_MODULE_API __attribute__((visibility("default")))
#endif

extern "C" TERMIN_TEST_MODULE_API void module_init() {
    TC_MODULE_REGISTER_COMPONENT(HotReloadNativeProbeComponent, CxxComponent);
    TC_MODULE_INSPECT_FIELD(
        HotReloadNativeProbeComponent,
        value,
        "Value",
        "int"
    );
}

extern "C" TERMIN_TEST_MODULE_API void module_shutdown() {
    // Intentionally do not unregister anything here. The integration test
    // verifies module-owner cleanup before dlclose/FreeLibrary.
}
