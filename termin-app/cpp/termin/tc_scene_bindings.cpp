// tc_scene_bindings.cpp - Render extension bindings (SceneRenderState, SceneRenderMount)
// TcSceneRef core binding lives in _scene_native.
// This file binds render-specific extensions as separate classes.
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>

#include <termin/tc_scene.hpp>
#include "termin/tc_scene_render_ext.hpp"
#include <termin/entity/component.hpp>
#include "bindings/entity/entity_helpers.hpp"
#include <tgfx/tgfx_mesh_handle.hpp>
#include "material/tc_material_handle.hpp"
#include "scene_bindings.hpp"
#include <termin/render/rendering_manager.hpp>
#include <termin/render/scene_pipeline_template.hpp>
#include <termin/geom/ray3.hpp>
#include <termin/geom/vec3.hpp>
#include <termin/geom/vec4.hpp>
#include "render/tc_value_trent.hpp"
#include "core/tc_scene_render_state.h"
#include "core/tc_scene_render_mount.h"
#include "core/tc_scene_extension.h"
#include "core/tc_scene_extension_ids.h"
#include "core/tc_component.h"

namespace nb = nanobind;

namespace termin {

// ============================================================================
// Trent <-> Python conversion helpers
// ============================================================================

static nb::object trent_to_python(const nos::trent& t) {
    switch (t.get_type()) {
        case nos::trent_type::nil:
            return nb::none();
        case nos::trent_type::boolean:
            return nb::bool_(t.as_bool());
        case nos::trent_type::numer:
            return nb::float_(static_cast<double>(t.as_numer()));
        case nos::trent_type::string:
            return nb::str(t.as_string().c_str());
        case nos::trent_type::list: {
            nb::list result;
            for (const auto& item : t.as_list()) {
                result.append(trent_to_python(item));
            }
            return result;
        }
        case nos::trent_type::dict: {
            nb::dict result;
            for (const auto& [key, value] : t.as_dict()) {
                result[nb::str(key.c_str())] = trent_to_python(value);
            }
            return result;
        }
        default:
            return nb::none();
    }
}

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

// ============================================================================
// C++ wrapper: SceneRenderState
// Thin handle over tc_scene_render_state, accessed via scene extension system.
// ============================================================================

class SceneRenderState {
public:
    tc_scene_handle _h;

    SceneRenderState(tc_scene_handle h) : _h(h) {}

    tc_scene_render_state* get() const {
        return tc_scene_render_state_get(_h);
    }

    tc_scene_render_state* ensure() {
        tc_scene_render_state_ensure(_h);
        return tc_scene_render_state_get(_h);
    }
};

// ============================================================================
// C++ wrapper: SceneRenderMount
// Thin handle over tc_scene_render_mount, accessed via scene extension system.
// ============================================================================

class SceneRenderMount {
public:
    tc_scene_handle _h;

