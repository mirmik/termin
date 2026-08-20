#include "guard_main.h"

GUARD_TEST_MAIN();

#include <string>
#include <vector>

#include <inspect/tc_runtime_type_registry.h>
#include <termin/engine/engine_core.hpp>
#include <termin/entity/component.hpp>
#include <termin/tc_scene.hpp>

extern "C" {
#include <core/tc_scene_extension.h>
#include <core/tc_scene_extension_ids.h>
#include <core/tc_scene_render_mount.h>
#include <render/tc_display.h>
#include <tc_viewport_config.h>
}

namespace {

    enum class Event {
        Construct,
        Start,
        Stop,
        Destroy,
        SceneClose,
    };

    struct SessionProbe {
        std::vector<Event> events;
        termin::EngineCore* engine = nullptr;
        bool fail_start = false;
        bool fail_stop = false;
        bool reenter = false;
        bool reentrant_begin_result = true;
        bool reentrant_end_result = true;
        bool shutdown_during_start_result = true;
        bool shutdown_during_stop_result = true;
        size_t scenes_during_start = 99;
        tc_scene_handle runtime_scene = TC_SCENE_HANDLE_INVALID;
        void* controller_object = nullptr;
        termin::WorldContext start_context;
        termin::WorldContext stop_context;
        bool scene_context_absent_during_stop = false;
    };

    SessionProbe* g_probe = nullptr;

    class SessionController final : public termin::WorldController {
    public:
        SessionController() {
            g_probe->controller_object = this;
            g_probe->events.push_back(Event::Construct);
        }

        ~SessionController() override {
            g_probe->events.push_back(Event::Destroy);
        }

        bool start(termin::WorldContext context, std::string& error) override {
            g_probe->events.push_back(Event::Start);
            g_probe->scenes_during_start = g_probe->engine->scene_manager.scene_names().size();
            CHECK(context.valid());
            g_probe->start_context = context;
            if (g_probe->reenter) {
                g_probe->reentrant_begin_result = g_probe->engine->begin_session();
                g_probe->shutdown_during_start_result = g_probe->engine->shutdown();
            }
            if (g_probe->fail_start) {
                error = "injected session start failure";
                return false;
            }
            return true;
        }

        bool stop(termin::WorldContext context, std::string& error) override {
            g_probe->events.push_back(Event::Stop);
            CHECK(context.valid());
            g_probe->stop_context = context;
            if (tc_scene_handle_valid(g_probe->runtime_scene)) {
                g_probe->scene_context_absent_during_stop =
                    !termin::WorldContext::from_scene(g_probe->runtime_scene).valid();
            }
            if (g_probe->reenter) {
                g_probe->reentrant_end_result = g_probe->engine->end_session();
                g_probe->shutdown_during_stop_result = g_probe->engine->shutdown();
            }
            if (g_probe->fail_stop) {
                error = "injected session stop failure";
                return false;
            }
            return true;
        }
    };

    constexpr const char* kType = "EngineRuntimeSessionController";
    constexpr const char* kOwner = "engine-runtime-session-test";

    void register_controller() {
        tc_runtime_type_registry_clear();
        REQUIRE(tc_world_controller_registry_init());
        auto descriptor =
            termin::WorldControllerTypeDescriptorBuilder::native<SessionController>(kType, kOwner);
        REQUIRE(descriptor.commit());
    }

    termin::WorldControllerInstance create_controller() {
        std::string error;
        auto controller = termin::WorldControllerInstance::create(kType, error);
        REQUIRE(controller.valid());
        CHECK(error.empty());
        return controller;
    }

    class ContextLifecycleProbe final : public termin::CxxComponent {
    public:
        ContextLifecycleProbe()
            : CxxComponent("ContextLifecycleProbe") {}

        void start() override {
            start_context = termin::WorldContext::require_from_component(
                tc_component_ptr(), "ContextLifecycleProbe::start");
        }

        void on_scene_active() override {
            active_context = termin::WorldContext::require_from_component(
                tc_component_ptr(), "ContextLifecycleProbe::on_scene_active");
        }

        termin::WorldContext start_context;
        termin::WorldContext active_context;
    };

