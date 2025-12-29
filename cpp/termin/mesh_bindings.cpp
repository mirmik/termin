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
        .def(py::init([](std::string name, py::array_t<float> vertices, py::array_t<uint32_t> triangles,
                         py::object uvs_obj, py::object normals_obj, py::object source_path_obj) {
            // Get vertex data (Nx3)
            auto v_buf = vertices.unchecked<2>();
            size_t num_verts = v_buf.shape(0);

            std::vector<float> verts_flat(num_verts * 3);
            for (size_t i = 0; i < num_verts; ++i) {
                verts_flat[i * 3] = v_buf(i, 0);
                verts_flat[i * 3 + 1] = v_buf(i, 1);
                verts_flat[i * 3 + 2] = v_buf(i, 2);
            }

            // Get triangle data (Mx3)
            auto t_buf = triangles.unchecked<2>();
            size_t num_tris = t_buf.shape(0);

            std::vector<uint32_t> tris_flat(num_tris * 3);
            for (size_t i = 0; i < num_tris; ++i) {
                tris_flat[i * 3] = t_buf(i, 0);
                tris_flat[i * 3 + 1] = t_buf(i, 1);
                tris_flat[i * 3 + 2] = t_buf(i, 2);
            }

            // Optional normals (Nx3)
            std::vector<float> normals_flat;
            if (!normals_obj.is_none()) {
                auto n_arr = normals_obj.cast<py::array_t<float>>();
                auto n_buf = n_arr.unchecked<2>();
                size_t n = n_buf.shape(0);
                normals_flat.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    normals_flat[i * 3] = n_buf(i, 0);
                    normals_flat[i * 3 + 1] = n_buf(i, 1);
                    normals_flat[i * 3 + 2] = n_buf(i, 2);
                }
            }

            // Optional UVs (Nx2)
            std::vector<float> uvs_flat;
            if (!uvs_obj.is_none()) {
                auto uv_arr = uvs_obj.cast<py::array_t<float>>();
                auto uv_buf = uv_arr.unchecked<2>();
                size_t n = uv_buf.shape(0);
                uvs_flat.resize(n * 2);
                for (size_t i = 0; i < n; ++i) {
                    uvs_flat[i * 2] = uv_buf(i, 0);
                    uvs_flat[i * 2 + 1] = uv_buf(i, 1);
                }
            }

            Mesh3 mesh(
                name.c_str(),
                verts_flat.data(), num_verts,
                tris_flat.data(), tris_flat.size(),
                normals_flat.empty() ? nullptr : normals_flat.data(),
                uvs_flat.empty() ? nullptr : uvs_flat.data()
            );

            // Store source path if provided
            if (!source_path_obj.is_none()) {
                mesh.source_path = source_path_obj.cast<std::string>();
            }

            return mesh;
        }),
             py::arg("name"),
             py::arg("vertices"),
             py::arg("triangles"),
             py::arg("uvs") = py::none(),
             py::arg("vertex_normals") = py::none(),
             py::arg("source_path") = py::none())

        // Constructor with explicit UUID (for primitives)
        .def(py::init([](std::string uuid, std::string name, py::array_t<float> vertices, py::array_t<uint32_t> triangles,
                         py::object uvs_obj, py::object normals_obj) {
            auto v_buf = vertices.unchecked<2>();
            size_t num_verts = v_buf.shape(0);

            std::vector<float> verts_flat(num_verts * 3);
            for (size_t i = 0; i < num_verts; ++i) {
                verts_flat[i * 3] = v_buf(i, 0);
                verts_flat[i * 3 + 1] = v_buf(i, 1);
                verts_flat[i * 3 + 2] = v_buf(i, 2);
            }

            auto t_buf = triangles.unchecked<2>();
            size_t num_tris = t_buf.shape(0);

            std::vector<uint32_t> tris_flat(num_tris * 3);
            for (size_t i = 0; i < num_tris; ++i) {
                tris_flat[i * 3] = t_buf(i, 0);
                tris_flat[i * 3 + 1] = t_buf(i, 1);
                tris_flat[i * 3 + 2] = t_buf(i, 2);
            }

            std::vector<float> normals_flat;
            if (!normals_obj.is_none()) {
                auto n_arr = normals_obj.cast<py::array_t<float>>();
                auto n_buf = n_arr.unchecked<2>();
                size_t n = n_buf.shape(0);
                normals_flat.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    normals_flat[i * 3] = n_buf(i, 0);
                    normals_flat[i * 3 + 1] = n_buf(i, 1);
                    normals_flat[i * 3 + 2] = n_buf(i, 2);
                }
            }

            std::vector<float> uvs_flat;
            if (!uvs_obj.is_none()) {
                auto uv_arr = uvs_obj.cast<py::array_t<float>>();
                auto uv_buf = uv_arr.unchecked<2>();
                size_t n = uv_buf.shape(0);
                uvs_flat.resize(n * 2);
                for (size_t i = 0; i < n; ++i) {
                    uvs_flat[i * 2] = uv_buf(i, 0);
                    uvs_flat[i * 2 + 1] = uv_buf(i, 1);
                }
            }

            return Mesh3(
                uuid.c_str(), name.c_str(),
                verts_flat.data(), num_verts,
                tris_flat.data(), tris_flat.size(),
                normals_flat.empty() ? nullptr : normals_flat.data(),
                uvs_flat.empty() ? nullptr : uvs_flat.data()
            );
        }),
             py::arg("uuid"),
             py::arg("name"),
             py::arg("vertices"),
             py::arg("triangles"),
             py::arg("uvs") = py::none(),
             py::arg("vertex_normals") = py::none())

        // Properties as numpy arrays
        .def_property("vertices",
            [](const Mesh3& m) {
                auto verts = m.get_vertices();
                size_t n = verts.size() / 3;
                auto result = py::array_t<float>({n, size_t(3)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = verts[i * 3];
                    buf(i, 1) = verts[i * 3 + 1];
                    buf(i, 2) = verts[i * 3 + 2];
                }
                return result;
            },
            [](Mesh3& m, py::array_t<float> arr) {
                // Setting vertices requires recreating the mesh
                // For now, this is a limitation - vertices are immutable after creation
                throw std::runtime_error("Mesh3 vertices are immutable after creation");
            })

        .def_property("triangles",
            [](const Mesh3& m) {
                auto indices = m.get_indices();
                size_t n = indices.size() / 3;
                auto result = py::array_t<uint32_t>({n, size_t(3)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = indices[i * 3];
                    buf(i, 1) = indices[i * 3 + 1];
                    buf(i, 2) = indices[i * 3 + 2];
                }
                return result;
            },
            [](Mesh3& m, py::array_t<uint32_t> arr) {
                throw std::runtime_error("Mesh3 triangles are immutable after creation");
            })

        // Alias for triangles
        .def_property("indices",
            [](const Mesh3& m) {
                auto indices = m.get_indices();
                size_t n = indices.size() / 3;
                auto result = py::array_t<uint32_t>({n, size_t(3)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = indices[i * 3];
                    buf(i, 1) = indices[i * 3 + 1];
                    buf(i, 2) = indices[i * 3 + 2];
                }
                return result;
            },
            [](Mesh3& m, py::array_t<uint32_t> arr) {
                throw std::runtime_error("Mesh3 indices are immutable after creation");
            })

        .def_property("uvs",
            [](const Mesh3& m) -> py::object {
                if (!m.has_uvs()) return py::none();
                auto uvs = m.get_uvs();
                size_t n = uvs.size() / 2;
                auto result = py::array_t<float>({n, size_t(2)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = uvs[i * 2];
                    buf(i, 1) = uvs[i * 2 + 1];
                }
                return result;
            },
            [](Mesh3& m, py::object obj) {
                throw std::runtime_error("Mesh3 uvs are immutable after creation");
            })

        .def_property("vertex_normals",
            [](const Mesh3& m) -> py::object {
                if (!m.has_vertex_normals()) return py::none();
                auto normals = m.get_normals();
                if (normals.empty()) return py::none();
                // Check if all normals are zero (not computed yet)
                bool all_zero = true;
                for (float f : normals) {
                    if (f != 0.0f) { all_zero = false; break; }
                }
                if (all_zero) return py::none();

                size_t n = normals.size() / 3;
                auto result = py::array_t<float>({n, size_t(3)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = normals[i * 3];
                    buf(i, 1) = normals[i * 3 + 1];
                    buf(i, 2) = normals[i * 3 + 2];
                }
                return result;
            },
            [](Mesh3& m, py::object obj) {
                throw std::runtime_error("Mesh3 vertex_normals are immutable after creation. Use compute_vertex_normals()");
            })

        .def_property("face_normals",
            [](const Mesh3& m) -> py::object {
                // Face normals not stored in tc_mesh, compute on demand if needed
                return py::none();
            },
            [](Mesh3& m, py::object obj) {
                // No-op for compatibility
            })

        .def_readwrite("source_path", &Mesh3::source_path)

        // Type property - Mesh3 always stores triangles
        .def_property_readonly("type", [](const Mesh3&) { return "triangles"; })

        // UUID property
        .def_property_readonly("uuid", [](const Mesh3& m) { return std::string(m.uuid()); })

        // tc_mesh pointer (for MeshGPU.draw)
        .def_property_readonly("tc_mesh", [](const Mesh3& m) { return m._mesh; }, py::return_value_policy::reference)

        // Name property (for debugging)
        .def_property("name",
            [](const Mesh3& m) { return std::string(m.name()); },
            [](Mesh3& m, const std::string& n) { m.set_name(n.c_str()); })

        // Version property
        .def_property_readonly("version", &Mesh3::version)

        // Methods
        .def("get_vertex_count", &Mesh3::get_vertex_count)
        .def("get_face_count", &Mesh3::get_face_count)
        .def("has_uvs", &Mesh3::has_uvs)
        .def("has_vertex_normals", &Mesh3::has_vertex_normals)
        .def("is_valid", &Mesh3::is_valid)

        .def("translate", [](Mesh3& m, py::array_t<float> offset) {
            auto buf = offset.unchecked<1>();
            m.translate(buf(0), buf(1), buf(2));
        }, py::arg("offset"))

        .def("scale", &Mesh3::scale, py::arg("factor"))

        .def("compute_vertex_normals", [](Mesh3& m) {
            m.compute_vertex_normals();
            // Return the computed normals
            auto normals = m.get_normals();
            size_t n = normals.size() / 3;
            auto result = py::array_t<float>({n, size_t(3)});
            auto buf = result.mutable_unchecked<2>();
            for (size_t i = 0; i < n; ++i) {
                buf(i, 0) = normals[i * 3];
                buf(i, 1) = normals[i * 3 + 1];
                buf(i, 2) = normals[i * 3 + 2];
            }
            return result;
        })

        .def("compute_faces_normals", [](Mesh3& m) {
            // Not implemented - face normals not stored in tc_mesh
            return py::none();
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

        .def_static("from_uuid", [](const std::string& uuid) {
            return Mesh3::from_uuid(uuid.c_str());
        }, py::arg("uuid"), "Get existing mesh from registry by UUID")

        // Serialization
        .def("direct_serialize", [](const Mesh3& m) {
            py::dict result;

            if (!m.source_path.empty()) {
                result["type"] = "path";
                result["path"] = m.source_path;
                return result;
            }

            result["type"] = "inline";
            result["uuid"] = std::string(m.uuid());

            // Vertices to nested list
            auto verts = m.get_vertices();
            size_t nv = verts.size() / 3;
            py::list verts_list;
            for (size_t i = 0; i < nv; ++i) {
                py::list v;
                v.append(verts[i * 3]);
                v.append(verts[i * 3 + 1]);
                v.append(verts[i * 3 + 2]);
                verts_list.append(v);
            }
            result["vertices"] = verts_list;

            // Triangles to nested list
            auto indices = m.get_indices();
            size_t nt = indices.size() / 3;
            py::list tris;
            for (size_t i = 0; i < nt; ++i) {
                py::list t;
                t.append(indices[i * 3]);
                t.append(indices[i * 3 + 1]);
                t.append(indices[i * 3 + 2]);
                tris.append(t);
            }
            result["triangles"] = tris;

            // Optional UVs
            if (m.has_uvs()) {
                auto uvs = m.get_uvs();
                size_t nu = uvs.size() / 2;
                py::list uvlist;
                for (size_t i = 0; i < nu; ++i) {
                    py::list uv;
                    uv.append(uvs[i * 2]);
                    uv.append(uvs[i * 2 + 1]);
                    uvlist.append(uv);
                }
                result["uvs"] = uvlist;
            }

            // Optional normals
            auto normals = m.get_normals();
            if (!normals.empty()) {
                size_t nn = normals.size() / 3;
                py::list nlist;
                for (size_t i = 0; i < nn; ++i) {
                    py::list n;
                    n.append(normals[i * 3]);
                    n.append(normals[i * 3 + 1]);
                    n.append(normals[i * 3 + 2]);
                    nlist.append(n);
                }
                result["normals"] = nlist;
            }

            return result;
        })

        .def_static("direct_deserialize", [](py::dict data) {
            // Vertices
            py::list verts = data["vertices"].cast<py::list>();
            size_t nv = verts.size();
            std::vector<float> verts_flat(nv * 3);
            for (size_t i = 0; i < nv; ++i) {
                py::list v = verts[i].cast<py::list>();
                verts_flat[i * 3] = v[0].cast<float>();
                verts_flat[i * 3 + 1] = v[1].cast<float>();
                verts_flat[i * 3 + 2] = v[2].cast<float>();
            }

            // Triangles
            py::list tris = data["triangles"].cast<py::list>();
            size_t nt = tris.size();
            std::vector<uint32_t> tris_flat(nt * 3);
            for (size_t i = 0; i < nt; ++i) {
                py::list t = tris[i].cast<py::list>();
                tris_flat[i * 3] = t[0].cast<uint32_t>();
                tris_flat[i * 3 + 1] = t[1].cast<uint32_t>();
                tris_flat[i * 3 + 2] = t[2].cast<uint32_t>();
            }

            // Optional UVs
            std::vector<float> uvs_flat;
            if (data.contains("uvs")) {
                py::list uvlist = data["uvs"].cast<py::list>();
                size_t nu = uvlist.size();
                uvs_flat.resize(nu * 2);
                for (size_t i = 0; i < nu; ++i) {
                    py::list uv = uvlist[i].cast<py::list>();
                    uvs_flat[i * 2] = uv[0].cast<float>();
                    uvs_flat[i * 2 + 1] = uv[1].cast<float>();
                }
            }

            // Optional normals
            std::vector<float> normals_flat;
            if (data.contains("normals")) {
                py::list nlist = data["normals"].cast<py::list>();
                size_t nn = nlist.size();
                normals_flat.resize(nn * 3);
                for (size_t i = 0; i < nn; ++i) {
                    py::list n = nlist[i].cast<py::list>();
                    normals_flat[i * 3] = n[0].cast<float>();
                    normals_flat[i * 3 + 1] = n[1].cast<float>();
                    normals_flat[i * 3 + 2] = n[2].cast<float>();
                }
            }

            // Get name from path or uuid
            std::string mesh_name;
            if (data.contains("path")) {
                mesh_name = data["path"].cast<std::string>();
            } else if (data.contains("uuid")) {
                mesh_name = data["uuid"].cast<std::string>();
            } else {
                mesh_name = "deserialized_mesh";
            }

            Mesh3 mesh(
                mesh_name.c_str(),
                verts_flat.data(), nv,
                tris_flat.data(), tris_flat.size(),
                normals_flat.empty() ? nullptr : normals_flat.data(),
                uvs_flat.empty() ? nullptr : uvs_flat.data()
            );

            // Source path
            if (data.contains("path")) {
                mesh.source_path = data["path"].cast<std::string>();
            }

            return mesh;
        }, py::arg("data"))

        .def("__repr__", [](const Mesh3& m) {
            return "<Mesh3 vertices=" + std::to_string(m.get_vertex_count()) +
                   " triangles=" + std::to_string(m.get_face_count()) +
                   " uuid=" + std::string(m.uuid()) + ">";
        });

    // SkinnedMesh3 - extends Mesh3 with skeletal animation data
    py::class_<SkinnedMesh3, Mesh3>(m, "SkinnedMesh3")
        .def(py::init<>())
        .def(py::init([](std::string name, py::array_t<float> vertices, py::array_t<uint32_t> triangles,
                         py::object uvs_obj, py::object normals_obj,
                         py::object joint_indices_obj, py::object joint_weights_obj,
                         py::object source_path_obj) {
            // Get vertex data (Nx3)
            auto v_buf = vertices.unchecked<2>();
            size_t num_verts = v_buf.shape(0);

            std::vector<float> verts_flat(num_verts * 3);
            for (size_t i = 0; i < num_verts; ++i) {
                verts_flat[i * 3] = v_buf(i, 0);
                verts_flat[i * 3 + 1] = v_buf(i, 1);
                verts_flat[i * 3 + 2] = v_buf(i, 2);
            }

            // Get triangle data (Mx3)
            auto t_buf = triangles.unchecked<2>();
            size_t num_tris = t_buf.shape(0);

            std::vector<uint32_t> tris_flat(num_tris * 3);
            for (size_t i = 0; i < num_tris; ++i) {
                tris_flat[i * 3] = t_buf(i, 0);
                tris_flat[i * 3 + 1] = t_buf(i, 1);
                tris_flat[i * 3 + 2] = t_buf(i, 2);
            }

            // Optional normals (Nx3)
            std::vector<float> normals_flat;
            if (!normals_obj.is_none()) {
                auto n_arr = normals_obj.cast<py::array_t<float>>();
                auto n_buf = n_arr.unchecked<2>();
                size_t n = n_buf.shape(0);
                normals_flat.resize(n * 3);
                for (size_t i = 0; i < n; ++i) {
                    normals_flat[i * 3] = n_buf(i, 0);
                    normals_flat[i * 3 + 1] = n_buf(i, 1);
                    normals_flat[i * 3 + 2] = n_buf(i, 2);
                }
            }

            // Optional UVs (Nx2)
            std::vector<float> uvs_flat;
            if (!uvs_obj.is_none()) {
                auto uv_arr = uvs_obj.cast<py::array_t<float>>();
                auto uv_buf = uv_arr.unchecked<2>();
                size_t n = uv_buf.shape(0);
                uvs_flat.resize(n * 2);
                for (size_t i = 0; i < n; ++i) {
                    uvs_flat[i * 2] = uv_buf(i, 0);
                    uvs_flat[i * 2 + 1] = uv_buf(i, 1);
                }
            }

            // Joint indices (Nx4)
            std::vector<float> joints_flat;
            if (!joint_indices_obj.is_none()) {
                auto ji_arr = joint_indices_obj.cast<py::array_t<float>>();
                auto ji_buf = ji_arr.unchecked<2>();
                size_t n = ji_buf.shape(0);
                joints_flat.resize(n * 4);
                for (size_t i = 0; i < n; ++i) {
                    joints_flat[i * 4] = ji_buf(i, 0);
                    joints_flat[i * 4 + 1] = ji_buf(i, 1);
                    joints_flat[i * 4 + 2] = ji_buf(i, 2);
                    joints_flat[i * 4 + 3] = ji_buf(i, 3);
                }
            }

            // Joint weights (Nx4)
            std::vector<float> weights_flat;
            if (!joint_weights_obj.is_none()) {
                auto jw_arr = joint_weights_obj.cast<py::array_t<float>>();
                auto jw_buf = jw_arr.unchecked<2>();
                size_t n = jw_buf.shape(0);
                weights_flat.resize(n * 4);
                for (size_t i = 0; i < n; ++i) {
                    weights_flat[i * 4] = jw_buf(i, 0);
                    weights_flat[i * 4 + 1] = jw_buf(i, 1);
                    weights_flat[i * 4 + 2] = jw_buf(i, 2);
                    weights_flat[i * 4 + 3] = jw_buf(i, 3);
                }
            }

            SkinnedMesh3 mesh(
                name.c_str(),
                verts_flat.data(), num_verts,
                tris_flat.data(), tris_flat.size(),
                normals_flat.empty() ? nullptr : normals_flat.data(),
                uvs_flat.empty() ? nullptr : uvs_flat.data(),
                joints_flat.empty() ? nullptr : joints_flat.data(),
                weights_flat.empty() ? nullptr : weights_flat.data()
            );

            // Store source path if provided
            if (!source_path_obj.is_none()) {
                mesh.source_path = source_path_obj.cast<std::string>();
            }

            return mesh;
        }),
             py::arg("name"),
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
                auto joints = m.get_joint_indices();
                if (joints.empty()) return py::none();
                size_t n = joints.size() / 4;
                auto result = py::array_t<float>({n, size_t(4)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = joints[i * 4];
                    buf(i, 1) = joints[i * 4 + 1];
                    buf(i, 2) = joints[i * 4 + 2];
                    buf(i, 3) = joints[i * 4 + 3];
                }
                return result;
            },
            [](SkinnedMesh3& m, py::object obj) {
                if (obj.is_none()) return;
                auto arr = obj.cast<py::array_t<float>>();
                auto buf = arr.unchecked<2>();
                size_t n = buf.shape(0);
                std::vector<float> data(n * 4);
                for (size_t i = 0; i < n; ++i) {
                    data[i * 4] = buf(i, 0);
                    data[i * 4 + 1] = buf(i, 1);
                    data[i * 4 + 2] = buf(i, 2);
                    data[i * 4 + 3] = buf(i, 3);
                }
                m.set_joint_indices(data.data(), n);
            })

        // Joint weights property (Nx4)
        .def_property("joint_weights",
            [](const SkinnedMesh3& m) -> py::object {
                auto weights = m.get_joint_weights();
                if (weights.empty()) return py::none();
                size_t n = weights.size() / 4;
                auto result = py::array_t<float>({n, size_t(4)});
                auto buf = result.mutable_unchecked<2>();
                for (size_t i = 0; i < n; ++i) {
                    buf(i, 0) = weights[i * 4];
                    buf(i, 1) = weights[i * 4 + 1];
                    buf(i, 2) = weights[i * 4 + 2];
                    buf(i, 3) = weights[i * 4 + 3];
                }
                return result;
            },
            [](SkinnedMesh3& m, py::object obj) {
                if (obj.is_none()) return;
                auto arr = obj.cast<py::array_t<float>>();
                auto buf = arr.unchecked<2>();
                size_t n = buf.shape(0);
                std::vector<float> data(n * 4);
                for (size_t i = 0; i < n; ++i) {
                    data[i * 4] = buf(i, 0);
                    data[i * 4 + 1] = buf(i, 1);
                    data[i * 4 + 2] = buf(i, 2);
                    data[i * 4 + 3] = buf(i, 3);
                }
                m.set_joint_weights(data.data(), n);
            })

        .def("has_skinning", &SkinnedMesh3::has_skinning)
        .def("normalize_weights", &SkinnedMesh3::normalize_weights)
        .def("init_default_skinning", &SkinnedMesh3::init_default_skinning)

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
                   " skinning=" + (m.has_skinning() ? "yes" : "no") +
                   " uuid=" + std::string(m.uuid()) + ">";
        });

    // =========================================================================
    // TcMesh - Low-level mesh API for Python-based mesh types (like VoxelMesh)
    // =========================================================================

    // TcAttribType enum
    py::enum_<tc_attrib_type>(m, "TcAttribType")
        .value("FLOAT32", TC_ATTRIB_FLOAT32)
        .value("INT32", TC_ATTRIB_INT32)
        .value("UINT32", TC_ATTRIB_UINT32)
        .value("INT16", TC_ATTRIB_INT16)
        .value("UINT16", TC_ATTRIB_UINT16)
        .value("INT8", TC_ATTRIB_INT8)
        .value("UINT8", TC_ATTRIB_UINT8);

    // TcVertexLayout - flexible vertex format builder
    py::class_<tc_vertex_layout>(m, "TcVertexLayout")
        .def(py::init([]() {
            tc_vertex_layout layout;
            tc_vertex_layout_init(&layout);
            return layout;
        }))
        .def_readonly("stride", &tc_vertex_layout::stride)
        .def_readonly("attrib_count", &tc_vertex_layout::attrib_count)
        .def("add", [](tc_vertex_layout& self, const std::string& name, uint8_t size, tc_attrib_type type) {
            return tc_vertex_layout_add(&self, name.c_str(), size, type);
        }, py::arg("name"), py::arg("size"), py::arg("type"))
        .def("find", [](const tc_vertex_layout& self, const std::string& name) -> py::object {
            const tc_vertex_attrib* attr = tc_vertex_layout_find(&self, name.c_str());
            if (!attr) return py::none();
            py::dict d;
            d["name"] = std::string(attr->name);
            d["size"] = attr->size;
            d["type"] = static_cast<tc_attrib_type>(attr->type);
            d["offset"] = attr->offset;
            return d;
        }, py::arg("name"))
        .def_static("pos_normal_uv", []() { return tc_vertex_layout_pos_normal_uv(); })
        .def_static("pos_normal_uv_color", []() { return tc_vertex_layout_pos_normal_uv_color(); })
        .def_static("skinned", []() { return tc_vertex_layout_skinned(); });

    // TcMesh - handle to tc_mesh with reference counting
    // This is for Python-based mesh classes like VoxelMesh
    py::class_<tc_mesh>(m, "TcMesh")
        .def_readonly("vertex_count", &tc_mesh::vertex_count)
        .def_readonly("index_count", &tc_mesh::index_count)
        .def_readonly("version", &tc_mesh::version)
        .def_readonly("ref_count", &tc_mesh::ref_count)
        .def_property_readonly("uuid", [](const tc_mesh& m) { return std::string(m.uuid); })
        .def_property_readonly("name", [](const tc_mesh& m) { return m.name ? std::string(m.name) : ""; })
        .def_property_readonly("stride", [](const tc_mesh& m) { return m.layout.stride; })
        .def_property_readonly("layout", [](const tc_mesh& m) { return m.layout; })
        .def("get_vertices_buffer", [](const tc_mesh& m) -> py::object {
            if (!m.vertices || m.vertex_count == 0) return py::none();
            size_t total_floats = (m.vertex_count * m.layout.stride) / sizeof(float);
            auto result = py::array_t<float>(total_floats);
            auto buf = result.mutable_unchecked<1>();
            const float* src = (const float*)m.vertices;
            for (size_t i = 0; i < total_floats; ++i) {
                buf(i) = src[i];
            }
            return result;
        })
        .def("get_indices_buffer", [](const tc_mesh& m) -> py::object {
            if (!m.indices || m.index_count == 0) return py::none();
            auto result = py::array_t<uint32_t>(m.index_count);
            auto buf = result.mutable_unchecked<1>();
            for (size_t i = 0; i < m.index_count; ++i) {
                buf(i) = m.indices[i];
            }
            return result;
        });

    // TcMeshHandle - RAII wrapper for tc_mesh* with reference counting
    // This is the main class for Python-based mesh types
    struct TcMeshHandle {
        tc_mesh* mesh = nullptr;

        TcMeshHandle() = default;
        TcMeshHandle(tc_mesh* m) : mesh(m) {}
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

    py::class_<TcMeshHandle>(m, "TcMeshHandle")
        .def(py::init<>())
        .def_property_readonly("is_valid", &TcMeshHandle::is_valid)
        .def_property_readonly("uuid", &TcMeshHandle::uuid)
        .def_property_readonly("name", &TcMeshHandle::name)
        .def_property_readonly("version", &TcMeshHandle::version)
        .def_property_readonly("vertex_count", &TcMeshHandle::vertex_count)
        .def_property_readonly("index_count", &TcMeshHandle::index_count)
        .def_property_readonly("stride", &TcMeshHandle::stride)
        .def_property_readonly("mesh", [](const TcMeshHandle& h) -> py::object {
            if (!h.mesh) return py::none();
            return py::cast(h.mesh, py::return_value_policy::reference);
        })
        .def("bump_version", &TcMeshHandle::bump_version)
        .def("get_vertices_buffer", [](const TcMeshHandle& h) -> py::object {
            if (!h.mesh || !h.mesh->vertices || h.mesh->vertex_count == 0) return py::none();
            size_t total_floats = (h.mesh->vertex_count * h.mesh->layout.stride) / sizeof(float);
            auto result = py::array_t<float>(total_floats);
            auto buf = result.mutable_unchecked<1>();
            const float* src = (const float*)h.mesh->vertices;
            for (size_t i = 0; i < total_floats; ++i) {
                buf(i) = src[i];
            }
            return result;
        })
        .def("get_indices_buffer", [](const TcMeshHandle& h) -> py::object {
            if (!h.mesh || !h.mesh->indices || h.mesh->index_count == 0) return py::none();
            auto result = py::array_t<uint32_t>(h.mesh->index_count);
            auto buf = result.mutable_unchecked<1>();
            for (size_t i = 0; i < h.mesh->index_count; ++i) {
                buf(i) = h.mesh->indices[i];
            }
            return result;
        })
        .def("__repr__", [](const TcMeshHandle& h) {
            if (!h.mesh) return std::string("<TcMeshHandle invalid>");
            return "<TcMeshHandle vertices=" + std::to_string(h.mesh->vertex_count) +
                   " indices=" + std::to_string(h.mesh->index_count) +
                   " uuid=" + std::string(h.mesh->uuid) + ">";
        });

    // Module-level functions for mesh registry
    m.def("tc_mesh_compute_uuid", [](py::array_t<float> vertices, py::array_t<uint32_t> indices) {
        auto v_buf = vertices.request();
        auto i_buf = indices.request();
        char uuid[40];
        tc_mesh_compute_uuid(v_buf.ptr, v_buf.size * sizeof(float),
                            (const uint32_t*)i_buf.ptr, i_buf.size, uuid);
        return std::string(uuid);
    }, py::arg("vertices"), py::arg("indices"),
       "Compute UUID from vertex and index data (hash-based)");

    m.def("tc_mesh_get_or_create", [](const std::string& uuid) {
        fprintf(stderr, "tc_mesh_get_or_create: uuid=%s\n", uuid.c_str());
        tc_mesh* mesh = tc_mesh_get_or_create(uuid.c_str());
        return TcMeshHandle(mesh);  // TcMeshHandle takes ownership
    }, py::arg("uuid"),
       "Get existing mesh or create new one (increments ref count)");

    m.def("tc_mesh_set_data", [](TcMeshHandle& handle, const std::string& name,
                                  py::array_t<float> vertices, size_t vertex_count,
                                  const tc_vertex_layout& layout,
                                  py::array_t<uint32_t> indices) {
        if (!handle.mesh) return false;
        auto v_buf = vertices.request();
        auto i_buf = indices.request();
        return tc_mesh_set_data(handle.mesh, name.c_str(),
                               v_buf.ptr, vertex_count, &layout,
                               (const uint32_t*)i_buf.ptr, i_buf.size);
    }, py::arg("handle"), py::arg("name"), py::arg("vertices"),
       py::arg("vertex_count"), py::arg("layout"), py::arg("indices"),
       "Set mesh vertex and index data");

    m.def("tc_mesh_contains", [](const std::string& uuid) {
        return tc_mesh_contains(uuid.c_str());
    }, py::arg("uuid"), "Check if mesh exists in registry");

    m.def("tc_mesh_count", []() {
        return tc_mesh_count();
    }, "Get number of meshes in registry");
}

} // namespace termin
