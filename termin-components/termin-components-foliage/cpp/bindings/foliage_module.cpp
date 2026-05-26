#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <termin/bindings/entity_helpers.hpp>
#include <termin/foliage/foliage_data.hpp>
#include <termin/foliage/foliage_data_registry.hpp>
#include <termin/foliage/foliage_layer_component.hpp>

namespace nb = nanobind;
using namespace termin;

namespace {

bool save_handle(TcFoliageData& handle) {
    FoliageData* data = handle.get();
    if (!data) {
        return false;
    }
    if (data->source_path.empty()) {
        return false;
    }
    return data->save_to_file(data->source_path);
}

std::vector<FoliageInstance> handle_instances(TcFoliageData& handle) {
    if (!handle.ensure_loaded()) {
        return {};
    }
    FoliageData* data = handle.get();
    if (!data) {
        return {};
    }
    return data->instances;
}

bool add_instance(TcFoliageData& handle, const FoliageInstance& instance) {
    if (!handle.ensure_loaded()) {
        return false;
    }
    FoliageData* data = handle.get();
    if (!data) {
        return false;
    }
    data->add_instance(instance);
    return true;
}

size_t remove_instances_in_radius(
    TcFoliageData& handle,
    float x,
    float y,
    float z,
    float radius
) {
    if (!handle.ensure_loaded()) {
        return 0;
    }
    FoliageData* data = handle.get();
    if (!data) {
        return 0;
    }
    return data->remove_instances_in_radius(FoliageVec3f{x, y, z}, radius);
}

} // namespace

NB_MODULE(_foliage_native, m) {
    m.doc() = "Native foliage data and component bindings";

    nb::module_::import_("termin.scene._scene_native");
    nb::module_::import_("tmesh._tmesh_native");
    nb::module_::import_("tgfx._tgfx_native");

    nb::class_<FoliageInstance>(m, "FoliageInstance")
        .def(nb::init<>())
        .def_rw("px", &FoliageInstance::px)
        .def_rw("py", &FoliageInstance::py)
        .def_rw("pz", &FoliageInstance::pz)
        .def_rw("nx", &FoliageInstance::nx)
        .def_rw("ny", &FoliageInstance::ny)
        .def_rw("nz", &FoliageInstance::nz)
        .def_rw("yaw", &FoliageInstance::yaw)
        .def_rw("scale", &FoliageInstance::scale)
        .def_rw("variant", &FoliageInstance::variant)
        .def_rw("seed", &FoliageInstance::seed);

    nb::class_<TcFoliageData>(m, "TcFoliageData")
        .def(nb::init<>())
        .def_static("declare", &TcFoliageData::declare,
            nb::arg("uuid"), nb::arg("name"), nb::arg("source_path") = "")
        .def_static("from_uuid", &TcFoliageData::from_uuid, nb::arg("uuid"))
        .def_static("clear_registry_for_tests", &TcFoliageData::clear_registry_for_tests)
        .def_prop_ro("is_valid", &TcFoliageData::is_valid)
        .def_prop_ro("is_loaded", &TcFoliageData::is_loaded)
        .def_prop_ro("uuid", [](const TcFoliageData& handle) {
            return std::string(handle.uuid());
        })
        .def_prop_ro("name", [](const TcFoliageData& handle) {
            return std::string(handle.name());
        })
        .def_prop_ro("source_path", [](const TcFoliageData& handle) {
            return std::string(handle.source_path());
        })
        .def_prop_ro("version", &TcFoliageData::version)
        .def_prop_ro("instance_count", &TcFoliageData::instance_count)
        .def_prop_ro("instances", &handle_instances)
        .def("ensure_loaded", &TcFoliageData::ensure_loaded)
        .def("reload", &TcFoliageData::reload)
        .def("save", &save_handle)
        .def("add_instance", &add_instance, nb::arg("instance"))
        .def("remove_instances_in_radius", &remove_instances_in_radius,
            nb::arg("x"), nb::arg("y"), nb::arg("z"), nb::arg("radius"));

    nb::class_<FoliageLayerComponent, CxxComponent>(m, "FoliageLayerComponent")
        .def("__init__", [](nb::handle self) {
            cxx_component_init<FoliageLayerComponent>(self);
        })
        .def_rw("enabled", &FoliageLayerComponent::enabled)
        .def_rw("foliage_uuid", &FoliageLayerComponent::foliage_uuid)
        .def_rw("prototype_mesh", &FoliageLayerComponent::prototype_mesh)
        .def_rw("material", &FoliageLayerComponent::material)
        .def_rw("layer_name", &FoliageLayerComponent::layer_name)
        .def_rw("density", &FoliageLayerComponent::density)
        .def_rw("min_spacing", &FoliageLayerComponent::min_spacing)
        .def_rw("scale_min", &FoliageLayerComponent::scale_min)
        .def_rw("scale_max", &FoliageLayerComponent::scale_max)
        .def_rw("slope_limit_degrees", &FoliageLayerComponent::slope_limit_degrees);
}
