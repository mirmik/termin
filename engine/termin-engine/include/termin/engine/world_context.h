#ifndef TERMIN_ENGINE_WORLD_CONTEXT_H
#define TERMIN_ENGINE_WORLD_CONTEXT_H

#include <stdbool.h>
#include <stdint.h>

#include <termin/engine/termin_engine_api.hpp>
#include <termin/engine/world_controller.h>

#include <core/tc_component.h>
#include <core/tc_scene_pool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Register the engine-owned transient WorldContext scene extension. The type
// is process-owned, but instances are attached only by a live RuntimeSession.
TERMIN_ENGINE_API bool tc_world_context_scene_extension_init(void);

// WorldContext is an invalidatable reference-counted control block. Retained
// handles may outlive their RuntimeSession safely; they then report invalid.
TERMIN_ENGINE_API tc_world_context* tc_world_context_retain(tc_world_context* context);
TERMIN_ENGINE_API void tc_world_context_release(tc_world_context* context);
TERMIN_ENGINE_API bool tc_world_context_is_valid(const tc_world_context* context);
TERMIN_ENGINE_API uint64_t tc_world_context_generation(const tc_world_context* context);
TERMIN_ENGINE_API bool tc_world_context_generation_is_valid(const tc_world_context* context,
                                                             uint64_t generation);

// Returns the optional controller supervised by the live session. The result
// is borrowed from context and must not be retained past a validity check.
TERMIN_ENGINE_API tc_world_controller_instance*
tc_world_context_controller(const tc_world_context* context);

// Acquire a context through the transient scene extension. The caller owns one
// reference and must release it. The require variants additionally log an
// actionable error naming the consumer.
TERMIN_ENGINE_API tc_world_context* tc_world_context_acquire_from_scene(tc_scene_handle scene);
TERMIN_ENGINE_API tc_world_context* tc_world_context_require_from_scene(tc_scene_handle scene,
                                                                        const char* consumer);
TERMIN_ENGINE_API tc_world_context* tc_world_context_acquire_from_component(const struct tc_component* component);
TERMIN_ENGINE_API tc_world_context* tc_world_context_require_from_component(const struct tc_component* component,
                                                                            const char* consumer);

#ifdef __cplusplus
}
#endif

#endif // TERMIN_ENGINE_WORLD_CONTEXT_H
