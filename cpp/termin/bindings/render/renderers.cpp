#include "common.hpp"
#include "termin/render/mesh_renderer.hpp"
#include "termin/render/skinned_mesh_renderer.hpp"
#include "termin/render/render.hpp"

namespace termin {

void bind_renderers(py::module_& m) {
    py::class_<MeshRenderer, Component>(m, "MeshRenderer")
        .def(py::init<>())
        // Constructor with mesh and material (for Python compatibility)
        .def(py::init([](py::object mesh_arg, py::object material_arg, bool cast_shadow) {
            auto renderer = new MeshRenderer();
            renderer->cast_shadow = cast_shadow;

            if (!mesh_arg.is_none()) {
                if (py::isinstance<MeshHandle>(mesh_arg)) {
                    renderer->mesh = mesh_arg.cast<MeshHandle>();
                } else if (py::hasattr(mesh_arg, "_handle")) {
                    py::object handle = mesh_arg.attr("_handle");
                    if (py::isinstance<MeshHandle>(handle)) {
                        renderer->mesh = handle.cast<MeshHandle>();
                    }
                }
            }

            if (!material_arg.is_none()) {
                renderer->material = MaterialHandle::from_asset(material_arg);
            }

            return renderer;
        }), py::arg("mesh") = py::none(), py::arg("material") = py::none(), py::arg("cast_shadow") = true)
        .def_readwrite("mesh", &MeshRenderer::mesh)
        .def_readwrite("material", &MeshRenderer::material)
        .def_readwrite("cast_shadow", &MeshRenderer::cast_shadow)
        .def_readwrite("_override_material", &MeshRenderer::_override_material)
        .def("mesh_handle", [](MeshRenderer& self) -> MeshHandle& {
            return self.mesh_handle();
        }, py::return_value_policy::reference_internal)
        .def("material_handle", [](MeshRenderer& self) -> MaterialHandle& {
            return self.material_handle();
        }, py::return_value_policy::reference_internal)
        .def("set_mesh", &MeshRenderer::set_mesh)
        .def("set_mesh_by_name", &MeshRenderer::set_mesh_by_name)
        .def("get_material", &MeshRenderer::get_material, py::return_value_policy::reference)
        .def("get_base_material", &MeshRenderer::get_base_material, py::return_value_policy::reference)
        .def("set_material", &MeshRenderer::set_material)
        .def("set_material_handle", &MeshRenderer::set_material_handle)
        .def("set_material_by_name", &MeshRenderer::set_material_by_name)
        .def_property("override_material",
            &MeshRenderer::override_material,
            &MeshRenderer::set_override_material)
        .def("set_override_material", &MeshRenderer::set_override_material)
        .def("overridden_material", &MeshRenderer::overridden_material, py::return_value_policy::reference)
        .def_property_readonly("phase_marks", [](MeshRenderer& self) {
            py::set marks;
            for (const auto& mark : self.phase_marks()) {
                marks.add(mark);
            }
            return marks;
        })
        .def("draw_geometry", &MeshRenderer::draw_geometry,
            py::arg("context"), py::arg("geometry_id") = "")
        .def("get_phases_for_mark", &MeshRenderer::get_phases_for_mark,
            py::arg("phase_mark"))
        .def("get_geometry_draws", &MeshRenderer::get_geometry_draws,
            py::arg("phase_mark") = "");

    py::class_<SkinnedMeshRenderer>(m, "SkinnedMeshRenderer")
        .def(py::init<>())
        .def("set_skeleton_instance", &SkinnedMeshRenderer::set_skeleton_instance)
        .def("update_bone_matrices", &SkinnedMeshRenderer::update_bone_matrices)
        .def("upload_bone_matrices", &SkinnedMeshRenderer::upload_bone_matrices)
        .def_readonly("bone_count", &SkinnedMeshRenderer::bone_count)
        .def("get_bone_matrices_flat", [](SkinnedMeshRenderer& self) {
            return py::array_t<float>(
                {self.bone_count, 4, 4},
                {16 * sizeof(float), 4 * sizeof(float), sizeof(float)},
                self.bone_matrices_flat.data()
            );
        });
}

} // namespace termin
