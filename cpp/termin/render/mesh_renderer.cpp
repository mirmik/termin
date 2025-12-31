#include "mesh_renderer.hpp"

#include <algorithm>

namespace termin {

MeshRenderer::MeshRenderer() {
    _type_name = "MeshRenderer";
    install_drawable_vtable(&_c);
}

void MeshRenderer::set_mesh(const MeshHandle& handle) {
    mesh = handle;
}

void MeshRenderer::set_mesh_by_name(const std::string& name) {
    mesh = MeshHandle::from_name(name);
}

Material* MeshRenderer::get_material() const {
    if (_override_material && _overridden_material != nullptr) {
        return _overridden_material;
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
    }
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
    TcMesh mesh_data = mesh.get();
    MeshGPU* gpu = mesh.gpu();
    if (!mesh_data.is_valid() || gpu == nullptr) {
        return;
    }
    gpu->draw(context, mesh_data.mesh, mesh.version());
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
    Material* mat = get_material();
    if (mat == nullptr) {
        return {};
    }

    std::vector<GeometryDrawCall> result;
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

} // namespace termin