    class PrimaryTransitionProbe final : public termin::CxxComponent {
    public:
        PrimaryTransitionProbe(std::vector<std::string>& events, std::string label)
            : CxxComponent("PrimaryTransitionProbe"),
              _events(events),
              _label(std::move(label)) {
            set_has_update(true);
        }

        void on_scene_active() override {
            _events.push_back(_label + ":active");
        }

        void on_scene_inactive() override {
            _events.push_back(_label + ":inactive");
        }

        void update(float) override {
            _events.push_back(_label + ":update");
            if (tc_scene_handle_valid(request_target)) {
                termin::WorldContext context = termin::WorldContext::require_from_component(
                    tc_component_ptr(), "PrimaryTransitionProbe::update");
                CHECK(context.request_primary_scene(request_target));
                request_target = TC_SCENE_HANDLE_INVALID;
            }
        }

        tc_scene_handle request_target = TC_SCENE_HANDLE_INVALID;

    private:
        std::vector<std::string>& _events;
        std::string _label;
    };

    PrimaryTransitionProbe* add_transition_probe(termin::TcSceneRef scene,
                                                 std::vector<std::string>& events,
                                                 const std::string& label) {
        termin::Entity entity = scene.create_entity(label);
        auto* probe = new PrimaryTransitionProbe(events, label);
        entity.add_component_ptr(probe->tc_component_ptr());
        return probe;
    }

} // namespace

TEST_CASE("EngineCore repeatedly owns explicit null RuntimeSessions") {
    termin::EngineCore engine;
    termin::EngineCore independent_engine;
    CHECK_FALSE(engine.has_runtime_session());
    CHECK(engine.begin_session());
    CHECK(independent_engine.begin_session());
    CHECK(engine.has_runtime_session());
    CHECK(independent_engine.has_runtime_session());
    CHECK_FALSE(engine.begin_session());
    CHECK(engine.end_session());
    CHECK_FALSE(engine.has_runtime_session());
    CHECK(independent_engine.has_runtime_session());
    CHECK(independent_engine.end_session());
    CHECK_FALSE(engine.end_session());
    CHECK(engine.begin_session());
    CHECK(engine.end_session());
    CHECK(engine.shutdown());
    CHECK_FALSE(engine.begin_session());
}

TEST_CASE("EngineCore consumes and supervises one native WorldController") {
    register_controller();
    termin::EngineCore engine;
    SessionProbe probe;
    probe.engine = &engine;
    probe.reenter = true;
    g_probe = &probe;
    auto controller = create_controller();
    CHECK_EQ(tc_runtime_type_registry_instance_count(kType), 1u);

    CHECK(engine.begin_session(std::move(controller)));
    CHECK_FALSE(controller.valid());
    CHECK(engine.has_runtime_session());
    CHECK_EQ(probe.scenes_during_start, 0u);
    CHECK_FALSE(probe.reentrant_begin_result);
    CHECK_FALSE(probe.shutdown_during_start_result);
    CHECK_FALSE(tc_runtime_type_registry_prepare_owner_unload(kOwner, nullptr));

    engine.scene_manager.set_on_before_scene_close(
        [&probe](const std::string&) { probe.events.push_back(Event::SceneClose); });
    probe.runtime_scene = engine.scene_manager.create_scene("runtime-scene");
    REQUIRE(engine.bind_runtime_scene(probe.runtime_scene));
    termin::WorldContext scene_context = termin::WorldContext::from_scene(probe.runtime_scene);
    CHECK(scene_context.valid());
    CHECK(scene_context == probe.start_context);
    auto controller_ref = scene_context.controller();
    REQUIRE(controller_ref.has_value());
    CHECK(controller_ref->valid());
    CHECK_EQ(std::string(controller_ref->type_name()), std::string(kType));
    CHECK_EQ(static_cast<void*>(controller_ref->object_as<SessionController>()),
             probe.controller_object);
    CHECK(engine.shutdown());
    CHECK_FALSE(engine.has_runtime_session());
    CHECK_FALSE(probe.reentrant_end_result);
    CHECK_FALSE(probe.shutdown_during_stop_result);
    CHECK(probe.scene_context_absent_during_stop);
    CHECK(probe.start_context == probe.stop_context);
    CHECK_FALSE(probe.start_context.valid());
    CHECK_FALSE(scene_context.valid());
    CHECK_FALSE(controller_ref->valid());
    CHECK(controller_ref->object() == nullptr);
    CHECK_EQ(tc_runtime_type_registry_instance_count(kType), 0u);
    CHECK(tc_runtime_type_registry_prepare_owner_unload(kOwner, nullptr));

    REQUIRE_EQ(probe.events.size(), 5u);
    CHECK(probe.events[0] == Event::Construct);
    CHECK(probe.events[1] == Event::Start);
    CHECK(probe.events[2] == Event::Stop);
    CHECK(probe.events[3] == Event::Destroy);
    CHECK(probe.events[4] == Event::SceneClose);
    tc_runtime_type_registry_clear();
}

