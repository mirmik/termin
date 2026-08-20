#include <termin/engine/world_controller.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <tcbase/tc_log.h>

typedef struct tc_world_controller_facet_payload {
    tc_runtime_owned_factory factory;
    bool is_abstract;
} tc_world_controller_facet_payload;

struct tc_world_controller_instance {
    void* object;
    tc_world_controller_destroy_fn destroy;
    const tc_world_controller_ops_v1* ops;
    tc_world_context* context;
    tc_runtime_type_instance_link type_link;
    tc_world_controller_state state;
};

static tc_world_controller_facet_payload* world_controller_facet(const char* type_name) {
    if (!type_name) {
        return NULL;
    }
    return (tc_world_controller_facet_payload*)tc_runtime_type_registry_get_facet(type_name,
                                                                                  TC_WORLD_CONTROLLER_FACET_ID);
}

static bool error_buffer_is_valid(const tc_world_controller_error_v1* error) {
    return error && error->struct_size >= sizeof(tc_world_controller_error_v1) && error->message &&
           error->message_capacity > 0;
}

static void clear_error(tc_world_controller_error_v1* error) {
    if (error_buffer_is_valid(error)) {
        error->message[0] = '\0';
    }
}

static const char* error_text(const tc_world_controller_error_v1* error, const char* fallback) {
    if (error_buffer_is_valid(error) && error->message[0]) {
        return error->message;
    }
    return fallback;
}

static bool fail_with_message(tc_world_controller_error_v1* error, const char* message) {
    tc_world_controller_set_error(error, message);
    tc_log(TC_LOG_ERROR, "[WorldController] %s", message ? message : "operation failed");
    return false;
}

static bool fail_for_type(tc_world_controller_error_v1* error, const char* type_name, const char* message) {
    char buffer[512] = {0};
    snprintf(buffer,
             sizeof(buffer),
             "type '%s': %s",
             type_name && type_name[0] ? type_name : "<unknown>",
             message ? message : "operation failed");
    return fail_with_message(error, buffer);
}

static void destroy_world_controller_facet(void* payload) {
    tc_world_controller_facet_payload* facet = (tc_world_controller_facet_payload*)payload;
    if (!facet) {
        return;
    }
    tc_runtime_owned_factory_reset(&facet->factory);
    free(facet);
}

static bool prepare_world_controller_facet_unload(const char* type_name, void* payload, void* context) {
    (void)payload;
    (void)context;

    const size_t instance_count = tc_runtime_type_registry_instance_count(type_name);
    if (instance_count == 0) {
        return true;
    }

    tc_log(TC_LOG_ERROR,
           "[WorldController] refusing to unload type '%s' while %zu controller instance(s) are live; stop and "
           "destroy the controller instances first",
           type_name ? type_name : "<unknown>",
           instance_count);
    return false;
}

bool tc_world_controller_type_descriptor_add_facet(tc_runtime_type_descriptor* descriptor,
                                                   tc_runtime_owned_factory* factory,
                                                   bool is_abstract) {
    tc_runtime_owned_factory owned_factory = tc_runtime_owned_factory_take(factory);
    if (!descriptor) {
        tc_log(TC_LOG_ERROR, "[WorldController] cannot attach a facet to a null runtime type descriptor");
        tc_runtime_owned_factory_reset(&owned_factory);
        return false;
    }
    if (is_abstract && owned_factory.create) {
        tc_log(TC_LOG_ERROR, "[WorldController] abstract types must not provide a factory");
        tc_runtime_owned_factory_reset(&owned_factory);
        return false;
    }
    if (!is_abstract && !owned_factory.create) {
        tc_log(TC_LOG_ERROR, "[WorldController] concrete types require a factory");
        tc_runtime_owned_factory_reset(&owned_factory);
        return false;
    }

    tc_world_controller_facet_payload* facet =
        (tc_world_controller_facet_payload*)calloc(1, sizeof(tc_world_controller_facet_payload));
    if (!facet) {
        tc_log(TC_LOG_ERROR, "[WorldController] failed to allocate a staged type facet");
        tc_runtime_owned_factory_reset(&owned_factory);
        return false;
    }
    facet->factory = tc_runtime_owned_factory_take(&owned_factory);
    facet->is_abstract = is_abstract;

    return tc_runtime_type_descriptor_add_facet(descriptor,
                                                TC_WORLD_CONTROLLER_FACET_ID,
                                                facet,
                                                destroy_world_controller_facet,
                                                prepare_world_controller_facet_unload,
                                                TC_WORLD_CONTROLLER_FACET_ABI_VERSION);
}

