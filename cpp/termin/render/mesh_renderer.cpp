#include "mesh_renderer.hpp"

#include <algorithm>
#include <cstring>

namespace termin {

MeshRenderer::MeshRenderer() {
    set_type_name("MeshRenderer");
    install_drawable_vtable(&_c);
}

void MeshRenderer::set_mesh(const TcMesh& m) {
    mesh = m;
}

void MeshRenderer::set_mesh_by_name(const std::string& name) {
    tc_mesh_handle h = tc_mesh_find_by_name(name.c_str());
    if (!tc_mesh_handle_is_invalid(h)) {
        mesh = TcMesh(h);
    } else {
        mesh = TcMesh();
    }
}

TcMaterial MeshRenderer::get_material() const {
    if (_override_material && _overridden_material.is_valid()) {
        return _overridden_material;
    }
    return material;
}

tc_material* MeshRenderer::get_material_ptr() const {
    if (_override_material && _overridden_material.is_valid()) {
        return _overridden_material.get();
    }
    return material.get();
}

void MeshRenderer::set_material(const TcMaterial& mat) {
    material = mat;

    if (_override_material) {
        recreate_overridden_material();
    }
}

void MeshRenderer::set_material_by_name(const std::string& name) {
    tc_material_handle h = tc_material_find_by_name(name.c_str());
    if (!tc_material_handle_is_invalid(h)) {
        material = TcMaterial(h);
    } else {
        material = TcMaterial();
    }

    if (_override_material) {
        recreate_overridden_material();
    }
}

void MeshRenderer::set_override_material(bool value) {
    if (value == _override_material) {
        return;
    }

    _override_material = value;

    if (value) {
        recreate_overridden_material();
    } else {
        _overridden_material = TcMaterial();
    }
}

void MeshRenderer::recreate_overridden_material() {
    _overridden_material = TcMaterial();

    if (!material.is_valid()) return;

    // Create a copy of the base material
    _overridden_material = TcMaterial::copy(material);
    if (_overridden_material.is_valid()) {
        std::string override_name = std::string(material.name()) + "_override";
        _overridden_material.set_name(override_name.c_str());

        // Apply pending override data if exists
        apply_pending_override_data();
    }
}

void MeshRenderer::try_create_override_material() {
    if (_overridden_material.is_valid()) return;
    if (!material.is_valid()) return;

    // Create override material from base
    _overridden_material = TcMaterial::copy(material);
    if (_overridden_material.is_valid()) {
        std::string override_name = std::string(material.name()) + "_override";
        _overridden_material.set_name(override_name.c_str());

        // Apply pending override data if exists
        apply_pending_override_data();
    }
}

void MeshRenderer::apply_pending_override_data() {
    if (!_pending_override_data || !_overridden_material.is_valid()) return;

    tc_material* mat = _overridden_material.get();
    if (!mat) return;

    const nos::trent& override_data = *_pending_override_data;

    // Apply uniforms
    if (override_data.contains("phases_uniforms")) {
        const nos::trent& phases_uniforms = override_data["phases_uniforms"];
        if (phases_uniforms.is_list()) {
            size_t phase_count = std::min(phases_uniforms.as_list().size(), mat->phase_count);
            for (size_t i = 0; i < phase_count; ++i) {
                const nos::trent& phase_uniforms = phases_uniforms.at(i);
                if (!phase_uniforms.is_dict()) continue;

                tc_material_phase* phase = &mat->phases[i];
                for (const auto& [key, val] : phase_uniforms.as_dict()) {
                    if (val.is_bool()) {
                        int v = val.as_bool() ? 1 : 0;
                        tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_INT, &v);
                    } else if (val.is_numer()) {
                        float v = static_cast<float>(val.as_numer());
                        tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_FLOAT, &v);
                    } else if (val.is_list()) {
                        const auto& lst = val.as_list();
                        if (lst.size() == 3) {
                            float v[3] = {
                                static_cast<float>(lst[0].as_numer()),
                                static_cast<float>(lst[1].as_numer()),
                                static_cast<float>(lst[2].as_numer())
                            };
                            tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_VEC3, v);
                        } else if (lst.size() == 4) {
                            float v[4] = {
                                static_cast<float>(lst[0].as_numer()),
                                static_cast<float>(lst[1].as_numer()),
                                static_cast<float>(lst[2].as_numer()),
                                static_cast<float>(lst[3].as_numer())
                            };
                            tc_material_phase_set_uniform(phase, key.c_str(), TC_UNIFORM_VEC4, v);
                        }
                    }
                }
            }
        }
    }

    // Apply textures
    if (override_data.contains("phases_textures")) {
        const nos::trent& phases_textures = override_data["phases_textures"];
        if (phases_textures.is_list()) {
            size_t phase_count = std::min(phases_textures.as_list().size(), mat->phase_count);
            for (size_t i = 0; i < phase_count; ++i) {
                const nos::trent& phase_textures = phases_textures.at(i);
                if (!phase_textures.is_dict()) continue;

                tc_material_phase* phase = &mat->phases[i];
                for (const auto& [key, val] : phase_textures.as_dict()) {
                    if (!val.is_dict()) continue;

                    if (val.contains("uuid")) {
                        std::string uuid = val["uuid"].as_string();
                        tc_texture_handle tex_h = tc_texture_find(uuid.c_str());
                        if (!tc_texture_handle_is_invalid(tex_h)) {
                            tc_material_phase_set_texture(phase, key.c_str(), tex_h);
                        } else {
                            std::string name = val.contains("name") ? val["name"].as_string() : "";
                            tc::Log::warn("[MeshRenderer] Texture not found: uuid=%s name=%s uniform=%s",
                                         uuid.c_str(), name.c_str(), key.c_str());
                        }
                    }
                }
            }
        }
    }

    // Clear pending data after applying
    _pending_override_data.reset();
}

