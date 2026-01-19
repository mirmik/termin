// navmesh_module.cpp - NavMesh bindings module

#include "common.hpp"
#include "termin/navmesh/recast_navmesh_builder_component.hpp"
#include "termin/entity/component.hpp"
#include "termin/inspect/inspect_registry.hpp"

namespace termin {

void bind_recast_navmesh_builder(nb::module_& m) {
    // Import _entity_native so nanobind can find Component type for inheritance
    nb::module_::import_("termin.entity._entity_native");

    // MeshSource enum
    nb::enum_<MeshSource>(m, "MeshSource")
        .value("CurrentMesh", MeshSource::CurrentMesh)
        .value("AllDescendants", MeshSource::AllDescendants);

    // RecastBuildResult - result of navmesh build
    nb::class_<RecastBuildResult>(m, "RecastBuildResult")
        .def_ro("success", &RecastBuildResult::success)
        .def_ro("error", &RecastBuildResult::error)
        .def("has_poly_mesh", [](const RecastBuildResult& r) {
            return r.poly_mesh != nullptr;
        })
        .def("has_detail_mesh", [](const RecastBuildResult& r) {
            return r.detail_mesh != nullptr;
        })
        .def("poly_count", [](const RecastBuildResult& r) -> int {
            return r.poly_mesh ? r.poly_mesh->npolys : 0;
        })
        .def("vert_count", [](const RecastBuildResult& r) -> int {
            return r.poly_mesh ? r.poly_mesh->nverts : 0;
        });

    // RecastNavMeshBuilderComponent
    nb::class_<RecastNavMeshBuilderComponent, CxxComponent>(m, "RecastNavMeshBuilderComponent")
        .def(nb::init<>())
        // Agent type selection
        .def_rw("agent_type_name", &RecastNavMeshBuilderComponent::agent_type_name)
        // Rasterization parameters
        .def_rw("cell_size", &RecastNavMeshBuilderComponent::cell_size)
        .def_rw("cell_height", &RecastNavMeshBuilderComponent::cell_height)
        // Agent parameters (internal, set via apply_agent_type)
        .def_rw("agent_height", &RecastNavMeshBuilderComponent::agent_height)
        .def_rw("agent_radius", &RecastNavMeshBuilderComponent::agent_radius)
        .def_rw("agent_max_climb", &RecastNavMeshBuilderComponent::agent_max_climb)
        .def_rw("agent_max_slope", &RecastNavMeshBuilderComponent::agent_max_slope)
        // Apply agent type parameters
        .def("apply_agent_type", &RecastNavMeshBuilderComponent::apply_agent_type,
             nb::arg("height"), nb::arg("radius"), nb::arg("max_climb"), nb::arg("max_slope"),
             "Apply agent type parameters (height, radius, max_climb, max_slope)")
        // Region building
        .def_rw("min_region_area", &RecastNavMeshBuilderComponent::min_region_area)
        .def_rw("merge_region_area", &RecastNavMeshBuilderComponent::merge_region_area)
        // Polygonization
        .def_rw("max_edge_length", &RecastNavMeshBuilderComponent::max_edge_length)
        .def_rw("max_simplification_error", &RecastNavMeshBuilderComponent::max_simplification_error)
        .def_rw("max_verts_per_poly", &RecastNavMeshBuilderComponent::max_verts_per_poly)
        // Detail mesh
        .def_rw("detail_sample_dist", &RecastNavMeshBuilderComponent::detail_sample_dist)
        .def_rw("detail_sample_max_error", &RecastNavMeshBuilderComponent::detail_sample_max_error)
        .def_rw("build_detail_mesh", &RecastNavMeshBuilderComponent::build_detail_mesh)
        // Mesh source
        .def_rw("mesh_source", &RecastNavMeshBuilderComponent::mesh_source)
        // Debug capture flags
        .def_rw("capture_heightfield", &RecastNavMeshBuilderComponent::capture_heightfield)
        .def_rw("capture_compact", &RecastNavMeshBuilderComponent::capture_compact)
        .def_rw("capture_contours", &RecastNavMeshBuilderComponent::capture_contours)
        .def_rw("capture_poly_mesh", &RecastNavMeshBuilderComponent::capture_poly_mesh)
        .def_rw("capture_detail_mesh", &RecastNavMeshBuilderComponent::capture_detail_mesh)
        // Debug visualization flags
        .def_rw("show_input_mesh", &RecastNavMeshBuilderComponent::show_input_mesh)
        .def_rw("show_heightfield", &RecastNavMeshBuilderComponent::show_heightfield)
        .def_rw("show_regions", &RecastNavMeshBuilderComponent::show_regions)
        .def_rw("show_distance_field", &RecastNavMeshBuilderComponent::show_distance_field)
        .def_rw("show_contours", &RecastNavMeshBuilderComponent::show_contours)
        .def_rw("show_poly_mesh", &RecastNavMeshBuilderComponent::show_poly_mesh)
        // Last build result
        .def_prop_ro("last_result", [](RecastNavMeshBuilderComponent& self) -> const RecastBuildResult& {
            return self.last_result;
        }, nb::rv_policy::reference_internal)
        // Build method - accepts numpy arrays
        .def("build", [](RecastNavMeshBuilderComponent& self,
                         nb::ndarray<float, nb::shape<-1, 3>, nb::c_contig> verts,
                         nb::ndarray<int, nb::shape<-1, 3>, nb::c_contig> tris) {
            int nverts = static_cast<int>(verts.shape(0));
            int ntris = static_cast<int>(tris.shape(0));
            const float* verts_ptr = verts.data();
            const int* tris_ptr = tris.data();
            return self.build(verts_ptr, nverts, tris_ptr, ntris);
        }, nb::arg("vertices"), nb::arg("triangles"),
           "Build navmesh from vertices (Nx3 float array) and triangles (Mx3 int array)")
        // Build from entity
        .def("build_from_entity", &RecastNavMeshBuilderComponent::build_from_entity)
        // Clear debug data
        .def("clear_debug_data", &RecastNavMeshBuilderComponent::clear_debug_data)
        // Free result
        .def_static("free_result", &RecastNavMeshBuilderComponent::free_result);
}

} // namespace termin

NB_MODULE(_navmesh_native, m) {
    m.doc() = "NavMesh native module (RecastNavMeshBuilderComponent)";
    termin::bind_recast_navmesh_builder(m);
}
