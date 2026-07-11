#include <termin_modules/native_module_abi.h>

namespace {

int32_t ok_init(const termin_native_module_host_v1*, termin_native_module_error*) {
    return 0;
}

int32_t ok_shutdown(const termin_native_module_host_v1*, termin_native_module_error*) {
    return 0;
}

int32_t failing_init(
    const termin_native_module_host_v1*,
    termin_native_module_error* error
) {
    termin_native_module_set_error(error, "injected structured init failure");
    return 17;
}

int g_shutdown_attempts = 0;

int32_t retrying_shutdown(
    const termin_native_module_host_v1*,
    termin_native_module_error* error
) {
    ++g_shutdown_attempts;
    if (g_shutdown_attempts == 1) {
        termin_native_module_set_error(error, "injected retryable shutdown failure");
        return 23;
    }
    return 0;
}

} // namespace

#if defined(TERMIN_ABI_TEST_MISSING_DESCRIPTOR)
extern "C" TERMIN_NATIVE_MODULE_EXPORT int termin_abi_test_marker = 1;
#elif defined(TERMIN_ABI_TEST_MISMATCH)
extern "C" TERMIN_NATIVE_MODULE_EXPORT const
    termin_native_module_descriptor_v1_data termin_module_descriptor_v1 = {
        sizeof(termin_native_module_descriptor_v1_data),
        999u,
        TERMIN_NATIVE_HOST_ABI_VERSION,
        TERMIN_NATIVE_MODULE_ABI_VERSION,
        TC_VERSION,
        TERMIN_MODULE_COMPILER_FAMILY,
        TERMIN_MODULE_COMPILER_VERSION,
        TERMIN_MODULE_CXX_ABI_FLAGS,
        (uint32_t)sizeof(void*),
        "abi_mismatch",
        "1.0.0",
        "abi-mismatch-test",
        TERMIN_NATIVE_MODULE_CAP_NONE,
        ok_init,
        ok_shutdown
    };
#elif defined(TERMIN_ABI_TEST_INIT_FAILURE)
TERMIN_NATIVE_MODULE_DESCRIPTOR_V1(
    "abi_init_failure",
    "1.0.0",
    "abi-init-failure-test",
    TERMIN_NATIVE_MODULE_CAP_NONE,
    failing_init,
    ok_shutdown
);
#elif defined(TERMIN_ABI_TEST_SHUTDOWN_RETRY)
TERMIN_NATIVE_MODULE_DESCRIPTOR_V1(
    "abi_shutdown_retry",
    "1.0.0",
    "abi-shutdown-retry-test",
    TERMIN_NATIVE_MODULE_CAP_NONE,
    ok_init,
    retrying_shutdown
);
#endif
