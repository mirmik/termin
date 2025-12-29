#include "common.hpp"
#include "termin/render/mesh_gpu.hpp"
#include "termin/render/texture_gpu.hpp"
#include "termin/render/render.hpp"
#include "termin/mesh/mesh3.hpp"
#include "termin/assets/texture_data.hpp"

extern "C" {
#include "termin_core.h"
}

namespace termin {

void bind_gpu(py::module_& m) {
    py::class_<MeshGPU>(m, "MeshGPU")
        .def(py::init<>())
        .def_readwrite("uploaded_version", &MeshGPU::uploaded_version)
        .def_property_readonly("is_uploaded", &MeshGPU::is_uploaded)
        // draw(context, tc_mesh*, version) - единственный интерфейс
        .def("draw", [](MeshGPU& self, py::object context, const tc_mesh* mesh, int version) {
            GraphicsBackend* graphics = context.attr("graphics").cast<GraphicsBackend*>();
            int64_t context_key = context.attr("context_key").cast<int64_t>();
            self.draw(graphics, mesh, version, context_key);
        }, py::arg("context"), py::arg("mesh"), py::arg("version"))
        .def("invalidate", &MeshGPU::invalidate)
        .def("delete", &MeshGPU::delete_resources);

    py::class_<TextureGPU>(m, "TextureGPU")
        .def(py::init<>())
        .def_readwrite("uploaded_version", &TextureGPU::uploaded_version)
        .def_property_readonly("is_uploaded", &TextureGPU::is_uploaded)
        .def("bind", &TextureGPU::bind,
            py::arg("graphics"), py::arg("texture_data"), py::arg("version"),
            py::arg("unit") = 0, py::arg("context_key") = 0)
        .def("invalidate", &TextureGPU::invalidate)
        .def("delete", &TextureGPU::delete_resources);
}

} // namespace termin
