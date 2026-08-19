#include <termin/runtime/game_application.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <tcbase/tc_log.h>

typedef struct tc_game_application_facet_payload {
    tc_runtime_owned_factory factory;
    bool is_abstract;
} tc_game_application_facet_payload;

struct tc_game_application_instance {
    void* object;
    tc_game_application_destroy_fn destroy;
    const tc_game_application_ops_v1* ops;
    tc_game_application_context_v1 context;
    tc_runtime_type_instance_link type_link;
    tc_game_application_state state;
};

static tc_game_application_facet_payload* game_application_facet(const char* type_name) {
    if (!type_name) {
        return NULL;
    }
    return (tc_game_application_facet_payload*)tc_runtime_type_registry_get_facet(type_name,
                                                                                  TC_GAME_APPLICATION_FACET_ID);
}

static bool error_buffer_is_valid(const tc_game_application_error_v1* error) {
    return error && error->struct_size >= sizeof(tc_game_application_error_v1) && error->message &&
           error->message_capacity > 0;
}

static void clear_error(tc_game_application_error_v1* error) {
    if (error_buffer_is_valid(error)) {
        error->message[0] = '\0';
    }
}

static const char* error_text(const tc_game_application_error_v1* error, const char* fallback) {
    if (error_buffer_is_valid(error) && error->message[0]) {
        return error->message;
    }
    return fallback;
}

static bool fail_with_message(tc_game_application_error_v1* error, const char* message) {
    tc_game_application_set_error(error, message);
    tc_log(TC_LOG_ERROR, "[GameApplication] %s", message ? message : "operation failed");
    return false;
}

static bool fail_for_type(tc_game_application_error_v1* error, const char* type_name, const char* message) {
    char buffer[512] = {0};
    snprintf(buffer,
             sizeof(buffer),
             "type '%s': %s",
             type_name && type_name[0] ? type_name : "<unknown>",
             message ? message : "operation failed");
    return fail_with_message(error, buffer);
}

static void destroy_game_application_facet(void* payload) {
    tc_game_application_facet_payload* facet = (tc_game_application_facet_payload*)payload;
    if (!facet) {
        return;
    }
    tc_runtime_owned_factory_reset(&facet->factory);
    free(facet);
}

static bool prepare_game_application_facet_unload(const char* type_name, void* payload, void* context) {
    (void)payload;
    (void)context;

    const size_t instance_count = tc_runtime_type_registry_instance_count(type_name);
    if (instance_count == 0) {
        return true;
    }

    tc_log(TC_LOG_ERROR,
           "[GameApplication] refusing to unload type '%s' while %zu application instance(s) are live; stop and "
           "destroy the RuntimeSession first",
           type_name ? type_name : "<unknown>",
           instance_count);
    return false;
}

bool tc_game_application_type_descriptor_add_facet(tc_runtime_type_descriptor* descriptor,
                                                   tc_runtime_owned_factory* factory,
                                                   bool is_abstract) {
    tc_runtime_owned_factory owned_factory = tc_runtime_owned_factory_take(factory);
    if (!descriptor) {
        tc_log(TC_LOG_ERROR, "[GameApplication] cannot attach a facet to a null runtime type descriptor");
        tc_runtime_owned_factory_reset(&owned_factory);
        return false;
    }
    if (is_abstract && owned_factory.create) {
        tc_log(TC_LOG_ERROR, "[GameApplication] abstract types must not provide a factory");
        tc_runtime_owned_factory_reset(&owned_factory);
        return false;
    }
    if (!is_abstract && !owned_factory.create) {
        tc_log(TC_LOG_ERROR, "[GameApplication] concrete types require a factory");
        tc_runtime_owned_factory_reset(&owned_factory);
        return false;
    }

    tc_game_application_facet_payload* facet =
        (tc_game_application_facet_payload*)calloc(1, sizeof(tc_game_application_facet_payload));
    if (!facet) {
        tc_log(TC_LOG_ERROR, "[GameApplication] failed to allocate a staged type facet");
        tc_runtime_owned_factory_reset(&owned_factory);
        return false;
    }
    facet->factory = tc_runtime_owned_factory_take(&owned_factory);
    facet->is_abstract = is_abstract;

    return tc_runtime_type_descriptor_add_facet(descriptor,
                                                TC_GAME_APPLICATION_FACET_ID,
                                                facet,
                                                destroy_game_application_facet,
                                                prepare_game_application_facet_unload,
                                                TC_GAME_APPLICATION_FACET_ABI_VERSION);
}

