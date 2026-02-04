// render_pipeline_bindings.cpp - nanobind bindings for RenderPipeline
#include "common.hpp"
#include "tc_log.hpp"
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/pair.h>
#include <nanobind/stl/array.h>
#include <iostream>

extern "C" {
#include "inspect/tc_binding.h"
}

#include "termin/render/render_pipeline.hpp"
#include "termin/render/tc_pass.hpp"
#include "termin/render/graph_compiler.hpp"

namespace termin {

void bind_render_pipeline(nb::module_& m) {
    nb::class_<RenderPipeline>(m, "RenderPipeline")
        .def(nb::init<const std::string&>(), nb::arg("name") = "default")

        // Constructor with passes and specs (accepts Python FramePass objects via _tc_pass attr)
        .def("__init__", [](RenderPipeline* self,
                           const std::string& name,
                           nb::list init_passes,
                           const std::vector<ResourceSpec>& init_specs) {
            new (self) RenderPipeline(name);
            for (size_t i = 0; i < nb::len(init_passes); i++) {
                nb::object pass_obj = init_passes[i];
                // Get _tc_pass attribute from FramePass
                if (nb::hasattr(pass_obj, "_tc_pass")) {
                    nb::object tc_pass_obj = pass_obj.attr("_tc_pass");
                    if (!tc_pass_obj.is_none()) {
                        // Try TcPassRef
                        if (nb::isinstance<TcPassRef>(tc_pass_obj)) {
                            TcPassRef ref = nb::cast<TcPassRef>(tc_pass_obj);
                            if (ref.valid()) {
                                self->add_pass(ref.ptr());
                            }
                        }
                        // Try TcPass*
                        else if (nb::isinstance<TcPass>(tc_pass_obj)) {
                            TcPass* pass = nb::cast<TcPass*>(tc_pass_obj);
                            if (pass && pass->ptr()) {
                                self->add_pass(pass->ptr());
                            }
                        }
                    }
                }
            }
            for (const auto& spec : init_specs) {
                self->add_spec(spec);
            }
        }, nb::arg("name") = "default",
           nb::arg("_init_passes") = nb::list(),
           nb::arg("_init_specs") = std::vector<ResourceSpec>{})

        // Name
        .def_prop_rw("name", &RenderPipeline::name, &RenderPipeline::set_name)

        // Access tc_pipeline (for compatibility with existing code)
        .def_prop_ro("_tc_pipeline", [](RenderPipeline& self) {
            return self.ptr();
        }, nb::rv_policy::reference)

        // Access handle as tuple (for new handle-based API)
        .def_prop_ro("_pipeline_handle", [](RenderPipeline& self) -> std::tuple<uint32_t, uint32_t> {
            tc_pipeline_handle h = self.handle();
            return std::make_tuple(h.index, h.generation);
        })

        // Pass count
        .def_prop_ro("pass_count", &RenderPipeline::pass_count)

        // Pass management
        .def("add_pass", [](RenderPipeline& self, TcPassRef pass_ref) {
            if (pass_ref.valid()) {
                self.add_pass(pass_ref.ptr());
            }
        })
        .def("add_pass", [](RenderPipeline& self, TcPass* pass) {
            if (pass && pass->ptr()) {
                self.add_pass(pass->ptr());
            }
        })
        // Accept Python FramePass objects via _tc_pass attribute
        .def("add_pass", [](RenderPipeline& self, nb::object pass_obj) {
            if (nb::hasattr(pass_obj, "_tc_pass")) {
                nb::object tc_pass_obj = pass_obj.attr("_tc_pass");
                if (!tc_pass_obj.is_none()) {
                    if (nb::isinstance<TcPassRef>(tc_pass_obj)) {
                        TcPassRef ref = nb::cast<TcPassRef>(tc_pass_obj);
                        if (ref.valid()) {
                            self.add_pass(ref.ptr());
                        }
                    } else if (nb::isinstance<TcPass>(tc_pass_obj)) {
                        TcPass* pass = nb::cast<TcPass*>(tc_pass_obj);
                        if (pass && pass->ptr()) {
                            self.add_pass(pass->ptr());
                        }
                    }
                }
            }
        })
        .def("remove_pass", [](RenderPipeline& self, TcPassRef pass_ref) {
            if (pass_ref.valid()) {
                self.remove_pass(pass_ref.ptr());
            }
        })
        // Accept Python FramePass objects via _tc_pass attribute
        .def("remove_pass", [](RenderPipeline& self, nb::object pass_obj) {
            if (nb::hasattr(pass_obj, "_tc_pass")) {
                nb::object tc_pass_obj = pass_obj.attr("_tc_pass");
                if (!tc_pass_obj.is_none() && nb::isinstance<TcPassRef>(tc_pass_obj)) {
                    TcPassRef ref = nb::cast<TcPassRef>(tc_pass_obj);
                    if (ref.valid()) {
                        self.remove_pass(ref.ptr());
                    }
                }
            }
        })
        .def("remove_passes_by_name", &RenderPipeline::remove_passes_by_name,
             nb::arg("name"),
             "Remove all passes with the given name, returns count of removed passes")
        .def("insert_pass_before", [](RenderPipeline& self, TcPassRef pass_ref, TcPassRef before_ref) {
            if (pass_ref.valid()) {
                self.insert_pass_before(pass_ref.ptr(), before_ref.valid() ? before_ref.ptr() : nullptr);
            }
        })
        // Accept Python FramePass objects via _tc_pass attribute
        .def("insert_pass_before", [](RenderPipeline& self, nb::object pass_obj, nb::object before_obj) {
            tc_pass* pass_ptr = nullptr;
            tc_pass* before_ptr = nullptr;

            if (nb::hasattr(pass_obj, "_tc_pass")) {
                nb::object tc_pass_obj = pass_obj.attr("_tc_pass");
                if (!tc_pass_obj.is_none() && nb::isinstance<TcPassRef>(tc_pass_obj)) {
                    TcPassRef ref = nb::cast<TcPassRef>(tc_pass_obj);
                    if (ref.valid()) pass_ptr = ref.ptr();
                }
            }

            if (!before_obj.is_none() && nb::hasattr(before_obj, "_tc_pass")) {
                nb::object tc_pass_obj = before_obj.attr("_tc_pass");
                if (!tc_pass_obj.is_none() && nb::isinstance<TcPassRef>(tc_pass_obj)) {
                    TcPassRef ref = nb::cast<TcPassRef>(tc_pass_obj);
                    if (ref.valid()) before_ptr = ref.ptr();
                }
            }

            if (pass_ptr) {
                self.insert_pass_before(pass_ptr, before_ptr);
            }
        })
        .def("get_pass", [](RenderPipeline& self, const std::string& name) {
            return TcPassRef(self.get_pass(name));
        })
        // Alias for compatibility
        .def("get_pass_by_name", [](RenderPipeline& self, const std::string& name) {
            return TcPassRef(self.get_pass(name));
        })
        .def("get_pass_at", [](RenderPipeline& self, size_t index) {
            return TcPassRef(self.get_pass_at(index));
        })

        // Iterate passes
        .def_prop_ro("passes", [](RenderPipeline& self) {
            std::vector<TcPassRef> result;
            for (size_t i = 0; i < self.pass_count(); i++) {
                tc_pass* p = self.get_pass_at(i);
                if (p) {
                    result.push_back(TcPassRef(p));
                }
            }
            return result;
        })

        // Specs management
        .def("add_spec", &RenderPipeline::add_spec)
        .def("clear_specs", &RenderPipeline::clear_specs)
        .def_prop_ro("spec_count", &RenderPipeline::spec_count)
        .def("get_spec_at", [](RenderPipeline& self, size_t index) -> nb::object {
            const ResourceSpec* spec = self.get_spec_at(index);
            if (!spec) return nb::none();
            return nb::cast(*spec);
        })

        // Pipeline specs as list
        .def_prop_ro("pipeline_specs", [](RenderPipeline& self) {
            return self.specs();
        })

        // Destroy (no-op for C++ managed object, but needed for API compatibility)
        .def("destroy", [](RenderPipeline& /*self*/) {
            // C++ RenderPipeline is destroyed automatically when Python ref count drops
            // This method exists for API compatibility with old Python RenderPipeline
        })

        // FBO pool access (moved from RenderEngine)
        .def("get_fbo", [](RenderPipeline& self, const std::string& key) -> FramebufferHandle* {
            return self.fbo_pool().get(key);
        }, nb::arg("key"), nb::rv_policy::reference)
        .def("get_fbo_keys", [](RenderPipeline& self) -> std::vector<std::string> {
            return self.fbo_pool().keys();
        })
        .def("clear_fbo_pool", [](RenderPipeline& self) {
            self.fbo_pool().clear();
        })

        // Dirty flag management
        .def_prop_ro("is_dirty", &RenderPipeline::is_dirty,
            "Returns True if pipeline needs frame graph rebuild")
        .def("mark_dirty", &RenderPipeline::mark_dirty,
            "Mark pipeline for frame graph rebuild on next render")

        // Iteration support
        .def("__len__", &RenderPipeline::pass_count)

        // Serialize to dict
        .def("serialize", [](RenderPipeline& self) -> nb::dict {
            nb::dict result;
            result["name"] = self.name();

            // Serialize passes via TcPassRef
            nb::list passes_list;
            for (size_t i = 0; i < self.pass_count(); i++) {
                tc_pass* p = self.get_pass_at(i);
                if (!p) continue;

                TcPassRef ref(p);
                nb::object serialized = nb::cast(ref).attr("serialize")();
                if (!serialized.is_none()) {
                    passes_list.append(serialized);
                }
            }
            result["passes"] = passes_list;

            // Serialize pipeline specs
            nb::list specs_list;
            for (const auto& spec : self.specs()) {
                nb::dict spec_dict;
                spec_dict["resource"] = spec.resource;
                spec_dict["resource_type"] = spec.resource_type;
                if (spec.size) {
                    nb::list sz;
                    sz.append(spec.size->first);
                    sz.append(spec.size->second);
                    spec_dict["size"] = sz;
                }
                if (spec.clear_color) {
                    const auto& cc = *spec.clear_color;
                    nb::list color;
                    color.append(cc[0]);
                    color.append(cc[1]);
                    color.append(cc[2]);
                    color.append(cc[3]);
                    spec_dict["clear_color"] = color;
                }
                if (spec.clear_depth) {
                    spec_dict["clear_depth"] = *spec.clear_depth;
                }
                if (spec.format) {
                    spec_dict["format"] = *spec.format;
                }
                if (spec.samples != 1) {
                    spec_dict["samples"] = spec.samples;
                }
                specs_list.append(spec_dict);
            }
            result["pipeline_specs"] = specs_list;

            return result;
        })

        // Deserialize from dict (static method)
        .def_static("deserialize", [](nb::dict data, nb::object resource_manager) -> RenderPipeline* {
            // Import FramePass for deserialization
            nb::module_ core_module = nb::module_::import_("termin.visualization.render.framegraph.core");
            nb::object FramePass = core_module.attr("FramePass");

            std::string name = "default";
            if (data.contains("name")) {
                name = nb::cast<std::string>(data["name"]);
            }

            RenderPipeline* pipeline = new RenderPipeline(name);

            // Deserialize passes
            if (data.contains("passes")) {
                nb::list passes = nb::cast<nb::list>(data["passes"]);
                for (size_t i = 0; i < nb::len(passes); i++) {
                    try {
                        nb::dict pass_data = nb::cast<nb::dict>(passes[i]);
                        nb::object frame_pass = FramePass.attr("deserialize")(pass_data, resource_manager);
                        if (!frame_pass.is_none() && nb::hasattr(frame_pass, "_tc_pass")) {
                            nb::object tc_pass_obj = frame_pass.attr("_tc_pass");
                            if (!tc_pass_obj.is_none() && nb::isinstance<TcPassRef>(tc_pass_obj)) {
                                TcPassRef ref = nb::cast<TcPassRef>(tc_pass_obj);
                                if (ref.valid()) {
                                    pipeline->add_pass(ref.ptr());
                                }
                            }
                        }
                    } catch (const std::exception& e) {
                        tc::Log::error("RenderPipeline::deserialize: failed to deserialize pass %zu: %s",
                                      i, e.what());
                        throw;
                    }
                }
            }

            // Deserialize pipeline specs
            if (data.contains("pipeline_specs")) {
                nb::list specs = nb::cast<nb::list>(data["pipeline_specs"]);
                for (size_t i = 0; i < nb::len(specs); i++) {
                    nb::dict spec_data = nb::cast<nb::dict>(specs[i]);
                    ResourceSpec spec;

                    if (spec_data.contains("resource")) {
                        spec.resource = nb::cast<std::string>(spec_data["resource"]);
                    }
                    if (spec_data.contains("resource_type")) {
                        spec.resource_type = nb::cast<std::string>(spec_data["resource_type"]);
                    }
                    if (spec_data.contains("size")) {
                        nb::list sz = nb::cast<nb::list>(spec_data["size"]);
                        spec.size = std::make_pair(nb::cast<int>(sz[0]), nb::cast<int>(sz[1]));
                    }
                    if (spec_data.contains("clear_color")) {
                        nb::list cc = nb::cast<nb::list>(spec_data["clear_color"]);
                        spec.clear_color = std::array<double, 4>{
                            nb::cast<double>(cc[0]), nb::cast<double>(cc[1]),
                            nb::cast<double>(cc[2]), nb::cast<double>(cc[3])
                        };
                    }
                    if (spec_data.contains("clear_depth")) {
                        spec.clear_depth = nb::cast<float>(spec_data["clear_depth"]);
                    }
                    if (spec_data.contains("format")) {
                        spec.format = nb::cast<std::string>(spec_data["format"]);
                    }
                    if (spec_data.contains("samples")) {
                        spec.samples = nb::cast<int>(spec_data["samples"]);
                    }

                    pipeline->add_spec(spec);
                }
            }

            return pipeline;
        }, nb::rv_policy::take_ownership)

        // Deep copy pipeline via serialization/deserialization
        .def("copy", [](RenderPipeline& self, nb::object resource_manager) -> nb::object {
            nb::dict data = nb::cast<nb::dict>(nb::cast(&self).attr("serialize")());

            nb::module_ render_module = nb::module_::import_("termin._native.render");
            nb::object RenderPipelineClass = render_module.attr("RenderPipeline");
            nb::object result = RenderPipelineClass.attr("deserialize")(data, resource_manager);

            return result;
        }, nb::arg("resource_manager"));

    // compile_graph_from_json - compile render pipeline from JSON string
    m.def("compile_graph_from_json", [](const std::string& json_str) {
        return tc::compile_graph(json_str);
    }, nb::arg("json_str"),
       nb::rv_policy::take_ownership,
       "Compile a render pipeline from JSON graph representation");
}

} // namespace termin
