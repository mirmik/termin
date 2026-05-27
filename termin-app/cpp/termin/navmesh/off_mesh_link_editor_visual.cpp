#include "termin/editor/component_editor_visual.hpp"
#include "termin/editor/editor_snap.hpp"
#include "termin/navmesh/detour_pathfinding_world_component.hpp"
#include "termin/navmesh/off_mesh_link_component.hpp"
#include <tgfx2/immediate_renderer.hpp>

#include <memory>

namespace termin {

namespace {

enum OffMeshLinkEndpointId {
    OFF_MESH_LINK_ENDPOINT_START = 1,
    OFF_MESH_LINK_ENDPOINT_END = 2,
};

Vec3f to_vec3f(const Vec3& value) {
    return Vec3f{
        static_cast<float>(value.x),
        static_cast<float>(value.y),
        static_cast<float>(value.z),
    };
}

tc_vec3 to_tc_vec3(const Vec3& value) {
    return tc_vec3{value.x, value.y, value.z};
}

class OffMeshLinkEndpointTarget : public TransformGizmoTarget {
private:
    OffMeshLinkComponent* _component = nullptr;
    int _endpoint = OFF_MESH_LINK_ENDPOINT_START;

public:
    OffMeshLinkEndpointTarget(OffMeshLinkComponent* component, int endpoint)
        : _component(component), _endpoint(endpoint) {}

    bool valid() const override {
        return _component && _component->entity().valid();
    }

    GeneralPose3 global_pose() const override {
        GeneralPose3 pose;
        pose.ang = Quat::identity();
        pose.scale = Vec3{1.0, 1.0, 1.0};
        Vec3 point = _endpoint == OFF_MESH_LINK_ENDPOINT_START
            ? _component->start_world()
            : _component->end_world();
        pose.lin = point;
        return pose;
    }

    GeneralPose3 local_pose_for_undo() const override {
        return global_pose();
    }

    void relocate_global(const GeneralPose3& pose) override {
        if (!valid()) {
            tc_log(TC_LOG_ERROR, "[OffMeshLinkEditorVisual] cannot relocate endpoint: target is invalid");
            return;
        }

        Entity ent = _component->entity();
        Vec3 local = ent.transform().global_pose().inverse_transform_point(pose.lin);
        if (_endpoint == OFF_MESH_LINK_ENDPOINT_START) {
            _component->start_local = to_tc_vec3(local);
        } else {
            _component->end_local = to_tc_vec3(local);
        }
    }

    Entity entity() const override {
        return _component ? _component->entity() : Entity();
    }

    bool supports_rotation() const override {
        return false;
    }

    bool can_snap() const override {
        return true;
    }

    EditorSnapSource preferred_snap_source() const override {
        return EditorSnapSource::NavMesh;
    }
};

class NavMeshEditorSnapProvider : public EditorSnapProvider {
public:
    bool snap(const EditorSnapRequest& request, EditorSnapResult& result) override {
        if (request.source != EditorSnapSource::NavMesh) {
            return false;
        }
        if (!tc_scene_alive(request.scene)) {
            tc_log(TC_LOG_ERROR, "[NavMeshEditorSnapProvider] cannot snap: scene is invalid");
            return false;
        }

        tc_component* component = tc_scene_first_component_of_type(
            request.scene,
            "DetourPathfindingWorldComponent");
        while (component) {
            CxxComponent* cxx = CxxComponent::from_tc(component);
            DetourPathfindingWorldComponent* world = dynamic_cast<DetourPathfindingWorldComponent*>(cxx);
            if (world) {
                DetourClosestPointResult closest = world->closest_point({
                    static_cast<float>(request.reference_position.x),
                    static_cast<float>(request.reference_position.y),
                    static_cast<float>(request.reference_position.z),
                });
                if (closest.success) {
                    result.success = true;
                    result.position = Vec3{
                        static_cast<double>(closest.point[0]),
                        static_cast<double>(closest.point[1]),
                        static_cast<double>(closest.point[2]),
                    };
                    return true;
                }
            }
            component = component->type_next;
        }

        tc_log(TC_LOG_WARN, "[NavMeshEditorSnapProvider] no Detour navmesh accepted snap request");
        return false;
    }
};

class OffMeshLinkEndpointGizmo : public Gizmo {
private:
    OffMeshLinkComponent* _component = nullptr;
    ComponentEditorVisualContext _context;
    int _hovered_endpoint = 0;

public:
    explicit OffMeshLinkEndpointGizmo(OffMeshLinkComponent* component, const ComponentEditorVisualContext& context)
        : _component(component), _context(context) {}

