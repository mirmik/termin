#include "common.hpp"
#include "termin/render/mesh_renderer.hpp"
#include "termin/render/skinned_mesh_renderer.hpp"
#include "termin/render/skeleton_controller.hpp"
#include "termin/render/render.hpp"
#include "termin/entity/entity.hpp"
#include "termin/mesh/tc_mesh_handle.hpp"
#include "termin/material/tc_material_handle.hpp"
#include "termin/bindings/entity/entity_helpers.hpp"

namespace termin {

void bind_renderers(nb::module_& m) {
    // Import _entity_native so nanobind can find Component type for inheritance
    nb::module_::import_("termin.entity._entity_native");

    // Import _skeleton_native for SkeletonController type (used by SkinnedMeshRenderer)
    nb::module_::import_("termin.skeleton._skeleton_native");

    // MeshRenderer - inherits from Component
    nb::class_<MeshRenderer, Component>(m, "MeshRenderer")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<MeshRenderer>(self);
        })
        // Constructor with mesh and material (for Python compatibility)
        .def("__init__", [](nb::handle self, nb::object mesh_arg, nb::object material_arg, bool cast_shadow) {
            cxx_component_init<MeshRenderer>(self);
            auto* cpp = nb::inst_ptr<MeshRenderer>(self);
            cpp->cast_shadow = cast_shadow;

            if (!mesh_arg.is_none()) {
                // Try TcMesh first
                if (nb::isinstance<TcMesh>(mesh_arg)) {
                    cpp->mesh = nb::cast<TcMesh>(mesh_arg);
                } else if (nb::hasattr(mesh_arg, "mesh_data")) {
                    // MeshAsset - get mesh_data (TcMesh)
                    nb::object res = mesh_arg.attr("mesh_data");
                    if (nb::isinstance<TcMesh>(res)) {
                        cpp->mesh = nb::cast<TcMesh>(res);
                    }
                } else if (nb::isinstance<nb::str>(mesh_arg)) {
                    // String - lookup by name
                    std::string name = nb::cast<std::string>(mesh_arg);
                    cpp->set_mesh_by_name(name);
                }
            }

            if (!material_arg.is_none()) {
                // Try TcMaterial first
                if (nb::isinstance<TcMaterial>(material_arg)) {
                    cpp->material = nb::cast<TcMaterial>(material_arg);
                } else if (nb::isinstance<nb::str>(material_arg)) {
                    // String - lookup by name
                    std::string name = nb::cast<std::string>(material_arg);
                    cpp->set_material_by_name(name);
                }
            }
        }, nb::arg("mesh") = nb::none(), nb::arg("material") = nb::none(), nb::arg("cast_shadow") = true)
        .def_prop_rw("mesh",
            [](MeshRenderer& self) -> TcMesh& { return self.mesh; },
            [](MeshRenderer& self, const TcMesh& m) { self.mesh = m; },
            nb::rv_policy::reference_internal)
        .def_prop_rw("material",
            [](MeshRenderer& self) -> TcMaterial& { return self.material; },
            [](MeshRenderer& self, const TcMaterial& m) { self.set_material(m); },
            nb::rv_policy::reference_internal)
        .def_rw("cast_shadow", &MeshRenderer::cast_shadow)
        .def_prop_rw("_override_material",
            [](MeshRenderer& self) { return self._override_material; },
            [](MeshRenderer& self, bool v) {
                // Use try_create instead of set_override_material to avoid early-return
                self._override_material = v;
                if (v && !self._overridden_material.is_valid()) {
                    self.try_create_override_material();
                } else if (!v) {
                    self._overridden_material = TcMaterial();
                }
            })
        .def("get_mesh", [](MeshRenderer& self) -> TcMesh& {
            return self.get_mesh();
        }, nb::rv_policy::reference_internal)
        .def("set_mesh", &MeshRenderer::set_mesh)
        .def("set_mesh_by_name", &MeshRenderer::set_mesh_by_name)
        .def("get_material", &MeshRenderer::get_material)
        .def("get_base_material", &MeshRenderer::get_base_material)
        .def("set_material", &MeshRenderer::set_material)
        .def("set_material_by_name", &MeshRenderer::set_material_by_name)
        .def_prop_rw("override_material",
            &MeshRenderer::override_material,
            &MeshRenderer::set_override_material)
        .def("set_override_material", &MeshRenderer::set_override_material)
        .def("get_overridden_material", &MeshRenderer::get_overridden_material)
        .def_prop_ro("phase_marks", [](MeshRenderer& self) {
            nb::set marks;
            for (const auto& mark : self.phase_marks()) {
                marks.add(nb::str(mark.c_str()));
            }
            return marks;
        })
        .def("draw_geometry", &MeshRenderer::draw_geometry,
            nb::arg("context"), nb::arg("geometry_id") = 0)
        .def("get_phases_for_mark", &MeshRenderer::get_phases_for_mark,
            nb::arg("phase_mark"))
        .def("get_geometry_draws", [](MeshRenderer& self, nb::object phase_mark) {
            if (phase_mark.is_none()) {
                return self.get_geometry_draws(nullptr);
            }
            std::string pm = nb::cast<std::string>(phase_mark);
            return self.get_geometry_draws(&pm);
        }, nb::arg("phase_mark") = nb::none());

    // SkinnedMeshRenderer - inherits from MeshRenderer
    nb::class_<SkinnedMeshRenderer, MeshRenderer>(m, "SkinnedMeshRenderer")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<SkinnedMeshRenderer>(self);
        })
        // Constructor with mesh, material, skeleton_controller
        .def("__init__", [](nb::handle self, nb::object mesh_arg, nb::object material_arg, SkeletonController* skeleton_controller, bool cast_shadow) {
            cxx_component_init<SkinnedMeshRenderer>(self);
            auto* cpp = nb::inst_ptr<SkinnedMeshRenderer>(self);
            cpp->cast_shadow = cast_shadow;

            if (!mesh_arg.is_none()) {
                // Try TcMesh first
                if (nb::isinstance<TcMesh>(mesh_arg)) {
                    cpp->mesh = nb::cast<TcMesh>(mesh_arg);
                } else if (nb::hasattr(mesh_arg, "mesh_data")) {
                    // MeshAsset - get mesh_data (TcMesh)
                    nb::object res = mesh_arg.attr("mesh_data");
                    if (nb::isinstance<TcMesh>(res)) {
                        cpp->mesh = nb::cast<TcMesh>(res);
                    }
                } else if (nb::isinstance<nb::str>(mesh_arg)) {
                    // String - lookup by name
                    std::string name = nb::cast<std::string>(mesh_arg);
                    cpp->set_mesh_by_name(name);
                }
            }

            if (!material_arg.is_none()) {
                // Try TcMaterial first
                if (nb::isinstance<TcMaterial>(material_arg)) {
                    cpp->material = nb::cast<TcMaterial>(material_arg);
                } else if (nb::isinstance<nb::str>(material_arg)) {
                    // String - lookup by name
                    std::string name = nb::cast<std::string>(material_arg);
                    cpp->set_material_by_name(name);
                }
            }

            if (skeleton_controller != nullptr) {
                cpp->set_skeleton_controller(skeleton_controller);
            }
        },
            nb::arg("mesh") = nb::none(),
            nb::arg("material") = nb::none(),
            nb::arg("skeleton_controller") = nullptr,
            nb::arg("cast_shadow") = true)
        .def_rw("_skeleton_controller", &SkinnedMeshRenderer::_skeleton_controller)
        .def_prop_rw("skeleton_controller",
            &SkinnedMeshRenderer::skeleton_controller,
            &SkinnedMeshRenderer::set_skeleton_controller,
            nb::rv_policy::reference)
        .def_prop_ro("skeleton_instance",
            &SkinnedMeshRenderer::skeleton_instance,
            nb::rv_policy::reference)
        .def("update_bone_matrices", &SkinnedMeshRenderer::update_bone_matrices)
        .def_ro("_bone_count", &SkinnedMeshRenderer::_bone_count)
        .def("get_bone_matrices_flat", [](SkinnedMeshRenderer& self) {
            if (self._bone_count == 0) {
                // Return empty array
                size_t shape[3] = {0, 4, 4};
                return nb::ndarray<nb::numpy, float>(nullptr, 3, shape);
            }
            // Create a copy of the data with capsule ownership
            size_t data_size = self._bone_count * 16;
            float* buf = new float[data_size];
            std::copy(self._bone_matrices_flat.data(),
                      self._bone_matrices_flat.data() + data_size, buf);
            nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<float*>(p); });
            size_t shape[3] = {static_cast<size_t>(self._bone_count), 4, 4};
            return nb::ndarray<nb::numpy, float>(buf, 3, shape, owner);
        });
}

} // namespace termin
