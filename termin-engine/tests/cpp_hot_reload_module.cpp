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

static termin::ComponentRegistrar<HotReloadNativeProbeComponent>
    hot_reload_native_probe_registrar("HotReloadNativeProbeComponent", "CxxComponent");

struct HotReloadNativeProbeInspectRegistration {
    HotReloadNativeProbeInspectRegistration() {
        tc::InspectRegistry::instance().add<HotReloadNativeProbeComponent, int>(
            "HotReloadNativeProbeComponent",
            &HotReloadNativeProbeComponent::value,
            "value",
            "Value",
            "int"
        );
    }
};

static HotReloadNativeProbeInspectRegistration hot_reload_native_probe_inspect_registration;

} // namespace

#ifdef _WIN32
    #define TERMIN_TEST_MODULE_API __declspec(dllexport)
#else
    #define TERMIN_TEST_MODULE_API __attribute__((visibility("default")))
#endif

extern "C" TERMIN_TEST_MODULE_API void module_init() {}

extern "C" TERMIN_TEST_MODULE_API void module_shutdown() {
    // Intentionally do not unregister anything here. The integration test
    // verifies module-owner cleanup before dlclose/FreeLibrary.
}
