#include <termin/engine/world_controller.hpp>

#include "world_context_internal.hpp"

#include <atomic>
#include <cstring>
#include <new>
#include <stdexcept>
#include <string>
#include <utility>

extern "C" {
#include <core/tc_scene.h>
#include <core/tc_scene_extension.h>
#include <core/tc_scene_extension_ids.h>
#include <tcbase/tc_log.h>
#include <termin_scene/internal/tc_scene_extension_registry.h>
}

namespace {
    constexpr std::uint64_t kNoSceneToken = UINT64_C(0xFFFFFFFF00000000);
}

struct tc_world_context {
    std::atomic<std::uint32_t> references{1};
    const std::uint64_t generation;
    std::atomic<bool> active{true};
    std::atomic<tc_world_controller_instance*> controller{nullptr};
    std::atomic<std::uint64_t> primary_scene{kNoSceneToken};
    std::atomic<std::uint64_t> pending_primary_scene{kNoSceneToken};

    tc_world_context(std::uint64_t generation_value,
                     tc_world_controller_instance* controller_value) noexcept
        : generation(generation_value),
          controller(controller_value) {}
};

namespace {

    struct WorldContextSceneExtension {
        tc_world_context* context = nullptr;
        std::uint64_t generation = 0;
    };

    std::atomic<std::uint64_t> g_next_world_context_generation{1};

    std::uint64_t scene_token(tc_scene_handle scene) noexcept {
        if (!tc_scene_handle_valid(scene)) {
            return kNoSceneToken;
        }
        return (static_cast<std::uint64_t>(scene.index) << 32) |
               static_cast<std::uint64_t>(scene.generation);
    }

    tc_scene_handle scene_from_token(std::uint64_t token) noexcept {
        if (token == kNoSceneToken) {
            return TC_SCENE_HANDLE_INVALID;
        }
        tc_scene_handle scene{};
        scene.index = static_cast<std::uint32_t>(token >> 32);
        scene.generation = static_cast<std::uint32_t>(token);
        return scene;
    }

    void* create_world_context_extension(tc_scene_handle, void*) {
        return new (std::nothrow) WorldContextSceneExtension();
    }

    void destroy_world_context_extension(void* instance, void*) {
        auto* extension = static_cast<WorldContextSceneExtension*>(instance);
        if (!extension) {
            return;
        }
        if (extension->context) {
            tc_world_context_release(extension->context);
        }
        delete extension;
    }

    WorldContextSceneExtension* world_context_extension(tc_scene_handle scene) noexcept {
        return static_cast<WorldContextSceneExtension*>(
            tc_scene_ext_get(scene, TC_SCENE_EXT_TYPE_WORLD_CONTEXT));
    }

    const char* consumer_name(const char* consumer) noexcept {
        return consumer && consumer[0] ? consumer : "runtime component";
    }

    bool scene_is_bound_to_context(tc_world_context* context, tc_scene_handle scene) noexcept {
        auto* extension = world_context_extension(scene);
        return extension && extension->context == context &&
               extension->generation == tc_world_context_generation(context) &&
               tc_world_context_generation_is_valid(context, extension->generation);
    }

} // namespace

