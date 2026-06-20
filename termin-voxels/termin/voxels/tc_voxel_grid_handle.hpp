#pragma once

extern "C" {
#include "termin/voxels/tc_voxel_grid_registry.h"
#include <tcbase/tc_log.h>
#include <tcbase/tc_value.h>
}

#include "termin/voxels/tc_voxel_grid_payload.hpp"

#include <cstring>
#include <string>

namespace termin {
namespace voxels {

class TcVoxelGrid {
public:
    tc_voxel_grid_handle handle = tc_voxel_grid_handle_invalid();

    TcVoxelGrid() = default;

    explicit TcVoxelGrid(tc_voxel_grid_handle h) : handle(h) {
        if (tc_voxel_grid* grid = tc_voxel_grid_get(handle)) {
            tc_voxel_grid_add_ref(grid);
        }
    }

    explicit TcVoxelGrid(tc_voxel_grid* grid) {
        if (grid) {
            handle = tc_voxel_grid_find(grid->uuid);
            tc_voxel_grid_add_ref(grid);
        }
    }

    TcVoxelGrid(const TcVoxelGrid& other) : handle(other.handle) {
        if (tc_voxel_grid* grid = tc_voxel_grid_get(handle)) {
            tc_voxel_grid_add_ref(grid);
        }
    }

    TcVoxelGrid(TcVoxelGrid&& other) noexcept : handle(other.handle) {
        other.handle = tc_voxel_grid_handle_invalid();
    }

    TcVoxelGrid& operator=(const TcVoxelGrid& other) {
        if (this != &other) {
            if (tc_voxel_grid* grid = tc_voxel_grid_get(handle)) {
                tc_voxel_grid_release(grid);
            }
            handle = other.handle;
            if (tc_voxel_grid* grid = tc_voxel_grid_get(handle)) {
                tc_voxel_grid_add_ref(grid);
            }
        }
        return *this;
    }

    TcVoxelGrid& operator=(TcVoxelGrid&& other) noexcept {
        if (this != &other) {
            if (tc_voxel_grid* grid = tc_voxel_grid_get(handle)) {
                tc_voxel_grid_release(grid);
            }
            handle = other.handle;
            other.handle = tc_voxel_grid_handle_invalid();
        }
        return *this;
    }

    ~TcVoxelGrid() {
        if (tc_voxel_grid* grid = tc_voxel_grid_get(handle)) {
            tc_voxel_grid_release(grid);
        }
        handle = tc_voxel_grid_handle_invalid();
    }

    tc_voxel_grid* get() const { return tc_voxel_grid_get(handle); }
    bool is_valid() const { return tc_voxel_grid_is_valid(handle); }
    bool is_loaded() const { return tc_voxel_grid_is_loaded(handle); }
    bool ensure_loaded() const { return tc_voxel_grid_ensure_loaded(handle); }

    const char* uuid() const {
        tc_voxel_grid* grid = get();
        return grid ? grid->uuid : "";
    }

    const char* name() const {
        tc_voxel_grid* grid = get();
        return grid && grid->name ? grid->name : "";
    }

    const char* source_path() const {
        tc_voxel_grid* grid = get();
        return grid && grid->source_path ? grid->source_path : "";
    }

    uint32_t version() const {
        tc_voxel_grid* grid = get();
        return grid ? grid->version : 0;
    }

    VoxelGrid* grid() const {
        return tc_voxel_grid_payload(handle);
    }

    bool set_grid(const VoxelGrid& payload) const {
        return tc_voxel_grid_set_payload_copy(handle, payload);
    }

    tc_value serialize_to_value() const {
        tc_value d = tc_value_dict_new();
        if (!is_valid()) {
            tc_value_dict_set(&d, "type", tc_value_string("none"));
            return d;
        }
        tc_value_dict_set(&d, "uuid", tc_value_string(uuid()));
        tc_value_dict_set(&d, "name", tc_value_string(name()));
        const char* path = source_path();
        if (path && path[0]) {
            tc_value_dict_set(&d, "type", tc_value_string("path"));
            tc_value_dict_set(&d, "path", tc_value_string(path));
        } else {
            tc_value_dict_set(&d, "type", tc_value_string("uuid"));
        }
        return d;
    }

    void deserialize_from(const tc_value* data, void* = nullptr) {
        if (tc_voxel_grid* grid_data = tc_voxel_grid_get(handle)) {
            tc_voxel_grid_release(grid_data);
        }
        handle = tc_voxel_grid_handle_invalid();

        if (!data) return;

        if (data->type == TC_VALUE_STRING && data->data.s && data->data.s[0]) {
            const char* grid_name = data->data.s;
            if (std::strcmp(grid_name, "(None)") == 0) return;

            tc_voxel_grid_handle h = tc_voxel_grid_find_by_name(grid_name);
            if (!tc_voxel_grid_handle_is_invalid(h)) {
                handle = h;
                if (tc_voxel_grid* grid_data = tc_voxel_grid_get(handle)) {
                    tc_voxel_grid_add_ref(grid_data);
                }
            } else {
                tc_log_error("[TcVoxelGrid] Voxel grid '%s' not found", grid_name);
            }
            return;
        }

        if (data->type != TC_VALUE_DICT) return;

        tc_value* uuid_val = tc_value_dict_get(const_cast<tc_value*>(data), "uuid");
        if (uuid_val && uuid_val->type == TC_VALUE_STRING && uuid_val->data.s) {
            tc_voxel_grid_handle h = tc_voxel_grid_find(uuid_val->data.s);
            if (!tc_voxel_grid_handle_is_invalid(h)) {
                handle = h;
                if (tc_voxel_grid* grid_data = tc_voxel_grid_get(handle)) {
                    tc_voxel_grid_add_ref(grid_data);
                }
                ensure_loaded();
                return;
            }
        }

        tc_value* name_val = tc_value_dict_get(const_cast<tc_value*>(data), "name");
        if (name_val && name_val->type == TC_VALUE_STRING && name_val->data.s) {
            const char* grid_name = name_val->data.s;
            tc_voxel_grid_handle h = tc_voxel_grid_find_by_name(grid_name);
            if (!tc_voxel_grid_handle_is_invalid(h)) {
                handle = h;
                if (tc_voxel_grid* grid_data = tc_voxel_grid_get(handle)) {
                    tc_voxel_grid_add_ref(grid_data);
                }
                ensure_loaded();
            } else {
                tc_log_error("[TcVoxelGrid] Voxel grid '%s' not found", grid_name);
            }
        }
    }

    static TcVoxelGrid from_uuid(const std::string& uuid) {
        tc_voxel_grid_handle h = tc_voxel_grid_find(uuid.c_str());
        return tc_voxel_grid_handle_is_invalid(h) ? TcVoxelGrid() : TcVoxelGrid(h);
    }

    static TcVoxelGrid from_name(const std::string& name) {
        tc_voxel_grid_handle h = tc_voxel_grid_find_by_name(name.c_str());
        return tc_voxel_grid_handle_is_invalid(h) ? TcVoxelGrid() : TcVoxelGrid(h);
    }

    static TcVoxelGrid declare(const std::string& uuid, const std::string& name = "") {
        tc_voxel_grid_handle h = tc_voxel_grid_declare(uuid.c_str(), name.empty() ? nullptr : name.c_str());
        return tc_voxel_grid_handle_is_invalid(h) ? TcVoxelGrid() : TcVoxelGrid(h);
    }
};

} // namespace voxels
} // namespace termin
