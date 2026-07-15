#include <cassert>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <string>

#include <termin/prefab/prefab_override_value.hpp>

using termin::prefab::PrefabOverrideValue;

namespace {

class TestResourceResolver final
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
        if (resource_type != "mesh" || target_kind != "tc_mesh" || uuid != "mesh-uuid") {
            error = "missing test resource";
            return false;
        }
        result = tc::trent::dict();
        result.set("uuid", std::string(uuid));
        result.set("name", std::string(display_name));
        return true;
    }
};

PrefabOverrideValue parse_ok(const std::string& value_json) {
    const std::string document =
        R"({"schema":"termin.prefab.override-value","version":1,"value":)" +
        value_json + "}";
    std::string error;
    auto value = PrefabOverrideValue::parse_json(document, error);
    if (!value) {
        std::cerr << "Unexpected parse failure: " << error << '\n';
        std::abort();
    }
    return std::move(*value);
}

void parse_fails(const std::string& document, const std::string& message_part) {
    std::string error;
    auto value = PrefabOverrideValue::parse_json(document, error);
    assert(!value.has_value());
    assert(error.find(message_part) != std::string::npos);
}

void test_scalar_round_trip_and_materialization() {
    PrefabOverrideValue none = parse_ok(R"({"tag":"none"})");
    assert(none.tag() == "none");
    std::string error;
    auto none_value = none.materialize_for_inspect("optional", error);
    assert(none_value && none_value->raw_type() == TC_VALUE_NIL);

    PrefabOverrideValue boolean = parse_ok(R"({"tag":"bool","value":true})");
    auto bool_value = boolean.materialize_for_inspect("bool", error);
    assert(bool_value && bool_value->raw_type() == TC_VALUE_BOOL && bool_value->as_bool());

    PrefabOverrideValue integer = parse_ok(
        R"({"tag":"int64","value":"9223372036854775807"})"
    );
    auto int_value = integer.materialize_for_inspect("int", error);
    assert(int_value && int_value->raw_type() == TC_VALUE_INT);
    assert(int_value->as_integer() == std::numeric_limits<int64_t>::max());

    PrefabOverrideValue number = parse_ok(
        R"({"tag":"float64","value":"1.2345678901234567"})"
    );
    auto float_value = number.materialize_for_inspect("double", error);
    assert(float_value && float_value->raw_type() == TC_VALUE_DOUBLE);
    assert(float_value->as_numer() == 1.2345678901234567);

    PrefabOverrideValue unsigned_integer = parse_ok(
        R"({"tag":"uint64","value":"18446744073709551615"})"
    );
    auto uint_value = unsigned_integer.materialize_for_inspect("uint64", error);
    assert(uint_value && uint_value->raw_type() == TC_VALUE_STRING);
    assert(uint_value->as_string() == "18446744073709551615");

    PrefabOverrideValue string = parse_ok(R"({"tag":"string","value":"hello"})");
    auto string_value = string.materialize_for_inspect("string", error);
    assert(string_value && string_value->as_string() == "hello");

    std::string round_trip_error;
    auto round_trip = PrefabOverrideValue::parse_json(integer.to_json(), round_trip_error);
    assert(round_trip && round_trip->to_json() == integer.to_json());
}

void test_container_identity_is_explicit() {
    PrefabOverrideValue list = parse_ok(
        R"({"tag":"list","items":[{"tag":"int64","value":"1"},{"tag":"int64","value":"2"},{"tag":"int64","value":"3"}]})"
    );
    PrefabOverrideValue tuple = parse_ok(
        R"({"tag":"tuple","items":[{"tag":"int64","value":"1"},{"tag":"int64","value":"2"},{"tag":"int64","value":"3"}]})"
    );
    assert(list.tag() == "list");
    assert(tuple.tag() == "tuple");

    std::string error;
    auto materialized = list.materialize_for_inspect("list[int]", error);
    assert(materialized && materialized->raw_type() == TC_VALUE_LIST);
    assert(materialized->size() == 3);

    PrefabOverrideValue dict = parse_ok(
        R"({"tag":"dict","entries":[{"key":"x","value":{"tag":"bool","value":true}},{"key":"y","value":{"tag":"string","value":"v"}}]})"
    );
    auto dict_value = dict.materialize_for_inspect("dict", error);
    assert(dict_value && dict_value->raw_type() == TC_VALUE_DICT);
    assert(dict_value->get("x").as_bool());
    assert(dict_value->get("y").as_string() == "v");
}

void test_dense_array_is_not_inferred_from_list() {
    PrefabOverrideValue array = parse_ok(
        R"({"tag":"array","dtype":"float32","shape":[2,2],"items":[{"tag":"float64","value":"1"},{"tag":"float64","value":"2"},{"tag":"float64","value":"3"},{"tag":"float64","value":"4"}]})"
    );
    assert(array.tag() == "array");
    std::string error;
    auto values = array.materialize_for_inspect("ndarray", error);
    assert(values && values->raw_type() == TC_VALUE_LIST && values->size() == 4);

    PrefabOverrideValue numeric_list = parse_ok(
        R"({"tag":"list","items":[{"tag":"float64","value":"1"},{"tag":"float64","value":"2"}]})"
    );
    assert(numeric_list.tag() == "list");
}

