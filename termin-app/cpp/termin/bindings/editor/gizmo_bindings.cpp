#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/function.h>
#include <nanobind/trampoline.h>

#include "termin/editor/gizmo.hpp"
#include "termin/editor/gizmo_manager.hpp"
#include "termin/editor/transform_gizmo.hpp"
#include <termin/entity/entity.hpp>
#include <termin/geom/mat44.hpp>
#include <tgfx2/immediate_renderer.hpp>
#include "termin/render/solid_primitive_renderer.hpp"
#include <tgfx2/render_context.hpp>

namespace nb = nanobind;

namespace termin {

namespace {

Mat44f mat44_to_mat44f(const Mat44& src) {
    Mat44f mat;
    for (int i = 0; i < 16; ++i) {
        mat.data[i] = static_cast<float>(src.data[i]);
    }
    return mat;
}

Vec3f vec3_to_vec3f(const Vec3& v) {
    return Vec3f{
        static_cast<float>(v.x),
        static_cast<float>(v.y),
        static_cast<float>(v.z)
    };
}

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

    void draw_solid(
        SolidPrimitiveRenderer* renderer,
        tgfx::RenderContext2* ctx2,
        const Mat44f& view,
        const Mat44f& proj
    ) override {
        NB_OVERRIDE(draw_solid, renderer, ctx2, view, proj);
    }

    void draw_transparent(ImmediateRenderer* renderer) override {
        NB_OVERRIDE(draw_transparent, renderer);
    }

    void draw_transparent_solid(
        SolidPrimitiveRenderer* renderer,
        tgfx::RenderContext2* ctx2,
        const Mat44f& view,
        const Mat44f& proj
    ) override {
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

    // GizmoHit
    nb::class_<GizmoHit>(m, "GizmoHit")
        .def_ro("gizmo", &GizmoHit::gizmo)
        .def_ro("collider", &GizmoHit::collider)
        .def_ro("t", &GizmoHit::t);

    // GizmoCollider
    nb::class_<GizmoCollider>(m, "GizmoCollider")
        .def_ro("id", &GizmoCollider::id);

    // GizmoManager
    nb::class_<GizmoManager>(m, "GizmoManager")
        .def(nb::init<>())
        .def("is_dragging", &GizmoManager::is_dragging)
        .def("add_gizmo", &GizmoManager::add_gizmo, nb::arg("gizmo"))
        .def("remove_gizmo", &GizmoManager::remove_gizmo, nb::arg("gizmo"))
        .def("clear", &GizmoManager::clear)
        .def("render", [](GizmoManager& self,
                          ImmediateRenderer* renderer,
                          tgfx::RenderContext2* ctx2,
                          const Mat44f& view,
                          const Mat44f& proj) {
            self.render(renderer, ctx2, view, proj);
        }, nb::arg("renderer"), nb::arg("ctx2"), nb::arg("view"), nb::arg("proj"))
        .def("render", [](GizmoManager& self,
                          ImmediateRenderer* renderer,
                          tgfx::RenderContext2* ctx2,
                          const Mat44& view,
                          const Mat44& proj) {
            self.render(renderer, ctx2, mat44_to_mat44f(view), mat44_to_mat44f(proj));
        }, nb::arg("renderer"), nb::arg("ctx2"), nb::arg("view"), nb::arg("proj"))
        .def("raycast", [](GizmoManager& self,
                           const Vec3& ray_origin,
                           const Vec3& ray_dir) {
            return self.raycast(vec3_to_vec3f(ray_origin), vec3_to_vec3f(ray_dir));
        }, nb::arg("ray_origin"), nb::arg("ray_dir"))
        .def("on_mouse_move", [](GizmoManager& self,
                                 const Vec3& ray_origin,
                                 const Vec3& ray_dir) {
            return self.on_mouse_move(vec3_to_vec3f(ray_origin), vec3_to_vec3f(ray_dir));
        }, nb::arg("ray_origin"), nb::arg("ray_dir"))
        .def("on_mouse_down", [](GizmoManager& self,
                                 const Vec3& ray_origin,
                                 const Vec3& ray_dir) {
            return self.on_mouse_down(vec3_to_vec3f(ray_origin), vec3_to_vec3f(ray_dir));
        }, nb::arg("ray_origin"), nb::arg("ray_dir"))
        .def("on_mouse_up", &GizmoManager::on_mouse_up);

    // TransformGizmo
    nb::class_<TransformGizmo, Gizmo>(m, "TransformGizmo")
        .def(nb::init<>())
        .def_rw("size", &TransformGizmo::size)
        .def_prop_rw("orientation_mode",
            [](const TransformGizmo& self) { return self.orientation_mode(); },
            [](TransformGizmo& self, const std::string& mode) { self.set_orientation_mode(mode); })
        .def_prop_rw("on_transform_changed",
            [](TransformGizmo& self) { return self.on_transform_changed; },
            [](TransformGizmo& self, std::function<void()> cb) { self.on_transform_changed = cb; })
        .def_prop_ro("target", [](TransformGizmo& self) -> Entity { return self.target(); })
        .def("set_target", [](TransformGizmo& self, nb::object obj) {
            self.set_target(obj.is_none() ? Entity() : nb::cast<Entity>(obj));
        }, nb::arg("entity"))
        .def("clear_target", [](TransformGizmo& self) { self.set_target(Entity()); })
        .def("set_screen_scale", &TransformGizmo::set_screen_scale)
        .def("set_orientation_mode", &TransformGizmo::set_orientation_mode)
        .def("set_drag_end_handler", &TransformGizmo::set_drag_end_handler);
}

} // namespace termin
