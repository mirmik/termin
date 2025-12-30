#include "mesh_bindings.hpp"

#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/optional.h>
#include <optional>

#include "termin/mesh/custom_mesh.hpp"
#include "termin/mesh/mesh3.hpp"
#include "termin/mesh/skinned_mesh3.hpp"

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
    // CustomMesh - base class for all mesh types
    nb::class_<CustomMesh>(m, "CustomMesh")
        .def(nb::init<>())
        .def("is_valid", &CustomMesh::is_valid)
        .def_prop_ro("uuid", [](const CustomMesh& m) { return std::string(m.uuid()); })
        .def_prop_ro("name", [](const CustomMesh& m) { return std::string(m.name()); })
        .def_prop_ro("vertex_count", &CustomMesh::vertex_count)
        .def_prop_ro("index_count", &CustomMesh::index_count)
        .def_prop_ro("triangle_count", &CustomMesh::triangle_count)
        .def_prop_ro("version", &CustomMesh::version)
        .def_prop_ro("tc_mesh", [](const CustomMesh& m) { return m.raw(); }, nb::rv_policy::reference)
        .def("has_attribute", &CustomMesh::has_attribute, nb::arg("name"))
        .def("get_indices", &CustomMesh::get_indices)
        .def("bump_version", &CustomMesh::bump_version)
        .def_prop_rw("source_path",
            [](const CustomMesh&) -> std::string {
                throw std::runtime_error("source_path is not supported for technical reasons");
            },
            [](CustomMesh&, const std::string&) {
                throw std::runtime_error("source_path is not supported for technical reasons");
            });

    // Mesh3 - triangle mesh with pos, normal, uv
    nb::class_<Mesh3, CustomMesh>(m, "Mesh3")
        .def(nb::init<>())
        .def("__init__", [](Mesh3* self,
                           nb::ndarray<float, nb::c_contig, nb::device::cpu> vertices,
                           nb::ndarray<uint32_t, nb::c_contig, nb::device::cpu> triangles,
                           nb::object uvs_obj, nb::object normals_obj,
                           std::string name) {
            // Get vertex data (Nx3)
            size_t num_verts = vertices.shape(0);
            float* v_ptr = vertices.data();

            std::vector<float> verts_flat(num_verts * 3);
            for (size_t i = 0; i < num_verts; ++i) {
                verts_flat[i * 3] = v_ptr[i * 3];
                verts_flat[i * 3 + 1] = v_ptr[i * 3 + 1];
                verts_flat[i * 3 + 2] = v_ptr[i * 3 + 2];
            }

            // Get triangle data (Mx3)
            size_t num_tris = triangles.shape(0);
            uint32_t* t_ptr = triangles.data();

            std::vector<uint32_t> tris_flat(num_tris * 3);
            for (size_t i = 0; i < num_tris; ++i) {
                tris_flat[i * 3] = t_ptr[i * 3];
                tris_flat[i * 3 + 1] = t_ptr[i * 3 + 1];
                tris_flat[i * 3 + 2] = t_ptr[i * 3 + 2];
            }

            // Optional normals (Nx3)
            std::vector<float> normals_flat;
            if (!normals_obj.is_none()) {
                auto n_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(normals_obj);
                float* n_ptr = n_arr.data();
                size_t n = n_arr.shape(0);
                normals_flat.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    normals_flat[i * 3] = n_ptr[i * 3];
                    normals_flat[i * 3 + 1] = n_ptr[i * 3 + 1];
                    normals_flat[i * 3 + 2] = n_ptr[i * 3 + 2];
                }
            }

            // Optional UVs (Nx2)
            std::vector<float> uvs_flat;
            if (!uvs_obj.is_none()) {
                auto uv_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(uvs_obj);
                float* uv_ptr = uv_arr.data();
                size_t n = uv_arr.shape(0);
                uvs_flat.resize(n * 2);
                for (size_t i = 0; i < n; ++i) {
                    uvs_flat[i * 2] = uv_ptr[i * 2];
                    uvs_flat[i * 2 + 1] = uv_ptr[i * 2 + 1];
                }
            }

            new (self) Mesh3(
                verts_flat.data(), num_verts,
                tris_flat.data(), tris_flat.size(),
                normals_flat.empty() ? nullptr : normals_flat.data(),
                uvs_flat.empty() ? nullptr : uvs_flat.data(),
                name.empty() ? nullptr : name.c_str()
            );
        },
             nb::arg("vertices"),
             nb::arg("triangles"),
             nb::arg("uvs") = nb::none(),
             nb::arg("vertex_normals") = nb::none(),
             nb::arg("name") = "")

        // Constructor with explicit UUID (for primitives)
        .def("__init__", [](Mesh3* self,
                           nb::ndarray<float, nb::c_contig, nb::device::cpu> vertices,
                           nb::ndarray<uint32_t, nb::c_contig, nb::device::cpu> triangles,
                           nb::object uvs_obj, nb::object normals_obj,
                           std::string name, std::string uuid) {
            size_t num_verts = vertices.shape(0);
            float* v_ptr = vertices.data();

            std::vector<float> verts_flat(num_verts * 3);
            for (size_t i = 0; i < num_verts; ++i) {
                verts_flat[i * 3] = v_ptr[i * 3];
                verts_flat[i * 3 + 1] = v_ptr[i * 3 + 1];
                verts_flat[i * 3 + 2] = v_ptr[i * 3 + 2];
            }

            size_t num_tris = triangles.shape(0);
            uint32_t* t_ptr = triangles.data();

            std::vector<uint32_t> tris_flat(num_tris * 3);
            for (size_t i = 0; i < num_tris; ++i) {
                tris_flat[i * 3] = t_ptr[i * 3];
                tris_flat[i * 3 + 1] = t_ptr[i * 3 + 1];
                tris_flat[i * 3 + 2] = t_ptr[i * 3 + 2];
            }

            std::vector<float> normals_flat;
            if (!normals_obj.is_none()) {
                auto n_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(normals_obj);
                float* n_ptr = n_arr.data();
                size_t n = n_arr.shape(0);
                normals_flat.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    normals_flat[i * 3] = n_ptr[i * 3];
                    normals_flat[i * 3 + 1] = n_ptr[i * 3 + 1];
                    normals_flat[i * 3 + 2] = n_ptr[i * 3 + 2];
                }
            }

            std::vector<float> uvs_flat;
            if (!uvs_obj.is_none()) {
                auto uv_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(uvs_obj);
                float* uv_ptr = uv_arr.data();
                size_t n = uv_arr.shape(0);
                uvs_flat.resize(n * 2);
                for (size_t i = 0; i < n; ++i) {
                    uvs_flat[i * 2] = uv_ptr[i * 2];
                    uvs_flat[i * 2 + 1] = uv_ptr[i * 2 + 1];
                }
            }

            new (self) Mesh3(
                uuid.c_str(),
                verts_flat.data(), num_verts,
                tris_flat.data(), tris_flat.size(),
                normals_flat.empty() ? nullptr : normals_flat.data(),
                uvs_flat.empty() ? nullptr : uvs_flat.data(),
                name.empty() ? nullptr : name.c_str()
            );
        },
             nb::arg("vertices"),
             nb::arg("triangles"),
             nb::arg("uvs") = nb::none(),
             nb::arg("vertex_normals") = nb::none(),
             nb::arg("name") = "",
             nb::arg("uuid"))

        // Properties as numpy arrays
        .def_prop_rw("vertices",
            [](const Mesh3& m) {
                auto verts = m.get_vertices();
                size_t n = verts.size() / 3;
                return make_array_2d(verts.data(), n, 3);
            },
            [](Mesh3& m, nb::object arr) {
                throw std::runtime_error("Mesh3 vertices are immutable after creation");
            })

        .def_prop_rw("triangles",
            [](const Mesh3& m) {
                auto indices = m.get_indices();
                size_t n = indices.size() / 3;
                return make_array_2d(indices.data(), n, 3);
            },
            [](Mesh3& m, nb::object arr) {
                throw std::runtime_error("Mesh3 triangles are immutable after creation");
            })

        .def_prop_rw("indices",
            [](const Mesh3& m) {
                auto indices = m.get_indices();
                size_t n = indices.size() / 3;
                return make_array_2d(indices.data(), n, 3);
            },
            [](Mesh3& m, nb::object arr) {
                throw std::runtime_error("Mesh3 indices are immutable after creation");
            })

        .def_prop_rw("uvs",
            [](const Mesh3& m) -> nb::object {
                if (!m.has_uvs()) return nb::none();
                auto uvs = m.get_uvs();
                size_t n = uvs.size() / 2;
                return make_array_2d(uvs.data(), n, 2);
            },
            [](Mesh3& m, nb::object obj) {
                throw std::runtime_error("Mesh3 uvs are immutable after creation");
            })

        .def_prop_rw("vertex_normals",
            [](const Mesh3& m) -> nb::object {
                if (!m.has_vertex_normals()) return nb::none();
                auto normals = m.get_normals();
                if (normals.empty()) return nb::none();
                bool all_zero = true;
                for (float f : normals) {
                    if (f != 0.0f) { all_zero = false; break; }
                }
                if (all_zero) return nb::none();
                size_t n = normals.size() / 3;
                return make_array_2d(normals.data(), n, 3);
            },
            [](Mesh3& m, nb::object obj) {
                throw std::runtime_error("Mesh3 vertex_normals are immutable after creation. Use compute_vertex_normals()");
            })

        .def_prop_rw("face_normals",
            [](const Mesh3& m) -> nb::object { return nb::none(); },
            [](Mesh3& m, nb::object obj) {})

        .def_prop_rw("source_path",
            [](const Mesh3&) -> std::string {
                throw std::runtime_error("source_path is not supported for technical reasons");
            },
            [](Mesh3&, const std::string&) {
                throw std::runtime_error("source_path is not supported for technical reasons");
            })

        .def_prop_ro("type", [](const Mesh3&) { return "triangles"; })
        .def_prop_ro("uuid", [](const Mesh3& m) { return std::string(m.uuid()); })
        .def_prop_ro("tc_mesh", [](const Mesh3& m) { return m.raw(); }, nb::rv_policy::reference)
        .def_prop_rw("name",
            [](const Mesh3& m) { return std::string(m.name()); },
            [](Mesh3& m, const std::string& n) { m.set_name(n.c_str()); })
        .def_prop_ro("version", &Mesh3::version)

        .def("get_vertex_count", &Mesh3::get_vertex_count)
        .def("get_face_count", &Mesh3::get_face_count)
        .def("has_uvs", &Mesh3::has_uvs)
        .def("has_vertex_normals", &Mesh3::has_vertex_normals)
        .def("is_valid", &Mesh3::is_valid)

        .def("translate", [](Mesh3& m, nb::ndarray<float, nb::c_contig, nb::device::cpu> offset) {
            float* ptr = offset.data();
            m.translate(ptr[0], ptr[1], ptr[2]);
        }, nb::arg("offset"))

        .def("scale", &Mesh3::scale, nb::arg("factor"))

        .def("compute_vertex_normals", [](Mesh3& m) {
            m.compute_normals();
            auto normals = m.get_normals();
            size_t n = normals.size() / 3;
            return make_array_2d(normals.data(), n, 3);
        })

        .def("compute_faces_normals", [](Mesh3& m) { return nb::none(); })

        .def("interleaved_buffer", [](const Mesh3& m) {
            auto buf = m.build_interleaved_buffer();
            size_t n = m.get_vertex_count();
            return make_array_2d(buf.data(), n, 8);
        })

        .def("build_interleaved_buffer", [](const Mesh3& m) {
            auto buf = m.build_interleaved_buffer();
            size_t n = m.get_vertex_count();
            return make_array_2d(buf.data(), n, 8);
        })

        .def("copy", &Mesh3::copy)

        .def_static("from_uuid", [](const std::string& uuid) {
            return Mesh3::from_uuid(uuid.c_str());
        }, nb::arg("uuid"), "Get existing mesh from registry by UUID")

        .def("direct_serialize", [](const Mesh3& m) {
            nb::dict result;
            result["type"] = "inline";
            result["uuid"] = std::string(m.uuid());

            auto verts = m.get_vertices();
            size_t nv = verts.size() / 3;
            nb::list verts_list;
            for (size_t i = 0; i < nv; ++i) {
                nb::list v;
                v.append(verts[i * 3]);
                v.append(verts[i * 3 + 1]);
                v.append(verts[i * 3 + 2]);
                verts_list.append(v);
            }
            result["vertices"] = verts_list;

            auto indices = m.get_indices();
            size_t nt = indices.size() / 3;
            nb::list tris;
            for (size_t i = 0; i < nt; ++i) {
                nb::list t;
                t.append(indices[i * 3]);
                t.append(indices[i * 3 + 1]);
                t.append(indices[i * 3 + 2]);
                tris.append(t);
            }
            result["triangles"] = tris;

            if (m.has_uvs()) {
                auto uvs = m.get_uvs();
                size_t nu = uvs.size() / 2;
                nb::list uvlist;
                for (size_t i = 0; i < nu; ++i) {
                    nb::list uv;
                    uv.append(uvs[i * 2]);
                    uv.append(uvs[i * 2 + 1]);
                    uvlist.append(uv);
                }
                result["uvs"] = uvlist;
            }

            auto normals = m.get_normals();
            if (!normals.empty()) {
                size_t nn = normals.size() / 3;
                nb::list nlist;
                for (size_t i = 0; i < nn; ++i) {
                    nb::list n;
                    n.append(normals[i * 3]);
                    n.append(normals[i * 3 + 1]);
                    n.append(normals[i * 3 + 2]);
                    nlist.append(n);
                }
                result["normals"] = nlist;
            }

            return result;
        })

        .def_static("direct_deserialize", [](nb::dict data) {
            nb::list verts = nb::cast<nb::list>(data["vertices"]);
            size_t nv = nb::len(verts);
            std::vector<float> verts_flat(nv * 3);
            for (size_t i = 0; i < nv; ++i) {
                nb::list v = nb::cast<nb::list>(verts[i]);
                verts_flat[i * 3] = nb::cast<float>(v[0]);
                verts_flat[i * 3 + 1] = nb::cast<float>(v[1]);
                verts_flat[i * 3 + 2] = nb::cast<float>(v[2]);
            }

            nb::list tris = nb::cast<nb::list>(data["triangles"]);
            size_t nt = nb::len(tris);
            std::vector<uint32_t> tris_flat(nt * 3);
            for (size_t i = 0; i < nt; ++i) {
                nb::list t = nb::cast<nb::list>(tris[i]);
                tris_flat[i * 3] = nb::cast<uint32_t>(t[0]);
                tris_flat[i * 3 + 1] = nb::cast<uint32_t>(t[1]);
                tris_flat[i * 3 + 2] = nb::cast<uint32_t>(t[2]);
            }

            std::vector<float> uvs_flat;
            if (data.contains("uvs")) {
                nb::list uvlist = nb::cast<nb::list>(data["uvs"]);
                size_t nu = nb::len(uvlist);
                uvs_flat.resize(nu * 2);
                for (size_t i = 0; i < nu; ++i) {
                    nb::list uv = nb::cast<nb::list>(uvlist[i]);
                    uvs_flat[i * 2] = nb::cast<float>(uv[0]);
                    uvs_flat[i * 2 + 1] = nb::cast<float>(uv[1]);
                }
            }

            std::vector<float> normals_flat;
            if (data.contains("normals")) {
                nb::list nlist = nb::cast<nb::list>(data["normals"]);
                size_t nn = nb::len(nlist);
                normals_flat.resize(nn * 3);
                for (size_t i = 0; i < nn; ++i) {
                    nb::list n = nb::cast<nb::list>(nlist[i]);
                    normals_flat[i * 3] = nb::cast<float>(n[0]);
                    normals_flat[i * 3 + 1] = nb::cast<float>(n[1]);
                    normals_flat[i * 3 + 2] = nb::cast<float>(n[2]);
                }
            }

            std::string mesh_name;
            if (data.contains("path")) {
                mesh_name = nb::cast<std::string>(data["path"]);
            } else if (data.contains("uuid")) {
                mesh_name = nb::cast<std::string>(data["uuid"]);
            } else {
                mesh_name = "deserialized_mesh";
            }

            return Mesh3(
                mesh_name.c_str(),
                verts_flat.data(), nv,
                tris_flat.data(), tris_flat.size(),
                normals_flat.empty() ? nullptr : normals_flat.data(),
                uvs_flat.empty() ? nullptr : uvs_flat.data()
            );
        }, nb::arg("data"))

        .def("__repr__", [](const Mesh3& m) {
            return "<Mesh3 vertices=" + std::to_string(m.get_vertex_count()) +
                   " triangles=" + std::to_string(m.get_face_count()) +
                   " uuid=" + std::string(m.uuid()) + ">";
        });

    // SkinnedMesh3 - extends CustomMesh with skeletal animation data
    nb::class_<SkinnedMesh3, CustomMesh>(m, "SkinnedMesh3")
        .def(nb::init<>())
        .def("__init__", [](SkinnedMesh3* self,
                           nb::ndarray<float, nb::c_contig, nb::device::cpu> vertices,
                           nb::ndarray<uint32_t, nb::c_contig, nb::device::cpu> triangles,
                           nb::object uvs_obj, nb::object normals_obj,
                           nb::object joint_indices_obj, nb::object joint_weights_obj,
                           std::string name) {
            size_t num_verts = vertices.shape(0);
            float* v_ptr = vertices.data();

            std::vector<float> verts_flat(num_verts * 3);
            for (size_t i = 0; i < num_verts; ++i) {
                verts_flat[i * 3] = v_ptr[i * 3];
                verts_flat[i * 3 + 1] = v_ptr[i * 3 + 1];
                verts_flat[i * 3 + 2] = v_ptr[i * 3 + 2];
            }

            size_t num_tris = triangles.shape(0);
            uint32_t* t_ptr = triangles.data();

            std::vector<uint32_t> tris_flat(num_tris * 3);
            for (size_t i = 0; i < num_tris; ++i) {
                tris_flat[i * 3] = t_ptr[i * 3];
                tris_flat[i * 3 + 1] = t_ptr[i * 3 + 1];
                tris_flat[i * 3 + 2] = t_ptr[i * 3 + 2];
            }

            std::vector<float> normals_flat;
            if (!normals_obj.is_none()) {
                auto n_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(normals_obj);
                float* n_ptr = n_arr.data();
                size_t n = n_arr.shape(0);
                normals_flat.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    normals_flat[i * 3] = n_ptr[i * 3];
                    normals_flat[i * 3 + 1] = n_ptr[i * 3 + 1];
                    normals_flat[i * 3 + 2] = n_ptr[i * 3 + 2];
                }
            }

            std::vector<float> uvs_flat;
            if (!uvs_obj.is_none()) {
                auto uv_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(uvs_obj);
                float* uv_ptr = uv_arr.data();
                size_t n = uv_arr.shape(0);
                uvs_flat.resize(n * 2);
                for (size_t i = 0; i < n; ++i) {
                    uvs_flat[i * 2] = uv_ptr[i * 2];
                    uvs_flat[i * 2 + 1] = uv_ptr[i * 2 + 1];
                }
            }

            std::vector<float> joints_flat;
            if (!joint_indices_obj.is_none()) {
                auto ji_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(joint_indices_obj);
                float* ji_ptr = ji_arr.data();
                size_t n = ji_arr.shape(0);
                joints_flat.resize(n * 4);
                for (size_t i = 0; i < n; ++i) {
                    joints_flat[i * 4] = ji_ptr[i * 4];
                    joints_flat[i * 4 + 1] = ji_ptr[i * 4 + 1];
                    joints_flat[i * 4 + 2] = ji_ptr[i * 4 + 2];
                    joints_flat[i * 4 + 3] = ji_ptr[i * 4 + 3];
                }
            }

            std::vector<float> weights_flat;
            if (!joint_weights_obj.is_none()) {
                auto jw_arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(joint_weights_obj);
                float* jw_ptr = jw_arr.data();
                size_t n = jw_arr.shape(0);
                weights_flat.resize(n * 4);
                for (size_t i = 0; i < n; ++i) {
                    weights_flat[i * 4] = jw_ptr[i * 4];
                    weights_flat[i * 4 + 1] = jw_ptr[i * 4 + 1];
                    weights_flat[i * 4 + 2] = jw_ptr[i * 4 + 2];
                    weights_flat[i * 4 + 3] = jw_ptr[i * 4 + 3];
                }
            }

            new (self) SkinnedMesh3(
                verts_flat.data(), num_verts,
                tris_flat.data(), tris_flat.size(),
                normals_flat.empty() ? nullptr : normals_flat.data(),
                uvs_flat.empty() ? nullptr : uvs_flat.data(),
                joints_flat.empty() ? nullptr : joints_flat.data(),
                weights_flat.empty() ? nullptr : weights_flat.data(),
                name.empty() ? nullptr : name.c_str()
            );
        },
             nb::arg("vertices"),
             nb::arg("triangles"),
             nb::arg("uvs") = nb::none(),
             nb::arg("vertex_normals") = nb::none(),
             nb::arg("joint_indices") = nb::none(),
             nb::arg("joint_weights") = nb::none(),
             nb::arg("name") = "")

        .def_prop_rw("vertices",
            [](const SkinnedMesh3& m) {
                auto verts = m.get_vertices();
                size_t n = verts.size() / 3;
                return make_array_2d(verts.data(), n, 3);
            },
            [](SkinnedMesh3& m, nb::object arr) {
                throw std::runtime_error("SkinnedMesh3 vertices are immutable after creation");
            })

        .def_prop_rw("triangles",
            [](const SkinnedMesh3& m) {
                auto indices = m.get_indices();
                size_t n = indices.size() / 3;
                return make_array_2d(indices.data(), n, 3);
            },
            [](SkinnedMesh3& m, nb::object arr) {
                throw std::runtime_error("SkinnedMesh3 triangles are immutable after creation");
            })

        .def_prop_rw("indices",
            [](const SkinnedMesh3& m) {
                auto indices = m.get_indices();
                size_t n = indices.size() / 3;
                return make_array_2d(indices.data(), n, 3);
            },
            [](SkinnedMesh3& m, nb::object arr) {
                throw std::runtime_error("SkinnedMesh3 indices are immutable after creation");
            })

        .def_prop_rw("uvs",
            [](const SkinnedMesh3& m) -> nb::object {
                auto uvs = m.get_uvs();
                if (uvs.empty()) return nb::none();
                size_t n = uvs.size() / 2;
                return make_array_2d(uvs.data(), n, 2);
            },
            [](SkinnedMesh3& m, nb::object obj) {
                throw std::runtime_error("SkinnedMesh3 uvs are immutable after creation");
            })

        .def_prop_rw("vertex_normals",
            [](const SkinnedMesh3& m) -> nb::object {
                auto normals = m.get_normals();
                if (normals.empty()) return nb::none();
                bool all_zero = true;
                for (float f : normals) {
                    if (f != 0.0f) { all_zero = false; break; }
                }
                if (all_zero) return nb::none();
                size_t n = normals.size() / 3;
                return make_array_2d(normals.data(), n, 3);
            },
            [](SkinnedMesh3& m, nb::object obj) {
                throw std::runtime_error("SkinnedMesh3 vertex_normals are immutable after creation");
            })

        .def_prop_ro("type", [](const SkinnedMesh3&) { return "triangles"; })

        .def_prop_rw("joint_indices",
            [](const SkinnedMesh3& m) -> nb::object {
                auto joints = m.get_joint_indices();
                if (joints.empty()) return nb::none();
                size_t n = joints.size() / 4;
                return make_array_2d(joints.data(), n, 4);
            },
            [](SkinnedMesh3& m, nb::object obj) {
                if (obj.is_none()) return;
                auto arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(obj);
                float* ptr = arr.data();
                size_t n = arr.shape(0);
                std::vector<float> data(n * 4);
                for (size_t i = 0; i < n * 4; ++i) {
                    data[i] = ptr[i];
                }
                m.set_joint_indices(data.data(), n);
            })

        .def_prop_rw("joint_weights",
            [](const SkinnedMesh3& m) -> nb::object {
                auto weights = m.get_joint_weights();
                if (weights.empty()) return nb::none();
                size_t n = weights.size() / 4;
                return make_array_2d(weights.data(), n, 4);
            },
            [](SkinnedMesh3& m, nb::object obj) {
                if (obj.is_none()) return;
                auto arr = nb::cast<nb::ndarray<float, nb::c_contig, nb::device::cpu>>(obj);
                float* ptr = arr.data();
                size_t n = arr.shape(0);
                std::vector<float> data(n * 4);
                for (size_t i = 0; i < n * 4; ++i) {
                    data[i] = ptr[i];
                }
                m.set_joint_weights(data.data(), n);
            })

        .def("has_skinning", &SkinnedMesh3::has_skinning)
        .def("normalize_weights", &SkinnedMesh3::normalize_weights)
        .def("init_default_skinning", &SkinnedMesh3::init_default_skinning)

        .def("get_vertex_layout", [](const SkinnedMesh3& m) {
            nb::module_ mesh_mod = nb::module_::import_("termin.mesh.mesh");
            nb::object VertexLayout = mesh_mod.attr("VertexLayout");
            nb::object VertexAttribute = mesh_mod.attr("VertexAttribute");
            nb::object VertexAttribType = mesh_mod.attr("VertexAttribType");
            nb::object FLOAT32 = VertexAttribType.attr("FLOAT32");

            nb::list attrs;
            attrs.append(VertexAttribute("position", 3, FLOAT32, 0));
            attrs.append(VertexAttribute("normal", 3, FLOAT32, 12));
            attrs.append(VertexAttribute("uv", 2, FLOAT32, 24));
            attrs.append(VertexAttribute("joints", 4, FLOAT32, 32));
            attrs.append(VertexAttribute("weights", 4, FLOAT32, 48));

            return VertexLayout(64, attrs);
        })

        .def("interleaved_buffer", [](const SkinnedMesh3& m) {
            auto buf = m.build_interleaved_buffer();
            size_t n = m.vertex_count();
            return make_array_2d(buf.data(), n, 16);
        })

        .def("build_interleaved_buffer", [](const SkinnedMesh3& m) {
            auto buf = m.build_interleaved_buffer();
            size_t n = m.vertex_count();
            return make_array_2d(buf.data(), n, 16);
        })

        .def("copy", &SkinnedMesh3::copy)

        .def_prop_rw("source_path",
            [](const SkinnedMesh3&) -> std::string {
                throw std::runtime_error("source_path is not supported for technical reasons");
            },
            [](SkinnedMesh3&, const std::string&) {
                throw std::runtime_error("source_path is not supported for technical reasons");
            })

        .def("get_vertex_count", &SkinnedMesh3::vertex_count)
        .def("get_face_count", &SkinnedMesh3::triangle_count)
        .def("has_uvs", [](const SkinnedMesh3& m) { return m.has_attribute("uv"); })
        .def("has_vertex_normals", [](const SkinnedMesh3& m) { return m.has_attribute("normal"); })
        .def("is_valid", &SkinnedMesh3::is_valid)

        .def_static("from_uuid", [](const std::string& uuid) {
            return SkinnedMesh3::from_uuid(uuid.c_str());
        }, nb::arg("uuid"), "Get existing skinned mesh from registry by UUID")

        .def("__repr__", [](const SkinnedMesh3& m) {
            return "<SkinnedMesh3 vertices=" + std::to_string(m.vertex_count()) +
                   " triangles=" + std::to_string(m.triangle_count()) +
                   " skinning=" + (m.has_skinning() ? "yes" : "no") +
                   " uuid=" + std::string(m.uuid()) + ">";
        });

    // =========================================================================
    // TcMesh - Low-level mesh API for Python-based mesh types (like VoxelMesh)
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

    nb::class_<tc_mesh>(m, "TcMesh")
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

    // TcMeshHandle - RAII wrapper for tc_mesh*
    struct TcMeshHandle {
        tc_mesh* mesh = nullptr;

        TcMeshHandle() = default;
        TcMeshHandle(tc_mesh* m) : mesh(m) {
            if (mesh) tc_mesh_add_ref(mesh);
        }
        TcMeshHandle(const TcMeshHandle& other) : mesh(other.mesh) {
            if (mesh) tc_mesh_add_ref(mesh);
        }
        TcMeshHandle(TcMeshHandle&& other) noexcept : mesh(other.mesh) {
            other.mesh = nullptr;
        }
        TcMeshHandle& operator=(const TcMeshHandle& other) {
            if (this != &other) {
                if (mesh) tc_mesh_release(mesh);
                mesh = other.mesh;
                if (mesh) tc_mesh_add_ref(mesh);
            }
            return *this;
        }
        TcMeshHandle& operator=(TcMeshHandle&& other) noexcept {
            if (this != &other) {
                if (mesh) tc_mesh_release(mesh);
                mesh = other.mesh;
                other.mesh = nullptr;
            }
            return *this;
        }
        ~TcMeshHandle() {
            if (mesh) {
                tc_mesh_release(mesh);
                mesh = nullptr;
            }
        }

        bool is_valid() const { return mesh != nullptr; }
        const char* uuid() const { return mesh ? mesh->uuid : ""; }
        const char* name() const { return mesh && mesh->name ? mesh->name : ""; }
        uint32_t version() const { return mesh ? mesh->version : 0; }
        size_t vertex_count() const { return mesh ? mesh->vertex_count : 0; }
        size_t index_count() const { return mesh ? mesh->index_count : 0; }
        uint16_t stride() const { return mesh ? mesh->layout.stride : 0; }

        void bump_version() {
            if (mesh) mesh->version++;
        }
    };

    nb::class_<TcMeshHandle>(m, "TcMeshHandle")
        .def(nb::init<>())
        .def_prop_ro("is_valid", &TcMeshHandle::is_valid)
        .def_prop_ro("uuid", &TcMeshHandle::uuid)
        .def_prop_ro("name", &TcMeshHandle::name)
        .def_prop_ro("version", &TcMeshHandle::version)
        .def_prop_ro("vertex_count", &TcMeshHandle::vertex_count)
        .def_prop_ro("index_count", &TcMeshHandle::index_count)
        .def_prop_ro("stride", &TcMeshHandle::stride)
        .def_prop_ro("mesh", [](const TcMeshHandle& h) -> nb::object {
            if (!h.mesh) return nb::none();
            return nb::cast(h.mesh, nb::rv_policy::reference);
        })
        .def("bump_version", &TcMeshHandle::bump_version)
        .def("get_vertices_buffer", [](const TcMeshHandle& h) -> nb::object {
            if (!h.mesh || !h.mesh->vertices || h.mesh->vertex_count == 0) return nb::none();
            size_t total_floats = (h.mesh->vertex_count * h.mesh->layout.stride) / sizeof(float);
            return make_array_1d((const float*)h.mesh->vertices, total_floats);
        })
        .def("get_indices_buffer", [](const TcMeshHandle& h) -> nb::object {
            if (!h.mesh || !h.mesh->indices || h.mesh->index_count == 0) return nb::none();
            return make_array_1d(h.mesh->indices, h.mesh->index_count);
        })
        .def("__repr__", [](const TcMeshHandle& h) {
            if (!h.mesh) return std::string("<TcMeshHandle invalid>");
            return "<TcMeshHandle vertices=" + std::to_string(h.mesh->vertex_count) +
                   " indices=" + std::to_string(h.mesh->index_count) +
                   " uuid=" + std::string(h.mesh->uuid) + ">";
        });

    // Module-level functions
    m.def("tc_mesh_compute_uuid", [](nb::ndarray<float, nb::c_contig, nb::device::cpu> vertices,
                                      nb::ndarray<uint32_t, nb::c_contig, nb::device::cpu> indices) {
        char uuid[40];
        tc_mesh_compute_uuid(vertices.data(), vertices.size() * sizeof(float),
                            indices.data(), indices.size(), uuid);
        return std::string(uuid);
    }, nb::arg("vertices"), nb::arg("indices"),
       "Compute UUID from vertex and index data (hash-based)");

    m.def("tc_mesh_get", [](const std::string& uuid) -> std::optional<TcMeshHandle> {
        tc_mesh* mesh = tc_mesh_get(uuid.c_str());
        if (!mesh) return std::nullopt;
        return TcMeshHandle(mesh);
    }, nb::arg("uuid"),
       "Get existing mesh by UUID (returns None if not found)");

    m.def("tc_mesh_get_or_create", [](const std::string& uuid) {
        tc_mesh* mesh = tc_mesh_get_or_create(uuid.c_str());
        return TcMeshHandle(mesh);
    }, nb::arg("uuid"),
       "Get existing mesh or create new one");

    m.def("tc_mesh_set_data", [](TcMeshHandle& handle,
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
}

} // namespace termin
