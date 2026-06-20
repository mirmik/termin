#pragma once

extern "C" {
#include "termin/voxels/tc_voxel_grid_registry.h"
}

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