    SceneRenderMount(tc_scene_handle h) : _h(h) {}
};

// ============================================================================
// Python bindings
// ============================================================================

void bind_tc_scene(nb::module_& m) {
    // --- ViewportConfig ---
    nb::class_<ViewportConfig>(m, "ViewportConfig")
        .def(nb::init<>())
        .def_rw("name", &ViewportConfig::name)
        .def_rw("display_name", &ViewportConfig::display_name)
        .def_rw("render_target_name", &ViewportConfig::render_target_name)
        .def_rw("region_x", &ViewportConfig::region_x)
        .def_rw("region_y", &ViewportConfig::region_y)
        .def_rw("region_w", &ViewportConfig::region_w)
        .def_rw("region_h", &ViewportConfig::region_h)
        .def_rw("depth", &ViewportConfig::depth)
        .def_rw("input_mode", &ViewportConfig::input_mode)
        .def_rw("block_input_in_editor", &ViewportConfig::block_input_in_editor)
        .def_rw("enabled", &ViewportConfig::enabled)
        .def_prop_ro("region", &ViewportConfig::region)
        .def("set_region", &ViewportConfig::set_region,
             nb::arg("x"), nb::arg("y"), nb::arg("w"), nb::arg("h"));

    // --- RenderTargetConfig ---
    nb::class_<RenderTargetConfig>(m, "RenderTargetConfig")
        .def(nb::init<>())
        .def_rw("name", &RenderTargetConfig::name)
        .def_rw("camera_uuid", &RenderTargetConfig::camera_uuid)
        .def_rw("width", &RenderTargetConfig::width)
        .def_rw("height", &RenderTargetConfig::height)
        .def_rw("pipeline_uuid", &RenderTargetConfig::pipeline_uuid)
        .def_rw("pipeline_name", &RenderTargetConfig::pipeline_name)
        .def_rw("layer_mask", &RenderTargetConfig::layer_mask)
        .def_rw("enabled", &RenderTargetConfig::enabled);

    // --- SceneRenderState ---
    nb::class_<SceneRenderState>(m, "SceneRenderState")
        // Background color
        .def_prop_rw("background_color",
            [](const SceneRenderState& self) -> Vec4 {
                TcSceneRef scene(self._h);
                return scene_background_color(scene);
            },
            [](SceneRenderState& self, const Vec4& c) {
                TcSceneRef scene(self._h);
                scene_set_background_color(scene, c);
            })
        .def("get_background_color", [](const SceneRenderState& self) {
            TcSceneRef scene(self._h);
            return scene_get_background_color(scene);
        })
        .def("set_background_color", [](SceneRenderState& self, float r, float g, float b, float a) {
            TcSceneRef scene(self._h);
            scene_set_background_color(scene, r, g, b, a);
        }, nb::arg("r"), nb::arg("g"), nb::arg("b"), nb::arg("a"))

        // Skybox type
        .def_prop_rw("skybox_type",
            [](const SceneRenderState& self) -> std::string {
                tc_scene_render_state* state = tc_scene_render_state_get(self._h);
                int t = state ? state->skybox.type : TC_SKYBOX_GRADIENT;
                if (t == TC_SKYBOX_NONE) return "none";
                if (t == TC_SKYBOX_SOLID) return "solid";
                return "gradient";
            },
            [](SceneRenderState& self, const std::string& s) {
                int t = TC_SKYBOX_GRADIENT;
                if (s == "none") t = TC_SKYBOX_NONE;
                else if (s == "solid") t = TC_SKYBOX_SOLID;
                if (!tc_scene_render_state_ensure(self._h)) return;
                tc_scene_render_state* state = tc_scene_render_state_get(self._h);
                if (!state) return;
                state->skybox.type = t;
            })
        .def("get_skybox_type", [](const SceneRenderState& self) -> int {
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            return state ? state->skybox.type : TC_SKYBOX_GRADIENT;
        })
        .def("set_skybox_type", [](SceneRenderState& self, int type) {
            if (!tc_scene_render_state_ensure(self._h)) return;
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            if (!state) return;
            state->skybox.type = type;
        })

        // Skybox colors
        .def_prop_rw("skybox_color",
            [](const SceneRenderState& self) -> Vec3 {
                TcSceneRef scene(self._h);
                return scene_skybox_color(scene);
            },
            [](SceneRenderState& self, const Vec3& c) {
                TcSceneRef scene(self._h);
                scene_set_skybox_color(scene, c);
            })
        .def_prop_rw("skybox_top_color",
            [](const SceneRenderState& self) -> Vec3 {
                TcSceneRef scene(self._h);
                return scene_skybox_top_color(scene);
            },
            [](SceneRenderState& self, const Vec3& c) {
                TcSceneRef scene(self._h);
                scene_set_skybox_top_color(scene, c);
            })
        .def_prop_rw("skybox_bottom_color",
            [](const SceneRenderState& self) -> Vec3 {
                TcSceneRef scene(self._h);
                return scene_skybox_bottom_color(scene);
            },
            [](SceneRenderState& self, const Vec3& c) {
                TcSceneRef scene(self._h);
                scene_set_skybox_bottom_color(scene, c);
            })

        // Skybox color get/set (tuple versions)
        .def("get_skybox_color", [](const SceneRenderState& self) -> std::tuple<float, float, float> {
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            if (!state) return {0.5f, 0.7f, 0.9f};
            return {state->skybox.color[0], state->skybox.color[1], state->skybox.color[2]};
        })
        .def("set_skybox_color", [](SceneRenderState& self, float r, float g, float b) {
            if (!tc_scene_render_state_ensure(self._h)) return;
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            if (!state) return;
            state->skybox.color[0] = r; state->skybox.color[1] = g; state->skybox.color[2] = b;
        })
        .def("get_skybox_top_color", [](const SceneRenderState& self) -> std::tuple<float, float, float> {
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            if (!state) return {0.4f, 0.6f, 0.9f};
            return {state->skybox.top_color[0], state->skybox.top_color[1], state->skybox.top_color[2]};
        })
        .def("set_skybox_top_color", [](SceneRenderState& self, float r, float g, float b) {
            if (!tc_scene_render_state_ensure(self._h)) return;
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            if (!state) return;
            state->skybox.top_color[0] = r; state->skybox.top_color[1] = g; state->skybox.top_color[2] = b;
        })
        .def("get_skybox_bottom_color", [](const SceneRenderState& self) -> std::tuple<float, float, float> {
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            if (!state) return {0.6f, 0.5f, 0.4f};
            return {state->skybox.bottom_color[0], state->skybox.bottom_color[1], state->skybox.bottom_color[2]};
        })
        .def("set_skybox_bottom_color", [](SceneRenderState& self, float r, float g, float b) {
            if (!tc_scene_render_state_ensure(self._h)) return;
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            if (!state) return;
            state->skybox.bottom_color[0] = r; state->skybox.bottom_color[1] = g; state->skybox.bottom_color[2] = b;
        })

        // Skybox mesh and material
        .def("skybox_mesh", [](const SceneRenderState& self) -> TcMesh {
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            tc_mesh* mesh = state ? tc_scene_skybox_ensure_mesh(&state->skybox) : nullptr;
            return mesh ? TcMesh(mesh) : TcMesh();
        })
        .def("skybox_material", [](const SceneRenderState& self) -> TcMaterial {
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            tc_material* mat = state ? state->skybox.material : nullptr;
            return TcMaterial(mat);
        })
        .def("ensure_skybox_material", [](SceneRenderState& self, int skybox_type) -> TcMaterial {
            tc_scene_render_state* state = tc_scene_render_state_get(self._h);
            tc_scene_skybox* skybox = state ? &state->skybox : nullptr;
            if (!skybox) return TcMaterial(nullptr);
            tc_material* mat = tc_scene_skybox_ensure_material(skybox, skybox_type);
            return TcMaterial(mat);
        }, nb::arg("skybox_type"))

        // Ambient lighting
        .def_prop_rw("ambient_color",
            [](const SceneRenderState& self) -> Vec3 {
                TcSceneRef scene(self._h);
                return scene_ambient_color(scene);
            },
            [](SceneRenderState& self, const Vec3& c) {
                TcSceneRef scene(self._h);
                scene_set_ambient_color(scene, c);
            })
        .def_prop_rw("ambient_intensity",
            [](const SceneRenderState& self) -> float {
                TcSceneRef scene(self._h);
                return scene_ambient_intensity(scene);
            },
            [](SceneRenderState& self, float v) {
                TcSceneRef scene(self._h);
                scene_set_ambient_intensity(scene, v);
            })

        // Lighting pointer
        .def("lighting_ptr", [](const SceneRenderState& self) -> uintptr_t {
            TcSceneRef scene(self._h);
            return reinterpret_cast<uintptr_t>(scene_lighting(scene));
        })
        .def("lighting", [](const SceneRenderState& self) -> nb::object {
            TcSceneRef scene(self._h);
            uintptr_t ptr = reinterpret_cast<uintptr_t>(scene_lighting(scene));
            if (ptr == 0) return nb::none();
            nb::module_ scene_module = nb::module_::import_("termin._native.scene");
            nb::object cls = scene_module.attr("TcSceneLighting");
            return cls(ptr);
        })

        // Shadow settings
        .def_prop_rw("shadow_settings",
            [](const SceneRenderState& self) -> nb::object {
                TcSceneRef scene(self._h);
                tc_scene_lighting* lit = scene_lighting(scene);
                if (!lit) return nb::none();
                nb::module_ lighting_module = nb::module_::import_("termin.lighting._lighting_native");
                nb::object cls = lighting_module.attr("ShadowSettings");
                return cls(lit->shadow_method, lit->shadow_softness, lit->shadow_bias);
            },
            [](SceneRenderState& self, nb::object value) {
                TcSceneRef scene(self._h);
                tc_scene_lighting* lit = scene_lighting(scene);
                if (!lit) return;
                lit->shadow_method = nb::cast<int>(value.attr("method"));
                lit->shadow_softness = static_cast<float>(nb::cast<double>(value.attr("softness")));
                lit->shadow_bias = static_cast<float>(nb::cast<double>(value.attr("bias")));
            });

    // --- SceneRenderMount ---
    nb::class_<SceneRenderMount>(m, "SceneRenderMount")
        // Viewport configurations
        .def("add_viewport_config", [](SceneRenderMount& self, const ViewportConfig& config) {
            TcSceneRef scene(self._h);
            scene_add_viewport_config(scene, config);
        }, nb::arg("config"))
        .def("remove_viewport_config", [](SceneRenderMount& self, size_t index) {
            TcSceneRef scene(self._h);
            scene_remove_viewport_config(scene, index);
        }, nb::arg("index"))
        .def("clear_viewport_configs", [](SceneRenderMount& self) {
            TcSceneRef scene(self._h);
            scene_clear_viewport_configs(scene);
        })
        .def("viewport_config_count", [](const SceneRenderMount& self) {
            TcSceneRef scene(self._h);
            return scene_viewport_config_count(scene);
        })
        .def("viewport_config_at", [](const SceneRenderMount& self, size_t index) -> nb::object {
            TcSceneRef scene(self._h);
            if (index >= scene_viewport_config_count(scene)) return nb::none();
            return nb::cast(scene_viewport_config_at(scene, index));
        }, nb::arg("index"))
        .def_prop_ro("viewport_configs", [](const SceneRenderMount& self) {
            TcSceneRef scene(self._h);
            return scene_viewport_configs(scene);
        })

        // Render target configurations
        .def("add_render_target_config", [](SceneRenderMount& self, const RenderTargetConfig& config) {
            TcSceneRef scene(self._h);
            scene_add_render_target_config(scene, config);
        }, nb::arg("config"))
        .def("remove_render_target_config", [](SceneRenderMount& self, size_t index) {
            TcSceneRef scene(self._h);
            scene_remove_render_target_config(scene, index);
        }, nb::arg("index"))
        .def("clear_render_target_configs", [](SceneRenderMount& self) {
            TcSceneRef scene(self._h);
            scene_clear_render_target_configs(scene);
        })
        .def("render_target_config_count", [](const SceneRenderMount& self) {
            TcSceneRef scene(self._h);
            return scene_render_target_config_count(scene);
        })
        .def("render_target_config_at", [](const SceneRenderMount& self, size_t index) -> nb::object {
            TcSceneRef scene(self._h);
            if (index >= scene_render_target_config_count(scene)) return nb::none();
            return nb::cast(scene_render_target_config_at(scene, index));
        }, nb::arg("index"))
        .def_prop_ro("render_target_configs", [](const SceneRenderMount& self) {
            TcSceneRef scene(self._h);
            return scene_render_target_configs(scene);
        })

        // Pipeline templates
        .def("add_pipeline_template", [](SceneRenderMount& self, const TcScenePipelineTemplate& templ) {
            TcSceneRef scene(self._h);
            scene_add_pipeline_template(scene, templ);
        }, nb::arg("template"))
        .def("remove_pipeline_template", [](SceneRenderMount& self, const TcScenePipelineTemplate& templ) {
            tc_scene_remove_pipeline_template(self._h, templ.handle());
        }, nb::arg("template"))
        .def("clear_pipeline_templates", [](SceneRenderMount& self) {
            TcSceneRef scene(self._h);
            scene_clear_pipeline_templates(scene);
        })
        .def("pipeline_template_count", [](const SceneRenderMount& self) {
            TcSceneRef scene(self._h);
            return scene_pipeline_template_count(scene);
        })
        .def("pipeline_template_at", [](const SceneRenderMount& self, size_t index) {
            TcSceneRef scene(self._h);
            return scene_pipeline_template_at(scene, index);
        }, nb::arg("index"))
        .def_prop_ro("scene_pipelines", [](const SceneRenderMount& self) {
            TcSceneRef scene(self._h);
            std::vector<TcScenePipelineTemplate> result;
            size_t count = scene_pipeline_template_count(scene);
            result.reserve(count);
            for (size_t i = 0; i < count; i++) {
                result.push_back(scene_pipeline_template_at(scene, i));
            }
            return result;
        })

        // Compiled pipelines (from RenderingManager)
        .def("get_pipeline", [](const SceneRenderMount& self, const std::string& name) {
            TcSceneRef scene(self._h);
            return scene_get_pipeline(scene, name);
        }, nb::arg("name"), nb::rv_policy::reference)
        .def("get_pipeline_names", [](const SceneRenderMount& self) {
            TcSceneRef scene(self._h);
            return scene_get_pipeline_names(scene);
        })
        .def("get_pipeline_targets", [](const SceneRenderMount& self, const std::string& name) -> const std::vector<std::string>& {
            return scene_get_pipeline_targets(name);
        }, nb::arg("name"), nb::rv_policy::reference);

    // --- Module-level functions ---

    // Get render state extension from scene
    m.def("scene_render_state", [](const TcSceneRef& scene) -> SceneRenderState {
        return SceneRenderState(scene._h);
    }, nb::arg("scene"), "Get SceneRenderState extension from scene");

    // Get render mount extension from scene
    m.def("scene_render_mount", [](const TcSceneRef& scene) -> SceneRenderMount {
        return SceneRenderMount(scene._h);
    }, nb::arg("scene"), "Get SceneRenderMount extension from scene");

    m.attr("SCENE_EXT_TYPE_RENDER_MOUNT") = nb::int_(TC_SCENE_EXT_TYPE_RENDER_MOUNT);
    m.attr("SCENE_EXT_TYPE_RENDER_STATE") = nb::int_(TC_SCENE_EXT_TYPE_RENDER_STATE);
    m.attr("SCENE_EXT_TYPE_COLLISION_WORLD") = nb::int_(TC_SCENE_EXT_TYPE_COLLISION_WORLD);

    // Get list of attached extension debug names for a scene
    m.def("scene_ext_attached_names", [](const TcSceneRef& scene) -> std::vector<std::string> {
        std::vector<std::string> result;
        tc_scene_ext_type_id ids[TC_SCENE_EXT_TYPE_COUNT];
        size_t count = tc_scene_ext_get_attached_types(scene._h, ids, TC_SCENE_EXT_TYPE_COUNT);
        for (size_t i = 0; i < count; i++) {
            const char* name = tc_scene_ext_type_debug_name(ids[i]);
            result.push_back(name ? name : "unknown");
        }
        return result;
    }, nb::arg("scene"), "Get debug names of all attached scene extensions");

    m.def("default_scene_extensions", &default_scene_extension_ids,
        "Default scene extensions for render-enabled scenes.");

    m.def("create_scene_with_extensions", &create_scene_with_extensions,
        nb::arg("name") = "", nb::arg("uuid") = "", nb::arg("extensions"),
        "Create a new scene with the provided scene extension ids attached");

    m.def("create_scene", [](const std::string& name, const std::string& uuid, nb::object extensions_obj) {
        if (extensions_obj.is_none()) {
            return create_scene_with_extensions(name, uuid, default_scene_extension_ids());
        }
        return create_scene_with_extensions(name, uuid, nb::cast<std::vector<tc_scene_ext_type_id>>(extensions_obj));
    }, nb::arg("name") = "", nb::arg("uuid") = "", nb::arg("extensions") = nb::none(),
        "Create a new scene with explicit extensions, or default render/collision extensions when omitted");

    // Destroy scene with render cleanup
    m.def("destroy_scene", [](TcSceneRef& scene) {
        if (!scene.is_alive()) return;
        for (Entity& e : scene.get_all_entities()) {
            size_t count = e.component_count();
            for (size_t i = 0; i < count; i++) {
                tc_component* c = e.component_at(i);
                if (c) {
                    tc_component_on_destroy(c);
                }
            }
        }
        destroy_scene_with_render(scene);
    }, nb::arg("scene"), "Destroy scene and clean up render resources");

    // Deserialize scene
    m.def("deserialize_scene", [](nb::handle data, const std::string& name) -> TcSceneRef {
        TcSceneRef scene = create_scene_with_extensions(name, "", default_scene_extension_ids());
        nos::trent t = python_to_trent(data);

        if (t.contains("uuid") && t["uuid"].is_string()) {
            scene.set_uuid(t["uuid"].as_string());
        }
        if (t.contains("background_color") && t["background_color"].is_list()) {
            const auto& bg = t["background_color"].as_list();
            if (bg.size() >= 4) {
                scene_set_background_color(scene,
                    static_cast<float>(bg[0].as_numer_default(0.05)),
                    static_cast<float>(bg[1].as_numer_default(0.05)),
                    static_cast<float>(bg[2].as_numer_default(0.08)),
                    static_cast<float>(bg[3].as_numer_default(1.0)));
            }
        }

        scene.load_from_data(t, true);
        return scene;
    }, nb::arg("data"), nb::arg("name") = "",
       "Create scene from serialized data");

}

} // namespace termin
