#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <algorithm>
#include <charconv>
#include <cmath>
#include <limits>
#include <optional>

#include <trent/json.h>
#include <termin/bindings/entity_helpers.hpp>
#include <termin/entity/entity.hpp>
#include <termin/prefab/prefab_document.hpp>
#include <termin/prefab/prefab_instance_state.hpp>
#include <termin/prefab/prefab_instantiator.hpp>
#include <termin/prefab/prefab_override_value.hpp>

namespace nb = nanobind;

namespace {

std::string canonical_float(double value) {
    if (!std::isfinite(value)) {
        throw nb::value_error("prefab override floats must be finite");
    }
    char buffer[64];
    auto result = std::to_chars(
        buffer, buffer + sizeof(buffer), value,
        std::chars_format::general, std::numeric_limits<double>::max_digits10
    );
    if (result.ec != std::errc()) {
        throw nb::value_error("failed to encode prefab override float");
    }
    return std::string(buffer, result.ptr);
}

nb::dict tagged(const char* tag) {
    nb::dict result;
    result["tag"] = tag;
    return result;
}

nb::object encode_python_node(nb::object value, size_t depth = 0) {
    if (depth > 64) {
        throw nb::value_error("prefab override value exceeds nesting limit");
    }
    if (value.is_none()) return tagged("none");
    if (nb::isinstance<nb::bool_>(value)) {
        nb::dict result = tagged("bool");
        result["value"] = value;
        return result;
    }
    if (nb::isinstance<nb::int_>(value)) {
        int64_t integer = 0;
        try {
            integer = nb::cast<int64_t>(value);
        } catch (const nb::cast_error&) {
            uint64_t unsigned_integer = 0;
            try {
                unsigned_integer = nb::cast<uint64_t>(value);
            } catch (const nb::cast_error&) {
                throw nb::value_error("prefab override integer is outside uint64 range");
            }
            nb::dict result = tagged("uint64");
            const std::string encoded = std::to_string(unsigned_integer);
            result["value"] = nb::str(encoded.c_str());
            return result;
        }
        nb::dict result = tagged("int64");
        const std::string encoded = std::to_string(integer);
        result["value"] = nb::str(encoded.c_str());
        return result;
    }
    if (nb::isinstance<nb::float_>(value)) {
        nb::dict result = tagged("float64");
        const std::string encoded = canonical_float(nb::cast<double>(value));
        result["value"] = nb::str(encoded.c_str());
        return result;
    }
    if (nb::isinstance<nb::str>(value)) {
        nb::dict result = tagged("string");
        result["value"] = value;
        return result;
    }
    if (nb::isinstance<nb::list>(value) || nb::isinstance<nb::tuple>(value)) {
        const bool is_tuple = nb::isinstance<nb::tuple>(value);
        nb::dict result = tagged(is_tuple ? "tuple" : "list");
        nb::list items;
        for (nb::handle item : value) {
            items.append(encode_python_node(nb::borrow<nb::object>(item), depth + 1));
        }
        result["items"] = std::move(items);
        return result;
    }
    if (nb::isinstance<nb::dict>(value)) {
        nb::dict result = tagged("dict");
        nb::list entries;
        for (auto item : nb::cast<nb::dict>(value)) {
            if (!nb::isinstance<nb::str>(item.first)) {
                throw nb::type_error("prefab override dictionaries require string keys");
            }
            nb::dict entry;
            entry["key"] = nb::borrow<nb::object>(item.first);
            entry["value"] = encode_python_node(
                nb::borrow<nb::object>(item.second), depth + 1
            );
            entries.append(std::move(entry));
        }
        result["entries"] = std::move(entries);
        return result;
    }

    nb::module_ numpy = nb::module_::import_("numpy");
    if (nb::isinstance(value, numpy.attr("ndarray"))) {
        const std::string dtype = nb::cast<std::string>(value.attr("dtype").attr("name"));
        static const std::vector<std::string> supported = {
            "bool", "int8", "int16", "int32", "int64",
            "uint8", "uint16", "uint32", "uint64", "float32", "float64"
        };
        if (std::find(supported.begin(), supported.end(), dtype) == supported.end()) {
            throw nb::type_error(("unsupported prefab override ndarray dtype '" + dtype + "'").c_str());
        }
        nb::dict result = tagged("array");
        result["dtype"] = nb::str(dtype.c_str());
        nb::list shape;
        for (nb::handle dimension : value.attr("shape")) shape.append(dimension);
        result["shape"] = std::move(shape);
        nb::list items;
        nb::object flattened = value.attr("reshape")(-1).attr("tolist")();
        for (nb::handle item : flattened) {
            items.append(encode_python_node(nb::borrow<nb::object>(item), depth + 1));
        }
        result["items"] = std::move(items);
        return result;
    }
    if (nb::isinstance(value, numpy.attr("generic"))) {
        return encode_python_node(value.attr("item")(), depth + 1);
    }

    nb::object inspect = nb::module_::import_("termin.inspect");
    nb::object registry = inspect.attr("KindRegistry").attr("instance")();
    const std::string kind = nb::cast<std::string>(registry.attr("kind_for_object")(value));
    if (!kind.empty()) {
        nb::object payload = registry.attr("serialize")(kind, value);
        nb::dict result = tagged("kind");
        result["kind"] = nb::str(kind.c_str());
        result["payload"] = encode_python_node(payload, depth + 1);
        return result;
    }
    throw nb::type_error("unsupported Python value for prefab override");
}

nb::object decode_python_node(nb::dict node) {
    const std::string tag = nb::cast<std::string>(node["tag"]);
    if (tag == "none") return nb::none();
    if (tag == "bool") return nb::borrow<nb::object>(node["value"]);
    if (tag == "int64") return nb::module_::import_("builtins").attr("int")(node["value"]);
    if (tag == "uint64") return nb::module_::import_("builtins").attr("int")(node["value"]);
    if (tag == "float64") return nb::module_::import_("builtins").attr("float")(node["value"]);
    if (tag == "string") return nb::borrow<nb::object>(node["value"]);
    if (tag == "list" || tag == "tuple") {
        nb::list items;
        for (nb::handle item : nb::cast<nb::list>(node["items"])) {
            items.append(decode_python_node(nb::cast<nb::dict>(item)));
        }
        if (tag == "tuple") return nb::tuple(items);
        return items;
    }
    if (tag == "dict") {
        nb::dict result;
        for (nb::handle item : nb::cast<nb::list>(node["entries"])) {
            nb::dict entry = nb::cast<nb::dict>(item);
            result[entry["key"]] = decode_python_node(nb::cast<nb::dict>(entry["value"]));
        }
        return result;
    }
    if (tag == "array") {
        nb::list items;
        for (nb::handle item : nb::cast<nb::list>(node["items"])) {
            items.append(decode_python_node(nb::cast<nb::dict>(item)));
        }
        nb::module_ numpy = nb::module_::import_("numpy");
        nb::object array = numpy.attr("asarray")(items, nb::arg("dtype") = node["dtype"]);
        return array.attr("reshape")(node["shape"]);
    }
    if (tag == "kind") {
        nb::object registry = nb::module_::import_("termin.inspect")
            .attr("KindRegistry").attr("instance")();
        nb::object payload = decode_python_node(nb::cast<nb::dict>(node["payload"]));
        if (!nb::cast<bool>(registry.attr("has_python")(node["kind"]))) {
            return payload;
        }
        return registry.attr("deserialize")(node["kind"], payload);
    }
    if (tag == "resource") {
        nb::dict payload;
        payload["uuid"] = node["uuid"];
        if (node.contains("name")) payload["name"] = node["name"];
        nb::object registry = nb::module_::import_("termin.inspect")
            .attr("KindRegistry").attr("instance")();
        return registry.attr("deserialize")(node["kind"], payload);
    }
    throw nb::value_error("unknown prefab override value tag");
}

termin::prefab::PrefabOverrideValue parse_override_data(nb::object data) {
    nb::object json = nb::module_::import_("json");
    const std::string encoded = nb::cast<std::string>(json.attr("dumps")(data));
    std::string error;
    auto result = termin::prefab::PrefabOverrideValue::parse_json(encoded, error);
    if (!result) throw nb::value_error(error.c_str());
    return std::move(*result);
}

termin::prefab::PrefabOverrideValue encode_python_override(
    nb::object value,
    nb::object explicit_kind,
    nb::object resource_type
) {
    nb::object node;
    if (!explicit_kind.is_none()) {
        const std::string kind = nb::cast<std::string>(explicit_kind);
        if (kind.empty()) throw nb::value_error("override kind must not be empty");
        nb::object registry = nb::module_::import_("termin.inspect")
            .attr("KindRegistry").attr("instance")();
        const bool has_python_kind = nb::cast<bool>(registry.attr("has_python")(kind));
        nb::object payload = has_python_kind
            ? registry.attr("serialize")(kind, value)
            : value;
        if (!resource_type.is_none()) {
            if (!has_python_kind) {
                throw nb::value_error(
                    "resource override kind requires a registered Python serializer"
                );
            }
            if (!nb::isinstance<nb::dict>(payload)) {
                throw nb::type_error("resource kind serializer must return a dictionary");
            }
            nb::dict serialized = nb::cast<nb::dict>(payload);
            if (!serialized.contains("uuid") || !nb::isinstance<nb::str>(serialized["uuid"])) {
                throw nb::value_error("resource override requires a serialized UUID");
            }
            nb::dict resource = tagged("resource");
            resource["resource_type"] = resource_type;
            resource["kind"] = explicit_kind;
            resource["uuid"] = serialized["uuid"];
            if (serialized.contains("name") && nb::isinstance<nb::str>(serialized["name"])) {
                resource["name"] = serialized["name"];
            }
            node = std::move(resource);
        } else {
            nb::dict semantic = tagged("kind");
            semantic["kind"] = explicit_kind;
            semantic["payload"] = encode_python_node(payload);
            node = std::move(semantic);
        }
    } else {
        if (!resource_type.is_none()) {
            throw nb::value_error("resource_type requires an explicit inspect kind");
        }
        node = encode_python_node(value);
    }

    nb::dict envelope;
    envelope["schema"] = termin::prefab::PrefabOverrideValue::Schema;
    envelope["version"] = termin::prefab::PrefabOverrideValue::Version;
    envelope["value"] = node;
    return parse_override_data(envelope);
}

class PythonBindingResourceResolver final
    : public termin::prefab::PrefabOverrideResourceResolver {
public:
    bool resolve(
        std::string_view resource_type,
        std::string_view target_kind,
        std::string_view uuid,
        std::string_view display_name,
        tc::trent& result,
        std::string& error
    ) const override {
        if (resource_type.empty() || target_kind.empty() || uuid.empty()) {
            error = "resource override identity is incomplete";
            return false;
        }
        result = tc::trent::dict();
        result.set("uuid", std::string(uuid));
        if (!display_name.empty()) result.set("name", std::string(display_name));
        return true;
    }
};

} // namespace

