#pragma once

#include <exception>
#include <string>
#include <type_traits>
#include <utility>

#include <termin/runtime/game_application.h>

namespace termin::runtime {

    // Optional native convenience interface. Registration still publishes the
    // C facet and calls through C function pointers; this class is not the
    // canonical cross-module ABI.
    class GameApplication {
    public:
        virtual ~GameApplication() = default;

        virtual bool start(const tc_game_application_context_v1& context, std::string& error) = 0;
        virtual bool stop(const tc_game_application_context_v1& context, std::string& error) = 0;
    };

    class TERMIN_RUNTIME_API GameApplicationTypeDescriptorBuilder {
        tc_runtime_type_descriptor* _descriptor = nullptr;
        tc_runtime_owned_factory _factory{};
        std::string _type_name;
        bool _abstract = false;
        bool _valid = true;

    public:
        GameApplicationTypeDescriptorBuilder(const char* type_name,
                                             const char* owner,
                                             const char* parent,
                                             tc_runtime_owned_factory factory,
                                             bool is_abstract = false,
                                             bool allow_same_owner_replacement = false);
        ~GameApplicationTypeDescriptorBuilder();

        GameApplicationTypeDescriptorBuilder(const GameApplicationTypeDescriptorBuilder&) = delete;
        GameApplicationTypeDescriptorBuilder& operator=(const GameApplicationTypeDescriptorBuilder&) = delete;
        GameApplicationTypeDescriptorBuilder(GameApplicationTypeDescriptorBuilder&& other) noexcept;
        GameApplicationTypeDescriptorBuilder& operator=(GameApplicationTypeDescriptorBuilder&& other) noexcept;

        GameApplicationTypeDescriptorBuilder&
        runtime_binding(const char* binding_id, void* payload, tc_runtime_type_facet_destroy_fn destroy = nullptr);
        bool commit();

        template <typename T>
        static GameApplicationTypeDescriptorBuilder native(const char* type_name,
                                                           const char* owner,
                                                           const char* parent = TC_GAME_APPLICATION_ROOT_TYPE,
                                                           bool allow_same_owner_replacement = false);

        static GameApplicationTypeDescriptorBuilder abstract(const char* type_name,
                                                             const char* owner,
                                                             const char* parent = TC_GAME_APPLICATION_ROOT_TYPE,
                                                             bool allow_same_owner_replacement = false) {
            return GameApplicationTypeDescriptorBuilder(
                type_name, owner, parent, tc_runtime_owned_factory{}, true, allow_same_owner_replacement);
        }
    };

    namespace detail {

        inline void set_factory_error(const tc_game_application_factory_request_v1* request, const char* message) {
            if (request && request->struct_size >= sizeof(tc_game_application_factory_request_v1)) {
                tc_game_application_set_error(request->error, message);
            }
        }

        template <typename T> struct NativeGameApplicationFactory {
            static_assert(std::is_base_of_v<GameApplication, T>,
                          "native GameApplication types must derive from termin::runtime::GameApplication");
            static_assert(std::is_default_constructible_v<T>,
                          "native GameApplication types must be default constructible");
            static_assert(std::is_nothrow_destructible_v<T>, "native GameApplication destructors must be noexcept");

            static bool create(void*, const void* request_raw, void* result_raw) {
                const auto* request = static_cast<const tc_game_application_factory_request_v1*>(request_raw);
                auto* result = static_cast<tc_game_application_factory_result_v1*>(result_raw);
                if (!request || request->struct_size < sizeof(tc_game_application_factory_request_v1) ||
                    !request->context || request->context->struct_size < sizeof(tc_game_application_context_v1) ||
                    !result || result->struct_size < sizeof(tc_game_application_factory_result_v1)) {
                    set_factory_error(request, "native factory received an incompatible request or result");
                    return false;
                }

                try {
                    result->struct_size = sizeof(tc_game_application_factory_result_v1);
                    result->object = new T();
                    result->destroy = &destroy;
                    result->ops = &ops;
                    return true;
                } catch (const std::exception& exception) {
                    set_factory_error(request, exception.what());
                } catch (...) {
                    set_factory_error(request, "native GameApplication constructor threw an unknown exception");
                }
                return false;
            }

            static bool
            start(void* object, const tc_game_application_context_v1* context, tc_game_application_error_v1* error) {
                if (!object || !context || context->struct_size < sizeof(tc_game_application_context_v1)) {
                    tc_game_application_set_error(error, "native start received an invalid object or context");
                    return false;
                }
                try {
                    std::string message;
                    const bool result = static_cast<T*>(object)->start(*context, message);
                    if (!result && !message.empty()) {
                        tc_game_application_set_error(error, message.c_str());
                    }
                    return result;
                } catch (const std::exception& exception) {
                    tc_game_application_set_error(error, exception.what());
                } catch (...) {
                    tc_game_application_set_error(error, "native GameApplication start threw an unknown exception");
                }
                return false;
            }

            static bool
            stop(void* object, const tc_game_application_context_v1* context, tc_game_application_error_v1* error) {
                if (!object || !context || context->struct_size < sizeof(tc_game_application_context_v1)) {
                    tc_game_application_set_error(error, "native stop received an invalid object or context");
                    return false;
                }
                try {
                    std::string message;
                    const bool result = static_cast<T*>(object)->stop(*context, message);
                    if (!result && !message.empty()) {
                        tc_game_application_set_error(error, message.c_str());
                    }
                    return result;
                } catch (const std::exception& exception) {
                    tc_game_application_set_error(error, exception.what());
                } catch (...) {
                    tc_game_application_set_error(error, "native GameApplication stop threw an unknown exception");
                }
                return false;
            }

            static void destroy(void* object) {
                delete static_cast<T*>(object);
            }

            inline static const tc_game_application_ops_v1 ops = {
                sizeof(tc_game_application_ops_v1),
                TC_GAME_APPLICATION_OPS_ABI_VERSION,
                &start,
                &stop,
            };
        };

    } // namespace detail

    template <typename T>
    GameApplicationTypeDescriptorBuilder GameApplicationTypeDescriptorBuilder::native(
        const char* type_name, const char* owner, const char* parent, bool allow_same_owner_replacement) {
        using Factory = detail::NativeGameApplicationFactory<T>;
        tc_runtime_owned_factory factory = tc_runtime_owned_factory_make(&Factory::create, nullptr, nullptr);
        return GameApplicationTypeDescriptorBuilder(
            type_name, owner, parent, factory, false, allow_same_owner_replacement);
    }

} // namespace termin::runtime
