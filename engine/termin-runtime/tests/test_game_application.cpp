#include "guard_main.h"

GUARD_TEST_MAIN();

#include <stdexcept>
#include <string>
#include <vector>

#include <termin/runtime/game_application.hpp>

extern "C" {
#include <inspect/tc_runtime_type_registry.h>
}

namespace {

    struct ErrorBuffer {
        char text[512] = {};
        tc_game_application_error_v1 value{sizeof(tc_game_application_error_v1), text, sizeof(text)};

        void clear() {
            text[0] = '\0';
        }
    };

    enum class Event {
        Create,
        Start,
        Stop,
        Destroy,
    };

    struct RawCounters {
        std::vector<Event> events;
        bool fail_create = false;
        bool invalid_ops = false;
        bool fail_start = false;
        bool fail_stop = false;
    };

    struct RawApplication {
        RawCounters* counters = nullptr;
    };

    bool raw_start(void* object, tc_game_application_error_v1* error) {
        auto* application = static_cast<RawApplication*>(object);
        application->counters->events.push_back(Event::Start);
        if (application->counters->fail_start) {
            tc_game_application_set_error(error, "injected start failure");
            return false;
        }
        return true;
    }

    bool raw_stop(void* object, tc_game_application_error_v1* error) {
        auto* application = static_cast<RawApplication*>(object);
        application->counters->events.push_back(Event::Stop);
        if (application->counters->fail_stop) {
            tc_game_application_set_error(error, "injected stop failure");
            return false;
        }
        return true;
    }

    const tc_game_application_ops_v1 kRawOps = {
        sizeof(tc_game_application_ops_v1),
        TC_GAME_APPLICATION_OPS_ABI_VERSION,
        &raw_start,
        &raw_stop,
    };

    const tc_game_application_ops_v1 kInvalidRawOps = {
        sizeof(tc_game_application_ops_v1),
        TC_GAME_APPLICATION_OPS_ABI_VERSION + 1,
        &raw_start,
        &raw_stop,
    };

    void raw_destroy(void* object) {
        auto* application = static_cast<RawApplication*>(object);
        application->counters->events.push_back(Event::Destroy);
        delete application;
    }

    bool raw_create(void* context, const void* request_raw, void* result_raw) {
        auto* counters = static_cast<RawCounters*>(context);
        const auto* request = static_cast<const tc_game_application_factory_request_v1*>(request_raw);
        auto* result = static_cast<tc_game_application_factory_result_v1*>(result_raw);
        counters->events.push_back(Event::Create);
        if (counters->fail_create) {
            tc_game_application_set_error(request ? request->error : nullptr, "injected creation failure");
            return false;
        }
        if (!request || request->struct_size < sizeof(tc_game_application_factory_request_v1) || !result ||
            result->struct_size < sizeof(tc_game_application_factory_result_v1)) {
            return false;
        }

        result->struct_size = sizeof(tc_game_application_factory_result_v1);
        result->object = new RawApplication{counters};
        result->destroy = &raw_destroy;
        result->ops = counters->invalid_ops ? &kInvalidRawOps : &kRawOps;
        return true;
    }

    bool register_raw_type(const char* type_name,
                           const char* owner,
                           RawCounters& counters,
                           bool allow_same_owner_replacement = false) {
        auto* descriptor = tc_runtime_type_descriptor_create(type_name, owner, TC_GAME_APPLICATION_ROOT_TYPE);
        if (!descriptor) {
            return false;
        }
        if (allow_same_owner_replacement && !tc_runtime_type_descriptor_allow_same_owner_replacement(descriptor)) {
            tc_runtime_type_descriptor_destroy(descriptor);
            return false;
        }
        tc_runtime_owned_factory factory = tc_runtime_owned_factory_make(&raw_create, &counters, nullptr);
        if (!tc_game_application_type_descriptor_add_facet(descriptor, &factory, false)) {
            tc_runtime_type_descriptor_destroy(descriptor);
            return false;
        }
        return tc_runtime_type_registry_commit_descriptor(descriptor);
    }

    void reset_registry() {
        tc_runtime_type_registry_clear();
        REQUIRE(tc_game_application_registry_init());
    }

    struct CxxCounters {
        int constructed = 0;
        int started = 0;
        int stopped = 0;
        int destroyed = 0;
        bool throw_on_start = false;
    };

    CxxCounters* g_cxx_counters = nullptr;