bool tc_game_application_registry_init(void) {
    if (tc_runtime_type_registry_has_type(TC_GAME_APPLICATION_ROOT_TYPE)) {
        const char* owner = tc_runtime_type_registry_get_owner(TC_GAME_APPLICATION_ROOT_TYPE);
        tc_game_application_facet_payload* facet = game_application_facet(TC_GAME_APPLICATION_ROOT_TYPE);
        if (owner && strcmp(owner, TC_GAME_APPLICATION_ROOT_OWNER) == 0 && facet && facet->is_abstract) {
            return true;
        }

        tc_log(TC_LOG_ERROR,
               "[GameApplication] root type '%s' is already registered with an incompatible owner or facet",
               TC_GAME_APPLICATION_ROOT_TYPE);
        return false;
    }

    tc_runtime_type_descriptor* descriptor =
        tc_runtime_type_descriptor_create(TC_GAME_APPLICATION_ROOT_TYPE, TC_GAME_APPLICATION_ROOT_OWNER, NULL);
    if (!descriptor) {
        tc_log(TC_LOG_ERROR, "[GameApplication] failed to create the abstract root descriptor");
        return false;
    }

    tc_runtime_owned_factory empty_factory = {0};
    if (!tc_game_application_type_descriptor_add_facet(descriptor, &empty_factory, true)) {
        tc_runtime_type_descriptor_destroy(descriptor);
        return false;
    }
    if (!tc_runtime_type_registry_commit_descriptor(descriptor)) {
        tc_log(TC_LOG_ERROR, "[GameApplication] failed to publish the abstract root type");
        return false;
    }
    return true;
}

bool tc_game_application_type_is_registered(const char* type_name) {
    return game_application_facet(type_name) != NULL;
}

bool tc_game_application_type_is_abstract(const char* type_name) {
    tc_game_application_facet_payload* facet = game_application_facet(type_name);
    return facet ? facet->is_abstract : false;
}

size_t tc_game_application_type_count(void) {
    return tc_runtime_type_registry_types_with_facet_count(TC_GAME_APPLICATION_FACET_ID);
}

const char* tc_game_application_type_at(size_t index) {
    return tc_runtime_type_registry_type_with_facet_at(TC_GAME_APPLICATION_FACET_ID, index);
}

static void destroy_factory_result(tc_game_application_factory_result_v1* result) {
    if (!result || !result->object || !result->destroy) {
        return;
    }
    result->destroy(result->object);
    result->object = NULL;
}

static bool factory_result_is_valid(const tc_game_application_factory_result_v1* result,
                                    tc_game_application_error_v1* error,
                                    const char* type_name) {
    if (!result || result->struct_size < sizeof(tc_game_application_factory_result_v1)) {
        return fail_for_type(error, type_name, "factory returned an incompatible result structure");
    }
    if (!result->object) {
        return fail_for_type(error, type_name, "factory returned no application object");
    }
    if (!result->destroy) {
        return fail_for_type(error, type_name, "factory returned no object destroy callback");
    }
    if (!result->ops || result->ops->struct_size < sizeof(tc_game_application_ops_v1) ||
        result->ops->abi_version != TC_GAME_APPLICATION_OPS_ABI_VERSION) {
        return fail_for_type(error, type_name, "factory returned incompatible lifecycle ops");
    }
    if (!result->ops->start || !result->ops->stop) {
        return fail_for_type(error, type_name, "factory lifecycle ops require both start and stop callbacks");
    }
    return true;
}

