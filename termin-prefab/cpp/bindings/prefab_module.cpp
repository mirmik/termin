#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>

#include <trent/json.h>
#include <termin/entity/entity.hpp>
#include <termin/prefab/prefab_instantiator.hpp>

namespace nb = nanobind;

NB_MODULE(_prefab_native, m) {
    m.doc() = "Native prefab document instantiation";

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
