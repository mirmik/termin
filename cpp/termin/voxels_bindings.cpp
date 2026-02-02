#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/optional.h>

#include "termin/voxels/voxel_grid.hpp"
#include "termin/assets/handles.hpp"
#include "termin/inspect/tc_kind.hpp"
#include "termin/bindings/inspect/tc_inspect_python.hpp"
#include "tc_log.hpp"

namespace nb = nanobind;
using namespace termin::voxels;
using namespace termin;

// Helper: numpy array to vector of Vec3
std::vector<Vec3> numpy_to_vec3_vector(nb::ndarray<double, nb::c_contig, nb::device::cpu> arr) {
    size_t n = arr.shape(0);
    double* ptr = arr.data();
    size_t stride = arr.shape(1);
    if (stride != 3) {
        throw std::runtime_error("Expected Nx3 array for vertices");
    }
    std::vector<Vec3> result;
    result.reserve(n);
    for (size_t i = 0; i < n; i++) {
        result.emplace_back(ptr[i * stride + 0], ptr[i * stride + 1], ptr[i * stride + 2]);
    }
    return result;
}

// Helper: numpy array to vector of triangles
std::vector<std::tuple<int, int, int>> numpy_to_triangles(nb::ndarray<int, nb::c_contig, nb::device::cpu> arr) {
    size_t n = arr.shape(0);
    int* ptr = arr.data();
    size_t stride = arr.shape(1);
    if (stride != 3) {
        throw std::runtime_error("Expected Mx3 array for triangles");
    }
    std::vector<std::tuple<int, int, int>> result;
    result.reserve(n);
    for (size_t i = 0; i < n; i++) {
        result.emplace_back(ptr[i * stride + 0], ptr[i * stride + 1], ptr[i * stride + 2]);
    }
    return result;
}

// Helper: surface normals to dict (list of normals per voxel)
nb::dict surface_normals_to_dict(const std::unordered_map<VoxelKey, std::vector<Vec3>, ChunkKeyHash>& normals) {
    nb::dict result;
    for (const auto& [key, normal_list] : normals) {
        nb::tuple py_key = nb::make_tuple(std::get<0>(key), std::get<1>(key), std::get<2>(key));
        nb::list py_normals;
        for (const auto& normal : normal_list) {
            double* data = new double[3]{normal.x, normal.y, normal.z};
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            auto py_normal = nb::ndarray<nb::numpy, double, nb::shape<3>>(data, {3}, owner);
            py_normals.append(py_normal);
        }
        result[py_key] = py_normals;
    }
    return result;
}

