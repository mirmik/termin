#include "termin_modules/native_module_validation.hpp"

#include <cstddef>
#include <sstream>

namespace termin_modules {
namespace {

NativeModuleValidationResult incompatible(std::string error) {
    return {false, std::move(error)};
}

} // namespace

termin_native_module_host_v1 make_native_module_host_v1(
    const char* module_id,
    void* host_context
) {
    return {
        sizeof(termin_native_module_host_v1),
        TERMIN_NATIVE_HOST_ABI_VERSION,
        TERMIN_NATIVE_MODULE_ABI_VERSION,
        TC_VERSION,
        TERMIN_MODULE_COMPILER_FAMILY,
        TERMIN_MODULE_COMPILER_VERSION,
        TERMIN_MODULE_CXX_ABI_FLAGS,
        static_cast<uint32_t>(sizeof(void*)),
        module_id,
        host_context,
        nullptr
    };
}

NativeModuleValidationResult validate_native_module_descriptor_v1(
    const termin_native_module_descriptor_v1_data* descriptor,
    const std::string& expected_module_id
) {
    if (!descriptor) return incompatible("missing native module descriptor");
    if (descriptor->struct_size < sizeof(termin_native_module_descriptor_v1_data)) {
        return incompatible("native module descriptor is smaller than ABI v1");
    }
    if (descriptor->module_abi_version != TERMIN_NATIVE_MODULE_ABI_VERSION) {
        return incompatible(
            "native module ABI mismatch: module=" +
            std::to_string(descriptor->module_abi_version) + " host=" +
            std::to_string(TERMIN_NATIVE_MODULE_ABI_VERSION)
        );
    }
    if (descriptor->required_host_abi_version != TERMIN_NATIVE_HOST_ABI_VERSION) {
        return incompatible("native host API version mismatch");
    }
    if (descriptor->required_sdk_abi_version != TERMIN_NATIVE_MODULE_ABI_VERSION) {
        return incompatible("native SDK ABI version mismatch");
    }
    if (descriptor->sdk_version != TC_VERSION) {
        return incompatible(
            "native SDK build mismatch: module=" +
            std::to_string(descriptor->sdk_version) + " host=" +
            std::to_string(TC_VERSION)
        );
    }
    if (descriptor->compiler_family != TERMIN_MODULE_COMPILER_FAMILY ||
        descriptor->compiler_version != TERMIN_MODULE_COMPILER_VERSION ||
        descriptor->cxx_abi_flags != TERMIN_MODULE_CXX_ABI_FLAGS ||
        descriptor->pointer_size != sizeof(void*)) {
        std::ostringstream message;
        message << "native compiler/runtime ABI mismatch: module="
                << descriptor->compiler_family << ':' << descriptor->compiler_version
                << ':' << descriptor->cxx_abi_flags << ':' << descriptor->pointer_size
                << " host=" << TERMIN_MODULE_COMPILER_FAMILY << ':'
                << TERMIN_MODULE_COMPILER_VERSION << ':' << TERMIN_MODULE_CXX_ABI_FLAGS
                << ':' << sizeof(void*);
        return incompatible(message.str());
    }
    if (!descriptor->module_id || !descriptor->module_id[0]) {
        return incompatible("native module descriptor has an empty module_id");
    }
    if (!expected_module_id.empty() && expected_module_id != descriptor->module_id) {
        return incompatible(
            "native module id mismatch: descriptor='" +
            std::string(descriptor->module_id) + "' project='" + expected_module_id + "'"
        );
    }
    if (!descriptor->module_version || !descriptor->module_version[0]) {
        return incompatible("native module descriptor has an empty module_version");
    }
    if (!descriptor->build_id || !descriptor->build_id[0]) {
        return incompatible("native module descriptor has an empty build_id");
    }
    if (!descriptor->init) return incompatible("native module descriptor has no init function");
    if (!descriptor->shutdown) return incompatible("native module descriptor has no shutdown function");
    return {true, {}};
}

} // namespace termin_modules
