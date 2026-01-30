#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/function.h>
#include <nanobind/ndarray.h>
#include <nanobind/trampoline.h>

#include "termin/editor/gizmo.hpp"
#include "termin/editor/gizmo_manager.hpp"
#include "termin/editor/transform_gizmo.hpp"
#include "termin/entity/entity.hpp"
#include "termin/render/immediate_renderer.hpp"
#include "termin/render/graphics_backend.hpp"
#include "termin/render/solid_primitive_renderer.hpp"

namespace nb = nanobind;

namespace termin {

namespace {

Vec3f ndarray_to_vec3f(nb::ndarray<nb::numpy, float, nb::shape<3>> arr) {
    return Vec3f{arr(0), arr(1), arr(2)};
}

Vec3f ndarray_to_vec3f_double(nb::ndarray<nb::numpy, double, nb::shape<3>> arr) {
    return Vec3f{
        static_cast<float>(arr(0)),
        static_cast<float>(arr(1)),
        static_cast<float>(arr(2))
    };
}

Mat44f ndarray_to_mat44f(nb::ndarray<nb::numpy, double, nb::shape<4, 4>> arr) {
    Mat44f mat;
    for (int row = 0; row < 4; ++row) {
        for (int col = 0; col < 4; ++col) {
            mat(col, row) = static_cast<float>(arr(row, col));
        }
    }
    return mat;
}

Mat44f ndarray_to_mat44f_float(nb::ndarray<nb::numpy, float, nb::shape<4, 4>> arr) {
    Mat44f mat;
    for (int row = 0; row < 4; ++row) {
        for (int col = 0; col < 4; ++col) {
            mat(col, row) = arr(row, col);
        }
    }
    return mat;
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
        GraphicsBackend* graphics,
        const Mat44f& view,
        const Mat44f& proj
    ) override {
        NB_OVERRIDE(draw_solid, renderer, graphics, view, proj);
    }

    void draw_transparent(ImmediateRenderer* renderer) override {
        NB_OVERRIDE(draw_transparent, renderer);
    }

    void draw_transparent_solid(
        SolidPrimitiveRenderer* renderer,
        GraphicsBackend* graphics,
        const Mat44f& view,
        const Mat44f& proj
    ) override {
        NB_OVERRIDE(draw_transparent_solid, renderer, graphics, view, proj);
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
        // render with float64 matrices (from camera)
        .def("render", [](GizmoManager& self,
                          ImmediateRenderer* renderer,
                          GraphicsBackend* graphics,
                          nb::ndarray<nb::numpy, double, nb::shape<4, 4>> view,
                          nb::ndarray<nb::numpy, double, nb::shape<4, 4>> proj) {
            self.render(renderer, graphics, ndarray_to_mat44f(view), ndarray_to_mat44f(proj));
        }, nb::arg("renderer"), nb::arg("graphics"), nb::arg("view"), nb::arg("proj"))
        // render with Mat44 (double)
        .def("render", [](GizmoManager& self,
                          ImmediateRenderer* renderer,
                          GraphicsBackend* graphics,
                          const Mat44& view,
                          const Mat44& proj) {
            Mat44f view_f, proj_f;
            for (int i = 0; i < 16; ++i) {
                view_f.data[i] = static_cast<float>(view.data[i]);
                proj_f.data[i] = static_cast<float>(proj.data[i]);
            }
            self.render(renderer, graphics, view_f, proj_f);
        }, nb::arg("renderer"), nb::arg("graphics"), nb::arg("view"), nb::arg("proj"))
        // raycast
        .def("raycast", [](GizmoManager& self,
                           nb::ndarray<nb::numpy, float, nb::shape<3>> ray_origin,
                           nb::ndarray<nb::numpy, float, nb::shape<3>> ray_dir) {
            return self.raycast(ndarray_to_vec3f(ray_origin), ndarray_to_vec3f(ray_dir));
        }, nb::arg("ray_origin"), nb::arg("ray_dir"))
        // mouse events with float arrays
        .def("on_mouse_move", [](GizmoManager& self,
                                 nb::ndarray<nb::numpy, float, nb::shape<3>> ray_origin,
                                 nb::ndarray<nb::numpy, float, nb::shape<3>> ray_dir) {
            return self.on_mouse_move(ndarray_to_vec3f(ray_origin), ndarray_to_vec3f(ray_dir));
        }, nb::arg("ray_origin"), nb::arg("ray_dir"))
        // mouse events with Vec3f
        .def("on_mouse_move", [](GizmoManager& self, const Vec3f& ray_origin, const Vec3f& ray_dir) {
            return self.on_mouse_move(ray_origin, ray_dir);
        }, nb::arg("ray_origin"), nb::arg("ray_dir"))
        .def("on_mouse_down", [](GizmoManager& self,
                                 nb::ndarray<nb::numpy, float, nb::shape<3>> ray_origin,
                                 nb::ndarray<nb::numpy, float, nb::shape<3>> ray_dir) {
            return self.on_mouse_down(ndarray_to_vec3f(ray_origin), ndarray_to_vec3f(ray_dir));
        }, nb::arg("ray_origin"), nb::arg("ray_dir"))
        // mouse events with Vec3f
        .def("on_mouse_down", [](GizmoManager& self, const Vec3f& ray_origin, const Vec3f& ray_dir) {
            return self.on_mouse_down(ray_origin, ray_dir);
        }, nb::arg("ray_origin"), nb::arg("ray_dir"))
        .def("on_mouse_up", &GizmoManager::on_mouse_up);

    // TransformGizmo
    nb::class_<TransformGizmo, Gizmo>(m, "TransformGizmo")
        .def(nb::init<>())
        .def_rw("size", &TransformGizmo::size)
        .def_rw("orientation_mode", &TransformGizmo::orientation_mode)
        .def_prop_rw("on_transform_changed",
            [](TransformGizmo& self) { return self.on_transform_changed; },
            [](TransformGizmo& self, std::function<void()> cb) { self.on_transform_changed = cb; })
        .def_prop_ro("target", [](TransformGizmo& self) -> Entity* { return self.target(); },
            nb::rv_policy::reference)
        .def("set_target", [](TransformGizmo& self, Entity* entity) { self.set_target(entity); },
            nb::arg("entity").none())
        .def("clear_target", [](TransformGizmo& self) { self.set_target(nullptr); })
        .def("set_screen_scale", &TransformGizmo::set_screen_scale)
        .def("set_orientation_mode", &TransformGizmo::set_orientation_mode)
        .def("set_undo_handler", &TransformGizmo::set_undo_handler);
}

} // namespace termin
