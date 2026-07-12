#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

#include "termin/voxels/voxel_chunk.hpp"
#include <termin/geom/vec3.hpp>

namespace termin::voxels {

struct ChunkKeyHash {
    size_t operator()(const std::tuple<int, int, int> &key) const;
};

using ChunkKey = std::tuple<int, int, int>;
using VoxelKey = std::tuple<int, int, int>;

namespace detail {
constexpr double EPSILON = 1e-6;
bool axis_test_x(const Vec3 &edge, const Vec3 &va, const Vec3 &vb, double hy, double hz);
bool axis_test_y(const Vec3 &edge, const Vec3 &va, const Vec3 &vb, double hx, double hz);
bool axis_test_z(const Vec3 &edge, const Vec3 &va, const Vec3 &vb, double hx, double hy);
} // namespace detail

bool triangle_aabb_intersect(Vec3 v0, Vec3 v1, Vec3 v2, const Vec3 &box_center,
                             const Vec3 &box_half_size);

Vec3 compute_triangle_normal(const Vec3 &v0, const Vec3 &v1, const Vec3 &v2);

class VoxelGrid {
  private:
    double cell_size_;
    Vec3 origin_;
    std::string name_;
    std::string source_path_;
    std::unordered_map<ChunkKey, VoxelChunk, ChunkKeyHash> chunks_;
    std::unordered_map<VoxelKey, std::vector<Vec3>, ChunkKeyHash> surface_normals_;

  public:
    VoxelGrid(double cell_size = 0.25, Vec3 origin = Vec3::zero(), const std::string &name = "",
              const std::string &source_path = "");

    const std::string &name() const;
    void set_name(const std::string &name);
    const std::string &source_path() const;
    void set_source_path(const std::string &path);

    std::tuple<int, int, int> world_to_voxel(const Vec3 &world_pos) const;
    Vec3 voxel_to_world(int vx, int vy, int vz) const;
    std::pair<ChunkKey, std::tuple<int, int, int>> voxel_to_chunk(int vx, int vy, int vz) const;

    uint8_t get(int vx, int vy, int vz) const;
    void set(int vx, int vy, int vz, uint8_t value);

    double cell_size() const;
    const Vec3 &origin() const;
    size_t chunk_count() const;
    int voxel_count() const;
    std::vector<std::tuple<int, int, int, uint8_t>> iter_non_empty() const;
    void clear();

    int voxelize_mesh(const std::vector<Vec3> &vertices,
                      const std::vector<std::tuple<int, int, int>> &triangles,
                      uint8_t voxel_type = VOXEL_SOLID);
    int fill_interior(uint8_t fill_value = VOXEL_SOLID);
    int mark_surface(uint8_t surface_value = VOXEL_SURFACE);
    int clear_by_type(uint8_t type_to_clear = VOXEL_SOLID);
    int compute_surface_normals(const std::vector<Vec3> &vertices,
                                const std::vector<std::tuple<int, int, int>> &triangles);

    const std::unordered_map<VoxelKey, std::vector<Vec3>, ChunkKeyHash> &surface_normals() const;
    Vec3 get_surface_normal(int vx, int vy, int vz) const;
    const std::vector<Vec3> &get_surface_normals(int vx, int vy, int vz) const;
    bool has_surface_normal(int vx, int vy, int vz) const;
    void add_surface_normal(int vx, int vy, int vz, const Vec3 &normal);
    void set_surface_normals(int vx, int vy, int vz, const std::vector<Vec3> &normals);

    uint8_t get_at_world(const Vec3 &world_pos) const;
    void set_at_world(const Vec3 &world_pos, uint8_t value);

    VoxelChunk *get_chunk(int cx, int cy, int cz);
    const VoxelChunk *get_chunk(int cx, int cy, int cz) const;
    std::vector<std::pair<ChunkKey, const VoxelChunk *>> iter_chunks() const;

    std::optional<std::pair<VoxelKey, VoxelKey>> bounds() const;
    std::optional<std::pair<Vec3, Vec3>> world_bounds() const;
    VoxelGrid extract_surface(uint8_t surface_value = VOXEL_SOLID) const;
};

} // namespace termin::voxels
