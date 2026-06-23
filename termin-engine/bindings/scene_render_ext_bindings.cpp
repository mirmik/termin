#include <nanobind/nanobind.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <termin/scene/tc_scene_render_ext.hpp>
#include <trent/trent.h>

extern "C" {
#include "core/tc_scene_extension.h"
#include "core/tc_scene_extension_ids.h"
}

namespace nb = nanobind;

namespace termin {

static nos::trent python_to_trent(nb::handle obj) {
    if (obj.is_none()) {
        return nos::trent();
    }
    if (nb::isinstance<nb::bool_>(obj)) {
        return nos::trent(nb::cast<bool>(obj));
    }
    if (nb::isinstance<nb::int_>(obj)) {
        return nos::trent(static_cast<int64_t>(nb::cast<int64_t>(obj)));
    }
    if (nb::isinstance<nb::float_>(obj)) {
        return nos::trent(nb::cast<double>(obj));
    }
    if (nb::isinstance<nb::str>(obj)) {
        return nos::trent(nb::cast<std::string>(obj));
    }
    if (nb::isinstance<nb::list>(obj) || nb::isinstance<nb::tuple>(obj)) {
        nos::trent result;
        result.init(nos::trent::type::list);
        for (auto item : obj) {
            result.push_back(python_to_trent(item));
        }
        return result;
    }
    if (nb::isinstance<nb::dict>(obj)) {
        nos::trent result;
        result.init(nos::trent::type::dict);
        for (auto [key, value] : nb::cast<nb::dict>(obj)) {
            std::string key_str = nb::cast<std::string>(nb::str(key));
            result[key_str] = python_to_trent(value);
        }
        return result;
    }
    return nos::trent(nb::cast<std::string>(nb::str(obj)));
}

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
    m.def("destroy_scene", &destroy_scene_with_render,
        nb::arg("scene"),
        "Destroy a render-enabled scene and clear engine render pipeline state.");

    m.def("deserialize_scene_with_render", [](nb::handle data, const std::string& name) -> TcSceneRef {
        return deserialize_scene_with_render(python_to_trent(data), name);
    }, nb::arg("data"), nb::arg("name") = "",
       "Create render-enabled scene from serialized data.");

    m.def("deserialize_scene", [](nb::handle data, const std::string& name) -> TcSceneRef {
        return deserialize_scene_with_render(python_to_trent(data), name);
    }, nb::arg("data"), nb::arg("name") = "",
       "Create render-enabled scene from serialized data.");

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