std::set<std::string> MeshRenderer::get_phase_marks() const {
    std::set<std::string> marks;

    tc_material* mat = get_material_ptr();
    if (mat) {
        for (size_t i = 0; i < mat->phase_count; i++) {
            marks.insert(mat->phases[i].phase_mark);
        }
    }

    if (cast_shadow) {
        marks.insert("shadow");
    }

    return marks;
}

void MeshRenderer::draw_geometry(const RenderContext& context, int geometry_id) {
    tc_mesh* m = mesh.get();
    if (!m) {
        return;
    }
    tc_mesh_upload_gpu(m);
    tc_mesh_draw_gpu(m);
}

std::vector<tc_material_phase*> MeshRenderer::get_phases_for_mark(const std::string& phase_mark) {
    std::vector<tc_material_phase*> result;

    tc_material* mat = get_material_ptr();
    if (!mat) return result;

    for (size_t i = 0; i < mat->phase_count; i++) {
        if (std::strcmp(mat->phases[i].phase_mark, phase_mark.c_str()) == 0) {
            result.push_back(&mat->phases[i]);
        }
    }

    std::sort(result.begin(), result.end(), [](tc_material_phase* a, tc_material_phase* b) {
        return a->priority < b->priority;
    });

    return result;
}

std::vector<GeometryDrawCall> MeshRenderer::get_geometry_draws(const std::string* phase_mark) {
    std::vector<GeometryDrawCall> result;

    // Shadow phase: just need geometry, no material phase required
    if (phase_mark != nullptr && *phase_mark == "shadow") {
        if (cast_shadow) {
            result.emplace_back(nullptr, 0);
        }
        return result;
    }

    // For other phases, need material
    tc_material* mat = get_material_ptr();
    if (!mat) {
        return {};
    }

    for (size_t i = 0; i < mat->phase_count; i++) {
        tc_material_phase* phase = &mat->phases[i];
        if (phase_mark == nullptr || phase_mark->empty() ||
            std::strcmp(phase->phase_mark, phase_mark->c_str()) == 0) {
            result.emplace_back(phase, 0);
        }
    }

    std::sort(result.begin(), result.end(), [](const GeometryDrawCall& a, const GeometryDrawCall& b) {
        return a.phase->priority < b.phase->priority;
    });

    return result;
}

