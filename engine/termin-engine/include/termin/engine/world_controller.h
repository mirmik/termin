#ifndef TERMIN_ENGINE_WORLD_CONTROLLER_H
#define TERMIN_ENGINE_WORLD_CONTROLLER_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <inspect/tc_runtime_type_registry.h>
#include <termin/engine/termin_engine_api.hpp>

#ifdef __cplusplus
extern "C" {
#endif

#define TC_WORLD_CONTROLLER_FACET_ID "termin.engine.world_controller"
#define TC_WORLD_CONTROLLER_FACET_ABI_VERSION 1u
#define TC_WORLD_CONTROLLER_OPS_ABI_VERSION 1u
#define TC_WORLD_CONTROLLER_ROOT_TYPE "WorldController"
#define TC_WORLD_CONTROLLER_ROOT_OWNER "termin-engine"

typedef struct tc_world_controller_instance tc_world_controller_instance;
typedef struct tc_world_context tc_world_context;

typedef struct tc_world_controller_error_v1 {
    uint32_t struct_size;
    char* message;
    size_t message_capacity;
} tc_world_controller_error_v1;

static inline void tc_world_controller_set_error(tc_world_controller_error_v1* error, const char* message) {
    if (!error || error->struct_size < sizeof(tc_world_controller_error_v1) || !error->message ||
        error->message_capacity == 0) {
        return;
    }

    const char* source = message ? message : "";
    size_t length = strlen(source);
    if (length >= error->message_capacity) {
        length = error->message_capacity - 1;
    }
    memcpy(error->message, source, length);
    error->message[length] = '\0';
}

typedef struct tc_world_controller_factory_request_v1 {
    uint32_t struct_size;
    tc_world_controller_error_v1* error;
} tc_world_controller_factory_request_v1;

typedef bool (*tc_world_controller_lifecycle_fn)(void* object,
                                                 tc_world_context* context,
                                                 tc_world_controller_error_v1* error);
typedef void (*tc_world_controller_destroy_fn)(void* object);

typedef struct tc_world_controller_ops_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    tc_world_controller_lifecycle_fn start;
    tc_world_controller_lifecycle_fn stop;
} tc_world_controller_ops_v1;

// The factory transfers object ownership to the caller only when it returns
// true. destroy is deliberately stored outside the versioned ops table so the
// caller can release an object whose lifecycle table fails validation.
typedef struct tc_world_controller_factory_result_v1 {
    uint32_t struct_size;
    void* object;
    tc_world_controller_destroy_fn destroy;
    const tc_world_controller_ops_v1* ops;
} tc_world_controller_factory_result_v1;

typedef enum tc_world_controller_state {
    TC_WORLD_CONTROLLER_STATE_CREATED = 0,
    TC_WORLD_CONTROLLER_STATE_STARTING = 1,
    TC_WORLD_CONTROLLER_STATE_STARTED = 2,
    TC_WORLD_CONTROLLER_STATE_START_FAILED = 3,
    TC_WORLD_CONTROLLER_STATE_STOPPING = 4,
    TC_WORLD_CONTROLLER_STATE_STOPPED = 5
} tc_world_controller_state;

// Registers the abstract engine-owned WorldController root type. This is an
// explicit, idempotent runtime bootstrap step; it does not rely on static
// initialization and can be called again after the common registry is reset.
TERMIN_ENGINE_API bool tc_world_controller_registry_init(void);

// Consumes factory on every path, matching tc_runtime_owned_factory ownership
// semantics. Concrete types require a factory; abstract types must not create
// instances.
TERMIN_ENGINE_API bool tc_world_controller_type_descriptor_add_facet(tc_runtime_type_descriptor* descriptor,
                                                                      tc_runtime_owned_factory* factory,
                                                                      bool is_abstract);

TERMIN_ENGINE_API bool tc_world_controller_type_is_registered(const char* type_name);
TERMIN_ENGINE_API bool tc_world_controller_type_is_abstract(const char* type_name);
TERMIN_ENGINE_API size_t tc_world_controller_type_count(void);
TERMIN_ENGINE_API const char* tc_world_controller_type_at(size_t index);

TERMIN_ENGINE_API tc_world_controller_instance* tc_world_controller_instance_create(
    const char* type_name, tc_world_controller_error_v1* error);
TERMIN_ENGINE_API bool tc_world_controller_instance_start(tc_world_controller_instance* instance,
                                                           tc_world_context* context,
                                                           tc_world_controller_error_v1* error);
TERMIN_ENGINE_API bool tc_world_controller_instance_stop(tc_world_controller_instance* instance,
                                                          tc_world_controller_error_v1* error);

// Clears *instance after releasing it. If start was attempted and stop was not,
// destroy performs one best-effort stop before destroying the language object
// and unlinking its runtime type record.
TERMIN_ENGINE_API bool tc_world_controller_instance_destroy(tc_world_controller_instance** instance,
                                                             tc_world_controller_error_v1* error);

TERMIN_ENGINE_API tc_world_controller_state
tc_world_controller_instance_state(const tc_world_controller_instance* instance);
TERMIN_ENGINE_API const char* tc_world_controller_instance_type_name(const tc_world_controller_instance* instance);

#ifdef __cplusplus
}
#endif

#endif // TERMIN_ENGINE_WORLD_CONTROLLER_H
