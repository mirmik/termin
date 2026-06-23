#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <termin/scene/tc_scene_render_ext.hpp>

extern "C" {
#include "core/tc_scene_extension.h"
#include "core/tc_scene_extension_ids.h"
}

namespace nb = nanobind;

namespace termin {

void bind_scene_render_ext(nb::module_& m) {
    m.attr("SCENE_EXT_TYPE_RENDER_MOUNT") = nb::int_(TC_SCENE_EXT_TYPE_RENDER_MOUNT);
    m.attr("SCENE_EXT_TYPE_RENDER_STATE") = nb::int_(TC_SCENE_EXT_TYPE_RENDER_STATE);
    m.attr("SCENE_EXT_TYPE_COLLISION_WORLD") = nb::int_(TC_SCENE_EXT_TYPE_COLLISION_WORLD);

    m.def("register_default_scene_extensions", &register_default_scene_extensions,
        "Register engine default scene extensions.");

    m.def("default_scene_extensions", &default_scene_extension_ids,
        "Default scene extensions for render-enabled scenes.");

    m.def("create_scene_with_extensions", &create_scene_with_extensions,
        nb::arg("name") = "", nb::arg("uuid") = "", nb::arg("extensions"),
        "Create a new scene with the provided scene extension ids attached.");

    m.def("create_scene_with_render", &create_scene_with_render,
        nb::arg("name") = "", nb::arg("uuid") = "",
        "Create a new scene with engine default render extensions attached.");

    m.def("create_scene", [](const std::string& name, const std::string& uuid, nb::object extensions_obj) {
        if (extensions_obj.is_none()) {
            return create_scene_with_render(name, uuid);
        }
        return create_scene_with_extensions(
            name,
            uuid,
            nb::cast<std::vector<tc_scene_ext_type_id>>(extensions_obj));
    }, nb::arg("name") = "", nb::arg("uuid") = "", nb::arg("extensions") = nb::none(),
       "Create a new scene with explicit extensions, or engine defaults when omitted.");

    m.def("destroy_scene_with_render", &destroy_scene_with_render,
        nb::arg("scene"),
        "Destroy a scene and clear engine render pipeline state.");

    m.def("scene_ext_attached_names", [](const TcSceneRef& scene) -> std::vector<std::string> {
        std::vector<std::string> result;
        tc_scene_ext_type_id ids[TC_SCENE_EXT_TYPE_COUNT];
        size_t count = tc_scene_ext_get_attached_types(scene.handle(), ids, TC_SCENE_EXT_TYPE_COUNT);
        result.reserve(count);
        for (size_t i = 0; i < count; ++i) {
            const char* name = tc_scene_ext_type_debug_name(ids[i]);
            result.push_back(name ? name : "unknown");
        }
        return result;
    }, nb::arg("scene"), "Get debug names of all attached scene extensions.");
}

} // namespace termin