bool tc_world_controller_registry_init(void) {
    if (tc_runtime_type_registry_has_type(TC_WORLD_CONTROLLER_ROOT_TYPE)) {
        const char* owner = tc_runtime_type_registry_get_owner(TC_WORLD_CONTROLLER_ROOT_TYPE);
        tc_world_controller_facet_payload* facet = world_controller_facet(TC_WORLD_CONTROLLER_ROOT_TYPE);
        if (owner && strcmp(owner, TC_WORLD_CONTROLLER_ROOT_OWNER) == 0 && facet && facet->is_abstract) {
            return true;
        }

        tc_log(TC_LOG_ERROR,
               "[WorldController] root type '%s' is already registered with an incompatible owner or facet",
               TC_WORLD_CONTROLLER_ROOT_TYPE);
        return false;
    }

    tc_runtime_type_descriptor* descriptor =
        tc_runtime_type_descriptor_create(TC_WORLD_CONTROLLER_ROOT_TYPE, TC_WORLD_CONTROLLER_ROOT_OWNER, NULL);
    if (!descriptor) {
        tc_log(TC_LOG_ERROR, "[WorldController] failed to create the abstract root descriptor");
        return false;
    }

    tc_runtime_owned_factory empty_factory = {0};
    if (!tc_world_controller_type_descriptor_add_facet(descriptor, &empty_factory, true)) {
        tc_runtime_type_descriptor_destroy(descriptor);
        return false;
    }
    if (!tc_runtime_type_registry_commit_descriptor(descriptor)) {
        tc_log(TC_LOG_ERROR, "[WorldController] failed to publish the abstract root type");
        return false;
    }
    return true;
}

bool tc_world_controller_type_is_registered(const char* type_name) {
    return world_controller_facet(type_name) != NULL;
}

bool tc_world_controller_type_is_abstract(const char* type_name) {
    tc_world_controller_facet_payload* facet = world_controller_facet(type_name);
    return facet ? facet->is_abstract : false;
}

size_t tc_world_controller_type_count(void) {
    return tc_runtime_type_registry_types_with_facet_count(TC_WORLD_CONTROLLER_FACET_ID);
}

const char* tc_world_controller_type_at(size_t index) {
    return tc_runtime_type_registry_type_with_facet_at(TC_WORLD_CONTROLLER_FACET_ID, index);
}

static void destroy_factory_result(tc_world_controller_factory_result_v1* result) {
    if (!result || !result->object || !result->destroy) {
        return;
    }
    result->destroy(result->object);
    result->object = NULL;
}

static bool factory_result_is_valid(const tc_world_controller_factory_result_v1* result,
                                    tc_world_controller_error_v1* error,
                                    const char* type_name) {
    if (!result || result->struct_size < sizeof(tc_world_controller_factory_result_v1)) {
        return fail_for_type(error, type_name, "factory returned an incompatible result structure");
    }
    if (!result->object) {
        return fail_for_type(error, type_name, "factory returned no controller object");
    }
    if (!result->destroy) {
        return fail_for_type(error, type_name, "factory returned no object destroy callback");
    }
    if (!result->ops || result->ops->struct_size < sizeof(tc_world_controller_ops_v1) ||
        result->ops->abi_version != TC_WORLD_CONTROLLER_OPS_ABI_VERSION) {
        return fail_for_type(error, type_name, "factory returned incompatible lifecycle ops");
    }
    if (!result->ops->start || !result->ops->stop) {
        return fail_for_type(error, type_name, "factory lifecycle ops require both start and stop callbacks");
    }
    return true;
}

