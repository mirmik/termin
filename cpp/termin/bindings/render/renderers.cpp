#include "common.hpp"
#include "termin/render/mesh_renderer.hpp"
#include "termin/render/skinned_mesh_renderer.hpp"
#include "termin/render/skeleton_controller.hpp"
#include "termin/render/render.hpp"
#include "termin/entity/entity.hpp"
#include "termin/mesh/tc_mesh_handle.hpp"
#include <iostream>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#undef near
#undef far

inline bool check_heap() {
    HANDLE heaps[100];
    DWORD numHeaps = GetProcessHeaps(100, heaps);
    for (DWORD i = 0; i < numHeaps; i++) {
        if (!HeapValidate(heaps[i], 0, nullptr)) {
            std::cerr << "[HEAP CORRUPT] Heap " << i << " is corrupted!" << std::endl;
            return false;
        }
    }
    return true;
}
#else
inline bool check_heap() { return true; }
#endif

namespace termin {

void bind_renderers(nb::module_& m) {
    // Import _entity_native so nanobind can find Component type for inheritance
    nb::module_::import_("termin.entity._entity_native");

    // SkeletonController - inherits from Component
    nb::class_<SkeletonController, Component>(m, "SkeletonController")
        .def(nb::init<>())
        .def("__init__", [](SkeletonController* self, nb::object skeleton_arg, nb::list bone_entities_list) {
            std::cerr << "[SkeletonController] Constructor start" << std::endl;
            if (!check_heap()) {
                std::cerr << "[SkeletonController] HEAP CORRUPTED at start!" << std::endl;
            }

            new (self) SkeletonController();

            // Handle skeleton argument: SkeletonHandle, SkeletonAsset, or SkeletonData*
            if (!skeleton_arg.is_none()) {
                std::cerr << "[SkeletonController] Processing skeleton arg" << std::endl;
                if (nb::isinstance<SkeletonHandle>(skeleton_arg)) {
                    self->skeleton = nb::cast<SkeletonHandle>(skeleton_arg);
                } else if (nb::hasattr(skeleton_arg, "resource")) {
                    // SkeletonAsset - wrap in handle
                    self->skeleton = SkeletonHandle::from_asset(skeleton_arg);
                } else {
                    // Raw SkeletonData* - wrap in handle via asset
                    auto skel_data = nb::cast<SkeletonData*>(skeleton_arg);
                    if (skel_data != nullptr) {
                        // Create minimal asset and set skeleton_data
                        nb::object rm_module = nb::module_::import_("termin.assets.resources");
                        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
                        nb::object asset = rm.attr("get_or_create_skeleton_asset")(nb::arg("name") = "skeleton");
                        asset.attr("skeleton_data") = skeleton_arg;
                        self->skeleton = SkeletonHandle::from_asset(asset);
                    }
                }
                std::cerr << "[SkeletonController] Skeleton set" << std::endl;
                if (!check_heap()) {
                    std::cerr << "[SkeletonController] HEAP CORRUPTED after skeleton!" << std::endl;
                }
            }

            std::cerr << "[SkeletonController] Processing " << bone_entities_list.size() << " bone entities" << std::endl;
            std::vector<Entity> entities;
            for (auto item : bone_entities_list) {
                if (!item.is_none()) {
                    entities.push_back(nb::cast<Entity>(item));
                }
            }
            self->set_bone_entities(std::move(entities));
            std::cerr << "[SkeletonController] Bone entities set" << std::endl;
            if (!check_heap()) {
                std::cerr << "[SkeletonController] HEAP CORRUPTED after bone entities!" << std::endl;
            }

            std::cerr << "[SkeletonController] Constructor done" << std::endl;
        },
            nb::arg("skeleton") = nb::none(),
            nb::arg("bone_entities") = nb::list())
        .def_rw("skeleton", &SkeletonController::skeleton)
        .def_prop_rw("skeleton_data",
            &SkeletonController::skeleton_data,
            [](SkeletonController& self, nb::object skel_arg) {
                // Setter accepts SkeletonData*, SkeletonAsset, or SkeletonHandle
                if (skel_arg.is_none()) {
                    self.skeleton = SkeletonHandle();
                    return;
                }
                if (nb::isinstance<SkeletonHandle>(skel_arg)) {
                    self.set_skeleton(nb::cast<SkeletonHandle>(skel_arg));
                } else if (nb::hasattr(skel_arg, "resource")) {
                    self.set_skeleton(SkeletonHandle::from_asset(skel_arg));
                } else {
                    auto skel_data = nb::cast<SkeletonData*>(skel_arg);
                    if (skel_data != nullptr) {
                        nb::object rm_module = nb::module_::import_("termin.assets.resources");
                        nb::object rm = rm_module.attr("ResourceManager").attr("instance")();
                        nb::object asset = rm.attr("get_or_create_skeleton_asset")(nb::arg("name") = "skeleton");
                        asset.attr("skeleton_data") = skel_arg;
                        self.set_skeleton(SkeletonHandle::from_asset(asset));
                    }
                }
            },
            nb::rv_policy::reference)
        .def_prop_rw("bone_entities",
            [](const SkeletonController& self) {
                nb::list result;
                for (const auto& e : self.bone_entities) {
                    if (e.valid()) {
                        result.append(nb::cast(e));
                    } else {
                        result.append(nb::none());
                    }
                }
                return result;
            },
            [](SkeletonController& self, nb::list entities) {
                std::vector<Entity> vec;
                for (auto item : entities) {
                    if (!item.is_none()) {
                        vec.push_back(nb::cast<Entity>(item));
                    }
                }
                self.set_bone_entities(std::move(vec));
            })
        .def_prop_ro("skeleton_instance",
            &SkeletonController::skeleton_instance,
            nb::rv_policy::reference)
        .def("set_skeleton", &SkeletonController::set_skeleton)
        .def("set_bone_entities", [](SkeletonController& self, nb::list entities) {
            std::vector<Entity> vec;
            for (auto item : entities) {
                if (!item.is_none()) {
                    vec.push_back(nb::cast<Entity>(item));
                }
            }
            self.set_bone_entities(std::move(vec));
        })
        .def("invalidate_instance", &SkeletonController::invalidate_instance);

    // MeshRenderer - inherits from Component
    nb::class_<MeshRenderer, Component>(m, "MeshRenderer")
        .def(nb::init<>())
        // Constructor with mesh and material (for Python compatibility)
        .def("__init__", [](MeshRenderer* self, nb::object mesh_arg, nb::object material_arg, bool cast_shadow) {
            new (self) MeshRenderer();
            self->cast_shadow = cast_shadow;

            if (!mesh_arg.is_none()) {
                // Try TcMesh first
                if (nb::isinstance<TcMesh>(mesh_arg)) {
                    self->mesh = nb::cast<TcMesh>(mesh_arg);
                } else if (nb::hasattr(mesh_arg, "mesh_data")) {
                    // MeshAsset - get mesh_data (TcMesh)
                    nb::object res = mesh_arg.attr("mesh_data");
                    if (nb::isinstance<TcMesh>(res)) {
                        self->mesh = nb::cast<TcMesh>(res);
                    }
                } else if (nb::isinstance<nb::str>(mesh_arg)) {
                    // String - lookup by name
                    std::string name = nb::cast<std::string>(mesh_arg);
                    self->set_mesh_by_name(name);
                }
            }

            if (!material_arg.is_none()) {
                // Check if it's a Material directly or a MaterialAsset
                try {
                    auto mat = nb::cast<Material*>(material_arg);
                    self->material = MaterialHandle::from_direct(mat);
                } catch (const nb::cast_error&) {
                    self->material = MaterialHandle::from_asset(material_arg);
                }
            }
        }, nb::arg("mesh") = nb::none(), nb::arg("material") = nb::none(), nb::arg("cast_shadow") = true)
        .def_prop_rw("mesh",
            [](MeshRenderer& self) -> TcMesh& { return self.mesh; },
            [](MeshRenderer& self, const TcMesh& m) { self.mesh = m; },
            nb::rv_policy::reference_internal)
        .def_prop_rw("material",
            [](MeshRenderer& self) -> MaterialHandle& { return self.material; },
            [](MeshRenderer& self, const MaterialHandle& h) { self.material = h; },
            nb::rv_policy::reference_internal)
        .def_rw("cast_shadow", &MeshRenderer::cast_shadow)
        .def_rw("_override_material", &MeshRenderer::_override_material)
        .def("get_mesh", [](MeshRenderer& self) -> TcMesh& {
            return self.get_mesh();
        }, nb::rv_policy::reference_internal)
        .def("material_handle", [](MeshRenderer& self) -> MaterialHandle& {
            return self.material_handle();
        }, nb::rv_policy::reference_internal)
        .def("set_mesh", &MeshRenderer::set_mesh)
        .def("set_mesh_by_name", &MeshRenderer::set_mesh_by_name)
        .def("get_material", &MeshRenderer::get_material, nb::rv_policy::reference)
        .def("get_base_material", &MeshRenderer::get_base_material, nb::rv_policy::reference)
        .def("set_material", &MeshRenderer::set_material)
        .def("set_material_handle", &MeshRenderer::set_material_handle)
        .def("set_material_by_name", &MeshRenderer::set_material_by_name)
        .def_prop_rw("override_material",
            &MeshRenderer::override_material,
            &MeshRenderer::set_override_material)
        .def("set_override_material", &MeshRenderer::set_override_material)
        .def("overridden_material", &MeshRenderer::overridden_material, nb::rv_policy::reference)
        .def_prop_ro("phase_marks", [](MeshRenderer& self) {
            nb::set marks;
            for (const auto& mark : self.phase_marks()) {
                marks.add(nb::str(mark.c_str()));
            }
            return marks;
        })
        .def("draw_geometry", &MeshRenderer::draw_geometry,
            nb::arg("context"), nb::arg("geometry_id") = "")
        .def("get_phases_for_mark", &MeshRenderer::get_phases_for_mark,
            nb::arg("phase_mark"))
        .def("get_geometry_draws", &MeshRenderer::get_geometry_draws,
            nb::arg("phase_mark") = "")
        .def_prop_ro("mesh_gpu", [](MeshRenderer& self) -> MeshGPU& {
            return self.mesh_gpu();
        }, nb::rv_policy::reference_internal);

    // SkinnedMeshRenderer - inherits from MeshRenderer
    nb::class_<SkinnedMeshRenderer, MeshRenderer>(m, "SkinnedMeshRenderer")
        .def(nb::init<>())
        // Constructor with mesh, material, skeleton_controller
        .def("__init__", [](SkinnedMeshRenderer* self, nb::object mesh_arg, nb::object material_arg, SkeletonController* skeleton_controller, bool cast_shadow) {
            new (self) SkinnedMeshRenderer();
            self->cast_shadow = cast_shadow;

            if (!mesh_arg.is_none()) {
                // Try TcMesh first
                if (nb::isinstance<TcMesh>(mesh_arg)) {
                    self->mesh = nb::cast<TcMesh>(mesh_arg);
                } else if (nb::hasattr(mesh_arg, "mesh_data")) {
                    // MeshAsset - get mesh_data (TcMesh)
                    nb::object res = mesh_arg.attr("mesh_data");
                    if (nb::isinstance<TcMesh>(res)) {
                        self->mesh = nb::cast<TcMesh>(res);
                    }
                } else if (nb::isinstance<nb::str>(mesh_arg)) {
                    // String - lookup by name
                    std::string name = nb::cast<std::string>(mesh_arg);
                    self->set_mesh_by_name(name);
                }
            }

            if (!material_arg.is_none()) {
                // Check if it's a Material directly or a MaterialAsset
                try {
                    auto mat = nb::cast<Material*>(material_arg);
                    self->material = MaterialHandle::from_direct(mat);
                } catch (const nb::cast_error&) {
                    self->material = MaterialHandle::from_asset(material_arg);
                }
            }

            if (skeleton_controller != nullptr) {
                self->set_skeleton_controller(skeleton_controller);
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
        .def("upload_bone_matrices", &SkinnedMeshRenderer::upload_bone_matrices)
        .def("get_skinned_material", &SkinnedMeshRenderer::get_skinned_material,
            nb::rv_policy::reference)
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
