#include "mesh_renderer.hpp"
#include "termin/inspect/inspect_registry.hpp"

#include <algorithm>

namespace termin {

MeshRenderer::MeshRenderer() {
    _type_name = "MeshRenderer";
    install_drawable_vtable(&_c);
}

void MeshRenderer::set_mesh(const TcMesh& m) {
    mesh = m;
}

void MeshRenderer::set_mesh_by_name(const std::string& name) {
    // Lookup mesh by name in tc_mesh registry
    tc_mesh_handle h = tc_mesh_find_by_name(name.c_str());
    if (!tc_mesh_handle_is_invalid(h)) {
        mesh = TcMesh(h);
    } else {
        mesh = TcMesh();
    }
}

Material* MeshRenderer::get_material() const {
    if (_override_material) {
        // Lazy initialization of overridden material
        if (_overridden_material == nullptr) {
            const_cast<MeshRenderer*>(this)->try_create_override_material();
        }
        if (_overridden_material != nullptr) {
            return _overridden_material;
        }
    }
    // Returns nullptr if material is Python-based (not C++ Material)
    return material.get();
}

Material* MeshRenderer::get_base_material() const {
    // Returns nullptr if material is Python-based (not C++ Material)
    return material.get();
}

void MeshRenderer::set_material(Material* mat) {
    if (mat == nullptr) {
        material = MaterialHandle();
    } else {
        material = MaterialHandle::from_direct(mat);
    }

    if (_override_material) {
        recreate_overridden_material();
    }
}

void MeshRenderer::set_material_handle(const MaterialHandle& handle) {
    material = handle;

    if (_override_material) {
        recreate_overridden_material();
    }
}

void MeshRenderer::set_material_by_name(const std::string& name) {
    material = MaterialHandle::from_name(name);

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
        delete _overridden_material;
        _overridden_material = nullptr;
    }
}

void MeshRenderer::recreate_overridden_material() {
    delete _overridden_material;
    _overridden_material = nullptr;

    Material* base = material.get_material_or_none();
    if (base != nullptr) {
        // Create a copy
        _overridden_material = new Material(base->copy());
        _overridden_material->name = base->name + "_override";

        // Apply pending override data if exists (from deserialization)
        apply_pending_override_data();
    }
}

void MeshRenderer::try_create_override_material() {
    if (_overridden_material != nullptr) return;

    Material* base = material.get_material_or_none();
    if (base == nullptr) return;

    // Create override material from base
    _overridden_material = new Material(base->copy());
    _overridden_material->name = base->name + "_override";

    // Apply pending override data if exists
    apply_pending_override_data();
}

