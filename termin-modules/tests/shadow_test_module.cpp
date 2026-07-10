#include <termin_modules/native_module_abi.h>

extern "C" int termin_shadow_test_dependency_value();

namespace {

int32_t shadow_init(
    const termin_native_module_host_v1*,
    termin_native_module_error* error
) {
    if (termin_shadow_test_dependency_value() != 42) {
        termin_native_module_set_error(error, "shadow test dependency mismatch");
        return 1;
    }
    return 0;
}

int32_t shadow_shutdown(
    const termin_native_module_host_v1*,
    termin_native_module_error*
) {
    return 0;
}

} // namespace

TERMIN_NATIVE_MODULE_DESCRIPTOR_V1(
    "shadow_test",
    "1.0.0",
    "termin-modules-shadow-test",
    TERMIN_NATIVE_MODULE_CAP_NONE,
    shadow_init,
    shadow_shutdown
);
