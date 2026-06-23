// navmesh_module.cpp - NavMesh bindings module

#include "common.hpp"
#include "termin/navmesh/detour_pathfinding_world_component.hpp"
#include "termin/navmesh/navmesh_keeper_component.hpp"
#include "termin/navmesh/off_mesh_link_component.hpp"
#include "termin/navmesh/recast_navmesh_builder_component.hpp"
#include "termin/navmesh/tc_navmesh_handle.hpp"
#include <termin/entity/component.hpp>
#include <termin/bindings/entity_helpers.hpp>
#include <inspect/tc_inspect_python.hpp>
#include <termin/inspect/tc_kind_cpp_ext.hpp>
#include <nanobind/stl/string.h>
#include <mutex>
#include <unordered_map>
#include <utility>

namespace termin {

namespace {
static std::mutex g_navmesh_callback_mutex;
static std::unordered_map<std::string, nb::callable> g_navmesh_load_callbacks;

void cleanup_navmesh_callbacks() {
    std::lock_guard<std::mutex> lock(g_navmesh_callback_mutex);
    g_navmesh_load_callbacks.clear();
}

void register_navmesh_kind_handlers() {
    static bool registered = false;
    if (registered) {
        return;
    }

    tc::register_cpp_handle_kind<TcNavMesh>("navmesh_handle");

    nb::module_ navmesh_module = nb::module_::import_("termin.navmesh._navmesh_native");
    nb::object navmesh_type = navmesh_module.attr("TcNavMesh");
    tc::KindRegistry::instance().register_type(navmesh_type, "navmesh_handle");
    tc::KindRegistry::instance().register_python(
        "navmesh_handle",
        nb::cpp_function([](nb::object obj) -> nb::object {
            TcNavMesh navmesh = nb::cast<TcNavMesh>(obj);
            nb::dict result;
            if (navmesh.is_valid()) {
                result["uuid"] = std::string(navmesh.uuid());
                result["name"] = std::string(navmesh.name());
                result["type"] = "uuid";
            }
            return result;
        }),
        nb::cpp_function([navmesh_type](nb::dict data) {
            return navmesh_type.attr("deserialize")(data);
        }));

    registered = true;
}

bool python_navmesh_load_callback(tc_navmesh* navmesh, void* user_data) {
    (void)user_data;
    if (!navmesh) {
        return false;
    }

    std::string uuid(navmesh->uuid);
    nb::callable callback;
    {
        std::lock_guard<std::mutex> lock(g_navmesh_callback_mutex);
        auto it = g_navmesh_load_callbacks.find(uuid);
        if (it == g_navmesh_load_callbacks.end()) {
            return false;
        }
        callback = it->second;
    }

    nb::gil_scoped_acquire gil;
    try {
        nb::object result = callback(nb::cast(TcNavMesh(navmesh)));
        return nb::cast<bool>(result);
    } catch (const std::exception& e) {
        tc_log_error("Python navmesh load callback failed for '%s': %s", uuid.c_str(), e.what());
        return false;
    }
}

std::array<float, 3> py_vec3(nb::handle value) {
    nb::sequence seq = nb::cast<nb::sequence>(value);
    return {
        nb::cast<float>(seq[0]),
        nb::cast<float>(seq[1]),
        nb::cast<float>(seq[2]),
    };
}

nb::list path_to_python(const std::vector<std::array<float, 3>>& path) {
    nb::list result;
    for (const auto& p : path) {
        nb::list item;
        item.append(p[0]);
        item.append(p[1]);
        item.append(p[2]);
        result.append(item);
    }
    return result;
}

nb::list point_to_python(const std::array<float, 3>& point) {
    nb::list result;
    result.append(point[0]);
    result.append(point[1]);
    result.append(point[2]);
    return result;
}

nb::list detailed_path_to_python(const DetourPathResult& path) {
    nb::list result;
    if (!path.success) {
        return result;
    }
    for (const DetourPathPoint& p : path.points) {
        nb::dict item;
        item["point"] = point_to_python(p.point);
        item["flags"] = p.flags;
        item["poly_ref"] = p.poly_ref;
        item["off_mesh_connection"] = p.off_mesh_connection;
        item["off_mesh_user_id"] = p.off_mesh_user_id;
        item["area"] = p.area;
        result.append(item);
    }
    return result;
}

nb::list vec3_to_python(const Vec3& point) {
    nb::list result;
    result.append(point.x);
    result.append(point.y);
    result.append(point.z);
    return result;
}

tc_vec3 tc_vec3_from_python(nb::handle value) {
    nb::sequence seq = nb::cast<nb::sequence>(value);
    return {
        nb::cast<double>(seq[0]),
        nb::cast<double>(seq[1]),
        nb::cast<double>(seq[2]),
    };
}

nb::list tc_vec3_to_python(const tc_vec3& point) {
    nb::list result;
    result.append(point.x);
    result.append(point.y);
    result.append(point.z);
    return result;
}

tc_navmesh_tile tile_from_python(nb::handle tile) {
    tc_navmesh_tile result{};
    result.x = nb::cast<int32_t>(tile.attr("x"));
    result.y = nb::cast<int32_t>(tile.attr("y"));
    result.layer = nb::cast<int32_t>(tile.attr("layer"));

    nb::bytes data = nb::cast<nb::bytes>(tile.attr("data"));
    char* raw = nullptr;
    Py_ssize_t size = 0;
    if (PyBytes_AsStringAndSize(data.ptr(), &raw, &size) == 0 && raw && size > 0) {
        result.data = reinterpret_cast<unsigned char*>(raw);
        result.data_size = static_cast<size_t>(size);
    }
    return result;
}
}

void bind_recast_navmesh_builder(nb::module_& m) {
    // Import scene native so nanobind can find Component type for inheritance.
    nb::module_::import_("termin.scene._scene_native");

    nb::class_<TcNavMesh>(m, "TcNavMesh")
        .def(nb::init<>())
        .def_static("from_uuid", &TcNavMesh::from_uuid, nb::arg("uuid"))
        .def_static("from_name", &TcNavMesh::from_name, nb::arg("name"))
        .def_static("declare", &TcNavMesh::declare, nb::arg("uuid"), nb::arg("name") = "")
        .def_prop_ro("is_valid", &TcNavMesh::is_valid)
        .def_prop_ro("is_loaded", &TcNavMesh::is_loaded)
        .def_prop_ro("uuid", [](const TcNavMesh& self) { return std::string(self.uuid()); })
        .def_prop_ro("name", [](const TcNavMesh& self) { return std::string(self.name()); })
        .def_prop_ro("version", &TcNavMesh::version)
        .def("ensure_loaded", &TcNavMesh::ensure_loaded)
        .def("serialize", [](const TcNavMesh& self) {
            nb::dict result;
            if (self.is_valid()) {
                result["uuid"] = std::string(self.uuid());
                result["name"] = std::string(self.name());
                result["type"] = "uuid";
            }
            return result;
        })
        .def_static("deserialize", [](const nb::dict& data) {
            if (data.contains("uuid")) {
                return TcNavMesh::from_uuid(nb::cast<std::string>(data["uuid"]));
            }
            if (data.contains("name")) {
                return TcNavMesh::from_name(nb::cast<std::string>(data["name"]));
            }
            return TcNavMesh();
        }, nb::arg("data"));

    m.attr("NavMeshHandle") = m.attr("TcNavMesh");

    m.def("declare_navmesh_asset", [](const std::string& uuid, const std::string& name) {
        TcNavMesh navmesh = TcNavMesh::declare(uuid, name);
        return navmesh.is_valid();
    }, nb::arg("uuid"), nb::arg("name") = "");

    m.def("set_navmesh_load_callback", [](TcNavMesh& navmesh, nb::callable callback) {
        tc_navmesh* raw = navmesh.get();
        if (!raw) {
            throw std::runtime_error("Invalid navmesh handle");
        }

        std::string uuid(raw->uuid);
        {
            std::lock_guard<std::mutex> lock(g_navmesh_callback_mutex);
            g_navmesh_load_callbacks[uuid] = callback;
        }

        tc_navmesh_set_load_callback(navmesh.handle, python_navmesh_load_callback, nullptr);
    }, nb::arg("navmesh"), nb::arg("callback"));

    m.def("clear_navmesh_load_callback", [](TcNavMesh& navmesh) {
        tc_navmesh* raw = navmesh.get();
        if (!raw) {
            return;
        }

        std::string uuid(raw->uuid);
        {
            std::lock_guard<std::mutex> lock(g_navmesh_callback_mutex);
            g_navmesh_load_callbacks.erase(uuid);
        }

        tc_navmesh_set_load_callback(navmesh.handle, nullptr, nullptr);
    }, nb::arg("navmesh"));

    m.def("set_detour_navmesh_asset_data",
          [](const std::string& uuid,
             const std::string& name,
             const std::string& agent_type,
             const std::string& coordinate_system,
             nb::sequence tiles) {
              TcNavMesh navmesh = TcNavMesh::declare(uuid, name);
              tc_navmesh* raw = navmesh.get();
              if (!raw) {
                  return false;
              }

              tc_navmesh_set_metadata(raw,
                                      name.empty() ? nullptr : name.c_str(),
                                      agent_type.empty() ? nullptr : agent_type.c_str(),
                                      coordinate_system.empty() ? nullptr : coordinate_system.c_str());

              std::vector<tc_navmesh_tile> c_tiles;
              c_tiles.reserve(static_cast<size_t>(nb::len(tiles)));
              for (nb::handle tile : tiles) {
                  c_tiles.push_back(tile_from_python(tile));
              }
              return tc_navmesh_set_tiles(raw, c_tiles.data(), c_tiles.size());
          },
          nb::arg("uuid"), nb::arg("name"), nb::arg("agent_type"),
          nb::arg("coordinate_system"), nb::arg("tiles"));

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

    nb::class_<NavMeshKeeperComponent, CxxComponent>(m, "NavMeshKeeperComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<NavMeshKeeperComponent>(self);
        })
        .def_rw("navmesh_uuid", &NavMeshKeeperComponent::navmesh_uuid)
        .def_prop_rw("navmesh",
            [](NavMeshKeeperComponent& self) {
                nb::dict value;
                value["uuid"] = self.navmesh_uuid;
                value["name"] = "";
                return value;
            },
            [](NavMeshKeeperComponent& self, nb::dict value) {
                if (value.contains("uuid")) {
                    self.navmesh_uuid = nb::cast<std::string>(value["uuid"]);
                } else {
                    self.navmesh_uuid.clear();
                }
            });