    class CxxApplication final : public termin::runtime::GameApplication {
    public:
        CxxApplication() {
            ++g_cxx_counters->constructed;
        }
        ~CxxApplication() override {
            ++g_cxx_counters->destroyed;
        }

        bool start(std::string& error) override {
            ++g_cxx_counters->started;
            if (g_cxx_counters->throw_on_start) {
                throw std::runtime_error("injected C++ start exception");
            }
            return true;
        }

        bool stop(std::string& error) override {
            (void)error;
            ++g_cxx_counters->stopped;
            return true;
        }
    };

} // namespace

TEST_CASE("GameApplication root bootstrap is explicit idempotent and abstract") {
    tc_runtime_type_registry_clear();
    REQUIRE(tc_game_application_registry_init());
    CHECK(tc_game_application_registry_init());
    CHECK(tc_game_application_type_is_registered(TC_GAME_APPLICATION_ROOT_TYPE));
    CHECK(tc_game_application_type_is_abstract(TC_GAME_APPLICATION_ROOT_TYPE));
    CHECK_EQ(std::string(tc_runtime_type_registry_get_owner(TC_GAME_APPLICATION_ROOT_TYPE)),
             std::string(TC_GAME_APPLICATION_ROOT_OWNER));

    ErrorBuffer error;
    CHECK(tc_game_application_instance_create(TC_GAME_APPLICATION_ROOT_TYPE, &error.value) == nullptr);
    CHECK(error.text[0] != '\0');
    CHECK_EQ(tc_runtime_type_registry_instance_count(TC_GAME_APPLICATION_ROOT_TYPE), 0u);
    tc_runtime_type_registry_clear();
}

TEST_CASE("C GameApplication lifecycle is exact and protects its module owner") {
    reset_registry();
    constexpr const char* type_name = "TestGameApplication";
    constexpr const char* owner = "game-application-test-module";
    RawCounters counters;
    REQUIRE(register_raw_type(type_name, owner, counters));

    ErrorBuffer error;
    tc_game_application_instance* instance = tc_game_application_instance_create(type_name, &error.value);
    REQUIRE(instance != nullptr);
    CHECK_EQ(tc_game_application_instance_state(instance), TC_GAME_APPLICATION_STATE_CREATED);
    CHECK_EQ(std::string(tc_game_application_instance_type_name(instance)), std::string(type_name));
    CHECK_EQ(tc_runtime_type_registry_instance_count(type_name), 1u);

    CHECK(tc_game_application_instance_start(instance, &error.value));
    CHECK_EQ(tc_game_application_instance_state(instance), TC_GAME_APPLICATION_STATE_STARTED);
    CHECK_FALSE(tc_game_application_instance_start(instance, &error.value));
    CHECK(error.text[0] != '\0');
    CHECK_EQ(counters.events.size(), 2u);

    RawCounters refused_replacement;
    CHECK_FALSE(register_raw_type(type_name, owner, refused_replacement, true));
    CHECK_FALSE(tc_runtime_type_registry_prepare_owner_unload(owner, nullptr));
    CHECK(tc_runtime_type_registry_has_type(type_name));

    CHECK(tc_game_application_instance_stop(instance, &error.value));
    CHECK_EQ(tc_game_application_instance_state(instance), TC_GAME_APPLICATION_STATE_STOPPED);
    CHECK_FALSE(tc_game_application_instance_stop(instance, &error.value));
    CHECK(error.text[0] != '\0');
    CHECK_EQ(counters.events.size(), 3u);

    CHECK(tc_game_application_instance_destroy(&instance, &error.value));
    CHECK(instance == nullptr);
    CHECK_EQ(tc_runtime_type_registry_instance_count(type_name), 0u);
    REQUIRE_EQ(counters.events.size(), 4u);
    CHECK(counters.events[0] == Event::Create);
    CHECK(counters.events[1] == Event::Start);
    CHECK(counters.events[2] == Event::Stop);
    CHECK(counters.events[3] == Event::Destroy);

    RawCounters replacement;
    REQUIRE(register_raw_type(type_name, owner, replacement, true));
    CHECK(tc_runtime_type_registry_prepare_owner_unload(owner, nullptr));
    size_t removed = 0;
    CHECK(tc_runtime_type_registry_commit_owner_unload(owner, &removed));
    CHECK_EQ(removed, 1u);
    CHECK_FALSE(tc_runtime_type_registry_has_type(type_name));
    tc_runtime_type_registry_clear();
}

