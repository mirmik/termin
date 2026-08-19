#ifndef TERMIN_RUNTIME_GAME_APPLICATION_H
#define TERMIN_RUNTIME_GAME_APPLICATION_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <inspect/tc_runtime_type_registry.h>
#include <termin/runtime/termin_runtime_api.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TC_GAME_APPLICATION_FACET_ID "termin.runtime.game_application"
#define TC_GAME_APPLICATION_FACET_ABI_VERSION 1u
#define TC_GAME_APPLICATION_OPS_ABI_VERSION 1u
#define TC_GAME_APPLICATION_ROOT_TYPE "GameApplication"
#define TC_GAME_APPLICATION_ROOT_OWNER "termin-runtime"

typedef struct tc_game_application_instance tc_game_application_instance;

typedef struct tc_game_application_error_v1 {
    uint32_t struct_size;
    char* message;
    size_t message_capacity;
} tc_game_application_error_v1;

static inline void tc_game_application_set_error(tc_game_application_error_v1* error, const char* message) {
    if (!error || error->struct_size < sizeof(tc_game_application_error_v1) || !error->message ||
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

typedef struct tc_game_application_factory_request_v1 {
    uint32_t struct_size;
    tc_game_application_error_v1* error;
} tc_game_application_factory_request_v1;

typedef bool (*tc_game_application_lifecycle_fn)(void* object, tc_game_application_error_v1* error);
typedef void (*tc_game_application_destroy_fn)(void* object);

typedef struct tc_game_application_ops_v1 {
    uint32_t struct_size;
    uint32_t abi_version;
    tc_game_application_lifecycle_fn start;
    tc_game_application_lifecycle_fn stop;
} tc_game_application_ops_v1;

// The factory transfers object ownership to the caller only when it returns
// true. destroy is deliberately stored outside the versioned ops table so the
// caller can release an object whose lifecycle table fails validation.
typedef struct tc_game_application_factory_result_v1 {
    uint32_t struct_size;
    void* object;
    tc_game_application_destroy_fn destroy;
    const tc_game_application_ops_v1* ops;
} tc_game_application_factory_result_v1;

typedef enum tc_game_application_state {
    TC_GAME_APPLICATION_STATE_CREATED = 0,
    TC_GAME_APPLICATION_STATE_STARTING = 1,
    TC_GAME_APPLICATION_STATE_STARTED = 2,
    TC_GAME_APPLICATION_STATE_START_FAILED = 3,
    TC_GAME_APPLICATION_STATE_STOPPING = 4,
    TC_GAME_APPLICATION_STATE_STOPPED = 5
} tc_game_application_state;

// Registers the abstract engine-owned GameApplication root type. This is an
// explicit, idempotent runtime bootstrap step; it does not rely on static
// initialization and can be called again after the common registry is reset.
TERMIN_RUNTIME_API bool tc_game_application_registry_init(void);

// Consumes factory on every path, matching tc_runtime_owned_factory ownership
// semantics. Concrete types require a factory; abstract types must not create
// instances.
TERMIN_RUNTIME_API bool tc_game_application_type_descriptor_add_facet(tc_runtime_type_descriptor* descriptor,
                                                                      tc_runtime_owned_factory* factory,
                                                                      bool is_abstract);

TERMIN_RUNTIME_API bool tc_game_application_type_is_registered(const char* type_name);
TERMIN_RUNTIME_API bool tc_game_application_type_is_abstract(const char* type_name);
TERMIN_RUNTIME_API size_t tc_game_application_type_count(void);
TERMIN_RUNTIME_API const char* tc_game_application_type_at(size_t index);

TERMIN_RUNTIME_API tc_game_application_instance* tc_game_application_instance_create(
    const char* type_name, tc_game_application_error_v1* error);
TERMIN_RUNTIME_API bool tc_game_application_instance_start(tc_game_application_instance* instance,
                                                           tc_game_application_error_v1* error);
TERMIN_RUNTIME_API bool tc_game_application_instance_stop(tc_game_application_instance* instance,
                                                          tc_game_application_error_v1* error);

// Clears *instance after releasing it. If start was attempted and stop was not,
// destroy performs one best-effort stop before destroying the language object
// and unlinking its runtime type record.
TERMIN_RUNTIME_API bool tc_game_application_instance_destroy(tc_game_application_instance** instance,
                                                             tc_game_application_error_v1* error);

TERMIN_RUNTIME_API tc_game_application_state
tc_game_application_instance_state(const tc_game_application_instance* instance);
TERMIN_RUNTIME_API const char* tc_game_application_instance_type_name(const tc_game_application_instance* instance);

#ifdef __cplusplus
}
#endif

#endif // TERMIN_RUNTIME_GAME_APPLICATION_H
