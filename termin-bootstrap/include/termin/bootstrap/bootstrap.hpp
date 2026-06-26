#pragma once

#ifdef _WIN32
    #ifdef TERMIN_BOOTSTRAP_EXPORTS
        #define TERMIN_BOOTSTRAP_API __declspec(dllexport)
    #else
        #define TERMIN_BOOTSTRAP_API __declspec(dllimport)
    #endif
#else
    #define TERMIN_BOOTSTRAP_API __attribute__((visibility("default")))
#endif

namespace termin::bootstrap {

struct RuntimeKindOptions {
    bool mesh = true;
    bool material = true;
    bool skeleton = true;
    bool animation = true;
    bool voxel_grid = true;
    bool navmesh = true;
    bool entity = true;
};

struct SceneExtensionOptions {
    bool render_mount = true;
    bool render_state = true;
    bool collision_world = true;
};

TERMIN_BOOTSTRAP_API void register_runtime_kinds(const RuntimeKindOptions& options = {});
TERMIN_BOOTSTRAP_API void register_scene_extensions(const SceneExtensionOptions& options = {});
TERMIN_BOOTSTRAP_API void init_inspect_adapters();
TERMIN_BOOTSTRAP_API void init_python_inspect_adapters();
TERMIN_BOOTSTRAP_API void init_python_render_passes();
TERMIN_BOOTSTRAP_API void init_python_kind_handlers(const RuntimeKindOptions& options = {});
TERMIN_BOOTSTRAP_API void init_pointer_extractors();
TERMIN_BOOTSTRAP_API void init_python_component_callbacks();

TERMIN_BOOTSTRAP_API void bootstrap_runtime();
TERMIN_BOOTSTRAP_API void bootstrap_player();
TERMIN_BOOTSTRAP_API void bootstrap_editor();
TERMIN_BOOTSTRAP_API void shutdown_runtime();

} // namespace termin::bootstrap