void test_kind_and_resource_contracts() {
    PrefabOverrideValue vector = parse_ok(
        R"({"tag":"kind","kind":"vec3","payload":{"tag":"list","items":[{"tag":"float64","value":"1"},{"tag":"float64","value":"2"},{"tag":"float64","value":"3"}]}})"
    );
    std::string error;
    assert(!vector.materialize_for_inspect("quat", error));
    assert(error.find("does not match") != std::string::npos);
    auto vector_value = vector.materialize_for_inspect("vec3", error);
    assert(vector_value && vector_value->size() == 3);

    PrefabOverrideValue resource = parse_ok(
        R"({"tag":"resource","resource_type":"mesh","kind":"tc_mesh","uuid":"mesh-uuid","name":"Cube"})"
    );
    assert(!resource.materialize_for_inspect("tc_material", error));
    assert(!resource.materialize_for_inspect("tc_mesh", error));
    assert(error.find("resolver") != std::string::npos);
    TestResourceResolver resolver;
    auto resource_value = resource.materialize_for_inspect("tc_mesh", resolver, error);
    assert(resource_value);
    assert(resource_value->get("uuid").as_string() == "mesh-uuid");
    assert(resource_value->get("name").as_string() == "Cube");
}

void test_native_inspect_value_factory() {
    tc_value vector = tc_value_list_new();
    tc_value_list_push(&vector, tc_value_double(1.0));
    tc_value_list_push(&vector, tc_value_double(2.0));
    tc_value_list_push(&vector, tc_value_double(3.0));
    std::string error;
    auto encoded = PrefabOverrideValue::from_inspect_value(&vector, "vec3", error);
    tc_value_free(&vector);
    assert(encoded && encoded->tag() == "kind");
    auto materialized = encoded->materialize_for_inspect("vec3", error);
    assert(materialized && materialized->size() == 3);
    assert(materialized->at(0).as_numer() == 1.0);
    assert(!encoded->materialize_for_inspect("quat", error));

    tc_value nested = tc_value_dict_new();
    tc_value_dict_set(&nested, "enabled", tc_value_bool(true));
    tc_value_dict_set(&nested, "name", tc_value_string("native"));
    auto nested_encoded = PrefabOverrideValue::from_inspect_value(
        &nested, "settings", error);
    tc_value_free(&nested);
    assert(nested_encoded);
    auto nested_value = nested_encoded->materialize_for_inspect("settings", error);
    assert(nested_value && nested_value->get("enabled").as_bool());
    assert(nested_value->get("name").as_string() == "native");
}

void test_malformed_values_are_rejected() {
    const std::string prefix =
        R"({"schema":"termin.prefab.override-value","version":1,"value":)";
    parse_fails(
        R"({"schema":"termin.prefab.override-value","version":2,"value":{"tag":"none"}})",
        "version"
    );
    parse_fails(prefix + R"({"tag":"wat"}})", "unknown");
    parse_fails(prefix + R"({"tag":"none","value":1}})", "unexpected");
    parse_fails(prefix + R"({"tag":"int64","value":"01"}})", "canonical");
    parse_fails(prefix + R"({"tag":"int64","value":"9223372036854775808"}})", "canonical");
    parse_fails(prefix + R"({"tag":"uint64","value":"-1"}})", "canonical");
    parse_fails(prefix + R"({"tag":"float64","value":"nan"}})", "finite");
    parse_fails(
        prefix + R"({"tag":"dict","entries":[{"key":"x","value":{"tag":"none"}},{"key":"x","value":{"tag":"none"}}]}})",
        "duplicate"
    );
    parse_fails(
        prefix + R"({"tag":"array","dtype":"float32","shape":[2,2],"items":[{"tag":"float64","value":"1"}]}})",
        "shape product"
    );
    parse_fails(
        prefix + R"({"tag":"array","dtype":"complex64","shape":[1],"items":[{"tag":"float64","value":"1"}]}})",
        "dtype"
    );
    parse_fails(
        prefix + R"({"tag":"array","dtype":"int32","shape":[1],"items":[{"tag":"float64","value":"1"}]}})",
        "incompatible"
    );
    parse_fails(
        prefix + R"({"tag":"resource","resource_type":"mesh","kind":"tc_mesh","uuid":""}})",
        "must not be empty"
    );
}

} // namespace

int main() {
    test_scalar_round_trip_and_materialization();
    test_container_identity_is_explicit();
    test_dense_array_is_not_inferred_from_list();
    test_kind_and_resource_contracts();
    test_native_inspect_value_factory();
    test_malformed_values_are_rejected();
    return 0;
}
