#include <termin/prefab/prefab_override_value.hpp>

#include <charconv>
#include <cmath>
#include <limits>
#include <string_view>
#include <unordered_set>

#include <tcbase/tc_trent_json.hpp>

namespace termin::prefab {
namespace {

constexpr size_t MaxDepth = 64;
constexpr size_t MaxNodes = 100000;
constexpr size_t MaxContainerItems = 100000;

struct ValidationBudget {
    size_t nodes = 0;
};

const tc_value* dict_value(const tc_value* value, const char* key) {
    if (value == nullptr || value->type != TC_VALUE_DICT) {
        return nullptr;
    }
    return tc_value_dict_get(const_cast<tc_value*>(value), key);
}

bool has_only_keys(
    const tc_value* value,
    std::initializer_list<std::string_view> allowed,
    std::string& error
) {
    if (value == nullptr || value->type != TC_VALUE_DICT) {
        error = "expected object";
        return false;
    }
    for (size_t index = 0; index < tc_value_dict_size(value); ++index) {
        const char* key = nullptr;
        tc_value* ignored = tc_value_dict_get_at(const_cast<tc_value*>(value), index, &key);
        (void)ignored;
        bool found = false;
        for (std::string_view candidate : allowed) {
            if (key != nullptr && candidate == key) {
                found = true;
                break;
            }
        }
        if (!found) {
            error = "unexpected field '" + std::string(key != nullptr ? key : "<null>") + "'";
            return false;
        }
    }
    return true;
}

bool require_string(
    const tc_value* object,
    const char* key,
    std::string& result,
    std::string& error,
    bool allow_empty = false
) {
    const tc_value* value = dict_value(object, key);
    if (value == nullptr || value->type != TC_VALUE_STRING || value->data.s == nullptr) {
        error = "field '" + std::string(key) + "' must be a string";
        return false;
    }
    result = value->data.s;
    if (!allow_empty && result.empty()) {
        error = "field '" + std::string(key) + "' must not be empty";
        return false;
    }
    return true;
}

bool parse_int64_string(const std::string& text, int64_t& result) {
    const char* begin = text.data();
    const char* end = begin + text.size();
    auto parsed = std::from_chars(begin, end, result);
    return parsed.ec == std::errc() && parsed.ptr == end &&
        std::to_string(result) == text;
}

bool parse_uint64_string(const std::string& text, uint64_t& result) {
    const char* begin = text.data();
    const char* end = begin + text.size();
    auto parsed = std::from_chars(begin, end, result);
    return parsed.ec == std::errc() && parsed.ptr == end &&
        std::to_string(result) == text;
}

bool parse_finite_double_string(const std::string& text, double& result) {
    const char* begin = text.data();
    const char* end = begin + text.size();
    auto parsed = std::from_chars(begin, end, result, std::chars_format::general);
    return parsed.ec == std::errc() && parsed.ptr == end && std::isfinite(result);
}

bool validate_node(
    const tc_value* node,
    size_t depth,
    ValidationBudget& budget,
    std::string& error
);

bool validate_items(
    const tc_value* items,
    size_t depth,
    ValidationBudget& budget,
    std::string& error
) {
    if (items == nullptr || items->type != TC_VALUE_LIST) {
        error = "field 'items' must be an array";
        return false;
    }
    const size_t count = tc_value_list_size(items);
    if (count > MaxContainerItems) {
        error = "override container exceeds item limit";
        return false;
    }
    for (size_t index = 0; index < count; ++index) {
        const tc_value* item = tc_value_list_get(const_cast<tc_value*>(items), index);
        if (!validate_node(item, depth + 1, budget, error)) {
            error = "items[" + std::to_string(index) + "]: " + error;
            return false;
        }
    }
    return true;
}

bool validate_node(
    const tc_value* node,
    size_t depth,
    ValidationBudget& budget,
    std::string& error
) {
    if (depth > MaxDepth) {
        error = "override value exceeds nesting limit";
        return false;
    }
    if (++budget.nodes > MaxNodes) {
        error = "override value exceeds node limit";
        return false;
    }
    if (node == nullptr || node->type != TC_VALUE_DICT) {
        error = "tagged value node must be an object";
        return false;
    }

    std::string tag;
    if (!require_string(node, "tag", tag, error)) {
        return false;
    }

    if (tag == "none") {
        return has_only_keys(node, {"tag"}, error);
    }
    if (tag == "bool") {
        if (!has_only_keys(node, {"tag", "value"}, error)) return false;
        const tc_value* value = dict_value(node, "value");
        if (value == nullptr || value->type != TC_VALUE_BOOL) {
            error = "bool value must contain a boolean 'value'";
            return false;
        }
        return true;
    }
    if (tag == "int64") {
        if (!has_only_keys(node, {"tag", "value"}, error)) return false;
        std::string text;
        int64_t parsed = 0;
        if (!require_string(node, "value", text, error) || !parse_int64_string(text, parsed)) {
            error = "int64 value must be a canonical signed decimal string";
            return false;
        }
        return true;
    }
    if (tag == "uint64") {
        if (!has_only_keys(node, {"tag", "value"}, error)) return false;
        std::string text;
        uint64_t parsed = 0;
        if (!require_string(node, "value", text, error) || !parse_uint64_string(text, parsed)) {
            error = "uint64 value must be a canonical unsigned decimal string";
            return false;
        }
        return true;
    }
    if (tag == "float64") {
        if (!has_only_keys(node, {"tag", "value"}, error)) return false;
        std::string text;
        double parsed = 0.0;
        if (!require_string(node, "value", text, error) ||
            !parse_finite_double_string(text, parsed)) {
            error = "float64 value must be a finite decimal string";
            return false;
        }
        return true;
    }
    if (tag == "string") {
        if (!has_only_keys(node, {"tag", "value"}, error)) return false;
        std::string ignored;
        return require_string(node, "value", ignored, error, true);
    }
    if (tag == "list" || tag == "tuple") {
        if (!has_only_keys(node, {"tag", "items"}, error)) return false;
        return validate_items(dict_value(node, "items"), depth, budget, error);
    }
    if (tag == "dict") {
        if (!has_only_keys(node, {"tag", "entries"}, error)) return false;
        const tc_value* entries = dict_value(node, "entries");
        if (entries == nullptr || entries->type != TC_VALUE_LIST) {
            error = "dict entries must be an array";
            return false;
        }
        if (tc_value_list_size(entries) > MaxContainerItems) {
            error = "override dictionary exceeds item limit";
            return false;
        }
        std::unordered_set<std::string> keys;
        for (size_t index = 0; index < tc_value_list_size(entries); ++index) {
            const tc_value* entry = tc_value_list_get(const_cast<tc_value*>(entries), index);
            if (!has_only_keys(entry, {"key", "value"}, error)) {
                error = "entries[" + std::to_string(index) + "]: " + error;
                return false;
            }
            std::string key;
            if (!require_string(entry, "key", key, error, true)) return false;
            if (!keys.insert(key).second) {
                error = "duplicate dictionary key '" + key + "'";
                return false;
            }
            if (!validate_node(dict_value(entry, "value"), depth + 1, budget, error)) {
                error = "entry '" + key + "': " + error;
                return false;
            }
        }
        return true;
    }
    if (tag == "array") {
        if (!has_only_keys(node, {"tag", "dtype", "shape", "items"}, error)) return false;
        std::string dtype;
        if (!require_string(node, "dtype", dtype, error)) return false;
        static const std::unordered_set<std::string> supported = {
            "bool", "int8", "int16", "int32", "int64",
            "uint8", "uint16", "uint32", "uint64", "float32", "float64"
        };
        if (!supported.contains(dtype)) {
            error = "unsupported dense array dtype '" + dtype + "'";
            return false;
        }
        const tc_value* shape = dict_value(node, "shape");
        const tc_value* items = dict_value(node, "items");
        if (shape == nullptr || shape->type != TC_VALUE_LIST ||
            items == nullptr || items->type != TC_VALUE_LIST) {
            error = "array shape and items must be arrays";
            return false;
        }
        size_t product = 1;
        for (size_t index = 0; index < tc_value_list_size(shape); ++index) {
            const tc_value* dimension = tc_value_list_get(const_cast<tc_value*>(shape), index);
            if (dimension == nullptr || dimension->type != TC_VALUE_INT || dimension->data.i < 0) {
                error = "array dimensions must be non-negative integers";
                return false;
            }
            const size_t size = static_cast<size_t>(dimension->data.i);
            if (size != 0 && product > MaxContainerItems / size) {
                error = "array shape exceeds item limit";
                return false;
            }
            product *= size;
        }
        if (product != tc_value_list_size(items)) {
            error = "array shape product does not match item count";
            return false;
        }
        if (!validate_items(items, depth, budget, error)) return false;
        const bool is_bool = dtype == "bool";
        const bool is_signed = dtype.starts_with("int");
        const bool is_unsigned = dtype.starts_with("uint");
        for (size_t index = 0; index < tc_value_list_size(items); ++index) {
            const tc_value* item = tc_value_list_get(const_cast<tc_value*>(items), index);
            std::string item_tag;
            if (!require_string(item, "tag", item_tag, error)) return false;
            bool compatible = false;
            if (is_bool) {
                compatible = item_tag == "bool";
            } else if (is_signed) {
                compatible = item_tag == "int64";
            } else if (is_unsigned) {
                compatible = item_tag == "uint64";
                if (item_tag == "int64") {
                    int64_t signed_value = 0;
                    parse_int64_string(dict_value(item, "value")->data.s, signed_value);
                    compatible = signed_value >= 0;
                }
            } else {
                compatible = item_tag == "float64" || item_tag == "int64" ||
                    item_tag == "uint64";
            }
            if (!compatible) {
                error = "array item " + std::to_string(index) +
                    " is incompatible with dtype '" + dtype + "'";
                return false;
            }
        }
        return true;
    }
    if (tag == "kind") {
        if (!has_only_keys(node, {"tag", "kind", "payload"}, error)) return false;
        std::string kind;
        if (!require_string(node, "kind", kind, error)) return false;
        return validate_node(dict_value(node, "payload"), depth + 1, budget, error);
    }
    if (tag == "resource") {
        if (!has_only_keys(node, {"tag", "resource_type", "kind", "uuid", "name"}, error)) {
            return false;
        }
        std::string ignored;
        if (!require_string(node, "resource_type", ignored, error) ||
            !require_string(node, "kind", ignored, error) ||
            !require_string(node, "uuid", ignored, error)) {
            return false;
        }
        const tc_value* name = dict_value(node, "name");
        if (name != nullptr && (name->type != TC_VALUE_STRING || name->data.s == nullptr)) {
            error = "resource name must be a string when present";
            return false;
        }
        return true;
    }

    error = "unknown override value tag '" + tag + "'";
    return false;
}

std::optional<tc::trent> materialize_node(const tc_value* node, std::string& error) {
    std::string tag;
    if (!require_string(node, "tag", tag, error)) return std::nullopt;
    if (tag == "none") return tc::trent::nil();
    if (tag == "bool") return tc::trent::boolean(dict_value(node, "value")->data.b);
    if (tag == "int64") {
        int64_t value = 0;
        parse_int64_string(dict_value(node, "value")->data.s, value);
        return tc::trent::integer(value);
    }
    if (tag == "uint64") {
        uint64_t value = 0;
        parse_uint64_string(dict_value(node, "value")->data.s, value);
        // tc_value has no unsigned integer variant. Keep the exact decimal
        // representation for target kinds that accept the full uint64 range.
        return tc::trent::string(std::to_string(value));
    }
    if (tag == "float64") {
        double value = 0.0;
        parse_finite_double_string(dict_value(node, "value")->data.s, value);
        return tc::trent::numer(value);
    }
    if (tag == "string") return tc::trent::string(dict_value(node, "value")->data.s);
    if (tag == "list" || tag == "tuple" || tag == "array") {
        tc::trent result = tc::trent::list();
        const tc_value* items = dict_value(node, "items");
        for (size_t index = 0; index < tc_value_list_size(items); ++index) {
            auto child = materialize_node(
                tc_value_list_get(const_cast<tc_value*>(items), index), error
            );
            if (!child) return std::nullopt;
            result.push_back(std::move(*child));
        }
        return result;
    }
    if (tag == "dict") {
        tc::trent result = tc::trent::dict();
        const tc_value* entries = dict_value(node, "entries");
        for (size_t index = 0; index < tc_value_list_size(entries); ++index) {
            const tc_value* entry = tc_value_list_get(const_cast<tc_value*>(entries), index);
            auto child = materialize_node(dict_value(entry, "value"), error);
            if (!child) return std::nullopt;
            result.set(dict_value(entry, "key")->data.s, std::move(*child));
        }
        return result;
    }
    if (tag == "kind") return materialize_node(dict_value(node, "payload"), error);
    if (tag == "resource") {
        tc::trent result = tc::trent::dict();
        result.set("uuid", dict_value(node, "uuid")->data.s);
        const tc_value* name = dict_value(node, "name");
        if (name != nullptr) result.set("name", name->data.s);
        return result;
    }
    error = "cannot materialize override tag '" + tag + "'";
    return std::nullopt;
}

std::optional<tc::trent> encode_inspect_node(
    const tc_value* value,
    size_t depth,
    std::string& error
) {
    if (value == nullptr || depth > MaxDepth) {
        error = value == nullptr ? "inspect override value is null"
                                 : "inspect override value exceeds nesting limit";
        return std::nullopt;
    }
    tc::trent node = tc::trent::dict();
    switch (value->type) {
    case TC_VALUE_NIL:
        node.set("tag", "none");
        return node;
    case TC_VALUE_BOOL:
        node.set("tag", "bool");
        node.set("value", value->data.b);
        return node;
    case TC_VALUE_INT:
        node.set("tag", "int64");
        node.set("value", std::to_string(value->data.i));
        return node;
    case TC_VALUE_FLOAT:
    case TC_VALUE_DOUBLE: {
        const double number = value->type == TC_VALUE_FLOAT
            ? static_cast<double>(value->data.f) : value->data.d;
        if (!std::isfinite(number)) {
            error = "inspect override floats must be finite";
            return std::nullopt;
        }
        char buffer[64];
        auto formatted = std::to_chars(
            buffer, buffer + sizeof(buffer), number,
            std::chars_format::general, std::numeric_limits<double>::max_digits10);
        if (formatted.ec != std::errc()) {
            error = "failed to encode inspect override float";
            return std::nullopt;
        }
        node.set("tag", "float64");
        node.set("value", std::string(buffer, formatted.ptr));
        return node;
    }
    case TC_VALUE_STRING:
        if (value->data.s == nullptr) {
            error = "inspect override string is null";
            return std::nullopt;
        }
        node.set("tag", "string");
        node.set("value", value->data.s);
        return node;
    case TC_VALUE_LIST: {
        node.set("tag", "list");
        tc::trent items = tc::trent::list();
        if (value->data.list.count > MaxContainerItems) {
            error = "inspect override list exceeds item limit";
            return std::nullopt;
        }
        for (size_t index = 0; index < value->data.list.count; ++index) {
            auto item = encode_inspect_node(&value->data.list.items[index], depth + 1, error);
            if (!item) return std::nullopt;
            items.push_back(std::move(*item));
        }
        node.set("items", std::move(items));
        return node;
    }
    case TC_VALUE_DICT: {
        node.set("tag", "dict");
        tc::trent entries = tc::trent::list();
        if (value->data.dict.count > MaxContainerItems) {
            error = "inspect override dictionary exceeds item limit";
            return std::nullopt;
        }
        for (size_t index = 0; index < value->data.dict.count; ++index) {
            const char* key = nullptr;
            tc_value* child = tc_value_dict_get_at(
                const_cast<tc_value*>(value), index, &key);
            if (key == nullptr || child == nullptr) {
                error = "inspect override dictionary contains an invalid entry";
                return std::nullopt;
            }
            auto encoded = encode_inspect_node(child, depth + 1, error);
            if (!encoded) return std::nullopt;
            tc::trent entry = tc::trent::dict();
            entry.set("key", key);
            entry.set("value", std::move(*encoded));
            entries.push_back(std::move(entry));
        }
        node.set("entries", std::move(entries));
        return node;
    }
    default:
        error = "unsupported tc_value type for prefab override";
        return std::nullopt;
    }
}

} // namespace

PrefabOverrideValue::PrefabOverrideValue()
    : _encoded(tc::trent::dict()) {
    _encoded.set("schema", Schema);
    _encoded.set("version", Version);
    tc::trent node = tc::trent::dict();
    node.set("tag", "none");
    _encoded.set("value", std::move(node));
}

PrefabOverrideValue::PrefabOverrideValue(tc::trent encoded)
    : _encoded(std::move(encoded))
{}

std::optional<PrefabOverrideValue> PrefabOverrideValue::parse(
    const tc_value* encoded,
    std::string& error
) {
    error.clear();
    if (encoded == nullptr || encoded->type != TC_VALUE_DICT) {
        error = "override value envelope must be an object";
        return std::nullopt;
    }
    if (!has_only_keys(encoded, {"schema", "version", "value"}, error)) {
        return std::nullopt;
    }
    std::string schema;
    if (!require_string(encoded, "schema", schema, error) || schema != Schema) {
        error = "unsupported override value schema";
        return std::nullopt;
    }
    const tc_value* version = dict_value(encoded, "version");
    if (version == nullptr || version->type != TC_VALUE_INT || version->data.i != Version) {
        error = "unsupported override value version";
        return std::nullopt;
    }
    ValidationBudget budget;
    if (!validate_node(dict_value(encoded, "value"), 0, budget, error)) {
        return std::nullopt;
    }
    return PrefabOverrideValue(tc::trent::copy_of(encoded));
}

std::optional<PrefabOverrideValue> PrefabOverrideValue::parse_json(
    const std::string& json,
    std::string& error
) {
    try {
        tc::trent encoded = tc::json::parse(json);
        return parse(encoded.raw(), error);
    } catch (const std::exception& exception) {
        error = std::string("invalid override value JSON: ") + exception.what();
        return std::nullopt;
    }
}

std::optional<PrefabOverrideValue> PrefabOverrideValue::from_inspect_value(
    const tc_value* value,
    std::string_view target_kind,
    std::string& error
) {
    error.clear();
    if (target_kind.empty()) {
        error = "target inspect kind must not be empty";
        return std::nullopt;
    }
    auto payload = encode_inspect_node(value, 0, error);
    if (!payload) return std::nullopt;
    tc::trent semantic = tc::trent::dict();
    semantic.set("tag", "kind");
    semantic.set("kind", std::string(target_kind));
    semantic.set("payload", std::move(*payload));
    tc::trent envelope = tc::trent::dict();
    envelope.set("schema", Schema);
    envelope.set("version", Version);
    envelope.set("value", std::move(semantic));
    ValidationBudget budget;
    if (!validate_node(envelope.get("value").raw(), 0, budget, error)) {
        return std::nullopt;
    }
    return PrefabOverrideValue(std::move(envelope));
}

tc_value PrefabOverrideValue::serialize() const {
    return tc_value_copy(_encoded.raw());
}

std::string PrefabOverrideValue::to_json(int indent) const {
    return tc::json::dump(_encoded, indent);
}

std::string PrefabOverrideValue::tag() const {
    return _encoded.get("value").get("tag").as_string();
}

std::optional<tc::trent> PrefabOverrideValue::materialize_for_inspect(
    std::string_view target_kind,
    std::string& error
) const {
    error.clear();
    const tc_value* node = _encoded.get("value").raw();
    const std::string node_tag = tag();
    if (node_tag == "kind" || node_tag == "resource") {
        const tc_value* stored_kind = dict_value(node, "kind");
        if (target_kind.empty() || stored_kind == nullptr || stored_kind->data.s == nullptr ||
            target_kind != stored_kind->data.s) {
            error = "override kind does not match target inspect kind";
            return std::nullopt;
        }
    }
    if (node_tag == "resource") {
        error = "resource override requires an explicit native resource resolver";
        return std::nullopt;
    }
    return materialize_node(node, error);
}

std::optional<tc::trent> PrefabOverrideValue::materialize_for_inspect(
    std::string_view target_kind,
    const PrefabOverrideResourceResolver& resource_resolver,
    std::string& error
) const {
    error.clear();
    const tc_value* node = _encoded.get("value").raw();
    if (tag() != "resource") {
        return materialize_for_inspect(target_kind, error);
    }
    const std::string stored_kind = dict_value(node, "kind")->data.s;
    if (target_kind.empty() || target_kind != stored_kind) {
        error = "override kind does not match target inspect kind";
        return std::nullopt;
    }
    const tc_value* name = dict_value(node, "name");
    tc::trent result;
    if (!resource_resolver.resolve(
            dict_value(node, "resource_type")->data.s,
            stored_kind,
            dict_value(node, "uuid")->data.s,
            name != nullptr ? std::string_view(name->data.s) : std::string_view(),
            result,
            error
        )) {
        if (error.empty()) error = "resource resolver rejected prefab override resource";
        return std::nullopt;
    }
    return result;
}

} // namespace termin::prefab
