#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/tuple.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/optional.h>

#include "termin/voxels/voxel_grid.hpp"
#include "termin/voxels/voxel_grid_handle.hpp"
#include "termin/inspect/tc_kind.hpp"
#include "inspect/tc_inspect_python.hpp"
#include <tcbase/tc_log.hpp>

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

void serialize_surface_normals(nb::dict& result, const VoxelGrid& grid) {
    const auto& normals = grid.surface_normals();
    if (normals.empty()) {
        return;
    }
    nb::dict normals_dict;
    for (const auto& [key, normal_list] : normals) {
        int vx = std::get<0>(key);
        int vy = std::get<1>(key);
        int vz = std::get<2>(key);
        std::string key_str = std::to_string(vx) + "," + std::to_string(vy) + "," + std::to_string(vz);
        nb::list py_normals;
        for (const auto& normal : normal_list) {
            py_normals.append(nb::make_tuple(normal.x, normal.y, normal.z));
        }
        normals_dict[nb::str(key_str.c_str())] = py_normals;
    }
    result["surface_normals"] = normals_dict;
}

Vec3 vec3_from_sequence(nb::handle value) {
    nb::sequence seq = nb::cast<nb::sequence>(value);
    return Vec3(
        nb::cast<double>(seq[0]),
        nb::cast<double>(seq[1]),
        nb::cast<double>(seq[2])
    );
}

void deserialize_surface_normals(VoxelGrid& grid, const nb::dict& data) {
    if (!data.contains("surface_normals")) {
        return;
    }
    nb::dict normals_dict = nb::cast<nb::dict>(data["surface_normals"]);
    for (auto item : normals_dict) {
        std::string key_str = nb::cast<std::string>(item.first);
        size_t pos1 = key_str.find(',');
        size_t pos2 = key_str.find(',', pos1 + 1);
        if (pos1 == std::string::npos || pos2 == std::string::npos) {
            continue;
        }
        int vx = std::stoi(key_str.substr(0, pos1));
        int vy = std::stoi(key_str.substr(pos1 + 1, pos2 - pos1 - 1));
        int vz = std::stoi(key_str.substr(pos2 + 1));

        nb::sequence normal_data = nb::cast<nb::sequence>(item.second);
        std::vector<Vec3> normals;
        if (nb::len(normal_data) == 3 && !nb::isinstance<nb::sequence>(normal_data[0])) {
            normals.push_back(vec3_from_sequence(item.second));
        } else {
            for (nb::handle normal : normal_data) {
                normals.push_back(vec3_from_sequence(normal));
            }
        }
        grid.set_surface_normals(vx, vy, vz, normals);
    }
}

