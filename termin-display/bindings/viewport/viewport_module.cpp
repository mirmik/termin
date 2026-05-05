// viewport_module.cpp - Viewport native module (_viewport_native)
// Contains TcViewport binding, shared between _entity_native and _native

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

#include "termin/viewport/tc_viewport_handle.hpp"
#include <tcbase/tc_log.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/component.hpp>
#include "core/tc_component.h"
#include "core/tc_scene.h"
#include "render/tc_pipeline.h"

namespace nb = nanobind;

namespace termin {

static tc_pipeline_handle object_to_pipeline_handle(nb::object pipeline_obj) {
    return nb::cast<tc_pipeline_handle>(pipeline_obj.attr("_pipeline_handle"));
}

static nb::object camera_component_from_tc(tc_component* c) {
    if (!c) {
        return nb::none();
    }

    if (c->native_language == TC_LANGUAGE_PYTHON && c->body) {
        return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(c->body));
    }

    if (c->kind != TC_CXX_COMPONENT) {
        return nb::none();
    }

    nb::module_ render_components = nb::module_::import_("termin.render_components._components_render_native");
    nb::object camera_class = render_components.attr("CameraComponent");
    return camera_class.attr("_from_c_component_ptr")(reinterpret_cast<uintptr_t>(c));
}

