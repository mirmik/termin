#pragma once

extern "C" {
#include <termin/navmesh/tc_navmesh_registry.h>
#include <tcbase/tc_log.h>
#include <tcbase/tc_value.h>
}

#include <cstring>
#include <string>

namespace termin {

class TcNavMesh {
public:
    tc_navmesh_handle handle = tc_navmesh_handle_invalid();

    TcNavMesh() = default;

    explicit TcNavMesh(tc_navmesh_handle h) : handle(h) {
        if (tc_navmesh* navmesh = tc_navmesh_get(handle)) {
            tc_navmesh_add_ref(navmesh);
        }
    }

    explicit TcNavMesh(tc_navmesh* navmesh) {
        if (navmesh) {
            handle = tc_navmesh_find(navmesh->uuid);
            tc_navmesh_add_ref(navmesh);
        }
    }

    TcNavMesh(const TcNavMesh& other) : handle(other.handle) {
        if (tc_navmesh* navmesh = tc_navmesh_get(handle)) {
            tc_navmesh_add_ref(navmesh);
        }
    }

    TcNavMesh(TcNavMesh&& other) noexcept : handle(other.handle) {
        other.handle = tc_navmesh_handle_invalid();
    }

    TcNavMesh& operator=(const TcNavMesh& other) {
        if (this != &other) {
            if (tc_navmesh* navmesh = tc_navmesh_get(handle)) {
                tc_navmesh_release(navmesh);
            }
            handle = other.handle;
            if (tc_navmesh* navmesh = tc_navmesh_get(handle)) {
                tc_navmesh_add_ref(navmesh);
            }
        }
        return *this;
    }

    TcNavMesh& operator=(TcNavMesh&& other) noexcept {
        if (this != &other) {
            if (tc_navmesh* navmesh = tc_navmesh_get(handle)) {
                tc_navmesh_release(navmesh);
            }
            handle = other.handle;
            other.handle = tc_navmesh_handle_invalid();
        }
        return *this;
    }

    ~TcNavMesh() {
        if (tc_navmesh* navmesh = tc_navmesh_get(handle)) {
            tc_navmesh_release(navmesh);
        }
        handle = tc_navmesh_handle_invalid();
    }

    tc_navmesh* get() const { return tc_navmesh_get(handle); }
    bool is_valid() const { return tc_navmesh_is_valid(handle); }
    bool is_loaded() const { return tc_navmesh_is_loaded(handle); }
    bool ensure_loaded() const { return tc_navmesh_ensure_loaded(handle); }

    const char* uuid() const {
        tc_navmesh* navmesh = get();
        return navmesh ? navmesh->uuid : "";
    }

    const char* name() const {
        tc_navmesh* navmesh = get();
        return navmesh && navmesh->name ? navmesh->name : "";
    }

    uint32_t version() const {
        tc_navmesh* navmesh = get();
        return navmesh ? navmesh->version : 0;
    }

    tc_value serialize_to_value() const {
        tc_value d = tc_value_dict_new();
        if (!is_valid()) {
            tc_value_dict_set(&d, "type", tc_value_string("none"));
            return d;
        }
        tc_value_dict_set(&d, "uuid", tc_value_string(uuid()));
        tc_value_dict_set(&d, "name", tc_value_string(name()));
        tc_value_dict_set(&d, "type", tc_value_string("uuid"));
        return d;
    }

    void deserialize_from(const tc_value* data, void* = nullptr) {
        if (tc_navmesh* navmesh = tc_navmesh_get(handle)) {
            tc_navmesh_release(navmesh);
        }
        handle = tc_navmesh_handle_invalid();

        if (!data) return;

        if (data->type == TC_VALUE_STRING && data->data.s && data->data.s[0]) {
            const char* navmesh_name = data->data.s;
            if (std::strcmp(navmesh_name, "(None)") == 0) return;

            tc_navmesh_handle h = tc_navmesh_find_by_name(navmesh_name);
            if (!tc_navmesh_handle_is_invalid(h)) {
                handle = h;
                if (tc_navmesh* navmesh = tc_navmesh_get(handle)) {
                    tc_navmesh_add_ref(navmesh);
                }
            } else {
                tc_log_error("[TcNavMesh] NavMesh '%s' not found", navmesh_name);
            }
            return;
        }

        if (data->type != TC_VALUE_DICT) return;

        tc_value* uuid_val = tc_value_dict_get(const_cast<tc_value*>(data), "uuid");
        if (uuid_val && uuid_val->type == TC_VALUE_STRING && uuid_val->data.s) {
            tc_navmesh_handle h = tc_navmesh_find(uuid_val->data.s);
            if (!tc_navmesh_handle_is_invalid(h)) {
                handle = h;
                if (tc_navmesh* navmesh = tc_navmesh_get(handle)) {
                    tc_navmesh_add_ref(navmesh);
                }
                ensure_loaded();
                return;
            }
        }

        tc_value* name_val = tc_value_dict_get(const_cast<tc_value*>(data), "name");
        if (name_val && name_val->type == TC_VALUE_STRING && name_val->data.s) {
            const char* navmesh_name = name_val->data.s;
            tc_navmesh_handle h = tc_navmesh_find_by_name(navmesh_name);
            if (!tc_navmesh_handle_is_invalid(h)) {
                handle = h;
                if (tc_navmesh* navmesh = tc_navmesh_get(handle)) {
                    tc_navmesh_add_ref(navmesh);
                }
                ensure_loaded();
            } else {
                tc_log_error("[TcNavMesh] NavMesh '%s' not found", navmesh_name);
            }
        }
    }

    static TcNavMesh from_uuid(const std::string& uuid) {
        tc_navmesh_handle h = tc_navmesh_find(uuid.c_str());
        return tc_navmesh_handle_is_invalid(h) ? TcNavMesh() : TcNavMesh(h);
    }

    static TcNavMesh from_name(const std::string& name) {
        tc_navmesh_handle h = tc_navmesh_find_by_name(name.c_str());
        return tc_navmesh_handle_is_invalid(h) ? TcNavMesh() : TcNavMesh(h);
    }

    static TcNavMesh get_or_create(const std::string& uuid) {
        tc_navmesh_handle h = tc_navmesh_get_or_create(uuid.c_str());
        return tc_navmesh_handle_is_invalid(h) ? TcNavMesh() : TcNavMesh(h);
    }

    static TcNavMesh declare(const std::string& uuid, const std::string& name = "") {
        tc_navmesh_handle h = tc_navmesh_declare(uuid.c_str(), name.empty() ? nullptr : name.c_str());
        return tc_navmesh_handle_is_invalid(h) ? TcNavMesh() : TcNavMesh(h);
    }
};

} // namespace termin
