// Python bindings for CpuMesh3 - pure CPU triangle mesh

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include "termin/mesh/cpu_mesh3.hpp"

namespace nb = nanobind;
using namespace termin;

// Helper to create 2D numpy array from data
template<typename T>
static nb::object make_array_2d(const T* data, size_t rows, size_t cols) {
    T* buf = new T[rows * cols];
    for (size_t i = 0; i < rows * cols; i++) {
        buf[i] = data[i];
    }
    nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<T*>(p); });
    size_t shape[2] = {rows, cols};
    return nb::cast(nb::ndarray<nb::numpy, T>(buf, 2, shape, owner));
}

void bind_cpu_mesh3(nb::module_& m) {
    // New pure CPU mesh class - will eventually replace old Mesh3
    nb::class_<CpuMesh3>(m, "CpuMesh3")
        .def(nb::init<>())

        // Constructor: vertices, triangles, uvs, normals, name, uuid
        .def("__init__", [](CpuMesh3* self,
                           nb::ndarray<float, nb::c_contig, nb::device::cpu> vertices,
                           nb::ndarray<uint32_t, nb::c_contig, nb::device::cpu> triangles,
                           nb::object uvs_obj,
                           nb::object normals_obj,
                           std::string name,
                           std::string uuid) {
            new (self) CpuMesh3();
            self->name = std::move(name);
            self->uuid = std::move(uuid);

            // Vertices (Nx3)
            size_t num_verts = vertices.shape(0);
            float* v_ptr = vertices.data();
            self->vertices.resize(num_verts);
            for (size_t i = 0; i < num_verts; i++) {
                self->vertices[i] = Vec3f(v_ptr[i*3], v_ptr[i*3+1], v_ptr[i*3+2]);
            }

            // Triangles (Mx3) -> flat indices
            size_t num_tris = triangles.shape(0);
            uint32_t* t_ptr = triangles.data();
            self->triangles.resize(num_tris * 3);
            for (size_t i = 0; i < num_tris * 3; i++) {
                self->triangles[i] = t_ptr[i];
            }

            // Optional UVs (Nx2)
            if (!uvs_obj.is_none()) {
                auto uv_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(uvs_obj);
                float* uv_ptr = uv_arr.data();
                size_t n = uv_arr.shape(0);
                self->uvs.resize(n);
                for (size_t i = 0; i < n; i++) {
                    self->uvs[i] = Vec2f(uv_ptr[i*2], uv_ptr[i*2+1]);
                }
            }

            // Optional normals (Nx3)
            if (!normals_obj.is_none()) {
                auto n_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(normals_obj);
                float* n_ptr = n_arr.data();
                size_t n = n_arr.shape(0);
                self->normals.resize(n);
                for (size_t i = 0; i < n; i++) {
                    self->normals[i] = Vec3f(n_ptr[i*3], n_ptr[i*3+1], n_ptr[i*3+2]);
                }
            }
        },
             nb::arg("vertices"),
             nb::arg("triangles"),
             nb::arg("uvs") = nb::none(),
             nb::arg("vertex_normals") = nb::none(),
             nb::arg("name") = "",
             nb::arg("uuid") = "")

        // Properties
        .def_prop_ro("vertices", [](const CpuMesh3& m) {
            size_t n = m.vertices.size();
            std::vector<float> flat(n * 3);
            for (size_t i = 0; i < n; i++) {
                flat[i*3] = m.vertices[i].x;
                flat[i*3+1] = m.vertices[i].y;
                flat[i*3+2] = m.vertices[i].z;
            }
            return make_array_2d(flat.data(), n, 3);
        })

        .def_prop_ro("triangles", [](const CpuMesh3& m) {
            size_t n = m.triangle_count();
            return make_array_2d(m.triangles.data(), n, 3);
        })

        .def_prop_ro("indices", [](const CpuMesh3& m) {
            size_t n = m.triangle_count();
            return make_array_2d(m.triangles.data(), n, 3);
        })

        .def_prop_ro("uvs", [](const CpuMesh3& m) -> nb::object {
            if (!m.has_uvs()) return nb::none();
            size_t n = m.uvs.size();
            std::vector<float> flat(n * 2);
            for (size_t i = 0; i < n; i++) {
                flat[i*2] = m.uvs[i].x;
                flat[i*2+1] = m.uvs[i].y;
            }
            return make_array_2d(flat.data(), n, 2);
        })

        .def_prop_ro("vertex_normals", [](const CpuMesh3& m) -> nb::object {
            if (!m.has_normals()) return nb::none();
            size_t n = m.normals.size();
            std::vector<float> flat(n * 3);
            for (size_t i = 0; i < n; i++) {
                flat[i*3] = m.normals[i].x;
                flat[i*3+1] = m.normals[i].y;
                flat[i*3+2] = m.normals[i].z;
            }
            return make_array_2d(flat.data(), n, 3);
        })

        .def_prop_ro("name", [](const CpuMesh3& m) { return m.name; })
        .def_prop_ro("uuid", [](const CpuMesh3& m) { return m.uuid; })
        .def_prop_ro("type", [](const CpuMesh3&) { return "triangles"; })

        // Query methods
        .def("is_valid", &CpuMesh3::is_valid)
        .def("has_uvs", &CpuMesh3::has_uvs)
        .def("has_vertex_normals", &CpuMesh3::has_normals)
        .def("get_vertex_count", &CpuMesh3::vertex_count)
        .def("get_face_count", &CpuMesh3::triangle_count)
        .def_prop_ro("vertex_count", &CpuMesh3::vertex_count)
        .def_prop_ro("triangle_count", &CpuMesh3::triangle_count)

        // Transformations
        .def("translate", [](CpuMesh3& m, nb::ndarray<float, nb::c_contig, nb::device::cpu> offset) {
            float* ptr = offset.data();
            m.translate(ptr[0], ptr[1], ptr[2]);
        }, nb::arg("offset"))

        .def("scale", [](CpuMesh3& m, float factor) {
            m.scale(factor);
        }, nb::arg("factor"))

        // Compute normals
        .def("compute_vertex_normals", [](CpuMesh3& m) {
            m.compute_normals();
            if (!m.has_normals()) return nb::none();
            size_t n = m.normals.size();
            std::vector<float> flat(n * 3);
            for (size_t i = 0; i < n; i++) {
                flat[i*3] = m.normals[i].x;
                flat[i*3+1] = m.normals[i].y;
                flat[i*3+2] = m.normals[i].z;
            }
            return make_array_2d(flat.data(), n, 3);
        })

        // Copy
        .def("copy", [](const CpuMesh3& m, std::string new_name) {
            return m.copy(new_name);
        }, nb::arg("name") = "")

        // Repr
        .def("__repr__", [](const CpuMesh3& m) {
            return "<Mesh3 vertices=" + std::to_string(m.vertex_count()) +
                   " triangles=" + std::to_string(m.triangle_count()) +
                   " name=\"" + m.name + "\">";
        });
}
