#pragma once

#include <cstdint>
#include <exception>
#include <optional>
#include <string>
#include <type_traits>
#include <utility>

#include <termin/engine/world_context.h>
#include <termin/engine/world_controller.h>

namespace termin {

    class EngineCore;
    class WorldControllerRef;

    // Safe value handle to the EngineCore-owned per-run context. Copies retain
    // only the invalidatable control block, never the RuntimeSession itself.
    class WorldContext {
        tc_world_context* _native = nullptr;
        std::uint64_t _generation = 0;

        struct AdoptRetained {};
        WorldContext(tc_world_context* native, AdoptRetained) noexcept;

    public:
        WorldContext() = default;
        explicit WorldContext(tc_world_context* native) noexcept;
        ~WorldContext();

        WorldContext(const WorldContext& other) noexcept;
        WorldContext& operator=(const WorldContext& other) noexcept;
        WorldContext(WorldContext&& other) noexcept;
        WorldContext& operator=(WorldContext&& other) noexcept;

        static WorldContext from_scene(tc_scene_handle scene) noexcept;
        static WorldContext require_from_scene(tc_scene_handle scene, const char* consumer);
        static WorldContext from_component(const tc_component* component) noexcept;
        static WorldContext require_from_component(const tc_component* component, const char* consumer);

        bool valid() const noexcept;
        explicit operator bool() const noexcept {
            return valid();
        }
        std::optional<WorldControllerRef> controller() const noexcept;

        tc_world_context* native_handle() const noexcept {
            return _native;
        }

        std::uint64_t generation() const noexcept {
            return _generation;
        }

        friend bool operator==(const WorldContext& lhs, const WorldContext& rhs) noexcept {
            return lhs._native == rhs._native && lhs._generation == rhs._generation;
        }
        friend bool operator!=(const WorldContext& lhs, const WorldContext& rhs) noexcept {
            return !(lhs == rhs);
        }
    };

    // Invalidatable, non-owning projection of the controller supervised by a
    // WorldContext. It intentionally exposes identity, not lifecycle authority.
    class TERMIN_ENGINE_API WorldControllerRef {
        friend class WorldContext;
        explicit WorldControllerRef(WorldContext context) noexcept
            : _context(std::move(context)) {}

        WorldContext _context;
        tc_world_controller_instance* native_handle() const noexcept;

    public:
        bool valid() const noexcept;
        explicit operator bool() const noexcept {
            return valid();
        }
        const char* type_name() const noexcept;
        void* object() const noexcept;

        template <typename T>
        T* object_as() const noexcept {
            return static_cast<T*>(object());
        }
    };

    // Optional native convenience interface. Registration still publishes the
    // C facet and calls through C function pointers; this class is not the
    // canonical cross-module ABI.
    class WorldController {
    public:
        virtual ~WorldController() = default;

        virtual bool start(WorldContext context, std::string& error) = 0;
        virtual bool stop(WorldContext context, std::string& error) = 0;
    };

    // Move-only owner of one language-neutral controller instance. The owner
    // may be transferred into EngineCore; destruction is a lifecycle backstop
    // and releases the runtime type instance link.
    class TERMIN_ENGINE_API WorldControllerInstance {
        friend class EngineCore;

        tc_world_controller_instance* _instance = nullptr;

        explicit WorldControllerInstance(tc_world_controller_instance* instance) noexcept
            : _instance(instance) {}

    public:
        WorldControllerInstance() = default;
        ~WorldControllerInstance();

        WorldControllerInstance(const WorldControllerInstance&) = delete;
        WorldControllerInstance& operator=(const WorldControllerInstance&) = delete;
        WorldControllerInstance(WorldControllerInstance&& other) noexcept;
        WorldControllerInstance& operator=(WorldControllerInstance&& other) noexcept;

        static WorldControllerInstance create(const char* type_name, std::string& error);

        bool valid() const noexcept {
            return _instance != nullptr;
        }
        explicit operator bool() const noexcept {
            return valid();
        }
        tc_world_controller_state state() const noexcept;
        const char* type_name() const noexcept;
        tc_world_controller_instance* native_handle() const noexcept {
            return _instance;
        }
        bool reset() noexcept;
    };

    class TERMIN_ENGINE_API WorldControllerTypeDescriptorBuilder {
        tc_runtime_type_descriptor* _descriptor = nullptr;
        tc_runtime_owned_factory _factory{};
        std::string _type_name;
        bool _abstract = false;
        bool _valid = true;

    public:
        WorldControllerTypeDescriptorBuilder(const char* type_name,
                                             const char* owner,
                                             const char* parent,
                                             tc_runtime_owned_factory factory,
                                             bool is_abstract = false,
                                             bool allow_same_owner_replacement = false);
        ~WorldControllerTypeDescriptorBuilder();

