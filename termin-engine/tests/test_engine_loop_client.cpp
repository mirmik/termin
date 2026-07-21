#include "guard_main.h"

#include <stdexcept>
#include <utility>

#include <termin/engine/engine_core.hpp>

namespace {

termin::EngineLoopClient make_client(
    int& polls,
    int& continuation_checks,
    int& shutdowns
) {
    return termin::EngineLoopClient{
        [&polls]() { ++polls; },
        [&continuation_checks]() {
            ++continuation_checks;
            return false;
        },
        [&shutdowns]() { ++shutdowns; },
    };
}

template <typename Exception, typename Callable>
bool throws_as(Callable&& callable) {
    try {
        std::forward<Callable>(callable)();
    } catch (const Exception&) {
        return true;
    } catch (...) {
        return false;
    }
    return false;
}

} // namespace

TEST_CASE("EngineCore atomically attaches and runs one complete loop client") {
    termin::EngineCore engine;
    engine.set_target_fps(0.0);
    int polls = 0;
    int continuation_checks = 0;
    int shutdowns = 0;

    auto connection = engine.attach_loop_client(
        make_client(polls, continuation_checks, shutdowns)
    );
    REQUIRE(connection.connected());

    engine.run();

    CHECK_EQ(polls, 1);
    CHECK_EQ(continuation_checks, 1);
    CHECK_EQ(shutdowns, 1);
    CHECK_FALSE(engine.is_running());
    CHECK(connection.connected());
}

TEST_CASE("EngineCore rejects incomplete loop clients without changing its connection") {
    termin::EngineCore engine;
    int polls = 0;
    int continuation_checks = 0;
    int shutdowns = 0;
    auto connection = engine.attach_loop_client(
        make_client(polls, continuation_checks, shutdowns)
    );

    termin::EngineLoopClient incomplete;
    incomplete.poll_events = []() {};
    incomplete.should_continue = []() { return false; };
    CHECK(throws_as<std::invalid_argument>([&]() {
        auto rejected = engine.attach_loop_client(std::move(incomplete));
        (void)rejected;
    }));
    CHECK(connection.connected());
}

TEST_CASE("EngineCore refuses to run without an attached loop client") {
    termin::EngineCore engine;

    CHECK(throws_as<std::logic_error>([&]() { engine.run(); }));
    CHECK_FALSE(engine.is_running());
}

TEST_CASE("EngineCore refuses a second client without replacing the first") {
    termin::EngineCore engine;
    int first_polls = 0;
    int first_checks = 0;
    int first_shutdowns = 0;
    int second_polls = 0;
    int second_checks = 0;
    int second_shutdowns = 0;
    auto first = engine.attach_loop_client(
        make_client(first_polls, first_checks, first_shutdowns)
    );

    CHECK(throws_as<std::logic_error>([&]() {
        auto rejected = engine.attach_loop_client(
            make_client(second_polls, second_checks, second_shutdowns)
        );
        (void)rejected;
    }));
    REQUIRE(first.connected());

    engine.set_target_fps(0.0);
    engine.run();
    CHECK_EQ(first_polls, 1);
    CHECK_EQ(first_shutdowns, 1);
    CHECK_EQ(second_polls, 0);
    CHECK_EQ(second_shutdowns, 0);
}

TEST_CASE("Detaching a connection removes the whole client and permits replacement") {
    termin::EngineCore engine;
    int polls = 0;
    int checks = 0;
    int shutdowns = 0;
    auto first = engine.attach_loop_client(make_client(polls, checks, shutdowns));

    first.detach();
    CHECK_FALSE(first.connected());

    auto replacement = engine.attach_loop_client(make_client(polls, checks, shutdowns));
    CHECK(replacement.connected());
}

TEST_CASE("A connection is harmless after its EngineCore has been destroyed") {
    termin::EngineLoopClientConnection connection;
    int polls = 0;
    int checks = 0;
    int shutdowns = 0;
    {
        termin::EngineCore engine;
        connection = engine.attach_loop_client(make_client(polls, checks, shutdowns));
        REQUIRE(connection.connected());
    }

    CHECK_FALSE(connection.connected());
    connection.detach();
    CHECK_FALSE(connection.connected());
}

GUARD_TEST_MAIN();
