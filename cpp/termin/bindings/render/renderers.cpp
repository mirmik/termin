#include "common.hpp"
#include "termin/render/mesh_renderer.hpp"
#include "termin/render/skinned_mesh_renderer.hpp"
#include "termin/render/skeleton_controller.hpp"
#include "termin/render/render.hpp"
#include "termin/entity/entity.hpp"
#include <iostream>

namespace termin {

void bind_renderers(py::module_& m) {
    // Import _entity_native so pybind11 can find Component type for inheritance
    py::module_::import("termin.entity._entity_native");

    // SkeletonController - inherits from Component
    py::class_<SkeletonController, Component>(m, "SkeletonController")
        .def(py::init<>())
        .def(py::init([](py::object skeleton_arg, py::list bone_entities_list) {
            auto controller = new SkeletonController();

            // Handle skeleton argument: SkeletonHandle, SkeletonAsset, or SkeletonData*
            if (!skeleton_arg.is_none()) {
                if (py::isinstance<SkeletonHandle>(skeleton_arg)) {
                    controller->skeleton = skeleton_arg.cast<SkeletonHandle>();
                } else if (py::hasattr(skeleton_arg, "resource")) {
                    // SkeletonAsset - wrap in handle
                    controller->skeleton = SkeletonHandle::from_asset(skeleton_arg);
                } else {
                    // Raw SkeletonData* - wrap in handle via asset
                    auto skel_data = skeleton_arg.cast<SkeletonData*>();
                    if (skel_data != nullptr) {
                        // Create minimal asset and wrap
                        py::object rm_module = py::module_::import("termin.assets.resources");
                        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
                        py::object asset = rm.attr("get_or_create_skeleton_asset")(
                            py::cast(skel_data), py::arg("name") = "skeleton"
                        );
                        controller->skeleton = SkeletonHandle::from_asset(asset);
                    }
                }
            }

            std::vector<Entity*> entities;
            for (auto item : bone_entities_list) {
                if (!item.is_none()) {
                    entities.push_back(item.cast<Entity*>());
                }
            }
            controller->set_bone_entities_from_ptrs(std::move(entities));

            return controller;
        }),
            py::arg("skeleton") = py::none(),
            py::arg("bone_entities") = py::list())
        .def_readwrite("skeleton", &SkeletonController::skeleton)
        .def_property("skeleton_data",
            &SkeletonController::skeleton_data,
            [](SkeletonController& self, py::object skel_arg) {
                // Setter accepts SkeletonData*, SkeletonAsset, or SkeletonHandle
                if (skel_arg.is_none()) {
                    self.skeleton = SkeletonHandle();
                    return;
                }
                if (py::isinstance<SkeletonHandle>(skel_arg)) {
                    self.set_skeleton(skel_arg.cast<SkeletonHandle>());
                } else if (py::hasattr(skel_arg, "resource")) {
                    self.set_skeleton(SkeletonHandle::from_asset(skel_arg));
                } else {
                    auto skel_data = skel_arg.cast<SkeletonData*>();
                    if (skel_data != nullptr) {
                        py::object rm_module = py::module_::import("termin.assets.resources");
                        py::object rm = rm_module.attr("ResourceManager").attr("instance")();
                        py::object asset = rm.attr("get_or_create_skeleton_asset")(
                            py::cast(skel_data), py::arg("name") = "skeleton"
                        );
                        self.set_skeleton(SkeletonHandle::from_asset(asset));
                    }
                }
            },
            py::return_value_policy::reference)
        .def_property("bone_entities",
            [](const SkeletonController& self) {
                std::cout << "[SkeletonController.bone_entities getter] this=" << &self
                          << " count=" << self.bone_entities.size() << std::endl;
                // Return resolved Entity* list
                py::list result;
                for (const auto& handle : self.bone_entities) {
                    Entity* e = handle.get();
                    std::cout << "  uuid=" << handle.uuid << " -> " << (e ? e->name : "null") << std::endl;
                    if (e) {
                        result.append(py::cast(e, py::return_value_policy::reference));
                    } else {
                        result.append(py::none());
                    }
                }
                return result;
            },
            [](SkeletonController& self, py::list entities) {
                std::vector<Entity*> vec;
                for (auto item : entities) {
                    if (item.is_none()) {
                        vec.push_back(nullptr);
                    } else {
                        vec.push_back(item.cast<Entity*>());
                    }
                }
                self.set_bone_entities_from_ptrs(std::move(vec));
            })
        .def_property_readonly("skeleton_instance",
            &SkeletonController::skeleton_instance,
            py::return_value_policy::reference)
        .def("set_skeleton", &SkeletonController::set_skeleton)
        .def("set_bone_entities", [](SkeletonController& self, py::list entities) {
            std::vector<Entity*> vec;
            for (auto item : entities) {
                if (!item.is_none()) {
                    vec.push_back(item.cast<Entity*>());
                }
            }
            self.set_bone_entities_from_ptrs(std::move(vec));
        })
        .def("invalidate_instance", &SkeletonController::invalidate_instance);

    // MeshRenderer - inherits from Component
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
                // Check if it's a Material directly or a MaterialAsset
                try {
                    auto mat = material_arg.cast<Material*>();
                    renderer->material = MaterialHandle::from_direct(mat);
                } catch (const py::cast_error&) {
                    renderer->material = MaterialHandle::from_asset(material_arg);
                }
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

    py::class_<SkinnedMeshRenderer, MeshRenderer>(m, "SkinnedMeshRenderer")
        .def(py::init<>())
        // Constructor with mesh, material, skeleton_controller
        .def(py::init([](py::object mesh_arg, py::object material_arg, SkeletonController* skeleton_controller, bool cast_shadow) {
            auto renderer = new SkinnedMeshRenderer();
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
                // Check if it's a Material directly or a MaterialAsset
                try {
                    auto mat = material_arg.cast<Material*>();
                    renderer->material = MaterialHandle::from_direct(mat);
                } catch (const py::cast_error&) {
                    renderer->material = MaterialHandle::from_asset(material_arg);
                }
            }

            if (skeleton_controller != nullptr) {
                renderer->set_skeleton_controller(skeleton_controller);
            }

            return renderer;
        }),
            py::arg("mesh") = py::none(),
            py::arg("material") = py::none(),
            py::arg("skeleton_controller") = nullptr,
            py::arg("cast_shadow") = true)
        .def_readwrite("_skeleton_controller", &SkinnedMeshRenderer::_skeleton_controller)
        .def_property("skeleton_controller",
            &SkinnedMeshRenderer::skeleton_controller,
            &SkinnedMeshRenderer::set_skeleton_controller,
            py::return_value_policy::reference)
        .def_property_readonly("skeleton_instance",
            &SkinnedMeshRenderer::skeleton_instance,
            py::return_value_policy::reference)
        .def("update_bone_matrices", &SkinnedMeshRenderer::update_bone_matrices)
        .def("upload_bone_matrices", &SkinnedMeshRenderer::upload_bone_matrices)
        .def("get_skinned_material", &SkinnedMeshRenderer::get_skinned_material,
            py::return_value_policy::reference)
        .def_readonly("_bone_count", &SkinnedMeshRenderer::_bone_count)
        .def("get_bone_matrices_flat", [](SkinnedMeshRenderer& self) {
            if (self._bone_count == 0) {
                return py::array_t<float>();
            }
            return py::array_t<float>(
                {self._bone_count, 4, 4},
                {16 * sizeof(float), 4 * sizeof(float), sizeof(float)},
                self._bone_matrices_flat.data()
            );
        });
}

} // namespace termin