TEST_CASE("GameApplication creation and start failures clean ownership without live links") {
    reset_registry();
    constexpr const char* create_failure_type = "CreationFailureGameApplication";
    constexpr const char* invalid_ops_type = "InvalidOpsGameApplication";
    constexpr const char* start_failure_type = "StartFailureGameApplication";
    constexpr const char* owner = "game-application-failure-test-module";
    ErrorBuffer error;

    RawCounters create_failure;
    create_failure.fail_create = true;
    REQUIRE(register_raw_type(create_failure_type, owner, create_failure));
    CHECK(tc_game_application_instance_create(create_failure_type, &error.value) == nullptr);
    CHECK_EQ(std::string(error.text), std::string("injected creation failure"));
    CHECK_EQ(tc_runtime_type_registry_instance_count(create_failure_type), 0u);
    REQUIRE_EQ(create_failure.events.size(), 1u);
    CHECK(create_failure.events[0] == Event::Create);

    RawCounters invalid_ops;
    invalid_ops.invalid_ops = true;
    REQUIRE(register_raw_type(invalid_ops_type, owner, invalid_ops));
    error.clear();
    CHECK(tc_game_application_instance_create(invalid_ops_type, &error.value) == nullptr);
    CHECK(error.text[0] != '\0');
    CHECK_EQ(tc_runtime_type_registry_instance_count(invalid_ops_type), 0u);
    REQUIRE_EQ(invalid_ops.events.size(), 2u);
    CHECK(invalid_ops.events[0] == Event::Create);
    CHECK(invalid_ops.events[1] == Event::Destroy);

    RawCounters start_failure;
    start_failure.fail_start = true;
    REQUIRE(register_raw_type(start_failure_type, owner, start_failure));
    error.clear();
    tc_game_application_instance* instance =
        tc_game_application_instance_create(start_failure_type, &error.value);
    REQUIRE(instance != nullptr);
    CHECK_FALSE(tc_game_application_instance_start(instance, &error.value));
    CHECK_EQ(std::string(error.text), std::string("injected start failure"));
    CHECK_EQ(tc_game_application_instance_state(instance), TC_GAME_APPLICATION_STATE_START_FAILED);
    CHECK_EQ(tc_runtime_type_registry_instance_count(start_failure_type), 1u);

    CHECK(tc_game_application_instance_destroy(&instance, &error.value));
    CHECK(instance == nullptr);
    CHECK_EQ(tc_runtime_type_registry_instance_count(start_failure_type), 0u);
    REQUIRE_EQ(start_failure.events.size(), 4u);
    CHECK(start_failure.events[0] == Event::Create);
    CHECK(start_failure.events[1] == Event::Start);
    CHECK(start_failure.events[2] == Event::Stop);
    CHECK(start_failure.events[3] == Event::Destroy);

    CHECK_EQ(tc_runtime_type_registry_unregister_owner(owner), 3u);
    tc_runtime_type_registry_clear();
}

TEST_CASE("C++ GameApplication adapter publishes C facet and contains exceptions") {
    reset_registry();
    constexpr const char* type_name = "CxxTestGameApplication";
    constexpr const char* owner = "cxx-game-application-test-module";
    CxxCounters counters;
    counters.throw_on_start = true;
    g_cxx_counters = &counters;

    auto descriptor = termin::runtime::GameApplicationTypeDescriptorBuilder::native<CxxApplication>(type_name, owner);
    REQUIRE(descriptor.commit());
    CHECK(tc_game_application_type_is_registered(type_name));
    CHECK_FALSE(tc_game_application_type_is_abstract(type_name));

    ErrorBuffer error;
    tc_game_application_instance* instance = tc_game_application_instance_create(type_name, &error.value);
    REQUIRE(instance != nullptr);
    CHECK_EQ(counters.constructed, 1);

    CHECK_FALSE(tc_game_application_instance_start(instance, &error.value));
    CHECK_EQ(std::string(error.text), std::string("injected C++ start exception"));
    CHECK_EQ(counters.started, 1);
    CHECK(tc_game_application_instance_destroy(&instance, &error.value));
    CHECK_EQ(counters.stopped, 1);
    CHECK_EQ(counters.destroyed, 1);
    CHECK_EQ(tc_runtime_type_registry_instance_count(type_name), 0u);

    CHECK_EQ(tc_runtime_type_registry_unregister_owner(owner), 1u);
    g_cxx_counters = nullptr;
    tc_runtime_type_registry_clear();
}