extern "C" {

    bool tc_world_context_scene_extension_init(void) {
        if (!tc_scene_ext_registry_initialized()) {
            tc_scene_ext_registry_init();
        }
        if (tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_WORLD_CONTEXT)) {
            const char* name = tc_scene_ext_type_debug_name(TC_SCENE_EXT_TYPE_WORLD_CONTEXT);
            if (name && std::strcmp(name, "world_context") == 0) {
                return true;
            }
            tc_log(TC_LOG_ERROR,
                   "[WorldContext] Scene extension slot is already owned by '%s'",
                   name ? name : "<unnamed>");
            return false;
        }

        tc_scene_ext_vtable vtable{};
        vtable.create = &create_world_context_extension;
        vtable.destroy = &destroy_world_context_extension;
        if (!tc_scene_ext_register(TC_SCENE_EXT_TYPE_WORLD_CONTEXT,
                                   "world_context",
                                   "",
                                   &vtable,
                                   nullptr)) {
            tc_log(TC_LOG_ERROR, "[WorldContext] Failed to register the transient scene extension");
            return false;
        }
        return true;
    }

    tc_world_context* tc_world_context_retain(tc_world_context* context) {
        if (context) {
            context->references.fetch_add(1, std::memory_order_relaxed);
        }
        return context;
    }

    void tc_world_context_release(tc_world_context* context) {
        if (!context) {
            return;
        }
        if (context->references.fetch_sub(1, std::memory_order_acq_rel) == 1) {
            if (context->active.load(std::memory_order_acquire)) {
                tc_log(TC_LOG_ERROR, "[WorldContext] Destroying a context that was not invalidated");
            }
            delete context;
        }
    }

    bool tc_world_context_is_valid(const tc_world_context* context) {
        return context && context->active.load(std::memory_order_acquire);
    }

    uint64_t tc_world_context_generation(const tc_world_context* context) {
        return context ? context->generation : 0;
    }

    bool tc_world_context_generation_is_valid(const tc_world_context* context, uint64_t generation) {
        return generation != 0 && context && context->generation == generation &&
               context->active.load(std::memory_order_acquire);
    }

    tc_world_controller_instance* tc_world_context_controller(const tc_world_context* context) {
        if (!tc_world_context_is_valid(context)) {
            return nullptr;
        }
        return context->controller.load(std::memory_order_acquire);
    }

    tc_scene_handle tc_world_context_primary_scene(const tc_world_context* context) {
        if (!tc_world_context_is_valid(context)) {
            return TC_SCENE_HANDLE_INVALID;
        }
        const tc_scene_handle scene =
            scene_from_token(context->primary_scene.load(std::memory_order_acquire));
        return tc_scene_alive(scene) ? scene : TC_SCENE_HANDLE_INVALID;
    }

    bool tc_world_context_request_primary_scene(tc_world_context* context, tc_scene_handle scene) {
        if (!tc_world_context_is_valid(context)) {
            tc_log(TC_LOG_ERROR, "[WorldContext] Cannot request a primary scene through an inactive context");
            return false;
        }
        if (!tc_scene_alive(scene)) {
            tc_log(TC_LOG_ERROR, "[WorldContext] Primary scene request requires a live scene");
            return false;
        }
        if (!scene_is_bound_to_context(context, scene)) {
            tc_log(TC_LOG_ERROR,
                   "[WorldContext] Primary scene request target is not bound to this RuntimeSession");
            return false;
        }

        const std::uint64_t token = scene_token(scene);
        const std::uint64_t pending =
            context->pending_primary_scene.load(std::memory_order_acquire);
        if (pending != kNoSceneToken) {
            if (pending == token) {
                return true;
            }
            tc_log(TC_LOG_ERROR, "[WorldContext] Another primary scene request is already pending");
            return false;
        }
        if (context->primary_scene.load(std::memory_order_acquire) == token) {
            return true;
        }
        if (tc_scene_get_mode(scene) != TC_SCENE_MODE_INACTIVE) {
            tc_log(TC_LOG_ERROR, "[WorldContext] Primary scene request target must be inactive");
            return false;
        }

        std::uint64_t expected = kNoSceneToken;
        if (!context->pending_primary_scene.compare_exchange_strong(
                expected, token, std::memory_order_acq_rel, std::memory_order_acquire)) {
            if (expected == token) {
                return true;
            }
            tc_log(TC_LOG_ERROR, "[WorldContext] Another primary scene request is already pending");
            return false;
        }
        if (!tc_world_context_is_valid(context)) {
            expected = token;
            context->pending_primary_scene.compare_exchange_strong(
                expected, kNoSceneToken, std::memory_order_acq_rel, std::memory_order_acquire);
            tc_log(TC_LOG_ERROR, "[WorldContext] RuntimeSession ended while queuing a primary scene request");
            return false;
        }
        return true;
    }

    tc_world_context* tc_world_context_acquire_from_scene(tc_scene_handle scene) {
        auto* extension = world_context_extension(scene);
        if (!extension || !extension->context || extension->generation == 0) {
            return nullptr;
        }

        tc_world_context* context = tc_world_context_retain(extension->context);
        if (!tc_world_context_generation_is_valid(context, extension->generation)) {
            tc_world_context_release(context);
            return nullptr;
        }
        return context;
    }

    tc_world_context* tc_world_context_require_from_scene(tc_scene_handle scene, const char* consumer) {
        tc_world_context* context = tc_world_context_acquire_from_scene(scene);
        if (context) {
            return context;
        }

        if (!tc_scene_alive(scene)) {
            tc_log(TC_LOG_ERROR,
                   "[WorldContext] %s requires a live runtime scene; handle=(%u,%u)",
                   consumer_name(consumer),
                   scene.index,
                   scene.generation);
        } else {
            const char* scene_name = tc_scene_get_name(scene);
            tc_log(TC_LOG_ERROR,
                   "[WorldContext] %s requires scene '%s' to be bound to a live RuntimeSession",
                   consumer_name(consumer),
                   scene_name && scene_name[0] ? scene_name : "<unnamed>");
        }
        return nullptr;
    }

    tc_world_context* tc_world_context_acquire_from_component(const tc_component* component) {
        if (!component) {
            return nullptr;
        }
        return tc_world_context_acquire_from_scene(component->lifecycle_scene);
    }

    tc_world_context* tc_world_context_require_from_component(const tc_component* component,
                                                              const char* consumer) {
        if (!component) {
            tc_log(TC_LOG_ERROR,
                   "[WorldContext] %s requires a non-null scene component",
                   consumer_name(consumer));
            return nullptr;
        }
        return tc_world_context_require_from_scene(component->lifecycle_scene, consumer);
    }

} // extern "C"

