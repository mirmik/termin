#include <termin/bootstrap/bootstrap.hpp>
#include <termin/bootstrap/bootstrap_c.h>
#include <termin/engine/engine_core.hpp>

extern "C" {
#include <core/tc_scene.h>
#include <core/tc_scene_extension.h>
#include <core/tc_scene_extension_ids.h>
#include <termin_scene/internal/tc_scene_extension_registry.h>
}

#include <cstdio>
#include <cstdlib>
#include <memory>

namespace {

int g_create_count = 0;
int g_destroy_count = 0;

bool require(bool condition, const char* message) {
    if (!condition) {
        std::fprintf(stderr, "scene extension lifecycle contract failed: %s\n", message);
    }
    return condition;
}

void* create_probe(tc_scene_handle, void*) {
    ++g_create_count;
    return std::malloc(1);
}

void destroy_probe(void* instance, void*) {
    ++g_destroy_count;
    std::free(instance);
}

} // namespace

int main() {
    bool ok = true;
    tc_scene_ext_vtable probe_vtable{};
    probe_vtable.create = create_probe;
    probe_vtable.destroy = destroy_probe;

    ok &= require(!tc_scene_ext_registry_initialized(),
                  "registry must not exist before process init");
    ok &= require(!tc_scene_ext_register(TC_SCENE_EXT_TYPE_PATHFINDING_WORLD,
                                         "lifecycle_probe", "lifecycle_probe",
                                         &probe_vtable, nullptr),
                  "registration before process init must fail");
    ok &= require(!tc_scene_ext_registry_initialized(),
                  "failed registration must not initialize the registry");
    ok &= require(!tc_scene_ext_attach(TC_SCENE_HANDLE_INVALID,
                                       TC_SCENE_EXT_TYPE_PATHFINDING_WORLD),
                  "attach before process init must fail");

    tc_init();
    ok &= require(tc_scene_ext_registry_initialized(),
                  "tc_init must create the registry");
    ok &= require(tc_scene_ext_register(TC_SCENE_EXT_TYPE_PATHFINDING_WORLD,
                                        "lifecycle_probe", "lifecycle_probe",
                                        &probe_vtable, nullptr),
                  "registration after tc_init must succeed");

    const tc_scene_handle scene = tc_scene_new();
    ok &= require(tc_scene_handle_valid(scene), "tc_init must make scene creation available");
    ok &= require(tc_scene_ext_attach(scene, TC_SCENE_EXT_TYPE_PATHFINDING_WORLD),
                  "registered extension must attach");
    ok &= require(g_create_count == 1, "extension create callback must run once");

    tc_scene_ext_registry_shutdown();
    ok &= require(tc_scene_ext_registry_initialized(),
                  "registry shutdown must refuse while scenes are alive");
    ok &= require(tc_scene_ext_has(scene, TC_SCENE_EXT_TYPE_PATHFINDING_WORLD),
                  "refused shutdown must preserve live extension instances");

    tc_shutdown();
    ok &= require(g_destroy_count == 1,
                  "tc_shutdown must destroy scene extensions before their type table");
    ok &= require(!tc_scene_ext_registry_initialized(),
                  "tc_shutdown must destroy the registry");

    termin::bootstrap::bootstrap_runtime();
    ok &= require(tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_RENDER_MOUNT),
                  "bootstrap must register render-mount extension");
    auto first = std::make_unique<termin::EngineCore>();
    auto second = std::make_unique<termin::EngineCore>();
    first.reset();
    ok &= require(tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_RENDER_MOUNT),
                  "destroying the first EngineCore must not change the registry");
    second.reset();
    ok &= require(tc_scene_ext_is_registered(TC_SCENE_EXT_TYPE_RENDER_MOUNT),
                  "destroying the last EngineCore must not change the registry");
    termin::bootstrap::shutdown_runtime();
    ok &= require(!tc_scene_ext_registry_initialized(),
                  "bootstrap shutdown must own the registry boundary");

    termin::bootstrap::bootstrap_runtime();
    ok &= require(tc_scene_ext_registry_initialized(),
                  "registry must support a second process init cycle");
    termin::bootstrap::shutdown_runtime();
    ok &= require(!tc_scene_ext_registry_initialized(),
                  "registry must support a second process shutdown cycle");
    return ok ? 0 : 1;
}
