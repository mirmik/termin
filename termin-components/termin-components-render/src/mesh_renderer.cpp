#include <termin/render/mesh_renderer.hpp>

#include <algorithm>
#include <stdexcept>

#include <tcbase/tc_log.hpp>
#include <tc_inspect_cpp.hpp>

namespace termin {

namespace {

tc_value make_mesh_renderer_inspector_layout_field(
    const char* path,
    const char* widget = nullptr,
    const char* visible_if = nullptr
) {
    tc_value item = tc_value_dict_new();
    tc_value_dict_set(&item, "kind", tc_value_string("field"));
    tc_value_dict_set(&item, "path", tc_value_string(path));
    if (widget && widget[0]) {
        tc_value_dict_set(&item, "widget", tc_value_string(widget));
    }
    if (visible_if && visible_if[0]) {
        tc_value_dict_set(&item, "visible_if", tc_value_string(visible_if));
    }
    return item;
}

tc_value make_mesh_renderer_inspector_section(const char* label) {
    tc_value item = tc_value_dict_new();
    tc_value_dict_set(&item, "kind", tc_value_string("section"));
    tc_value_dict_set(&item, "label", tc_value_string(label));
    return item;
}

tc_value make_mesh_renderer_inspector_metadata() {
    tc_value inspector = tc_value_dict_new();

    tc_value fields = tc_value_dict_new();
    tc_value overridden = tc_value_dict_new();
    tc_value_dict_set(&overridden, "visible_if", tc_value_string("_override_material"));
    tc_value_dict_set(&overridden, "widget", tc_value_string("inline_material"));
    tc_value_dict_set(&fields, "_overridden_material", overridden);
    tc_value_dict_set(&inspector, "fields", fields);

    tc_value layout = tc_value_list_new();
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("material"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("cast_shadow"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_section("Material Override"));
    tc_value_list_push(&layout, make_mesh_renderer_inspector_layout_field("_override_material"));
    tc_value_list_push(
        &layout,
        make_mesh_renderer_inspector_layout_field(
            "_overridden_material",
            "inline_material",
            "_override_material"));
    tc_value_dict_set(&inspector, "layout", layout);

    return inspector;
}

void register_mesh_renderer_inspect_fields() {
    auto& inspect = tc::InspectRegistry::instance();
    if (!inspect.find_field("MeshRenderer", "material")) {
        tc::register_inspect_field(
            &MeshRenderer::material,
            "MeshRenderer",
            "material",
            "Material",
            "tc_material"
        );
    }
    if (!inspect.find_field("MeshRenderer", "cast_shadow")) {
        tc::register_inspect_field(
            &MeshRenderer::cast_shadow,
            "MeshRenderer",
            "cast_shadow",
            "Cast Shadow",
            "bool"
        );
    }
    if (!inspect.find_field("MeshRenderer", "_override_material")) {
        inspect.add_with_callbacks<MeshRenderer, bool>(
            "MeshRenderer",
            "_override_material",
            "Override Material",
            "bool",
            [](MeshRenderer* self) -> bool& { return self->_override_material; },
            [](MeshRenderer* self, const bool& value) {
                if (self) {
                    self->set_override_material(value);
                }
            }
        );
    }
    if (!inspect.find_field("MeshRenderer", "_overridden_material")) {
        tc::InspectAccessorFieldRegistrar<MeshRenderer, TcMaterial>(
            "MeshRenderer",
            "_overridden_material",
            "Overridden Material",
            "tc_material",
            [](MeshRenderer* self) -> TcMaterial {
                return self ? self->_overridden_material : TcMaterial();
            },
            [](MeshRenderer* self, TcMaterial value) {
                if (self) {
                    self->_overridden_material = value;
                }
            },
            false,
            true
        );
    }
    if (!inspect.find_field("MeshRenderer", "_overridden_material_data")) {
        tc::SerializableFieldRegistrar<MeshRenderer>(
            "MeshRenderer",
            "_overridden_material_data",
            [](MeshRenderer* self) -> tc_value {
                return self ? self->get_override_data() : tc_value_nil();
            },
            [](MeshRenderer* self, const tc_value* val) {
                if (self) {
                    self->set_override_data(val);
                }
            }
        );
    }

    tc_value metadata = make_mesh_renderer_inspector_metadata();
    inspect.set_type_metadata_key("MeshRenderer", "inspector", &metadata);
    tc_value_free(&metadata);
}

} // namespace

MeshRenderer::MeshRenderer(const char* type_name)
    : Component(type_name)
{
    install_drawable_vtable(&_c);
}

void MeshRenderer::register_type() {
    MeshComponent::register_type();
    register_component_type<MeshRenderer>("MeshRenderer", "Component");
    register_component_requirement("MeshRenderer", "MeshComponent");
    register_mesh_renderer_inspect_fields();
}

MeshRenderer::~MeshRenderer() {
    tc_value_free(&_pending_override_data);
}

TcMesh& MeshRenderer::get_mesh() {
    bind_mesh_component();
    if (!_mesh_component) {
        tc::Log::error("[MeshRenderer] get_mesh() requires MeshComponent on the same entity");
        throw std::runtime_error("MeshRenderer no longer owns mesh; use MeshComponent");
    }
    return _mesh_component->mesh;
}

const TcMesh& MeshRenderer::get_mesh() const {
    const_cast<MeshRenderer*>(this)->bind_mesh_component();
    if (!_mesh_component) {
        tc::Log::error("[MeshRenderer] get_mesh() requires MeshComponent on the same entity");
        throw std::runtime_error("MeshRenderer no longer owns mesh; use MeshComponent");
    }
    return _mesh_component->mesh;
}

void MeshRenderer::bind_mesh_component() {
    if (_mesh_component) {
        return;
    }
    Entity owner = entity();
    if (!owner.valid()) {
        return;
    }
    _mesh_component = owner.get_component<MeshComponent>();
}

tc_mesh* MeshRenderer::current_mesh_ptr() const {
    const_cast<MeshRenderer*>(this)->bind_mesh_component();
    if (_mesh_component) {
        return _mesh_component->mesh.get();
    }
    return nullptr;
}

TcMaterial MeshRenderer::get_material() const {
    if (_override_material) {
        const_cast<MeshRenderer*>(this)->ensure_override_material_ready();
    }
    if (_override_material && _overridden_material.is_valid()) {
        return _overridden_material;
    }
    return material;
}

tc_material* MeshRenderer::get_material_ptr() const {
    if (_override_material) {
        const_cast<MeshRenderer*>(this)->ensure_override_material_ready();
    }
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

TcMaterial MeshRenderer::get_overridden_material() const {
    if (_override_material) {
        const_cast<MeshRenderer*>(this)->ensure_override_material_ready();
        return _overridden_material;
    }
    return TcMaterial();
}

void MeshRenderer::ensure_override_material_ready() {
    if (!_override_material || _overridden_material.is_valid()) {
        return;
    }
    try_create_override_material();
}

void MeshRenderer::recreate_overridden_material() {
    _overridden_material = TcMaterial();

    if (!material.is_valid()) return;

    _overridden_material = TcMaterial::copy(material);
    if (_overridden_material.is_valid()) {
        std::string override_name = std::string(material.name()) + "_override";
        _overridden_material.set_name(override_name.c_str());
        apply_pending_override_data();
    }
}

void MeshRenderer::try_create_override_material() {
    if (_overridden_material.is_valid()) {
        return;
    }
    if (!material.is_valid()) {
        return;
    }

    _overridden_material = TcMaterial::copy(material);
    if (_overridden_material.is_valid()) {
        std::string override_name = std::string(material.name()) + "_override";
        _overridden_material.set_name(override_name.c_str());
        apply_pending_override_data();
    }
}

static double tc_val_as_double(const tc_value* v) {
    if (!v) return 0.0;
    switch (v->type) {
        case TC_VALUE_INT: return static_cast<double>(v->data.i);
        case TC_VALUE_FLOAT: return static_cast<double>(v->data.f);
        case TC_VALUE_DOUBLE: return v->data.d;
        default: return 0.0;
    }
}

static tc_value serialize_uniform_value(const tc_uniform_value& uniform) {
    switch (uniform.type) {
        case TC_UNIFORM_BOOL:
            return tc_value_bool(uniform.data.i != 0);
        case TC_UNIFORM_INT:
            return tc_value_int(uniform.data.i);
        case TC_UNIFORM_FLOAT:
            return tc_value_float(uniform.data.f);
        case TC_UNIFORM_VEC2: {
            tc_value v = tc_value_list_new();
            tc_value_list_push(&v, tc_value_float(uniform.data.v2[0]));
            tc_value_list_push(&v, tc_value_float(uniform.data.v2[1]));
            return v;
        }
        case TC_UNIFORM_VEC3: {
            tc_value v = tc_value_list_new();
            tc_value_list_push(&v, tc_value_float(uniform.data.v3[0]));
            tc_value_list_push(&v, tc_value_float(uniform.data.v3[1]));
            tc_value_list_push(&v, tc_value_float(uniform.data.v3[2]));
            return v;
        }
        case TC_UNIFORM_VEC4: {
            tc_value v = tc_value_list_new();
            tc_value_list_push(&v, tc_value_float(uniform.data.v4[0]));
            tc_value_list_push(&v, tc_value_float(uniform.data.v4[1]));
            tc_value_list_push(&v, tc_value_float(uniform.data.v4[2]));
            tc_value_list_push(&v, tc_value_float(uniform.data.v4[3]));
            return v;
        }
        default:
            return tc_value_nil();
    }
}

void MeshRenderer::apply_pending_override_data() {
    if (_pending_override_data.type == TC_VALUE_NIL || !_overridden_material.is_valid()) return;

    tc_material* mat = _overridden_material.get();
    if (!mat) return;

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

Mat44f MeshRenderer::get_model_matrix(const Entity& entity) const {
    Mat44f model = Drawable::get_model_matrix(entity);

    const_cast<MeshRenderer*>(this)->bind_mesh_component();
    if (_mesh_component) {
        return model * _mesh_component->get_mesh_offset_matrix();
    }

    return model;
}

void MeshRenderer::draw_geometry(const RenderContext& context, int geometry_id) {
    (void)context;
    (void)geometry_id;
}

std::vector<tc_material_phase*> MeshRenderer::get_phases_for_mark(const std::string& phase_mark) {
    std::vector<tc_material_phase*> result;
    tc_material* mat = get_material_ptr();
    if (!mat) return result;

    tc_material_phase* phases[TC_MATERIAL_MAX_PHASES];
    size_t count = tc_material_get_phases_for_mark(mat, phase_mark.c_str(), phases, TC_MATERIAL_MAX_PHASES);
    result.reserve(count);
    for (size_t i = 0; i < count; i++) {
        result.push_back(phases[i]);
    }
    return result;
}

std::vector<GeometryDrawCall> MeshRenderer::get_geometry_draws(const std::string* phase_mark) {
    std::vector<GeometryDrawCall> draws;
    tc_mesh* m = current_mesh_ptr();
    if (!m) return draws;

    tc_material* mat = get_material_ptr();
    if (!mat) return draws;

    std::vector<tc_material_phase*> phases;
    if (phase_mark) {
        phases = get_phases_for_mark(*phase_mark);
    } else {
        for (size_t i = 0; i < mat->phase_count; i++) {
            phases.push_back(&mat->phases[i]);
        }
    }

    for (auto* phase : phases) {
        draws.emplace_back(phase, 0);
    }
    return draws;
}

void MeshRenderer::on_added() {
    Component::on_added();
    bind_mesh_component();
}

void MeshRenderer::start() {
    Component::start();
    bind_mesh_component();
}

void MeshRenderer::on_editor_start() {
    bind_mesh_component();
}

void MeshRenderer::on_scene_active() {
    bind_mesh_component();
}

void MeshRenderer::on_render_attach() {
    bind_mesh_component();
}

void MeshRenderer::deserialize_data(const tc_value* data, tc_scene_handle scene) {
    Component::deserialize_data(data, scene);
    bind_mesh_component();
}

tc_value MeshRenderer::get_override_data() const {
    if (_override_material && _overridden_material.is_valid()) {
        tc_material* mat = _overridden_material.get();
        if (mat) {
            tc_value result = tc_value_dict_new();

            tc_value phases_uniforms = tc_value_list_new();
            tc_value phases_textures = tc_value_list_new();

            for (size_t i = 0; i < mat->phase_count; ++i) {
                const tc_material_phase& phase = mat->phases[i];

                tc_value phase_uniforms = tc_value_dict_new();
                for (size_t j = 0; j < phase.uniform_count; ++j) {
                    const tc_uniform_value& uniform = phase.uniforms[j];
                    tc_value serialized = serialize_uniform_value(uniform);
                    if (serialized.type != TC_VALUE_NIL) {
                        tc_value_dict_set(&phase_uniforms, uniform.name, serialized);
                    }
                }
                tc_value_list_push(&phases_uniforms, phase_uniforms);

                tc_value phase_textures = tc_value_dict_new();
                for (size_t j = 0; j < phase.texture_count; ++j) {
                    const tc_material_texture& tex_binding = phase.textures[j];
                    if (tc_texture_handle_is_invalid(tex_binding.texture)) {
                        continue;
                    }

                    tc_texture* tex = tc_texture_get(tex_binding.texture);
                    if (!tex) continue;

                    tc_value tex_value = tc_value_dict_new();
                    tc_value_dict_set(&tex_value, "uuid", tc_value_string(tex->header.uuid));
                    if (tex->header.name && tex->header.name[0]) {
                        tc_value_dict_set(&tex_value, "name", tc_value_string(tex->header.name));
                    }
                    tc_value_dict_set(&phase_textures, tex_binding.name, tex_value);
                }
                tc_value_list_push(&phases_textures, phase_textures);
            }

            tc_value_dict_set(&result, "phases_uniforms", phases_uniforms);
            tc_value_dict_set(&result, "phases_textures", phases_textures);
            return result;
        }
    }

    return tc_value_copy(&_pending_override_data);
}

void MeshRenderer::set_override_data(const tc_value* val) {
    tc_value_free(&_pending_override_data);
    _pending_override_data = val ? tc_value_copy(val) : tc_value_nil();

    if (_override_material) {
        if (!_overridden_material.is_valid()) {
            try_create_override_material();
        }
        if (_overridden_material.is_valid()) {
            apply_pending_override_data();
        }
    }
}

} // namespace termin