TEST_CASE("RuntimeSession start failure destroys its controller and leaves no active run") {
    register_controller();
    termin::EngineCore engine;
    SessionProbe probe;
    probe.engine = &engine;
    probe.fail_start = true;
    g_probe = &probe;
    auto controller = create_controller();

    CHECK_FALSE(engine.begin_session(std::move(controller)));
    CHECK_FALSE(controller.valid());
    CHECK_FALSE(engine.has_runtime_session());
    CHECK_EQ(tc_runtime_type_registry_instance_count(kType), 0u);
    REQUIRE_EQ(probe.events.size(), 4u);
    CHECK(probe.events[0] == Event::Construct);
    CHECK(probe.events[1] == Event::Start);
    CHECK(probe.events[2] == Event::Stop);
    CHECK(probe.events[3] == Event::Destroy);
    CHECK(engine.begin_session());
    CHECK(engine.end_session());
    tc_runtime_type_registry_clear();
}

TEST_CASE("RuntimeSession reports stop failure after releasing controller ownership") {
    register_controller();
    termin::EngineCore engine;
    SessionProbe probe;
    probe.engine = &engine;
    probe.fail_stop = true;
    g_probe = &probe;
    auto controller = create_controller();

    CHECK(engine.begin_session(std::move(controller)));
    CHECK_FALSE(engine.end_session());
    CHECK_FALSE(engine.has_runtime_session());
    CHECK_EQ(tc_runtime_type_registry_instance_count(kType), 0u);
    CHECK(engine.shutdown());
    tc_runtime_type_registry_clear();
}

TEST_CASE("Null RuntimeSession binds transient scene context before component lifecycle") {
    termin::EngineCore engine;
    tc_scene_handle scene_handle = engine.scene_manager.create_scene("null-controller-runtime-scene");
    REQUIRE(tc_scene_alive(scene_handle));
    termin::TcSceneRef scene(scene_handle);
    termin::Entity entity = scene.create_entity("context-probe");
    auto* component = new ContextLifecycleProbe();
    entity.add_component_ptr(component->tc_component_ptr());

    CHECK_FALSE(termin::WorldContext::from_scene(scene_handle).valid());
    CHECK_FALSE(tc_scene_ext_has(scene_handle, TC_SCENE_EXT_TYPE_WORLD_CONTEXT));
    CHECK(engine.begin_session());
    CHECK_FALSE(termin::WorldContext::from_scene(scene_handle).valid());
    REQUIRE(engine.bind_runtime_scene(scene_handle));
    CHECK(tc_scene_ext_has(scene_handle, TC_SCENE_EXT_TYPE_WORLD_CONTEXT));

    termin::WorldContext retained = termin::WorldContext::from_scene(scene_handle);
    REQUIRE(retained.valid());
    CHECK_FALSE(retained.controller().has_value());
    CHECK(scene.to_json_string().find("world_context") == std::string::npos);

    engine.scene_manager.set_mode("null-controller-runtime-scene", TC_SCENE_MODE_PLAY);
    CHECK(component->active_context.valid());
    CHECK(component->active_context == retained);
    engine.scene_manager.tick(0.016);
    CHECK(component->start_context.valid());
    CHECK(component->start_context == retained);

    CHECK(engine.end_session());
    CHECK(tc_scene_alive(scene_handle));
    CHECK_FALSE(tc_scene_ext_has(scene_handle, TC_SCENE_EXT_TYPE_WORLD_CONTEXT));
    CHECK_FALSE(termin::WorldContext::from_scene(scene_handle).valid());
    CHECK_FALSE(retained.valid());
    CHECK_FALSE(component->start_context.valid());
    CHECK(engine.shutdown());
}

