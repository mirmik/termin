#pragma once

#include <termin/entity/entity.hpp>
#include <termin/geom/vec3.hpp>

#include <memory>
#include <vector>

namespace termin {

enum class EditorSnapSource {
    None = 0,
    VisibleGeometry = 1,
    NavMesh = 2,
    GroundCollision = 3,
};

struct EditorSnapRequest {
    EditorSnapSource source = EditorSnapSource::None;
    tc_scene_handle scene = TC_SCENE_HANDLE_INVALID;
    Entity target_entity;
    Vec3 reference_position = Vec3::zero();
};

struct EditorSnapResult {
    bool success = false;
    Vec3 position = Vec3::zero();
};

class EditorSnapProvider {
public:
    virtual ~EditorSnapProvider() = default;
    virtual bool snap(const EditorSnapRequest& request, EditorSnapResult& result) = 0;
};

class EditorSnapRegistry {
private:
    std::vector<std::unique_ptr<EditorSnapProvider>> _providers;

public:
    static EditorSnapRegistry& instance();

    void register_provider(std::unique_ptr<EditorSnapProvider> provider);
    bool snap(const EditorSnapRequest& request, EditorSnapResult& result);
};

} // namespace termin