tc_game_application_instance* tc_game_application_instance_create(const char* type_name,
                                                                  const tc_game_application_context_v1* context,
                                                                  tc_game_application_error_v1* error) {
    clear_error(error);
    if (!type_name || !type_name[0]) {
        fail_with_message(error, "application type name must be non-empty");
        return NULL;
    }
    if (!context || context->struct_size < sizeof(tc_game_application_context_v1) || !context->session) {
        fail_for_type(error, type_name, "creation requires a valid per-run RuntimeSession context");
        return NULL;
    }

    tc_game_application_facet_payload* facet = game_application_facet(type_name);
    if (!facet) {
        fail_for_type(error, type_name, "runtime type has no GameApplication facet");
        return NULL;
    }
    if (facet->is_abstract) {
        fail_for_type(error, type_name, "abstract application types cannot be instantiated");
        return NULL;
    }
    if (!facet->factory.create) {
        fail_for_type(error, type_name, "concrete application type has no factory");
        return NULL;
    }

    tc_game_application_instance* instance =
        (tc_game_application_instance*)calloc(1, sizeof(tc_game_application_instance));
    if (!instance) {
        fail_for_type(error, type_name, "failed to allocate the engine-owned instance wrapper");
        return NULL;
    }
    instance->context.struct_size = sizeof(tc_game_application_context_v1);
    instance->context.session = context->session;
    instance->state = TC_GAME_APPLICATION_STATE_CREATED;
    tc_runtime_type_instance_link_init(&instance->type_link);

    tc_game_application_factory_request_v1 request = {
        sizeof(tc_game_application_factory_request_v1), &instance->context, error};
    tc_game_application_factory_result_v1 result = {sizeof(tc_game_application_factory_result_v1), NULL, NULL, NULL};
    if (!tc_runtime_owned_factory_invoke(&facet->factory, &request, &result)) {
        free(instance);
        if (!error_text(error, NULL)) {
            fail_for_type(error, type_name, "factory creation failed");
        } else {
            tc_log(TC_LOG_ERROR, "[GameApplication] type '%s': %s", type_name, error_text(error, "factory failed"));
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

bool tc_game_application_instance_start(tc_game_application_instance* instance, tc_game_application_error_v1* error) {
    clear_error(error);
    if (!instance) {
        return fail_with_message(error, "cannot start a null application instance");
    }
    if (instance->state != TC_GAME_APPLICATION_STATE_CREATED) {
        return fail_for_type(
            error, instance->type_link.type_name, "start is valid exactly once from the CREATED state");
    }

    instance->state = TC_GAME_APPLICATION_STATE_STARTING;
    const bool started = instance->ops->start(instance->object, &instance->context, error);
    if (!started) {
        instance->state = TC_GAME_APPLICATION_STATE_START_FAILED;
        if (!error_text(error, NULL)) {
            tc_game_application_set_error(error, "application start callback failed");
        }
        tc_log(TC_LOG_ERROR,
               "[GameApplication] type '%s' failed to start: %s",
               instance->type_link.type_name ? instance->type_link.type_name : "<unknown>",
               error_text(error, "application start callback failed"));
        return false;
    }

    instance->state = TC_GAME_APPLICATION_STATE_STARTED;
    clear_error(error);
    return true;
}

bool tc_game_application_instance_stop(tc_game_application_instance* instance, tc_game_application_error_v1* error) {
    clear_error(error);
    if (!instance) {
        return fail_with_message(error, "cannot stop a null application instance");
    }
    if (instance->state != TC_GAME_APPLICATION_STATE_STARTED &&
        instance->state != TC_GAME_APPLICATION_STATE_START_FAILED) {
        return fail_for_type(error, instance->type_link.type_name, "stop is valid exactly once after a start attempt");
    }

    instance->state = TC_GAME_APPLICATION_STATE_STOPPING;
    const bool stopped = instance->ops->stop(instance->object, &instance->context, error);
    instance->state = TC_GAME_APPLICATION_STATE_STOPPED;
    if (!stopped) {
        if (!error_text(error, NULL)) {
            tc_game_application_set_error(error, "application stop callback failed");
        }
        tc_log(TC_LOG_ERROR,
               "[GameApplication] type '%s' failed to stop: %s",
               instance->type_link.type_name ? instance->type_link.type_name : "<unknown>",
               error_text(error, "application stop callback failed"));
        return false;
    }

    clear_error(error);
    return true;
}

bool tc_game_application_instance_destroy(tc_game_application_instance** instance_ptr,
                                          tc_game_application_error_v1* error) {
    clear_error(error);
    if (!instance_ptr) {
        return fail_with_message(error, "application destroy requires a non-null instance slot");
    }
    tc_game_application_instance* instance = *instance_ptr;
    if (!instance) {
        return true;
    }
    if (instance->state == TC_GAME_APPLICATION_STATE_STARTING ||
        instance->state == TC_GAME_APPLICATION_STATE_STOPPING) {
        return fail_for_type(
            error, instance->type_link.type_name, "cannot destroy an application from inside a lifecycle callback");
    }

    bool stopped_cleanly = true;
    if (instance->state == TC_GAME_APPLICATION_STATE_STARTED ||
        instance->state == TC_GAME_APPLICATION_STATE_START_FAILED) {
        stopped_cleanly = tc_game_application_instance_stop(instance, error);
    }

    instance->destroy(instance->object);
    instance->object = NULL;
    tc_runtime_type_registry_unlink_instance(&instance->type_link);
    free(instance);
    *instance_ptr = NULL;
    return stopped_cleanly;
}

tc_game_application_state tc_game_application_instance_state(const tc_game_application_instance* instance) {
    return instance ? instance->state : TC_GAME_APPLICATION_STATE_STOPPED;
}

const char* tc_game_application_instance_type_name(const tc_game_application_instance* instance) {
    return instance ? instance->type_link.type_name : NULL;
}

tc_runtime_session* tc_game_application_instance_session(const tc_game_application_instance* instance) {
    return instance ? instance->context.session : NULL;
}