static tc_world_controller_instance* create_world_controller_instance(
    const char* type_name,
    const char* expected_owner,
    tc_world_controller_error_v1* error) {
    clear_error(error);
    if (!type_name || !type_name[0]) {
        fail_with_message(error, "controller type name must be non-empty");
        return NULL;
    }
    if (expected_owner && !expected_owner[0]) {
        fail_with_message(error, "expected controller owner must be non-empty");
        return NULL;
    }
    tc_world_controller_facet_payload* facet = world_controller_facet(type_name);
    if (!facet) {
        fail_for_type(error, type_name, "runtime type has no WorldController facet");
        return NULL;
    }
    if (expected_owner) {
        const char* actual_owner = tc_runtime_type_registry_get_owner(type_name);
        if (!actual_owner || strcmp(actual_owner, expected_owner) != 0) {
            char message[512] = {0};
            snprintf(message,
                     sizeof(message),
                     "runtime type owner is '%s', expected '%s'",
                     actual_owner && actual_owner[0] ? actual_owner : "<unknown>",
                     expected_owner);
            fail_for_type(error, type_name, message);
            return NULL;
        }
    }
    if (facet->is_abstract) {
        fail_for_type(error, type_name, "abstract controller types cannot be instantiated");
        return NULL;
    }
    if (!facet->factory.create) {
        fail_for_type(error, type_name, "concrete controller type has no factory");
        return NULL;
    }

    tc_world_controller_instance* instance =
        (tc_world_controller_instance*)calloc(1, sizeof(tc_world_controller_instance));
    if (!instance) {
        fail_for_type(error, type_name, "failed to allocate the engine-owned instance wrapper");
        return NULL;
    }
    instance->state = TC_WORLD_CONTROLLER_STATE_CREATED;
    tc_runtime_type_instance_link_init(&instance->type_link);

    tc_world_controller_factory_request_v1 request = {sizeof(tc_world_controller_factory_request_v1), error};
    tc_world_controller_factory_result_v1 result = {sizeof(tc_world_controller_factory_result_v1), NULL, NULL, NULL};
    if (!tc_runtime_owned_factory_invoke(&facet->factory, &request, &result)) {
        free(instance);
        if (!error_text(error, NULL)) {
            fail_for_type(error, type_name, "factory creation failed");
        } else {
            tc_log(TC_LOG_ERROR, "[WorldController] type '%s': %s", type_name, error_text(error, "factory failed"));
        }
        return NULL;
    }
    if (!factory_result_is_valid(&result, error, type_name)) {
        destroy_factory_result(&result);
        free(instance);
        return NULL;
    }

    instance->object = result.object;
    instance->destroy = result.destroy;
    instance->ops = result.ops;
    if (!tc_runtime_type_registry_link_instance(type_name, &instance->type_link, instance)) {
        fail_for_type(error, type_name, "failed to link the live instance to its runtime type");
        instance->destroy(instance->object);
        free(instance);
        return NULL;
    }

    return instance;
}

tc_world_controller_instance* tc_world_controller_instance_create(
    const char* type_name,
    tc_world_controller_error_v1* error) {
    return create_world_controller_instance(type_name, NULL, error);
}

tc_world_controller_instance* tc_world_controller_instance_create_for_owner(
    const char* type_name,
    const char* expected_owner,
    tc_world_controller_error_v1* error) {
    return create_world_controller_instance(type_name, expected_owner, error);
}

