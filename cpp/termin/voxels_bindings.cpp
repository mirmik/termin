#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "termin/voxels/voxel_grid.hpp"

namespace py = pybind11;
using namespace termin::voxels;
using namespace termin::geom;

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

    // VoxelGrid class
    py::class_<VoxelGrid>(m, "VoxelGrid")
        .def(py::init<double, Vec3>(),
             py::arg("cell_size") = 0.25,
             py::arg("origin") = Vec3::zero())

        .def("cell_size", &VoxelGrid::cell_size)
        .def("chunk_count", &VoxelGrid::chunk_count)
        .def("voxel_count", &VoxelGrid::voxel_count)

        .def("get", &VoxelGrid::get)
        .def("set", &VoxelGrid::set)
        .def("clear", &VoxelGrid::clear)

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

        .def("iter_non_empty", &VoxelGrid::iter_non_empty)

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

        .def("compute_surface_normals", [](VoxelGrid& grid,
                                           py::array_t<double> vertices,
                                           py::array_t<int> triangles) {
            auto verts = numpy_to_vec3_vector(vertices);
            auto tris = numpy_to_triangles(triangles);
            return grid.compute_surface_normals(verts, tris);
        })

        .def("surface_normals", [](const VoxelGrid& grid) {
            return surface_normals_to_dict(grid.surface_normals());
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

        .def("has_surface_normal", &VoxelGrid::has_surface_normal);

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