NB_MODULE(_voxels_native, m) {
    m.doc() = "Native C++ voxelization module";

    // Constants
    m.attr("CHUNK_SIZE") = CHUNK_SIZE;
    m.attr("VOXEL_EMPTY") = VOXEL_EMPTY;
    m.attr("VOXEL_SOLID") = VOXEL_SOLID;
    m.attr("VOXEL_SURFACE") = VOXEL_SURFACE;

    // VoxelChunk class
    nb::class_<VoxelChunk>(m, "VoxelChunk")
        .def(nb::init<>())
        .def("get", &VoxelChunk::get)
        .def("set", &VoxelChunk::set)
        .def("fill", &VoxelChunk::fill)
        .def("clear", &VoxelChunk::clear)
        .def_prop_ro("is_empty", &VoxelChunk::is_empty)
        .def_prop_ro("non_empty_count", &VoxelChunk::non_empty_count)
        .def("iter_non_empty", &VoxelChunk::iter_non_empty)
        .def_prop_ro("data", [](const VoxelChunk& c) {
            // Return as numpy array
            uint8_t* data = new uint8_t[CHUNK_VOLUME];
            const auto& chunk_data = c.data();
            for (int z = 0; z < CHUNK_SIZE; z++) {
                for (int y = 0; y < CHUNK_SIZE; y++) {
                    for (int x = 0; x < CHUNK_SIZE; x++) {
                        data[x + y * CHUNK_SIZE + z * CHUNK_SIZE * CHUNK_SIZE] =
                            chunk_data[x + y * CHUNK_SIZE + z * CHUNK_SIZE * CHUNK_SIZE];
                    }
                }
            }
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<uint8_t*>(p); });
            size_t shape[3] = {CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE};
            return nb::ndarray<nb::numpy, uint8_t>(data, 3, shape, owner);
        })
        .def("serialize", [](const VoxelChunk& c) {
            nb::module_ gzip = nb::module_::import_("gzip");
            nb::module_ base64 = nb::module_::import_("base64");

            // Get raw data as bytes
            const auto& data = c.data();
            nb::bytes raw_bytes(reinterpret_cast<const char*>(data.data()), CHUNK_VOLUME);

            // Compress and encode
            nb::bytes compressed = nb::cast<nb::bytes>(gzip.attr("compress")(raw_bytes));
            nb::object encoded = base64.attr("b64encode")(compressed).attr("decode")("ascii");

            nb::dict result;
            result["data"] = encoded;
            result["count"] = c.non_empty_count();
            return result;
        })
        .def_static("deserialize", [](const nb::dict& data) {
            nb::module_ gzip = nb::module_::import_("gzip");
            nb::module_ base64 = nb::module_::import_("base64");

            nb::bytes compressed = nb::cast<nb::bytes>(base64.attr("b64decode")(data["data"]));
            nb::bytes raw = nb::cast<nb::bytes>(gzip.attr("decompress")(compressed));

            std::string raw_str = nb::cast<std::string>(raw);

            VoxelChunk chunk;
            // Set data directly
            for (int z = 0; z < CHUNK_SIZE; z++) {
                for (int y = 0; y < CHUNK_SIZE; y++) {
                    for (int x = 0; x < CHUNK_SIZE; x++) {
                        int idx = x + y * CHUNK_SIZE + z * CHUNK_SIZE * CHUNK_SIZE;
                        uint8_t val = static_cast<uint8_t>(raw_str[idx]);
                        if (val != VOXEL_EMPTY) {
                            chunk.set(x, y, z, val);
                        }
                    }
                }
            }
            return chunk;
        })
        .def("recalculate_count", [](VoxelChunk& c) {
            // Recalculate count by iterating all data
            // For C++ VoxelChunk, count is always accurate, but we provide this for compatibility
        });

    // VoxelGrid class
    nb::class_<VoxelGrid>(m, "VoxelGrid")
        .def("__init__", [](VoxelGrid* self, double cell_size, nb::object origin, std::string name, std::string source_path) {
            Vec3 o = Vec3::zero();
            if (!origin.is_none()) {
                if (nb::isinstance<Vec3>(origin)) {
                    o = nb::cast<Vec3>(origin);
                } else if (nb::isinstance<nb::tuple>(origin)) {
                    nb::tuple t = nb::cast<nb::tuple>(origin);
                    o = Vec3(nb::cast<double>(t[0]), nb::cast<double>(t[1]), nb::cast<double>(t[2]));
                } else if (nb::isinstance<nb::list>(origin)) {
                    nb::list l = nb::cast<nb::list>(origin);
                    o = Vec3(nb::cast<double>(l[0]), nb::cast<double>(l[1]), nb::cast<double>(l[2]));
                } else {
                    // Try numpy array
                    auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(origin);
                    double* ptr = arr.data();
                    o = Vec3(ptr[0], ptr[1], ptr[2]);
                }
            }
            new (self) VoxelGrid(cell_size, o, name, source_path);
        },
             nb::arg("cell_size") = 0.25,
             nb::arg("origin") = nb::none(),
             nb::arg("name") = "",
             nb::arg("source_path") = "")

        // Properties (as Python properties, not methods, for compatibility)
        .def_prop_ro("cell_size", &VoxelGrid::cell_size)
        .def_prop_ro("chunk_count", &VoxelGrid::chunk_count)
        .def_prop_ro("voxel_count", &VoxelGrid::voxel_count)
        .def_prop_rw("name",
            [](const VoxelGrid& g) { return g.name(); },
            [](VoxelGrid& g, const std::string& n) { g.set_name(n); })
        .def_prop_rw("source_path",
            [](const VoxelGrid& g) { return g.source_path(); },
            [](VoxelGrid& g, const std::string& p) { g.set_source_path(p); })
        .def_prop_ro("origin", [](const VoxelGrid& g) {
            Vec3 o = g.origin();
            double* data = new double[3]{o.x, o.y, o.z};
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            return nb::ndarray<nb::numpy, double, nb::shape<3>>(data, {3}, owner);
        })
        .def_prop_ro("surface_normals", [](const VoxelGrid& grid) {
            return surface_normals_to_dict(grid.surface_normals());
        })

        // Voxel access
        .def("get", &VoxelGrid::get)
        .def("set", &VoxelGrid::set)
        .def("clear", &VoxelGrid::clear)

        .def("get_at_world", [](const VoxelGrid& grid, nb::ndarray<double, nb::c_contig, nb::device::cpu> pos) {
            double* ptr = pos.data();
            return grid.get_at_world(Vec3(ptr[0], ptr[1], ptr[2]));
        })
        .def("set_at_world", [](VoxelGrid& grid, nb::ndarray<double, nb::c_contig, nb::device::cpu> pos, uint8_t value) {
            double* ptr = pos.data();
            grid.set_at_world(Vec3(ptr[0], ptr[1], ptr[2]), value);
        })

        .def("world_to_voxel", [](const VoxelGrid& grid, nb::ndarray<double, nb::c_contig, nb::device::cpu> pos) {
            double* ptr = pos.data();
            return grid.world_to_voxel(Vec3(ptr[0], ptr[1], ptr[2]));
        })

        .def("voxel_to_world", [](const VoxelGrid& grid, int vx, int vy, int vz) {
            Vec3 w = grid.voxel_to_world(vx, vy, vz);
            double* data = new double[3]{w.x, w.y, w.z};
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            return nb::ndarray<nb::numpy, double, nb::shape<3>>(data, {3}, owner);
        })

        // Chunk access
        .def("get_chunk", [](const VoxelGrid& grid, int cx, int cy, int cz) -> nb::object {
            const VoxelChunk* chunk = grid.get_chunk(cx, cy, cz);
            if (!chunk) return nb::none();
            // Return copy to avoid dangling pointer issues
            return nb::cast(*chunk);
        })
        .def("iter_chunks", [](const VoxelGrid& grid) {
            nb::list result;
            for (const auto& [key, chunk_ptr] : grid.iter_chunks()) {
                nb::tuple py_key = nb::make_tuple(std::get<0>(key), std::get<1>(key), std::get<2>(key));
                result.append(nb::make_tuple(py_key, *chunk_ptr));
            }
            return result;
        })

        .def("iter_non_empty", &VoxelGrid::iter_non_empty)

        // Bounds
        .def("bounds", [](const VoxelGrid& grid) -> nb::object {
            auto b = grid.bounds();
            if (!b) return nb::none();
            auto [min_v, max_v] = *b;
            return nb::make_tuple(
                nb::make_tuple(std::get<0>(min_v), std::get<1>(min_v), std::get<2>(min_v)),
                nb::make_tuple(std::get<0>(max_v), std::get<1>(max_v), std::get<2>(max_v))
            );
        })
        .def("world_bounds", [](const VoxelGrid& grid) -> nb::object {
            auto b = grid.world_bounds();
            if (!b) return nb::none();
            auto [min_w, max_w] = *b;
            double* min_data = new double[3]{min_w.x, min_w.y, min_w.z};
            double* max_data = new double[3]{max_w.x, max_w.y, max_w.z};
            nb::capsule min_owner(min_data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            nb::capsule max_owner(max_data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            auto min_arr = nb::ndarray<nb::numpy, double, nb::shape<3>>(min_data, {3}, min_owner);
            auto max_arr = nb::ndarray<nb::numpy, double, nb::shape<3>>(max_data, {3}, max_owner);
            return nb::make_tuple(min_arr, max_arr);
        })

        // Voxelization
        .def("voxelize_mesh", [](VoxelGrid& grid,
                                  nb::ndarray<double, nb::c_contig, nb::device::cpu> vertices,
                                  nb::ndarray<int, nb::c_contig, nb::device::cpu> triangles,
                                  uint8_t voxel_type) {
            auto verts = numpy_to_vec3_vector(vertices);
            auto tris = numpy_to_triangles(triangles);
            return grid.voxelize_mesh(verts, tris, voxel_type);
        }, nb::arg("vertices"), nb::arg("triangles"), nb::arg("voxel_type") = VOXEL_SOLID)

        .def("fill_interior", &VoxelGrid::fill_interior,
             nb::arg("fill_value") = VOXEL_SOLID)

        .def("mark_surface", &VoxelGrid::mark_surface,
             nb::arg("surface_value") = VOXEL_SURFACE)

        .def("clear_by_type", &VoxelGrid::clear_by_type,
             nb::arg("type_to_clear") = VOXEL_SOLID)

        .def("extract_surface", &VoxelGrid::extract_surface,
             nb::arg("surface_value") = VOXEL_SOLID)

        // Surface normals
        .def("compute_surface_normals", [](VoxelGrid& grid,
                                           nb::ndarray<double, nb::c_contig, nb::device::cpu> vertices,
                                           nb::ndarray<int, nb::c_contig, nb::device::cpu> triangles) {
            auto verts = numpy_to_vec3_vector(vertices);
            auto tris = numpy_to_triangles(triangles);
            return grid.compute_surface_normals(verts, tris);
        })

        .def("get_surface_normal", [](const VoxelGrid& grid, int vx, int vy, int vz) -> nb::object {
            if (!grid.has_surface_normal(vx, vy, vz)) {
                return nb::none();
            }
            Vec3 n = grid.get_surface_normal(vx, vy, vz);
            double* data = new double[3]{n.x, n.y, n.z};
            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
            return nb::cast(nb::ndarray<nb::numpy, double, nb::shape<3>>(data, {3}, owner));
        })

        .def("get_surface_normals", [](const VoxelGrid& grid, int vx, int vy, int vz) -> nb::object {
            const auto& normals = grid.get_surface_normals(vx, vy, vz);
            if (normals.empty()) return nb::none();
            nb::list result;
            for (const auto& n : normals) {
                double* data = new double[3]{n.x, n.y, n.z};
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
                result.append(nb::cast(nb::ndarray<nb::numpy, double, nb::shape<3>>(data, {3}, owner)));
            }
            return result;
        })

        .def("has_surface_normal", &VoxelGrid::has_surface_normal)

        .def("add_surface_normal", [](VoxelGrid& grid, int vx, int vy, int vz, nb::ndarray<double, nb::c_contig, nb::device::cpu> normal) {
            double* ptr = normal.data();
            grid.add_surface_normal(vx, vy, vz, Vec3(ptr[0], ptr[1], ptr[2]));
        })

        .def("set_surface_normals", [](VoxelGrid& grid, int vx, int vy, int vz, nb::list normals) {
            std::vector<Vec3> vec_normals;
            for (auto item : normals) {
                auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(item);
                double* ptr = arr.data();
                vec_normals.emplace_back(ptr[0], ptr[1], ptr[2]);
            }
            grid.set_surface_normals(vx, vy, vz, vec_normals);
        })

        // Serialization
        .def("serialize", [](const VoxelGrid& grid) {
            if (!grid.source_path().empty()) {
                nb::dict result;
                result["type"] = "path";
                result["path"] = grid.source_path();
                return result;
            }
            // Inline serialization
            nb::dict result;
            result["type"] = "inline";
            Vec3 o = grid.origin();
            result["origin"] = nb::make_tuple(o.x, o.y, o.z);
            result["cell_size"] = grid.cell_size();

            nb::dict chunks_dict;
            for (const auto& [key, chunk_ptr] : grid.iter_chunks()) {
                int cx = std::get<0>(key);
                int cy = std::get<1>(key);
                int cz = std::get<2>(key);
                std::string key_str = std::to_string(cx) + "," + std::to_string(cy) + "," + std::to_string(cz);

                // Serialize chunk
                nb::module_ gzip = nb::module_::import_("gzip");
                nb::module_ base64 = nb::module_::import_("base64");
                const auto& data = chunk_ptr->data();
                nb::bytes raw_bytes(reinterpret_cast<const char*>(data.data()), CHUNK_VOLUME);
                nb::bytes compressed = nb::cast<nb::bytes>(gzip.attr("compress")(raw_bytes));
                nb::object encoded = base64.attr("b64encode")(compressed).attr("decode")("ascii");

                nb::dict chunk_data;
                chunk_data["data"] = encoded;
                chunk_data["count"] = chunk_ptr->non_empty_count();
                chunks_dict[nb::str(key_str.c_str())] = chunk_data;
            }
            result["chunks"] = chunks_dict;
            return result;
        })
        .def("direct_serialize", [](const VoxelGrid& grid) {
            nb::dict result;
            result["type"] = "inline";
            Vec3 o = grid.origin();
            result["origin"] = nb::make_tuple(o.x, o.y, o.z);
            result["cell_size"] = grid.cell_size();

            nb::dict chunks_dict;
            for (const auto& [key, chunk_ptr] : grid.iter_chunks()) {
                int cx = std::get<0>(key);
                int cy = std::get<1>(key);
                int cz = std::get<2>(key);
                std::string key_str = std::to_string(cx) + "," + std::to_string(cy) + "," + std::to_string(cz);

                nb::module_ gzip = nb::module_::import_("gzip");
                nb::module_ base64 = nb::module_::import_("base64");
                const auto& data = chunk_ptr->data();
                nb::bytes raw_bytes(reinterpret_cast<const char*>(data.data()), CHUNK_VOLUME);
                nb::bytes compressed = nb::cast<nb::bytes>(gzip.attr("compress")(raw_bytes));
                nb::object encoded = base64.attr("b64encode")(compressed).attr("decode")("ascii");

                nb::dict chunk_data;
                chunk_data["data"] = encoded;
                chunk_data["count"] = chunk_ptr->non_empty_count();
                chunks_dict[nb::str(key_str.c_str())] = chunk_data;
            }
            result["chunks"] = chunks_dict;
            return result;
        })
        .def_static("deserialize", [](const nb::dict& data) {
            nb::object origin_obj = data["origin"];
            nb::tuple origin_tuple = nb::cast<nb::tuple>(origin_obj);
            Vec3 origin(
                nb::cast<double>(origin_tuple[0]),
                nb::cast<double>(origin_tuple[1]),
                nb::cast<double>(origin_tuple[2])
            );
            double cell_size = nb::cast<double>(data["cell_size"]);
            std::string source_path = data.contains("path") ? nb::cast<std::string>(data["path"]) : "";

            VoxelGrid grid(cell_size, origin, "", source_path);

            if (data.contains("chunks")) {
                nb::dict chunks_dict = nb::cast<nb::dict>(data["chunks"]);
                nb::module_ gzip = nb::module_::import_("gzip");
                nb::module_ base64 = nb::module_::import_("base64");

                for (auto item : chunks_dict) {
                    std::string key_str = nb::cast<std::string>(item.first);
                    nb::dict chunk_data = nb::cast<nb::dict>(item.second);

                    // Parse key "cx,cy,cz"
                    size_t pos1 = key_str.find(',');
                    size_t pos2 = key_str.find(',', pos1 + 1);
                    int cx = std::stoi(key_str.substr(0, pos1));
                    int cy = std::stoi(key_str.substr(pos1 + 1, pos2 - pos1 - 1));
                    int cz = std::stoi(key_str.substr(pos2 + 1));

                    // Deserialize chunk data
                    nb::bytes compressed = nb::cast<nb::bytes>(base64.attr("b64decode")(chunk_data["data"]));
                    nb::bytes raw = nb::cast<nb::bytes>(gzip.attr("decompress")(compressed));
                    std::string raw_str = nb::cast<std::string>(raw);

                    for (int z = 0; z < CHUNK_SIZE; z++) {
                        for (int y = 0; y < CHUNK_SIZE; y++) {
                            for (int x = 0; x < CHUNK_SIZE; x++) {
                                int idx = x + y * CHUNK_SIZE + z * CHUNK_SIZE * CHUNK_SIZE;
                                uint8_t val = static_cast<uint8_t>(raw_str[idx]);
                                if (val != VOXEL_EMPTY) {
                                    int vx = cx * CHUNK_SIZE + x;
                                    int vy = cy * CHUNK_SIZE + y;
                                    int vz = cz * CHUNK_SIZE + z;
                                    grid.set(vx, vy, vz, val);
                                }
                            }
                        }
                    }
                }
            }
            return grid;
        })
        .def_static("direct_deserialize", [](const nb::dict& data) {
            // Same as deserialize
            nb::object origin_obj = data["origin"];
            nb::tuple origin_tuple = nb::cast<nb::tuple>(origin_obj);
            Vec3 origin(
                nb::cast<double>(origin_tuple[0]),
                nb::cast<double>(origin_tuple[1]),
                nb::cast<double>(origin_tuple[2])
            );
            double cell_size = nb::cast<double>(data["cell_size"]);
            std::string source_path = data.contains("path") ? nb::cast<std::string>(data["path"]) : "";

            VoxelGrid grid(cell_size, origin, "", source_path);

            if (data.contains("chunks")) {
                nb::dict chunks_dict = nb::cast<nb::dict>(data["chunks"]);
                nb::module_ gzip = nb::module_::import_("gzip");
                nb::module_ base64 = nb::module_::import_("base64");

                for (auto item : chunks_dict) {
                    std::string key_str = nb::cast<std::string>(item.first);
                    nb::dict chunk_data = nb::cast<nb::dict>(item.second);

                    size_t pos1 = key_str.find(',');
                    size_t pos2 = key_str.find(',', pos1 + 1);
                    int cx = std::stoi(key_str.substr(0, pos1));
                    int cy = std::stoi(key_str.substr(pos1 + 1, pos2 - pos1 - 1));
                    int cz = std::stoi(key_str.substr(pos2 + 1));

                    nb::bytes compressed = nb::cast<nb::bytes>(base64.attr("b64decode")(chunk_data["data"]));
                    nb::bytes raw = nb::cast<nb::bytes>(gzip.attr("decompress")(compressed));
                    std::string raw_str = nb::cast<std::string>(raw);

                    for (int z = 0; z < CHUNK_SIZE; z++) {
                        for (int y = 0; y < CHUNK_SIZE; y++) {
                            for (int x = 0; x < CHUNK_SIZE; x++) {
                                int idx = x + y * CHUNK_SIZE + z * CHUNK_SIZE * CHUNK_SIZE;
                                uint8_t val = static_cast<uint8_t>(raw_str[idx]);
                                if (val != VOXEL_EMPTY) {
                                    int vx = cx * CHUNK_SIZE + x;
                                    int vy = cy * CHUNK_SIZE + y;
                                    int vz = cz * CHUNK_SIZE + z;
                                    grid.set(vx, vy, vz, val);
                                }
                            }
                        }
                    }
                }
            }
            return grid;
        });

    // ========== VoxelGridHandle ==========
    nb::class_<VoxelGridHandle>(m, "VoxelGridHandle")
        .def(nb::init<>())
        .def("__init__", [](VoxelGridHandle* self, nb::object asset) {
            new (self) VoxelGridHandle(asset);
        }, nb::arg("asset"))
        .def_static("from_name", &VoxelGridHandle::from_name, nb::arg("name"))
        .def_static("from_asset", &VoxelGridHandle::from_asset, nb::arg("asset"))
        .def_static("from_uuid", &VoxelGridHandle::from_uuid, nb::arg("uuid"))
        .def_static("deserialize", &VoxelGridHandle::deserialize, nb::arg("data"))
        .def_rw("asset", &VoxelGridHandle::asset)
        .def_prop_ro("is_valid", &VoxelGridHandle::is_valid)
        .def_prop_ro("name", &VoxelGridHandle::name)
        .def_prop_ro("grid", &VoxelGridHandle::grid)
        .def_prop_ro("version", &VoxelGridHandle::version)
        .def("get", &VoxelGridHandle::get)
        .def("get_grid", &VoxelGridHandle::get)
        .def("get_grid_or_none", &VoxelGridHandle::get)
        .def("get_asset", [](const VoxelGridHandle& self) { return self.asset; })
        .def("serialize", &VoxelGridHandle::serialize);

    // Register kind handler for voxel_grid_handle
    // C++ handler for C++ fields
    tc::register_cpp_handle_kind<VoxelGridHandle>("voxel_grid_handle");

    // Python handler for Python fields
    tc::KindRegistry::instance().register_python(
        "voxel_grid_handle",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            VoxelGridHandle handle = nb::cast<VoxelGridHandle>(obj);
            return handle.serialize();
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            // Handle UUID string
            if (nb::isinstance<nb::str>(data)) {
                return nb::cast(VoxelGridHandle::from_uuid(nb::cast<std::string>(data)));
            }

            // Handle dict format
            if (nb::isinstance<nb::dict>(data)) {
                nb::dict d = nb::cast<nb::dict>(data);
                return nb::cast(VoxelGridHandle::deserialize(d));
            }
            return nb::cast(VoxelGridHandle());
        })
    );

    // Standalone function for testing
    m.def("triangle_aabb_intersect", [](
        nb::ndarray<double, nb::c_contig, nb::device::cpu> v0,
        nb::ndarray<double, nb::c_contig, nb::device::cpu> v1,
        nb::ndarray<double, nb::c_contig, nb::device::cpu> v2,
        nb::ndarray<double, nb::c_contig, nb::device::cpu> center,
        nb::ndarray<double, nb::c_contig, nb::device::cpu> half_size
    ) {
        double* b0 = v0.data();
        double* b1 = v1.data();
        double* b2 = v2.data();
        double* bc = center.data();
        double* bh = half_size.data();

        return triangle_aabb_intersect(
            Vec3(b0[0], b0[1], b0[2]),
            Vec3(b1[0], b1[1], b1[2]),
            Vec3(b2[0], b2[1], b2[2]),
            Vec3(bc[0], bc[1], bc[2]),
            Vec3(bh[0], bh[1], bh[2])
        );
    });
}
