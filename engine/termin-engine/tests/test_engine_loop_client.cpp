#include "guard_main.h"

#include <stdexcept>
#include <utility>
#include <cmath>
#include <vector>

#include <termin/engine/engine_core.hpp>

extern "C" {
#include <tc_profiler.h>
#include <core/tc_component.h>
}

namespace {

    termin::EngineLoopClient make_client(int& polls, int& continuation_checks, int& shutdowns) {
        return termin::EngineLoopClient{
            [&polls]() { ++polls; },
            [&continuation_checks]() {
                ++continuation_checks;
                return false;
            },
            [&shutdowns]() { ++shutdowns; },
        };
    }

    template <typename Exception, typename Callable> bool throws_as(Callable&& callable) {
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

    auto connection = engine.attach_loop_client(make_client(polls, continuation_checks, shutdowns));
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
    auto connection = engine.attach_loop_client(make_client(polls, continuation_checks, shutdowns));

    termin::EngineLoopClient incomplete;
    incomplete.poll_events = []() {
    };
    incomplete.should_continue = []() {
        return false;
    };
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
    auto first = engine.attach_loop_client(make_client(first_polls, first_checks, first_shutdowns));

    CHECK(throws_as<std::logic_error>([&]() {
        auto rejected = engine.attach_loop_client(make_client(second_polls, second_checks, second_shutdowns));
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

TEST_CASE("EngineCore invokes frame completion callbacks after profiler frames close") {
    termin::EngineCore engine;
    engine.set_target_fps(0.0);
    int polls = 0;
    int checks = 0;
    int shutdowns = 0;
    int completions = 0;
    bool callback_saw_open_frame = false;

    auto loop = engine.attach_loop_client(termin::EngineLoopClient{
        [&polls]() { ++polls; },
        [&checks]() { return ++checks < 3; },
        [&shutdowns]() { ++shutdowns; },
    });
    auto completion = engine.attach_frame_completion_callback([&]() {
        ++completions;
        callback_saw_open_frame = callback_saw_open_frame || tc_profiler_current_frame() != nullptr;
    });

    engine.run();

    CHECK_EQ(polls, 3);
    CHECK_EQ(completions, 2);
    CHECK_FALSE(callback_saw_open_frame);
    CHECK_EQ(shutdowns, 1);
    CHECK(loop.connected());
    CHECK(completion.connected());
}

TEST_CASE("EngineCore owns only one detachable frame completion callback") {
    termin::EngineCore engine;
    auto first = engine.attach_frame_completion_callback([]() {});
    CHECK(first.connected());
    CHECK(throws_as<std::logic_error>([&]() {
        auto rejected = engine.attach_frame_completion_callback([]() {});
        (void)rejected;
    }));

    first.detach();
    CHECK_FALSE(first.connected());
    auto replacement = engine.attach_frame_completion_callback([]() {});
    CHECK(replacement.connected());
}

TEST_CASE("Planned loop sleeps indefinitely when idle and services wakes without frames") {
    termin::EngineCore engine;
    engine.set_target_fps(0);
    double now = 0;
    int polls = 0, waits = 0, frames = 0, shutdowns = 0;
    bool request_frame = false;
    bool service_has_frame = false;
    auto connection = engine.attach_loop_client(termin::EngineLoopClient{
        .poll_events = [&]() { ++polls; service_has_frame |= tc_profiler_current_frame() != nullptr; },
        .should_continue = []() { return true; },
        .on_shutdown = [&]() { ++shutdowns; },
        .plan_work = [&](double) { return termin::EngineLoopPlan{.frame_requested = request_frame}; },
        .wait_until = [&](std::optional<double> deadline) {
            CHECK_FALSE(deadline.has_value());
            ++waits;
            if (waits == 1) { now = 60; request_frame = true; }
            else engine.stop();
        },
        .wake = []() {},
        .before_frame = [&](double dt) { CHECK_EQ(dt, 0.0); ++frames; },
        .after_frame = [&]() { CHECK_FALSE(engine.last_frame_rendered()); request_frame = false; },
        .monotonic_time = [&]() { return now; },
    });
    engine.run();
    CHECK_EQ(waits, 2);
    CHECK_EQ(frames, 1);
    CHECK_EQ(polls, 3);
    CHECK_EQ(shutdowns, 1);
    CHECK_FALSE(service_has_frame);
}

TEST_CASE("Service wakes do not bypass the requested frame cap") {
    termin::EngineCore engine;
    engine.set_target_fps(10);
    double now = 0;
    int waits = 0, frames = 0;
    auto connection = engine.attach_loop_client(termin::EngineLoopClient{
        .poll_events = []() {}, .should_continue = []() { return true; }, .on_shutdown = []() {},
        .plan_work = [](double) { return termin::EngineLoopPlan{.continuous_update = true}; },
        .wait_until = [&](std::optional<double> deadline) {
            REQUIRE(deadline.has_value());
            CHECK_EQ(*deadline, 0.1);
            now = ++waits == 1 ? 0.04 : *deadline;
        },
        .wake = []() {},
        .before_frame = [&](double dt) {
            if (++frames == 1) CHECK_EQ(dt, 0.0);
            else { CHECK_EQ(dt, 0.1); engine.stop(); }
        },
        .monotonic_time = [&]() { return now; },
    });
    engine.run();
    CHECK_EQ(waits, 2);
    CHECK_EQ(frames, 2);
}

TEST_CASE("Bounded service backlog is drained without manufacturing frames") {
    termin::EngineCore engine;
    int polls = 0, frames = 0, waits = 0;
    auto connection = engine.attach_loop_client(termin::EngineLoopClient{
        .poll_events = [&]() { ++polls; }, .should_continue = []() { return true; }, .on_shutdown = []() {},
        .plan_work = [&](double) { return termin::EngineLoopPlan{.immediate_work = polls < 3}; },
        .wait_until = [&](std::optional<double> deadline) { CHECK_FALSE(deadline); ++waits; engine.stop(); },
        .wake = []() {}, .before_frame = [&](double) { ++frames; },
    });
    engine.run();
    CHECK_EQ(polls, 3);
    CHECK_EQ(waits, 1);
    CHECK_EQ(frames, 0);
}

TEST_CASE("Planned loop uses earliest service deadline and stop wakes its host") {
    termin::EngineCore engine;
    double now = 0;
    int waits = 0, wakes = 0;
    auto connection = engine.attach_loop_client(termin::EngineLoopClient{
        .poll_events = []() {}, .should_continue = []() { return true; }, .on_shutdown = []() {},
        .plan_work = [](double) { return termin::EngineLoopPlan{.next_deadline = 12.0}; },
        .wait_until = [&](std::optional<double> deadline) {
            REQUIRE(deadline.has_value()); CHECK_EQ(*deadline, 12.0); ++waits; engine.stop();
        },
        .wake = [&]() { ++wakes; }, .monotonic_time = [&]() { return now; },
    });
    engine.run();
    CHECK_EQ(waits, 1);
    CHECK_EQ(wakes, 1);
    CHECK_FALSE(engine.is_running());
}

TEST_CASE("Partial planning contract is rejected") {
    termin::EngineCore engine;
    termin::EngineLoopClient client{[]() {}, []() { return true; }, []() {}};
    client.plan_work = [](double) { return termin::EngineLoopPlan{}; };
    CHECK(throws_as<std::invalid_argument>([&]() { auto connection = engine.attach_loop_client(client); }));
}

TEST_CASE("Scene simulation excludes idle time but preserves active elapsed time") {
    termin::EngineCore engine;
    engine.set_target_fps(10);
    const auto scene = engine.scene_manager.create_scene(termin::SceneKey("clock", termin::SceneRole::Authoring));
    tc_scene_set_mode(scene, TC_SCENE_MODE_STOP);
    tc_scene_set_fixed_timestep(scene, 0.05);
    struct Counters { std::vector<float> deltas; int fixed = 0; } counters;
    tc_component_vtable vtable{};
    vtable.update = [](tc_component* component, float dt) {
        static_cast<Counters*>(component->body)->deltas.push_back(dt);
    };
    vtable.fixed_update = [](tc_component* component, float) { ++static_cast<Counters*>(component->body)->fixed; };
    tc_component component;
    tc_component_init(&component, &vtable);
    component.body = &counters;
    component._started = true;
    tc_scene_register_component(scene, &component);
    double now = 0;
    int sleeps = 0, polls = 0;
    auto connection = engine.attach_loop_client(termin::EngineLoopClient{
        .poll_events = [&]() { if (++polls > 20) engine.stop(); },
        .should_continue = []() { return true; }, .on_shutdown = []() {},
        .plan_work = [](double) { return termin::EngineLoopPlan{}; },
        .wait_until = [&](std::optional<double> deadline) {
            if (deadline) now = *deadline;
            else {
                now = ++sleeps == 1 ? 60 : 180;
                tc_component_set_active_in_editor(&component, true);
            }
        },
        .wake = []() {},
        .after_frame = [&]() {
            if (counters.deltas.size() == 2) tc_component_set_active_in_editor(&component, false);
            if (counters.deltas.size() == 3) engine.stop();
        },
        .monotonic_time = [&]() { return now; },
    });
    engine.run();
    REQUIRE_EQ(counters.deltas.size(), 3u);
    CHECK_EQ(counters.deltas[0], 0.0f);
    CHECK(std::abs(counters.deltas[1] - 0.1f) < 0.00001f);
    CHECK_EQ(counters.deltas[2], 0.0f);
    CHECK(counters.fixed <= 2);
    CHECK_EQ(sleeps, 2);
    tc_scene_unregister_component(scene, &component);
}

TEST_CASE("A scene invalidated by before_frame is processed in that frame") {
    termin::EngineCore engine;
    engine.set_target_fps(0);
    int rendered = 0, frames = 0;
    engine.scene_manager.set_on_after_render([&]() { ++rendered; });
    auto connection = engine.attach_loop_client(termin::EngineLoopClient{
        .poll_events = []() {}, .should_continue = []() { return true; }, .on_shutdown = []() {},
        .plan_work = [](double) { return termin::EngineLoopPlan{.frame_requested = true}; },
        .wait_until = [&](std::optional<double>) { engine.stop(); }, .wake = []() {},
        .before_frame = [&](double) { ++frames; engine.scene_manager.request_render(); },
        .after_frame = [&]() { CHECK(engine.last_frame_rendered()); engine.stop(); },
    });
    engine.run();
    CHECK_EQ(frames, 1);
    CHECK_EQ(rendered, 1);
}

TEST_CASE("A service timer preempts frame waiting without creating an early frame") {
    termin::EngineCore engine;
    engine.set_target_fps(10);
    double now = 0;
    int frames = 0, waits = 0;
    bool timer_pending = true;
    auto connection = engine.attach_loop_client(termin::EngineLoopClient{
        .poll_events = [&]() { if (now >= 0.04) timer_pending = false; },
        .should_continue = []() { return true; }, .on_shutdown = []() {},
        .plan_work = [&](double) {
            return termin::EngineLoopPlan{.continuous_update = true,
                .next_deadline = timer_pending ? std::optional<double>(0.04) : std::nullopt};
        },
        .wait_until = [&](std::optional<double> deadline) {
            REQUIRE(deadline.has_value());
            CHECK_EQ(*deadline, ++waits == 1 ? 0.04 : 0.1);
            now = *deadline;
        }, .wake = []() {},
        .before_frame = [&](double) { if (++frames == 2) engine.stop(); },
        .monotonic_time = [&]() { return now; },
    });
    engine.run();
    CHECK_EQ(frames, 2);
    CHECK_EQ(waits, 2);
}

GUARD_TEST_MAIN();
