#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <termin/bindings/entity_helpers.hpp>
#include <termin/ui/tc_scene_ui_document_capability.h>
#include <termin/ui/ui_component.hpp>
#include <termin/ui/world_ui_surface_component.hpp>

namespace nb = nanobind;

NB_MODULE(_ui_components_native, module) {
    module.doc() = "Native scene UI component bindings";

    nb::module_::import_("termin.scene._scene_native");
    nb::module_::import_("termin.gui_native._gui_native");

    nb::class_<termin::UIComponent, termin::CxxComponent>(module, "UIComponent")
        .def(
            "__init__",
            [](nb::handle self, int priority) { termin::cxx_component_init<termin::UIComponent>(self, priority); },
            nb::arg("priority") = 1000)
        .def_prop_rw("priority", &termin::UIComponent::priority, &termin::UIComponent::set_priority)
        .def_prop_rw("input_source_mask",
                     &termin::UIComponent::input_source_mask,
                     &termin::UIComponent::set_input_source_mask_value)
        .def_prop_rw("ui_layout_uuid",
                     &termin::UIComponent::ui_layout_uuid,
                     [](termin::UIComponent& self, const std::string& uuid) {
                         if (!self.set_ui_layout_uuid(uuid)) {
                             throw std::runtime_error("failed to assign native UI document asset '" + uuid + "'");
                         }
                     })
        .def_prop_rw("ui_layout",
                     &termin::UIComponent::ui_layout,
                     [](termin::UIComponent& self, const termin::gui_native::TcUiDocumentAsset& asset) {
                         if (!asset.valid()) {
                             self.set_ui_layout_uuid({});
                             return;
                         }
                         if (!self.set_ui_layout_uuid(asset.uuid())) {
                             throw std::runtime_error("failed to assign native UI document asset '" + asset.uuid() +
                                                      "'");
                         }
                     })
        .def_prop_ro("document", &termin::UIComponent::document)
        .def_prop_ro("has_document", &termin::UIComponent::has_document)
        .def("reload_document", &termin::UIComponent::reload_document)
        .def("clear_document", &termin::UIComponent::clear_document);

    nb::class_<termin::WorldUiSurfaceComponent, termin::CxxComponent>(module, "WorldUiSurfaceComponent")
        .def("__init__", [](nb::handle self) { termin::cxx_component_init<termin::WorldUiSurfaceComponent>(self); })
        .def_rw("ui_entity_uuid", &termin::WorldUiSurfaceComponent::ui_entity_uuid)
        .def_rw("local_width", &termin::WorldUiSurfaceComponent::local_width)
        .def_rw("local_height", &termin::WorldUiSurfaceComponent::local_height)
        .def_rw("two_sided", &termin::WorldUiSurfaceComponent::two_sided);

    module.def("scene_ui_document_capability_id", &tc_scene_ui_document_capability_id);
    module.def(
        "has_scene_ui_document_capability",
        [](std::uintptr_t component_ptr) {
            const auto* component = reinterpret_cast<const tc_component*>(component_ptr);
            return tc_scene_ui_document_capability_get(component) != nullptr;
        },
        nb::arg("component_ptr"));
}
