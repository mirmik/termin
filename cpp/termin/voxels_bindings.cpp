#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "termin/voxels/voxel_grid.hpp"
#include "termin/assets/handles.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "../../core_c/include/tc_kind.hpp"

namespace py = pybind11;
using namespace termin::voxels;
using namespace termin;

// Helper: numpy array to vector of Vec3
std::vector<Vec3> numpy_to_vec3_vector(py::array_t<double> arr) {
    auto buf = arr.unchecked<2>();
    if (buf.shape(1) != 3) {
        throw std::runtime_error("Expected Nx3 array for vertices");
    }
    std::vector<Vec3> result;
    result.reserve(static_cast<size_t>(buf.shape(0)));
    for (py::ssize_t i = 0; i < buf.shape(0); i++) {
        result.emplace_back(buf(i, 0), buf(i, 1), buf(i, 2));
    }
    return result;
}

// Helper: numpy array to vector of triangles
std::vector<std::tuple<int, int, int>> numpy_to_triangles(py::array_t<int> arr) {
    auto buf = arr.unchecked<2>();
    if (buf.shape(1) != 3) {
        throw std::runtime_error("Expected Mx3 array for triangles");
    }
    std::vector<std::tuple<int, int, int>> result;
    result.reserve(static_cast<size_t>(buf.shape(0)));
    for (py::ssize_t i = 0; i < buf.shape(0); i++) {
        result.emplace_back(buf(i, 0), buf(i, 1), buf(i, 2));
    }
    return result;
}

// Helper: surface normals to dict (list of normals per voxel)
py::dict surface_normals_to_dict(const std::unordered_map<VoxelKey, std::vector<Vec3>, ChunkKeyHash>& normals) {
    py::dict result;
    for (const auto& [key, normal_list] : normals) {
        py::tuple py_key = py::make_tuple(std::get<0>(key), std::get<1>(key), std::get<2>(key));
        py::list py_normals;
        for (const auto& normal : normal_list) {
            py::array_t<double> py_normal(3);
            auto buf = py_normal.mutable_unchecked<1>();
            buf(0) = normal.x;
            buf(1) = normal.y;
            buf(2) = normal.z;
            py_normals.append(py_normal);
        }
        result[py_key] = py_normals;
    }
    return result;
}