TEST_CASE("RuntimeSession rejects unregistered scenes and explicit unbind removes only its link") {
    termin::EngineCore engine;
    termin::TcSceneRef external = termin::TcSceneRef::create("unregistered-runtime-scene");
    REQUIRE(external.valid());
    REQUIRE(engine.begin_session());
    CHECK_FALSE(engine.bind_runtime_scene(external.handle()));

    engine.scene_manager.register_scene("registered-runtime-scene", external.handle());
    REQUIRE(engine.bind_runtime_scene(external.handle()));
    termin::WorldContext retained = termin::WorldContext::from_scene(external.handle());
    REQUIRE(retained.valid());
    CHECK(engine.unbind_runtime_scene(external.handle()));
    CHECK_FALSE(termin::WorldContext::from_scene(external.handle()).valid());
    CHECK(retained.valid());
    CHECK_FALSE(engine.unbind_runtime_scene(external.handle()));

    engine.scene_manager.unregister_scene("registered-runtime-scene");
    CHECK(engine.end_session());
    CHECK_FALSE(retained.valid());
    external.destroy();
    CHECK(engine.shutdown());
}

TEST_CASE("Primary scene requests commit at the next EngineCore tick safe point") {
    tc_scene_render_mount_extension_init();
    termin::EngineCore engine;
    termin::TcSceneRef first(engine.scene_manager.create_scene("primary-first"));
    termin::TcSceneRef second(engine.scene_manager.create_scene("primary-second"));
    termin::TcSceneRef auxiliary(engine.scene_manager.create_scene("primary-auxiliary"));
    REQUIRE(first.valid());
    REQUIRE(second.valid());
    REQUIRE(auxiliary.valid());
    (void)engine.rendering_manager.attach_scene_full(auxiliary.handle());
    REQUIRE(engine.render_topology.is_attached(auxiliary.handle()));

    std::vector<std::string> events;
    PrimaryTransitionProbe* first_probe = add_transition_probe(first, events, "first");
    (void)add_transition_probe(second, events, "second");

    REQUIRE(engine.begin_session());
    REQUIRE(engine.bind_runtime_scene(first.handle()));
    REQUIRE(engine.bind_runtime_scene(second.handle()));
    termin::WorldContext context = termin::WorldContext::require_from_scene(
        first.handle(), "primary transition test");
    CHECK_FALSE(tc_scene_handle_valid(context.primary_scene()));
    REQUIRE(context.request_primary_scene(first.handle()));
    CHECK_FALSE(context.request_primary_scene(second.handle()));

    CHECK(engine.tick_and_render(0.016));
    CHECK(tc_scene_handle_eq(context.primary_scene(), first.handle()));
    CHECK(tc_scene_get_mode(first.handle()) == TC_SCENE_MODE_PLAY);
    CHECK(tc_scene_get_mode(second.handle()) == TC_SCENE_MODE_INACTIVE);
    CHECK(engine.render_topology.is_attached(first.handle()));
    CHECK_FALSE(engine.render_topology.is_attached(second.handle()));
    CHECK(engine.render_topology.is_attached(auxiliary.handle()));
    const std::vector<std::string> first_frame_events{"first:active", "first:update"};
    CHECK(events == first_frame_events);
    CHECK(context.request_primary_scene(first.handle()));

    first_probe->request_target = second.handle();
    events.clear();
    CHECK(engine.tick_and_render(0.016));
    CHECK(tc_scene_handle_eq(context.primary_scene(), first.handle()));
    CHECK(events == std::vector<std::string>{"first:update"});

    events.clear();
    CHECK(engine.tick_and_render(0.016));
    CHECK(tc_scene_handle_eq(context.primary_scene(), second.handle()));
    CHECK(tc_scene_get_mode(first.handle()) == TC_SCENE_MODE_INACTIVE);
    CHECK(tc_scene_get_mode(second.handle()) == TC_SCENE_MODE_PLAY);
    CHECK_FALSE(engine.render_topology.is_attached(first.handle()));
    CHECK(engine.render_topology.is_attached(second.handle()));
    CHECK(engine.render_topology.is_attached(auxiliary.handle()));
    const std::vector<std::string> transition_frame_events{
        "first:inactive", "second:active", "second:update"};
    CHECK(events == transition_frame_events);

    REQUIRE(context.request_primary_scene(first.handle()));
    CHECK(engine.tick_and_render(0.016));
    CHECK(tc_scene_handle_eq(context.primary_scene(), first.handle()));
    CHECK(engine.render_topology.is_attached(first.handle()));
    CHECK_FALSE(engine.render_topology.is_attached(second.handle()));
    CHECK(engine.render_topology.is_attached(auxiliary.handle()));
    CHECK(engine.end_session());
    CHECK_FALSE(tc_scene_handle_valid(context.primary_scene()));
    CHECK(tc_scene_get_mode(first.handle()) == TC_SCENE_MODE_INACTIVE);
    CHECK_FALSE(engine.render_topology.is_attached(first.handle()));
    CHECK(engine.render_topology.is_attached(auxiliary.handle()));
    CHECK(engine.shutdown());
}

