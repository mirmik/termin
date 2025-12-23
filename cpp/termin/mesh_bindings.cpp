#include "mesh_bindings.hpp"

#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include "termin/mesh/mesh3.hpp"
#include "termin/mesh/skinned_mesh3.hpp"

namespace py = pybind11;

namespace termin {

void bind_mesh(py::module_& m) {
    py::class_<Mesh3>(m, "Mesh3")
        .def(py::init<>())
        .def(py::init([](py::array_t<float> vertices, py::array_t<uint32_t> triangles,
                         py::object uvs_obj, py::object normals_obj, py::object source_path_obj) {
            Mesh3 mesh;

            // Copy vertices (Nx3 -> flattened)
            auto v_buf = vertices.unchecked<2>();
            size_t num_verts = v_buf.shape(0);
            mesh.vertices.resize(num_verts * 3);
            for (size_t i = 0; i < num_verts; ++i) {
                mesh.vertices[i * 3] = v_buf(i, 0);
                mesh.vertices[i * 3 + 1] = v_buf(i, 1);
                mesh.vertices[i * 3 + 2] = v_buf(i, 2);
            }

            // Copy triangles (Mx3 -> flattened)
            auto t_buf = triangles.unchecked<2>();
            size_t num_tris = t_buf.shape(0);
            mesh.indices.resize(num_tris * 3);
            for (size_t i = 0; i < num_tris; ++i) {
                mesh.indices[i * 3] = t_buf(i, 0);
                mesh.indices[i * 3 + 1] = t_buf(i, 1);
                mesh.indices[i * 3 + 2] = t_buf(i, 2);
            }

            // Optional UVs (Nx2)
            if (!uvs_obj.is_none()) {
                auto uv_arr = uvs_obj.cast<py::array_t<float>>();
                auto uv_buf = uv_arr.unchecked<2>();
                size_t n = uv_buf.shape(0);
                mesh.uvs.resize(n * 2);
                for (size_t i = 0; i < n; ++i) {
                    mesh.uvs[i * 2] = uv_buf(i, 0);
                    mesh.uvs[i * 2 + 1] = uv_buf(i, 1);
                }
            }

            // Optional vertex normals (Nx3)
            if (!normals_obj.is_none()) {
                auto n_arr = normals_obj.cast<py::array_t<float>>();
                auto n_buf = n_arr.unchecked<2>();
                size_t n = n_buf.shape(0);
                mesh.vertex_normals.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    mesh.vertex_normals[i * 3] = n_buf(i, 0);
                    mesh.vertex_normals[i * 3 + 1] = n_buf(i, 1);
                    mesh.vertex_normals[i * 3 + 2] = n_buf(i, 2);
                }
            }

            // Optional source path
            if (!source_path_obj.is_none()) {
                mesh.source_path = source_path_obj.cast<std::string>();
            }

            return mesh;
        }),
             py::arg("vertices"),
             py::arg("triangles"),
             py::arg("uvs") = py::none(),
             py::arg("vertex_normals") = py::none(),
             py::arg("source_path") = py::none())

        // Properties as numpy arrays
        .def_property("vertices",
            [](const Mesh3& m) {
                size_t n = m.get_vertex_count();
                auto result = py::array_t<float>({n, size_t(3)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = m.vertices[i * 3];
                    buf(i, 1) = m.vertices[i * 3 + 1];
                    buf(i, 2) = m.vertices[i * 3 + 2];
                }
                return result;
            },
            [](Mesh3& m, py::array_t<float> arr) {
                auto buf = arr.unchecked<2>();
                size_t n = buf.shape(0);
                m.vertices.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    m.vertices[i * 3] = buf(i, 0);
                    m.vertices[i * 3 + 1] = buf(i, 1);
                    m.vertices[i * 3 + 2] = buf(i, 2);
                }
            })

