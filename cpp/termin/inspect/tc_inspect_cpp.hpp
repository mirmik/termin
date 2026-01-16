// tc_inspect_cpp.hpp - C++ wrapper for tc_inspect with template-based field registration
#pragma once

#include "tc_inspect.h"
#include <string>
#include <type_traits>
#include <cstring>

namespace tc {

// ============================================================================
// Type traits for tc_value conversion
// ============================================================================

template<typename T> struct tc_value_traits;

template<> struct tc_value_traits<bool> {
    static tc_value to_value(bool v) { return tc_value_bool(v); }
    static bool from_value(const tc_value& v) { return v.data.b; }
    static constexpr tc_value_type type = TC_VALUE_BOOL;
    static constexpr const char* kind = "bool";
};

template<> struct tc_value_traits<int> {
    static tc_value to_value(int v) { return tc_value_int(v); }
    static int from_value(const tc_value& v) { return static_cast<int>(v.data.i); }
    static constexpr tc_value_type type = TC_VALUE_INT;
    static constexpr const char* kind = "int";
};

template<> struct tc_value_traits<int64_t> {
    static tc_value to_value(int64_t v) { return tc_value_int(v); }
    static int64_t from_value(const tc_value& v) { return v.data.i; }
    static constexpr tc_value_type type = TC_VALUE_INT;
    static constexpr const char* kind = "int";
};

template<> struct tc_value_traits<float> {
    static tc_value to_value(float v) { return tc_value_float(v); }
    static float from_value(const tc_value& v) { return v.data.f; }
    static constexpr tc_value_type type = TC_VALUE_FLOAT;
    static constexpr const char* kind = "float";
};

template<> struct tc_value_traits<double> {
    static tc_value to_value(double v) { return tc_value_double(v); }
    static double from_value(const tc_value& v) { return v.data.d; }
    static constexpr tc_value_type type = TC_VALUE_DOUBLE;
    static constexpr const char* kind = "double";
};

template<> struct tc_value_traits<std::string> {
    static tc_value to_value(const std::string& v) { return tc_value_string(v.c_str()); }
    static std::string from_value(const tc_value& v) { return v.data.s ? v.data.s : ""; }
    static constexpr tc_value_type type = TC_VALUE_STRING;
    static constexpr const char* kind = "string";
};

template<> struct tc_value_traits<tc_vec3> {
    static tc_value to_value(tc_vec3 v) { return tc_value_vec3(v); }
    static tc_vec3 from_value(const tc_value& v) { return v.data.v3; }
    static constexpr tc_value_type type = TC_VALUE_VEC3;
    static constexpr const char* kind = "vec3";
};

template<> struct tc_value_traits<tc_quat> {
    static tc_value to_value(tc_quat v) { return tc_value_quat(v); }
    static tc_quat from_value(const tc_value& v) { return v.data.q; }
    static constexpr tc_value_type type = TC_VALUE_QUAT;
    static constexpr const char* kind = "quat";
};

// ============================================================================
// Field context - stores member pointer for getter/setter
// ============================================================================

template<typename C, typename T>
struct FieldContext {
    T C::* member;
};

// ============================================================================
// Generic getter/setter that use FieldContext
// ============================================================================

template<typename C, typename T>
static tc_value cpp_field_getter(void* obj, const tc_field_desc* field, void* user_data) {
    (void)field;
    auto* ctx = static_cast<FieldContext<C, T>*>(user_data);
    C* instance = static_cast<C*>(obj);
    return tc_value_traits<T>::to_value(instance->*(ctx->member));
}

template<typename C, typename T>
static void cpp_field_setter(void* obj, const tc_field_desc* field, tc_value value, void* user_data) {
    (void)field;
    if (value.type != tc_value_traits<T>::type) return;
    auto* ctx = static_cast<FieldContext<C, T>*>(user_data);
    C* instance = static_cast<C*>(obj);
    instance->*(ctx->member) = tc_value_traits<T>::from_value(value);
}

// ============================================================================
// InspectCpp - static methods for C++ field registration
// ============================================================================

class InspectCpp {
public:
    // Register a type (if not already registered)
    static void register_type(const char* type_name, const char* base_type = nullptr) {
        if (!tc_inspect_has_type(type_name)) {
            tc_inspect_register_type(type_name, base_type);
        }
    }

    // Register a field using pointer-to-member
    // Note: For types without tc_value_traits, you MUST provide kind explicitly
    template<typename C, typename T>
    static void register_field(
        const char* type_name,
        T C::* member,
        const char* path,
        const char* label,
        const char* kind,  // Required - cannot be nullptr
        double min = 0.0,
        double max = 1.0,
        double step = 0.01,
        bool is_serializable = true,
        bool is_inspectable = true
    ) {
        // Ensure type exists
        register_type(type_name);

        // Create field descriptor
        tc_field_desc desc = {};
        desc.path = path;
        desc.label = label;
        desc.kind = kind;
        desc.min = min;
        desc.max = max;
        desc.step = step;
        desc.is_serializable = is_serializable;
        desc.is_inspectable = is_inspectable;

        // Add field to registry
        tc_inspect_add_field(type_name, &desc);

        // Note: We don't set vtable here for complex types - they use InspectRegistry's
        // C++ getter/setter which work with std::any. The C vtable is for simple types only.
    }

    // Register a field for simple types with tc_value_traits (bool, int, float, etc.)
    // This version sets up the C vtable for direct access
    template<typename C, typename T>
    static void register_simple_field(
        const char* type_name,
        T C::* member,
        const char* path,
        const char* label,
        double min = 0.0,
        double max = 1.0,
        double step = 0.01
    ) {
        // Ensure type exists
        register_type(type_name);

        // Create field descriptor
        tc_field_desc desc = {};
        desc.path = path;
        desc.label = label;
        desc.kind = tc_value_traits<T>::kind;
        desc.min = min;
        desc.max = max;
        desc.step = step;
        desc.is_serializable = true;
        desc.is_inspectable = true;

        tc_inspect_add_field(type_name, &desc);

        // Create context with member pointer (must be static/persistent)
        static thread_local FieldContext<C, T> ctx;
        ctx.member = member;

        // Create vtable
        tc_field_vtable vtable = {};
        vtable.get = cpp_field_getter<C, T>;
        vtable.set = cpp_field_setter<C, T>;
        vtable.user_data = &ctx;

        tc_inspect_set_field_vtable(type_name, path, TC_INSPECT_LANG_CPP, &vtable);
    }
};

// ============================================================================
// Convenience macros
// ============================================================================

// Register a simple field
#define TC_INSPECT_FIELD(type, member, label) \
    tc::InspectCpp::register_field<type>(#type, &type::member, #member, label)

// Register a field with kind
#define TC_INSPECT_FIELD_KIND(type, member, label, kind) \
    tc::InspectCpp::register_field<type>(#type, &type::member, #member, label, kind)

// Register a field with full options
#define TC_INSPECT_FIELD_FULL(type, member, label, kind, min, max, step) \
    tc::InspectCpp::register_field<type>(#type, &type::member, #member, label, kind, min, max, step)

} // namespace tc