    nb::enum_<OffMeshLinkType>(m, "OffMeshLinkType")
        .value("Generic", OffMeshLinkType::Generic)
        .value("JumpDown", OffMeshLinkType::JumpDown)
        .value("Jump", OffMeshLinkType::Jump)
        .value("Climb", OffMeshLinkType::Climb);

    nb::class_<OffMeshLinkComponent, CxxComponent>(m, "OffMeshLinkComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<OffMeshLinkComponent>(self);
        })
        .def_rw("enabled", &OffMeshLinkComponent::enabled)
        .def_rw("link_type", &OffMeshLinkComponent::link_type)
        .def_rw("agent_type", &OffMeshLinkComponent::agent_type)
        .def_rw("area_id", &OffMeshLinkComponent::area_id)
        .def_prop_rw("start_local",
            [](OffMeshLinkComponent& self) {
                return tc_vec3_to_python(self.start_local);
            },
            [](OffMeshLinkComponent& self, nb::handle value) {
                self.start_local = tc_vec3_from_python(value);
            })
        .def_prop_rw("end_local",
            [](OffMeshLinkComponent& self) {
                return tc_vec3_to_python(self.end_local);
            },
            [](OffMeshLinkComponent& self, nb::handle value) {
                self.end_local = tc_vec3_from_python(value);
            })
        .def_rw("radius", &OffMeshLinkComponent::radius)
        .def_rw("bidirectional", &OffMeshLinkComponent::bidirectional)
        .def("start_world", [](OffMeshLinkComponent& self) {
            return vec3_to_python(self.start_world());
        })
        .def("end_world", [](OffMeshLinkComponent& self) {
            return vec3_to_python(self.end_world());
        })
        .def("center_entity", &OffMeshLinkComponent::center_entity);

    nb::class_<DetourClosestPointResult>(m, "DetourClosestPointResult")
        .def_ro("success", &DetourClosestPointResult::success)
        .def_ro("over_poly", &DetourClosestPointResult::over_poly)
        .def_ro("poly_ref", &DetourClosestPointResult::poly_ref)
        .def_prop_ro("point", [](const DetourClosestPointResult& self) {
            return point_to_python(self.point);
        });

    nb::class_<DetourRaycastResult>(m, "DetourRaycastResult")
        .def_ro("success", &DetourRaycastResult::success)
        .def_ro("hit", &DetourRaycastResult::hit)
        .def_ro("t", &DetourRaycastResult::t)
        .def_ro("visited", &DetourRaycastResult::visited)
        .def_prop_ro("hit_position", [](const DetourRaycastResult& self) {
            return point_to_python(self.hit_position);
        })
        .def_prop_ro("hit_normal", [](const DetourRaycastResult& self) {
            return point_to_python(self.hit_normal);
        });

    nb::class_<DetourPathfindingWorldComponent, CxxComponent>(m, "DetourPathfindingWorldComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<DetourPathfindingWorldComponent>(self);
        })
        .def_rw("navmesh_uuid", &DetourPathfindingWorldComponent::navmesh_uuid)
        .def_rw("query_extent_x", &DetourPathfindingWorldComponent::query_extent_x)
        .def_rw("query_extent_y", &DetourPathfindingWorldComponent::query_extent_y)
        .def_rw("query_extent_z", &DetourPathfindingWorldComponent::query_extent_z)
        .def_rw("max_polys", &DetourPathfindingWorldComponent::max_polys)
        .def_rw("max_straight_path", &DetourPathfindingWorldComponent::max_straight_path)
        .def_prop_rw("navmesh",
            [](DetourPathfindingWorldComponent& self) {
                nb::dict value;
                value["uuid"] = self.navmesh_uuid;
                value["name"] = "";
                return value;
            },
            [](DetourPathfindingWorldComponent& self, nb::dict value) {
                std::string uuid;
                if (value.contains("uuid")) {
                    uuid = nb::cast<std::string>(value["uuid"]);
                }
                if (self.navmesh_uuid != uuid) {
                    self.navmesh_uuid = std::move(uuid);
                    self.clear();
                }
            })
        .def("rebuild", &DetourPathfindingWorldComponent::rebuild)
        .def("clear", &DetourPathfindingWorldComponent::clear)
        .def("is_ready", &DetourPathfindingWorldComponent::is_ready)
        .def("closest_point", [](DetourPathfindingWorldComponent& self, nb::handle point) {
            return self.closest_point(py_vec3(point));
        }, nb::arg("point"))
        .def("find_path", [](DetourPathfindingWorldComponent& self, nb::handle start, nb::handle end) {
            return path_to_python(self.find_path(py_vec3(start), py_vec3(end)));
        }, nb::arg("start"), nb::arg("end"))
        .def("find_detailed_path", [](DetourPathfindingWorldComponent& self, nb::handle start, nb::handle end) {
            return detailed_path_to_python(self.find_detailed_path(py_vec3(start), py_vec3(end)));
        }, nb::arg("start"), nb::arg("end"))
        .def("raycast", [](DetourPathfindingWorldComponent& self, nb::handle start, nb::handle end) {
            return self.raycast(py_vec3(start), py_vec3(end));
        }, nb::arg("start"), nb::arg("end"));

    // RecastNavMeshBuilderComponent
    nb::class_<RecastNavMeshBuilderComponent, CxxComponent>(m, "RecastNavMeshBuilderComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<RecastNavMeshBuilderComponent>(self);
        })
        // Agent type selection
        .def_rw("agent_type_name", &RecastNavMeshBuilderComponent::agent_type_name)
        .def_rw("area_id", &RecastNavMeshBuilderComponent::area_id)
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
        .def_rw("show_detail_mesh", &RecastNavMeshBuilderComponent::show_detail_mesh)
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

    nb::module_ atexit = nb::module_::import_("atexit");
    atexit.attr("register")(nb::cpp_function(&cleanup_navmesh_callbacks));
}

} // namespace termin

NB_MODULE(_navmesh_native, m) {
    m.doc() = "NavMesh native module (RecastNavMeshBuilderComponent)";
    termin::bind_recast_navmesh_builder(m);
    m.def("register_navmesh_kind_handlers", &termin::register_navmesh_kind_handlers,
        "Register navmesh_handle kind handlers explicitly.");
}
