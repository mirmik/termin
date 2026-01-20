// tc_kind_cpp.cpp - KindRegistryCpp singleton and C++ language vtable registration
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
// C++ language vtable callbacks for C dispatcher
// ============================================================================

static bool cpp_has(const char* kind_name, void* ctx) {
    (void)ctx;
    return KindRegistryCpp::instance().has(kind_name);
}

static tc_value cpp_serialize(const char* kind_name, const tc_value* input, void* ctx) {
    (void)ctx;
    // For C++ kinds, actual serialization is done via KindRegistryCpp::serialize()
    // which works with std::any. This callback is pass-through since the value
    // is already serialized by the time it reaches the C API.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static tc_value cpp_deserialize(const char* kind_name, const tc_value* input, tc_scene* scene, void* ctx) {
    (void)ctx;
    (void)scene;
    // For C++ kinds, actual deserialization is done via KindRegistryCpp::deserialize()
    // which works with std::any. This callback is pass-through.
    if (!input) return tc_value_nil();
    return tc_value_copy(input);
}

static size_t cpp_list(const char** out_names, size_t max_count, void* ctx) {
    (void)ctx;
    auto kinds = KindRegistryCpp::instance().kinds();
    size_t count = std::min(kinds.size(), max_count);
    if (out_names) {
        // Note: returning pointers to temporary strings is unsafe for this API
        // For now, we just return the count. Caller should use KindRegistryCpp::kinds() directly.
    }
    return kinds.size();
}

static bool g_cpp_vtable_initialized = false;

static void init_cpp_lang_vtable() {
    if (g_cpp_vtable_initialized) return;
    g_cpp_vtable_initialized = true;

    static tc_kind_lang_registry cpp_registry = {
        cpp_has,
        cpp_serialize,
        cpp_deserialize,
        cpp_list,
        nullptr
    };

    tc_kind_set_lang_registry(TC_KIND_LANG_CPP, &cpp_registry);
}

// ============================================================================
// Singleton
// ============================================================================

KindRegistryCpp& KindRegistryCpp::instance() {
    static KindRegistryCpp inst;

    // Ensure vtable is registered on first access
    init_cpp_lang_vtable();

    return inst;
}

} // namespace tc
