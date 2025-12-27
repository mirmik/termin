#include "common.hpp"
#include "termin/render/material.hpp"
#include "termin/assets/handles.hpp"
#include "termin/render/shader_parser.hpp"
#include "termin/render/render_state.hpp"
#include "termin/render/render.hpp"

namespace termin {

void bind_material(py::module_& m) {
    // MaterialPhase
    py::class_<MaterialPhase, std::shared_ptr<MaterialPhase>>(m, "MaterialPhase")
        .def(py::init<>())
        .def(py::init([](std::shared_ptr<ShaderProgram> shader, const RenderState& rs,
                         const std::string& phase_mark, int priority) {
            return std::make_shared<MaterialPhase>(shader, rs, phase_mark, priority);
        }), py::arg("shader"), py::arg("render_state") = RenderState::opaque(),
            py::arg("phase_mark") = "opaque", py::arg("priority") = 0)
        // Python-compatible kwargs constructor (supports shader_programm, color)
        .def(py::init([](py::kwargs kwargs) {
            std::shared_ptr<ShaderProgram> shader;
            if (kwargs.contains("shader_programm")) {
                shader = kwargs["shader_programm"].cast<std::shared_ptr<ShaderProgram>>();
            } else if (kwargs.contains("shader")) {
                shader = kwargs["shader"].cast<std::shared_ptr<ShaderProgram>>();
            }
            if (!shader) {
                throw std::runtime_error("MaterialPhase requires 'shader' or 'shader_programm' argument");
            }

            RenderState rs = RenderState::opaque();
            if (kwargs.contains("render_state")) {
                rs = kwargs["render_state"].cast<RenderState>();
            }

            std::string phase_mark = "opaque";
            if (kwargs.contains("phase_mark")) {
                phase_mark = kwargs["phase_mark"].cast<std::string>();
            }

            int priority = 0;
            if (kwargs.contains("priority")) {
                priority = kwargs["priority"].cast<int>();
            }

            auto phase = std::make_shared<MaterialPhase>(shader, rs, phase_mark, priority);

            // Set color
            if (kwargs.contains("color") && !kwargs["color"].is_none()) {
                auto arr = py::array_t<float>::ensure(kwargs["color"]);
                auto buf = arr.unchecked<1>();
                phase->set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
            }

            // Set textures
            if (kwargs.contains("textures") && !kwargs["textures"].is_none()) {
                py::dict tex_dict = kwargs["textures"].cast<py::dict>();
                for (auto item : tex_dict) {
                    std::string key = item.first.cast<std::string>();
                    phase->textures[key] = item.second.cast<TextureHandle>();
                }
            }

            // Set uniforms
            if (kwargs.contains("uniforms") && !kwargs["uniforms"].is_none()) {
                py::dict uniforms_dict = kwargs["uniforms"].cast<py::dict>();
                for (auto item : uniforms_dict) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::bool_>(val)) {
                        phase->uniforms[key] = val.cast<bool>();
                    } else if (py::isinstance<py::int_>(val)) {
                        phase->uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::float_>(val)) {
                        phase->uniforms[key] = val.cast<float>();
                    }
                }
            }

            return phase;
        }))
        .def_readwrite("shader", &MaterialPhase::shader)
        .def_readwrite("shader_programm", &MaterialPhase::shader)  // Python compatibility alias
        .def_readwrite("render_state", &MaterialPhase::render_state)
        .def_property("color",
            [](MaterialPhase& self) -> py::object {
                if (!self.color.has_value()) return py::none();
                Vec4 c = self.color.value();
                auto result = py::array_t<float>(4);
                auto buf = result.mutable_unchecked<1>();
                buf(0) = static_cast<float>(c.x);
                buf(1) = static_cast<float>(c.y);
                buf(2) = static_cast<float>(c.z);
                buf(3) = static_cast<float>(c.w);
                return result;
            },
            [](MaterialPhase& self, py::object val) {
                if (val.is_none()) {
                    self.color = std::nullopt;
                } else {
                    auto arr = py::array_t<float>::ensure(val);
                    auto buf = arr.unchecked<1>();
                    self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
                }
            })
        .def_readwrite("phase_mark", &MaterialPhase::phase_mark)
        .def_readwrite("priority", &MaterialPhase::priority)
        .def_readwrite("textures", &MaterialPhase::textures)
        .def_property("uniforms",
            [](MaterialPhase& self) -> py::dict {
                py::dict result;
                for (const auto& [key, val] : self.uniforms) {
                    std::visit([&](auto&& arg) {
                        using T = std::decay_t<decltype(arg)>;
                        if constexpr (std::is_same_v<T, bool>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, int>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, float>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, Vec3>) {
                            auto arr = py::array_t<float>(3);
                            auto buf = arr.mutable_unchecked<1>();
                            buf(0) = arg.x;
                            buf(1) = arg.y;
                            buf(2) = arg.z;
                            result[key.c_str()] = arr;
                        } else if constexpr (std::is_same_v<T, Vec4>) {
                            auto arr = py::array_t<float>(4);
                            auto buf = arr.mutable_unchecked<1>();
                            buf(0) = arg.x;
                            buf(1) = arg.y;
                            buf(2) = arg.z;
                            buf(3) = arg.w;
                            result[key.c_str()] = arr;
                        }
                    }, val);
                }
                return result;
            },
            [](MaterialPhase& self, py::dict uniforms) {
                for (auto item : uniforms) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::bool_>(val)) {
                        self.uniforms[key] = val.cast<bool>();
                    } else if (py::isinstance<py::int_>(val)) {
                        self.uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::float_>(val)) {
                        self.uniforms[key] = val.cast<float>();
                    } else if (py::isinstance<py::array>(val)) {
                        auto arr = py::array_t<float>::ensure(val);
                        auto buf = arr.request();
                        if (buf.size == 3) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            self.uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (buf.size == 4) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            self.uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            })
        .def("set_texture", [](MaterialPhase& self, const std::string& name, const TextureHandle& tex) {
            self.textures[name] = tex;
        })
        .def("set_param", [](MaterialPhase& self, const std::string& name, py::object value) {
            if (py::isinstance<py::bool_>(value)) {
                self.set_param(name, value.cast<bool>());
            } else if (py::isinstance<py::int_>(value)) {
                self.set_param(name, value.cast<int>());
            } else if (py::isinstance<py::float_>(value)) {
                self.set_param(name, value.cast<float>());
            } else if (py::isinstance<py::array>(value)) {
                auto arr = py::array_t<float>::ensure(value);
                auto buf = arr.request();
                if (buf.size == 3) {
                    auto* ptr = static_cast<float*>(buf.ptr);
                    self.set_param(name, Vec3{ptr[0], ptr[1], ptr[2]});
                } else if (buf.size == 4) {
                    auto* ptr = static_cast<float*>(buf.ptr);
                    self.set_param(name, Vec4{ptr[0], ptr[1], ptr[2], ptr[3]});
                }
            }
        })
        .def("set_color", [](MaterialPhase& self, py::array_t<float> rgba) {
            auto buf = rgba.unchecked<1>();
            self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
        })
        .def("update_color", [](MaterialPhase& self, py::array_t<float> rgba) {
            auto buf = rgba.unchecked<1>();
            self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
        })
        .def("apply", [](MaterialPhase& self,
                         py::array_t<float> model,
                         py::array_t<float> view,
                         py::array_t<float> proj,
                         GraphicsBackend* graphics,
                         int64_t context_key) {
            auto m_buf = model.unchecked<2>();
            auto v_buf = view.unchecked<2>();
            auto p_buf = proj.unchecked<2>();

            Mat44f m_mat, v_mat, p_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    m_mat.data[col * 4 + row] = m_buf(row, col);
                    v_mat.data[col * 4 + row] = v_buf(row, col);
                    p_mat.data[col * 4 + row] = p_buf(row, col);
                }
            }
            self.apply(m_mat, v_mat, p_mat, graphics, context_key);
        }, py::arg("model"), py::arg("view"), py::arg("projection"),
           py::arg("graphics"), py::arg("context_key") = 0)
        .def("apply_state", &MaterialPhase::apply_state)
        .def("copy", &MaterialPhase::copy)
        // serialize - serialize MaterialPhase to dict
        .def("serialize", [](const MaterialPhase& self) -> py::dict {
            py::dict result;
            result["phase_mark"] = self.phase_mark;
            result["priority"] = self.priority;

            // Color
            if (self.color.has_value()) {
                Vec4 c = self.color.value();
                py::list col_list;
                col_list.append(c.x);
                col_list.append(c.y);
                col_list.append(c.z);
                col_list.append(c.w);
                result["color"] = col_list;
            } else {
                result["color"] = py::none();
            }

            // Uniforms
            py::dict uniforms_dict;
            for (const auto& [key, val] : self.uniforms) {
                std::visit([&](auto&& arg) {
                    using T = std::decay_t<decltype(arg)>;
                    if constexpr (std::is_same_v<T, bool>) {
                        uniforms_dict[key.c_str()] = arg;
                    } else if constexpr (std::is_same_v<T, int>) {
                        uniforms_dict[key.c_str()] = arg;
                    } else if constexpr (std::is_same_v<T, float>) {
                        uniforms_dict[key.c_str()] = arg;
                    } else if constexpr (std::is_same_v<T, Vec3>) {
                        py::list vec;
                        vec.append(arg.x);
                        vec.append(arg.y);
                        vec.append(arg.z);
                        uniforms_dict[key.c_str()] = vec;
                    } else if constexpr (std::is_same_v<T, Vec4>) {
                        py::list vec;
                        vec.append(arg.x);
                        vec.append(arg.y);
                        vec.append(arg.z);
                        vec.append(arg.w);
                        uniforms_dict[key.c_str()] = vec;
                    }
                }, val);
            }
            result["uniforms"] = uniforms_dict;

            // Textures - store source_path
            py::dict textures_dict;
            for (const auto& [key, tex] : self.textures) {
                std::string path = tex.source_path();
                if (!path.empty()) {
                    textures_dict[key.c_str()] = path;
                }
            }
            result["textures"] = textures_dict;

            // Render state
            py::dict rs_dict;
            rs_dict["depth_test"] = self.render_state.depth_test;
            rs_dict["depth_write"] = self.render_state.depth_write;
            rs_dict["blend"] = self.render_state.blend;
            rs_dict["cull"] = self.render_state.cull;
            result["render_state"] = rs_dict;

            // Shader sources
            py::dict shader_dict;
            if (self.shader) {
                shader_dict["vertex"] = self.shader->vertex_source();
                shader_dict["fragment"] = self.shader->fragment_source();
                shader_dict["geometry"] = self.shader->geometry_source();
            }
            result["shader"] = shader_dict;

            return result;
        })
        // deserialize - deserialize MaterialPhase from dict
        .def_static("deserialize", [](py::dict data, py::object context) -> std::shared_ptr<MaterialPhase> {
            // Get shader sources
            py::dict shader_data = data["shader"].cast<py::dict>();
            std::string vs = shader_data["vertex"].cast<std::string>();
            std::string fs = shader_data["fragment"].cast<std::string>();
            std::string gs = shader_data.contains("geometry") ?
                shader_data["geometry"].cast<std::string>() : "";

            auto shader = std::make_shared<ShaderProgram>(vs, fs, gs, "");

            // Get render state
            RenderState rs;
            if (data.contains("render_state")) {
                py::dict rs_data = data["render_state"].cast<py::dict>();
                rs.depth_test = rs_data.contains("depth_test") ?
                    rs_data["depth_test"].cast<bool>() : true;
                rs.depth_write = rs_data.contains("depth_write") ?
                    rs_data["depth_write"].cast<bool>() : true;
                rs.blend = rs_data.contains("blend") ?
                    rs_data["blend"].cast<bool>() : false;
                rs.cull = rs_data.contains("cull") ?
                    rs_data["cull"].cast<bool>() : true;
            }

            std::string phase_mark = data.contains("phase_mark") ?
                data["phase_mark"].cast<std::string>() : "opaque";
            int priority = data.contains("priority") ?
                data["priority"].cast<int>() : 0;

            auto phase = std::make_shared<MaterialPhase>(shader, rs, phase_mark, priority);

            // Color
            if (data.contains("color") && !data["color"].is_none()) {
                py::list color_list = data["color"].cast<py::list>();
                if (py::len(color_list) >= 4) {
                    phase->set_color(Vec4{
                        color_list[0].cast<float>(),
                        color_list[1].cast<float>(),
                        color_list[2].cast<float>(),
                        color_list[3].cast<float>()
                    });
                }
            }

            // Uniforms
            if (data.contains("uniforms")) {
                py::dict uniforms_dict = data["uniforms"].cast<py::dict>();
                for (auto item : uniforms_dict) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::list>(val)) {
                        py::list lst = val.cast<py::list>();
                        if (py::len(lst) == 3) {
                            phase->uniforms[key] = Vec3{
                                lst[0].cast<float>(),
                                lst[1].cast<float>(),
                                lst[2].cast<float>()
                            };
                        } else if (py::len(lst) == 4) {
                            phase->uniforms[key] = Vec4{
                                lst[0].cast<float>(),
                                lst[1].cast<float>(),
                                lst[2].cast<float>(),
                                lst[3].cast<float>()
                            };
                        }
                    } else if (py::isinstance<py::float_>(val)) {
                        phase->uniforms[key] = val.cast<float>();
                    } else if (py::isinstance<py::int_>(val)) {
                        phase->uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::bool_>(val)) {
                        phase->uniforms[key] = val.cast<bool>();
                    }
                }
            }

            // Textures (if context provided)
            if (data.contains("textures") && !context.is_none()) {
                py::dict textures_dict = data["textures"].cast<py::dict>();
                for (auto item : textures_dict) {
                    std::string key = item.first.cast<std::string>();
                    std::string path = item.second.cast<std::string>();
                    if (py::hasattr(context, "load_texture")) {
                        phase->textures[key] = context.attr("load_texture")(path).cast<TextureHandle>();
                    }
                }
            }

            return phase;
        }, py::arg("data"), py::arg("context") = py::none())
        // from_shader_phase - create MaterialPhase from parsed ShaderPhase
        .def_static("from_shader_phase", [](
            const ShaderPhase& shader_phase,
            py::object color,
            py::object textures,
            py::object extra_uniforms
        ) -> MaterialPhase {
            // 1. Get shader sources from stages
            auto it_vert = shader_phase.stages.find("vertex");
            auto it_frag = shader_phase.stages.find("fragment");
            auto it_geom = shader_phase.stages.find("geometry");

            if (it_vert == shader_phase.stages.end()) {
                throw std::runtime_error("Phase has no vertex stage");
            }
            if (it_frag == shader_phase.stages.end()) {
                throw std::runtime_error("Phase has no fragment stage");
            }

            std::string vs = it_vert->second.source;
            std::string fs = it_frag->second.source;
            std::string gs = (it_geom != shader_phase.stages.end()) ? it_geom->second.source : "";

            auto shader = std::make_shared<ShaderProgram>(vs, fs, gs, "");

            // 2. Build RenderState from gl-flags
            RenderState rs;
            rs.depth_write = shader_phase.gl_depth_mask.value_or(true);
            rs.depth_test = shader_phase.gl_depth_test.value_or(true);
            rs.blend = shader_phase.gl_blend.value_or(false);
            rs.cull = shader_phase.gl_cull.value_or(true);

            MaterialPhase phase(shader, rs, shader_phase.phase_mark, shader_phase.priority);

            // 3. Apply uniforms from defaults
            for (const auto& prop : shader_phase.uniforms) {
                if (std::holds_alternative<std::monostate>(prop.default_value)) continue;

                if (std::holds_alternative<bool>(prop.default_value)) {
                    phase.uniforms[prop.name] = std::get<bool>(prop.default_value);
                } else if (std::holds_alternative<int>(prop.default_value)) {
                    phase.uniforms[prop.name] = std::get<int>(prop.default_value);
                } else if (std::holds_alternative<double>(prop.default_value)) {
                    phase.uniforms[prop.name] = static_cast<float>(std::get<double>(prop.default_value));
                } else if (std::holds_alternative<std::vector<double>>(prop.default_value)) {
                    const auto& vec = std::get<std::vector<double>>(prop.default_value);
                    if (vec.size() == 3) {
                        phase.uniforms[prop.name] = Vec3{vec[0], vec[1], vec[2]};
                    } else if (vec.size() == 4) {
                        phase.uniforms[prop.name] = Vec4{vec[0], vec[1], vec[2], vec[3]};
                    }
                }
            }

            // 4. Apply extra_uniforms
            if (!extra_uniforms.is_none()) {
                py::dict extras = extra_uniforms.cast<py::dict>();
                for (auto item : extras) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::bool_>(val)) {
                        phase.uniforms[key] = val.cast<bool>();
                    } else if (py::isinstance<py::int_>(val)) {
                        phase.uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::float_>(val)) {
                        phase.uniforms[key] = val.cast<float>();
                    } else if (py::isinstance<py::array>(val)) {
                        auto arr = py::array_t<float>::ensure(val);
                        auto buf = arr.request();
                        if (buf.size == 3) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            phase.uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (buf.size == 4) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            phase.uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            }

            // 5. Set textures (use white texture as default for Texture properties)
            py::object white_tex_fn = py::module_::import("termin.visualization.core.texture_handle").attr("get_white_texture_handle");
            TextureHandle white_tex = white_tex_fn().cast<TextureHandle>();

            for (const auto& prop : shader_phase.uniforms) {
                if (prop.property_type == "Texture") {
                    phase.textures[prop.name] = white_tex;
                }
            }

            // Override with provided textures
            if (!textures.is_none()) {
                py::dict tex_dict = textures.cast<py::dict>();
                for (auto item : tex_dict) {
                    std::string key = item.first.cast<std::string>();
                    phase.textures[key] = item.second.cast<TextureHandle>();
                }
            }

            // 6. Set color
            if (!color.is_none()) {
                auto arr = py::array_t<float>::ensure(color);
                auto buf = arr.unchecked<1>();
                phase.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
            }

            return phase;
        }, py::arg("shader_phase"),
           py::arg("color") = py::none(),
           py::arg("textures") = py::none(),
           py::arg("extra_uniforms") = py::none());

    // Material
    py::class_<Material, std::shared_ptr<Material>>(m, "Material")
        .def(py::init<>())
        .def(py::init([](std::shared_ptr<ShaderProgram> shader, const RenderState& rs,
                         const std::string& phase_mark, int priority) {
            return std::make_shared<Material>(shader, rs, phase_mark, priority);
        }), py::arg("shader"), py::arg("render_state") = RenderState::opaque(),
            py::arg("phase_mark") = "opaque", py::arg("priority") = 0)
        // Python-compatible kwargs constructor
        .def(py::init([](py::kwargs kwargs) {
            // Get default shader if not provided
            std::shared_ptr<ShaderProgram> shader;
            if (kwargs.contains("shader")) {
                shader = kwargs["shader"].cast<std::shared_ptr<ShaderProgram>>();
            } else {
                // Import default shader
                py::object shader_mod = py::module_::import("termin.visualization.render.materials.default_material");
                shader = shader_mod.attr("default_shader")().cast<std::shared_ptr<ShaderProgram>>();
            }

            RenderState rs = RenderState::opaque();
            if (kwargs.contains("render_state")) {
                rs = kwargs["render_state"].cast<RenderState>();
            }

            std::string phase_mark = "opaque";
            if (kwargs.contains("phase_mark")) {
                phase_mark = kwargs["phase_mark"].cast<std::string>();
            }

            int priority = 0;
            if (kwargs.contains("priority")) {
                priority = kwargs["priority"].cast<int>();
            }

            auto mat = std::make_shared<Material>(shader, rs, phase_mark, priority);

            if (kwargs.contains("name")) {
                mat->name = kwargs["name"].cast<std::string>();
            }
            if (kwargs.contains("source_path")) {
                mat->source_path = kwargs["source_path"].cast<std::string>();
            }
            if (kwargs.contains("shader_name")) {
                mat->shader_name = kwargs["shader_name"].cast<std::string>();
            }

            // Set color
            if (kwargs.contains("color")) {
                auto arr = py::array_t<float>::ensure(kwargs["color"]);
                auto buf = arr.unchecked<1>();
                mat->set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
            }

            // Set textures
            if (kwargs.contains("textures") && !kwargs["textures"].is_none()) {
                py::dict tex_dict = kwargs["textures"].cast<py::dict>();
                for (auto item : tex_dict) {
                    std::string key = item.first.cast<std::string>();
                    mat->default_phase().textures[key] = item.second.cast<TextureHandle>();
                }
            }

            // Set uniforms
            if (kwargs.contains("uniforms") && !kwargs["uniforms"].is_none()) {
                py::dict uniforms_dict = kwargs["uniforms"].cast<py::dict>();
                for (auto item : uniforms_dict) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::bool_>(val)) {
                        mat->default_phase().uniforms[key] = val.cast<bool>();
                    } else if (py::isinstance<py::int_>(val)) {
                        mat->default_phase().uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::float_>(val)) {
                        mat->default_phase().uniforms[key] = val.cast<float>();
                    } else if (py::isinstance<py::array>(val)) {
                        auto arr = py::array_t<float>::ensure(val);
                        auto buf = arr.request();
                        if (buf.size == 3) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            mat->default_phase().uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (buf.size == 4) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            mat->default_phase().uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            }

            return mat;
        }))
        .def_readwrite("name", &Material::name)
        .def_readwrite("source_path", &Material::source_path)
        .def_readwrite("shader_name", &Material::shader_name)
        .def_readwrite("phases", &Material::phases)
        .def("default_phase", static_cast<MaterialPhase& (Material::*)()>(&Material::default_phase),
             py::return_value_policy::reference)
        .def_property_readonly("_default_phase", [](Material& self) -> MaterialPhase& {
            return self.default_phase();
        }, py::return_value_policy::reference)
        // Convenience properties for default phase (Python compatibility)
        .def_property("shader",
            [](Material& self) { return self.default_phase().shader; },
            [](Material& self, std::shared_ptr<ShaderProgram> shader) {
                self.default_phase().shader = shader;
            })
        .def("set_shader", [](Material& self, std::shared_ptr<ShaderProgram> shader, const std::string& shader_name) {
            // Update shader in all phases
            for (auto& phase : self.phases) {
                phase.shader = shader;
            }
            self.shader_name = shader_name;
        }, py::arg("shader"), py::arg("shader_name") = "")
        // Overload for multi-phase shader program
        .def("set_shader", [](Material& self, const ShaderMultyPhaseProgramm& program, const std::string& shader_name) {
            if (program.phases.empty()) {
                throw std::runtime_error("Program has no phases");
            }

            // Preserve existing color, textures, uniforms from first phase
            std::optional<Vec4> old_color;
            std::unordered_map<std::string, TextureHandle> old_textures;
            std::unordered_map<std::string, MaterialUniformValue> old_uniforms;

            if (!self.phases.empty()) {
                old_color = self.phases[0].color;
                old_textures = self.phases[0].textures;
                old_uniforms = self.phases[0].uniforms;
            }

            // Clear and rebuild phases
            self.phases.clear();
            self.shader_name = shader_name.empty() ? program.program : shader_name;

            // Get MaterialPhase class for from_shader_phase
            py::object MaterialPhase_cls = py::module_::import("termin._native.render").attr("MaterialPhase");

            // Convert old values to py::object for from_shader_phase
            py::object py_color = py::none();
            if (old_color.has_value()) {
                auto arr = py::array_t<float>(4);
                auto buf = arr.mutable_unchecked<1>();
                buf(0) = static_cast<float>(old_color->x);
                buf(1) = static_cast<float>(old_color->y);
                buf(2) = static_cast<float>(old_color->z);
                buf(3) = static_cast<float>(old_color->w);
                py_color = arr;
            }

            for (const auto& shader_phase : program.phases) {
                MaterialPhase phase = MaterialPhase_cls.attr("from_shader_phase")(
                    shader_phase, py_color, py::none(), py::none()
                ).cast<MaterialPhase>();

                // Restore old textures and uniforms
                for (const auto& [key, val] : old_textures) {
                    phase.textures[key] = val;
                }
                for (const auto& [key, val] : old_uniforms) {
                    phase.uniforms[key] = val;
                }

                self.phases.push_back(std::move(phase));
            }
        }, py::arg("program"), py::arg("shader_name") = "")
        .def_property("color",
            [](Material& self) -> py::object {
                if (!self.default_phase().color.has_value()) return py::none();
                Vec4 c = self.default_phase().color.value();
                auto result = py::array_t<float>(4);
                auto buf = result.mutable_unchecked<1>();
                buf(0) = static_cast<float>(c.x);
                buf(1) = static_cast<float>(c.y);
                buf(2) = static_cast<float>(c.z);
                buf(3) = static_cast<float>(c.w);
                return result;
            },
            [](Material& self, py::object val) {
                if (val.is_none()) {
                    self.default_phase().color = std::nullopt;
                } else {
                    auto arr = py::array_t<float>::ensure(val);
                    auto buf = arr.unchecked<1>();
                    self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
                }
            })
        .def_property("textures",
            [](Material& self) -> std::unordered_map<std::string, TextureHandle>& {
                return self.default_phase().textures;
            },
            [](Material& self, const std::unordered_map<std::string, TextureHandle>& textures) {
                self.default_phase().textures = textures;
            }, py::return_value_policy::reference)
        .def_property("uniforms",
            [](Material& self) -> py::dict {
                py::dict result;
                for (const auto& [key, val] : self.default_phase().uniforms) {
                    std::visit([&](auto&& arg) {
                        using T = std::decay_t<decltype(arg)>;
                        if constexpr (std::is_same_v<T, bool>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, int>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, float>) {
                            result[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, Vec3>) {
                            auto arr = py::array_t<float>(3);
                            auto buf = arr.mutable_unchecked<1>();
                            buf(0) = arg.x;
                            buf(1) = arg.y;
                            buf(2) = arg.z;
                            result[key.c_str()] = arr;
                        } else if constexpr (std::is_same_v<T, Vec4>) {
                            auto arr = py::array_t<float>(4);
                            auto buf = arr.mutable_unchecked<1>();
                            buf(0) = arg.x;
                            buf(1) = arg.y;
                            buf(2) = arg.z;
                            buf(3) = arg.w;
                            result[key.c_str()] = arr;
                        }
                    }, val);
                }
                return result;
            },
            [](Material& self, py::dict uniforms) {
                // Convert from Python dict to C++ map
                for (auto item : uniforms) {
                    std::string key = item.first.cast<std::string>();
                    py::object val = py::reinterpret_borrow<py::object>(item.second);
                    if (py::isinstance<py::bool_>(val)) {
                        self.default_phase().uniforms[key] = val.cast<bool>();
                    } else if (py::isinstance<py::int_>(val)) {
                        self.default_phase().uniforms[key] = val.cast<int>();
                    } else if (py::isinstance<py::float_>(val)) {
                        self.default_phase().uniforms[key] = val.cast<float>();
                    } else if (py::isinstance<py::array>(val)) {
                        auto arr = py::array_t<float>::ensure(val);
                        auto buf = arr.request();
                        if (buf.size == 3) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            self.default_phase().uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (buf.size == 4) {
                            auto* ptr = static_cast<float*>(buf.ptr);
                            self.default_phase().uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            })
        .def("get_phases_for_mark", &Material::get_phases_for_mark)
        .def("set_param", [](Material& self, const std::string& name, py::object value) {
            if (py::isinstance<py::bool_>(value)) {
                self.set_param(name, value.cast<bool>());
            } else if (py::isinstance<py::int_>(value)) {
                self.set_param(name, value.cast<int>());
            } else if (py::isinstance<py::float_>(value)) {
                self.set_param(name, value.cast<float>());
            } else if (py::isinstance<py::array>(value)) {
                auto arr = py::array_t<float>::ensure(value);
                auto buf = arr.request();
                if (buf.size == 3) {
                    auto* ptr = static_cast<float*>(buf.ptr);
                    self.set_param(name, Vec3{ptr[0], ptr[1], ptr[2]});
                } else if (buf.size == 4) {
                    auto* ptr = static_cast<float*>(buf.ptr);
                    self.set_param(name, Vec4{ptr[0], ptr[1], ptr[2], ptr[3]});
                }
            }
        })
        .def("set_color", [](Material& self, py::array_t<float> rgba) {
            auto buf = rgba.unchecked<1>();
            self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
        })
        .def("update_color", [](Material& self, py::array_t<float> rgba) {
            auto buf = rgba.unchecked<1>();
            self.set_color(Vec4{buf(0), buf(1), buf(2), buf(3)});
        })
        .def("apply", [](Material& self,
                         py::array_t<float> model,
                         py::array_t<float> view,
                         py::array_t<float> proj,
                         GraphicsBackend* graphics,
                         int64_t context_key) {
            auto m_buf = model.unchecked<2>();
            auto v_buf = view.unchecked<2>();
            auto p_buf = proj.unchecked<2>();

            Mat44f m_mat, v_mat, p_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    m_mat.data[col * 4 + row] = m_buf(row, col);
                    v_mat.data[col * 4 + row] = v_buf(row, col);
                    p_mat.data[col * 4 + row] = p_buf(row, col);
                }
            }
            self.apply(m_mat, v_mat, p_mat, graphics, context_key);
        }, py::arg("model"), py::arg("view"), py::arg("projection"),
           py::arg("graphics"), py::arg("context_key") = 0)
        .def("copy", &Material::copy)
        // from_parsed - create Material from ShaderMultyPhaseProgramm
        .def_static("from_parsed", [](
            const ShaderMultyPhaseProgramm& program,
            py::object color,
            py::object textures,
            py::object uniforms,
            py::object name,
            py::object source_path
        ) -> std::shared_ptr<Material> {
            if (program.phases.empty()) {
                throw std::runtime_error("Program has no phases");
            }

            auto mat = std::make_shared<Material>();
            mat->name = name.is_none() ? program.program : name.cast<std::string>();
            mat->source_path = source_path.is_none() ? "" : source_path.cast<std::string>();
            mat->shader_name = program.program;
            mat->phases.clear();

            // Get MaterialPhase class for from_shader_phase
            py::object MaterialPhase_cls = py::module_::import("termin._native.render").attr("MaterialPhase");

            for (const auto& shader_phase : program.phases) {
                MaterialPhase phase = MaterialPhase_cls.attr("from_shader_phase")(
                    shader_phase, color, textures, uniforms
                ).cast<MaterialPhase>();
                mat->phases.push_back(std::move(phase));
            }

            return mat;
        }, py::arg("program"),
           py::arg("color") = py::none(),
           py::arg("textures") = py::none(),
           py::arg("uniforms") = py::none(),
           py::arg("name") = py::none(),
           py::arg("source_path") = py::none())
        // serialize - serialize Material to dict
        .def("serialize", [](const Material& self) -> py::dict {
            py::dict result;

            // If source_path is set, serialize as file reference
            if (!self.source_path.empty()) {
                result["type"] = "path";
                result["path"] = self.source_path;
                result["name"] = self.name;
                return result;
            }

            // Otherwise serialize inline
            result["type"] = "inline";
            result["name"] = self.name;
            result["shader_name"] = self.shader_name;

            py::list phases_list;
            for (const auto& phase : self.phases) {
                // Serialize phase using its serialize method
                py::dict phase_dict;
                phase_dict["phase_mark"] = phase.phase_mark;
                phase_dict["priority"] = phase.priority;

                // Color
                if (phase.color.has_value()) {
                    Vec4 c = phase.color.value();
                    py::list col_list;
                    col_list.append(c.x);
                    col_list.append(c.y);
                    col_list.append(c.z);
                    col_list.append(c.w);
                    phase_dict["color"] = col_list;
                } else {
                    phase_dict["color"] = py::none();
                }

                // Uniforms
                py::dict uniforms_dict;
                for (const auto& [key, val] : phase.uniforms) {
                    std::visit([&](auto&& arg) {
                        using T = std::decay_t<decltype(arg)>;
                        if constexpr (std::is_same_v<T, bool>) {
                            uniforms_dict[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, int>) {
                            uniforms_dict[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, float>) {
                            uniforms_dict[key.c_str()] = arg;
                        } else if constexpr (std::is_same_v<T, Vec3>) {
                            py::list vec;
                            vec.append(arg.x);
                            vec.append(arg.y);
                            vec.append(arg.z);
                            uniforms_dict[key.c_str()] = vec;
                        } else if constexpr (std::is_same_v<T, Vec4>) {
                            py::list vec;
                            vec.append(arg.x);
                            vec.append(arg.y);
                            vec.append(arg.z);
                            vec.append(arg.w);
                            uniforms_dict[key.c_str()] = vec;
                        }
                    }, val);
                }
                phase_dict["uniforms"] = uniforms_dict;

                // Textures - store source_path
                py::dict textures_dict;
                for (const auto& [key, tex] : phase.textures) {
                    std::string path = tex.source_path();
                    if (!path.empty()) {
                        textures_dict[key.c_str()] = path;
                    }
                }
                phase_dict["textures"] = textures_dict;

                // Render state
                py::dict rs_dict;
                rs_dict["depth_test"] = phase.render_state.depth_test;
                rs_dict["depth_write"] = phase.render_state.depth_write;
                rs_dict["blend"] = phase.render_state.blend;
                rs_dict["cull"] = phase.render_state.cull;
                phase_dict["render_state"] = rs_dict;

                // Shader sources
                py::dict shader_dict;
                if (phase.shader) {
                    shader_dict["vertex"] = phase.shader->vertex_source();
                    shader_dict["fragment"] = phase.shader->fragment_source();
                    shader_dict["geometry"] = phase.shader->geometry_source();
                }
                phase_dict["shader"] = shader_dict;

                phases_list.append(phase_dict);
            }
            result["phases"] = phases_list;

            return result;
        })
        // deserialize - deserialize Material from dict
        .def_static("deserialize", [](py::dict data, py::object context) -> std::shared_ptr<Material> {
            std::string type_str = "inline";
            if (data.contains("type")) {
                type_str = data["type"].cast<std::string>();
            }

            if (type_str == "path") {
                // Load from file
                std::string path = data["path"].cast<std::string>();
                if (!context.is_none() && py::hasattr(context, "load_material")) {
                    return context.attr("load_material")(path).cast<std::shared_ptr<Material>>();
                }
                throw std::runtime_error("Cannot deserialize path-based material without context");
            }

            // Inline deserialization
            auto mat = std::make_shared<Material>();
            if (data.contains("name")) {
                mat->name = data["name"].cast<std::string>();
            }
            if (data.contains("shader_name")) {
                mat->shader_name = data["shader_name"].cast<std::string>();
            }

            mat->phases.clear();
            if (data.contains("phases")) {
                py::list phases_list = data["phases"].cast<py::list>();
                for (auto phase_obj : phases_list) {
                    py::dict phase_data = phase_obj.cast<py::dict>();

                    // Get shader sources
                    py::dict shader_data = phase_data["shader"].cast<py::dict>();
                    std::string vs = shader_data["vertex"].cast<std::string>();
                    std::string fs = shader_data["fragment"].cast<std::string>();
                    std::string gs = shader_data.contains("geometry") ?
                        shader_data["geometry"].cast<std::string>() : "";

                    auto shader = std::make_shared<ShaderProgram>(vs, fs, gs, "");

                    // Get render state
                    RenderState rs;
                    if (phase_data.contains("render_state")) {
                        py::dict rs_data = phase_data["render_state"].cast<py::dict>();
                        rs.depth_test = rs_data.contains("depth_test") ?
                            rs_data["depth_test"].cast<bool>() : true;
                        rs.depth_write = rs_data.contains("depth_write") ?
                            rs_data["depth_write"].cast<bool>() : true;
                        rs.blend = rs_data.contains("blend") ?
                            rs_data["blend"].cast<bool>() : false;
                        rs.cull = rs_data.contains("cull") ?
                            rs_data["cull"].cast<bool>() : true;
                    }

                    std::string phase_mark = phase_data.contains("phase_mark") ?
                        phase_data["phase_mark"].cast<std::string>() : "opaque";
                    int priority = phase_data.contains("priority") ?
                        phase_data["priority"].cast<int>() : 0;

                    MaterialPhase phase(shader, rs, phase_mark, priority);

                    // Color
                    if (phase_data.contains("color") && !phase_data["color"].is_none()) {
                        py::list color_list = phase_data["color"].cast<py::list>();
                        if (py::len(color_list) >= 4) {
                            phase.set_color(Vec4{
                                color_list[0].cast<float>(),
                                color_list[1].cast<float>(),
                                color_list[2].cast<float>(),
                                color_list[3].cast<float>()
                            });
                        }
                    }

                    // Uniforms
                    if (phase_data.contains("uniforms")) {
                        py::dict uniforms_dict = phase_data["uniforms"].cast<py::dict>();
                        for (auto item : uniforms_dict) {
                            std::string key = item.first.cast<std::string>();
                            py::object val = py::reinterpret_borrow<py::object>(item.second);
                            if (py::isinstance<py::list>(val)) {
                                py::list lst = val.cast<py::list>();
                                if (py::len(lst) == 3) {
                                    phase.uniforms[key] = Vec3{
                                        lst[0].cast<float>(),
                                        lst[1].cast<float>(),
                                        lst[2].cast<float>()
                                    };
                                } else if (py::len(lst) == 4) {
                                    phase.uniforms[key] = Vec4{
                                        lst[0].cast<float>(),
                                        lst[1].cast<float>(),
                                        lst[2].cast<float>(),
                                        lst[3].cast<float>()
                                    };
                                }
                            } else if (py::isinstance<py::float_>(val)) {
                                phase.uniforms[key] = val.cast<float>();
                            } else if (py::isinstance<py::int_>(val)) {
                                phase.uniforms[key] = val.cast<int>();
                            } else if (py::isinstance<py::bool_>(val)) {
                                phase.uniforms[key] = val.cast<bool>();
                            }
                        }
                    }

                    // Textures (if context provided)
                    if (phase_data.contains("textures") && !context.is_none()) {
                        py::dict textures_dict = phase_data["textures"].cast<py::dict>();
                        for (auto item : textures_dict) {
                            std::string key = item.first.cast<std::string>();
                            std::string path = item.second.cast<std::string>();
                            if (py::hasattr(context, "load_texture")) {
                                phase.textures[key] = context.attr("load_texture")(path).cast<TextureHandle>();
                            }
                        }
                    }

                    mat->phases.push_back(std::move(phase));
                }
            }

            return mat;
        }, py::arg("data"), py::arg("context") = py::none());

    m.def("get_error_material", []() -> std::shared_ptr<Material> {
        static std::shared_ptr<Material> error_mat;
        if (!error_mat) {
            py::object shader_mod = py::module_::import("termin.visualization.render.materials.default_material");
            auto shader = shader_mod.attr("default_shader")().cast<std::shared_ptr<ShaderProgram>>();
            error_mat = std::make_shared<Material>(shader, RenderState::opaque(), "opaque", 0);
            error_mat->name = "__ErrorMaterial__";
            error_mat->shader_name = "DefaultShader";
            error_mat->set_color(Vec4{1.0, 0.0, 1.0, 1.0});
        }
        return error_mat;
    });
}

} // namespace termin
