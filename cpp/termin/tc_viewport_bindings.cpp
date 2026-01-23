// tc_viewport_bindings.cpp - Direct bindings for tc_viewport C API
#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

#include "../../core_c/include/tc_viewport.h"
#include "../../core_c/include/tc_scene.h"
#include "../../core_c/include/tc_component.h"
#include "../../core_c/include/tc_pipeline.h"

namespace nb = nanobind;

namespace termin {

void bind_tc_viewport(nb::module_& m) {
    nb::class_<tc_viewport>(m, "Viewport")
        // Constructor
        .def("__init__", [](tc_viewport* self,
                           const std::string& name,
                           nb::object scene,
                           nb::object camera,
                           std::tuple<float, float, float, float> rect,
                           nb::object canvas,
                           int depth,
                           nb::object pipeline,
                           const std::string& input_mode,
                           bool block_input_in_editor,
                           const std::string& managed_by_scene_pipeline,
                           uint64_t layer_mask,
                           bool enabled,
                           nb::object internal_entities,
                           std::tuple<int, int, int, int> pixel_rect) {
            // Get tc_scene* from Scene
            tc_scene* tc_s = nullptr;
            if (!scene.is_none()) {
                nb::object tc_scene_obj = scene.attr("_tc_scene");
                uintptr_t ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                tc_s = reinterpret_cast<tc_scene*>(ptr);
            }

            // Get tc_component* from CameraComponent
            tc_component* tc_c = nullptr;
            if (!camera.is_none()) {
                uintptr_t ptr = nb::cast<uintptr_t>(camera.attr("c_component_ptr")());
                tc_c = reinterpret_cast<tc_component*>(ptr);
            }

            // Create viewport
            tc_viewport* vp = tc_viewport_new(name.c_str(), tc_s, tc_c);

            // Set rect
            tc_viewport_set_rect(vp, std::get<0>(rect), std::get<1>(rect),
                                std::get<2>(rect), std::get<3>(rect));
            tc_viewport_set_pixel_rect(vp, std::get<0>(pixel_rect), std::get<1>(pixel_rect),
                                      std::get<2>(pixel_rect), std::get<3>(pixel_rect));

            // Set properties
            tc_viewport_set_depth(vp, depth);
            tc_viewport_set_layer_mask(vp, layer_mask);
            tc_viewport_set_enabled(vp, enabled);
            tc_viewport_set_input_mode(vp, input_mode.c_str());
            tc_viewport_set_block_input_in_editor(vp, block_input_in_editor);
            if (!managed_by_scene_pipeline.empty()) {
                tc_viewport_set_managed_by(vp, managed_by_scene_pipeline.c_str());
            }

            // Canvas (Python object stored directly)
            if (!canvas.is_none()) {
                tc_viewport_set_canvas(vp, canvas.ptr());
            }

            // Pipeline - get tc_pipeline* and set py_wrapper
            if (!pipeline.is_none()) {
                nb::object tc_pl = pipeline.attr("_tc_pipeline");
                tc_pipeline* tc_p = nb::cast<tc_pipeline*>(tc_pl);
                tc_p->py_wrapper = pipeline.ptr();
                vp->pipeline = tc_p;
            }

            // Internal entities - store Python Entity directly in internal_entities field
            // (we reuse the tc_entity* slot to store PyObject*)
            if (!internal_entities.is_none()) {
                vp->internal_entities = reinterpret_cast<tc_entity*>(internal_entities.ptr());
            }

            // Copy into placement
            memcpy(self, vp, sizeof(tc_viewport));
            // Don't free vp - we copied the data, self owns it now
            // But we need to handle the allocated strings - they're now owned by self
            free(vp);  // Free the struct itself, not the contents
        },
        nb::arg("name"),
        nb::arg("scene"),
        nb::arg("camera"),
        nb::arg("rect") = std::make_tuple(0.0f, 0.0f, 1.0f, 1.0f),
        nb::arg("canvas") = nb::none(),
        nb::arg("depth") = 0,
        nb::arg("pipeline") = nb::none(),
        nb::arg("input_mode") = "simple",
        nb::arg("block_input_in_editor") = false,
        nb::arg("managed_by_scene_pipeline") = "",
        nb::arg("layer_mask") = 0xFFFFFFFFFFFFFFFFULL,
        nb::arg("enabled") = true,
        nb::arg("internal_entities") = nb::none(),
        nb::arg("pixel_rect") = std::make_tuple(0, 0, 1, 1))

        // Name
        .def_prop_rw("name",
            [](tc_viewport& self) {
                const char* n = tc_viewport_get_name(&self);
                return n ? std::string(n) : "";
            },
            [](tc_viewport& self, const std::string& n) {
                tc_viewport_set_name(&self, n.c_str());
            })

        // Scene - returns Python wrapper via tc_scene's py_wrapper
        .def_prop_rw("scene",
            [](tc_viewport& self) -> nb::object {
                tc_scene* s = tc_viewport_get_scene(&self);
                if (s) {
                    void* wrapper = tc_scene_get_py_wrapper(s);
                    if (wrapper) {
                        return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(wrapper));
                    }
                }
                return nb::none();
            },
            [](tc_viewport& self, nb::object scene_obj) {
                if (scene_obj.is_none()) {
                    tc_viewport_set_scene(&self, nullptr);
                } else {
                    nb::object tc_scene_obj = scene_obj.attr("_tc_scene");
                    uintptr_t ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                    tc_viewport_set_scene(&self, reinterpret_cast<tc_scene*>(ptr));
                }
            })