namespace termin {

    WorldContext::WorldContext(tc_world_context* native, AdoptRetained) noexcept
        : _native(native),
          _generation(tc_world_context_generation(native)) {}

    WorldContext::WorldContext(tc_world_context* native) noexcept
        : WorldContext(tc_world_context_retain(native), AdoptRetained{}) {}

    WorldContext::~WorldContext() {
        tc_world_context_release(_native);
    }

    WorldContext::WorldContext(const WorldContext& other) noexcept
        : _native(tc_world_context_retain(other._native)),
          _generation(other._generation) {}

    WorldContext& WorldContext::operator=(const WorldContext& other) noexcept {
        if (this != &other) {
            tc_world_context* replacement = tc_world_context_retain(other._native);
            tc_world_context_release(_native);
            _native = replacement;
            _generation = other._generation;
        }
        return *this;
    }

    WorldContext::WorldContext(WorldContext&& other) noexcept
        : _native(std::exchange(other._native, nullptr)),
          _generation(std::exchange(other._generation, 0)) {}

    WorldContext& WorldContext::operator=(WorldContext&& other) noexcept {
        if (this != &other) {
            tc_world_context_release(_native);
            _native = std::exchange(other._native, nullptr);
            _generation = std::exchange(other._generation, 0);
        }
        return *this;
    }

    WorldContext WorldContext::from_scene(tc_scene_handle scene) noexcept {
        return WorldContext(tc_world_context_acquire_from_scene(scene), AdoptRetained{});
    }

    WorldContext WorldContext::require_from_scene(tc_scene_handle scene, const char* consumer) {
        tc_world_context* context = tc_world_context_require_from_scene(scene, consumer);
        if (!context) {
            throw std::runtime_error(std::string(consumer_name(consumer)) +
                                     " requires a scene bound to a live RuntimeSession");
        }
        return WorldContext(context, AdoptRetained{});
    }

    WorldContext WorldContext::from_component(const tc_component* component) noexcept {
        return WorldContext(tc_world_context_acquire_from_component(component), AdoptRetained{});
    }

    WorldContext WorldContext::require_from_component(const tc_component* component, const char* consumer) {
        tc_world_context* context = tc_world_context_require_from_component(component, consumer);
        if (!context) {
            throw std::runtime_error(std::string(consumer_name(consumer)) +
                                     " requires a component in a scene bound to a live RuntimeSession");
        }
        return WorldContext(context, AdoptRetained{});
    }

    bool WorldContext::valid() const noexcept {
        return tc_world_context_generation_is_valid(_native, _generation);
    }

    std::optional<WorldControllerRef> WorldContext::controller() const noexcept {
        if (!tc_world_context_controller(_native)) {
            return std::nullopt;
        }
        return WorldControllerRef(*this);
    }

    tc_scene_handle WorldContext::primary_scene() const noexcept {
        return tc_world_context_primary_scene(_native);
    }

    bool WorldContext::request_primary_scene(tc_scene_handle scene) const noexcept {
        return tc_world_context_request_primary_scene(_native, scene);
    }

    bool WorldControllerRef::valid() const noexcept {
        return tc_world_context_controller(_context.native_handle()) != nullptr;
    }

    const char* WorldControllerRef::type_name() const noexcept {
        tc_world_controller_instance* controller = native_handle();
        return controller ? tc_world_controller_instance_type_name(controller) : nullptr;
    }

    void* WorldControllerRef::object() const noexcept {
        return tc_world_controller_instance_object(native_handle());
    }

    tc_world_controller_instance* WorldControllerRef::native_handle() const noexcept {
        return tc_world_context_controller(_context.native_handle());
    }

    namespace engine_detail {

