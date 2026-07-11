#include <iostream>

#include <termin_modules/native_module_abi.h>

namespace {

int32_t cpp_demo_init(
    const termin_native_module_host_v1*,
    termin_native_module_error*
) {
    std::cout << "[cpp_demo] init\n";
    return 0;
}

int32_t cpp_demo_shutdown(
    const termin_native_module_host_v1*,
    termin_native_module_error*
) {
    std::cout << "[cpp_demo] shutdown\n";
    return 0;
}

} // namespace

TERMIN_NATIVE_MODULE_DESCRIPTOR_V1(
    "cpp_demo",
    "1.0.0",
    "termin-modules-basic-example",
    TERMIN_NATIVE_MODULE_CAP_NONE,
    cpp_demo_init,
    cpp_demo_shutdown
);