        .def_property("triangles",
            [](const Mesh3& m) {
                size_t n = m.get_face_count();
                auto result = py::array_t<uint32_t>({n, size_t(3)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = m.indices[i * 3];
                    buf(i, 1) = m.indices[i * 3 + 1];
                    buf(i, 2) = m.indices[i * 3 + 2];
                }
                return result;
            },
            [](Mesh3& m, py::array_t<uint32_t> arr) {
                auto buf = arr.unchecked<2>();
                size_t n = buf.shape(0);
                m.indices.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    m.indices[i * 3] = buf(i, 0);
                    m.indices[i * 3 + 1] = buf(i, 1);
                    m.indices[i * 3 + 2] = buf(i, 2);
                }
            })

        // Alias for triangles
        .def_property("indices",
            [](const Mesh3& m) {
                size_t n = m.get_face_count();
                auto result = py::array_t<uint32_t>({n, size_t(3)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = m.indices[i * 3];
                    buf(i, 1) = m.indices[i * 3 + 1];
                    buf(i, 2) = m.indices[i * 3 + 2];
                }
                return result;
            },
            [](Mesh3& m, py::array_t<uint32_t> arr) {
                auto buf = arr.unchecked<2>();
                size_t n = buf.shape(0);
                m.indices.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    m.indices[i * 3] = buf(i, 0);
                    m.indices[i * 3 + 1] = buf(i, 1);
                    m.indices[i * 3 + 2] = buf(i, 2);
                }
            })

        .def_property("uvs",
            [](const Mesh3& m) -> py::object {
                if (m.uvs.empty()) return py::none();
                size_t n = m.uvs.size() / 2;
                auto result = py::array_t<float>({n, size_t(2)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = m.uvs[i * 2];
                    buf(i, 1) = m.uvs[i * 2 + 1];
                }
                return result;
            },
            [](Mesh3& m, py::object obj) {
                if (obj.is_none()) {
                    m.uvs.clear();
                    return;
                }
                auto arr = obj.cast<py::array_t<float>>();
                auto buf = arr.unchecked<2>();
                size_t n = buf.shape(0);
                m.uvs.resize(n * 2);
                for (size_t i = 0; i < n; ++i) {
                    m.uvs[i * 2] = buf(i, 0);
                    m.uvs[i * 2 + 1] = buf(i, 1);
                }
            })

        .def_property("vertex_normals",
            [](const Mesh3& m) -> py::object {
                if (m.vertex_normals.empty()) return py::none();
                size_t n = m.vertex_normals.size() / 3;
                auto result = py::array_t<float>({n, size_t(3)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = m.vertex_normals[i * 3];
                    buf(i, 1) = m.vertex_normals[i * 3 + 1];
                    buf(i, 2) = m.vertex_normals[i * 3 + 2];
                }
                return result;
            },
            [](Mesh3& m, py::object obj) {
                if (obj.is_none()) {
                    m.vertex_normals.clear();
                    return;
                }
                auto arr = obj.cast<py::array_t<float>>();
                auto buf = arr.unchecked<2>();
                size_t n = buf.shape(0);
                m.vertex_normals.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    m.vertex_normals[i * 3] = buf(i, 0);
                    m.vertex_normals[i * 3 + 1] = buf(i, 1);
                    m.vertex_normals[i * 3 + 2] = buf(i, 2);
                }
            })

        .def_property("face_normals",
            [](const Mesh3& m) -> py::object {
                if (m.face_normals.empty()) return py::none();
                size_t n = m.face_normals.size() / 3;
                auto result = py::array_t<float>({n, size_t(3)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = m.face_normals[i * 3];
                    buf(i, 1) = m.face_normals[i * 3 + 1];
                    buf(i, 2) = m.face_normals[i * 3 + 2];
                }
                return result;
            },
            [](Mesh3& m, py::object obj) {
                if (obj.is_none()) {
                    m.face_normals.clear();
                    return;
                }
                auto arr = obj.cast<py::array_t<float>>();
                auto buf = arr.unchecked<2>();
                size_t n = buf.shape(0);
                m.face_normals.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    m.face_normals[i * 3] = buf(i, 0);
                    m.face_normals[i * 3 + 1] = buf(i, 1);
                    m.face_normals[i * 3 + 2] = buf(i, 2);
                }
            })

        .def_readwrite("source_path", &Mesh3::source_path)

        // Type property - Mesh3 always stores triangles
        .def_property_readonly("type", [](const Mesh3&) { return "triangles"; })

        // Methods
        .def("get_vertex_count", &Mesh3::get_vertex_count)
        .def("get_face_count", &Mesh3::get_face_count)
        .def("has_uvs", &Mesh3::has_uvs)
        .def("has_vertex_normals", &Mesh3::has_vertex_normals)

        .def("translate", [](Mesh3& m, py::array_t<float> offset) {
            auto buf = offset.unchecked<1>();
            m.translate(buf(0), buf(1), buf(2));
        }, py::arg("offset"))

        .def("scale", &Mesh3::scale, py::arg("factor"))

        .def("compute_vertex_normals", [](Mesh3& m) {
            m.compute_vertex_normals();
            // Return the computed normals
            size_t n = m.vertex_normals.size() / 3;
            auto result = py::array_t<float>({n, size_t(3)});
            auto buf = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                buf(i, 0) = m.vertex_normals[i * 3];
                buf(i, 1) = m.vertex_normals[i * 3 + 1];
                buf(i, 2) = m.vertex_normals[i * 3 + 2];
            }
            return result;
        })

