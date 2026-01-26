// render_pipeline_bindings.cpp - nanobind bindings for RenderPipeline
#include "common.hpp"
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "termin/render/render_pipeline.hpp"
#include "termin/render/tc_pass.hpp"

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
        .def("remove_pass", [](RenderPipeline& self, TcPassRef pass_ref) {
            if (pass_ref.valid()) {
                self.remove_pass(pass_ref.ptr());
            }
        })
        .def("insert_pass_before", [](RenderPipeline& self, TcPassRef pass_ref, TcPassRef before_ref) {
            if (pass_ref.valid()) {
                self.insert_pass_before(pass_ref.ptr(), before_ref.valid() ? before_ref.ptr() : nullptr);
            }
        })
        .def("get_pass", [](RenderPipeline& self, const std::string& name) {
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

        // Iteration support
        .def("__len__", &RenderPipeline::pass_count);
}

} // namespace termin
