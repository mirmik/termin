#include <cstring>

#include <emscripten/emscripten.h>

#include <core/tc_scene.h>
#include <inspect/tc_kind.h>
#include <tcbase/tc_version.h>
#include <termin_scene/termin_scene.h>
#include <tgfx/resources/tc_mesh_registry.h>

extern "C" EMSCRIPTEN_KEEPALIVE int termin_web_core_smoke() {
    if (tc_version_int() <= 0 || termin_scene_version_int() <= 0) {
        return 1;
    }
    if (tc_kind_get_lang_registry(TC_KIND_LANG_RUST) != nullptr) {
        return 2;
    }

    tc_mesh_init();
    tc_mesh_handle mesh = tc_mesh_declare("web-smoke-mesh", "Web smoke mesh");
    if (!tc_mesh_is_valid(mesh) || tc_mesh_count() != 1) {
        tc_mesh_shutdown();
        return 3;
    }
    tc_mesh_destroy(mesh);
    tc_mesh_shutdown();

    tc_scene_handle scene = tc_scene_new_named("Web smoke scene");
    const char* scene_name = tc_scene_get_name(scene);
    if (scene_name == nullptr || std::strcmp(scene_name, "Web smoke scene") != 0) {
        tc_scene_free(scene);
        return 4;
    }
    tc_scene_update(scene, 1.0 / 60.0);
    tc_scene_free(scene);
    return 0x5443;
}
