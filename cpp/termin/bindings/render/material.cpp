#include "common.hpp"
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/optional.h>
#include "termin/render/material.hpp"
#include "termin/assets/handles.hpp"
#include "termin/render/shader_parser.hpp"
#include "termin/render/render_state.hpp"
#include "termin/render/render.hpp"

namespace termin {

void bind_material(nb::module_& m) {
    // MaterialPhase
    nb::class_<MaterialPhase>(m, "MaterialPhase")
        .def(nb::init<>())
        .def("__init__", [](MaterialPhase* self, std::shared_ptr<ShaderProgram> shader, const RenderState& rs,
                         const std::string& phase_mark, int priority) {
            new (self) MaterialPhase(shader, rs, phase_mark, priority);
        }, nb::arg("shader"), nb::arg("render_state") = RenderState::opaque(),
            nb::arg("phase_mark") = "opaque", nb::arg("priority") = 0)
        // Python-compatible kwargs constructor (supports shader_programm, color)
        .def("__init__", [](MaterialPhase* self, nb::kwargs kwargs) {
            std::shared_ptr<ShaderProgram> shader;
            if (kwargs.contains("shader_programm")) {
                shader = nb::cast<std::shared_ptr<ShaderProgram>>(kwargs["shader_programm"]);
            } else if (kwargs.contains("shader")) {
                shader = nb::cast<std::shared_ptr<ShaderProgram>>(kwargs["shader"]);
            }
            if (!shader) {
                throw std::runtime_error("MaterialPhase requires 'shader' or 'shader_programm' argument");
            }

            RenderState rs = RenderState::opaque();
            if (kwargs.contains("render_state")) {
                rs = nb::cast<RenderState>(kwargs["render_state"]);
            }

            std::string phase_mark = "opaque";
            if (kwargs.contains("phase_mark")) {
                phase_mark = nb::cast<std::string>(kwargs["phase_mark"]);
            }

            int priority = 0;
            if (kwargs.contains("priority")) {
                priority = nb::cast<int>(kwargs["priority"]);
            }

            new (self) MaterialPhase(shader, rs, phase_mark, priority);

            // Set color
            if (kwargs.contains("color") && !kwargs["color"].is_none()) {
                nb::object color_obj = nb::borrow<nb::object>(kwargs["color"]);
                if (nb::ndarray_check(color_obj)) {
                    nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(color_obj);
                    float* ptr = arr.data();
                    self->set_color(Vec4{ptr[0], ptr[1], ptr[2], ptr[3]});
                } else if (nb::isinstance<nb::tuple>(color_obj) || nb::isinstance<nb::list>(color_obj)) {
                    nb::sequence seq = nb::cast<nb::sequence>(color_obj);
                    self->set_color(Vec4{
                        nb::cast<float>(seq[0]),
                        nb::cast<float>(seq[1]),
                        nb::cast<float>(seq[2]),
                        nb::cast<float>(seq[3])
                    });
                }
            }

            // Set textures
            if (kwargs.contains("textures") && !kwargs["textures"].is_none()) {
                nb::dict tex_dict = nb::cast<nb::dict>(kwargs["textures"]);
                for (auto item : tex_dict) {
                    std::string key = nb::cast<std::string>(item.first);
                    self->textures[key] = nb::cast<TextureHandle>(item.second);
                }
            }

            // Set uniforms
            if (kwargs.contains("uniforms") && !kwargs["uniforms"].is_none()) {
                nb::dict uniforms_dict = nb::cast<nb::dict>(kwargs["uniforms"]);
                for (auto item : uniforms_dict) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<nb::bool_>(val)) {
                        self->uniforms[key] = nb::cast<bool>(val);
                    } else if (nb::isinstance<nb::int_>(val)) {
                        self->uniforms[key] = nb::cast<int>(val);
                    } else if (nb::isinstance<nb::float_>(val)) {
                        self->uniforms[key] = nb::cast<float>(val);
                    }
                }
            }
        })
        .def_rw("shader", &MaterialPhase::shader)
        .def_rw("shader_programm", &MaterialPhase::shader)  // Python compatibility alias
        .def_rw("render_state", &MaterialPhase::render_state)
        .def_prop_rw("color",
            [](const MaterialPhase& self) -> std::optional<Vec4> {
                return self.color;
            },
            [](MaterialPhase& self, nb::object val) {
                if (val.is_none()) {
                    self.color = std::nullopt;
                } else if (nb::isinstance<Vec4>(val)) {
                    self.set_color(nb::cast<Vec4>(val));
                } else if (nb::isinstance<nb::tuple>(val) || nb::isinstance<nb::list>(val)) {
                    nb::sequence seq = nb::cast<nb::sequence>(val);
                    self.set_color(Vec4{
                        nb::cast<double>(seq[0]),
                        nb::cast<double>(seq[1]),
                        nb::cast<double>(seq[2]),
                        nb::cast<double>(seq[3])
                    });
                }
            })
        .def_rw("phase_mark", &MaterialPhase::phase_mark)
        .def_rw("available_marks", &MaterialPhase::available_marks)
        // Note: mark_render_states is not exposed - managed internally in C++
        .def_prop_rw("mark_render_states",
            [](const MaterialPhase& self) {
                nb::dict result;
                for (const auto& [key, val] : self.mark_render_states) {
                    result[key.c_str()] = val;
                }
                return result;
            },
            [](MaterialPhase& self, nb::dict d) {
                self.mark_render_states.clear();
                for (auto item : d) {
                    std::string key = nb::cast<std::string>(item.first);
                    RenderState val = nb::cast<RenderState>(item.second);
                    self.mark_render_states[key] = val;
                }
            })
        .def("set_phase_mark", [](MaterialPhase& self, const std::string& mark) {
            self.phase_mark = mark;
            // Apply render state for this mark if available
            auto it = self.mark_render_states.find(mark);
            if (it != self.mark_render_states.end()) {
                self.render_state = it->second;
            }
        }, nb::arg("mark"), "Set phase mark and apply corresponding render state")
        .def_rw("priority", &MaterialPhase::priority)
        .def_rw("textures", &MaterialPhase::textures)
        .def_prop_rw("uniforms",
            [](MaterialPhase& self) -> nb::dict {
                nb::dict result;
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
                            float* data = new float[3]{static_cast<float>(arg.x), static_cast<float>(arg.y), static_cast<float>(arg.z)};
                            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
                            result[key.c_str()] = nb::cast(nb::ndarray<nb::numpy, float, nb::shape<3>>(data, {3}, owner));
                        } else if constexpr (std::is_same_v<T, Vec4>) {
                            float* data = new float[4]{static_cast<float>(arg.x), static_cast<float>(arg.y), static_cast<float>(arg.z), static_cast<float>(arg.w)};
                            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
                            result[key.c_str()] = nb::cast(nb::ndarray<nb::numpy, float, nb::shape<4>>(data, {4}, owner));
                        }
                    }, val);
                }
                return result;
            },
            [](MaterialPhase& self, nb::dict uniforms) {
                for (auto item : uniforms) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<nb::bool_>(val)) {
                        self.uniforms[key] = nb::cast<bool>(val);
                    } else if (nb::isinstance<nb::int_>(val)) {
                        self.uniforms[key] = nb::cast<int>(val);
                    } else if (nb::isinstance<nb::float_>(val)) {
                        self.uniforms[key] = nb::cast<float>(val);
                    } else if (nb::ndarray_check(val)) {
                        nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(val);
                        float* ptr = arr.data();
                        size_t size = arr.shape(0);
                        if (size == 3) {
                            self.uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (size == 4) {
                            self.uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            })
        .def("set_texture", [](MaterialPhase& self, const std::string& name, const TextureHandle& tex) {
            self.textures[name] = tex;
        })
        .def("set_param", [](MaterialPhase& self, const std::string& name, nb::object value) {
            if (nb::isinstance<nb::bool_>(value)) {
                self.set_param(name, nb::cast<bool>(value));
            } else if (nb::isinstance<nb::int_>(value)) {
                self.set_param(name, nb::cast<int>(value));
            } else if (nb::isinstance<nb::float_>(value)) {
                self.set_param(name, nb::cast<float>(value));
            } else if (nb::ndarray_check(value)) {
                nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(value);
                float* ptr = arr.data();
                size_t size = arr.shape(0);
                if (size == 3) {
                    self.set_param(name, Vec3{ptr[0], ptr[1], ptr[2]});
                } else if (size == 4) {
                    self.set_param(name, Vec4{ptr[0], ptr[1], ptr[2], ptr[3]});
                }
            }
        })
        .def("set_color", [](MaterialPhase& self, nb::ndarray<nb::numpy, float, nb::shape<4>> rgba) {
            self.set_color(Vec4{rgba(0), rgba(1), rgba(2), rgba(3)});
        })
        .def("update_color", [](MaterialPhase& self, nb::ndarray<nb::numpy, float, nb::shape<4>> rgba) {
            self.set_color(Vec4{rgba(0), rgba(1), rgba(2), rgba(3)});
        })
        .def("apply", [](MaterialPhase& self,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> proj,
                         GraphicsBackend* graphics,
                         int64_t context_key) {
            Mat44f m_mat, v_mat, p_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    m_mat.data[col * 4 + row] = model(row, col);
                    v_mat.data[col * 4 + row] = view(row, col);
                    p_mat.data[col * 4 + row] = proj(row, col);
                }
            }
            self.apply(m_mat, v_mat, p_mat, graphics, context_key);
        }, nb::arg("model"), nb::arg("view"), nb::arg("projection"),
           nb::arg("graphics"), nb::arg("context_key") = 0)
        .def("apply_state", &MaterialPhase::apply_state)
        .def("copy", &MaterialPhase::copy)
        // serialize - serialize MaterialPhase to dict
        .def("serialize", [](const MaterialPhase& self) -> nb::dict {
            nb::dict result;
            result["phase_mark"] = self.phase_mark;
            result["priority"] = self.priority;

            // Color
            if (self.color.has_value()) {
                Vec4 c = self.color.value();
                nb::list col_list;
                col_list.append(c.x);
                col_list.append(c.y);
                col_list.append(c.z);
                col_list.append(c.w);
                result["color"] = col_list;
            } else {
                result["color"] = nb::none();
            }

            // Uniforms
            nb::dict uniforms_dict;
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
                        nb::list vec;
                        vec.append(arg.x);
                        vec.append(arg.y);
                        vec.append(arg.z);
                        uniforms_dict[key.c_str()] = vec;
                    } else if constexpr (std::is_same_v<T, Vec4>) {
                        nb::list vec;
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
            nb::dict textures_dict;
            for (const auto& [key, tex] : self.textures) {
                std::string path = tex.source_path();
                if (!path.empty()) {
                    textures_dict[key.c_str()] = path;
                }
            }
            result["textures"] = textures_dict;

            // Render state
            nb::dict rs_dict;
            rs_dict["depth_test"] = self.render_state.depth_test;
            rs_dict["depth_write"] = self.render_state.depth_write;
            rs_dict["blend"] = self.render_state.blend;
            rs_dict["cull"] = self.render_state.cull;
            result["render_state"] = rs_dict;

            // Shader sources
            nb::dict shader_dict;
            if (self.shader) {
                shader_dict["vertex"] = self.shader->vertex_source();
                shader_dict["fragment"] = self.shader->fragment_source();
                shader_dict["geometry"] = self.shader->geometry_source();
            }
            result["shader"] = shader_dict;

            return result;
        })
        // deserialize - deserialize MaterialPhase from dict
        .def_static("deserialize", [](nb::dict data, nb::object context) -> std::shared_ptr<MaterialPhase> {
            // Get shader sources
            nb::dict shader_data = nb::cast<nb::dict>(data["shader"]);
            std::string vs = nb::cast<std::string>(shader_data["vertex"]);
            std::string fs = nb::cast<std::string>(shader_data["fragment"]);
            std::string gs = shader_data.contains("geometry") ?
                nb::cast<std::string>(shader_data["geometry"]) : "";

            auto shader = std::make_shared<ShaderProgram>(vs, fs, gs, "");

            // Get render state
            RenderState rs;
            if (data.contains("render_state")) {
                nb::dict rs_data = nb::cast<nb::dict>(data["render_state"]);
                rs.depth_test = rs_data.contains("depth_test") ?
                    nb::cast<bool>(rs_data["depth_test"]) : true;
                rs.depth_write = rs_data.contains("depth_write") ?
                    nb::cast<bool>(rs_data["depth_write"]) : true;
                rs.blend = rs_data.contains("blend") ?
                    nb::cast<bool>(rs_data["blend"]) : false;
                rs.cull = rs_data.contains("cull") ?
                    nb::cast<bool>(rs_data["cull"]) : true;
            }

            std::string phase_mark = data.contains("phase_mark") ?
                nb::cast<std::string>(data["phase_mark"]) : "opaque";
            int priority = data.contains("priority") ?
                nb::cast<int>(data["priority"]) : 0;

            auto phase = std::make_shared<MaterialPhase>(shader, rs, phase_mark, priority);

            // Color
            if (data.contains("color") && !data["color"].is_none()) {
                nb::list color_list = nb::cast<nb::list>(data["color"]);
                if (nb::len(color_list) >= 4) {
                    phase->set_color(Vec4{
                        nb::cast<float>(color_list[0]),
                        nb::cast<float>(color_list[1]),
                        nb::cast<float>(color_list[2]),
                        nb::cast<float>(color_list[3])
                    });
                }
            }

            // Uniforms
            if (data.contains("uniforms")) {
                nb::dict uniforms_dict = nb::cast<nb::dict>(data["uniforms"]);
                for (auto item : uniforms_dict) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<nb::list>(val)) {
                        nb::list lst = nb::cast<nb::list>(val);
                        if (nb::len(lst) == 3) {
                            phase->uniforms[key] = Vec3{
                                nb::cast<float>(lst[0]),
                                nb::cast<float>(lst[1]),
                                nb::cast<float>(lst[2])
                            };
                        } else if (nb::len(lst) == 4) {
                            phase->uniforms[key] = Vec4{
                                nb::cast<float>(lst[0]),
                                nb::cast<float>(lst[1]),
                                nb::cast<float>(lst[2]),
                                nb::cast<float>(lst[3])
                            };
                        }
                    } else if (nb::isinstance<nb::float_>(val)) {
                        phase->uniforms[key] = nb::cast<float>(val);
                    } else if (nb::isinstance<nb::int_>(val)) {
                        phase->uniforms[key] = nb::cast<int>(val);
                    } else if (nb::isinstance<nb::bool_>(val)) {
                        phase->uniforms[key] = nb::cast<bool>(val);
                    }
                }
            }

            // Textures (if context provided)
            if (data.contains("textures") && !context.is_none()) {
                nb::dict textures_dict = nb::cast<nb::dict>(data["textures"]);
                for (auto item : textures_dict) {
                    std::string key = nb::cast<std::string>(item.first);
                    std::string path = nb::cast<std::string>(item.second);
                    if (nb::hasattr(context, "load_texture")) {
                        phase->textures[key] = nb::cast<TextureHandle>(context.attr("load_texture")(path));
                    }
                }
            }

            return phase;
        }, nb::arg("data"), nb::arg("context") = nb::none())
        // from_shader_phase - create MaterialPhase from parsed ShaderPhase
        .def_static("from_shader_phase", [](
            const ShaderPhase& shader_phase,
            nb::object color,
            nb::object textures,
            nb::object extra_uniforms,
            const std::string& program_name
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

            // Build shader name: program_name/phase_mark (e.g. "PBR/forward")
            std::string shader_name;
            if (!program_name.empty()) {
                shader_name = program_name;
                if (!shader_phase.phase_mark.empty()) {
                    shader_name += "/" + shader_phase.phase_mark;
                }
            } else if (!shader_phase.phase_mark.empty()) {
                shader_name = shader_phase.phase_mark;
            }

            auto shader = std::make_shared<ShaderProgram>(vs, fs, gs, "", shader_name);

            // 2. Build RenderState from gl-flags
            RenderState rs;
            rs.depth_write = shader_phase.gl_depth_mask.value_or(true);
            rs.depth_test = shader_phase.gl_depth_test.value_or(true);
            rs.blend = shader_phase.gl_blend.value_or(false);
            rs.cull = shader_phase.gl_cull.value_or(true);

            MaterialPhase phase(shader, rs, shader_phase.phase_mark, shader_phase.priority);
            phase.available_marks = shader_phase.available_marks;

            // Copy per-mark render states from shader
            for (const auto& [mark, settings] : shader_phase.mark_settings) {
                RenderState mark_rs;
                mark_rs.depth_write = settings.gl_depth_mask.value_or(true);
                mark_rs.depth_test = settings.gl_depth_test.value_or(true);
                mark_rs.blend = settings.gl_blend.value_or(false);
                mark_rs.cull = settings.gl_cull.value_or(true);
                phase.mark_render_states[mark] = mark_rs;
            }

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
                nb::dict extras = nb::cast<nb::dict>(extra_uniforms);
                for (auto item : extras) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<nb::bool_>(val)) {
                        phase.uniforms[key] = nb::cast<bool>(val);
                    } else if (nb::isinstance<nb::int_>(val)) {
                        phase.uniforms[key] = nb::cast<int>(val);
                    } else if (nb::isinstance<nb::float_>(val)) {
                        phase.uniforms[key] = nb::cast<float>(val);
                    } else if (nb::ndarray_check(val)) {
                        nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(val);
                        float* ptr = arr.data();
                        size_t size = arr.shape(0);
                        if (size == 3) {
                            phase.uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (size == 4) {
                            phase.uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            }

            // 5. Set textures (use white texture as default for Texture properties)
            nb::object white_tex_fn = nb::module_::import_("termin.visualization.core.texture_handle").attr("get_white_texture_handle");
            TextureHandle white_tex = nb::cast<TextureHandle>(white_tex_fn());

            for (const auto& prop : shader_phase.uniforms) {
                if (prop.property_type == "Texture") {
                    phase.textures[prop.name] = white_tex;
                }
            }

            // Override with provided textures
            if (!textures.is_none()) {
                nb::dict tex_dict = nb::cast<nb::dict>(textures);
                for (auto item : tex_dict) {
                    std::string key = nb::cast<std::string>(item.first);
                    phase.textures[key] = nb::cast<TextureHandle>(item.second);
                }
            }

            // 6. Set color
            if (!color.is_none()) {
                if (nb::ndarray_check(color)) {
                    nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(color);
                    float* ptr = arr.data();
                    phase.set_color(Vec4{ptr[0], ptr[1], ptr[2], ptr[3]});
                } else if (nb::isinstance<nb::tuple>(color) || nb::isinstance<nb::list>(color)) {
                    nb::sequence seq = nb::cast<nb::sequence>(color);
                    phase.set_color(Vec4{
                        nb::cast<float>(seq[0]),
                        nb::cast<float>(seq[1]),
                        nb::cast<float>(seq[2]),
                        nb::cast<float>(seq[3])
                    });
                }
            }

            return phase;
        }, nb::arg("shader_phase"),
           nb::arg("color") = nb::none(),
           nb::arg("textures") = nb::none(),
           nb::arg("extra_uniforms") = nb::none(),
           nb::arg("program_name") = "");

    // Material
    nb::class_<Material>(m, "Material")
        .def(nb::init<>())
        .def("__init__", [](Material* self, std::shared_ptr<ShaderProgram> shader, const RenderState& rs,
                         const std::string& phase_mark, int priority) {
            new (self) Material(shader, rs, phase_mark, priority);
        }, nb::arg("shader"), nb::arg("render_state") = RenderState::opaque(),
            nb::arg("phase_mark") = "opaque", nb::arg("priority") = 0)
        // Python-compatible kwargs constructor
        .def("__init__", [](Material* self, nb::kwargs kwargs) {
            // Get default shader if not provided
            std::shared_ptr<ShaderProgram> shader;
            if (kwargs.contains("shader")) {
                shader = nb::cast<std::shared_ptr<ShaderProgram>>(kwargs["shader"]);
            } else {
                // Import default shader
                nb::object shader_mod = nb::module_::import_("termin.visualization.render.materials.default_material");
                shader = nb::cast<std::shared_ptr<ShaderProgram>>(shader_mod.attr("default_shader")());
            }

            RenderState rs = RenderState::opaque();
            if (kwargs.contains("render_state")) {
                rs = nb::cast<RenderState>(kwargs["render_state"]);
            }

            std::string phase_mark = "opaque";
            if (kwargs.contains("phase_mark")) {
                phase_mark = nb::cast<std::string>(kwargs["phase_mark"]);
            }

            int priority = 0;
            if (kwargs.contains("priority")) {
                priority = nb::cast<int>(kwargs["priority"]);
            }

            new (self) Material(shader, rs, phase_mark, priority);

            if (kwargs.contains("name")) {
                self->name = nb::cast<std::string>(kwargs["name"]);
            }
            if (kwargs.contains("source_path")) {
                self->source_path = nb::cast<std::string>(kwargs["source_path"]);
            }
            if (kwargs.contains("shader_name")) {
                self->shader_name = nb::cast<std::string>(kwargs["shader_name"]);
            }

            // Set color
            if (kwargs.contains("color") && !kwargs["color"].is_none()) {
                nb::object color_obj = nb::borrow<nb::object>(kwargs["color"]);
                if (nb::ndarray_check(color_obj)) {
                    nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(color_obj);
                    float* ptr = arr.data();
                    self->set_color(Vec4{ptr[0], ptr[1], ptr[2], ptr[3]});
                } else if (nb::isinstance<nb::tuple>(color_obj) || nb::isinstance<nb::list>(color_obj)) {
                    nb::sequence seq = nb::cast<nb::sequence>(color_obj);
                    self->set_color(Vec4{
                        nb::cast<float>(seq[0]),
                        nb::cast<float>(seq[1]),
                        nb::cast<float>(seq[2]),
                        nb::cast<float>(seq[3])
                    });
                }
            }

            // Set textures
            if (kwargs.contains("textures") && !kwargs["textures"].is_none()) {
                nb::dict tex_dict = nb::cast<nb::dict>(kwargs["textures"]);
                for (auto item : tex_dict) {
                    std::string key = nb::cast<std::string>(item.first);
                    self->default_phase().textures[key] = nb::cast<TextureHandle>(item.second);
                }
            }

            // Set uniforms
            if (kwargs.contains("uniforms") && !kwargs["uniforms"].is_none()) {
                nb::dict uniforms_dict = nb::cast<nb::dict>(kwargs["uniforms"]);
                for (auto item : uniforms_dict) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<nb::bool_>(val)) {
                        self->default_phase().uniforms[key] = nb::cast<bool>(val);
                    } else if (nb::isinstance<nb::int_>(val)) {
                        self->default_phase().uniforms[key] = nb::cast<int>(val);
                    } else if (nb::isinstance<nb::float_>(val)) {
                        self->default_phase().uniforms[key] = nb::cast<float>(val);
                    } else if (nb::ndarray_check(val)) {
                        nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(val);
                        float* ptr = arr.data();
                        size_t size = arr.shape(0);
                        if (size == 3) {
                            self->default_phase().uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (size == 4) {
                            self->default_phase().uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            }
        })
        .def_rw("name", &Material::name)
        .def_rw("source_path", &Material::source_path)
        .def_rw("shader_name", &Material::shader_name)
        .def_rw("active_phase_mark", &Material::active_phase_mark)
        .def_rw("phases", &Material::phases)
        .def("default_phase", static_cast<MaterialPhase& (Material::*)()>(&Material::default_phase),
             nb::rv_policy::reference)
        .def_prop_ro("_default_phase", [](Material& self) -> MaterialPhase& {
            return self.default_phase();
        }, nb::rv_policy::reference)
        // Convenience properties for default phase (Python compatibility)
        .def_prop_rw("shader",
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
        }, nb::arg("shader"), nb::arg("shader_name") = "")
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
            nb::object MaterialPhase_cls = nb::module_::import_("termin._native.render").attr("MaterialPhase");

            // Convert old values to nb::object for from_shader_phase
            nb::object py_color = nb::none();
            if (old_color.has_value()) {
                float* data = new float[4]{
                    static_cast<float>(old_color->x),
                    static_cast<float>(old_color->y),
                    static_cast<float>(old_color->z),
                    static_cast<float>(old_color->w)
                };
                nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
                py_color = nb::cast(nb::ndarray<nb::numpy, float, nb::shape<4>>(data, {4}, owner));
            }

            for (const auto& shader_phase : program.phases) {
                MaterialPhase phase = nb::cast<MaterialPhase>(MaterialPhase_cls.attr("from_shader_phase")(
                    shader_phase, py_color, nb::none(), nb::none(), program.program
                ));

                // Restore old textures and uniforms
                for (const auto& [key, val] : old_textures) {
                    phase.textures[key] = val;
                }
                for (const auto& [key, val] : old_uniforms) {
                    phase.uniforms[key] = val;
                }

                self.phases.push_back(std::move(phase));
            }
        }, nb::arg("program"), nb::arg("shader_name") = "")
        .def_prop_rw("color",
            [](const Material& self) { return self.color(); },
            [](Material& self, nb::object val) {
                if (nb::isinstance<Vec4>(val)) {
                    self.set_color(nb::cast<Vec4>(val));
                } else if (nb::isinstance<nb::tuple>(val) || nb::isinstance<nb::list>(val)) {
                    nb::sequence seq = nb::cast<nb::sequence>(val);
                    self.set_color(Vec4{
                        nb::cast<double>(seq[0]),
                        nb::cast<double>(seq[1]),
                        nb::cast<double>(seq[2]),
                        nb::cast<double>(seq[3])
                    });
                }
            })
        .def_prop_rw("textures",
            [](Material& self) -> std::unordered_map<std::string, TextureHandle>& {
                return self.default_phase().textures;
            },
            [](Material& self, const std::unordered_map<std::string, TextureHandle>& textures) {
                self.default_phase().textures = textures;
            }, nb::rv_policy::reference)
        .def_prop_rw("uniforms",
            [](Material& self) -> nb::dict {
                nb::dict result;
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
                            float* data = new float[3]{static_cast<float>(arg.x), static_cast<float>(arg.y), static_cast<float>(arg.z)};
                            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
                            result[key.c_str()] = nb::cast(nb::ndarray<nb::numpy, float, nb::shape<3>>(data, {3}, owner));
                        } else if constexpr (std::is_same_v<T, Vec4>) {
                            float* data = new float[4]{static_cast<float>(arg.x), static_cast<float>(arg.y), static_cast<float>(arg.z), static_cast<float>(arg.w)};
                            nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<float*>(p); });
                            result[key.c_str()] = nb::cast(nb::ndarray<nb::numpy, float, nb::shape<4>>(data, {4}, owner));
                        }
                    }, val);
                }
                return result;
            },
            [](Material& self, nb::dict uniforms) {
                // Convert from Python dict to C++ map
                for (auto item : uniforms) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<nb::bool_>(val)) {
                        self.default_phase().uniforms[key] = nb::cast<bool>(val);
                    } else if (nb::isinstance<nb::int_>(val)) {
                        self.default_phase().uniforms[key] = nb::cast<int>(val);
                    } else if (nb::isinstance<nb::float_>(val)) {
                        self.default_phase().uniforms[key] = nb::cast<float>(val);
                    } else if (nb::ndarray_check(val)) {
                        nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(val);
                        float* ptr = arr.data();
                        size_t size = arr.shape(0);
                        if (size == 3) {
                            self.default_phase().uniforms[key] = Vec3{ptr[0], ptr[1], ptr[2]};
                        } else if (size == 4) {
                            self.default_phase().uniforms[key] = Vec4{ptr[0], ptr[1], ptr[2], ptr[3]};
                        }
                    }
                }
            })
        .def("get_phases_for_mark", &Material::get_phases_for_mark)
        .def("set_param", [](Material& self, const std::string& name, nb::object value) {
            if (nb::isinstance<nb::bool_>(value)) {
                self.set_param(name, nb::cast<bool>(value));
            } else if (nb::isinstance<nb::int_>(value)) {
                self.set_param(name, nb::cast<int>(value));
            } else if (nb::isinstance<nb::float_>(value)) {
                self.set_param(name, nb::cast<float>(value));
            } else if (nb::ndarray_check(value)) {
                nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(value);
                float* ptr = arr.data();
                size_t size = arr.shape(0);
                if (size == 3) {
                    self.set_param(name, Vec3{ptr[0], ptr[1], ptr[2]});
                } else if (size == 4) {
                    self.set_param(name, Vec4{ptr[0], ptr[1], ptr[2], ptr[3]});
                }
            }
        })
        .def("set_color", [](Material& self, nb::ndarray<nb::numpy, float, nb::shape<4>> rgba) {
            self.set_color(Vec4{rgba(0), rgba(1), rgba(2), rgba(3)});
        })
        .def("update_color", [](Material& self, nb::ndarray<nb::numpy, float, nb::shape<4>> rgba) {
            self.set_color(Vec4{rgba(0), rgba(1), rgba(2), rgba(3)});
        })
        .def("apply", [](Material& self,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> proj,
                         GraphicsBackend* graphics,
                         int64_t context_key) {
            Mat44f m_mat, v_mat, p_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    m_mat.data[col * 4 + row] = model(row, col);
                    v_mat.data[col * 4 + row] = view(row, col);
                    p_mat.data[col * 4 + row] = proj(row, col);
                }
            }
            self.apply(m_mat, v_mat, p_mat, graphics, context_key);
        }, nb::arg("model"), nb::arg("view"), nb::arg("projection"),
           nb::arg("graphics"), nb::arg("context_key") = 0)
        .def("copy", &Material::copy)
        // from_parsed - create Material from ShaderMultyPhaseProgramm
        .def_static("from_parsed", [](
            const ShaderMultyPhaseProgramm& program,
            nb::object color,
            nb::object textures,
            nb::object uniforms,
            nb::object name,
            nb::object source_path
        ) -> std::shared_ptr<Material> {
            if (program.phases.empty()) {
                throw std::runtime_error("Program has no phases");
            }

            auto mat = std::make_shared<Material>();
            mat->name = name.is_none() ? program.program : nb::cast<std::string>(name);
            mat->source_path = source_path.is_none() ? "" : nb::cast<std::string>(source_path);
            mat->shader_name = program.program;
            mat->phases.clear();

            // Get MaterialPhase class for from_shader_phase
            nb::object MaterialPhase_cls = nb::module_::import_("termin._native.render").attr("MaterialPhase");

            for (const auto& shader_phase : program.phases) {
                MaterialPhase phase = nb::cast<MaterialPhase>(MaterialPhase_cls.attr("from_shader_phase")(
                    shader_phase, color, textures, uniforms, program.program
                ));
                mat->phases.push_back(std::move(phase));
            }

            return mat;
        }, nb::arg("program"),
           nb::arg("color") = nb::none(),
           nb::arg("textures") = nb::none(),
           nb::arg("uniforms") = nb::none(),
           nb::arg("name") = nb::none(),
           nb::arg("source_path") = nb::none())
        // serialize - serialize Material to dict
        .def("serialize", [](const Material& self) -> nb::dict {
            nb::dict result;

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

            nb::list phases_list;
            for (const auto& phase : self.phases) {
                // Serialize phase using its serialize method
                nb::dict phase_dict;
                phase_dict["phase_mark"] = phase.phase_mark;
                phase_dict["priority"] = phase.priority;

                // Color
                if (phase.color.has_value()) {
                    Vec4 c = phase.color.value();
                    nb::list col_list;
                    col_list.append(c.x);
                    col_list.append(c.y);
                    col_list.append(c.z);
                    col_list.append(c.w);
                    phase_dict["color"] = col_list;
                } else {
                    phase_dict["color"] = nb::none();
                }

                // Uniforms
                nb::dict uniforms_dict;
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
                            nb::list vec;
                            vec.append(arg.x);
                            vec.append(arg.y);
                            vec.append(arg.z);
                            uniforms_dict[key.c_str()] = vec;
                        } else if constexpr (std::is_same_v<T, Vec4>) {
                            nb::list vec;
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
                nb::dict textures_dict;
                for (const auto& [key, tex] : phase.textures) {
                    std::string path = tex.source_path();
                    if (!path.empty()) {
                        textures_dict[key.c_str()] = path;
                    }
                }
                phase_dict["textures"] = textures_dict;

                // Render state
                nb::dict rs_dict;
                rs_dict["depth_test"] = phase.render_state.depth_test;
                rs_dict["depth_write"] = phase.render_state.depth_write;
                rs_dict["blend"] = phase.render_state.blend;
                rs_dict["cull"] = phase.render_state.cull;
                phase_dict["render_state"] = rs_dict;

                // Shader sources
                nb::dict shader_dict;
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
        .def_static("deserialize", [](nb::dict data, nb::object context) -> std::shared_ptr<Material> {
            std::string type_str = "inline";
            if (data.contains("type")) {
                type_str = nb::cast<std::string>(data["type"]);
            }

            if (type_str == "path") {
                // Load from file
                std::string path = nb::cast<std::string>(data["path"]);
                if (!context.is_none() && nb::hasattr(context, "load_material")) {
                    return nb::cast<std::shared_ptr<Material>>(context.attr("load_material")(path));
                }
                throw std::runtime_error("Cannot deserialize path-based material without context");
            }

            // Inline deserialization
            auto mat = std::make_shared<Material>();
            if (data.contains("name")) {
                mat->name = nb::cast<std::string>(data["name"]);
            }
            if (data.contains("shader_name")) {
                mat->shader_name = nb::cast<std::string>(data["shader_name"]);
            }

            mat->phases.clear();
            if (data.contains("phases")) {
                nb::list phases_list = nb::cast<nb::list>(data["phases"]);
                for (auto phase_obj : phases_list) {
                    nb::dict phase_data = nb::cast<nb::dict>(phase_obj);

                    // Get shader sources
                    nb::dict shader_data = nb::cast<nb::dict>(phase_data["shader"]);
                    std::string vs = nb::cast<std::string>(shader_data["vertex"]);
                    std::string fs = nb::cast<std::string>(shader_data["fragment"]);
                    std::string gs = shader_data.contains("geometry") ?
                        nb::cast<std::string>(shader_data["geometry"]) : "";

                    auto shader = std::make_shared<ShaderProgram>(vs, fs, gs, "");

                    // Get render state
                    RenderState rs;
                    if (phase_data.contains("render_state")) {
                        nb::dict rs_data = nb::cast<nb::dict>(phase_data["render_state"]);
                        rs.depth_test = rs_data.contains("depth_test") ?
                            nb::cast<bool>(rs_data["depth_test"]) : true;
                        rs.depth_write = rs_data.contains("depth_write") ?
                            nb::cast<bool>(rs_data["depth_write"]) : true;
                        rs.blend = rs_data.contains("blend") ?
                            nb::cast<bool>(rs_data["blend"]) : false;
                        rs.cull = rs_data.contains("cull") ?
                            nb::cast<bool>(rs_data["cull"]) : true;
                    }

                    std::string phase_mark = phase_data.contains("phase_mark") ?
                        nb::cast<std::string>(phase_data["phase_mark"]) : "opaque";
                    int priority = phase_data.contains("priority") ?
                        nb::cast<int>(phase_data["priority"]) : 0;

                    MaterialPhase phase(shader, rs, phase_mark, priority);

                    // Color
                    if (phase_data.contains("color") && !phase_data["color"].is_none()) {
                        nb::list color_list = nb::cast<nb::list>(phase_data["color"]);
                        if (nb::len(color_list) >= 4) {
                            phase.set_color(Vec4{
                                nb::cast<float>(color_list[0]),
                                nb::cast<float>(color_list[1]),
                                nb::cast<float>(color_list[2]),
                                nb::cast<float>(color_list[3])
                            });
                        }
                    }

                    // Uniforms
                    if (phase_data.contains("uniforms")) {
                        nb::dict uniforms_dict = nb::cast<nb::dict>(phase_data["uniforms"]);
                        for (auto item : uniforms_dict) {
                            std::string key = nb::cast<std::string>(item.first);
                            nb::object val = nb::borrow<nb::object>(item.second);
                            if (nb::isinstance<nb::list>(val)) {
                                nb::list lst = nb::cast<nb::list>(val);
                                if (nb::len(lst) == 3) {
                                    phase.uniforms[key] = Vec3{
                                        nb::cast<float>(lst[0]),
                                        nb::cast<float>(lst[1]),
                                        nb::cast<float>(lst[2])
                                    };
                                } else if (nb::len(lst) == 4) {
                                    phase.uniforms[key] = Vec4{
                                        nb::cast<float>(lst[0]),
                                        nb::cast<float>(lst[1]),
                                        nb::cast<float>(lst[2]),
                                        nb::cast<float>(lst[3])
                                    };
                                }
                            } else if (nb::isinstance<nb::float_>(val)) {
                                phase.uniforms[key] = nb::cast<float>(val);
                            } else if (nb::isinstance<nb::int_>(val)) {
                                phase.uniforms[key] = nb::cast<int>(val);
                            } else if (nb::isinstance<nb::bool_>(val)) {
                                phase.uniforms[key] = nb::cast<bool>(val);
                            }
                        }
                    }

                    // Textures (if context provided)
                    if (phase_data.contains("textures") && !context.is_none()) {
                        nb::dict textures_dict = nb::cast<nb::dict>(phase_data["textures"]);
                        for (auto item : textures_dict) {
                            std::string key = nb::cast<std::string>(item.first);
                            std::string path = nb::cast<std::string>(item.second);
                            if (nb::hasattr(context, "load_texture")) {
                                phase.textures[key] = nb::cast<TextureHandle>(context.attr("load_texture")(path));
                            }
                        }
                    }

                    mat->phases.push_back(std::move(phase));
                }
            }

            return mat;
        }, nb::arg("data"), nb::arg("context") = nb::none());

    m.def("get_error_material", []() -> std::shared_ptr<Material> {
        static std::shared_ptr<Material> error_mat;
        if (!error_mat) {
            nb::object shader_mod = nb::module_::import_("termin.visualization.render.materials.default_material");
            auto shader = nb::cast<std::shared_ptr<ShaderProgram>>(shader_mod.attr("default_shader")());
            error_mat = std::make_shared<Material>(shader, RenderState::opaque(), "opaque", 0);
            error_mat->name = "__ErrorMaterial__";
            error_mat->shader_name = "DefaultShader";
            error_mat->set_color(Vec4{1.0, 0.0, 1.0, 1.0});
        }
        return error_mat;
    });
}

} // namespace termin