        .def("compute_faces_normals", [](Mesh3& m) {
            m.compute_face_normals();
            size_t n = m.face_normals.size() / 3;
            auto result = py::array_t<float>({n, size_t(3)});
            auto buf = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                buf(i, 0) = m.face_normals[i * 3];
                buf(i, 1) = m.face_normals[i * 3 + 1];
                buf(i, 2) = m.face_normals[i * 3 + 2];
            }
            return result;
        })

        .def("interleaved_buffer", [](const Mesh3& m) {
            auto buf = m.build_interleaved_buffer();
            size_t n = m.get_vertex_count();
            auto result = py::array_t<float>({n, size_t(8)});
            auto out = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                for (size_t j = 0; j < 8; ++j) {
                    out(i, j) = buf[i * 8 + j];
                }
            }
            return result;
        })

        .def("build_interleaved_buffer", [](const Mesh3& m) {
            auto buf = m.build_interleaved_buffer();
            size_t n = m.get_vertex_count();
            auto result = py::array_t<float>({n, size_t(8)});
            auto out = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                for (size_t j = 0; j < 8; ++j) {
                    out(i, j) = buf[i * 8 + j];
                }
            }
            return result;
        })

        .def("copy", &Mesh3::copy)

        // Serialization
        .def("direct_serialize", [](const Mesh3& m) {
            py::dict result;

            if (!m.source_path.empty()) {
                result["type"] = "path";
                result["path"] = m.source_path;
                return result;
            }

            result["type"] = "inline";

            // Vertices to nested list
            size_t nv = m.get_vertex_count();
            py::list verts;
            for (size_t i = 0; i < nv; ++i) {
                py::list v;
                v.append(m.vertices[i * 3]);
                v.append(m.vertices[i * 3 + 1]);
                v.append(m.vertices[i * 3 + 2]);
                verts.append(v);
            }
            result["vertices"] = verts;

            // Triangles to nested list
            size_t nt = m.get_face_count();
            py::list tris;
            for (size_t i = 0; i < nt; ++i) {
                py::list t;
                t.append(m.indices[i * 3]);
                t.append(m.indices[i * 3 + 1]);
                t.append(m.indices[i * 3 + 2]);
                tris.append(t);
            }
            result["triangles"] = tris;

            // Optional UVs
            if (!m.uvs.empty()) {
                size_t nu = m.uvs.size() / 2;
                py::list uvlist;
                for (size_t i = 0; i < nu; ++i) {
                    py::list uv;
                    uv.append(m.uvs[i * 2]);
                    uv.append(m.uvs[i * 2 + 1]);
                    uvlist.append(uv);
                }
                result["uvs"] = uvlist;
            }

            // Optional normals
            if (!m.vertex_normals.empty()) {
                size_t nn = m.vertex_normals.size() / 3;
                py::list nlist;
                for (size_t i = 0; i < nn; ++i) {
                    py::list n;
                    n.append(m.vertex_normals[i * 3]);
                    n.append(m.vertex_normals[i * 3 + 1]);
                    n.append(m.vertex_normals[i * 3 + 2]);
                    nlist.append(n);
                }
                result["normals"] = nlist;
            }

            return result;
        })

        .def_static("direct_deserialize", [](py::dict data) {
            Mesh3 mesh;

            // Vertices
            py::list verts = data["vertices"].cast<py::list>();
            size_t nv = verts.size();
            mesh.vertices.resize(nv * 3);
            for (size_t i = 0; i < nv; ++i) {
                py::list v = verts[i].cast<py::list>();
                mesh.vertices[i * 3] = v[0].cast<float>();
                mesh.vertices[i * 3 + 1] = v[1].cast<float>();
                mesh.vertices[i * 3 + 2] = v[2].cast<float>();
            }

            // Triangles
            py::list tris = data["triangles"].cast<py::list>();
            size_t nt = tris.size();
            mesh.indices.resize(nt * 3);
            for (size_t i = 0; i < nt; ++i) {
                py::list t = tris[i].cast<py::list>();
                mesh.indices[i * 3] = t[0].cast<uint32_t>();
                mesh.indices[i * 3 + 1] = t[1].cast<uint32_t>();
                mesh.indices[i * 3 + 2] = t[2].cast<uint32_t>();
            }

            // Optional UVs
            if (data.contains("uvs")) {
                py::list uvlist = data["uvs"].cast<py::list>();
                size_t nu = uvlist.size();
                mesh.uvs.resize(nu * 2);
                for (size_t i = 0; i < nu; ++i) {
                    py::list uv = uvlist[i].cast<py::list>();
                    mesh.uvs[i * 2] = uv[0].cast<float>();
                    mesh.uvs[i * 2 + 1] = uv[1].cast<float>();
                }
            }

            // Optional normals
            if (data.contains("normals")) {
                py::list nlist = data["normals"].cast<py::list>();
                size_t nn = nlist.size();
                mesh.vertex_normals.resize(nn * 3);
                for (size_t i = 0; i < nn; ++i) {
                    py::list n = nlist[i].cast<py::list>();
                    mesh.vertex_normals[i * 3] = n[0].cast<float>();
                    mesh.vertex_normals[i * 3 + 1] = n[1].cast<float>();
                    mesh.vertex_normals[i * 3 + 2] = n[2].cast<float>();
                }
            }

            // Source path
            if (data.contains("path")) {
                mesh.source_path = data["path"].cast<std::string>();
            }

            return mesh;
        }, py::arg("data"))

        .def("__repr__", [](const Mesh3& m) {
            return "<Mesh3 vertices=" + std::to_string(m.get_vertex_count()) +
                   " triangles=" + std::to_string(m.get_face_count()) + ">";
        });

    // SkinnedMesh3 - extends Mesh3 with skeletal animation data
    py::class_<SkinnedMesh3, Mesh3>(m, "SkinnedMesh3")
        .def(py::init<>())
        .def(py::init([](py::array_t<float> vertices, py::array_t<uint32_t> triangles,
                         py::object uvs_obj, py::object normals_obj,
                         py::object joint_indices_obj, py::object joint_weights_obj,
                         py::object source_path_obj) {
            SkinnedMesh3 mesh;

            // Copy vertices (Nx3 -> flattened)
            auto v_buf = vertices.unchecked<2>();
            size_t num_verts = v_buf.shape(0);
            mesh.vertices.resize(num_verts * 3);
            for (size_t i = 0; i < num_verts; ++i) {
                mesh.vertices[i * 3] = v_buf(i, 0);
                mesh.vertices[i * 3 + 1] = v_buf(i, 1);
                mesh.vertices[i * 3 + 2] = v_buf(i, 2);
            }

            // Copy triangles (Mx3 -> flattened)
            auto t_buf = triangles.unchecked<2>();
            size_t num_tris = t_buf.shape(0);
            mesh.indices.resize(num_tris * 3);
            for (size_t i = 0; i < num_tris; ++i) {
                mesh.indices[i * 3] = t_buf(i, 0);
                mesh.indices[i * 3 + 1] = t_buf(i, 1);
                mesh.indices[i * 3 + 2] = t_buf(i, 2);
            }

            // Optional UVs (Nx2)
            if (!uvs_obj.is_none()) {
                auto uv_arr = uvs_obj.cast<py::array_t<float>>();
                auto uv_buf = uv_arr.unchecked<2>();
                size_t n = uv_buf.shape(0);
                mesh.uvs.resize(n * 2);
                for (size_t i = 0; i < n; ++i) {
                    mesh.uvs[i * 2] = uv_buf(i, 0);
                    mesh.uvs[i * 2 + 1] = uv_buf(i, 1);
                }
            }

            // Optional vertex normals (Nx3)
            if (!normals_obj.is_none()) {
                auto n_arr = normals_obj.cast<py::array_t<float>>();
                auto n_buf = n_arr.unchecked<2>();
                size_t n = n_buf.shape(0);
                mesh.vertex_normals.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    mesh.vertex_normals[i * 3] = n_buf(i, 0);
                    mesh.vertex_normals[i * 3 + 1] = n_buf(i, 1);
                    mesh.vertex_normals[i * 3 + 2] = n_buf(i, 2);
                }
            }

            // Joint indices (Nx4)
            if (!joint_indices_obj.is_none()) {
                auto ji_arr = joint_indices_obj.cast<py::array_t<float>>();
                auto ji_buf = ji_arr.unchecked<2>();
                size_t n = ji_buf.shape(0);
                mesh.joint_indices.resize(n * 4);
                for (size_t i = 0; i < n; ++i) {
                    mesh.joint_indices[i * 4] = ji_buf(i, 0);
                    mesh.joint_indices[i * 4 + 1] = ji_buf(i, 1);
                    mesh.joint_indices[i * 4 + 2] = ji_buf(i, 2);
                    mesh.joint_indices[i * 4 + 3] = ji_buf(i, 3);
                }
            } else {
                mesh.init_default_skinning();
            }

            // Joint weights (Nx4)
            if (!joint_weights_obj.is_none()) {
                auto jw_arr = joint_weights_obj.cast<py::array_t<float>>();
                auto jw_buf = jw_arr.unchecked<2>();
                size_t n = jw_buf.shape(0);
                mesh.joint_weights.resize(n * 4);
                for (size_t i = 0; i < n; ++i) {
                    mesh.joint_weights[i * 4] = jw_buf(i, 0);
                    mesh.joint_weights[i * 4 + 1] = jw_buf(i, 1);
                    mesh.joint_weights[i * 4 + 2] = jw_buf(i, 2);
                    mesh.joint_weights[i * 4 + 3] = jw_buf(i, 3);
                }
            }

            // Optional source path
            if (!source_path_obj.is_none()) {
                mesh.source_path = source_path_obj.cast<std::string>();
            }

            return mesh;
        }),
             py::arg("vertices"),
             py::arg("triangles"),
             py::arg("uvs") = py::none(),
             py::arg("vertex_normals") = py::none(),
             py::arg("joint_indices") = py::none(),
             py::arg("joint_weights") = py::none(),
             py::arg("source_path") = py::none())

        // Joint indices property (Nx4)
        .def_property("joint_indices",
            [](const SkinnedMesh3& m) -> py::object {
                if (m.joint_indices.empty()) return py::none();
                size_t n = m.joint_indices.size() / 4;
                auto result = py::array_t<float>({n, size_t(4)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = m.joint_indices[i * 4];
                    buf(i, 1) = m.joint_indices[i * 4 + 1];
                    buf(i, 2) = m.joint_indices[i * 4 + 2];
                    buf(i, 3) = m.joint_indices[i * 4 + 3];
                }
                return result;
            },
            [](SkinnedMesh3& m, py::object obj) {
                if (obj.is_none()) {
                    m.joint_indices.clear();
                    return;
                }
                auto arr = obj.cast<py::array_t<float>>();
                auto buf = arr.unchecked<2>();
                size_t n = buf.shape(0);
                m.joint_indices.resize(n * 4);
                for (size_t i = 0; i < n; ++i) {
                    m.joint_indices[i * 4] = buf(i, 0);
                    m.joint_indices[i * 4 + 1] = buf(i, 1);
                    m.joint_indices[i * 4 + 2] = buf(i, 2);
                    m.joint_indices[i * 4 + 3] = buf(i, 3);
                }
            })

        // Joint weights property (Nx4)
        .def_property("joint_weights",
            [](const SkinnedMesh3& m) -> py::object {
                if (m.joint_weights.empty()) return py::none();
                size_t n = m.joint_weights.size() / 4;
                auto result = py::array_t<float>({n, size_t(4)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = m.joint_weights[i * 4];
                    buf(i, 1) = m.joint_weights[i * 4 + 1];
                    buf(i, 2) = m.joint_weights[i * 4 + 2];
                    buf(i, 3) = m.joint_weights[i * 4 + 3];
                }
                return result;
            },
            [](SkinnedMesh3& m, py::object obj) {
                if (obj.is_none()) {
                    m.joint_weights.clear();
                    return;
                }
                auto arr = obj.cast<py::array_t<float>>();
                auto buf = arr.unchecked<2>();
                size_t n = buf.shape(0);
                m.joint_weights.resize(n * 4);
                for (size_t i = 0; i < n; ++i) {
                    m.joint_weights[i * 4] = buf(i, 0);
                    m.joint_weights[i * 4 + 1] = buf(i, 1);
                    m.joint_weights[i * 4 + 2] = buf(i, 2);
                    m.joint_weights[i * 4 + 3] = buf(i, 3);
                }
            })

        .def("has_skinning", &SkinnedMesh3::has_skinning)
        .def("normalize_weights", &SkinnedMesh3::normalize_weights)

        // get_vertex_layout for create_mesh compatibility
        .def("get_vertex_layout", [](const SkinnedMesh3& m) {
            // Import VertexLayout, VertexAttribute from Python
            py::module_ mesh_mod = py::module_::import("termin.mesh.mesh");
            py::object VertexLayout = mesh_mod.attr("VertexLayout");
            py::object VertexAttribute = mesh_mod.attr("VertexAttribute");
            py::object VertexAttribType = mesh_mod.attr("VertexAttribType");
            py::object FLOAT32 = VertexAttribType.attr("FLOAT32");

            // Create layout: pos(3) + normal(3) + uv(2) + joints(4) + weights(4) = 64 bytes
            py::list attrs;
            attrs.append(VertexAttribute("position", 3, FLOAT32, 0));
            attrs.append(VertexAttribute("normal", 3, FLOAT32, 12));
            attrs.append(VertexAttribute("uv", 2, FLOAT32, 24));
            attrs.append(VertexAttribute("joints", 4, FLOAT32, 32));
            attrs.append(VertexAttribute("weights", 4, FLOAT32, 48));

            return VertexLayout(64, attrs);
        })

        // Override interleaved_buffer for skinned mesh (16 floats per vertex)
        .def("interleaved_buffer", [](const SkinnedMesh3& m) {
            auto buf = m.build_interleaved_buffer();
            size_t n = m.get_vertex_count();
            auto result = py::array_t<float>({n, size_t(16)});
            auto out = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                for (size_t j = 0; j < 16; ++j) {
                    out(i, j) = buf[i * 16 + j];
                }
            }
            return result;
        })

        .def("build_interleaved_buffer", [](const SkinnedMesh3& m) {
            auto buf = m.build_interleaved_buffer();
            size_t n = m.get_vertex_count();
            auto result = py::array_t<float>({n, size_t(16)});
            auto out = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                for (size_t j = 0; j < 16; ++j) {
                    out(i, j) = buf[i * 16 + j];
                }
            }
            return result;
        })

        .def("copy", &SkinnedMesh3::copy)

        .def("__repr__", [](const SkinnedMesh3& m) {
            return "<SkinnedMesh3 vertices=" + std::to_string(m.get_vertex_count()) +
                   " triangles=" + std::to_string(m.get_face_count()) +
                   " skinning=" + (m.has_skinning() ? "yes" : "no") + ">";
        });
}

} // namespace termin
