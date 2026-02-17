// tc_value_helpers.hpp - tc_value <-> Python conversion helpers
#pragma once

#include <nanobind/nanobind.h>

extern "C" {
#include "tc_value.h"
#include "tc_log.h"
}

namespace nb = nanobind;

namespace termin {

// Convert Python object to tc_value
// Caller owns the returned tc_value and must call tc_value_free on it
inline tc_value py_to_tc_value(nb::object obj) {
    if (obj.is_none()) {
        return tc_value_nil();
    }
    if (nb::isinstance<nb::bool_>(obj)) {
        return tc_value_bool(nb::cast<bool>(obj));
    }
    if (nb::isinstance<nb::int_>(obj)) {
        return tc_value_int(nb::cast<int64_t>(obj));
    }
    if (nb::isinstance<nb::float_>(obj)) {
        return tc_value_double(nb::cast<double>(obj));
    }
    if (nb::isinstance<nb::str>(obj)) {
        return tc_value_string(nb::cast<std::string>(obj).c_str());
    }
    if (nb::isinstance<nb::list>(obj) || nb::isinstance<nb::tuple>(obj)) {
        tc_value result = tc_value_list_new();
        for (auto item : obj) {
            tc_value child = py_to_tc_value(nb::borrow<nb::object>(item));
            tc_value_list_push(&result, child);
            // Note: list_push takes ownership, don't free child
        }
        return result;
    }
    if (nb::isinstance<nb::dict>(obj)) {
        tc_value result = tc_value_dict_new();
        for (auto item : nb::cast<nb::dict>(obj)) {
            std::string key = nb::cast<std::string>(item.first);
            tc_value child = py_to_tc_value(nb::borrow<nb::object>(item.second));
            tc_value_dict_set(&result, key.c_str(), child);
            // Note: dict_set takes ownership, don't free child
        }
        return result;
    }

    // numpy arrays / numpy scalars and similar sequence-like objects
    try {
        return py_to_tc_value(obj.attr("tolist")());
    } catch (const std::exception& e) {
        tc_log(TC_LOG_DEBUG, "[py_to_tc_value] tolist() conversion failed: %s", e.what());
    } catch (...) {
        tc_log(TC_LOG_DEBUG, "[py_to_tc_value] tolist() conversion failed with unknown exception");
    }
    return tc_value_nil();
}

// Convert tc_value to Python object
inline nb::object tc_value_to_py(const tc_value* v) {
    if (!v) return nb::none();

    switch (v->type) {
        case TC_VALUE_NIL:
            return nb::none();
        case TC_VALUE_BOOL:
            return nb::bool_(v->data.b);
        case TC_VALUE_INT:
            return nb::int_(v->data.i);
        case TC_VALUE_FLOAT:
            return nb::float_(static_cast<double>(v->data.f));
        case TC_VALUE_DOUBLE:
            return nb::float_(v->data.d);
        case TC_VALUE_STRING:
            return nb::str(v->data.s ? v->data.s : "");
        case TC_VALUE_VEC3: {
            nb::list result;
            result.append(v->data.v3.x);
            result.append(v->data.v3.y);
            result.append(v->data.v3.z);
            return result;
        }
        case TC_VALUE_QUAT: {
            nb::list result;
            result.append(v->data.q.x);
            result.append(v->data.q.y);
            result.append(v->data.q.z);
            result.append(v->data.q.w);
            return result;
        }
        case TC_VALUE_LIST: {
            nb::list result;
            size_t count = tc_value_list_size(v);
            for (size_t i = 0; i < count; i++) {
                tc_value* item = tc_value_list_get(const_cast<tc_value*>(v), i);
                result.append(tc_value_to_py(item));
            }
            return result;
        }
        case TC_VALUE_DICT: {
            nb::dict result;
            size_t count = tc_value_dict_size(v);
            for (size_t i = 0; i < count; i++) {
                const char* key = nullptr;
                tc_value* val = tc_value_dict_get_at(const_cast<tc_value*>(v), i, &key);
                if (key && val) {
                    result[nb::str(key)] = tc_value_to_py(val);
                }
            }
            return result;
        }
    }
    return nb::none();
}

} // namespace termin
