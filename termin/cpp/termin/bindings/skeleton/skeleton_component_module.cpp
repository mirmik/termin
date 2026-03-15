#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <termin/render/skeleton_controller.hpp>
#include <termin/skeleton/tc_skeleton_handle.hpp>
#include <termin/entity/entity.hpp>
#include <termin/bindings/entity_helpers.hpp>

namespace nb = nanobind;

namespace termin {
namespace {

void bind_skeleton_controller(nb::module_& m) {
    nb::class_<termin::SkeletonController, termin::Component>(m, "SkeletonController")
        .def("__init__", [](nb::handle self) {
            termin::cxx_component_init<termin::SkeletonController>(self);
        })
        .def("__init__", [](nb::handle self, nb::object skeleton_arg, nb::list bone_entities_list) {
            termin::cxx_component_init<termin::SkeletonController>(self);
            auto* cpp = nb::inst_ptr<termin::SkeletonController>(self);

            if (!skeleton_arg.is_none() && nb::isinstance<termin::TcSkeleton>(skeleton_arg)) {
                cpp->skeleton = nb::cast<termin::TcSkeleton>(skeleton_arg);
            }

            std::vector<termin::Entity> entities;
            for (auto item : bone_entities_list) {
                if (!item.is_none()) {
                    entities.push_back(nb::cast<termin::Entity>(item));
                }
            }
            cpp->set_bone_entities(std::move(entities));
        },
            nb::arg("skeleton") = nb::none(),
            nb::arg("bone_entities") = nb::list())
        .def_rw("skeleton", &termin::SkeletonController::skeleton)
        .def_prop_ro("skeleton_data",
            [](const termin::SkeletonController& self) {
                return self.skeleton.get();
            },
            nb::rv_policy::reference)
        .def_prop_rw("bone_entities",
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
                std::vector<termin::Entity> vec;
                for (auto item : entities) {
                    if (!item.is_none()) {
                        vec.push_back(nb::cast<termin::Entity>(item));
                    }
                }
                self.set_bone_entities(std::move(vec));
            })
        .def_prop_ro("skeleton_instance",
            &termin::SkeletonController::skeleton_instance,
            nb::rv_policy::reference)
        .def("set_skeleton", &termin::SkeletonController::set_skeleton)
        .def("set_bone_entities", [](termin::SkeletonController& self, nb::list entities) {
            std::vector<termin::Entity> vec;
            for (auto item : entities) {
                if (!item.is_none()) {
                    vec.push_back(nb::cast<termin::Entity>(item));
                }
            }
            self.set_bone_entities(std::move(vec));
        })
        .def("invalidate_instance", &termin::SkeletonController::invalidate_instance);
}

} // namespace
} // namespace termin

NB_MODULE(_components_skeleton_native, m) {
    m.doc() = "Native C++ skeleton component module (SkeletonController)";

    nb::module_::import_("termin.entity._entity_native");
    nb::module_::import_("termin.skeleton._skeleton_native");

    termin::bind_skeleton_controller(m);
}