        // Camera - returns Python wrapper via tc_component's wrapper
        .def_prop_rw("camera",
            [](tc_viewport& self) -> nb::object {
                tc_component* c = tc_viewport_get_camera(&self);
                if (c && c->wrapper) {
                    return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(c->wrapper));
                }
                return nb::none();
            },
            [](tc_viewport& self, nb::object camera_obj) {
                if (camera_obj.is_none()) {
                    tc_viewport_set_camera(&self, nullptr);
                } else {
                    uintptr_t ptr = nb::cast<uintptr_t>(camera_obj.attr("c_component_ptr")());
                    tc_viewport_set_camera(&self, reinterpret_cast<tc_component*>(ptr));
                }
            })

        // Rect (normalized 0-1)
        .def_prop_rw("rect",
            [](tc_viewport& self) {
                float x, y, w, h;
                tc_viewport_get_rect(&self, &x, &y, &w, &h);
                return std::make_tuple(x, y, w, h);
            },
            [](tc_viewport& self, std::tuple<float, float, float, float> r) {
                tc_viewport_set_rect(&self, std::get<0>(r), std::get<1>(r),
                                    std::get<2>(r), std::get<3>(r));
            })

        // Pixel rect
        .def_prop_rw("pixel_rect",
            [](tc_viewport& self) {
                int px, py, pw, ph;
                tc_viewport_get_pixel_rect(&self, &px, &py, &pw, &ph);
                return std::make_tuple(px, py, pw, ph);
            },
            [](tc_viewport& self, std::tuple<int, int, int, int> r) {
                tc_viewport_set_pixel_rect(&self, std::get<0>(r), std::get<1>(r),
                                          std::get<2>(r), std::get<3>(r));
            })

        .def("update_pixel_rect", [](tc_viewport& self, int w, int h) {
            tc_viewport_update_pixel_rect(&self, w, h);
        }, nb::arg("display_width"), nb::arg("display_height"))

        // Canvas
        .def_prop_rw("canvas",
            [](tc_viewport& self) -> nb::object {
                void* ptr = tc_viewport_get_canvas(&self);
                if (ptr) {
                    return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(ptr));
                }
                return nb::none();
            },
            [](tc_viewport& self, nb::object canvas) {
                tc_viewport_set_canvas(&self, canvas.is_none() ? nullptr : canvas.ptr());
            })

        // Depth
        .def_prop_rw("depth",
            [](tc_viewport& self) { return tc_viewport_get_depth(&self); },
            [](tc_viewport& self, int d) { tc_viewport_set_depth(&self, d); })

        // Pipeline
        .def_prop_rw("pipeline",
            [](tc_viewport& self) -> nb::object {
                tc_pipeline* p = self.pipeline;
                if (p && p->py_wrapper) {
                    return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(p->py_wrapper));
                }
                return nb::none();
            },
            [](tc_viewport& self, nb::object pipeline_obj) {
                if (pipeline_obj.is_none()) {
                    self.pipeline = nullptr;
                } else {
                    nb::object tc_pl = pipeline_obj.attr("_tc_pipeline");
                    tc_pipeline* tc_p = nb::cast<tc_pipeline*>(tc_pl);
                    tc_p->py_wrapper = pipeline_obj.ptr();
                    self.pipeline = tc_p;
                }
            })

        // Layer mask
        .def_prop_rw("layer_mask",
            [](tc_viewport& self) { return tc_viewport_get_layer_mask(&self); },
            [](tc_viewport& self, uint64_t m) { tc_viewport_set_layer_mask(&self, m); })

        // Enabled
        .def_prop_rw("enabled",
            [](tc_viewport& self) { return tc_viewport_get_enabled(&self); },
            [](tc_viewport& self, bool e) { tc_viewport_set_enabled(&self, e); })

        // Input mode
        .def_prop_rw("input_mode",
            [](tc_viewport& self) {
                const char* m = tc_viewport_get_input_mode(&self);
                return m ? std::string(m) : "";
            },
            [](tc_viewport& self, const std::string& m) {
                tc_viewport_set_input_mode(&self, m.c_str());
            })

        // Block input in editor
        .def_prop_rw("block_input_in_editor",
            [](tc_viewport& self) { return tc_viewport_get_block_input_in_editor(&self); },
            [](tc_viewport& self, bool b) { tc_viewport_set_block_input_in_editor(&self, b); })

        // Managed by scene pipeline
        .def_prop_rw("managed_by_scene_pipeline",
            [](tc_viewport& self) -> nb::object {
                const char* m = tc_viewport_get_managed_by(&self);
                if (m && m[0]) {
                    return nb::cast(std::string(m));
                }
                return nb::none();
            },
            [](tc_viewport& self, nb::object v) {
                if (v.is_none()) {
                    tc_viewport_set_managed_by(&self, "");
                } else {
                    tc_viewport_set_managed_by(&self, nb::cast<std::string>(v).c_str());
                }
            })

        // Internal entities (Python Entity object stored in tc_entity* slot)
        .def_prop_rw("internal_entities",
            [](tc_viewport& self) -> nb::object {
                if (self.internal_entities) {
                    return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(self.internal_entities));
                }
                return nb::none();
            },
            [](tc_viewport& self, nb::object entity_obj) {
                if (entity_obj.is_none()) {
                    self.internal_entities = nullptr;
                } else {
                    self.internal_entities = reinterpret_cast<tc_entity*>(entity_obj.ptr());
                }
            })

        // Effective layer mask (checks ViewportHintComponent on camera)
        .def_prop_ro("effective_layer_mask", [](tc_viewport& self) -> uint64_t {
            tc_component* cam = tc_viewport_get_camera(&self);
            if (cam && cam->wrapper) {
                try {
                    nb::object camera_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(cam->wrapper));
                    nb::object entity = camera_obj.attr("entity");
                    if (!entity.is_none()) {
                        nb::module_ hint_module = nb::module_::import_("termin.visualization.core.viewport_hint");
                        nb::object hint_class = hint_module.attr("ViewportHintComponent");
                        nb::object hint = entity.attr("get_component")(hint_class);
                        if (!hint.is_none()) {
                            return nb::cast<uint64_t>(hint.attr("layer_mask"));
                        }
                    }
                } catch (...) {
                    // Fall through to default
                }
            }
            return tc_viewport_get_layer_mask(&self);
        })

        // Screen point to ray
        .def("screen_point_to_ray", [](tc_viewport& self, float x, float y) -> nb::object {
            tc_component* cam = tc_viewport_get_camera(&self);
            if (!cam || !cam->wrapper) {
                return nb::none();
            }
            try {
                nb::object camera_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(cam->wrapper));
                nb::object entity = camera_obj.attr("entity");
                if (entity.is_none()) {
                    return nb::none();
                }
                int px, py, pw, ph;
                tc_viewport_get_pixel_rect(&self, &px, &py, &pw, &ph);
                auto rect = std::make_tuple(px, py, pw, ph);
                return camera_obj.attr("screen_point_to_ray")(x, y, nb::arg("viewport_rect") = rect);
            } catch (...) {
                return nb::none();
            }
        }, nb::arg("x"), nb::arg("y"))

        // Serialize
        .def("serialize", [](tc_viewport& self) {
            nb::dict result;

            const char* n = tc_viewport_get_name(&self);
            result["name"] = n ? std::string(n) : "";

            // Camera entity name
            tc_component* cam = tc_viewport_get_camera(&self);
            if (cam && cam->wrapper) {
                try {
                    nb::object camera_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(cam->wrapper));
                    nb::object entity = camera_obj.attr("entity");
                    if (!entity.is_none()) {
                        result["camera_entity"] = entity.attr("name");
                    }
                } catch (...) {}
            }

            float rx, ry, rw, rh;
            tc_viewport_get_rect(&self, &rx, &ry, &rw, &rh);
            result["rect"] = nb::make_tuple(rx, ry, rw, rh);
            result["depth"] = tc_viewport_get_depth(&self);

            // Pipeline name
            tc_pipeline* pl = self.pipeline;
            if (pl && pl->py_wrapper) {
                try {
                    nb::object pl_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(pl->py_wrapper));
                    result["pipeline"] = pl_obj.attr("name");
                } catch (...) {}
            }

            const char* im = tc_viewport_get_input_mode(&self);
            result["input_mode"] = im ? std::string(im) : "";
            result["block_input_in_editor"] = tc_viewport_get_block_input_in_editor(&self);
            result["enabled"] = tc_viewport_get_enabled(&self);

            uint64_t mask = tc_viewport_get_layer_mask(&self);
            if (mask != 0xFFFFFFFFFFFFFFFFULL) {
                char buf[32];
                snprintf(buf, sizeof(buf), "0x%llx", (unsigned long long)mask);
                result["layer_mask"] = std::string(buf);
            }

            return result;
        })
        ;
}

} // namespace termin