void bind_tc_viewport_class(nb::module_& m) {
    nb::class_<TcViewport>(m, "Viewport")
        // Default constructor
        .def(nb::init<>())

        // Constructor with parameters
        .def("__init__", [](TcViewport* self,
                           const std::string& name,
                           nb::object scene,
                           nb::object camera,
                           std::tuple<float, float, float, float> rect,
                           int depth,
                           nb::object pipeline,
                           const std::string& input_mode,
                           bool block_input_in_editor,
                           const std::string& managed_by_scene_pipeline,
                           uint64_t layer_mask,
                           bool enabled,
                           nb::object internal_entities,
                           std::tuple<int, int, int, int> pixel_rect) {
            // Get tc_scene_handle from Scene (Scene inherits from TcScene)
            tc_scene_handle tc_s = TC_SCENE_HANDLE_INVALID;
            if (!scene.is_none()) {
                tc_s = nb::cast<tc_scene_handle>(scene.attr("scene_handle")());
            }

            // Get tc_component* from CameraComponent
            tc_component* tc_c = nullptr;
            if (!camera.is_none()) {
                uintptr_t ptr = nb::cast<uintptr_t>(camera.attr("c_component_ptr")());
                tc_c = reinterpret_cast<tc_component*>(ptr);
            }

            // Create viewport via pool
            tc_viewport_handle vh = tc_viewport_new(name.c_str(), tc_s, tc_c);

            // Set rect
            tc_viewport_set_rect(vh, std::get<0>(rect), std::get<1>(rect),
                                std::get<2>(rect), std::get<3>(rect));
            tc_viewport_set_pixel_rect(vh, std::get<0>(pixel_rect), std::get<1>(pixel_rect),
                                      std::get<2>(pixel_rect), std::get<3>(pixel_rect));

            // Set properties
            tc_viewport_set_depth(vh, depth);
            tc_viewport_set_layer_mask(vh, layer_mask);
            tc_viewport_set_enabled(vh, enabled);
            tc_viewport_set_input_mode(vh, input_mode.c_str());
            tc_viewport_set_block_input_in_editor(vh, block_input_in_editor);
            if (!managed_by_scene_pipeline.empty()) {
                tc_viewport_set_managed_by(vh, managed_by_scene_pipeline.c_str());
            }

            // Pipeline
            if (!pipeline.is_none()) {
                tc_pipeline_handle ph = object_to_pipeline_handle(pipeline);
                tc_viewport_set_pipeline(vh, ph);
            }

            // Internal entities
            if (!internal_entities.is_none()) {
                termin::Entity ent = nb::cast<termin::Entity>(internal_entities);
                tc_viewport_set_internal_entities(vh, ent.handle());
            }

            // Construct TcViewport in-place with handle
            new (self) TcViewport(vh);
        },
        nb::arg("name"),
        nb::arg("scene"),
        nb::arg("camera"),
        nb::arg("rect") = std::make_tuple(0.0f, 0.0f, 1.0f, 1.0f),
        nb::arg("depth") = 0,
        nb::arg("pipeline") = nb::none(),
        nb::arg("input_mode") = "simple",
        nb::arg("block_input_in_editor") = false,
        nb::arg("managed_by_scene_pipeline") = "",
        nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL,
        nb::arg("enabled") = true,
        nb::arg("internal_entities") = nb::none(),
        nb::arg("pixel_rect") = std::make_tuple(0, 0, 1, 1))

        // Check validity
        .def("is_valid", &TcViewport::is_valid)

        // Name
        .def_prop_rw("name",
            [](TcViewport& self) {
                const char* n = self.name();
                return n ? std::string(n) : "";
            },
            [](TcViewport& self, const std::string& n) {
                if (self.is_valid()) tc_viewport_set_name(self.handle_, n.c_str());
            })

        // Scene - returns TcScene directly (TcSceneRef is a non-owning reference)
        .def_prop_rw("scene",
            [](TcViewport& self) -> nb::object {
                tc_scene_handle s = self.scene();
                if (tc_scene_handle_valid(s) && tc_scene_alive(s)) {
                    // Import TcScene from _entity_native and create via from_handle
                    nb::module_ entity_module = nb::module_::import_("termin.entity._entity_native");
                    nb::object tc_scene_class = entity_module.attr("TcScene");
                    return tc_scene_class.attr("from_handle")(s.index, s.generation);
                }
                return nb::none();
            },
            [](TcViewport& self, nb::object scene_obj) {
                if (!self.is_valid()) return;
                if (scene_obj.is_none()) {
                    tc_viewport_set_scene(self.handle_, TC_SCENE_HANDLE_INVALID);
                } else {
                    tc_scene_handle handle = nb::cast<tc_scene_handle>(scene_obj.attr("scene_handle")());
                    tc_viewport_set_scene(self.handle_, handle);
                }
            })

        // Camera - returns Python wrapper for CameraComponent
        .def_prop_rw("camera",
            [](TcViewport& self) -> nb::object {
                tc_component* c = self.camera();
                return camera_component_from_tc(c);
            },
            [](TcViewport& self, nb::object camera_obj) {
                if (!self.is_valid()) return;
                if (camera_obj.is_none()) {
                    tc_viewport_set_camera(self.handle_, nullptr);
                } else {
                    uintptr_t ptr = nb::cast<uintptr_t>(camera_obj.attr("c_component_ptr")());
                    tc_viewport_set_camera(self.handle_, reinterpret_cast<tc_component*>(ptr));
                }
            },
            nb::arg().none())

        // Rect (normalized 0-1)
        .def_prop_rw("rect",
            [](TcViewport& self) {
                float x, y, w, h;
                self.get_rect(x, y, w, h);
                return std::make_tuple(x, y, w, h);
            },
            [](TcViewport& self, std::tuple<float, float, float, float> r) {
                self.set_rect(std::get<0>(r), std::get<1>(r),
                             std::get<2>(r), std::get<3>(r));
            })

        // Pixel rect
        .def_prop_rw("pixel_rect",
            [](TcViewport& self) {
                int px, py, pw, ph;
                self.get_pixel_rect(px, py, pw, ph);
                return std::make_tuple(px, py, pw, ph);
            },
            [](TcViewport& self, std::tuple<int, int, int, int> r) {
                self.set_pixel_rect(std::get<0>(r), std::get<1>(r),
                                   std::get<2>(r), std::get<3>(r));
            })

        .def("update_pixel_rect", &TcViewport::update_pixel_rect,
             nb::arg("display_width"), nb::arg("display_height"))

        // Depth
        .def_prop_rw("depth",
            [](TcViewport& self) { return self.depth(); },
            [](TcViewport& self, int d) { self.set_depth(d); })

        // Render target handle
        .def_prop_rw("render_target",
            [](TcViewport& self) -> nb::object {
                tc_render_target_handle rt = tc_viewport_get_render_target(self.handle_);
                if (!tc_render_target_handle_valid(rt)) return nb::none();
                nb::module_ rf = nb::module_::import_("termin.render_framework._render_framework_native");
                nb::object obj = rf.attr("RenderTargetHandle")();
                obj.attr("index") = rt.index;
                obj.attr("generation") = rt.generation;
                return obj;
            },
            [](TcViewport& self, nb::object rt_obj) {
                if (!self.is_valid()) return;
                if (rt_obj.is_none()) {
                    tc_viewport_set_render_target(self.handle_, TC_RENDER_TARGET_HANDLE_INVALID);
                } else {
                    tc_render_target_handle rt;
                    rt.index = nb::cast<uint32_t>(rt_obj.attr("index"));
                    rt.generation = nb::cast<uint32_t>(rt_obj.attr("generation"));
                    tc_viewport_set_render_target(self.handle_, rt);
                }
            },
            nb::arg().none())

        // Pipeline — creates wrapper from handle, no py_wrapper
        .def_prop_rw("pipeline",
            [](TcViewport& self) -> nb::object {
                tc_pipeline_handle ph = self.pipeline();
                if (!tc_pipeline_handle_valid(ph)) return nb::none();
                nb::module_ render_module = nb::module_::import_("termin._native.render");
                nb::object cls = render_module.attr("RenderPipeline");
                return cls.attr("from_handle")(ph.index, ph.generation);
            },
            [](TcViewport& self, nb::object pipeline_obj) {
                if (!self.is_valid()) {
                    tc::Log::error("viewport.pipeline setter: viewport is not valid");
                    return;
                }
                if (pipeline_obj.is_none()) {
                    tc_viewport_set_pipeline(self.handle_, TC_PIPELINE_HANDLE_INVALID);
                } else {
                    try {
                        tc_pipeline_handle ph = object_to_pipeline_handle(pipeline_obj);
                        tc::Log::info("viewport.pipeline setter: handle=(%u,%u)", ph.index, ph.generation);
                        tc_viewport_set_pipeline(self.handle_, ph);
                        // verify
                        tc_pipeline_handle check = tc_viewport_get_pipeline(self.handle_);
                        tc::Log::info("viewport.pipeline verify: handle=(%u,%u) valid=%d",
                            check.index, check.generation, tc_pipeline_handle_valid(check));
                    } catch (const std::exception& e) {
                        tc::Log::error("viewport.pipeline setter: %s", e.what());
                    }
                }
            }, nb::arg("value").none())

        // Layer mask
        .def_prop_rw("layer_mask",
            [](TcViewport& self) { return self.layer_mask(); },
            [](TcViewport& self, uint64_t m) { self.set_layer_mask(m); })

        // Override render target resolution from viewport pixel rect
        .def_prop_rw("override_resolution",
            [](TcViewport& self) {
                return self.is_valid() ? tc_viewport_get_override_resolution(self.handle_) : false;
            },
            [](TcViewport& self, bool value) {
                if (self.is_valid()) tc_viewport_set_override_resolution(self.handle_, value);
            })

        // Enabled
        .def_prop_rw("enabled",
            [](TcViewport& self) { return self.enabled(); },
            [](TcViewport& self, bool e) { self.set_enabled(e); })

        // Input mode
        .def_prop_rw("input_mode",
            [](TcViewport& self) {
                if (!self.is_valid()) return std::string("");
                const char* m = tc_viewport_get_input_mode(self.handle_);
                return m ? std::string(m) : std::string("");
            },
            [](TcViewport& self, const std::string& m) {
                if (self.is_valid()) tc_viewport_set_input_mode(self.handle_, m.c_str());
            })

        // Block input in editor
        .def_prop_rw("block_input_in_editor",
            [](TcViewport& self) {
                return self.is_valid() ? tc_viewport_get_block_input_in_editor(self.handle_) : false;
            },
            [](TcViewport& self, bool b) {
                if (self.is_valid()) tc_viewport_set_block_input_in_editor(self.handle_, b);
            })

        // Managed by scene pipeline
        .def_prop_rw("managed_by_scene_pipeline",
            [](TcViewport& self) -> nb::object {
                if (!self.is_valid()) return nb::none();
                const char* m = tc_viewport_get_managed_by(self.handle_);
                if (m && m[0]) {
                    return nb::cast(std::string(m));
                }
                return nb::none();
            },
            [](TcViewport& self, nb::object v) {
                if (!self.is_valid()) return;
                if (v.is_none()) {
                    tc_viewport_set_managed_by(self.handle_, "");
                } else {
                    tc_viewport_set_managed_by(self.handle_, nb::cast<std::string>(v).c_str());
                }
            })

        // Internal entities
        .def_prop_rw("internal_entities",
            [](TcViewport& self) -> nb::object {
                if (!self.is_valid()) return nb::none();
                if (!tc_viewport_has_internal_entities(self.handle_)) return nb::none();
                tc_entity_handle h = tc_viewport_get_internal_entities(self.handle_);
                return nb::cast(termin::Entity(h));
            },
            [](TcViewport& self, nb::object entity_obj) {
                if (!self.is_valid()) return;
                if (entity_obj.is_none()) {
                    tc_viewport_set_internal_entities(self.handle_, TC_ENTITY_HANDLE_INVALID);
                } else {
                    termin::Entity ent = nb::cast<termin::Entity>(entity_obj);
                    tc_viewport_set_internal_entities(self.handle_, ent.handle());
                }
            },
            nb::arg().none())

        // Effective layer mask (checks ViewportHintComponent on camera)
        .def_prop_ro("effective_layer_mask", [](TcViewport& self) -> uint64_t {
            tc_component* cam = self.camera();
            nb::object camera_obj = camera_component_from_tc(cam);
            if (!camera_obj.is_none()) {
                try {
                    nb::object entity = camera_obj.attr("entity");
                    if (!entity.is_none()) {
                        nb::module_ hint_module = nb::module_::import_("termin.visualization.core.viewport_hint");
                        nb::object hint_class = hint_module.attr("ViewportHintComponent");
                        nb::object hint = entity.attr("get_component")(hint_class);
                        if (!hint.is_none()) {
                            return nb::cast<uint64_t>(hint.attr("layer_mask"));
                        }
                    }
                } catch (const std::exception& e) {
                    tc::Log::error("Viewport.effective_layer_mask failed: %s", e.what());
                }
            }
            return self.layer_mask();
        })

        // Screen point to ray
        .def("screen_point_to_ray", [](TcViewport& self, float x, float y) -> nb::object {
            tc_component* cam = self.camera();
            nb::object camera_obj = camera_component_from_tc(cam);
            if (camera_obj.is_none()) {
                return nb::none();
            }
            try {
                nb::object entity = camera_obj.attr("entity");
                if (entity.is_none()) {
                    return nb::none();
                }
                int px, py, pw, ph;
                self.get_pixel_rect(px, py, pw, ph);
                auto rect = std::make_tuple(px, py, pw, ph);
                return camera_obj.attr("screen_point_to_ray")(x, y, nb::arg("viewport_rect") = rect);
            } catch (const std::exception& e) {
                tc::Log::error("Viewport.screen_point_to_ray failed: %s", e.what());
                return nb::none();
            }
        }, nb::arg("x"), nb::arg("y"))

        // Serialize
        .def("serialize", [](TcViewport& self) {
            nb::dict result;

            result["name"] = self.name();

            // Camera entity name
            tc_component* cam = self.camera();
            nb::object camera_obj = camera_component_from_tc(cam);
            if (!camera_obj.is_none()) {
                try {
                    nb::object entity = camera_obj.attr("entity");
                    if (!entity.is_none()) {
                        result["camera_entity"] = entity.attr("name");
                    }
                } catch (const std::exception& e) {
                    tc::Log::error("Viewport.serialize camera lookup failed: %s", e.what());
                }
            }

            float rx, ry, rw, rh;
            self.get_rect(rx, ry, rw, rh);
            result["rect"] = nb::make_tuple(rx, ry, rw, rh);
            result["depth"] = self.depth();

            // Pipeline name
            tc_pipeline_handle ph = self.pipeline();
            if (tc_pipeline_handle_valid(ph)) {
                const char* pname = tc_pipeline_get_name(ph);
                if (pname && pname[0]) {
                    result["pipeline"] = nb::str(pname);
                }
            }

            if (self.is_valid()) {
                const char* im = tc_viewport_get_input_mode(self.handle_);
                result["input_mode"] = im ? std::string(im) : "";
                result["block_input_in_editor"] = tc_viewport_get_block_input_in_editor(self.handle_);
            }
            result["enabled"] = self.enabled();

            uint64_t mask = self.layer_mask();
            if (mask != 0xFFFFFFFFFFFFFFFFULL) {
                char buf[32];
                snprintf(buf, sizeof(buf), "0x%llx", (unsigned long long)mask);
                result["layer_mask"] = std::string(buf);
            }

            return result;
        })

        // Handle access (as tuple for Python hashability)
        .def("_viewport_handle", [](TcViewport& self) {
            // Return Python tuple instead of C++ std::tuple to avoid RTTI issues across modules
            return nb::make_tuple(self.handle_.index, self.handle_.generation);
        })

        // Stable handle for use as dictionary key
        .def_prop_ro("handle", [](TcViewport& self) -> uint64_t {
            // Combine index and generation into 64-bit value for dict key
            return (static_cast<uint64_t>(self.handle_.index) << 32) | self.handle_.generation;
        })

        // Create from handle tuple (for cross-module interop)
        .def_static("_from_handle", [](std::tuple<uint32_t, uint32_t> h) {
            tc_viewport_handle handle;
            handle.index = std::get<0>(h);
            handle.generation = std::get<1>(h);
            return TcViewport(handle);
        }, nb::arg("handle"))

        // Destroy the viewport
        .def("destroy", &TcViewport::destroy)
        ;
}

} // namespace termin

NB_MODULE(_viewport_native, m) {
    m.doc() = "Viewport native module (TcViewport)";
    nb::module_::import_("termin.scene._scene_native");
    termin::bind_tc_viewport_class(m);
}
