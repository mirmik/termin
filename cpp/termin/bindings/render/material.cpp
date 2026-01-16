#include "common.hpp"
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/unordered_map.h>
#include <nanobind/stl/optional.h>
#include "termin/render/material.hpp"
#include "termin/material/tc_material_handle.hpp"
#include "termin/assets/handles.hpp"
#include "termin/render/shader_parser.hpp"
#include "termin/render/render_state.hpp"
#include "termin/render/render.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "termin/inspect/inspect_registry.hpp"
#include "../../../../core_c/include/tc_kind.hpp"
#include "tc_log.hpp"
extern "C" {
#include "tc_shader.h"
#include "tc_material_registry.h"
}

namespace termin {

void bind_material(nb::module_& m) {
    // MaterialPhase
    nb::class_<MaterialPhase>(m, "MaterialPhase")
        .def(nb::init<>())
        .def("__init__", [](MaterialPhase* self, TcShader shader, const RenderState& rs,
                         const std::string& phase_mark, int priority) {
            new (self) MaterialPhase(std::move(shader), rs, phase_mark, priority);
        }, nb::arg("shader"), nb::arg("render_state") = RenderState::opaque(),
            nb::arg("phase_mark") = "opaque", nb::arg("priority") = 0)
        // Python-compatible kwargs constructor (supports shader_programm, color)
        .def("__init__", [](MaterialPhase* self, nb::kwargs kwargs) {
            TcShader shader;
            if (kwargs.contains("shader_programm")) {
                shader = nb::cast<TcShader>(kwargs["shader_programm"]);
            } else if (kwargs.contains("shader")) {
                shader = nb::cast<TcShader>(kwargs["shader"]);
            }
            if (!shader.is_valid()) {
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

            new (self) MaterialPhase(std::move(shader), rs, phase_mark, priority);

            // Set color
            if (kwargs.contains("color") && !kwargs["color"].is_none()) {
                nb::object color_obj = nb::borrow<nb::object>(kwargs["color"]);
                if (nb::isinstance<Vec4>(color_obj)) {
                    self->set_color(nb::cast<Vec4>(color_obj));
                } else if (nb::ndarray_check(color_obj)) {
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
                    // Accept both TextureHandle and TcTexture
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<TcTexture>(val)) {
                        self->textures[key] = nb::cast<TcTexture>(val);
                    } else {
                        TextureHandle handle = nb::cast<TextureHandle>(val);
                        self->textures[key] = handle.get();
                    }
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
                    } else if (nb::isinstance<Vec3>(val)) {
                        self->uniforms[key] = nb::cast<Vec3>(val);
                    } else if (nb::isinstance<Vec4>(val)) {
                        self->uniforms[key] = nb::cast<Vec4>(val);
                    }
                }
            }
        })
        .def_rw("shader", &MaterialPhase::shader)
        .def_rw("shader_programm", &MaterialPhase::shader)  // Python compatibility alias
        .def_rw("render_state", &MaterialPhase::render_state)
        .def_prop_rw("color",
            [](const MaterialPhase& self) -> std::optional<Vec4> {
                return self.color();
            },
            [](MaterialPhase& self, nb::object val) {
                if (val.is_none()) {
                    self.uniforms.erase("u_color");
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
        .def("set_texture", [](MaterialPhase& self, const std::string& name, TextureHandle handle) {
            self.textures[name] = handle.get();
        }, nb::arg("name"), nb::arg("handle"), "Set texture by uniform name (from TextureHandle)")
        .def("set_texture", [](MaterialPhase& self, const std::string& name, TcTexture tex) {
            self.textures[name] = tex;
        }, nb::arg("name"), nb::arg("tex"), "Set texture by uniform name (from TcTexture)")
        .def("get_texture", [](MaterialPhase& self, const std::string& name) -> nb::object {
            auto it = self.textures.find(name);
            if (it != self.textures.end()) {
                return nb::cast(it->second);
            }
            return nb::none();
        }, nb::arg("name"), "Get texture by uniform name (returns TcTexture)")
        .def_prop_rw("textures",
            [](MaterialPhase& self) -> nb::dict {
                nb::dict result;
                for (const auto& [key, tex] : self.textures) {
                    result[key.c_str()] = tex;
                }
                return result;
            },
            [](MaterialPhase& self, nb::dict textures) {
                self.textures.clear();
                for (auto item : textures) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<TcTexture>(val)) {
                        self.textures[key] = nb::cast<TcTexture>(val);
                    } else {
                        TextureHandle handle = nb::cast<TextureHandle>(val);
                        self.textures[key] = handle.get();
                    }
                }
            })
        .def_prop_rw("uniforms",
            [](MaterialPhase& self) -> nb::dict {
                nb::dict result;
                for (const auto& [key, val] : self.uniforms) {
                    std::visit([&](auto&& arg) {
                        using T = std::decay_t<decltype(arg)>;
                        if constexpr (std::is_same_v<T, bool> || std::is_same_v<T, int> ||
                                      std::is_same_v<T, float> || std::is_same_v<T, Vec3> ||
                                      std::is_same_v<T, Vec4>) {
                            result[key.c_str()] = arg;
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
                    } else if (nb::isinstance<Vec3>(val)) {
                        self.uniforms[key] = nb::cast<Vec3>(val);
                    } else if (nb::isinstance<Vec4>(val)) {
                        self.uniforms[key] = nb::cast<Vec4>(val);
                    }
                }
            })
        .def("set_texture", [](MaterialPhase& self, const std::string& name, const TextureHandle& tex) {
            self.textures[name] = tex.get();
        })
        .def("set_param", [](MaterialPhase& self, const std::string& name, nb::object value) {
            if (nb::isinstance<nb::bool_>(value)) {
                self.set_param(name, nb::cast<bool>(value));
            } else if (nb::isinstance<nb::int_>(value)) {
                self.set_param(name, nb::cast<int>(value));
            } else if (nb::isinstance<nb::float_>(value)) {
                self.set_param(name, nb::cast<float>(value));
            } else if (nb::isinstance<Vec3>(value)) {
                self.set_param(name, nb::cast<Vec3>(value));
            } else if (nb::isinstance<Vec4>(value)) {
                self.set_param(name, nb::cast<Vec4>(value));
            } else if (nb::isinstance<Mat44>(value)) {
                // Mat44 is already column-major, convert to Mat44f
                self.set_param(name, nb::cast<Mat44>(value).to_float());
            } else if (nb::isinstance<Mat44f>(value)) {
                // Mat44f is already in the right format
                self.set_param(name, nb::cast<Mat44f>(value));
            } else if (nb::ndarray_check(value)) {
                // Try to cast as 4x4 matrix (float32 or float64)
                try {
                    auto arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(value);
                    Mat44f mat;
                    // Convert row-major numpy to column-major Mat44f
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            mat.data[col * 4 + row] = arr(row, col);
                        }
                    }
                    self.set_param(name, mat);
                } catch (const nb::cast_error&) {
                    try {
                        auto arr = nb::cast<nb::ndarray<nb::numpy, double, nb::shape<4, 4>>>(value);
                        Mat44f mat;
                        // Convert row-major numpy to column-major Mat44f
                        for (int row = 0; row < 4; ++row) {
                            for (int col = 0; col < 4; ++col) {
                                mat.data[col * 4 + row] = static_cast<float>(arr(row, col));
                            }
                        }
                        self.set_param(name, mat);
                    } catch (const nb::cast_error&) {
                        // Unsupported array type
                    }
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
        // Mat44 overload (column-major, no conversion needed)
        .def("apply", [](MaterialPhase& self,
                         const Mat44& model, const Mat44& view, const Mat44& proj,
                         GraphicsBackend* graphics, int64_t context_key) {
            self.apply(model.to_float(), view.to_float(), proj.to_float(), graphics, context_key);
        }, nb::arg("model"), nb::arg("view"), nb::arg("projection"),
           nb::arg("graphics"), nb::arg("context_key") = 0)
        .def("apply_state", &MaterialPhase::apply_state)
        .def("copy", &MaterialPhase::copy)
        // serialize - serialize MaterialPhase to dict
        .def("serialize", [](const MaterialPhase& self) -> nb::dict {
            nb::dict result;
            result["phase_mark"] = self.phase_mark;
            result["priority"] = self.priority;

            // Color (from u_color uniform)
            auto col = self.color();
            if (col.has_value()) {
                Vec4 c = col.value();
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
            if (self.shader.is_valid()) {
                shader_dict["vertex"] = self.shader.vertex_source();
                shader_dict["fragment"] = self.shader.fragment_source();
                shader_dict["geometry"] = self.shader.geometry_source();
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

            TcShader shader = TcShader::from_sources(vs, fs, gs, "deserialized");

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

            auto phase = std::make_shared<MaterialPhase>(std::move(shader), rs, phase_mark, priority);

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
                        TextureHandle handle = nb::cast<TextureHandle>(context.attr("load_texture")(path));
                        phase->textures[key] = handle.get();
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
            const std::string& program_name,
            const std::string& phase_uuid,
            const std::vector<std::string>& features
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

            // phase_uuid is passed directly (generated by Python using uuid5)
            TcShader shader;
            if (!phase_uuid.empty()) {
                shader = TcShader::get_or_create(phase_uuid);
                shader.set_sources(vs, fs, gs, shader_name, "");
            } else {
                shader = TcShader::from_sources(vs, fs, gs, shader_name, "");
            }

            // Apply features to the shader
            for (const auto& feature : features) {
                if (feature == "lighting_ubo") {
                    shader.set_feature(TC_SHADER_FEATURE_LIGHTING_UBO);
                }
                // Add more feature mappings here as needed
            }

            // 2. Build RenderState from gl-flags
            RenderState rs;
            rs.depth_write = shader_phase.gl_depth_mask.value_or(true);
            rs.depth_test = shader_phase.gl_depth_test.value_or(true);
            rs.blend = shader_phase.gl_blend.value_or(false);
            rs.cull = shader_phase.gl_cull.value_or(true);

            MaterialPhase phase(std::move(shader), rs, shader_phase.phase_mark, shader_phase.priority);
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
                    } else if (nb::isinstance<Vec3>(val)) {
                        phase.uniforms[key] = nb::cast<Vec3>(val);
                    } else if (nb::isinstance<Vec4>(val)) {
                        phase.uniforms[key] = nb::cast<Vec4>(val);
                    }
                }
            }

            // 5. Set textures (use appropriate default texture based on property default_value)
            nb::object tex_handle_module = nb::module_::import_("termin.visualization.core.texture_handle");
            nb::object white_tex_fn = tex_handle_module.attr("get_white_texture_handle");
            nb::object normal_tex_fn = tex_handle_module.attr("get_normal_texture_handle");
            TcTexture white_tex = nb::cast<TextureHandle>(white_tex_fn()).get();
            TcTexture normal_tex = nb::cast<TextureHandle>(normal_tex_fn()).get();

            for (const auto& prop : shader_phase.uniforms) {
                if (prop.property_type == "Texture") {
                    // Check if default_value specifies "normal" texture
                    if (std::holds_alternative<std::string>(prop.default_value)) {
                        const std::string& default_tex_name = std::get<std::string>(prop.default_value);
                        if (default_tex_name == "normal") {
                            phase.textures[prop.name] = normal_tex;
                        } else {
                            phase.textures[prop.name] = white_tex;
                        }
                    } else {
                        phase.textures[prop.name] = white_tex;
                    }
                }
            }

            // Override with provided textures
            if (!textures.is_none()) {
                nb::dict tex_dict = nb::cast<nb::dict>(textures);
                for (auto item : tex_dict) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<TcTexture>(val)) {
                        phase.textures[key] = nb::cast<TcTexture>(val);
                    } else {
                        phase.textures[key] = nb::cast<TextureHandle>(val).get();
                    }
                }
            }

            // 6. Set color
            if (!color.is_none()) {
                if (nb::isinstance<Vec4>(color)) {
                    phase.set_color(nb::cast<Vec4>(color));
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
           nb::arg("program_name") = "",
           nb::arg("phase_uuid") = "",
           nb::arg("features") = std::vector<std::string>{});

    // Material
    nb::class_<Material>(m, "Material")
        .def(nb::init<>())
        .def("__init__", [](Material* self, TcShader shader, const RenderState& rs,
                         const std::string& phase_mark, int priority) {
            new (self) Material(std::move(shader), rs, phase_mark, priority);
        }, nb::arg("shader"), nb::arg("render_state") = RenderState::opaque(),
            nb::arg("phase_mark") = "opaque", nb::arg("priority") = 0)
        // Python-compatible kwargs constructor
        .def("__init__", [](Material* self, nb::kwargs kwargs) {
            // Get default shader if not provided
            TcShader shader;
            if (kwargs.contains("shader")) {
                shader = nb::cast<TcShader>(kwargs["shader"]);
            } else {
                // Import default shader
                nb::object shader_mod = nb::module_::import_("termin.visualization.render.materials.default_material");
                shader = nb::cast<TcShader>(shader_mod.attr("default_shader")());
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

            new (self) Material(std::move(shader), rs, phase_mark, priority);

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
                if (nb::isinstance<Vec4>(color_obj)) {
                    self->set_color(nb::cast<Vec4>(color_obj));
                } else if (nb::ndarray_check(color_obj)) {
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
                    TextureHandle handle = nb::cast<TextureHandle>(item.second);
                    self->set_texture(key, handle);
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
                    } else if (nb::isinstance<Vec3>(val)) {
                        self->default_phase().uniforms[key] = nb::cast<Vec3>(val);
                    } else if (nb::isinstance<Vec4>(val)) {
                        self->default_phase().uniforms[key] = nb::cast<Vec4>(val);
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
            [](Material& self, TcShader shader) {
                self.default_phase().shader = std::move(shader);
            })
        .def("set_shader", [](Material& self, TcShader shader, const std::string& shader_name) {
            // Update shader in all phases
            for (auto& phase : self.phases) {
                phase.shader = shader;
            }
            self.shader_name = shader_name;
        }, nb::arg("shader"), nb::arg("shader_name") = "")
        // Overload for multi-phase shader program
        .def("set_shader", [](Material& self, const ShaderMultyPhaseProgramm& program, const std::string& shader_name, const std::string& shader_uuid) {
            if (program.phases.empty()) {
                throw std::runtime_error("Program has no phases");
            }

            // Preserve existing color, textures, uniforms from first phase
            std::optional<Vec4> old_color;
            std::unordered_map<std::string, TcTexture> old_textures;
            std::unordered_map<std::string, MaterialUniformValue> old_uniforms;

            if (!self.phases.empty()) {
                old_color = self.phases[0].color();
                old_textures = self.phases[0].textures;
                old_uniforms = self.phases[0].uniforms;
            }

            // Clear and rebuild phases
            self.phases.clear();
            self.shader_name = shader_name.empty() ? program.program : shader_name;

            // Get MaterialPhase class for from_shader_phase
            nb::object MaterialPhase_cls = nb::module_::import_("termin._native.render").attr("MaterialPhase");

            // Pass Vec4 directly if available
            nb::object py_color = old_color.has_value() ? nb::cast(old_color.value()) : nb::none();

            for (const auto& shader_phase : program.phases) {
                MaterialPhase phase = nb::cast<MaterialPhase>(MaterialPhase_cls.attr("from_shader_phase")(
                    shader_phase, py_color, nb::none(), nb::none(), program.program, shader_uuid, program.features
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
        }, nb::arg("program"), nb::arg("shader_name") = "", nb::arg("shader_uuid") = "")
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
                return self.texture_handles;
            },
            [](Material& self, const std::unordered_map<std::string, TextureHandle>& textures) {
                for (const auto& [name, handle] : textures) {
                    self.set_texture(name, handle);
                }
            }, nb::rv_policy::reference)
        .def_prop_rw("uniforms",
            [](Material& self) -> nb::dict {
                nb::dict result;
                for (const auto& [key, val] : self.default_phase().uniforms) {
                    std::visit([&](auto&& arg) {
                        using T = std::decay_t<decltype(arg)>;
                        if constexpr (std::is_same_v<T, bool> || std::is_same_v<T, int> ||
                                      std::is_same_v<T, float> || std::is_same_v<T, Vec3> ||
                                      std::is_same_v<T, Vec4>) {
                            result[key.c_str()] = arg;
                        }
                    }, val);
                }
                return result;
            },
            [](Material& self, nb::dict uniforms) {
                for (auto item : uniforms) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<nb::bool_>(val)) {
                        self.default_phase().uniforms[key] = nb::cast<bool>(val);
                    } else if (nb::isinstance<nb::int_>(val)) {
                        self.default_phase().uniforms[key] = nb::cast<int>(val);
                    } else if (nb::isinstance<nb::float_>(val)) {
                        self.default_phase().uniforms[key] = nb::cast<float>(val);
                    } else if (nb::isinstance<Vec3>(val)) {
                        self.default_phase().uniforms[key] = nb::cast<Vec3>(val);
                    } else if (nb::isinstance<Vec4>(val)) {
                        self.default_phase().uniforms[key] = nb::cast<Vec4>(val);
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
            } else if (nb::isinstance<Vec3>(value)) {
                self.set_param(name, nb::cast<Vec3>(value));
            } else if (nb::isinstance<Vec4>(value)) {
                self.set_param(name, nb::cast<Vec4>(value));
            } else if (nb::isinstance<Mat44>(value)) {
                // Mat44 is already column-major, convert to Mat44f
                self.set_param(name, nb::cast<Mat44>(value).to_float());
            } else if (nb::isinstance<Mat44f>(value)) {
                // Mat44f is already in the right format
                self.set_param(name, nb::cast<Mat44f>(value));
            } else if (nb::ndarray_check(value)) {
                // Try to cast as 4x4 matrix (float32 or float64)
                try {
                    auto arr = nb::cast<nb::ndarray<nb::numpy, float, nb::shape<4, 4>>>(value);
                    Mat44f mat;
                    // Convert row-major numpy to column-major Mat44f
                    for (int row = 0; row < 4; ++row) {
                        for (int col = 0; col < 4; ++col) {
                            mat.data[col * 4 + row] = arr(row, col);
                        }
                    }
                    self.set_param(name, mat);
                } catch (const nb::cast_error&) {
                    try {
                        auto arr = nb::cast<nb::ndarray<nb::numpy, double, nb::shape<4, 4>>>(value);
                        Mat44f mat;
                        // Convert row-major numpy to column-major Mat44f
                        for (int row = 0; row < 4; ++row) {
                            for (int col = 0; col < 4; ++col) {
                                mat.data[col * 4 + row] = static_cast<float>(arr(row, col));
                            }
                        }
                        self.set_param(name, mat);
                    } catch (const nb::cast_error&) {
                        // Unsupported array type
                    }
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
        // Mat44 overload (column-major, no conversion needed)
        .def("apply", [](Material& self,
                         const Mat44& model, const Mat44& view, const Mat44& proj,
                         GraphicsBackend* graphics, int64_t context_key) {
            self.apply(model.to_float(), view.to_float(), proj.to_float(), graphics, context_key);
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
            nb::object source_path,
            const std::string& shader_uuid
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
                    shader_phase, color, textures, uniforms, program.program, shader_uuid, program.features
                ));
                mat->phases.push_back(std::move(phase));
            }

            return mat;
        }, nb::arg("program"),
           nb::arg("color") = nb::none(),
           nb::arg("textures") = nb::none(),
           nb::arg("uniforms") = nb::none(),
           nb::arg("name") = nb::none(),
           nb::arg("source_path") = nb::none(),
           nb::arg("shader_uuid") = "")
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

                // Color (from u_color uniform)
                auto col = phase.color();
                if (col.has_value()) {
                    Vec4 c = col.value();
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
                if (phase.shader.is_valid()) {
                    shader_dict["vertex"] = phase.shader.vertex_source();
                    shader_dict["fragment"] = phase.shader.fragment_source();
                    shader_dict["geometry"] = phase.shader.geometry_source();
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

                    TcShader shader = TcShader::from_sources(vs, fs, gs, "deserialized");

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

                    MaterialPhase phase(std::move(shader), rs, phase_mark, priority);

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
                                TextureHandle handle = nb::cast<TextureHandle>(context.attr("load_texture")(path));
                                phase.textures[key] = handle.get();
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
            TcShader shader = nb::cast<TcShader>(shader_mod.attr("default_shader")());
            error_mat = std::make_shared<Material>(std::move(shader), RenderState::opaque(), "opaque", 0);
            error_mat->name = "__ErrorMaterial__";
            error_mat->shader_name = "DefaultShader";
            error_mat->set_color(Vec4{1.0, 0.0, 1.0, 1.0});
        }
        return error_mat;
    });
}

void bind_tc_material(nb::module_& m) {
    // tc_render_state struct
    nb::class_<tc_render_state>(m, "TcRenderState")
        .def(nb::init<>())
        .def_rw("polygon_mode", &tc_render_state::polygon_mode)
        .def_rw("cull", &tc_render_state::cull)
        .def_rw("depth_test", &tc_render_state::depth_test)
        .def_rw("depth_write", &tc_render_state::depth_write)
        .def_rw("blend", &tc_render_state::blend)
        .def_rw("blend_src", &tc_render_state::blend_src)
        .def_rw("blend_dst", &tc_render_state::blend_dst)
        .def_rw("depth_func", &tc_render_state::depth_func)
        .def_static("opaque", &tc_render_state_opaque)
        .def_static("transparent", &tc_render_state_transparent)
        .def_static("wireframe", &tc_render_state_wireframe);

    // tc_material_phase struct (opaque pointer, limited access)
    nb::class_<tc_material_phase>(m, "TcMaterialPhase")
        .def_prop_ro("phase_mark", [](tc_material_phase& p) { return p.phase_mark; })
        .def_prop_ro("priority", [](tc_material_phase& p) { return p.priority; })
        .def_prop_ro("texture_count", [](tc_material_phase& p) { return p.texture_count; })
        .def_prop_ro("uniform_count", [](tc_material_phase& p) { return p.uniform_count; })
        .def_prop_ro("shader", [](tc_material_phase& p) { return TcShader(p.shader); })
        .def_prop_ro("textures", [](tc_material_phase& p) {
            nb::dict result;
            for (size_t i = 0; i < p.texture_count; i++) {
                std::string name = p.textures[i].name;
                if (!tc_texture_handle_is_invalid(p.textures[i].texture)) {
                    result[nb::cast(name)] = TcTexture(p.textures[i].texture);
                }
            }
            return result;
        })
        .def_prop_ro("uniforms", [](tc_material_phase& p) {
            nb::dict result;
            for (size_t i = 0; i < p.uniform_count; i++) {
                std::string name = p.uniforms[i].name;
                tc_uniform_value& u = p.uniforms[i];
                switch (u.type) {
                    case TC_UNIFORM_BOOL:
                    case TC_UNIFORM_INT:
                        result[nb::cast(name)] = u.data.i;
                        break;
                    case TC_UNIFORM_FLOAT:
                        result[nb::cast(name)] = u.data.f;
                        break;
                    case TC_UNIFORM_VEC2:
                        result[nb::cast(name)] = nb::make_tuple(u.data.v2[0], u.data.v2[1]);
                        break;
                    case TC_UNIFORM_VEC3:
                        result[nb::cast(name)] = Vec3{u.data.v3[0], u.data.v3[1], u.data.v3[2]};
                        break;
                    case TC_UNIFORM_VEC4:
                        result[nb::cast(name)] = Vec4{u.data.v4[0], u.data.v4[1], u.data.v4[2], u.data.v4[3]};
                        break;
                    default:
                        break;
                }
            }
            return result;
        })
        .def_prop_rw("state",
            [](tc_material_phase& p) { return p.state; },
            [](tc_material_phase& p, const tc_render_state& s) { p.state = s; })
        .def("set_uniform_float", [](tc_material_phase& p, const char* name, float v) {
            tc_material_phase_set_uniform(&p, name, TC_UNIFORM_FLOAT, &v);
        })
        .def("set_uniform_int", [](tc_material_phase& p, const char* name, int v) {
            tc_material_phase_set_uniform(&p, name, TC_UNIFORM_INT, &v);
        })
        .def("set_uniform_vec3", [](tc_material_phase& p, const char* name, const Vec3& v) {
            float arr[3] = {(float)v.x, (float)v.y, (float)v.z};
            tc_material_phase_set_uniform(&p, name, TC_UNIFORM_VEC3, arr);
        })
        .def("set_uniform_vec4", [](tc_material_phase& p, const char* name, const Vec4& v) {
            float arr[4] = {(float)v.x, (float)v.y, (float)v.z, (float)v.w};
            tc_material_phase_set_uniform(&p, name, TC_UNIFORM_VEC4, arr);
        })
        .def("set_texture", [](tc_material_phase& p, const char* name, TcTexture& tex) {
            tc_material_phase_set_texture(&p, name, tex.handle);
        })
        // Overload for TextureHandle (Material API compatibility)
        .def("set_texture", [](tc_material_phase& p, const char* name, TextureHandle& handle) {
            TcTexture tex = handle.get();
            if (tex.is_valid()) {
                tc_material_phase_set_texture(&p, name, tex.handle);
            }
        })
        .def("set_color", [](tc_material_phase& p, float r, float g, float b, float a) {
            tc_material_phase_set_color(&p, r, g, b, a);
        })
        .def("set_available_marks", [](tc_material_phase& p, const std::vector<std::string>& marks) {
            p.available_mark_count = std::min(marks.size(), (size_t)TC_MATERIAL_MAX_MARKS);
            for (size_t i = 0; i < p.available_mark_count; i++) {
                strncpy(p.available_marks[i], marks[i].c_str(), TC_PHASE_MARK_MAX - 1);
                p.available_marks[i][TC_PHASE_MARK_MAX - 1] = '\0';
            }
        })
        .def("get_available_marks", [](tc_material_phase& p) -> std::vector<std::string> {
            std::vector<std::string> result;
            for (size_t i = 0; i < p.available_mark_count; i++) {
                result.push_back(p.available_marks[i]);
            }
            return result;
        })
        // available_marks property for Material API compatibility
        .def_prop_ro("available_marks", [](tc_material_phase& p) -> std::vector<std::string> {
            std::vector<std::string> result;
            for (size_t i = 0; i < p.available_mark_count; i++) {
                result.push_back(p.available_marks[i]);
            }
            return result;
        })
        // set_phase_mark for Material API compatibility
        .def("set_phase_mark", [](tc_material_phase& p, const std::string& mark) {
            strncpy(p.phase_mark, mark.c_str(), TC_PHASE_MARK_MAX - 1);
            p.phase_mark[TC_PHASE_MARK_MAX - 1] = '\0';
        }, nb::arg("mark"))
        // set_param for Material API compatibility (variant-based uniform setter)
        .def("set_param", [](tc_material_phase& p, const std::string& name, nb::object value) {
            if (nb::isinstance<nb::bool_>(value)) {
                int v = nb::cast<bool>(value) ? 1 : 0;
                tc_material_phase_set_uniform(&p, name.c_str(), TC_UNIFORM_INT, &v);
            } else if (nb::isinstance<nb::int_>(value)) {
                int v = nb::cast<int>(value);
                tc_material_phase_set_uniform(&p, name.c_str(), TC_UNIFORM_INT, &v);
            } else if (nb::isinstance<nb::float_>(value)) {
                float v = nb::cast<float>(value);
                tc_material_phase_set_uniform(&p, name.c_str(), TC_UNIFORM_FLOAT, &v);
            } else if (nb::isinstance<Vec3>(value)) {
                Vec3 v = nb::cast<Vec3>(value);
                float arr[3] = {(float)v.x, (float)v.y, (float)v.z};
                tc_material_phase_set_uniform(&p, name.c_str(), TC_UNIFORM_VEC3, arr);
            } else if (nb::isinstance<Vec4>(value)) {
                Vec4 v = nb::cast<Vec4>(value);
                float arr[4] = {(float)v.x, (float)v.y, (float)v.z, (float)v.w};
                tc_material_phase_set_uniform(&p, name.c_str(), TC_UNIFORM_VEC4, arr);
            } else if (nb::ndarray_check(value)) {
                nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(value);
                size_t size = arr.size();
                float* ptr = arr.data();
                if (size == 2) {
                    tc_material_phase_set_uniform(&p, name.c_str(), TC_UNIFORM_VEC2, ptr);
                } else if (size == 3) {
                    tc_material_phase_set_uniform(&p, name.c_str(), TC_UNIFORM_VEC3, ptr);
                } else if (size == 4) {
                    tc_material_phase_set_uniform(&p, name.c_str(), TC_UNIFORM_VEC4, ptr);
                } else if (size == 16) {
                    tc_material_phase_set_uniform(&p, name.c_str(), TC_UNIFORM_MAT4, ptr);
                }
            }
        }, nb::arg("name"), nb::arg("value"));

    nb::class_<TcMaterial>(m, "TcMaterial")
        .def(nb::init<>())
        // kwargs constructor for Material API compatibility
        .def("__init__", [](TcMaterial* self, nb::kwargs kwargs) {
            // Create material
            std::string mat_name = "";
            if (kwargs.contains("name")) {
                mat_name = nb::cast<std::string>(kwargs["name"]);
            }

            TcMaterial mat = TcMaterial::create(mat_name, "");
            if (!mat.is_valid()) {
                throw std::runtime_error("Failed to create TcMaterial");
            }

            // Get shader
            TcShader shader;
            if (kwargs.contains("shader")) {
                shader = nb::cast<TcShader>(kwargs["shader"]);
            } else if (kwargs.contains("shader_programm")) {
                shader = nb::cast<TcShader>(kwargs["shader_programm"]);
            }

            // Get render state
            tc_render_state rs = tc_render_state_opaque();
            if (kwargs.contains("render_state")) {
                nb::object rs_obj = nb::borrow<nb::object>(kwargs["render_state"]);
                if (nb::isinstance<tc_render_state>(rs_obj)) {
                    rs = nb::cast<tc_render_state>(rs_obj);
                } else if (nb::isinstance<RenderState>(rs_obj)) {
                    RenderState old_rs = nb::cast<RenderState>(rs_obj);
                    rs.depth_test = old_rs.depth_test;
                    rs.depth_write = old_rs.depth_write;
                    rs.blend = old_rs.blend;
                    rs.cull = old_rs.cull;
                }
            }

            std::string phase_mark = "opaque";
            if (kwargs.contains("phase_mark")) {
                phase_mark = nb::cast<std::string>(kwargs["phase_mark"]);
            }

            int priority = 0;
            if (kwargs.contains("priority")) {
                priority = nb::cast<int>(kwargs["priority"]);
            }

            // Add phase with shader
            tc_material_phase* phase = nullptr;
            if (shader.is_valid()) {
                phase = mat.add_phase(shader, phase_mark.c_str(), priority);
                if (phase) {
                    phase->state = rs;
                }
            }

            // Set other properties
            if (kwargs.contains("source_path")) {
                mat.set_source_path(nb::cast<std::string>(kwargs["source_path"]).c_str());
            }
            if (kwargs.contains("shader_name")) {
                mat.set_shader_name(nb::cast<std::string>(kwargs["shader_name"]).c_str());
            }

            // Set color
            if (kwargs.contains("color") && !kwargs["color"].is_none() && phase) {
                nb::object color_obj = nb::borrow<nb::object>(kwargs["color"]);
                if (nb::isinstance<Vec4>(color_obj)) {
                    Vec4 c = nb::cast<Vec4>(color_obj);
                    tc_material_phase_set_color(phase, c.x, c.y, c.z, c.w);
                } else if (nb::ndarray_check(color_obj)) {
                    nb::ndarray<nb::numpy, float> arr = nb::cast<nb::ndarray<nb::numpy, float>>(color_obj);
                    float* ptr = arr.data();
                    tc_material_phase_set_color(phase, ptr[0], ptr[1], ptr[2], ptr[3]);
                } else if (nb::isinstance<nb::tuple>(color_obj) || nb::isinstance<nb::list>(color_obj)) {
                    nb::sequence seq = nb::cast<nb::sequence>(color_obj);
                    tc_material_phase_set_color(phase,
                        nb::cast<float>(seq[0]),
                        nb::cast<float>(seq[1]),
                        nb::cast<float>(seq[2]),
                        nb::cast<float>(seq[3])
                    );
                }
            }

            // Set textures
            if (kwargs.contains("textures") && !kwargs["textures"].is_none() && phase) {
                nb::dict tex_dict = nb::cast<nb::dict>(kwargs["textures"]);
                for (auto item : tex_dict) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<TcTexture>(val)) {
                        TcTexture tex = nb::cast<TcTexture>(val);
                        tc_material_phase_set_texture(phase, key.c_str(), tex.handle);
                    } else {
                        TextureHandle handle = nb::cast<TextureHandle>(val);
                        TcTexture tex = handle.get();
                        if (tex.is_valid()) {
                            tc_material_phase_set_texture(phase, key.c_str(), tex.handle);
                        }
                    }
                }
            }

            // Set uniforms
            if (kwargs.contains("uniforms") && !kwargs["uniforms"].is_none() && phase) {
                nb::dict uniforms_dict = nb::cast<nb::dict>(kwargs["uniforms"]);
                for (auto item : uniforms_dict) {
                    std::string key = nb::cast<std::string>(item.first);
                    nb::object val = nb::borrow<nb::object>(item.second);
                    if (nb::isinstance<nb::bool_>(val)) {
                        int v = nb::cast<bool>(val) ? 1 : 0;
                        tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_INT, &v);
                    } else if (nb::isinstance<nb::int_>(val)) {
                        int v = nb::cast<int>(val);
                        tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_INT, &v);
                    } else if (nb::isinstance<nb::float_>(val)) {
                        float v = nb::cast<float>(val);
                        tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_FLOAT, &v);
                    } else if (nb::isinstance<Vec3>(val)) {
                        Vec3 v = nb::cast<Vec3>(val);
                        float arr[3] = {(float)v.x, (float)v.y, (float)v.z};
                        tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_VEC3, arr);
                    } else if (nb::isinstance<Vec4>(val)) {
                        Vec4 v = nb::cast<Vec4>(val);
                        float arr[4] = {(float)v.x, (float)v.y, (float)v.z, (float)v.w};
                        tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_VEC4, arr);
                    }
                }
            }

            // Use placement new to construct in-place
            new (self) TcMaterial(std::move(mat));
        })
        .def_static("from_uuid", &TcMaterial::from_uuid, nb::arg("uuid"))
        .def_static("from_name", &TcMaterial::from_name, nb::arg("name"))
        .def_static("get_or_create", &TcMaterial::get_or_create, nb::arg("uuid"))
        .def_static("create", &TcMaterial::create,
            nb::arg("name") = "", nb::arg("uuid_hint") = "")
        .def_static("copy", &TcMaterial::copy, nb::arg("src"), nb::arg("new_uuid") = "")
        .def_prop_ro("is_valid", &TcMaterial::is_valid)
        .def_prop_ro("uuid", &TcMaterial::uuid)
        .def_prop_rw("name",
            &TcMaterial::name,
            &TcMaterial::set_name)
        .def_prop_ro("version", &TcMaterial::version)
        .def_prop_rw("shader_name",
            &TcMaterial::shader_name,
            &TcMaterial::set_shader_name)
        .def_prop_rw("source_path",
            &TcMaterial::source_path,
            &TcMaterial::set_source_path)
        .def_prop_ro("phase_count", &TcMaterial::phase_count)
        .def("get_phase", [](TcMaterial& self, size_t index) -> tc_material_phase* {
            return self.get_phase(index);
        }, nb::arg("index"), nb::rv_policy::reference)
        .def_prop_ro("phases", [](TcMaterial& self) {
            nb::list result;
            for (size_t i = 0; i < self.phase_count(); i++) {
                result.append(nb::cast(self.get_phase(i), nb::rv_policy::reference));
            }
            return result;
        })
        .def("default_phase", [](TcMaterial& self) -> tc_material_phase* {
            return self.default_phase();
        }, nb::rv_policy::reference)
        .def("add_phase_from_sources", [](
            TcMaterial& self,
            const std::string& vertex_source,
            const std::string& fragment_source,
            const std::string& geometry_source,
            const std::string& shader_name,
            const std::string& phase_mark,
            int priority,
            const tc_render_state& state
        ) -> tc_material_phase* {
            return self.add_phase_from_sources(
                vertex_source.c_str(),
                fragment_source.c_str(),
                geometry_source.empty() ? nullptr : geometry_source.c_str(),
                shader_name.c_str(),
                phase_mark.c_str(),
                priority,
                state
            );
        }, nb::arg("vertex_source"), nb::arg("fragment_source"),
           nb::arg("geometry_source") = "", nb::arg("shader_name") = "",
           nb::arg("phase_mark") = "opaque", nb::arg("priority") = 0,
           nb::arg("state") = tc_render_state_opaque(),
           nb::rv_policy::reference)
        .def("bump_version", &TcMaterial::bump_version)
        // Color
        .def_prop_rw("color",
            [](const TcMaterial& self) -> nb::object {
                auto c = self.color();
                if (!c.has_value()) return nb::none();
                return nb::cast(c.value());
            },
            [](TcMaterial& self, nb::object val) {
                if (val.is_none()) return;
                if (nb::isinstance<Vec4>(val)) {
                    self.set_color(nb::cast<Vec4>(val));
                } else if (nb::isinstance<nb::tuple>(val) || nb::isinstance<nb::list>(val)) {
                    nb::sequence seq = nb::cast<nb::sequence>(val);
                    self.set_color(
                        nb::cast<float>(seq[0]),
                        nb::cast<float>(seq[1]),
                        nb::cast<float>(seq[2]),
                        nb::cast<float>(seq[3])
                    );
                }
            })
        .def("set_color", [](TcMaterial& self, float r, float g, float b, float a) {
            self.set_color(r, g, b, a);
        }, nb::arg("r"), nb::arg("g"), nb::arg("b"), nb::arg("a") = 1.0f)
        // Uniforms
        .def("set_uniform_float", &TcMaterial::set_uniform_float)
        .def("set_uniform_int", &TcMaterial::set_uniform_int)
        .def("set_uniform_vec3", &TcMaterial::set_uniform_vec3)
        .def("set_uniform_vec4", &TcMaterial::set_uniform_vec4)
        // Phase access
        .def_prop_rw("active_phase_mark",
            &TcMaterial::active_phase_mark,
            &TcMaterial::set_active_phase_mark)
        // uniforms property for Material API compatibility (from default phase)
        .def_prop_ro("uniforms", [](TcMaterial& self) -> nb::dict {
            nb::dict result;
            tc_material_phase* phase = self.default_phase();
            if (!phase) return result;
            for (size_t i = 0; i < phase->uniform_count; i++) {
                std::string name = phase->uniforms[i].name;
                tc_uniform_value& u = phase->uniforms[i];
                switch (u.type) {
                    case TC_UNIFORM_BOOL:
                    case TC_UNIFORM_INT:
                        result[nb::cast(name)] = u.data.i;
                        break;
                    case TC_UNIFORM_FLOAT:
                        result[nb::cast(name)] = u.data.f;
                        break;
                    case TC_UNIFORM_VEC2:
                        result[nb::cast(name)] = nb::make_tuple(u.data.v2[0], u.data.v2[1]);
                        break;
                    case TC_UNIFORM_VEC3:
                        result[nb::cast(name)] = Vec3{u.data.v3[0], u.data.v3[1], u.data.v3[2]};
                        break;
                    case TC_UNIFORM_VEC4:
                        result[nb::cast(name)] = Vec4{u.data.v4[0], u.data.v4[1], u.data.v4[2], u.data.v4[3]};
                        break;
                    default:
                        break;
                }
            }
            return result;
        })
        // textures property for Material API compatibility (from default phase)
        .def_prop_ro("textures", [](TcMaterial& self) -> nb::dict {
            nb::dict result;
            tc_material_phase* phase = self.default_phase();
            if (!phase) return result;
            for (size_t i = 0; i < phase->texture_count; i++) {
                std::string name = phase->textures[i].name;
                if (!tc_texture_handle_is_invalid(phase->textures[i].texture)) {
                    result[nb::cast(name)] = TcTexture(phase->textures[i].texture);
                }
            }
            return result;
        })
        // shader property for Material API compatibility (from default phase)
        .def_prop_ro("shader", [](TcMaterial& self) -> TcShader {
            tc_material_phase* phase = self.default_phase();
            if (!phase) return TcShader();
            return TcShader(phase->shader);
        })
        // apply method for Material API compatibility
        .def("apply", [](TcMaterial& self,
                         const Mat44& model, const Mat44& view, const Mat44& proj,
                         GraphicsBackend* graphics, int64_t context_key) {
            tc_material_phase* phase = self.default_phase();
            if (!phase) return;

            TcShader shader(phase->shader);
            if (!shader.is_valid()) return;

            // Ensure shader is compiled and use it
            shader.ensure_ready();
            shader.use();

            // Convert to float matrices
            Mat44f m_mat = model.to_float();
            Mat44f v_mat = view.to_float();
            Mat44f p_mat = proj.to_float();

            // Upload MVP matrices
            shader.set_uniform_mat4("u_model", m_mat.data, false);
            shader.set_uniform_mat4("u_view", v_mat.data, false);
            shader.set_uniform_mat4("u_projection", p_mat.data, false);

            // Bind textures
            int texture_unit = 0;
            for (size_t i = 0; i < phase->texture_count; i++) {
                if (!tc_texture_handle_is_invalid(phase->textures[i].texture)) {
                    TcTexture tex(phase->textures[i].texture);
                    tex.bind_gpu(texture_unit);
                    shader.set_uniform_int(phase->textures[i].name, texture_unit);
                    ++texture_unit;
                }
            }

            // Upload uniforms
            for (size_t i = 0; i < phase->uniform_count; i++) {
                const tc_uniform_value& u = phase->uniforms[i];
                switch (u.type) {
                    case TC_UNIFORM_BOOL:
                    case TC_UNIFORM_INT:
                        shader.set_uniform_int(u.name, u.data.i);
                        break;
                    case TC_UNIFORM_FLOAT:
                        shader.set_uniform_float(u.name, u.data.f);
                        break;
                    case TC_UNIFORM_VEC2:
                        shader.set_uniform_vec2(u.name, u.data.v2[0], u.data.v2[1]);
                        break;
                    case TC_UNIFORM_VEC3:
                        shader.set_uniform_vec3(u.name, u.data.v3[0], u.data.v3[1], u.data.v3[2]);
                        break;
                    case TC_UNIFORM_VEC4:
                        shader.set_uniform_vec4(u.name, u.data.v4[0], u.data.v4[1], u.data.v4[2], u.data.v4[3]);
                        break;
                    case TC_UNIFORM_MAT4:
                        shader.set_uniform_mat4(u.name, u.data.m4, false);
                        break;
                    default:
                        break;
                }
            }
        }, nb::arg("model"), nb::arg("view"), nb::arg("projection"),
           nb::arg("graphics"), nb::arg("context_key") = 0)
        // numpy array overload of apply
        .def("apply", [](TcMaterial& self,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> model,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> view,
                         nb::ndarray<nb::numpy, float, nb::shape<4, 4>> proj,
                         GraphicsBackend* graphics,
                         int64_t context_key) {
            tc_material_phase* phase = self.default_phase();
            if (!phase) return;

            TcShader shader(phase->shader);
            if (!shader.is_valid()) return;

            // Ensure shader is compiled and use it
            shader.ensure_ready();
            shader.use();

            // Convert row-major numpy to column-major Mat44f
            Mat44f m_mat, v_mat, p_mat;
            for (int row = 0; row < 4; ++row) {
                for (int col = 0; col < 4; ++col) {
                    m_mat.data[col * 4 + row] = model(row, col);
                    v_mat.data[col * 4 + row] = view(row, col);
                    p_mat.data[col * 4 + row] = proj(row, col);
                }
            }

            // Upload MVP matrices
            shader.set_uniform_mat4("u_model", m_mat.data, false);
            shader.set_uniform_mat4("u_view", v_mat.data, false);
            shader.set_uniform_mat4("u_projection", p_mat.data, false);

            // Bind textures
            int texture_unit = 0;
            for (size_t i = 0; i < phase->texture_count; i++) {
                if (!tc_texture_handle_is_invalid(phase->textures[i].texture)) {
                    TcTexture tex(phase->textures[i].texture);
                    tex.bind_gpu(texture_unit);
                    shader.set_uniform_int(phase->textures[i].name, texture_unit);
                    ++texture_unit;
                }
            }

            // Upload uniforms
            for (size_t i = 0; i < phase->uniform_count; i++) {
                const tc_uniform_value& u = phase->uniforms[i];
                switch (u.type) {
                    case TC_UNIFORM_BOOL:
                    case TC_UNIFORM_INT:
                        shader.set_uniform_int(u.name, u.data.i);
                        break;
                    case TC_UNIFORM_FLOAT:
                        shader.set_uniform_float(u.name, u.data.f);
                        break;
                    case TC_UNIFORM_VEC2:
                        shader.set_uniform_vec2(u.name, u.data.v2[0], u.data.v2[1]);
                        break;
                    case TC_UNIFORM_VEC3:
                        shader.set_uniform_vec3(u.name, u.data.v3[0], u.data.v3[1], u.data.v3[2]);
                        break;
                    case TC_UNIFORM_VEC4:
                        shader.set_uniform_vec4(u.name, u.data.v4[0], u.data.v4[1], u.data.v4[2], u.data.v4[3]);
                        break;
                    case TC_UNIFORM_MAT4:
                        shader.set_uniform_mat4(u.name, u.data.m4, false);
                        break;
                    default:
                        break;
                }
            }
        }, nb::arg("model"), nb::arg("view"), nb::arg("projection"),
           nb::arg("graphics"), nb::arg("context_key") = 0)
        // Serialization
        .def("serialize", [](const TcMaterial& self) {
            nb::dict d;
            if (!self.is_valid()) {
                d["type"] = "none";
                return d;
            }
            d["uuid"] = self.uuid();
            d["name"] = self.name();
            d["type"] = "uuid";
            return d;
        })
        // from_parsed - create TcMaterial from ShaderMultyPhaseProgramm
        .def_static("from_parsed", [](
            const ShaderMultyPhaseProgramm& program,
            nb::object color,
            nb::object textures,
            nb::object uniforms,
            nb::object name,
            nb::object source_path,
            const std::string& shader_uuid
        ) -> TcMaterial {
            if (program.phases.empty()) {
                throw std::runtime_error("Program has no phases");
            }

            // Create material with uuid hint if provided
            TcMaterial mat = TcMaterial::create(
                name.is_none() ? program.program : nb::cast<std::string>(name),
                shader_uuid
            );
            if (!mat.is_valid()) {
                throw std::runtime_error("Failed to create TcMaterial");
            }

            mat.set_shader_name(program.program.c_str());
            if (!source_path.is_none()) {
                mat.set_source_path(nb::cast<std::string>(source_path).c_str());
            }

            // Get default textures
            nb::object tex_handle_module = nb::module_::import_("termin.visualization.core.texture_handle");
            nb::object white_tex_fn = tex_handle_module.attr("get_white_texture_handle");
            nb::object normal_tex_fn = tex_handle_module.attr("get_normal_texture_handle");
            TcTexture white_tex = nb::cast<TextureHandle>(white_tex_fn()).get();
            TcTexture normal_tex = nb::cast<TextureHandle>(normal_tex_fn()).get();

            for (const auto& shader_phase : program.phases) {
                // Get shader sources from stages
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

                // Build render state
                tc_render_state rs = tc_render_state_opaque();
                rs.depth_write = shader_phase.gl_depth_mask.value_or(true);
                rs.depth_test = shader_phase.gl_depth_test.value_or(true);
                rs.blend = shader_phase.gl_blend.value_or(false);
                rs.cull = shader_phase.gl_cull.value_or(true);

                // Build shader name
                std::string shader_name;
                if (!program.program.empty()) {
                    shader_name = program.program;
                    if (!shader_phase.phase_mark.empty()) {
                        shader_name += "/" + shader_phase.phase_mark;
                    }
                } else if (!shader_phase.phase_mark.empty()) {
                    shader_name = shader_phase.phase_mark;
                }

                // Add phase
                tc_material_phase* phase = mat.add_phase_from_sources(
                    vs.c_str(), fs.c_str(), gs.empty() ? nullptr : gs.c_str(),
                    shader_name.c_str(),
                    shader_phase.phase_mark.c_str(),
                    shader_phase.priority,
                    rs
                );

                if (!phase) {
                    tc::Log::error("Failed to add phase '%s' to material", shader_phase.phase_mark.c_str());
                    continue;
                }

                // Set available marks
                phase->available_mark_count = std::min(shader_phase.available_marks.size(), (size_t)TC_MATERIAL_MAX_MARKS);
                for (size_t i = 0; i < phase->available_mark_count; i++) {
                    strncpy(phase->available_marks[i], shader_phase.available_marks[i].c_str(), TC_PHASE_MARK_MAX - 1);
                    phase->available_marks[i][TC_PHASE_MARK_MAX - 1] = '\0';
                }

                // Apply shader features
                TcShader shader(phase->shader);
                for (const auto& feature : program.features) {
                    if (feature == "lighting_ubo") {
                        shader.set_feature(TC_SHADER_FEATURE_LIGHTING_UBO);
                    }
                }

                // Apply uniforms from defaults
                for (const auto& prop : shader_phase.uniforms) {
                    if (std::holds_alternative<std::monostate>(prop.default_value)) continue;

                    if (std::holds_alternative<bool>(prop.default_value)) {
                        int val = std::get<bool>(prop.default_value) ? 1 : 0;
                        tc_material_phase_set_uniform(phase, prop.name.c_str(), TC_UNIFORM_INT, &val);
                    } else if (std::holds_alternative<int>(prop.default_value)) {
                        int val = std::get<int>(prop.default_value);
                        tc_material_phase_set_uniform(phase, prop.name.c_str(), TC_UNIFORM_INT, &val);
                    } else if (std::holds_alternative<double>(prop.default_value)) {
                        float val = static_cast<float>(std::get<double>(prop.default_value));
                        tc_material_phase_set_uniform(phase, prop.name.c_str(), TC_UNIFORM_FLOAT, &val);
                    } else if (std::holds_alternative<std::vector<double>>(prop.default_value)) {
                        const auto& vec = std::get<std::vector<double>>(prop.default_value);
                        if (vec.size() == 3) {
                            float arr[3] = {(float)vec[0], (float)vec[1], (float)vec[2]};
                            tc_material_phase_set_uniform(phase, prop.name.c_str(), TC_UNIFORM_VEC3, arr);
                        } else if (vec.size() == 4) {
                            float arr[4] = {(float)vec[0], (float)vec[1], (float)vec[2], (float)vec[3]};
                            tc_material_phase_set_uniform(phase, prop.name.c_str(), TC_UNIFORM_VEC4, arr);
                        }
                    }
                }

                // Apply extra uniforms
                if (!uniforms.is_none()) {
                    nb::dict extras = nb::cast<nb::dict>(uniforms);
                    for (auto item : extras) {
                        std::string key = nb::cast<std::string>(item.first);
                        nb::object val = nb::borrow<nb::object>(item.second);
                        if (nb::isinstance<nb::bool_>(val)) {
                            int v = nb::cast<bool>(val) ? 1 : 0;
                            tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_INT, &v);
                        } else if (nb::isinstance<nb::int_>(val)) {
                            int v = nb::cast<int>(val);
                            tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_INT, &v);
                        } else if (nb::isinstance<nb::float_>(val)) {
                            float v = nb::cast<float>(val);
                            tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_FLOAT, &v);
                        } else if (nb::isinstance<Vec3>(val)) {
                            Vec3 v = nb::cast<Vec3>(val);
                            float arr[3] = {(float)v.x, (float)v.y, (float)v.z};
                            tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_VEC3, arr);
                        } else if (nb::isinstance<Vec4>(val)) {
                            Vec4 v = nb::cast<Vec4>(val);
                            float arr[4] = {(float)v.x, (float)v.y, (float)v.z, (float)v.w};
                            tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_VEC4, arr);
                        }
                    }
                }

                // Set default textures
                for (const auto& prop : shader_phase.uniforms) {
                    if (prop.property_type == "Texture") {
                        if (std::holds_alternative<std::string>(prop.default_value)) {
                            const std::string& default_tex_name = std::get<std::string>(prop.default_value);
                            if (default_tex_name == "normal") {
                                tc_material_phase_set_texture(phase, prop.name.c_str(), normal_tex.handle);
                            } else {
                                tc_material_phase_set_texture(phase, prop.name.c_str(), white_tex.handle);
                            }
                        } else {
                            tc_material_phase_set_texture(phase, prop.name.c_str(), white_tex.handle);
                        }
                    }
                }

                // Override with provided textures
                if (!textures.is_none()) {
                    nb::dict tex_dict = nb::cast<nb::dict>(textures);
                    for (auto item : tex_dict) {
                        std::string key = nb::cast<std::string>(item.first);
                        nb::object val = nb::borrow<nb::object>(item.second);
                        if (nb::isinstance<TcTexture>(val)) {
                            TcTexture tex = nb::cast<TcTexture>(val);
                            tc_material_phase_set_texture(phase, key.c_str(), tex.handle);
                        } else {
                            TextureHandle handle = nb::cast<TextureHandle>(val);
                            TcTexture tex = handle.get();
                            if (tex.is_valid()) {
                                tc_material_phase_set_texture(phase, key.c_str(), tex.handle);
                            }
                        }
                    }
                }

                // Set color
                if (!color.is_none()) {
                    if (nb::isinstance<Vec4>(color)) {
                        Vec4 c = nb::cast<Vec4>(color);
                        tc_material_phase_set_color(phase, c.x, c.y, c.z, c.w);
                    } else if (nb::isinstance<nb::tuple>(color) || nb::isinstance<nb::list>(color)) {
                        nb::sequence seq = nb::cast<nb::sequence>(color);
                        tc_material_phase_set_color(phase,
                            nb::cast<float>(seq[0]),
                            nb::cast<float>(seq[1]),
                            nb::cast<float>(seq[2]),
                            nb::cast<float>(seq[3])
                        );
                    }
                }
            }

            return mat;
        }, nb::arg("program"),
           nb::arg("color") = nb::none(),
           nb::arg("textures") = nb::none(),
           nb::arg("uniforms") = nb::none(),
           nb::arg("name") = nb::none(),
           nb::arg("source_path") = nb::none(),
           nb::arg("shader_uuid") = "");

    // Material registry info functions
    m.def("tc_material_get_all_info", []() -> nb::list {
        nb::list result;
        size_t count = 0;
        tc_material_info* infos = tc_material_get_all_info(&count);
        if (!infos) return result;

        for (size_t i = 0; i < count; i++) {
            nb::dict d;
            d["uuid"] = infos[i].uuid;
            d["name"] = infos[i].name ? infos[i].name : "";
            d["ref_count"] = infos[i].ref_count;
            d["version"] = infos[i].version;
            d["phase_count"] = infos[i].phase_count;
            d["texture_count"] = infos[i].texture_count;
            result.append(d);
        }

        free(infos);
        return result;
    }, "Get info for all materials in the registry");

    m.def("tc_material_count", []() -> size_t {
        return tc_material_count();
    }, "Get number of materials in the registry");
}

