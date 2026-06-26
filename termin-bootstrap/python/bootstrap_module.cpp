#include <termin/bootstrap/bootstrap.hpp>

#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace {

termin::bootstrap::RuntimeKindOptions runtime_kind_options_from_kwargs(
    bool mesh,
    bool material,
    bool skeleton,
    bool animation,
    bool voxel_grid,
    bool navmesh,
    bool entity
) {
    termin::bootstrap::RuntimeKindOptions options;
    options.mesh = mesh;
    options.material = material;
    options.skeleton = skeleton;
    options.animation = animation;
    options.voxel_grid = voxel_grid;
    options.navmesh = navmesh;
    options.entity = entity;
    return options;
}

termin::bootstrap::SceneExtensionOptions scene_extension_options_from_kwargs(
    bool render_mount,
    bool render_state,
    bool collision_world
) {
    termin::bootstrap::SceneExtensionOptions options;
    options.render_mount = render_mount;
    options.render_state = render_state;
    options.collision_world = collision_world;
    return options;
}

} // namespace

NB_MODULE(_bootstrap_native, m) {
    m.doc() = "Explicit startup bootstrap helpers for Termin runtime/player/editor";

    m.def("register_runtime_kinds",
        [](bool mesh, bool material, bool skeleton, bool animation, bool voxel_grid, bool navmesh, bool entity) {
            termin::bootstrap::register_runtime_kinds(
                runtime_kind_options_from_kwargs(mesh, material, skeleton, animation, voxel_grid, navmesh, entity)
            );
        },
        nb::arg("mesh") = true,
        nb::arg("material") = true,
        nb::arg("skeleton") = true,
        nb::arg("animation") = true,
        nb::arg("voxel_grid") = true,
        nb::arg("navmesh") = true,
        nb::arg("entity") = true);

    m.def("register_scene_extensions",
        [](bool render_mount, bool render_state, bool collision_world) {
            termin::bootstrap::register_scene_extensions(
                scene_extension_options_from_kwargs(render_mount, render_state, collision_world)
            );
        },
        nb::arg("render_mount") = true,
        nb::arg("render_state") = true,
        nb::arg("collision_world") = true);

    m.def("init_inspect_adapters", &termin::bootstrap::init_inspect_adapters);
    m.def("init_python_inspect_adapters", &termin::bootstrap::init_python_inspect_adapters);
    m.def("init_python_render_passes", &termin::bootstrap::init_python_render_passes);
    m.def("init_python_kind_handlers",
        [](bool mesh, bool material, bool skeleton, bool animation, bool voxel_grid, bool navmesh, bool entity) {
            termin::bootstrap::init_python_kind_handlers(
                runtime_kind_options_from_kwargs(mesh, material, skeleton, animation, voxel_grid, navmesh, entity)
            );
        },
        nb::arg("mesh") = true,
        nb::arg("material") = true,
        nb::arg("skeleton") = true,
        nb::arg("animation") = true,
        nb::arg("voxel_grid") = true,
        nb::arg("navmesh") = true,
        nb::arg("entity") = true);
    m.def("init_pointer_extractors", &termin::bootstrap::init_pointer_extractors);
    m.def("init_python_component_callbacks", &termin::bootstrap::init_python_component_callbacks);
    m.def("bootstrap_runtime", &termin::bootstrap::bootstrap_runtime);
    m.def("bootstrap_player", &termin::bootstrap::bootstrap_player);
    m.def("bootstrap_editor", &termin::bootstrap::bootstrap_editor);
    m.def("shutdown_runtime", &termin::bootstrap::shutdown_runtime);
}