    void draw_transparent(ImmediateRenderer* renderer) override {
        if (!_component || !_component->enabled || !renderer) {
            return;
        }

        Vec3 start = _component->start_world();
        Vec3 end = _component->end_world();
        Color4 start_color = _hovered_endpoint == OFF_MESH_LINK_ENDPOINT_START
            ? Color4{1.0f, 0.95f, 0.2f, 1.0f}
            : Color4{1.0f, 0.45f, 0.1f, 0.85f};
        Color4 end_color = _hovered_endpoint == OFF_MESH_LINK_ENDPOINT_END
            ? Color4{1.0f, 0.95f, 0.2f, 1.0f}
            : Color4{0.2f, 0.85f, 1.0f, 0.85f};

        renderer->sphere_wireframe(start, 0.18, start_color, 16, true);
        renderer->sphere_wireframe(end, 0.18, end_color, 16, true);
    }

    std::vector<GizmoCollider> get_colliders() override {
        std::vector<GizmoCollider> result;
        if (!_component || !_component->enabled) {
            return result;
        }

        Vec3f start = to_vec3f(_component->start_world());
        Vec3f end = to_vec3f(_component->end_world());
        result.push_back(GizmoCollider{
            OFF_MESH_LINK_ENDPOINT_START,
            SphereGeometry{start, 0.22f},
            NoDrag{},
        });
        result.push_back(GizmoCollider{
            OFF_MESH_LINK_ENDPOINT_END,
            SphereGeometry{end, 0.22f},
            NoDrag{},
        });
        return result;
    }

    void on_hover_enter(int collider_id) override {
        _hovered_endpoint = collider_id;
    }

    void on_hover_exit(int collider_id) override {
        if (_hovered_endpoint == collider_id) {
            _hovered_endpoint = 0;
        }
    }

    void on_click(int collider_id, const Vec3f* hit_position) override {
        (void)hit_position;
        if (!_context.transform_gizmo) {
            tc_log(TC_LOG_ERROR, "[OffMeshLinkEditorVisual] cannot select endpoint: transform gizmo is missing");
            return;
        }
        if (collider_id != OFF_MESH_LINK_ENDPOINT_START && collider_id != OFF_MESH_LINK_ENDPOINT_END) {
            tc_log(TC_LOG_ERROR, "[OffMeshLinkEditorVisual] unknown endpoint collider id=%d", collider_id);
            return;
        }

        _context.transform_gizmo->set_target(
            std::make_shared<OffMeshLinkEndpointTarget>(_component, collider_id));
    }
};

class OffMeshLinkEditorVisualProvider : public ComponentEditorVisualProvider {
public:
    void collect_gizmos(
        Entity entity,
        tc_component* component,
        const ComponentEditorVisualContext& context,
        std::vector<std::unique_ptr<Gizmo>>& out_gizmos) override
    {
        (void)entity;
        CxxComponent* cxx = CxxComponent::from_tc(component);
        OffMeshLinkComponent* link = dynamic_cast<OffMeshLinkComponent*>(cxx);
        if (!link) {
            return;
        }

        out_gizmos.push_back(std::make_unique<OffMeshLinkEndpointGizmo>(link, context));
    }
};

struct OffMeshLinkEditorVisualRegistration {
    OffMeshLinkEditorVisualRegistration() {
        ComponentEditorVisualRegistry::instance().register_provider(
            std::make_unique<OffMeshLinkEditorVisualProvider>());
        EditorSnapRegistry::instance().register_provider(
            std::make_unique<NavMeshEditorSnapProvider>());
    }
};

static OffMeshLinkEditorVisualRegistration off_mesh_link_editor_visual_registration;

} // namespace

} // namespace termin