PYBIND11_MODULE(_voxels_native, m) {
    m.doc() = "Native C++ voxelization module";

    // Constants
    m.attr("CHUNK_SIZE") = CHUNK_SIZE;
    m.attr("VOXEL_EMPTY") = VOXEL_EMPTY;
    m.attr("VOXEL_SOLID") = VOXEL_SOLID;
    m.attr("VOXEL_SURFACE") = VOXEL_SURFACE;

    // VoxelChunk class
    py::class_<VoxelChunk>(m, "VoxelChunk")
        .def(py::init<>())
        .def("get", &VoxelChunk::get)
        .def("set", &VoxelChunk::set)
        .def("fill", &VoxelChunk::fill)
        .def("clear", &VoxelChunk::clear)
        .def_property_readonly("is_empty", &VoxelChunk::is_empty)
        .def_property_readonly("non_empty_count", &VoxelChunk::non_empty_count)
        .def("iter_non_empty", &VoxelChunk::iter_non_empty)
        .def_property_readonly("data", [](const VoxelChunk& c) {
            // Return as numpy array
            py::array_t<uint8_t> result({CHUNK_SIZE, CHUNK_SIZE, CHUNK_SIZE});
            auto buf = result.mutable_unchecked<3>();
            const auto& data = c.data();
            for (int z = 0; z < CHUNK_SIZE; z++) {
                for (int y = 0; y < CHUNK_SIZE; y++) {
                    for (int x = 0; x < CHUNK_SIZE; x++) {
                        buf(x, y, z) = data[x + y * CHUNK_SIZE + z * CHUNK_SIZE * CHUNK_SIZE];
                    }
                }
            }
            return result;
        })
        .def("serialize", [](const VoxelChunk& c) {
            py::module_ gzip = py::module_::import("gzip");
            py::module_ base64 = py::module_::import("base64");

            // Get raw data as bytes
            const auto& data = c.data();
            py::bytes raw_bytes(reinterpret_cast<const char*>(data.data()), CHUNK_VOLUME);

            // Compress and encode
            py::bytes compressed = gzip.attr("compress")(raw_bytes);
            py::object encoded = base64.attr("b64encode")(compressed).attr("decode")("ascii");

            py::dict result;
            result["data"] = encoded;
            result["count"] = c.non_empty_count();
            return result;
        })
        .def_static("deserialize", [](const py::dict& data) {
            py::module_ gzip = py::module_::import("gzip");
            py::module_ base64 = py::module_::import("base64");

            py::bytes compressed = base64.attr("b64decode")(data["data"]);
            py::bytes raw = gzip.attr("decompress")(compressed);

            std::string raw_str = raw.cast<std::string>();

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
    py::class_<VoxelGrid>(m, "VoxelGrid")
        .def(py::init([](double cell_size, py::object origin, std::string name, std::string source_path) {
            Vec3 o = Vec3::zero();
            if (!origin.is_none()) {
                if (py::isinstance<py::tuple>(origin)) {
                    py::tuple t = origin.cast<py::tuple>();
                    o = Vec3(t[0].cast<double>(), t[1].cast<double>(), t[2].cast<double>());
                } else if (py::isinstance<py::list>(origin)) {
                    py::list l = origin.cast<py::list>();
                    o = Vec3(l[0].cast<double>(), l[1].cast<double>(), l[2].cast<double>());
                } else {
                    // Try numpy array
                    auto arr = origin.cast<py::array_t<double>>();
                    auto buf = arr.unchecked<1>();
                    o = Vec3(buf(0), buf(1), buf(2));
                }
            }
            return VoxelGrid(cell_size, o, name, source_path);
        }),
             py::arg("cell_size") = 0.25,
             py::arg("origin") = py::none(),
             py::arg("name") = "",
             py::arg("source_path") = "")

        // Properties (as Python properties, not methods, for compatibility)
        .def_property_readonly("cell_size", &VoxelGrid::cell_size)
        .def_property_readonly("chunk_count", &VoxelGrid::chunk_count)
        .def_property_readonly("voxel_count", &VoxelGrid::voxel_count)
        .def_property("name",
            [](const VoxelGrid& g) { return g.name(); },
            [](VoxelGrid& g, const std::string& n) { g.set_name(n); })
        .def_property("source_path",
            [](const VoxelGrid& g) { return g.source_path(); },
            [](VoxelGrid& g, const std::string& p) { g.set_source_path(p); })
        .def_property_readonly("origin", [](const VoxelGrid& g) {
            Vec3 o = g.origin();
            py::array_t<double> result(3);
            auto buf = result.mutable_unchecked<1>();
            buf(0) = o.x; buf(1) = o.y; buf(2) = o.z;
            return result;
        })
        .def_property_readonly("surface_normals", [](const VoxelGrid& grid) {
            return surface_normals_to_dict(grid.surface_normals());
        })

        // Voxel access
        .def("get", &VoxelGrid::get)
        .def("set", &VoxelGrid::set)
        .def("clear", &VoxelGrid::clear)

        .def("get_at_world", [](const VoxelGrid& grid, py::array_t<double> pos) {
            auto buf = pos.unchecked<1>();
            return grid.get_at_world(Vec3(buf(0), buf(1), buf(2)));
        })
        .def("set_at_world", [](VoxelGrid& grid, py::array_t<double> pos, uint8_t value) {
            auto buf = pos.unchecked<1>();
            grid.set_at_world(Vec3(buf(0), buf(1), buf(2)), value);
        })

        .def("world_to_voxel", [](const VoxelGrid& grid, py::array_t<double> pos) {
            auto buf = pos.unchecked<1>();
            return grid.world_to_voxel(Vec3(buf(0), buf(1), buf(2)));
        })

        .def("voxel_to_world", [](const VoxelGrid& grid, int vx, int vy, int vz) {
            Vec3 w = grid.voxel_to_world(vx, vy, vz);
            py::array_t<double> result(3);
            auto buf = result.mutable_unchecked<1>();
            buf(0) = w.x; buf(1) = w.y; buf(2) = w.z;
            return result;
        })

        // Chunk access
        .def("get_chunk", [](const VoxelGrid& grid, int cx, int cy, int cz) -> py::object {
            const VoxelChunk* chunk = grid.get_chunk(cx, cy, cz);
            if (!chunk) return py::none();
            // Return copy to avoid dangling pointer issues
            return py::cast(*chunk);
        })
        .def("iter_chunks", [](const VoxelGrid& grid) {
            py::list result;
            for (const auto& [key, chunk_ptr] : grid.iter_chunks()) {
                py::tuple py_key = py::make_tuple(std::get<0>(key), std::get<1>(key), std::get<2>(key));
                result.append(py::make_tuple(py_key, *chunk_ptr));
            }
            return result;
        })

        .def("iter_non_empty", &VoxelGrid::iter_non_empty)

        // Bounds
        .def("bounds", [](const VoxelGrid& grid) -> py::object {
            auto b = grid.bounds();
            if (!b) return py::none();
            auto [min_v, max_v] = *b;
            return py::make_tuple(
                py::make_tuple(std::get<0>(min_v), std::get<1>(min_v), std::get<2>(min_v)),
                py::make_tuple(std::get<0>(max_v), std::get<1>(max_v), std::get<2>(max_v))
            );
        })
        .def("world_bounds", [](const VoxelGrid& grid) -> py::object {
            auto b = grid.world_bounds();
            if (!b) return py::none();
            auto [min_w, max_w] = *b;
            py::array_t<double> min_arr(3), max_arr(3);
            auto buf_min = min_arr.mutable_unchecked<1>();
            auto buf_max = max_arr.mutable_unchecked<1>();
            buf_min(0) = min_w.x; buf_min(1) = min_w.y; buf_min(2) = min_w.z;
            buf_max(0) = max_w.x; buf_max(1) = max_w.y; buf_max(2) = max_w.z;
            return py::make_tuple(min_arr, max_arr);
        })

        // Voxelization
        .def("voxelize_mesh", [](VoxelGrid& grid,
                                  py::array_t<double> vertices,
                                  py::array_t<int> triangles,
                                  uint8_t voxel_type) {
            auto verts = numpy_to_vec3_vector(vertices);
            auto tris = numpy_to_triangles(triangles);
            return grid.voxelize_mesh(verts, tris, voxel_type);
        }, py::arg("vertices"), py::arg("triangles"), py::arg("voxel_type") = VOXEL_SOLID)

        .def("fill_interior", &VoxelGrid::fill_interior,
             py::arg("fill_value") = VOXEL_SOLID)

        .def("mark_surface", &VoxelGrid::mark_surface,
             py::arg("surface_value") = VOXEL_SURFACE)

        .def("clear_by_type", &VoxelGrid::clear_by_type,
             py::arg("type_to_clear") = VOXEL_SOLID)

        .def("extract_surface", &VoxelGrid::extract_surface,
             py::arg("surface_value") = VOXEL_SOLID)

        // Surface normals
        .def("compute_surface_normals", [](VoxelGrid& grid,
                                           py::array_t<double> vertices,
                                           py::array_t<int> triangles) {
            auto verts = numpy_to_vec3_vector(vertices);
            auto tris = numpy_to_triangles(triangles);
            return grid.compute_surface_normals(verts, tris);
        })

        .def("get_surface_normal", [](const VoxelGrid& grid, int vx, int vy, int vz) -> py::object {
            if (!grid.has_surface_normal(vx, vy, vz)) {
                return py::none();
            }
            Vec3 n = grid.get_surface_normal(vx, vy, vz);
            py::array_t<double> result(3);
            auto buf = result.mutable_unchecked<1>();
            buf(0) = n.x; buf(1) = n.y; buf(2) = n.z;
            return result;
        })

        .def("get_surface_normals", [](const VoxelGrid& grid, int vx, int vy, int vz) -> py::object {
            const auto& normals = grid.get_surface_normals(vx, vy, vz);
            if (normals.empty()) return py::none();
            py::list result;
            for (const auto& n : normals) {
                py::array_t<double> arr(3);
                auto buf = arr.mutable_unchecked<1>();
                buf(0) = n.x; buf(1) = n.y; buf(2) = n.z;
                result.append(arr);
            }
            return result;
        })

        .def("has_surface_normal", &VoxelGrid::has_surface_normal)

        .def("add_surface_normal", [](VoxelGrid& grid, int vx, int vy, int vz, py::array_t<double> normal) {
            auto buf = normal.unchecked<1>();
            grid.add_surface_normal(vx, vy, vz, Vec3(buf(0), buf(1), buf(2)));
        })

        .def("set_surface_normals", [](VoxelGrid& grid, int vx, int vy, int vz, py::list normals) {
            std::vector<Vec3> vec_normals;
            for (auto item : normals) {
                py::array_t<double> arr = item.cast<py::array_t<double>>();
                auto buf = arr.unchecked<1>();
                vec_normals.emplace_back(buf(0), buf(1), buf(2));
            }
            grid.set_surface_normals(vx, vy, vz, vec_normals);
        })

        // Serialization
        .def("serialize", [](const VoxelGrid& grid) {
            if (!grid.source_path().empty()) {
                py::dict result;
                result["type"] = "path";
                result["path"] = grid.source_path();
                return result;
            }
            // Inline serialization
            py::dict result;
            result["type"] = "inline";
            Vec3 o = grid.origin();
            result["origin"] = py::make_tuple(o.x, o.y, o.z);
            result["cell_size"] = grid.cell_size();

            py::dict chunks_dict;
            for (const auto& [key, chunk_ptr] : grid.iter_chunks()) {
                int cx = std::get<0>(key);
                int cy = std::get<1>(key);
                int cz = std::get<2>(key);
                std::string key_str = std::to_string(cx) + "," + std::to_string(cy) + "," + std::to_string(cz);

                // Serialize chunk
                py::module_ gzip = py::module_::import("gzip");
                py::module_ base64 = py::module_::import("base64");
                const auto& data = chunk_ptr->data();
                py::bytes raw_bytes(reinterpret_cast<const char*>(data.data()), CHUNK_VOLUME);
                py::bytes compressed = gzip.attr("compress")(raw_bytes);
                py::object encoded = base64.attr("b64encode")(compressed).attr("decode")("ascii");

                py::dict chunk_data;
                chunk_data["data"] = encoded;
                chunk_data["count"] = chunk_ptr->non_empty_count();
                chunks_dict[py::str(key_str)] = chunk_data;
            }
            result["chunks"] = chunks_dict;
            return result;
        })
        .def("direct_serialize", [](const VoxelGrid& grid) {
            py::dict result;
            result["type"] = "inline";
            Vec3 o = grid.origin();
            result["origin"] = py::make_tuple(o.x, o.y, o.z);
            result["cell_size"] = grid.cell_size();

            py::dict chunks_dict;
            for (const auto& [key, chunk_ptr] : grid.iter_chunks()) {
                int cx = std::get<0>(key);
                int cy = std::get<1>(key);
                int cz = std::get<2>(key);
                std::string key_str = std::to_string(cx) + "," + std::to_string(cy) + "," + std::to_string(cz);

                py::module_ gzip = py::module_::import("gzip");
                py::module_ base64 = py::module_::import("base64");
                const auto& data = chunk_ptr->data();
                py::bytes raw_bytes(reinterpret_cast<const char*>(data.data()), CHUNK_VOLUME);
                py::bytes compressed = gzip.attr("compress")(raw_bytes);
                py::object encoded = base64.attr("b64encode")(compressed).attr("decode")("ascii");

                py::dict chunk_data;
                chunk_data["data"] = encoded;
                chunk_data["count"] = chunk_ptr->non_empty_count();
                chunks_dict[py::str(key_str)] = chunk_data;
            }
            result["chunks"] = chunks_dict;
            return result;
        })
        .def_static("deserialize", [](const py::dict& data) {
            py::object origin_obj = data["origin"];
            py::tuple origin_tuple = origin_obj.cast<py::tuple>();
            Vec3 origin(
                origin_tuple[0].cast<double>(),
                origin_tuple[1].cast<double>(),
                origin_tuple[2].cast<double>()
            );
            double cell_size = data["cell_size"].cast<double>();
            std::string source_path = data.contains("path") ? data["path"].cast<std::string>() : "";

            VoxelGrid grid(cell_size, origin, "", source_path);

            if (data.contains("chunks")) {
                py::dict chunks_dict = data["chunks"].cast<py::dict>();
                py::module_ gzip = py::module_::import("gzip");
                py::module_ base64 = py::module_::import("base64");

                for (auto item : chunks_dict) {
                    std::string key_str = item.first.cast<std::string>();
                    py::dict chunk_data = item.second.cast<py::dict>();

                    // Parse key "cx,cy,cz"
                    size_t pos1 = key_str.find(',');
                    size_t pos2 = key_str.find(',', pos1 + 1);
                    int cx = std::stoi(key_str.substr(0, pos1));
                    int cy = std::stoi(key_str.substr(pos1 + 1, pos2 - pos1 - 1));
                    int cz = std::stoi(key_str.substr(pos2 + 1));

                    // Deserialize chunk data
                    py::bytes compressed = base64.attr("b64decode")(chunk_data["data"]);
                    py::bytes raw = gzip.attr("decompress")(compressed);
                    std::string raw_str = raw.cast<std::string>();

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
        .def_static("direct_deserialize", [](const py::dict& data) {
            // Same as deserialize
            py::object origin_obj = data["origin"];
            py::tuple origin_tuple = origin_obj.cast<py::tuple>();
            Vec3 origin(
                origin_tuple[0].cast<double>(),
                origin_tuple[1].cast<double>(),
                origin_tuple[2].cast<double>()
            );
            double cell_size = data["cell_size"].cast<double>();
            std::string source_path = data.contains("path") ? data["path"].cast<std::string>() : "";

            VoxelGrid grid(cell_size, origin, "", source_path);

            if (data.contains("chunks")) {
                py::dict chunks_dict = data["chunks"].cast<py::dict>();
                py::module_ gzip = py::module_::import("gzip");
                py::module_ base64 = py::module_::import("base64");

                for (auto item : chunks_dict) {
                    std::string key_str = item.first.cast<std::string>();
                    py::dict chunk_data = item.second.cast<py::dict>();

                    size_t pos1 = key_str.find(',');
                    size_t pos2 = key_str.find(',', pos1 + 1);
                    int cx = std::stoi(key_str.substr(0, pos1));
                    int cy = std::stoi(key_str.substr(pos1 + 1, pos2 - pos1 - 1));
                    int cz = std::stoi(key_str.substr(pos2 + 1));

                    py::bytes compressed = base64.attr("b64decode")(chunk_data["data"]);
                    py::bytes raw = gzip.attr("decompress")(compressed);
                    std::string raw_str = raw.cast<std::string>();

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
    py::class_<VoxelGridHandle>(m, "VoxelGridHandle")
        .def(py::init<>())
        .def(py::init<py::object>(), py::arg("asset"))
        .def_static("from_name", &VoxelGridHandle::from_name, py::arg("name"))
        .def_static("from_asset", &VoxelGridHandle::from_asset, py::arg("asset"))
        .def_static("from_uuid", &VoxelGridHandle::from_uuid, py::arg("uuid"))
        .def_static("deserialize", &VoxelGridHandle::deserialize, py::arg("data"))
        .def_readwrite("asset", &VoxelGridHandle::asset)
        .def_property_readonly("is_valid", &VoxelGridHandle::is_valid)
        .def_property_readonly("name", &VoxelGridHandle::name)
        .def_property_readonly("grid", &VoxelGridHandle::grid)
        .def_property_readonly("version", &VoxelGridHandle::version)
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
        py::cpp_function([](py::object obj) -> py::object {
            VoxelGridHandle handle = obj.cast<VoxelGridHandle>();
            return handle.serialize();
        }),
        // deserialize
        py::cpp_function([](py::object data) -> py::object {
            // Handle UUID string
            if (py::isinstance<py::str>(data)) {
                return py::cast(VoxelGridHandle::from_uuid(data.cast<std::string>()));
            }
            // Handle dict format
            if (py::isinstance<py::dict>(data)) {
                py::dict d = data.cast<py::dict>();
                return py::cast(VoxelGridHandle::deserialize(d));
            }
            return py::cast(VoxelGridHandle());
        }),
        // convert
        py::cpp_function([](py::object value) -> py::object {
            if (value.is_none()) {
                return py::cast(VoxelGridHandle());
            }
            if (py::isinstance<VoxelGridHandle>(value)) {
                return value;
            }
            return value;
        })
    );

    // Standalone function for testing
    m.def("triangle_aabb_intersect", [](
        py::array_t<double> v0,
        py::array_t<double> v1,
        py::array_t<double> v2,
        py::array_t<double> center,
        py::array_t<double> half_size
    ) {
        auto b0 = v0.unchecked<1>();
        auto b1 = v1.unchecked<1>();
        auto b2 = v2.unchecked<1>();
        auto bc = center.unchecked<1>();
        auto bh = half_size.unchecked<1>();

        return triangle_aabb_intersect(
            Vec3(b0(0), b0(1), b0(2)),
            Vec3(b1(0), b1(1), b1(2)),
            Vec3(b2(0), b2(1), b2(2)),
            Vec3(bc(0), bc(1), bc(2)),
            Vec3(bh(0), bh(1), bh(2))
        );
    });
}
