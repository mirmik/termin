#include "common.hpp"
#include "termin/render/mesh_gpu.hpp"
#include "termin/render/render.hpp"
#include "termin/mesh/mesh3.hpp"

extern "C" {
#include "termin_core.h"
}

namespace termin {

void bind_gpu(nb::module_& m) {
    nb::class_<MeshGPU>(m, "MeshGPU")
        .def(nb::init<>())
        .def_rw("uploaded_version", &MeshGPU::uploaded_version)
        .def_prop_ro("is_uploaded", &MeshGPU::is_uploaded)
        // draw(context, tc_mesh*, version) - единственный интерфейс
        .def("draw", [](MeshGPU& self, nb::object context, const tc_mesh* mesh, int version) {
            GraphicsBackend* graphics = nb::cast<GraphicsBackend*>(context.attr("graphics"));
            int64_t context_key = nb::cast<int64_t>(context.attr("context_key"));
            self.draw(graphics, mesh, version, context_key);
        }, nb::arg("context"), nb::arg("mesh"), nb::arg("version"))
        .def("invalidate", &MeshGPU::invalidate)
        .def("delete", &MeshGPU::delete_resources);
}

} // namespace termin