        WorldControllerTypeDescriptorBuilder(const WorldControllerTypeDescriptorBuilder&) = delete;
        WorldControllerTypeDescriptorBuilder& operator=(const WorldControllerTypeDescriptorBuilder&) = delete;
        WorldControllerTypeDescriptorBuilder(WorldControllerTypeDescriptorBuilder&& other) noexcept;
        WorldControllerTypeDescriptorBuilder& operator=(WorldControllerTypeDescriptorBuilder&& other) noexcept;

        WorldControllerTypeDescriptorBuilder&
        runtime_binding(const char* binding_id, void* payload, tc_runtime_type_facet_destroy_fn destroy = nullptr);
        bool commit();

        template <typename T>
        static WorldControllerTypeDescriptorBuilder native(const char* type_name,
                                                           const char* owner,
                                                           const char* parent = TC_WORLD_CONTROLLER_ROOT_TYPE,
                                                           bool allow_same_owner_replacement = false);

        static WorldControllerTypeDescriptorBuilder abstract(const char* type_name,
                                                             const char* owner,
                                                             const char* parent = TC_WORLD_CONTROLLER_ROOT_TYPE,
                                                             bool allow_same_owner_replacement = false) {
            return WorldControllerTypeDescriptorBuilder(
                type_name, owner, parent, tc_runtime_owned_factory{}, true, allow_same_owner_replacement);
        }
    };

    namespace detail {

        inline void set_factory_error(const tc_world_controller_factory_request_v1* request, const char* message) {
            if (request && request->struct_size >= sizeof(tc_world_controller_factory_request_v1)) {
                tc_world_controller_set_error(request->error, message);
            }
        }

        template <typename T> struct NativeWorldControllerFactory {
            static_assert(std::is_base_of_v<WorldController, T>,
                          "native WorldController types must derive from termin::WorldController");
            static_assert(std::is_default_constructible_v<T>,
                          "native WorldController types must be default constructible");
            static_assert(std::is_nothrow_destructible_v<T>, "native WorldController destructors must be noexcept");

            static bool create(void*, const void* request_raw, void* result_raw) {
                const auto* request = static_cast<const tc_world_controller_factory_request_v1*>(request_raw);
                auto* result = static_cast<tc_world_controller_factory_result_v1*>(result_raw);
                if (!request || request->struct_size < sizeof(tc_world_controller_factory_request_v1) ||
                    !result || result->struct_size < sizeof(tc_world_controller_factory_result_v1)) {
                    set_factory_error(request, "native factory received an incompatible request or result");
                    return false;
                }

                try {
                    result->struct_size = sizeof(tc_world_controller_factory_result_v1);
                    result->object = new T();
                    result->destroy = &destroy;
                    result->ops = &ops;
                    return true;
                } catch (const std::exception& exception) {
                    set_factory_error(request, exception.what());
                } catch (...) {
                    set_factory_error(request, "native WorldController constructor threw an unknown exception");
                }
                return false;
            }

            static bool start(void* object, tc_world_context* context, tc_world_controller_error_v1* error) {
                if (!object || !context) {
                    tc_world_controller_set_error(error, "native start received a null object or WorldContext");
                    return false;
                }
                try {
                    std::string message;
                    const bool result = static_cast<T*>(object)->start(WorldContext(context), message);
                    if (!result && !message.empty()) {
                        tc_world_controller_set_error(error, message.c_str());
                    }
                    return result;
                } catch (const std::exception& exception) {
                    tc_world_controller_set_error(error, exception.what());
                } catch (...) {
                    tc_world_controller_set_error(error, "native WorldController start threw an unknown exception");
                }
                return false;
            }

            static bool stop(void* object, tc_world_context* context, tc_world_controller_error_v1* error) {
                if (!object || !context) {
                    tc_world_controller_set_error(error, "native stop received a null object or WorldContext");
                    return false;
                }
                try {
                    std::string message;
                    const bool result = static_cast<T*>(object)->stop(WorldContext(context), message);
                    if (!result && !message.empty()) {
                        tc_world_controller_set_error(error, message.c_str());
                    }
                    return result;
                } catch (const std::exception& exception) {
                    tc_world_controller_set_error(error, exception.what());
                } catch (...) {
                    tc_world_controller_set_error(error, "native WorldController stop threw an unknown exception");
                }
                return false;
            }

            static void destroy(void* object) {
                delete static_cast<T*>(object);
            }

            inline static const tc_world_controller_ops_v1 ops = {
                sizeof(tc_world_controller_ops_v1),
                TC_WORLD_CONTROLLER_OPS_ABI_VERSION,
                &start,
                &stop,
            };
        };

    } // namespace detail

    template <typename T>
    WorldControllerTypeDescriptorBuilder WorldControllerTypeDescriptorBuilder::native(
        const char* type_name, const char* owner, const char* parent, bool allow_same_owner_replacement) {
        using Factory = detail::NativeWorldControllerFactory<T>;
        tc_runtime_owned_factory factory = tc_runtime_owned_factory_make(&Factory::create, nullptr, nullptr);
        return WorldControllerTypeDescriptorBuilder(
            type_name, owner, parent, factory, false, allow_same_owner_replacement);
    }

} // namespace termin
