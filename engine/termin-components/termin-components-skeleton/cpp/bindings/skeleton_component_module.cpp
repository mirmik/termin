#include <nanobind/nanobind.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <termin/bindings/entity_helpers.hpp>
#include <termin/entity/entity.hpp>
#include <termin/render/skeleton_controller.hpp>
#include <termin/skeleton/tc_skeleton_handle.hpp>

namespace nb = nanobind;

namespace termin {
    namespace {

        void set_controller_skeleton(SkeletonController& controller, nb::handle value) {
            if (value.is_none()) {
                controller.set_skeleton(TcSkeleton());
                return;
            }
            if (!nb::isinstance<TcSkeleton>(value)) {
                throw nb::type_error("skeleton must be a TcSkeleton or None");
            }

            TcSkeleton skeleton = nb::cast<TcSkeleton>(value);
            if (!skeleton.is_valid()) {
                throw nb::value_error("skeleton must reference a live skeleton resource");
            }
            controller.set_skeleton(skeleton);
        }

        nb::object get_controller_skeleton(const SkeletonController& controller) {
            if (!controller.skeleton.has_handle()) {
                return nb::none();
            }
            return nb::cast(TcSkeleton(controller.skeleton));
        }

        std::vector<Entity> entity_mapping_from_python(nb::list values) {
            std::vector<Entity> entities;
            entities.reserve(nb::len(values));
            for (nb::handle value : values) {
                // None represents an invalid mapping entry. Keep the slot so
                // later entries cannot silently shift to different bones.
                entities.push_back(value.is_none() ? Entity() : nb::cast<Entity>(value));
            }
            return entities;
        }

        void bind_skeleton_controller(nb::module_& m) {
            nb::class_<termin::SkeletonController, termin::Component>(m, "SkeletonController")
                .def("__init__", [](nb::handle self) { termin::cxx_component_init<termin::SkeletonController>(self); })
                .def(
                    "__init__",
                    [](nb::handle self, nb::object skeleton_arg, nb::list bone_entities_list) {
                        termin::cxx_component_init<termin::SkeletonController>(self);
                        auto* cpp = nb::inst_ptr<termin::SkeletonController>(self);

                        set_controller_skeleton(*cpp, skeleton_arg);
                        cpp->set_bone_entities(entity_mapping_from_python(bone_entities_list));
                    },
                    nb::arg("skeleton").none() = nb::none(),
                    nb::arg("bone_entities") = nb::list())
                .def_prop_rw("skeleton", &get_controller_skeleton, &set_controller_skeleton, nb::arg().none())
                .def_prop_rw(
                    "bone_entities",
                    [](const termin::SkeletonController& self) {
                        nb::list result;
                        for (const auto& e : self.bone_entities) {
                            if (e.valid()) {
                                result.append(nb::cast(e));
                            } else {
                                result.append(nb::none());
                            }
                        }
                        return result;
                    },
                    [](termin::SkeletonController& self, nb::list entities) {
                        self.set_bone_entities(entity_mapping_from_python(entities));
                    })
                .def_prop_rw(
                    "skeleton_root",
                    [](const termin::SkeletonController& self) -> nb::object {
                        if (self.skeleton_root.valid()) {
                            return nb::cast(self.skeleton_root);
                        }
                        return nb::none();
                    },
                    [](termin::SkeletonController& self, nb::object root) {
                        self.set_skeleton_root(root.is_none() ? termin::Entity() : nb::cast<termin::Entity>(root));
                    },
                    nb::arg().none())
                .def_prop_ro("skeleton_instance",
                             &termin::SkeletonController::skeleton_instance,
                             nb::rv_policy::reference_internal)
                .def("set_skeleton", &set_controller_skeleton, nb::arg("skeleton").none())
                .def("set_bone_entities",
                     [](termin::SkeletonController& self, nb::list entities) {
                         self.set_bone_entities(entity_mapping_from_python(entities));
                     })
                .def("set_skeleton_root", &termin::SkeletonController::set_skeleton_root);
        }

    } // namespace
} // namespace termin

NB_MODULE(_components_skeleton_native, m) {
    m.doc() = "Native C++ skeleton component module (SkeletonController)";

    nb::module_::import_("termin.scene._scene_native");
    nb::module_::import_("termin.skeleton._skeleton_native");

    termin::bind_skeleton_controller(m);
}