NB_MODULE(_prefab_native, m) {
    m.doc() = "Native prefab document instantiation";
    nb::module_::import_("termin.scene._scene_native");

    nb::class_<termin::prefab::PrefabOverrideValue>(m, "PrefabOverrideValue")
        .def(nb::init<>())
        .def_static("from_json", [](const std::string& json) {
            std::string error;
            auto value = termin::prefab::PrefabOverrideValue::parse_json(json, error);
            if (!value) throw nb::value_error(error.c_str());
            return std::move(*value);
        }, nb::arg("json"))
        .def_static("from_data", &parse_override_data, nb::arg("data"))
        .def_static(
            "from_python", &encode_python_override,
            nb::arg("value").none(), nb::arg("kind") = nb::none(),
            nb::arg("resource_type") = nb::none()
        )
        .def_prop_ro("tag", &termin::prefab::PrefabOverrideValue::tag)
        .def("to_json", &termin::prefab::PrefabOverrideValue::to_json, nb::arg("indent") = -1)
        .def("to_data", [](const termin::prefab::PrefabOverrideValue& value) {
            return nb::module_::import_("json").attr("loads")(value.to_json());
        })
        .def("to_python", [](const termin::prefab::PrefabOverrideValue& value) {
            nb::dict envelope = nb::cast<nb::dict>(
                nb::module_::import_("json").attr("loads")(value.to_json())
            );
            return decode_python_node(nb::cast<nb::dict>(envelope["value"]));
        });

    nb::enum_<termin::prefab::PrefabPropertyApplyError>(m, "PrefabPropertyApplyError")
        .value("NONE", termin::prefab::PrefabPropertyApplyError::None)
        .value("INVALID_STATE", termin::prefab::PrefabPropertyApplyError::InvalidState)
        .value("INVALID_DOCUMENT", termin::prefab::PrefabPropertyApplyError::InvalidDocument)
        .value("DOCUMENT_MISMATCH", termin::prefab::PrefabPropertyApplyError::DocumentMismatch)
        .value("OVERRIDE_NOT_FOUND", termin::prefab::PrefabPropertyApplyError::OverrideNotFound)
        .value("SOURCE_ENTITY_NOT_FOUND", termin::prefab::PrefabPropertyApplyError::SourceEntityNotFound)
        .value("RUNTIME_ENTITY_NOT_FOUND", termin::prefab::PrefabPropertyApplyError::RuntimeEntityNotFound)
        .value("SOURCE_COMPONENT_NOT_FOUND", termin::prefab::PrefabPropertyApplyError::SourceComponentNotFound)
        .value("RUNTIME_COMPONENT_NOT_FOUND", termin::prefab::PrefabPropertyApplyError::RuntimeComponentNotFound)
        .value("COMPONENT_OWNER_MISMATCH", termin::prefab::PrefabPropertyApplyError::ComponentOwnerMismatch)
        .value("COMPONENT_TYPE_MISMATCH", termin::prefab::PrefabPropertyApplyError::ComponentTypeMismatch)
        .value("FIELD_NOT_FOUND", termin::prefab::PrefabPropertyApplyError::FieldNotFound)
        .value("FIELD_NOT_SERIALIZABLE", termin::prefab::PrefabPropertyApplyError::FieldNotSerializable)
        .value("KIND_MISMATCH", termin::prefab::PrefabPropertyApplyError::KindMismatch)
        .value("INVALID_SOURCE_VALUE", termin::prefab::PrefabPropertyApplyError::InvalidSourceValue)
        .value("RESOURCE_RESOLUTION_FAILED", termin::prefab::PrefabPropertyApplyError::ResourceResolutionFailed)
        .value("SETTER_FAILED", termin::prefab::PrefabPropertyApplyError::SetterFailed)
        .value("STRUCTURAL_OVERRIDE_INVALID", termin::prefab::PrefabPropertyApplyError::StructuralOverrideInvalid)
        .value("FACTORY_UNAVAILABLE", termin::prefab::PrefabPropertyApplyError::FactoryUnavailable)
        .value("ATTACHMENT_FAILED", termin::prefab::PrefabPropertyApplyError::AttachmentFailed)
        .value("PARENT_CYCLE", termin::prefab::PrefabPropertyApplyError::ParentCycle)
        .value("ORDER_FAILED", termin::prefab::PrefabPropertyApplyError::OrderFailed)
        .value("REMOVAL_CONFLICT", termin::prefab::PrefabPropertyApplyError::RemovalConflict);
    m.attr("PrefabOverrideRestoreError") = m.attr("PrefabPropertyApplyError");

    nb::class_<termin::prefab::PrefabOverrideRestoreFailure>(m, "PrefabOverrideRestoreFailure")
        .def_ro("error", &termin::prefab::PrefabOverrideRestoreFailure::error)
        .def_ro("source_entity_id", &termin::prefab::PrefabOverrideRestoreFailure::source_entity_id)
        .def_ro("source_component_id", &termin::prefab::PrefabOverrideRestoreFailure::source_component_id)
        .def_ro("field_path", &termin::prefab::PrefabOverrideRestoreFailure::field_path)
        .def_ro("message", &termin::prefab::PrefabOverrideRestoreFailure::message);

    nb::class_<termin::prefab::PrefabOverrideRestoreResult>(m, "PrefabOverrideRestoreResult")
        .def_prop_ro("ok", &termin::prefab::PrefabOverrideRestoreResult::ok)
        .def_ro("requested_count", &termin::prefab::PrefabOverrideRestoreResult::requested_count)
        .def_ro("restored_count", &termin::prefab::PrefabOverrideRestoreResult::restored_count)
        .def_ro("failures", &termin::prefab::PrefabOverrideRestoreResult::failures);

    nb::enum_<termin::prefab::PrefabReconcilePhase>(m, "PrefabReconcilePhase")
        .value("VALIDATION", termin::prefab::PrefabReconcilePhase::Validation)
        .value("STRUCTURE", termin::prefab::PrefabReconcilePhase::Structure)
        .value("SOURCE_VALUE", termin::prefab::PrefabReconcilePhase::SourceValue)
        .value("OVERRIDE_VALUE", termin::prefab::PrefabReconcilePhase::OverrideValue);

    nb::class_<termin::prefab::PrefabReconcileFailure>(m, "PrefabReconcileFailure")
        .def_ro("phase", &termin::prefab::PrefabReconcileFailure::phase)
        .def_ro("error", &termin::prefab::PrefabReconcileFailure::error)
        .def_ro("source_entity_id", &termin::prefab::PrefabReconcileFailure::source_entity_id)
        .def_ro("source_component_id", &termin::prefab::PrefabReconcileFailure::source_component_id)
        .def_ro("field_path", &termin::prefab::PrefabReconcileFailure::field_path)
        .def_ro("message", &termin::prefab::PrefabReconcileFailure::message);

    nb::class_<termin::prefab::PrefabReconcileResult>(m, "PrefabReconcileResult")
        .def_prop_ro("ok", &termin::prefab::PrefabReconcileResult::ok)
        .def_ro("structure_operation_count", &termin::prefab::PrefabReconcileResult::structure_operation_count)
        .def_ro("structure_operations_applied", &termin::prefab::PrefabReconcileResult::structure_operations_applied)
        .def_ro("source_field_count", &termin::prefab::PrefabReconcileResult::source_field_count)
        .def_ro("source_fields_applied", &termin::prefab::PrefabReconcileResult::source_fields_applied)
        .def_ro("override_count", &termin::prefab::PrefabReconcileResult::override_count)
        .def_ro("overrides_applied", &termin::prefab::PrefabReconcileResult::overrides_applied)
        .def_ro("dormant_override_count", &termin::prefab::PrefabReconcileResult::dormant_override_count)
        .def_ro("revision_updated", &termin::prefab::PrefabReconcileResult::revision_updated)
        .def_ro("previous_revision", &termin::prefab::PrefabReconcileResult::previous_revision)
        .def_ro("target_revision", &termin::prefab::PrefabReconcileResult::target_revision)
        .def_ro("failures", &termin::prefab::PrefabReconcileResult::failures);

    nb::enum_<termin::prefab::PrefabStructuralOverrideKind>(m, "PrefabStructuralOverrideKind")
        .value("SUPPRESS_ENTITY", termin::prefab::PrefabStructuralOverrideKind::SuppressEntity)
        .value("SUPPRESS_COMPONENT", termin::prefab::PrefabStructuralOverrideKind::SuppressComponent)
        .value("PLACE_ENTITY", termin::prefab::PrefabStructuralOverrideKind::PlaceEntity)
        .value("PLACE_COMPONENT", termin::prefab::PrefabStructuralOverrideKind::PlaceComponent);

    nb::enum_<termin::prefab::PrefabStructureReferenceKind>(m, "PrefabStructureReferenceKind")
        .value("END", termin::prefab::PrefabStructureReferenceKind::End)
        .value("SOURCE", termin::prefab::PrefabStructureReferenceKind::Source)
        .value("LOCAL", termin::prefab::PrefabStructureReferenceKind::Local);

    nb::class_<termin::prefab::PrefabStructureReference>(m, "PrefabStructureReference")
        .def(nb::init<>())
        .def_rw("kind", &termin::prefab::PrefabStructureReference::kind)
        .def_rw("source_id", &termin::prefab::PrefabStructureReference::source_id)
        .def_rw("local_entity", &termin::prefab::PrefabStructureReference::local_entity)
        .def_rw(
            "local_component_source_id",
            &termin::prefab::PrefabStructureReference::local_component_source_id
        );

    nb::class_<termin::prefab::PrefabStructuralOverride>(m, "PrefabStructuralOverride")
        .def(nb::init<>())
        .def_rw("kind", &termin::prefab::PrefabStructuralOverride::kind)
        .def_rw("source_entity_id", &termin::prefab::PrefabStructuralOverride::source_entity_id)
        .def_rw("source_component_id", &termin::prefab::PrefabStructuralOverride::source_component_id)
        .def_rw("parent", &termin::prefab::PrefabStructuralOverride::parent)
        .def_rw("before", &termin::prefab::PrefabStructuralOverride::before);

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
        .def_prop_ro(
            "property_override_count",
            &termin::prefab::PrefabInstanceState::property_override_count
        )
        .def_prop_ro(
            "structural_override_count",
            &termin::prefab::PrefabInstanceState::structural_override_count
        )
        .def_prop_ro(
            "overrides_valid",
            &termin::prefab::PrefabInstanceState::overrides_valid
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
        )
        .def(
            "set_property_override",
            [](termin::prefab::PrefabInstanceState& self,
               const std::string& source_entity_id,
               const std::string& source_component_id,
               const std::string& field_path,
               const std::string& target_kind,
               termin::prefab::PrefabOverrideValue value) {
                termin::prefab::PrefabPropertyOverride property_override;
                property_override.source_entity_id = source_entity_id;
                property_override.source_component_id = source_component_id;
                property_override.field_path = field_path;
                property_override.target_kind = target_kind;
                property_override.value = std::move(value);
                std::string error;
                if (!self.set_property_override(std::move(property_override), error)) {
                    throw nb::value_error(error.c_str());
                }
            },
            nb::arg("source_entity_id"),
            nb::arg("source_component_id"),
            nb::arg("field_path"),
            nb::arg("target_kind"),
            nb::arg("value")
        )
        .def(
            "get_property_override",
            [](const termin::prefab::PrefabInstanceState& self,
               const std::string& source_entity_id,
               const std::string& source_component_id,
               const std::string& field_path) -> nb::object {
                const auto* found = self.property_override(
                    source_entity_id, source_component_id, field_path
                );
                if (found == nullptr) return nb::none();
                return nb::cast(found->value);
            },
            nb::arg("source_entity_id"),
            nb::arg("source_component_id"),
            nb::arg("field_path")
        )
        .def(
            "clear_property_override",
            &termin::prefab::PrefabInstanceState::clear_property_override,
            nb::arg("source"),
            nb::arg("source_entity_id"),
            nb::arg("source_component_id"),
            nb::arg("field_path")
        )
        .def(
            "reconcile_properties",
            [](termin::prefab::PrefabInstanceState& self,
               const termin::prefab::PrefabDocument& source) {
                const PythonBindingResourceResolver resource_resolver;
                return self.reconcile_properties(source, &resource_resolver);
            },
            nb::arg("source")
        )
        .def(
            "reconcile",
            [](termin::prefab::PrefabInstanceState& self,
               const termin::prefab::PrefabDocument& source) {
                const PythonBindingResourceResolver resource_resolver;
                return self.reconcile(source, &resource_resolver);
            },
            nb::arg("source")
        )
        .def(
            "set_structural_override",
            [](termin::prefab::PrefabInstanceState& self,
               termin::prefab::PrefabStructuralOverride item) {
                std::string error;
                if (!self.set_structural_override(std::move(item), error)) {
                    throw nb::value_error(error.c_str());
                }
            },
            nb::arg("structural_override")
        )
        .def(
            "discard_structural_override",
            &termin::prefab::PrefabInstanceState::discard_structural_override,
            nb::arg("kind"),
            nb::arg("source_id")
        )
        .def(
            "clear_all_property_overrides",
            &termin::prefab::PrefabInstanceState::clear_all_property_overrides,
            nb::arg("source")
        )
        .def(
            "discard_property_override",
            &termin::prefab::PrefabInstanceState::discard_property_override,
            nb::arg("source_entity_id"),
            nb::arg("source_component_id"),
            nb::arg("field_path")
        )
        .def(
            "discard_all_property_overrides",
            &termin::prefab::PrefabInstanceState::discard_all_property_overrides
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
