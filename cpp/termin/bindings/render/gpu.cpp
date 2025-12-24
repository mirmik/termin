#include "common.hpp"
#include "termin/render/mesh_gpu.hpp"
#include "termin/render/texture_gpu.hpp"
#include "termin/render/render.hpp"
#include "termin/mesh/mesh3.hpp"
#include "termin/assets/texture_data.hpp"

namespace termin {

void bind_gpu(py::module_& m) {
    py::class_<MeshGPU>(m, "MeshGPU")
        .def(py::init<>())
        .def_readwrite("uploaded_version", &MeshGPU::uploaded_version)
        .def_property_readonly("is_uploaded", &MeshGPU::is_uploaded)
        // Overload 1: explicit parameters
        .def("draw", [](MeshGPU& self, GraphicsBackend* graphics, const Mesh3& mesh, int version, int64_t context_key) {
            self.draw(graphics, mesh, version, context_key);
        }, py::arg("graphics"), py::arg("mesh"), py::arg("version"), py::arg("context_key"))
        // Overload 2: Python RenderContext (extracts graphics and context_key)
        .def("draw", [](MeshGPU& self, py::object context, const Mesh3& mesh, int version) {
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
