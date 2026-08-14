#include <nanobind/nanobind.h>
#include <nanobind/stl/function.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/trampoline.h>

#include "termin/editor/gizmo.hpp"
#include "termin/editor/transform_gizmo.hpp"
#include "termin/render/solid_primitive_renderer.hpp"
#include <termin/entity/entity.hpp>
#include <tgfx2/immediate_renderer.hpp>
#include <tgfx2/render_context.hpp>

namespace nb = nanobind;

namespace termin {

    namespace {

        // Trampoline class for Gizmo to allow Python subclassing
        class PyGizmo : public Gizmo {
        public:
            NB_TRAMPOLINE(Gizmo, 10);

            bool uses_solid_renderer() const override {
                NB_OVERRIDE(uses_solid_renderer);
                return Gizmo::uses_solid_renderer();
            }

            void draw(ImmediateRenderer* renderer) override {
                NB_OVERRIDE(draw, renderer);
            }

            void draw_solid(SolidPrimitiveRenderer* renderer,
                            tgfx::RenderContext2* ctx2,
                            const Mat44f& view,
                            const Mat44f& proj) override {
                NB_OVERRIDE(draw_solid, renderer, ctx2, view, proj);
            }

            void draw_transparent(ImmediateRenderer* renderer) override {
                NB_OVERRIDE(draw_transparent, renderer);
            }

            void draw_transparent_solid(SolidPrimitiveRenderer* renderer,
                                        tgfx::RenderContext2* ctx2,
                                        const Mat44f& view,
                                        const Mat44f& proj) override {
                NB_OVERRIDE(draw_transparent_solid, renderer, ctx2, view, proj);
            }

            std::vector<GizmoCollider> get_colliders() override {
                NB_OVERRIDE_PURE(get_colliders);
            }

            void on_hover_enter(int collider_id) override {
                NB_OVERRIDE(on_hover_enter, collider_id);
            }

            void on_hover_exit(int collider_id) override {
                NB_OVERRIDE(on_hover_exit, collider_id);
            }

            void on_click(int collider_id, const Vec3f* hit_position) override {
                NB_OVERRIDE(on_click, collider_id, hit_position);
            }

            void on_drag(int collider_id, const Vec3f& position, const Vec3f& delta) override {
                NB_OVERRIDE(on_drag, collider_id, position, delta);
            }

            void on_release(int collider_id) override {
                NB_OVERRIDE(on_release, collider_id);
            }
        };

    } // anonymous namespace

    void bind_gizmo(nb::module_& m) {
        // TransformElement enum
        nb::enum_<TransformElement>(m, "TransformElement")
            .value("TRANSLATE_X", TransformElement::TRANSLATE_X)
            .value("TRANSLATE_Y", TransformElement::TRANSLATE_Y)
            .value("TRANSLATE_Z", TransformElement::TRANSLATE_Z)
            .value("TRANSLATE_XY", TransformElement::TRANSLATE_XY)
            .value("TRANSLATE_XZ", TransformElement::TRANSLATE_XZ)
            .value("TRANSLATE_YZ", TransformElement::TRANSLATE_YZ)
            .value("ROTATE_X", TransformElement::ROTATE_X)
            .value("ROTATE_Y", TransformElement::ROTATE_Y)
            .value("ROTATE_Z", TransformElement::ROTATE_Z);

        // Gizmo base class
        nb::class_<Gizmo, PyGizmo>(m, "Gizmo")
            .def(nb::init<>())
            .def_rw("visible", &Gizmo::visible)
            .def("uses_solid_renderer", &Gizmo::uses_solid_renderer)
            .def("draw", &Gizmo::draw)
            .def("draw_transparent", &Gizmo::draw_transparent)
            .def("get_colliders", &Gizmo::get_colliders)
            .def("on_hover_enter", &Gizmo::on_hover_enter)
            .def("on_hover_exit", &Gizmo::on_hover_exit)
            .def("on_release", &Gizmo::on_release);

        // GizmoCollider
        nb::class_<GizmoCollider>(m, "GizmoCollider").def_ro("id", &GizmoCollider::id);

        // TransformGizmo
        nb::class_<TransformGizmo, Gizmo>(m, "TransformGizmo")
            .def(nb::init<>())
            .def_rw("size", &TransformGizmo::size)
            .def_prop_rw(
                "orientation_mode",
                [](const TransformGizmo& self) { return self.orientation_mode(); },
                [](TransformGizmo& self, const std::string& mode) { self.set_orientation_mode(mode); })
            .def_prop_rw(
                "on_transform_changed",
                [](TransformGizmo& self) { return self.on_transform_changed; },
                [](TransformGizmo& self, std::function<void()> cb) { self.on_transform_changed = cb; })
            .def_prop_ro("target", [](TransformGizmo& self) -> Entity { return self.target(); })
            .def(
                "set_target",
                [](TransformGizmo& self, nb::object obj) {
                    self.set_target(obj.is_none() ? Entity() : nb::cast<Entity>(obj));
                },
                nb::arg("entity"))
            .def("clear_target", [](TransformGizmo& self) { self.set_target(Entity()); })
            .def("set_screen_scale", &TransformGizmo::set_screen_scale)
            .def("set_orientation_mode", &TransformGizmo::set_orientation_mode)
            .def("set_drag_end_handler", &TransformGizmo::set_drag_end_handler);
    }

} // namespace termin