VoxelGrid voxel_grid_from_dict(const nb::dict& data) {
    Vec3 origin = Vec3::zero();
    if (data.contains("origin")) {
        origin = vec3_from_sequence(data["origin"]);
    }
    double cell_size = data.contains("cell_size") ? nb::cast<double>(data["cell_size"]) : 0.25;
    std::string name = data.contains("name") ? nb::cast<std::string>(data["name"]) : "";
    std::string source_path = data.contains("path") ? nb::cast<std::string>(data["path"]) : "";

    VoxelGrid grid(cell_size, origin, name, source_path);

    if (data.contains("chunks")) {
        nb::dict chunks_dict = nb::cast<nb::dict>(data["chunks"]);
        nb::module_ gzip = nb::module_::import_("gzip");
        nb::module_ base64 = nb::module_::import_("base64");

        for (auto item : chunks_dict) {
            std::string key_str = nb::cast<std::string>(item.first);
            nb::dict chunk_data = nb::cast<nb::dict>(item.second);

            size_t pos1 = key_str.find(',');
            size_t pos2 = key_str.find(',', pos1 + 1);
            if (pos1 == std::string::npos || pos2 == std::string::npos) {
                continue;
            }
            int cx = std::stoi(key_str.substr(0, pos1));
            int cy = std::stoi(key_str.substr(pos1 + 1, pos2 - pos1 - 1));
            int cz = std::stoi(key_str.substr(pos2 + 1));

            nb::bytes compressed = nb::cast<nb::bytes>(base64.attr("b64decode")(chunk_data["data"]));
            nb::bytes raw = nb::cast<nb::bytes>(gzip.attr("decompress")(compressed));
            char* raw_data = nullptr;
            Py_ssize_t raw_size = 0;
            if (PyBytes_AsStringAndSize(raw.ptr(), &raw_data, &raw_size) != 0 || raw_data == nullptr) {
                throw std::runtime_error("VoxelGrid.deserialize: expected bytes chunk payload");
            }
            if (raw_size < CHUNK_VOLUME) {
                throw std::runtime_error("VoxelGrid.deserialize: chunk payload is shorter than CHUNK_VOLUME");
            }

            for (int z = 0; z < CHUNK_SIZE; z++) {
                for (int y = 0; y < CHUNK_SIZE; y++) {
                    for (int x = 0; x < CHUNK_SIZE; x++) {
                        int idx = x + y * CHUNK_SIZE + z * CHUNK_SIZE * CHUNK_SIZE;
                        uint8_t val = static_cast<uint8_t>(raw_data[idx]);
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

    deserialize_surface_normals(grid, data);
    return grid;
}

void register_voxel_grid_kind_handlers() {
    static bool registered = false;
    if (registered) {
        return;
    }

    // The legacy kind name is kept for scene compatibility; the value type is TcVoxelGrid.
    tc::register_cpp_handle_kind<TcVoxelGrid>("voxel_grid_handle");

    nb::module_ voxels_module = nb::module_::import_("termin.voxels._voxels_native");
    tc::KindRegistry::instance().register_type(voxels_module.attr("TcVoxelGrid"), "voxel_grid_handle");

    tc::KindRegistry::instance().register_python(
        "voxel_grid_handle",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            TcVoxelGrid handle = nb::cast<TcVoxelGrid>(obj);
            nb::dict result;
            if (handle.is_valid()) {
                result["uuid"] = std::string(handle.uuid());
                result["name"] = std::string(handle.name());
                std::string path = std::string(handle.source_path());
                result["type"] = path.empty() ? "uuid" : "path";
                if (!path.empty()) {
                    result["path"] = path;
                }
            }
            return result;
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            if (nb::isinstance<nb::str>(data)) {
                return nb::cast(TcVoxelGrid::from_uuid(nb::cast<std::string>(data)));
            }

            if (nb::isinstance<nb::dict>(data)) {
                nb::dict d = nb::cast<nb::dict>(data);
                if (d.contains("uuid")) {
                    return nb::cast(TcVoxelGrid::from_uuid(nb::cast<std::string>(d["uuid"])));
                }
                if (d.contains("name")) {
                    return nb::cast(TcVoxelGrid::from_name(nb::cast<std::string>(d["name"])));
                }
            }
            return nb::cast(TcVoxelGrid());
        })
    );

    registered = true;
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
        }, nb::rv_policy::move)
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
        }, nb::rv_policy::move)
        .def_prop_ro("surface_normals", [](const VoxelGrid& grid) {
            return surface_normals_to_dict(grid.surface_normals());
        }, nb::rv_policy::move)

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

        .def("voxel_to_chunk", [](const VoxelGrid& grid, int vx, int vy, int vz) {
            auto [chunk_key, local] = grid.voxel_to_chunk(vx, vy, vz);
            return nb::make_tuple(
                nb::make_tuple(std::get<0>(chunk_key), std::get<1>(chunk_key), std::get<2>(chunk_key)),
                nb::make_tuple(std::get<0>(local), std::get<1>(local), std::get<2>(local))
            );
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
            result["name"] = grid.name();
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
            serialize_surface_normals(result, grid);
            return result;
        })
        .def("direct_serialize", [](const VoxelGrid& grid) {
            nb::dict result;
            result["type"] = "inline";
            result["name"] = grid.name();
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
            serialize_surface_normals(result, grid);
            return result;
        })
        .def_static("deserialize", [](const nb::dict& data) {
            return voxel_grid_from_dict(data);
        })
        .def_static("direct_deserialize", [](const nb::dict& data) {
            return voxel_grid_from_dict(data);
        });

    // ========== TcVoxelGrid ==========
    nb::class_<TcVoxelGrid>(m, "TcVoxelGrid")
        .def(nb::init<>())
        .def_static("from_uuid", &TcVoxelGrid::from_uuid, nb::arg("uuid"))
        .def_static("from_name", &TcVoxelGrid::from_name, nb::arg("name"))
        .def_static("declare", &TcVoxelGrid::declare, nb::arg("uuid"), nb::arg("name") = "")
        .def_prop_ro("is_valid", &TcVoxelGrid::is_valid)
        .def_prop_ro("is_loaded", &TcVoxelGrid::is_loaded)
        .def_prop_ro("uuid", [](const TcVoxelGrid& self) { return std::string(self.uuid()); })
        .def_prop_ro("name", [](const TcVoxelGrid& self) { return std::string(self.name()); })
        .def_prop_ro("source_path", [](const TcVoxelGrid& self) { return std::string(self.source_path()); })
        .def_prop_ro("version", &TcVoxelGrid::version)
        .def_prop_ro("grid", [](const TcVoxelGrid& self) -> nb::object {
            VoxelGrid* grid = self.grid();
            if (!grid) {
                return nb::none();
            }
            return nb::cast(grid, nb::rv_policy::reference);
        })
        .def("ensure_loaded", &TcVoxelGrid::ensure_loaded)
        .def("set_grid", &TcVoxelGrid::set_grid, nb::arg("grid"))
        .def("serialize", [](const TcVoxelGrid& self) {
            nb::dict result;
            if (self.is_valid()) {
                result["uuid"] = std::string(self.uuid());
                result["name"] = std::string(self.name());
                std::string path = std::string(self.source_path());
                result["type"] = path.empty() ? "uuid" : "path";
                if (!path.empty()) {
                    result["path"] = path;
                }
            }
            return result;
        })
        .def_static("deserialize", [](const nb::dict& data) {
            if (data.contains("uuid")) {
                return TcVoxelGrid::from_uuid(nb::cast<std::string>(data["uuid"]));
            }
            if (data.contains("name")) {
                return TcVoxelGrid::from_name(nb::cast<std::string>(data["name"]));
            }
            return TcVoxelGrid();
        }, nb::arg("data"));

    m.def("declare_voxel_grid_asset", [](const std::string& uuid, const std::string& name) {
        TcVoxelGrid grid = TcVoxelGrid::declare(uuid, name);
        return grid.is_valid();
    }, nb::arg("uuid"), nb::arg("name") = "");

    m.def("tc_voxel_grid_get_all_info", []() {
        nb::list result;
        size_t count = 0;
        tc_voxel_grid_info* infos = tc_voxel_grid_get_all_info(&count);
        for (size_t i = 0; i < count; ++i) {
            nb::dict info;
            info["handle"] = nb::make_tuple(infos[i].handle.index, infos[i].handle.generation);
            info["uuid"] = std::string(infos[i].uuid);
            info["name"] = infos[i].name ? std::string(infos[i].name) : "";
            info["source_path"] = infos[i].source_path ? std::string(infos[i].source_path) : "";
            info["ref_count"] = infos[i].ref_count;
            info["version"] = infos[i].version;
            info["is_loaded"] = infos[i].is_loaded != 0;
            result.append(info);
        }
        free(infos);
        return result;
    });

    m.def("set_voxel_grid_asset_metadata",
          [](const std::string& uuid, const std::string& name, const std::string& source_path) {
              TcVoxelGrid grid = TcVoxelGrid::declare(uuid, name);
              tc_voxel_grid* raw = grid.get();
              if (!raw) {
                  return false;
              }
              return tc_voxel_grid_set_metadata(
                  raw,
                  name.empty() ? nullptr : name.c_str(),
                  source_path.empty() ? nullptr : source_path.c_str());
          },
          nb::arg("uuid"), nb::arg("name") = "", nb::arg("source_path") = "");

    m.def("set_voxel_grid_asset_data",
          [](const std::string& uuid,
             const std::string& name,
             const std::string& source_path,
             const VoxelGrid& payload) {
              TcVoxelGrid grid = TcVoxelGrid::declare(uuid, name);
              tc_voxel_grid* raw = grid.get();
              if (!raw) {
                  return false;
              }
              tc_voxel_grid_set_metadata(
                  raw,
                  name.empty() ? nullptr : name.c_str(),
                  source_path.empty() ? nullptr : source_path.c_str());
              return grid.set_grid(payload);
          },
          nb::arg("uuid"), nb::arg("name"), nb::arg("source_path"), nb::arg("payload"));

    m.attr("VoxelGridHandle") = m.attr("TcVoxelGrid");

    m.def("register_voxel_grid_kind_handlers", &register_voxel_grid_kind_handlers,
        "Register voxel_grid_handle kind handlers explicitly.");

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
