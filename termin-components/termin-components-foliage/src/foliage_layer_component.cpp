#include <termin/foliage/foliage_layer_component.hpp>

#include <any>
#include <utility>

#include <inspect/tc_kind_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <tc_inspect_cpp.hpp>

namespace termin {
namespace {

struct FoliageDataHandleKindRegistrar {
    FoliageDataHandleKindRegistrar() {
        tc::KindRegistryCpp::instance().register_kind(
            "foliage_data_handle",
            [](const std::any& value) -> tc_value {
                const std::string uuid =
                    value.type() == typeid(std::string) ? std::any_cast<std::string>(value) : std::string();
                tc_value result = tc_value_dict_new();
                tc_value_dict_set(&result, "uuid", tc_value_string(uuid.c_str()));
                tc_value_dict_set(&result, "name", tc_value_string(""));
                return result;
            },
            [](const tc_value* value, void*) -> std::any {
                if (!value || value->type == TC_VALUE_NIL) {
                    return std::string();
                }
                if (value->type == TC_VALUE_STRING && value->data.s) {
                    return std::string(value->data.s);
                }
                if (value->type == TC_VALUE_DICT) {
                    tc_value* uuid = tc_value_dict_get(const_cast<tc_value*>(value), "uuid");
                    if (uuid && uuid->type == TC_VALUE_STRING && uuid->data.s) {
                        return std::string(uuid->data.s);
                    }
                }
                return std::string();
            }
        );
    }
};

FoliageDataHandleKindRegistrar foliage_data_handle_kind_registrar;

} // namespace

FoliageLayerComponent::FoliageLayerComponent()
    : CxxComponent("FoliageLayerComponent")
{
    install_drawable_vtable(&_c);
}

void FoliageLayerComponent::register_type() {
    auto& component_registry = ComponentRegistry::instance();
    if (!component_registry.has("FoliageLayerComponent")) {
        component_registry.register_native(
            "FoliageLayerComponent",
            &CxxComponentFactoryData<FoliageLayerComponent>::create,
            nullptr,
            "Component"
        );
    }

    auto& inspect = tc::InspectRegistry::instance();
    inspect.set_type_parent("FoliageLayerComponent", "Component");
    if (!inspect.find_field("FoliageLayerComponent", "enabled")) {
        inspect.add<FoliageLayerComponent, bool>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::enabled,
            "enabled",
            "Enabled",
            "bool"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "prototype_mesh")) {
        inspect.add<FoliageLayerComponent, TcMesh>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::prototype_mesh,
            "prototype_mesh",
            "Prototype Mesh",
            "tc_mesh"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "material")) {
        inspect.add<FoliageLayerComponent, TcMaterial>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::material,
            "material",
            "Material",
            "tc_material"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "layer_name")) {
        inspect.add<FoliageLayerComponent, std::string>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::layer_name,
            "layer_name",
            "Layer Name",
            "string"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "density")) {
        inspect.add<FoliageLayerComponent, double>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::density,
            "density",
            "Density",
            "double"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "min_spacing")) {
        inspect.add<FoliageLayerComponent, double>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::min_spacing,
            "min_spacing",
            "Min Spacing",
            "double"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "scale_min")) {
        inspect.add<FoliageLayerComponent, double>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::scale_min,
            "scale_min",
            "Scale Min",
            "double"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "scale_max")) {
        inspect.add<FoliageLayerComponent, double>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::scale_max,
            "scale_max",
            "Scale Max",
            "double"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "slope_limit_degrees")) {
        inspect.add<FoliageLayerComponent, double>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::slope_limit_degrees,
            "slope_limit_degrees",
            "Slope Limit",
            "double"
        );
    }
}

std::set<std::string> FoliageLayerComponent::get_phase_marks() const {
    if (!enabled || !prototype_mesh.is_valid() || !material.is_valid()) {
        return {};
    }

    std::set<std::string> marks;
    tc_material* mat = material.get();
    if (mat) {
        for (size_t i = 0; i < mat->phase_count; i++) {
            marks.insert(mat->phases[i].phase_mark);
        }
    }
    return marks;
}

void FoliageLayerComponent::draw_geometry(const RenderContext& context, int geometry_id) {
    (void)context;
    (void)geometry_id;
    if (!enabled || !prototype_mesh.is_valid()) {
        return;
    }
    tc_mesh* mesh = prototype_mesh.get();
    if (!mesh) {
        return;
    }
    tc_mesh_draw_gpu(mesh);
}

std::vector<GeometryDrawCall> FoliageLayerComponent::get_geometry_draws(const std::string* phase_mark) {
    std::vector<GeometryDrawCall> draws;
    if (!enabled || !prototype_mesh.is_valid() || !material.is_valid()) {
        return draws;
    }

    tc_material* mat = material.get();
    if (!mat) {
        return draws;
    }

    if (phase_mark) {
        tc_material_phase* phases[TC_MATERIAL_MAX_PHASES];
        size_t count = tc_material_get_phases_for_mark(mat, phase_mark->c_str(), phases, TC_MATERIAL_MAX_PHASES);
        draws.reserve(count);
        for (size_t i = 0; i < count; i++) {
            draws.emplace_back(phases[i], 0);
        }
        return draws;
    }

    draws.reserve(mat->phase_count);
    for (size_t i = 0; i < mat->phase_count; i++) {
        draws.emplace_back(&mat->phases[i], 0);
    }
    return draws;
}

tc_mesh* FoliageLayerComponent::get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const {
    (void)geometry_id;
    if (!enabled || !prototype_mesh.is_valid() || !material.is_valid()) {
        return nullptr;
    }
    tc_material* mat = material.get();
    if (!mat) {
        return nullptr;
    }
    tc_material_phase* phases[TC_MATERIAL_MAX_PHASES];
    size_t count = tc_material_get_phases_for_mark(mat, phase_mark.c_str(), phases, TC_MATERIAL_MAX_PHASES);
    if (count == 0) {
        return nullptr;
    }
    return prototype_mesh.get();
}

namespace {

tc::InspectAccessorFieldRegistrar<FoliageLayerComponent, std::string>
    foliage_layer_asset_field_reg{
        "FoliageLayerComponent",
        "foliage",
        "Foliage Data",
        "foliage_data_handle",
        [](FoliageLayerComponent* self) { return self->foliage_uuid; },
        [](FoliageLayerComponent* self, std::string value) { self->foliage_uuid = std::move(value); }
    };

} // namespace

REGISTER_COMPONENT(FoliageLayerComponent, Component);

} // namespace termin
