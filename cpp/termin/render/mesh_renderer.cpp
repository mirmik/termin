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

// Helper to get double from tc_value
static double tc_val_as_double(const tc_value* v) {
    if (!v) return 0.0;
    switch (v->type) {
        case TC_VALUE_INT: return static_cast<double>(v->data.i);
        case TC_VALUE_FLOAT: return static_cast<double>(v->data.f);
        case TC_VALUE_DOUBLE: return v->data.d;
        default: return 0.0;
    }
}

void MeshRenderer::apply_pending_override_data() {
    if (_pending_override_data.type == TC_VALUE_NIL || !_overridden_material.is_valid()) return;

    tc_material* mat = _overridden_material.get();
    if (!mat) return;

    // Apply uniforms
    tc_value* phases_uniforms = tc_value_dict_get(&_pending_override_data, "phases_uniforms");
    if (phases_uniforms && phases_uniforms->type == TC_VALUE_LIST) {
        size_t phase_count = std::min(tc_value_list_size(phases_uniforms), mat->phase_count);
        for (size_t i = 0; i < phase_count; ++i) {
            tc_value* phase_uniforms = tc_value_list_get(phases_uniforms, i);
            if (!phase_uniforms || phase_uniforms->type != TC_VALUE_DICT) continue;

            tc_material_phase* phase = &mat->phases[i];
            size_t uniform_count = tc_value_dict_size(phase_uniforms);
            for (size_t j = 0; j < uniform_count; ++j) {
                const char* key = nullptr;
                tc_value* val = tc_value_dict_get_at(phase_uniforms, j, &key);
                if (!key || !val) continue;

                if (val->type == TC_VALUE_BOOL) {
                    int v = val->data.b ? 1 : 0;
                    tc_material_phase_set_uniform(phase, key, TC_UNIFORM_INT, &v);
                } else if (val->type == TC_VALUE_INT || val->type == TC_VALUE_FLOAT || val->type == TC_VALUE_DOUBLE) {
                    float v = static_cast<float>(tc_val_as_double(val));
                    tc_material_phase_set_uniform(phase, key, TC_UNIFORM_FLOAT, &v);
                } else if (val->type == TC_VALUE_LIST) {
                    size_t lst_size = tc_value_list_size(val);
                    if (lst_size == 3) {
                        float v[3] = {
                            static_cast<float>(tc_val_as_double(tc_value_list_get(val, 0))),
                            static_cast<float>(tc_val_as_double(tc_value_list_get(val, 1))),
                            static_cast<float>(tc_val_as_double(tc_value_list_get(val, 2)))
                        };
                        tc_material_phase_set_uniform(phase, key, TC_UNIFORM_VEC3, v);
                    } else if (lst_size == 4) {
                        float v[4] = {
                            static_cast<float>(tc_val_as_double(tc_value_list_get(val, 0))),
                            static_cast<float>(tc_val_as_double(tc_value_list_get(val, 1))),
                            static_cast<float>(tc_val_as_double(tc_value_list_get(val, 2))),
                            static_cast<float>(tc_val_as_double(tc_value_list_get(val, 3)))
                        };
                        tc_material_phase_set_uniform(phase, key, TC_UNIFORM_VEC4, v);
                    }
                }
            }
        }
    }

    // Apply textures
    tc_value* phases_textures = tc_value_dict_get(&_pending_override_data, "phases_textures");
    if (phases_textures && phases_textures->type == TC_VALUE_LIST) {
        size_t phase_count = std::min(tc_value_list_size(phases_textures), mat->phase_count);
        for (size_t i = 0; i < phase_count; ++i) {
            tc_value* phase_textures = tc_value_list_get(phases_textures, i);
            if (!phase_textures || phase_textures->type != TC_VALUE_DICT) continue;

            tc_material_phase* phase = &mat->phases[i];
            size_t tex_count = tc_value_dict_size(phase_textures);
            for (size_t j = 0; j < tex_count; ++j) {
                const char* key = nullptr;
                tc_value* val = tc_value_dict_get_at(phase_textures, j, &key);
                if (!key || !val || val->type != TC_VALUE_DICT) continue;

                tc_value* uuid_val = tc_value_dict_get(val, "uuid");
                if (uuid_val && uuid_val->type == TC_VALUE_STRING && uuid_val->data.s) {
                    std::string uuid = uuid_val->data.s;
                    tc_texture_handle tex_h = tc_texture_find(uuid.c_str());
                    if (!tc_texture_handle_is_invalid(tex_h)) {
                        tc_material_phase_set_texture(phase, key, tex_h);
                    } else {
                        tc_value* name_val = tc_value_dict_get(val, "name");
                        std::string name = (name_val && name_val->type == TC_VALUE_STRING && name_val->data.s)
                            ? name_val->data.s : "";
                        tc::Log::warn("[MeshRenderer] Texture not found: uuid=%s name=%s uniform=%s",
                                     uuid.c_str(), name.c_str(), key);
                    }
                }
            }
        }
    }

    // Clear pending data after applying
    tc_value_free(&_pending_override_data);
    _pending_override_data = tc_value_nil();
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

tc_value MeshRenderer::get_override_data() const {
    // Return nil if override is not enabled or no overridden material
    if (!_override_material || !_overridden_material.is_valid()) {
        return tc_value_nil();
    }

    tc_material* mat = _overridden_material.get();
    if (!mat) return tc_value_nil();

    tc_value override_data = tc_value_dict_new();
    tc_value phases_uniforms = tc_value_list_new();
    tc_value phases_textures = tc_value_list_new();

    for (size_t i = 0; i < mat->phase_count; i++) {
        const tc_material_phase* phase = &mat->phases[i];

        // Serialize uniforms
        tc_value phase_uniforms = tc_value_dict_new();

        for (size_t j = 0; j < phase->uniform_count; j++) {
            const tc_uniform_value* u = &phase->uniforms[j];
            switch (u->type) {
                case TC_UNIFORM_BOOL:
                case TC_UNIFORM_INT:
                    tc_value_dict_set(&phase_uniforms, u->name, tc_value_int(u->data.i));
                    break;
                case TC_UNIFORM_FLOAT:
                    tc_value_dict_set(&phase_uniforms, u->name, tc_value_double(static_cast<double>(u->data.f)));
                    break;
                case TC_UNIFORM_VEC3: {
                    tc_value vec = tc_value_list_new();
                    tc_value_list_push(&vec, tc_value_double(static_cast<double>(u->data.v3[0])));
                    tc_value_list_push(&vec, tc_value_double(static_cast<double>(u->data.v3[1])));
                    tc_value_list_push(&vec, tc_value_double(static_cast<double>(u->data.v3[2])));
                    tc_value_dict_set(&phase_uniforms, u->name, vec);
                    break;
                }
                case TC_UNIFORM_VEC4: {
                    tc_value vec = tc_value_list_new();
                    tc_value_list_push(&vec, tc_value_double(static_cast<double>(u->data.v4[0])));
                    tc_value_list_push(&vec, tc_value_double(static_cast<double>(u->data.v4[1])));
                    tc_value_list_push(&vec, tc_value_double(static_cast<double>(u->data.v4[2])));
                    tc_value_list_push(&vec, tc_value_double(static_cast<double>(u->data.v4[3])));
                    tc_value_dict_set(&phase_uniforms, u->name, vec);
                    break;
                }
                default:
                    break;
            }
        }
        tc_value_list_push(&phases_uniforms, phase_uniforms);

        // Serialize textures
        tc_value phase_textures = tc_value_dict_new();

        for (size_t j = 0; j < phase->texture_count; j++) {
            const tc_material_texture* tex = &phase->textures[j];
            tc_texture* t = tc_texture_get(tex->texture);
            if (!t) continue;

            tc_value tex_data = tc_value_dict_new();
            tc_value_dict_set(&tex_data, "uuid", tc_value_string(t->header.uuid));
            if (t->header.name) {
                tc_value_dict_set(&tex_data, "name", tc_value_string(t->header.name));
            }
            if (t->source_path && t->source_path[0] != '\0') {
                tc_value_dict_set(&tex_data, "type", tc_value_string("path"));
                tc_value_dict_set(&tex_data, "path", tc_value_string(t->source_path));
            } else {
                tc_value_dict_set(&tex_data, "type", tc_value_string("named"));
            }
            tc_value_dict_set(&phase_textures, tex->name, tex_data);
        }
        tc_value_list_push(&phases_textures, phase_textures);
    }

    tc_value_dict_set(&override_data, "phases_uniforms", phases_uniforms);
    tc_value_dict_set(&override_data, "phases_textures", phases_textures);
    return override_data;
}

void MeshRenderer::set_override_data(const tc_value* val) {
    // Save data for lazy application (base material may not be loaded yet)
    if (val && val->type != TC_VALUE_NIL) {
        tc_value_free(&_pending_override_data);
        _pending_override_data = tc_value_copy(val);
    }

    // If override flag is already set (from deserialization), create the override material now
    if (_override_material && !_overridden_material.is_valid()) {
        try_create_override_material();
    }
}

} // namespace termin
