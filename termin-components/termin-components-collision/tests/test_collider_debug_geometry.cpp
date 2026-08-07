#include "guard_main.h"

GUARD_TEST_MAIN();

#include <components/collider_component.hpp>
#include <inspect/tc_inspect_component_adapter.h>
#include <inspect/tc_inspect_init.h>
#include <termin/render/render_lifecycle.hpp>
#include <termin/tc_scene.hpp>
#include <termin_collision/termin_collision.h>
#include <termin_scene/internal/tc_scene_extension_registry.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_primitive_mesh.h>

extern "C" {
#include <core/tc_debug_geometry.h>
#include <core/tc_scene_render_mount.h>
}

namespace {

    void initialize_runtime() {
        static const bool initialized = [] {
            tc_inspect_kind_core_init();
            tc_inspect_component_adapter_init();
            tc_scene_ext_registry_init();
            tc_scene_render_mount_extension_init();
            tc_mesh_init();
            termin_collision_runtime_init();
            termin::register_builtin_scene_component_types();
            termin::ColliderComponent::register_type();
            return true;
        }();
        (void)initialized;
    }

    void prepare_render(const termin::TcSceneRef& scene) {
        const termin::RenderPrepareContext context(scene.handle());
        tc_scene_render_mount_prepare(scene.handle(), reinterpret_cast<const tc_render_prepare_context*>(&context));
    }

    std::size_t count_kind(tc_scene_handle scene, tc_debug_geometry_primitive_kind kind) {
        std::size_t result = 0;
        for (std::size_t index = 0; index < tc_scene_debug_geometry_primitive_count(scene); ++index) {
            const tc_debug_geometry_primitive* primitive = tc_scene_debug_geometry_primitive_at(scene, index);
            REQUIRE(primitive != nullptr);
            if (primitive->kind == kind)
                ++result;
        }
        return result;
    }

} // namespace

TEST_CASE("colliders publish registry-controlled canonical debug primitives") {
    using namespace termin;

    initialize_runtime();
    const tc_debug_geometry_type_id type_id = tc_debug_geometry_type_find("physics.colliders");
    REQUIRE(type_id != TC_DEBUG_GEOMETRY_TYPE_INVALID);

    TcSceneRef scene = TcSceneRef::create("collider debug geometry");

    Entity box_entity = scene.create_entity("Box");
    box_entity.transform().set_local_position({4.0, 0.0, 0.0});
    auto* box = new ColliderComponent();
    box->collider_offset_enabled = true;
    box->collider_offset_position = {1.0, 2.0, 3.0};
    box_entity.add_component(box);

    Entity sphere_entity = scene.create_entity("Sphere");
    auto* sphere = new ColliderComponent();
    sphere_entity.add_component(sphere);
    sphere->set_collider_type("Sphere");

    Entity capsule_entity = scene.create_entity("Capsule");
    auto* capsule = new ColliderComponent();
    capsule_entity.add_component(capsule);
    capsule->set_collider_type("Capsule");

    Entity hull_entity = scene.create_entity("Convex Hull");
    auto* hull = new ColliderComponent();
    hull_entity.add_component(hull);
    hull->set_convex_hull_mesh(TcMesh(tc_primitive_unit_cube()));
    hull->set_collider_type("ConvexHull");

    REQUIRE(tc_scene_render_mount_ensure(scene.handle()));
    int attachment_storage = 0;
    const auto* attachment = reinterpret_cast<const tc_render_attachment_context*>(&attachment_storage);
    tc_scene_render_mount_notify_attach(scene.handle(), attachment);

    // Colliders preserve the editor's previous opt-in default.
    prepare_render(scene);
    CHECK(tc_scene_debug_geometry_primitive_count(scene.handle()) == 0U);

    REQUIRE(tc_scene_debug_geometry_set_enabled(scene.handle(), type_id, true));
    prepare_render(scene);
    CHECK(count_kind(scene.handle(), TC_DEBUG_GEOMETRY_WIRE_BOX) == 1U);
    CHECK(count_kind(scene.handle(), TC_DEBUG_GEOMETRY_WIRE_SPHERE) == 1U);
    CHECK(count_kind(scene.handle(), TC_DEBUG_GEOMETRY_WIRE_CAPSULE) == 1U);
    CHECK(count_kind(scene.handle(), TC_DEBUG_GEOMETRY_LINE) > 0U);

    const tc_debug_geometry_primitive* box_primitive = nullptr;
    for (std::size_t index = 0; index < tc_scene_debug_geometry_primitive_count(scene.handle()); ++index) {
        const tc_debug_geometry_primitive* primitive = tc_scene_debug_geometry_primitive_at(scene.handle(), index);
        REQUIRE(primitive != nullptr);
        CHECK(primitive->type_id == type_id);
        CHECK_FALSE(primitive->depth_test);
        if (primitive->kind == TC_DEBUG_GEOMETRY_WIRE_BOX) {
            box_primitive = primitive;
        }
    }
    REQUIRE(box_primitive != nullptr);
    CHECK(box_primitive->data.box.center[0] == guard::Approx(5.0F));
    CHECK(box_primitive->data.box.center[1] == guard::Approx(2.0F));
    CHECK(box_primitive->data.box.center[2] == guard::Approx(3.0F));

    const std::size_t all_count = tc_scene_debug_geometry_primitive_count(scene.handle());
    sphere->set_enabled(false);
    prepare_render(scene);
    CHECK(tc_scene_debug_geometry_primitive_count(scene.handle()) == all_count - 1U);

    capsule_entity.remove_component(capsule);
    capsule = nullptr;
    prepare_render(scene);
    CHECK(tc_scene_debug_geometry_primitive_count(scene.handle()) == all_count - 2U);

    REQUIRE(tc_scene_debug_geometry_set_enabled(scene.handle(), type_id, false));
    prepare_render(scene);
    CHECK(tc_scene_debug_geometry_primitive_count(scene.handle()) == 0U);

    tc_scene_render_mount_notify_detach(scene.handle(), attachment);
    scene.destroy();
}