nos::trent MeshRenderer::get_override_data() const {
    // Return nil if override is not enabled or no overridden material
    if (!_override_material || !_overridden_material.is_valid()) {
        return nos::trent::nil();
    }

    tc_material* mat = _overridden_material.get();
    if (!mat) return nos::trent::nil();

    nos::trent override_data;
    override_data.init(nos::trent_type::dict);

    nos::trent phases_uniforms;
    phases_uniforms.init(nos::trent_type::list);

    nos::trent phases_textures;
    phases_textures.init(nos::trent_type::list);

    for (size_t i = 0; i < mat->phase_count; i++) {
        const tc_material_phase* phase = &mat->phases[i];

        // Serialize uniforms
        nos::trent phase_uniforms;
        phase_uniforms.init(nos::trent_type::dict);

        for (size_t j = 0; j < phase->uniform_count; j++) {
            const tc_uniform_value* u = &phase->uniforms[j];
            switch (u->type) {
                case TC_UNIFORM_BOOL:
                case TC_UNIFORM_INT:
                    phase_uniforms[u->name] = static_cast<int64_t>(u->data.i);
                    break;
                case TC_UNIFORM_FLOAT:
                    phase_uniforms[u->name] = static_cast<double>(u->data.f);
                    break;
                case TC_UNIFORM_VEC3: {
                    nos::trent vec;
                    vec.init(nos::trent_type::list);
                    vec.as_list().push_back(static_cast<double>(u->data.v3[0]));
                    vec.as_list().push_back(static_cast<double>(u->data.v3[1]));
                    vec.as_list().push_back(static_cast<double>(u->data.v3[2]));
                    phase_uniforms[u->name] = std::move(vec);
                    break;
                }
                case TC_UNIFORM_VEC4: {
                    nos::trent vec;
                    vec.init(nos::trent_type::list);
                    vec.as_list().push_back(static_cast<double>(u->data.v4[0]));
                    vec.as_list().push_back(static_cast<double>(u->data.v4[1]));
                    vec.as_list().push_back(static_cast<double>(u->data.v4[2]));
                    vec.as_list().push_back(static_cast<double>(u->data.v4[3]));
                    phase_uniforms[u->name] = std::move(vec);
                    break;
                }
                default:
                    break;
            }
        }
        phases_uniforms.as_list().push_back(std::move(phase_uniforms));

        // Serialize textures
        nos::trent phase_textures;
        phase_textures.init(nos::trent_type::dict);

        for (size_t j = 0; j < phase->texture_count; j++) {
            const tc_material_texture* tex = &phase->textures[j];
            tc_texture* t = tc_texture_get(tex->texture);
            if (!t) continue;

            nos::trent tex_data;
            tex_data.init(nos::trent_type::dict);
            tex_data["uuid"] = t->header.uuid;
            if (t->header.name) {
                tex_data["name"] = t->header.name;
            }
            if (t->source_path && t->source_path[0] != '\0') {
                tex_data["type"] = "path";
                tex_data["path"] = t->source_path;
            } else {
                tex_data["type"] = "named";
            }
            phase_textures[tex->name] = std::move(tex_data);
        }
        phases_textures.as_list().push_back(std::move(phase_textures));
    }

    override_data["phases_uniforms"] = std::move(phases_uniforms);
    override_data["phases_textures"] = std::move(phases_textures);
    return override_data;
}

void MeshRenderer::set_override_data(const nos::trent& val) {
    // Save data for lazy application (base material may not be loaded yet)
    if (!val.is_nil()) {
        _pending_override_data = std::make_unique<nos::trent>(val);
    }

    // If override flag is already set (from deserialization), create the override material now
    if (_override_material && !_overridden_material.is_valid()) {
        try_create_override_material();
    }
}

} // namespace termin