TEST_CASE("Primary scene preparation failure preserves the old world and permits retry") {
    tc_scene_render_mount_extension_init();
    termin::EngineCore engine;
    termin::TcSceneRef first(engine.scene_manager.create_scene("prepare-old"));
    termin::TcSceneRef broken(engine.scene_manager.create_scene("prepare-broken"));
    termin::TcSceneRef recovery(engine.scene_manager.create_scene("prepare-recovery"));
    REQUIRE(first.valid());
    REQUIRE(broken.valid());
    REQUIRE(recovery.valid());

    tc_viewport_config viewport;
    tc_viewport_config_init(&viewport);
    viewport.name = "BrokenViewport";
    viewport.display_name = "UnavailableDisplay";
    viewport.enabled = true;
    tc_scene_add_viewport_config(broken.handle(), &viewport);
    engine.rendering_manager.set_display_factory(
        [](const std::string&) { return TC_DISPLAY_HANDLE_INVALID; });

    REQUIRE(engine.begin_session());
    REQUIRE(engine.bind_runtime_scene(first.handle()));
    REQUIRE(engine.bind_runtime_scene(broken.handle()));
    REQUIRE(engine.bind_runtime_scene(recovery.handle()));
    termin::WorldContext context = termin::WorldContext::require_from_scene(
        first.handle(), "primary prepare rollback test");
    REQUIRE(context.request_primary_scene(first.handle()));
    CHECK(engine.tick_and_render(0.0));
    REQUIRE(tc_scene_handle_eq(context.primary_scene(), first.handle()));

    REQUIRE(context.request_primary_scene(broken.handle()));
    CHECK(engine.tick_and_render(0.0));
    CHECK(tc_scene_handle_eq(context.primary_scene(), first.handle()));
    CHECK(tc_scene_get_mode(first.handle()) == TC_SCENE_MODE_PLAY);
    CHECK(tc_scene_get_mode(broken.handle()) == TC_SCENE_MODE_INACTIVE);
    CHECK(engine.render_topology.is_attached(first.handle()));
    CHECK_FALSE(engine.render_topology.is_attached(broken.handle()));

    REQUIRE(context.request_primary_scene(recovery.handle()));
    CHECK(engine.tick_and_render(0.0));
    CHECK(tc_scene_handle_eq(context.primary_scene(), recovery.handle()));
    CHECK_FALSE(engine.render_topology.is_attached(first.handle()));
    CHECK(engine.render_topology.is_attached(recovery.handle()));

    tc_scene_set_mode(recovery.handle(), TC_SCENE_MODE_STOP);
    REQUIRE(context.request_primary_scene(first.handle()));
    CHECK(engine.tick_and_render(0.0));
    CHECK(tc_scene_handle_eq(context.primary_scene(), first.handle()));
    CHECK(tc_scene_get_mode(first.handle()) == TC_SCENE_MODE_STOP);
    CHECK(engine.end_session());
    CHECK(engine.shutdown());
}