void register_material_kind_handlers() {
    // C++ handler for C++ fields
    tc::register_cpp_handle_kind<TcMaterial>("tc_material");

    // Python handler for Python fields
    tc::KindRegistry::instance().register_python(
        "tc_material",
        // serialize
        nb::cpp_function([](nb::object obj) -> nb::object {
            TcMaterial mat = nb::cast<TcMaterial>(obj);
            nb::dict d;
            if (!mat.is_valid()) {
                d["type"] = "none";
                return d;
            }
            d["uuid"] = mat.uuid();
            d["name"] = mat.name();
            d["type"] = "uuid";
            return d;
        }),
        // deserialize
        nb::cpp_function([](nb::object data) -> nb::object {
            if (nb::isinstance<nb::str>(data)) {
                return nb::cast(TcMaterial::from_uuid(nb::cast<std::string>(data)));
            }
            if (nb::isinstance<nb::dict>(data)) {
                nb::dict d = nb::cast<nb::dict>(data);
                if (d.contains("uuid")) {
                    std::string uuid = nb::cast<std::string>(d["uuid"]);
                    return nb::cast(TcMaterial::from_uuid(uuid));
                }
            }
            return nb::cast(TcMaterial());
        }),
        // convert
        nb::cpp_function([](nb::object value) -> nb::object {
            if (value.is_none()) {
                return nb::cast(TcMaterial());
            }
            if (nb::isinstance<TcMaterial>(value)) {
                return value;
            }
            if (nb::isinstance<nb::str>(value)) {
                return nb::cast(TcMaterial::from_uuid(nb::cast<std::string>(value)));
            }
            nb::str type_str = nb::borrow<nb::str>(value.type().attr("__name__"));
            std::string type_name = nb::cast<std::string>(type_str);
            tc::Log::error("tc_material convert failed: cannot convert %s to TcMaterial", type_name.c_str());
            return nb::cast(TcMaterial());
        })
    );
}

} // namespace termin
