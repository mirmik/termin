#include "termin/editor/component_editor_visual.hpp"
#include "termin/editor/editor_snap.hpp"
#include "termin/editor/gizmo_visual_item3d.hpp"
#include "termin/navmesh/detour_pathfinding_world_component.hpp"
#include "termin/navmesh/off_mesh_link_component.hpp"
#include <tgfx2/immediate_renderer.hpp>

#include <memory>
#include <string>

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

        class OffMeshLinkRef {
        public:
            OffMeshLinkRef() = default;

            OffMeshLinkRef(Entity entity, OffMeshLinkComponent& component)
                : _entity(entity) {
                const char* source_id = tc_component_ensure_source_id(component.c_component());
                if (source_id)
                    _source_id = source_id;
                if (_source_id.empty())
                    tc_log(TC_LOG_ERROR, "[OffMeshLinkEditorVisual] component has no stable source id");
            }

            OffMeshLinkComponent* resolve() const {
                if (!_entity.valid() || _source_id.empty())
                    return nullptr;
                for (std::size_t index = 0; index < _entity.component_count(); ++index) {
                    tc_component* component = _entity.component_at(index);
                    const char* source_id = tc_component_get_source_id(component);
                    if (!source_id || _source_id != source_id)
                        continue;
                    return dynamic_cast<OffMeshLinkComponent*>(CxxComponent::from_tc(component));
                }
                return nullptr;
            }

            Entity entity() const {
                return resolve() ? _entity : Entity();
            }

        private:
            Entity _entity;
            std::string _source_id;
        };

        class OffMeshLinkEndpointTarget : public TransformGizmoTarget {
        private:
            OffMeshLinkRef _component;
            int _endpoint = OFF_MESH_LINK_ENDPOINT_START;

        public:
            OffMeshLinkEndpointTarget(OffMeshLinkRef component, int endpoint)
                : _component(std::move(component)),
                  _endpoint(endpoint) {}

            bool valid() const override {
                return _component.resolve() != nullptr;
            }

            Vec3 global_position() const override {
                OffMeshLinkComponent* component = _component.resolve();
                if (!component) {
                    tc_log(TC_LOG_ERROR, "[OffMeshLinkEditorVisual] cannot read endpoint: target is invalid");
                    return {};
                }
                return _endpoint == OFF_MESH_LINK_ENDPOINT_START ? component->start_world() : component->end_world();
            }

            Quat global_orientation() const override {
                return Quat::identity();
            }

            GeneralPose3 local_pose_for_undo() const override {
                return GeneralPose3{
                    Quat::identity(),
                    global_position(),
                    Vec3{1.0, 1.0, 1.0},
                };
            }

            void set_global_position(const Vec3& position) override {
                if (!valid()) {
                    tc_log(TC_LOG_ERROR, "[OffMeshLinkEditorVisual] cannot relocate endpoint: target is invalid");
                    return;
                }

                OffMeshLinkComponent* component = _component.resolve();
                if (!component)
                    return;
                Entity ent = component->entity();
                Vec3 local = ent.transform().transform_point_inverse(position);
                if (_endpoint == OFF_MESH_LINK_ENDPOINT_START) {
                    component->start_local = to_tc_vec3(local);
                } else {
                    component->end_local = to_tc_vec3(local);
                }
            }

            void set_global_orientation(const Quat&) override {}

            Entity entity() const override {
                return _component.entity();
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

                tc_component* component =
                    tc_scene_first_component_of_type(request.scene, "DetourPathfindingWorldComponent");
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
            OffMeshLinkRef _component;
            ComponentEditorVisualContext _context;
            int _hovered_endpoint = 0;

        public:
            explicit OffMeshLinkEndpointGizmo(OffMeshLinkRef component,
                                              const ComponentEditorVisualContext& context)
                : _component(std::move(component)),
                  _context(context) {}

            void draw_transparent(ImmediateRenderer* renderer) override {
                OffMeshLinkComponent* component = _component.resolve();
                if (!component || !component->enabled || !renderer) {
                    return;
                }

                Vec3 start = component->start_world();
                Vec3 end = component->end_world();
                SrgbColor start_color = _hovered_endpoint == OFF_MESH_LINK_ENDPOINT_START
                                             ? SrgbColor{1.0f, 0.95f, 0.2f, 1.0f}
                                             : SrgbColor{1.0f, 0.45f, 0.1f, 0.85f};
                SrgbColor end_color = _hovered_endpoint == OFF_MESH_LINK_ENDPOINT_END
                                          ? SrgbColor{1.0f, 0.95f, 0.2f, 1.0f}
                                          : SrgbColor{0.2f, 0.85f, 1.0f, 0.85f};

                renderer->sphere_wireframe(start, 0.18, start_color, 16, true);
                renderer->sphere_wireframe(end, 0.18, end_color, 16, true);
            }

            std::vector<GizmoCollider> get_colliders() override {
                std::vector<GizmoCollider> result;
                OffMeshLinkComponent* component = _component.resolve();
                if (!component || !component->enabled) {
                    return result;
                }

                Vec3f start = to_vec3f(component->start_world());
                Vec3f end = to_vec3f(component->end_world());
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
                    tc_log(TC_LOG_ERROR,
                           "[OffMeshLinkEditorVisual] cannot select endpoint: transform gizmo is missing");
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
            void collect_overlay_items(Entity entity,
                                       tc_component* component,
                                       const ComponentEditorVisualContext& context,
                                       std::vector<ComponentEditorVisualContribution>& out_items) override {
                CxxComponent* cxx = CxxComponent::from_tc(component);
                OffMeshLinkComponent* link = dynamic_cast<OffMeshLinkComponent*>(cxx);
                if (!link) {
                    return;
                }

                auto item = std::make_unique<GizmoVisualItem3D>(
                    std::make_unique<OffMeshLinkEndpointGizmo>(OffMeshLinkRef(entity, *link), context));
                auto* adapter = item.get();
                out_items.push_back(ComponentEditorVisualContribution{
                    std::move(item),
                    [adapter](visual::SceneInteraction3D& interaction, visual::VisualItem3DHandle) {
                        adapter->bind_controller(interaction);
                    },
                });
            }
        };

        struct OffMeshLinkEditorVisualRegistration {
            OffMeshLinkEditorVisualRegistration() {
                ComponentEditorVisualRegistry::instance().register_provider(
                    std::make_unique<OffMeshLinkEditorVisualProvider>());
                EditorSnapRegistry::instance().register_provider(std::make_unique<NavMeshEditorSnapProvider>());
            }
        };

        static OffMeshLinkEditorVisualRegistration off_mesh_link_editor_visual_registration;

    } // namespace

} // namespace termin