void MeshRenderer::apply_pending_override_data() {
    if (!_pending_override_data || _overridden_material == nullptr) return;

    fprintf(stderr, "[MeshRenderer] Applying pending override data, phases: %zu\n",
            _overridden_material->phases.size());

    const nos::trent& override_data = *_pending_override_data;

    // Apply uniforms
    if (override_data.contains("phases_uniforms")) {
        const nos::trent& phases_uniforms = override_data["phases_uniforms"];
        if (phases_uniforms.is_list()) {
            size_t phase_count = std::min(phases_uniforms.as_list().size(), _overridden_material->phases.size());
            for (size_t i = 0; i < phase_count; ++i) {
                const nos::trent& phase_uniforms = phases_uniforms.at(i);
                if (!phase_uniforms.is_dict()) continue;

                auto& phase = _overridden_material->phases[i];
                for (const auto& [key, val] : phase_uniforms.as_dict()) {
                    if (val.is_bool()) {
                        phase.uniforms[key] = val.as_bool();
                    } else if (val.is_numer()) {
                        phase.uniforms[key] = static_cast<float>(val.as_numer());
                    } else if (val.is_list()) {
                        const auto& lst = val.as_list();
                        if (lst.size() == 3) {
                            phase.uniforms[key] = Vec3{
                                static_cast<float>(lst[0].as_numer()),
                                static_cast<float>(lst[1].as_numer()),
                                static_cast<float>(lst[2].as_numer())
                            };
                        } else if (lst.size() == 4) {
                            phase.uniforms[key] = Vec4{
                                static_cast<float>(lst[0].as_numer()),
                                static_cast<float>(lst[1].as_numer()),
                                static_cast<float>(lst[2].as_numer()),
                                static_cast<float>(lst[3].as_numer())
                            };
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
            size_t phase_count = std::min(phases_textures.as_list().size(), _overridden_material->phases.size());
            for (size_t i = 0; i < phase_count; ++i) {
                const nos::trent& phase_textures = phases_textures.at(i);
                if (!phase_textures.is_dict()) continue;

                auto& phase = _overridden_material->phases[i];
                for (const auto& [key, val] : phase_textures.as_dict()) {
                    if (!val.is_dict()) continue;

                    // Deserialize TextureHandle using existing method
                    TextureHandle tex_handle;
                    tex_handle.deserialize_from(val, nullptr);

                    if (tex_handle.is_valid()) {
                        phase.textures[key] = std::move(tex_handle);
                        fprintf(stderr, "[MeshRenderer] Applied texture '%s' to phase %zu\n", key.c_str(), i);
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

    Material* mat = material.get();
    if (mat != nullptr) {
        for (const auto& phase : mat->phases) {
            marks.insert(phase.phase_mark);
        }
    }

    if (cast_shadow) {
        marks.insert("shadow");
    }

    return marks;
}

void MeshRenderer::draw_geometry(const RenderContext& context, const std::string& geometry_id) {
    if (!mesh.is_valid()) {
        return;
    }
    _mesh_gpu.draw(context, mesh.get(), mesh.version());
}

std::vector<MaterialPhase*> MeshRenderer::get_phases_for_mark(const std::string& phase_mark) {
    Material* mat = get_material();
    if (mat == nullptr) {
        return {};
    }

    std::vector<MaterialPhase*> result;
    for (auto& phase : mat->phases) {
        if (phase.phase_mark == phase_mark) {
            result.push_back(&phase);
        }
    }

    std::sort(result.begin(), result.end(), [](MaterialPhase* a, MaterialPhase* b) {
        return a->priority < b->priority;
    });

    return result;
}

std::vector<GeometryDrawCall> MeshRenderer::get_geometry_draws(const std::string* phase_mark) {
    std::vector<GeometryDrawCall> result;

    // Shadow phase: just need geometry, no material phase required
    if (phase_mark != nullptr && *phase_mark == "shadow") {
        if (cast_shadow) {
            result.emplace_back(nullptr, "");
        }
        return result;
    }

    // For other phases, need material
    Material* mat = get_material();
    if (mat == nullptr) {
        return {};
    }

    for (auto& phase : mat->phases) {
        if (phase_mark == nullptr || phase_mark->empty() || phase.phase_mark == *phase_mark) {
            result.emplace_back(&phase, "");
        }
    }

    std::sort(result.begin(), result.end(), [](const GeometryDrawCall& a, const GeometryDrawCall& b) {
        return a.phase->priority < b.phase->priority;
    });

    return result;
}

nos::trent MeshRenderer::get_override_data() const {
    // Return nil if override is not enabled or no overridden material
    if (!_override_material || _overridden_material == nullptr) {
        return nos::trent::nil();
    }

    nos::trent override_data;
    override_data.init(nos::trent_type::dict);

    nos::trent phases_uniforms;
    phases_uniforms.init(nos::trent_type::list);

    nos::trent phases_textures;
    phases_textures.init(nos::trent_type::list);

    for (const auto& phase : _overridden_material->phases) {
        // Serialize uniforms
        nos::trent phase_uniforms;
        phase_uniforms.init(nos::trent_type::dict);

        for (const auto& [key, val] : phase.uniforms) {
            std::visit([&](auto&& arg) {
                using T = std::decay_t<decltype(arg)>;
                if constexpr (std::is_same_v<T, bool>) {
                    phase_uniforms[key] = arg;
                } else if constexpr (std::is_same_v<T, int>) {
                    phase_uniforms[key] = static_cast<int64_t>(arg);
                } else if constexpr (std::is_same_v<T, float>) {
                    phase_uniforms[key] = static_cast<double>(arg);
                } else if constexpr (std::is_same_v<T, Vec3>) {
                    nos::trent vec;
                    vec.init(nos::trent_type::list);
                    vec.as_list().push_back(static_cast<double>(arg.x));
                    vec.as_list().push_back(static_cast<double>(arg.y));
                    vec.as_list().push_back(static_cast<double>(arg.z));
                    phase_uniforms[key] = std::move(vec);
                } else if constexpr (std::is_same_v<T, Vec4>) {
                    nos::trent vec;
                    vec.init(nos::trent_type::list);
                    vec.as_list().push_back(static_cast<double>(arg.x));
                    vec.as_list().push_back(static_cast<double>(arg.y));
                    vec.as_list().push_back(static_cast<double>(arg.z));
                    vec.as_list().push_back(static_cast<double>(arg.w));
                    phase_uniforms[key] = std::move(vec);
                }
            }, val);
        }
        phases_uniforms.as_list().push_back(std::move(phase_uniforms));

        // Serialize textures
        nos::trent phase_textures;
        phase_textures.init(nos::trent_type::dict);

        for (const auto& [key, tex_handle] : phase.textures) {
            if (!tex_handle.is_valid()) continue;

            nos::trent tex_data;
            tex_data.init(nos::trent_type::dict);

            // Serialize TextureHandle (similar to TextureHandle::serialize())
            if (!tex_handle.asset.is_none()) {
                try {
                    tex_data["uuid"] = nb::cast<std::string>(tex_handle.asset.attr("uuid"));
                    tex_data["name"] = nb::cast<std::string>(tex_handle.asset.attr("name"));
                    nb::object source_path = tex_handle.asset.attr("source_path");
                    if (!source_path.is_none()) {
                        tex_data["type"] = "path";
                        tex_data["path"] = nb::cast<std::string>(nb::str(source_path.attr("as_posix")()));
                    } else {
                        tex_data["type"] = "named";
                    }
                } catch (const nb::python_error& e) {
                    fprintf(stderr, "[MeshRenderer] Error serializing texture '%s': %s\n", key.c_str(), e.what());
                    continue;
                }
            } else {
                tex_data["type"] = "none";
            }

            phase_textures[key] = std::move(tex_data);
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
        fprintf(stderr, "[MeshRenderer] Saved pending override data\n");
    }
}

} // namespace termin
