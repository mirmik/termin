#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <trent/json.h>
#include <termin/bindings/entity_helpers.hpp>
#include <termin/entity/entity.hpp>
#include <termin/prefab/prefab_document.hpp>
#include <termin/prefab/prefab_instance_state.hpp>
#include <termin/prefab/prefab_instantiator.hpp>

namespace nb = nanobind;

NB_MODULE(_prefab_native, m) {
    m.doc() = "Native prefab document instantiation";
    nb::module_::import_("termin.scene._scene_native");

    nb::class_<termin::prefab::PrefabInstanceState, termin::CxxComponent>(
        m,
        "PrefabInstanceState"
    )
        .def("__init__", [](nb::handle self, const std::string& prefab_asset_uuid) {
            termin::prefab::register_prefab_component_types();
            termin::cxx_component_init<termin::prefab::PrefabInstanceState>(
                self,
                prefab_asset_uuid
            );
        }, nb::arg("prefab_asset_uuid") = "")
        .def_prop_rw(
            "prefab_asset_uuid",
            &termin::prefab::PrefabInstanceState::prefab_asset_uuid,
            &termin::prefab::PrefabInstanceState::set_prefab_asset_uuid
        )
        .def_prop_rw(
            "source_revision",
            &termin::prefab::PrefabInstanceState::source_revision,
            &termin::prefab::PrefabInstanceState::set_source_revision
        )
        .def_prop_ro(
            "entity_mapping_count",
            &termin::prefab::PrefabInstanceState::entity_mapping_count
        )
        .def_prop_ro(
            "component_mapping_count",
            &termin::prefab::PrefabInstanceState::component_mapping_count
        )
        .def(
            "entity_for_source",
            &termin::prefab::PrefabInstanceState::entity_for_source,
            nb::arg("source_id")
        )
        .def(
            "component_owner_for_source",
            &termin::prefab::PrefabInstanceState::component_owner_for_source,
            nb::arg("source_id")
        );

    m.def(
        "find_live_instances",
        [](const std::string& prefab_asset_uuid) {
            return termin::prefab::find_live_prefab_instances(prefab_asset_uuid);
        },
        nb::arg("prefab_asset_uuid")
    );
    m.def(
        "count_live_instances",
        &termin::prefab::count_live_prefab_instances,
        nb::arg("prefab_asset_uuid")
    );

    nb::enum_<termin::prefab::PrefabDocumentError>(m, "PrefabDocumentError")
        .value("NONE", termin::prefab::PrefabDocumentError::None)
        .value("INVALID_JSON", termin::prefab::PrefabDocumentError::InvalidJson)
        .value("INVALID_DOCUMENT", termin::prefab::PrefabDocumentError::InvalidDocument)
        .value("UNSUPPORTED_VERSION", termin::prefab::PrefabDocumentError::UnsupportedVersion)
        .value("INVALID_TARGET_SCENE", termin::prefab::PrefabDocumentError::InvalidTargetScene)
        .value("INVALID_PARENT", termin::prefab::PrefabDocumentError::InvalidParent)
        .value("SOURCE_MATERIALIZATION_FAILED", termin::prefab::PrefabDocumentError::SourceMaterializationFailed);

    nb::class_<termin::prefab::PrefabDocument>(m, "PrefabDocument")
        .def_static("from_json", [](const std::string& text) {
            termin::prefab::PrefabDocumentResult result =
                termin::prefab::PrefabDocument::parse_json(text);
            if (!result.ok()) {
                throw nb::value_error(result.message.c_str());
            }
            return result.document;
        }, nb::arg("text"))
        .def_static("capture", [](const std::string& asset_uuid, const termin::Entity& root) {
            termin::prefab::PrefabDocumentResult result =
                termin::prefab::PrefabDocument::capture(asset_uuid, root);
            if (!result.ok()) {
                throw nb::value_error(result.message.c_str());
            }
            return result.document;
        }, nb::arg("asset_uuid"), nb::arg("root"))
        .def_static("empty", [](
            const std::string& asset_uuid,
            const std::string& root_source_id,
            const std::string& root_name
        ) {
            termin::prefab::PrefabDocumentResult result =
                termin::prefab::PrefabDocument::empty(
                    asset_uuid,
                    root_source_id,
                    root_name
                );
            if (!result.ok()) {
                throw nb::value_error(result.message.c_str());
            }
            return result.document;
        }, nb::arg("asset_uuid"), nb::arg("root_source_id"), nb::arg("root_name"))
        .def_prop_ro("version", [](const termin::prefab::PrefabDocument&) {
            return std::string(termin::prefab::PrefabDocument::CurrentVersion);
        })
        .def_prop_ro("uuid", &termin::prefab::PrefabDocument::asset_uuid)
        .def_prop_ro("source_revision", &termin::prefab::PrefabDocument::source_revision)
        .def("to_json", &termin::prefab::PrefabDocument::to_json, nb::arg("indent") = 2)
        .def_prop_ro("data", [](const termin::prefab::PrefabDocument& document) {
            nb::object json = nb::module_::import_("json");
            return json.attr("loads")(document.to_json());
        })
        .def("materialize_source", [](
            const termin::prefab::PrefabDocument& document,
            nb::object scene,
            nb::object parent
        ) {
            if (scene.is_none()) {
                throw nb::value_error("prefab target scene is required");
            }
            tc_scene_handle scene_handle = nb::cast<tc_scene_handle>(scene.attr("scene_handle")());
            termin::Entity parent_entity;
            if (!parent.is_none()) {
                parent_entity = nb::cast<termin::Entity>(parent);
            }
            termin::prefab::PrefabDocumentResult result =
                document.materialize_source(scene_handle, parent_entity);
            if (!result.ok()) {
                throw std::runtime_error(result.message);
            }
            return result.root;
        }, nb::arg("scene"), nb::arg("parent") = nb::none());

    m.def(
        "instantiate_document",
        [](const termin::prefab::PrefabDocument& document,
           nb::object scene,
           nb::object parent,
           nb::object name,
           nb::object position) {
            if (scene.is_none()) {
                throw nb::value_error("prefab target scene is required");
            }
            tc_scene_handle scene_handle = nb::cast<tc_scene_handle>(scene.attr("scene_handle")());
            termin::Entity parent_entity;
            if (!parent.is_none()) {
                parent_entity = nb::cast<termin::Entity>(parent);
            }
            termin::prefab::PrefabInstantiateOptions options;
            if (!name.is_none()) {
                options.root_name = nb::cast<std::string>(name);
            }
            if (!position.is_none()) {
                nb::sequence values = nb::cast<nb::sequence>(position);
                if (nb::len(values) != 3) {
                    throw nb::value_error("prefab position must contain exactly three values");
                }
                options.has_position = true;
                for (size_t i = 0; i < 3; ++i) {
                    options.position[i] = nb::cast<double>(values[i]);
                }
            }
            termin::prefab::PrefabInstantiateResult result =
                termin::prefab::PrefabInstantiator::instantiate(
                    document,
                    scene_handle,
                    parent_entity,
                    options
                );
            if (!result.ok()) {
                throw std::runtime_error(result.message);
            }
            return result.root;
        },
        nb::arg("document"),
        nb::arg("scene"),
        nb::arg("parent") = nb::none(),
        nb::arg("name") = nb::none(),
        nb::arg("position") = nb::none()
    );

    m.def(
        "instantiate_hierarchy",
        [](nb::object data, nb::object scene, nb::object parent, nb::object name, nb::object position) {
            if (data.is_none()) {
                throw nb::value_error("prefab hierarchy data is required");
            }
            if (scene.is_none()) {
                throw nb::value_error("prefab target scene is required");
            }

            nb::object json = nb::module_::import_("json");
            const std::string serialized = nb::cast<std::string>(json.attr("dumps")(data));
            nos::trent hierarchy = nos::json::parse(serialized);
            tc_scene_handle scene_handle = nb::cast<tc_scene_handle>(scene.attr("scene_handle")());

            termin::Entity parent_entity;
            if (!parent.is_none()) {
                parent_entity = nb::cast<termin::Entity>(parent);
            }

            termin::prefab::PrefabInstantiateOptions options;
            if (!name.is_none()) {
                options.root_name = nb::cast<std::string>(name);
            }
            if (!position.is_none()) {
                nb::sequence values = nb::cast<nb::sequence>(position);
                if (nb::len(values) != 3) {
                    throw nb::value_error("prefab position must contain exactly three values");
                }
                options.has_position = true;
                for (size_t i = 0; i < 3; ++i) {
                    options.position[i] = nb::cast<double>(values[i]);
                }
            }

            termin::prefab::PrefabInstantiateResult result =
                termin::prefab::PrefabInstantiator::instantiate(
                    hierarchy,
                    scene_handle,
                    parent_entity,
                    options
                );
            if (!result.ok()) {
                throw std::runtime_error(result.message);
            }
            return result.root;
        },
        nb::arg("data"),
        nb::arg("scene"),
        nb::arg("parent") = nb::none(),
        nb::arg("name") = nb::none(),
        nb::arg("position") = nb::none()
    );
}
