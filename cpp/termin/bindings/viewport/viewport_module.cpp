// viewport_module.cpp - Viewport native module (_viewport_native)
// Contains TcViewport binding, shared between _entity_native and _native

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

#include "termin/viewport/tc_viewport_handle.hpp"
#include "termin/entity/entity.hpp"
#include "termin_core.h"
#include "tc_pipeline.h"

namespace nb = nanobind;

namespace termin {

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

            // Create viewport (ref_count starts at 1)
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

            // Pipeline - get tc_pipeline* and set py_wrapper
            if (!pipeline.is_none()) {
                nb::object tc_pl = pipeline.attr("_tc_pipeline");
                tc_pipeline* tc_p = nb::cast<tc_pipeline*>(tc_pl);
                Py_INCREF(pipeline.ptr());
                tc_p->py_wrapper = pipeline.ptr();
                vp->pipeline = tc_p;
            }

            // Internal entities - store pool + entity_id
            if (!internal_entities.is_none()) {
                termin::Entity ent = nb::cast<termin::Entity>(internal_entities);
                tc_viewport_set_internal_entities(vp, ent.pool(), ent.id());
            }

            // Construct TcViewport in-place (don't add_ref since tc_viewport_new already set ref_count=1)
            new (self) TcViewport();
            self->ptr_ = vp;
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

        // Reference count (for debugging)
        .def_prop_ro("ref_count", &TcViewport::ref_count)

        // Name
        .def_prop_rw("name",
            [](TcViewport& self) {
                const char* n = self.name();
                return n ? std::string(n) : "";
            },
            [](TcViewport& self, const std::string& n) {
                if (self.ptr_) tc_viewport_set_name(self.ptr_, n.c_str());
            })

