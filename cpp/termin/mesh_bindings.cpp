#include "mesh_bindings.hpp"

#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/optional.h>
#include <optional>

#include "termin/mesh/mesh3.hpp"
#include "termin/mesh/tc_mesh_handle.hpp"

namespace nb = nanobind;

namespace termin {

// Helper: create 2D numpy array of floats
template<typename T>
nb::object make_array_2d(const T* data, size_t rows, size_t cols) {
    T* buf = new T[rows * cols];
    for (size_t i = 0; i < rows * cols; ++i) {
        buf[i] = data[i];
    }
    nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<T*>(p); });
    size_t shape[2] = {rows, cols};
    return nb::cast(nb::ndarray<nb::numpy, T>(buf, 2, shape, owner));
}

// Helper: create 1D numpy array
template<typename T>
nb::object make_array_1d(const T* data, size_t size) {
    T* buf = new T[size];
    for (size_t i = 0; i < size; ++i) {
        buf[i] = data[i];
    }
    nb::capsule owner(buf, [](void* p) noexcept { delete[] static_cast<T*>(p); });
    return nb::cast(nb::ndarray<nb::numpy, T>(buf, {size}, owner));
}

void bind_mesh(nb::module_& m) {
    // =========================================================================
    // Mesh3 - Pure CPU mesh (vertices, triangles, normals, uvs)
    // Does NOT register in tc_mesh registry - that's TcMesh's job.
    // uuid field is a hint for TcMesh creation.
    // =========================================================================
    nb::class_<Mesh3>(m, "Mesh3")
        .def(nb::init<>())
        .def("__init__", [](Mesh3* self,
                           nb::ndarray<float, nb::c_contig, nb::device::cpu> vertices,
                           nb::ndarray<uint32_t, nb::c_contig, nb::device::cpu> triangles,
                           nb::object uvs_obj,
                           nb::object normals_obj,
                           std::string name,
                           std::string uuid) {
            size_t num_verts = vertices.shape(0);
            float* v_ptr = vertices.data();

            std::vector<Vec3f> verts(num_verts);
            for (size_t i = 0; i < num_verts; ++i) {
                verts[i] = Vec3f(v_ptr[i * 3], v_ptr[i * 3 + 1], v_ptr[i * 3 + 2]);
            }

            size_t num_tris = triangles.shape(0);
            uint32_t* t_ptr = triangles.data();

            std::vector<uint32_t> tris(num_tris * 3);
            for (size_t i = 0; i < num_tris * 3; ++i) {
                tris[i] = t_ptr[i];
            }

            new (self) Mesh3(std::move(verts), std::move(tris), name, uuid);

            // Optional normals
            if (!normals_obj.is_none()) {
                auto n_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(normals_obj);
                float* n_ptr = n_arr.data();
                size_t n = n_arr.shape(0);
                self->normals.resize(n);
                for (size_t i = 0; i < n; ++i) {
                    self->normals[i] = Vec3f(n_ptr[i * 3], n_ptr[i * 3 + 1], n_ptr[i * 3 + 2]);
                }
            }

            // Optional UVs
            if (!uvs_obj.is_none()) {
                auto uv_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(uvs_obj);
                float* uv_ptr = uv_arr.data();
                size_t n = uv_arr.shape(0);
                self->uvs.resize(n);
                for (size_t i = 0; i < n; ++i) {
                    self->uvs[i] = Vec2f(uv_ptr[i * 2], uv_ptr[i * 2 + 1]);
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
        .def_prop_ro("vertices", [](const Mesh3& m) {
            size_t n = m.vertices.size();
            std::vector<float> flat(n * 3);
            for (size_t i = 0; i < n; ++i) {
                flat[i * 3] = m.vertices[i].x;
                flat[i * 3 + 1] = m.vertices[i].y;
                flat[i * 3 + 2] = m.vertices[i].z;
            }
            return make_array_2d(flat.data(), n, 3);
        })

        .def_prop_ro("triangles", [](const Mesh3& m) {
            size_t n = m.triangles.size() / 3;
            return make_array_2d(m.triangles.data(), n, 3);
        })

        .def_prop_ro("vertex_normals", [](const Mesh3& m) -> nb::object {
            if (m.normals.empty()) return nb::none();
            size_t n = m.normals.size();
            std::vector<float> flat(n * 3);
            for (size_t i = 0; i < n; ++i) {
                flat[i * 3] = m.normals[i].x;
                flat[i * 3 + 1] = m.normals[i].y;
                flat[i * 3 + 2] = m.normals[i].z;
            }
            return make_array_2d(flat.data(), n, 3);
        })

        .def_prop_ro("uvs", [](const Mesh3& m) -> nb::object {
            if (m.uvs.empty()) return nb::none();
            size_t n = m.uvs.size();
            std::vector<float> flat(n * 2);
            for (size_t i = 0; i < n; ++i) {
                flat[i * 2] = m.uvs[i].x;
                flat[i * 2 + 1] = m.uvs[i].y;
            }
            return make_array_2d(flat.data(), n, 2);
        })

        .def_prop_rw("name",
            [](const Mesh3& m) { return m.name; },
            [](Mesh3& m, const std::string& n) { m.name = n; })

        .def_prop_rw("uuid",
            [](const Mesh3& m) { return m.uuid; },
            [](Mesh3& m, const std::string& u) { m.uuid = u; })

        .def_prop_ro("vertex_count", &Mesh3::vertex_count)
        .def_prop_ro("triangle_count", &Mesh3::triangle_count)

        // Methods
        .def("is_valid", &Mesh3::is_valid)
        .def("has_normals", &Mesh3::has_normals)
        .def("has_uvs", &Mesh3::has_uvs)
        .def("compute_normals", &Mesh3::compute_normals)

        .def("translate", [](Mesh3& m, float x, float y, float z) {
            m.translate(x, y, z);
        }, nb::arg("x"), nb::arg("y"), nb::arg("z"))

        .def("scale", [](Mesh3& m, float factor) {
            m.scale(factor);
        }, nb::arg("factor"))

        .def("copy", &Mesh3::copy, nb::arg("new_name") = "")

        .def("__repr__", [](const Mesh3& m) {
            return "<Mesh3 vertices=" + std::to_string(m.vertex_count()) +
                   " triangles=" + std::to_string(m.triangle_count()) +
                   " name=\"" + m.name + "\"" +
                   " uuid=\"" + m.uuid + "\">";
        });

    // =========================================================================
    // TcMesh - GPU-ready mesh registered in tc_mesh C registry
    // =========================================================================
    nb::enum_<tc_attrib_type>(m, "TcAttribType")
        .value("FLOAT32", TC_ATTRIB_FLOAT32)
        .value("INT32", TC_ATTRIB_INT32)
        .value("UINT32", TC_ATTRIB_UINT32)
        .value("INT16", TC_ATTRIB_INT16)
        .value("UINT16", TC_ATTRIB_UINT16)
        .value("INT8", TC_ATTRIB_INT8)
        .value("UINT8", TC_ATTRIB_UINT8);

    nb::class_<tc_vertex_layout>(m, "TcVertexLayout")
        .def("__init__", [](tc_vertex_layout* self) {
            new (self) tc_vertex_layout();
            tc_vertex_layout_init(self);
        })
        .def_ro("stride", &tc_vertex_layout::stride)
        .def_ro("attrib_count", &tc_vertex_layout::attrib_count)
        .def("add", [](tc_vertex_layout& self, const std::string& name, uint8_t size, tc_attrib_type type) {
            return tc_vertex_layout_add(&self, name.c_str(), size, type);
        }, nb::arg("name"), nb::arg("size"), nb::arg("type"))
        .def("find", [](const tc_vertex_layout& self, const std::string& name) -> nb::object {
            const tc_vertex_attrib* attr = tc_vertex_layout_find(&self, name.c_str());
            if (!attr) return nb::none();
            nb::dict d;
            d["name"] = std::string(attr->name);
            d["size"] = attr->size;
            d["type"] = static_cast<tc_attrib_type>(attr->type);
            d["offset"] = attr->offset;
            return d;
        }, nb::arg("name"))
        .def_static("pos_normal_uv", []() { return tc_vertex_layout_pos_normal_uv(); })
        .def_static("pos_normal_uv_color", []() { return tc_vertex_layout_pos_normal_uv_color(); })
        .def_static("skinned", []() { return tc_vertex_layout_skinned(); });

    // Raw tc_mesh struct binding (for internal use)
    nb::class_<tc_mesh>(m, "TcMeshData")
        .def_ro("vertex_count", &tc_mesh::vertex_count)
        .def_ro("index_count", &tc_mesh::index_count)
        .def_ro("version", &tc_mesh::version)
        .def_ro("ref_count", &tc_mesh::ref_count)
        .def_prop_ro("uuid", [](const tc_mesh& m) { return std::string(m.uuid); })
        .def_prop_ro("name", [](const tc_mesh& m) { return m.name ? std::string(m.name) : ""; })
        .def_prop_ro("stride", [](const tc_mesh& m) { return m.layout.stride; })
        .def_prop_ro("layout", [](const tc_mesh& m) { return m.layout; })
        .def("get_vertices_buffer", [](const tc_mesh& m) -> nb::object {
            if (!m.vertices || m.vertex_count == 0) return nb::none();
            size_t total_floats = (m.vertex_count * m.layout.stride) / sizeof(float);
            return make_array_1d((const float*)m.vertices, total_floats);
        })
        .def("get_indices_buffer", [](const tc_mesh& m) -> nb::object {
            if (!m.indices || m.index_count == 0) return nb::none();
            return make_array_1d(m.indices, m.index_count);
        });

    // TcMesh - GPU-ready mesh wrapper
    nb::class_<TcMesh>(m, "TcMesh")
        .def(nb::init<>())
        .def_prop_ro("is_valid", &TcMesh::is_valid)
        .def_prop_ro("uuid", &TcMesh::uuid)
        .def_prop_ro("name", &TcMesh::name)
        .def_prop_ro("version", &TcMesh::version)
        .def_prop_ro("vertex_count", &TcMesh::vertex_count)
        .def_prop_ro("index_count", &TcMesh::index_count)
        .def_prop_ro("triangle_count", &TcMesh::triangle_count)
        .def_prop_ro("stride", &TcMesh::stride)
        .def_prop_ro("mesh", [](const TcMesh& h) -> nb::object {
            if (!h.mesh) return nb::none();
            return nb::cast(h.mesh, nb::rv_policy::reference);
        })
        .def("bump_version", &TcMesh::bump_version)
        .def("get_vertices_buffer", [](const TcMesh& h) -> nb::object {
            if (!h.mesh || !h.mesh->vertices || h.mesh->vertex_count == 0) return nb::none();
            size_t total_floats = (h.mesh->vertex_count * h.mesh->layout.stride) / sizeof(float);
            return make_array_1d((const float*)h.mesh->vertices, total_floats);
        })
        .def("get_indices_buffer", [](const TcMesh& h) -> nb::object {
            if (!h.mesh || !h.mesh->indices || h.mesh->index_count == 0) return nb::none();
            return make_array_1d(h.mesh->indices, h.mesh->index_count);
        })
        .def_static("from_mesh3", [](const Mesh3& mesh, std::string name) {
            return TcMesh::from_mesh3(mesh, name);
        }, nb::arg("mesh"), nb::arg("name") = "")
        .def_static("from_interleaved", [](
                nb::ndarray<nb::c_contig, nb::device::cpu> vertices,
                size_t vertex_count,
                nb::ndarray<uint32_t, nb::c_contig, nb::device::cpu> indices,
                const tc_vertex_layout& layout,
                std::string name,
                std::string uuid_hint) {
            return TcMesh::from_interleaved(
                vertices.data(), vertex_count,
                indices.data(), indices.size(),
                layout, name, uuid_hint);
        }, nb::arg("vertices"), nb::arg("vertex_count"), nb::arg("indices"),
           nb::arg("layout"), nb::arg("name") = "", nb::arg("uuid") = "")
        .def_static("from_uuid", &TcMesh::from_uuid, nb::arg("uuid"))
        .def_static("get_or_create", &TcMesh::get_or_create, nb::arg("uuid"))
        .def_static("from_name", [](const std::string& name) {
            tc_mesh* m = tc_mesh_get_by_name(name.c_str());
            return m ? TcMesh(m) : TcMesh();
        }, nb::arg("name"))
        .def_static("list_all_names", []() {
            std::vector<std::string> names;
            tc_mesh_foreach([](const tc_mesh* mesh, void* user_data) -> bool {
                auto* vec = static_cast<std::vector<std::string>*>(user_data);
                if (mesh && mesh->name) {
                    vec->push_back(mesh->name);
                }
                return true;
            }, &names);
            return names;
        })
        .def("__repr__", [](const TcMesh& h) {
            if (!h.mesh) return std::string("<TcMesh invalid>");
            return "<TcMesh vertices=" + std::to_string(h.mesh->vertex_count) +
                   " triangles=" + std::to_string(h.mesh->index_count / 3) +
                   " uuid=" + std::string(h.mesh->uuid) + ">";
        });

    // Alias for backward compatibility
    m.attr("TcMeshHandle") = m.attr("TcMesh");

    // =========================================================================
    // Module-level functions
    // =========================================================================
    m.def("tc_mesh_compute_uuid", [](nb::ndarray<float, nb::c_contig, nb::device::cpu> vertices,
                                      nb::ndarray<uint32_t, nb::c_contig, nb::device::cpu> indices) {
        char uuid[40];
        tc_mesh_compute_uuid(vertices.data(), vertices.size() * sizeof(float),
                            indices.data(), indices.size(), uuid);
        return std::string(uuid);
    }, nb::arg("vertices"), nb::arg("indices"),
       "Compute UUID from vertex and index data (hash-based)");

    m.def("tc_mesh_get", [](const std::string& uuid) -> std::optional<TcMesh> {
        tc_mesh* mesh = tc_mesh_get(uuid.c_str());
        if (!mesh) return std::nullopt;
        return TcMesh(mesh);
    }, nb::arg("uuid"),
       "Get existing mesh by UUID (returns None if not found)");

    m.def("tc_mesh_get_or_create", [](const std::string& uuid) {
        tc_mesh* mesh = tc_mesh_get_or_create(uuid.c_str());
        return TcMesh(mesh);
    }, nb::arg("uuid"),
       "Get existing mesh or create new one");

    m.def("tc_mesh_set_data", [](TcMesh& handle,
                                  nb::ndarray<float, nb::c_contig, nb::device::cpu> vertices, size_t vertex_count,
                                  const tc_vertex_layout& layout,
                                  nb::ndarray<uint32_t, nb::c_contig, nb::device::cpu> indices,
                                  const std::string& name) {
        if (!handle.mesh) return false;
        return tc_mesh_set_data(handle.mesh,
                               vertices.data(), vertex_count, &layout,
                               indices.data(), indices.size(),
                               name.empty() ? nullptr : name.c_str());
    }, nb::arg("handle"), nb::arg("vertices"),
       nb::arg("vertex_count"), nb::arg("layout"), nb::arg("indices"),
       nb::arg("name") = "",
       "Set mesh vertex and index data");

    m.def("tc_mesh_contains", [](const std::string& uuid) {
        return tc_mesh_contains(uuid.c_str());
    }, nb::arg("uuid"), "Check if mesh exists in registry");

    m.def("tc_mesh_count", []() {
        return tc_mesh_count();
    }, "Get number of meshes in registry");

    m.def("tc_mesh_get_all_info", []() {
        nb::list result;
        size_t count = 0;
        tc_mesh_info* infos = tc_mesh_get_all_info(&count);
        if (infos) {
            for (size_t i = 0; i < count; ++i) {
                nb::dict d;
                d["uuid"] = std::string(infos[i].uuid);
                d["name"] = infos[i].name ? std::string(infos[i].name) : "";
                d["ref_count"] = infos[i].ref_count;
                d["version"] = infos[i].version;
                d["vertex_count"] = infos[i].vertex_count;
                d["index_count"] = infos[i].index_count;
                d["stride"] = infos[i].stride;
                d["memory_bytes"] = infos[i].memory_bytes;
                result.append(d);
            }
            free(infos);
        }
        return result;
    }, "Get info for all meshes in registry");
}

} // namespace termin