bool tc_world_controller_instance_start(tc_world_controller_instance* instance,
                                        tc_world_context* context,
                                        tc_world_controller_error_v1* error) {
    clear_error(error);
    if (!instance) {
        return fail_with_message(error, "cannot start a null controller instance");
    }
    if (!context) {
        return fail_for_type(error, instance->type_link.type_name, "start requires a non-null WorldContext");
    }
    if (instance->state != TC_WORLD_CONTROLLER_STATE_CREATED) {
        return fail_for_type(
            error, instance->type_link.type_name, "start is valid exactly once from the CREATED state");
    }

    instance->state = TC_WORLD_CONTROLLER_STATE_STARTING;
    instance->context = context;
    const bool started = instance->ops->start(instance->object, context, error);
    if (!started) {
        instance->state = TC_WORLD_CONTROLLER_STATE_START_FAILED;
        if (!error_text(error, NULL)) {
            tc_world_controller_set_error(error, "controller start callback failed");
        }
        tc_log(TC_LOG_ERROR,
               "[WorldController] type '%s' failed to start: %s",
               instance->type_link.type_name ? instance->type_link.type_name : "<unknown>",
               error_text(error, "controller start callback failed"));
        return false;
    }

    instance->state = TC_WORLD_CONTROLLER_STATE_STARTED;
    clear_error(error);
    return true;
}

bool tc_world_controller_instance_stop(tc_world_controller_instance* instance, tc_world_controller_error_v1* error) {
    clear_error(error);
    if (!instance) {
        return fail_with_message(error, "cannot stop a null controller instance");
    }
    if (instance->state != TC_WORLD_CONTROLLER_STATE_STARTED &&
        instance->state != TC_WORLD_CONTROLLER_STATE_START_FAILED) {
        return fail_for_type(error, instance->type_link.type_name, "stop is valid exactly once after a start attempt");
    }

    instance->state = TC_WORLD_CONTROLLER_STATE_STOPPING;
    const bool stopped = instance->ops->stop(instance->object, instance->context, error);
    instance->state = TC_WORLD_CONTROLLER_STATE_STOPPED;
    if (!stopped) {
        if (!error_text(error, NULL)) {
            tc_world_controller_set_error(error, "controller stop callback failed");
        }
        tc_log(TC_LOG_ERROR,
               "[WorldController] type '%s' failed to stop: %s",
               instance->type_link.type_name ? instance->type_link.type_name : "<unknown>",
               error_text(error, "controller stop callback failed"));
        return false;
    }

    clear_error(error);
    return true;
}

bool tc_world_controller_instance_destroy(tc_world_controller_instance** instance_ptr,
                                          tc_world_controller_error_v1* error) {
    clear_error(error);
    if (!instance_ptr) {
        return fail_with_message(error, "controller destroy requires a non-null instance slot");
    }
    tc_world_controller_instance* instance = *instance_ptr;
    if (!instance) {
        return true;
    }
    if (instance->state == TC_WORLD_CONTROLLER_STATE_STARTING ||
        instance->state == TC_WORLD_CONTROLLER_STATE_STOPPING) {
        return fail_for_type(
            error, instance->type_link.type_name, "cannot destroy a controller from inside a lifecycle callback");
    }

    bool stopped_cleanly = true;
    if (instance->state == TC_WORLD_CONTROLLER_STATE_STARTED ||
        instance->state == TC_WORLD_CONTROLLER_STATE_START_FAILED) {
        stopped_cleanly = tc_world_controller_instance_stop(instance, error);
    }

    instance->destroy(instance->object);
    instance->object = NULL;
    tc_runtime_type_registry_unlink_instance(&instance->type_link);
    free(instance);
    *instance_ptr = NULL;
    return stopped_cleanly;
}

tc_world_controller_state tc_world_controller_instance_state(const tc_world_controller_instance* instance) {
    return instance ? instance->state : TC_WORLD_CONTROLLER_STATE_STOPPED;
}

const char* tc_world_controller_instance_type_name(const tc_world_controller_instance* instance) {
    return instance ? instance->type_link.type_name : NULL;
}

void* tc_world_controller_instance_object(const tc_world_controller_instance* instance) {
    return instance ? instance->object : NULL;
}