TEST_CASE("RuntimeSession cancellation drops pending primary work during shutdown") {
    tc_scene_render_mount_extension_init();
    termin::EngineCore engine;
    termin::TcSceneRef scene(engine.scene_manager.create_scene("pending-at-shutdown"));
    REQUIRE(scene.valid());
    REQUIRE(engine.begin_session());
    REQUIRE(engine.bind_runtime_scene(scene.handle()));
    termin::WorldContext context = termin::WorldContext::require_from_scene(
        scene.handle(), "pending shutdown test");
    REQUIRE(context.request_primary_scene(scene.handle()));
    CHECK(engine.end_session());
    CHECK_FALSE(context.valid());
    CHECK(tc_scene_get_mode(scene.handle()) == TC_SCENE_MODE_INACTIVE);
    CHECK_FALSE(engine.render_topology.is_attached(scene.handle()));
    CHECK(engine.shutdown());
}

TEST_CASE("Blocking EngineCore loop processes primary requests before each scene tick") {
    tc_scene_render_mount_extension_init();
    termin::EngineCore engine;
    engine.set_target_fps(0.0);
    termin::TcSceneRef first(engine.scene_manager.create_scene("loop-primary-first"));
    termin::TcSceneRef second(engine.scene_manager.create_scene("loop-primary-second"));
    REQUIRE(first.valid());
    REQUIRE(second.valid());

    std::vector<std::string> events;
    PrimaryTransitionProbe* first_probe = add_transition_probe(first, events, "loop-first");
    (void)add_transition_probe(second, events, "loop-second");
    first_probe->request_target = second.handle();

    REQUIRE(engine.begin_session());
    REQUIRE(engine.bind_runtime_scene(first.handle()));
    REQUIRE(engine.bind_runtime_scene(second.handle()));
    termin::WorldContext context = termin::WorldContext::require_from_scene(
        first.handle(), "blocking loop transition test");
    REQUIRE(context.request_primary_scene(first.handle()));

    int continuation_checks = 0;
    int shutdowns = 0;
    std::vector<tc_scene_handle> completed_primary_scenes;
    auto loop = engine.attach_loop_client(termin::EngineLoopClient{
        []() {},
        [&continuation_checks]() { return ++continuation_checks < 3; },
        [&shutdowns]() { ++shutdowns; },
    });
    auto completion = engine.attach_frame_completion_callback([&]() {
        completed_primary_scenes.push_back(context.primary_scene());
    });

    engine.run();

    REQUIRE_EQ(completed_primary_scenes.size(), 2u);
    CHECK(tc_scene_handle_eq(completed_primary_scenes[0], first.handle()));
    CHECK(tc_scene_handle_eq(completed_primary_scenes[1], second.handle()));
    CHECK_EQ(shutdowns, 1);
    CHECK(loop.connected());
    CHECK(completion.connected());
    CHECK(engine.end_session());
    CHECK(engine.shutdown());
}

TEST_CASE("RuntimeSession lifecycle changes are safe in the owning loop poll phase") {
    tc_scene_render_mount_extension_init();
    termin::EngineCore engine;
    engine.set_target_fps(0.0);
    termin::TcSceneRef scene(engine.scene_manager.create_scene("poll-owned-session"));
    REQUIRE(scene.valid());

    int polls = 0;
    int completions = 0;
    int shutdowns = 0;
    termin::WorldContext context;
    auto loop = engine.attach_loop_client(termin::EngineLoopClient{
        [&]() {
            ++polls;
            if (polls == 1) {
                REQUIRE(engine.begin_session());
                REQUIRE(engine.bind_runtime_scene(scene.handle()));
                context = termin::WorldContext::require_from_scene(
                    scene.handle(), "loop poll session test");
                REQUIRE(context.request_primary_scene(scene.handle()));
            } else if (polls == 2) {
                CHECK(tc_scene_handle_eq(context.primary_scene(), scene.handle()));
                CHECK(engine.end_session());
            }
        },
        [&]() { return polls < 2; },
        [&]() { ++shutdowns; },
    });
    auto completion = engine.attach_frame_completion_callback([&]() {
        ++completions;
        CHECK_FALSE(engine.end_session());
        CHECK(engine.has_runtime_session());
    });

    engine.run();

    CHECK_EQ(polls, 2);
    CHECK_EQ(completions, 1);
    CHECK_EQ(shutdowns, 1);
    CHECK_FALSE(engine.has_runtime_session());
    CHECK_FALSE(context.valid());
    CHECK(loop.connected());
    CHECK(completion.connected());
    CHECK(engine.shutdown());
}
