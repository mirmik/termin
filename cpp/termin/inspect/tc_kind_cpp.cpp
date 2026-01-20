// tc_kind_cpp.cpp - KindRegistryCpp singleton implementation
// Compiled into entity_lib to ensure single instance across all modules

#include "tc_kind_cpp.hpp"

extern "C" {
#include "tc_kind.h"
}

namespace tc {

// ============================================================================
// tc_value <-> trent conversion (local to this file)
// ============================================================================

static tc_value trent_to_tc_value(const nos::trent& t) {
    switch (t.get_type()) {
    case nos::trent_type::nil:
        return tc_value_nil();
    case nos::trent_type::boolean:
        return tc_value_bool(t.as_bool());
    case nos::trent_type::numer: {
        double val = t.as_numer();
        if (val == static_cast<int64_t>(val)) {
            return tc_value_int(static_cast<int64_t>(val));
        }
        return tc_value_double(val);
    }
    case nos::trent_type::string:
        return tc_value_string(t.as_string().c_str());
    case nos::trent_type::list: {
        tc_value list = tc_value_list_new();
        for (const auto& item : t.as_list()) {
            tc_value_list_push(&list, trent_to_tc_value(item));
        }
        return list;
    }
    case nos::trent_type::dict: {
        tc_value dict = tc_value_dict_new();
        for (const auto& [key, val] : t.as_dict()) {
            tc_value_dict_set(&dict, key.c_str(), trent_to_tc_value(val));
        }
        return dict;
    }
    default:
        return tc_value_nil();
    }
}

static nos::trent tc_value_to_trent(const tc_value* v) {
    if (!v) return nos::trent::nil();

    switch (v->type) {
    case TC_VALUE_NIL:
        return nos::trent::nil();
    case TC_VALUE_BOOL:
        return nos::trent(v->data.b);
    case TC_VALUE_INT:
        return nos::trent(static_cast<nos::trent::numer_type>(v->data.i));
    case TC_VALUE_FLOAT:
        return nos::trent(static_cast<nos::trent::numer_type>(v->data.f));
    case TC_VALUE_DOUBLE:
        return nos::trent(static_cast<nos::trent::numer_type>(v->data.d));
    case TC_VALUE_STRING:
        return v->data.s ? nos::trent(std::string(v->data.s)) : nos::trent::nil();
    case TC_VALUE_VEC3: {
        nos::trent list;
        list.init(nos::trent_type::list);
        list.push_back(nos::trent(v->data.v3.x));
        list.push_back(nos::trent(v->data.v3.y));
        list.push_back(nos::trent(v->data.v3.z));
        return list;
    }
    case TC_VALUE_QUAT: {
        nos::trent list;
        list.init(nos::trent_type::list);
        list.push_back(nos::trent(v->data.q.x));
        list.push_back(nos::trent(v->data.q.y));
        list.push_back(nos::trent(v->data.q.z));
        list.push_back(nos::trent(v->data.q.w));
        return list;
    }
    case TC_VALUE_LIST: {
        nos::trent list;
        list.init(nos::trent_type::list);
        for (size_t i = 0; i < v->data.list.count; i++) {
            list.push_back(tc_value_to_trent(&v->data.list.items[i]));
        }
        return list;
    }
    case TC_VALUE_DICT: {
        nos::trent dict;
        dict.init(nos::trent_type::dict);
        for (size_t i = 0; i < v->data.dict.count; i++) {
            dict[v->data.dict.entries[i].key] =
                tc_value_to_trent(v->data.dict.entries[i].value);
        }
        return dict;
    }
    default:
        return nos::trent::nil();
    }
}

// ============================================================================
// C++ callbacks for C kind registry
// ============================================================================

static tc_value cpp_kind_serialize_callback(const char* kind_name, const tc_value* input) {
    (void)kind_name;
    // For C++ kinds, the getter already returns serialized tc_value (via KindRegistry::serialize_cpp).
    // This callback is called by tc_kind_serialize_any, but the value is already serialized.
    // Just pass through the input.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static tc_value cpp_kind_deserialize_callback(const char* kind_name, const tc_value* input, tc_scene* scene) {
    (void)kind_name;
    (void)scene;
    // For C++ kinds, the setter (cpp_field_setter_via_kind) handles deserialization itself
    // by calling KindRegistry::deserialize_cpp(). This callback just needs to pass through
    // the serialized tc_value so tc_kind_deserialize_any returns non-NIL.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static bool g_cpp_callbacks_initialized = false;

void init_cpp_kind_callbacks() {
    if (g_cpp_callbacks_initialized) return;
    g_cpp_callbacks_initialized = true;

    tc_kind_set_cpp_callbacks(
        cpp_kind_serialize_callback,
        cpp_kind_deserialize_callback
    );
}

// ============================================================================
// Singleton
// ============================================================================

KindRegistryCpp& KindRegistryCpp::instance() {
    static KindRegistryCpp inst;

    // Ensure callbacks are initialized
    init_cpp_kind_callbacks();

    return inst;
}

} // namespace tc