        tc_world_context* create_world_context(tc_world_controller_instance* controller) noexcept {
            std::uint64_t generation = g_next_world_context_generation.fetch_add(1, std::memory_order_relaxed);
            if (generation == 0) {
                generation = g_next_world_context_generation.fetch_add(1, std::memory_order_relaxed);
            }
            auto* context = new (std::nothrow) tc_world_context(generation, controller);
            if (!context) {
                tc_log(TC_LOG_ERROR, "[WorldContext] Failed to allocate the RuntimeSession context");
            }
            return context;
        }

        void invalidate_world_context(tc_world_context* context) noexcept {
            if (!context) {
                return;
            }
            context->active.store(false, std::memory_order_release);
            context->pending_primary_scene.store(kNoSceneToken, std::memory_order_release);
            context->primary_scene.store(kNoSceneToken, std::memory_order_release);
            context->controller.store(nullptr, std::memory_order_release);
        }

        bool bind_world_context_scene(tc_world_context* context, tc_scene_handle scene) noexcept {
            if (!tc_world_context_is_valid(context)) {
                tc_log(TC_LOG_ERROR, "[WorldContext] Cannot bind a scene to an inactive context");
                return false;
            }
            if (!tc_scene_alive(scene)) {
                tc_log(TC_LOG_ERROR, "[WorldContext] Cannot bind a dead or invalid scene handle");
                return false;
            }
            if (!tc_world_context_scene_extension_init() ||
                !tc_scene_ext_attach(scene, TC_SCENE_EXT_TYPE_WORLD_CONTEXT)) {
                tc_log(TC_LOG_ERROR, "[WorldContext] Failed to attach the transient scene extension");
                return false;
            }

            auto* extension = world_context_extension(scene);
            if (!extension) {
                tc_log(TC_LOG_ERROR, "[WorldContext] Attached scene extension is unavailable");
                return false;
            }
            if (extension->context == context && extension->generation == context->generation) {
                return true;
            }
            if (extension->context &&
                tc_world_context_generation_is_valid(extension->context, extension->generation)) {
                tc_log(TC_LOG_ERROR, "[WorldContext] Scene is already bound to another live RuntimeSession");
                return false;
            }
            if (extension->context) {
                tc_world_context_release(extension->context);
            }
            extension->context = tc_world_context_retain(context);
            extension->generation = context->generation;
            return true;
        }

        bool unbind_world_context_scene(tc_world_context* context, tc_scene_handle scene) noexcept {
            if (!tc_scene_alive(scene)) {
                return true;
            }
            auto* extension = world_context_extension(scene);
            if (!extension) {
                return true;
            }
            if (extension->context != context || extension->generation != tc_world_context_generation(context)) {
                tc_log(TC_LOG_ERROR, "[WorldContext] Refusing to unbind a scene owned by another RuntimeSession");
                return false;
            }
            tc_scene_ext_detach(scene, TC_SCENE_EXT_TYPE_WORLD_CONTEXT);
            return true;
        }

        tc_scene_handle take_world_context_primary_request(tc_world_context* context) noexcept {
            if (!tc_world_context_is_valid(context)) {
                return TC_SCENE_HANDLE_INVALID;
            }
            return scene_from_token(
                context->pending_primary_scene.exchange(kNoSceneToken, std::memory_order_acq_rel));
        }

        bool publish_world_context_primary_scene(tc_world_context* context,
                                                 tc_scene_handle scene) noexcept {
            if (!tc_world_context_is_valid(context)) {
                return false;
            }
            if (tc_scene_handle_valid(scene) && !scene_is_bound_to_context(context, scene)) {
                tc_log(TC_LOG_ERROR,
                       "[WorldContext] Refusing to publish a primary scene owned by another RuntimeSession");
                return false;
            }
            context->primary_scene.store(scene_token(scene), std::memory_order_release);
            return true;
        }

        void clear_world_context_scene_references(tc_world_context* context,
                                                  tc_scene_handle scene) noexcept {
            if (!context) {
                return;
            }
            const std::uint64_t token = scene_token(scene);
            if (token == kNoSceneToken) {
                return;
            }
            std::uint64_t expected = token;
            context->pending_primary_scene.compare_exchange_strong(
                expected, kNoSceneToken, std::memory_order_acq_rel, std::memory_order_acquire);
            expected = token;
            context->primary_scene.compare_exchange_strong(
                expected, kNoSceneToken, std::memory_order_acq_rel, std::memory_order_acquire);
        }

    } // namespace engine_detail
} // namespace termin
