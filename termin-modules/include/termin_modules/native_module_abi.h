#ifndef TERMIN_MODULES_NATIVE_MODULE_ABI_H
#define TERMIN_MODULES_NATIVE_MODULE_ABI_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <tcbase/tc_version.h>

#if defined(__cplusplus) && defined(__has_include)
#  if __has_include(<bits/c++config.h>)
#    include <bits/c++config.h>
#  endif
#endif

#if defined(_WIN32)
#  define TERMIN_NATIVE_MODULE_EXPORT __declspec(dllexport)
#else
#  define TERMIN_NATIVE_MODULE_EXPORT __attribute__((visibility("default")))
#endif

#if defined(__cplusplus)
#  define TERMIN_NATIVE_MODULE_EXTERN_C extern "C"
#else
#  define TERMIN_NATIVE_MODULE_EXTERN_C extern
#endif

#define TERMIN_NATIVE_MODULE_ABI_VERSION 1u
#define TERMIN_NATIVE_HOST_ABI_VERSION 1u
#define TERMIN_NATIVE_MODULE_DESCRIPTOR_SYMBOL "termin_module_descriptor_v1"

#define TERMIN_MODULE_STRINGIFY_IMPL(value) #value
#define TERMIN_MODULE_STRINGIFY(value) TERMIN_MODULE_STRINGIFY_IMPL(value)

#if defined(_MSC_VER)
#  define TERMIN_MODULE_COMPILER_FAMILY 3u
#  define TERMIN_MODULE_COMPILER_VERSION ((uint32_t)(_MSC_VER))
#elif defined(__clang__)
#  define TERMIN_MODULE_COMPILER_FAMILY 2u
#  define TERMIN_MODULE_COMPILER_VERSION \
    ((uint32_t)(__clang_major__ * 10000u + __clang_minor__ * 100u + __clang_patchlevel__))
#elif defined(__GNUC__)
#  define TERMIN_MODULE_COMPILER_FAMILY 1u
#  define TERMIN_MODULE_COMPILER_VERSION \
    ((uint32_t)(__GNUC__ * 10000u + __GNUC_MINOR__ * 100u + __GNUC_PATCHLEVEL__))
#else
#  define TERMIN_MODULE_COMPILER_FAMILY 0u
#  define TERMIN_MODULE_COMPILER_VERSION 0u
#endif

#if defined(_GLIBCXX_USE_CXX11_ABI)
#  define TERMIN_MODULE_CXX_ABI_FLAGS ((uint32_t)(_GLIBCXX_USE_CXX11_ABI & 1u))
#elif defined(_ITERATOR_DEBUG_LEVEL)
#  define TERMIN_MODULE_CXX_ABI_FLAGS ((uint32_t)(_ITERATOR_DEBUG_LEVEL))
#else
#  define TERMIN_MODULE_CXX_ABI_FLAGS 0u
#endif

enum termin_native_module_capability {
    TERMIN_NATIVE_MODULE_CAP_NONE = 0,
    TERMIN_NATIVE_MODULE_CAP_COMPONENTS = 1ull << 0,
    TERMIN_NATIVE_MODULE_CAP_FRAME_PASSES = 1ull << 1,
    TERMIN_NATIVE_MODULE_CAP_INSPECT_TYPES = 1ull << 2
};

enum termin_native_module_log_level {
    TERMIN_NATIVE_MODULE_LOG_DEBUG = 0,
    TERMIN_NATIVE_MODULE_LOG_INFO = 1,
    TERMIN_NATIVE_MODULE_LOG_WARN = 2,
    TERMIN_NATIVE_MODULE_LOG_ERROR = 3
};

typedef struct termin_native_module_error {
    uint32_t struct_size;
    char* message;
    size_t message_capacity;
} termin_native_module_error;

static inline void termin_native_module_set_error(
    termin_native_module_error* error,
    const char* message
) {
    if (!error || error->struct_size < sizeof(termin_native_module_error) ||
        !error->message || error->message_capacity == 0) return;
    const char* source = message ? message : "";
    size_t length = strlen(source);
    if (length >= error->message_capacity) length = error->message_capacity - 1;
    memcpy(error->message, source, length);
    error->message[length] = '\0';
}

typedef void (*termin_native_module_log_fn)(
    void* host_context,
    int level,
    const char* message
);

typedef struct termin_native_module_host_v1 {
    uint32_t struct_size;
    uint32_t host_abi_version;
    uint32_t sdk_abi_version;
    uint32_t sdk_version;
    uint32_t compiler_family;
    uint32_t compiler_version;
    uint32_t cxx_abi_flags;
    uint32_t pointer_size;
    const char* module_id;
    void* host_context;
    termin_native_module_log_fn log;
} termin_native_module_host_v1;

typedef int32_t (*termin_native_module_init_v1_fn)(
    const termin_native_module_host_v1* host,
    termin_native_module_error* error
);

typedef int32_t (*termin_native_module_shutdown_v1_fn)(
    const termin_native_module_host_v1* host,
    termin_native_module_error* error
);

typedef struct termin_native_module_descriptor_v1_data {
    uint32_t struct_size;
    uint32_t module_abi_version;
    uint32_t required_host_abi_version;
    uint32_t required_sdk_abi_version;
    uint32_t sdk_version;
    uint32_t compiler_family;
    uint32_t compiler_version;
    uint32_t cxx_abi_flags;
    uint32_t pointer_size;
    const char* module_id;
    const char* module_version;
    const char* build_id;
    uint64_t capabilities;
    termin_native_module_init_v1_fn init;
    termin_native_module_shutdown_v1_fn shutdown;
} termin_native_module_descriptor_v1_data;

#define TERMIN_NATIVE_MODULE_DESCRIPTOR_V1(                                 \
    module_id_value, module_version_value, build_id_value, capabilities_value, \
    init_value, shutdown_value)                                              \
    TERMIN_NATIVE_MODULE_EXTERN_C TERMIN_NATIVE_MODULE_EXPORT const          \
        termin_native_module_descriptor_v1_data termin_module_descriptor_v1 = { \
            sizeof(termin_native_module_descriptor_v1_data),                 \
            TERMIN_NATIVE_MODULE_ABI_VERSION,                                \
            TERMIN_NATIVE_HOST_ABI_VERSION,                                  \
            TERMIN_NATIVE_MODULE_ABI_VERSION,                                \
            TC_VERSION,                                                      \
            TERMIN_MODULE_COMPILER_FAMILY,                                   \
            TERMIN_MODULE_COMPILER_VERSION,                                  \
            TERMIN_MODULE_CXX_ABI_FLAGS,                                     \
            (uint32_t)sizeof(void*),                                          \
            module_id_value,                                                 \
            module_version_value,                                            \
            build_id_value,                                                  \
            (uint64_t)(capabilities_value),                                  \
            init_value,                                                      \
            shutdown_value                                                   \
        }

#endif