        // Scene - returns Python wrapper via tc_scene's py_wrapper
        .def_prop_rw("scene",
            [](TcViewport& self) -> nb::object {
                tc_scene* s = self.scene();
                if (s) {
                    void* wrapper = tc_scene_get_py_wrapper(s);
                    if (wrapper) {
                        return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(wrapper));
                    }
                }
                return nb::none();
            },
            [](TcViewport& self, nb::object scene_obj) {
                if (!self.ptr_) return;
                if (scene_obj.is_none()) {
                    tc_viewport_set_scene(self.ptr_, nullptr);
                } else {
                    nb::object tc_scene_obj = scene_obj.attr("_tc_scene");
                    uintptr_t ptr = nb::cast<uintptr_t>(tc_scene_obj.attr("scene_ptr")());
                    tc_viewport_set_scene(self.ptr_, reinterpret_cast<tc_scene*>(ptr));
                }
            })

        // Camera - returns Python wrapper via tc_component's wrapper
        .def_prop_rw("camera",
            [](TcViewport& self) -> nb::object {
                tc_component* c = self.camera();
                if (c && c->wrapper) {
                    return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(c->wrapper));
                }
                return nb::none();
            },
            [](TcViewport& self, nb::object camera_obj) {
                if (!self.ptr_) return;
                if (camera_obj.is_none()) {
                    tc_viewport_set_camera(self.ptr_, nullptr);
                } else {
                    uintptr_t ptr = nb::cast<uintptr_t>(camera_obj.attr("c_component_ptr")());
                    tc_viewport_set_camera(self.ptr_, reinterpret_cast<tc_component*>(ptr));
                }
            })

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

        // Pipeline
        .def_prop_rw("pipeline",
            [](TcViewport& self) -> nb::object {
                tc_pipeline* p = self.pipeline();
                if (p && p->py_wrapper) {
                    return nb::borrow<nb::object>(reinterpret_cast<PyObject*>(p->py_wrapper));
                }
                return nb::none();
            },
            [](TcViewport& self, nb::object pipeline_obj) {
                if (!self.ptr_) return;
                if (pipeline_obj.is_none()) {
                    self.ptr_->pipeline = nullptr;
                } else {
                    nb::object tc_pl = pipeline_obj.attr("_tc_pipeline");
                    tc_pipeline* tc_p = nb::cast<tc_pipeline*>(tc_pl);
                    Py_INCREF(pipeline_obj.ptr());
                    tc_p->py_wrapper = pipeline_obj.ptr();
                    self.ptr_->pipeline = tc_p;
                }
            })

        // Layer mask
        .def_prop_rw("layer_mask",
            [](TcViewport& self) { return self.layer_mask(); },
            [](TcViewport& self, uint64_t m) { self.set_layer_mask(m); })

        // Enabled
        .def_prop_rw("enabled",
            [](TcViewport& self) { return self.enabled(); },
            [](TcViewport& self, bool e) { self.set_enabled(e); })

        // Input mode
        .def_prop_rw("input_mode",
            [](TcViewport& self) {
                if (!self.ptr_) return std::string("");
                const char* m = tc_viewport_get_input_mode(self.ptr_);
                return m ? std::string(m) : std::string("");
            },
            [](TcViewport& self, const std::string& m) {
                if (self.ptr_) tc_viewport_set_input_mode(self.ptr_, m.c_str());
            })

        // Block input in editor
        .def_prop_rw("block_input_in_editor",
            [](TcViewport& self) {
                return self.ptr_ ? tc_viewport_get_block_input_in_editor(self.ptr_) : false;
            },
            [](TcViewport& self, bool b) {
                if (self.ptr_) tc_viewport_set_block_input_in_editor(self.ptr_, b);
            })

        // Managed by scene pipeline
        .def_prop_rw("managed_by_scene_pipeline",
            [](TcViewport& self) -> nb::object {
                if (!self.ptr_) return nb::none();
                const char* m = tc_viewport_get_managed_by(self.ptr_);
                if (m && m[0]) {
                    return nb::cast(std::string(m));
                }
                return nb::none();
            },
            [](TcViewport& self, nb::object v) {
                if (!self.ptr_) return;
                if (v.is_none()) {
                    tc_viewport_set_managed_by(self.ptr_, "");
                } else {
                    tc_viewport_set_managed_by(self.ptr_, nb::cast<std::string>(v).c_str());
                }
            })

        // Internal entities (stored as pool + entity_id)
        .def_prop_rw("internal_entities",
            [](TcViewport& self) -> nb::object {
                if (!self.ptr_) return nb::none();
                if (!tc_viewport_has_internal_entities(self.ptr_)) return nb::none();
                tc_entity_pool* pool = tc_viewport_get_internal_entities_pool(self.ptr_);
                tc_entity_id id = tc_viewport_get_internal_entities_id(self.ptr_);
                return nb::cast(termin::Entity(pool, id));
            },
            [](TcViewport& self, nb::object entity_obj) {
                if (!self.ptr_) return;
                if (entity_obj.is_none()) {
                    tc_viewport_set_internal_entities(self.ptr_, nullptr, TC_ENTITY_ID_INVALID);
                } else {
                    termin::Entity ent = nb::cast<termin::Entity>(entity_obj);
                    tc_viewport_set_internal_entities(self.ptr_, ent.pool(), ent.id());
                }
            })

        // Effective layer mask (checks ViewportHintComponent on camera)
        .def_prop_ro("effective_layer_mask", [](TcViewport& self) -> uint64_t {
            tc_component* cam = self.camera();
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
            return self.layer_mask();
        })

        // Screen point to ray
        .def("screen_point_to_ray", [](TcViewport& self, float x, float y) -> nb::object {
            tc_component* cam = self.camera();
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
                self.get_pixel_rect(px, py, pw, ph);
                auto rect = std::make_tuple(px, py, pw, ph);
                return camera_obj.attr("screen_point_to_ray")(x, y, nb::arg("viewport_rect") = rect);
            } catch (...) {
                return nb::none();
            }
        }, nb::arg("x"), nb::arg("y"))

        // Serialize
        .def("serialize", [](TcViewport& self) {
            nb::dict result;

            result["name"] = self.name();

            // Camera entity name
            tc_component* cam = self.camera();
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
            self.get_rect(rx, ry, rw, rh);
            result["rect"] = nb::make_tuple(rx, ry, rw, rh);
            result["depth"] = self.depth();

            // Pipeline name
            tc_pipeline* pl = self.pipeline();
            if (pl && pl->py_wrapper) {
                try {
                    nb::object pl_obj = nb::borrow<nb::object>(reinterpret_cast<PyObject*>(pl->py_wrapper));
                    result["pipeline"] = pl_obj.attr("name");
                } catch (...) {}
            }

            if (self.ptr_) {
                const char* im = tc_viewport_get_input_mode(self.ptr_);
                result["input_mode"] = im ? std::string(im) : "";
                result["block_input_in_editor"] = tc_viewport_get_block_input_in_editor(self.ptr_);
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

        // Raw pointer access (for C interop)
        .def("_tc_viewport_ptr", [](TcViewport& self) -> uintptr_t {
            return reinterpret_cast<uintptr_t>(self.ptr_);
        })
        ;
}

} // namespace termin

NB_MODULE(_viewport_native, m) {
    m.doc() = "Viewport native module (TcViewport)";
    termin::bind_tc_viewport_class(m);
}
