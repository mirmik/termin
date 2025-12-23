#pragma once

#include <unordered_map>
#include <vector>
#include <tuple>
#include <queue>
#include <cmath>
#include <algorithm>

#include "termin/voxels/voxel_chunk.hpp"
#include "termin/geom/vec3.hpp"

namespace termin {
namespace voxels {


// Hash for tuple<int,int,int>
struct ChunkKeyHash {
    size_t operator()(const std::tuple<int, int, int>& key) const {
        auto h1 = std::hash<int>{}(std::get<0>(key));
        auto h2 = std::hash<int>{}(std::get<1>(key));
        auto h3 = std::hash<int>{}(std::get<2>(key));
        return h1 ^ (h2 << 1) ^ (h3 << 2);
    }
};

using ChunkKey = std::tuple<int, int, int>;
using VoxelKey = std::tuple<int, int, int>;

// ============================================================================
// Triangle-AABB intersection (Tomas Akenine-Möller SAT algorithm)
// ============================================================================

namespace detail {

constexpr double EPSILON = 1e-6;

inline bool axis_test_x(const Vec3& edge, const Vec3& va, const Vec3& vb, double hy, double hz) {
    double p0 = -edge.z * va.y + edge.y * va.z;
    double p1 = -edge.z * vb.y + edge.y * vb.z;
    double r = hy * std::abs(edge.z) + hz * std::abs(edge.y);
    return !(std::min(p0, p1) > r + EPSILON || std::max(p0, p1) < -r - EPSILON);
}

inline bool axis_test_y(const Vec3& edge, const Vec3& va, const Vec3& vb, double hx, double hz) {
    double p0 = edge.z * va.x - edge.x * va.z;
    double p1 = edge.z * vb.x - edge.x * vb.z;
    double r = hx * std::abs(edge.z) + hz * std::abs(edge.x);
    return !(std::min(p0, p1) > r + EPSILON || std::max(p0, p1) < -r - EPSILON);
}

inline bool axis_test_z(const Vec3& edge, const Vec3& va, const Vec3& vb, double hx, double hy) {
    double p0 = -edge.y * va.x + edge.x * va.y;
    double p1 = -edge.y * vb.x + edge.x * vb.y;
    double r = hx * std::abs(edge.y) + hy * std::abs(edge.x);
    return !(std::min(p0, p1) > r + EPSILON || std::max(p0, p1) < -r - EPSILON);
}

} // namespace detail

inline bool triangle_aabb_intersect(
    Vec3 v0, Vec3 v1, Vec3 v2,
    const Vec3& box_center,
    const Vec3& box_half_size
) {
    // Move triangle to box-centered coordinates
    v0 = v0 - box_center;
    v1 = v1 - box_center;
    v2 = v2 - box_center;

    Vec3 e0 = v1 - v0;
    Vec3 e1 = v2 - v1;
    Vec3 e2 = v0 - v2;

    double hx = box_half_size.x;
    double hy = box_half_size.y;
    double hz = box_half_size.z;

    // Test 1: AABB axes
    double min_x = std::min({v0.x, v1.x, v2.x});
    double max_x = std::max({v0.x, v1.x, v2.x});
    if (min_x > hx + detail::EPSILON || max_x < -hx - detail::EPSILON) return false;

    double min_y = std::min({v0.y, v1.y, v2.y});
    double max_y = std::max({v0.y, v1.y, v2.y});
    if (min_y > hy + detail::EPSILON || max_y < -hy - detail::EPSILON) return false;

    double min_z = std::min({v0.z, v1.z, v2.z});
    double max_z = std::max({v0.z, v1.z, v2.z});
    if (min_z > hz + detail::EPSILON || max_z < -hz - detail::EPSILON) return false;

    // Test 2: Triangle normal
    Vec3 normal = e0.cross(e1);
    double d = -normal.dot(v0);
    double r = hx * std::abs(normal.x) + hy * std::abs(normal.y) + hz * std::abs(normal.z);
    if (d > r + detail::EPSILON || d < -r - detail::EPSILON) return false;

    // Test 3: Cross products of edges with axes
    if (!detail::axis_test_x(e0, v0, v2, hy, hz)) return false;
    if (!detail::axis_test_y(e0, v0, v2, hx, hz)) return false;
    if (!detail::axis_test_z(e0, v0, v2, hx, hy)) return false;

    if (!detail::axis_test_x(e1, v1, v0, hy, hz)) return false;
    if (!detail::axis_test_y(e1, v1, v0, hx, hz)) return false;
    if (!detail::axis_test_z(e1, v1, v0, hx, hy)) return false;

    if (!detail::axis_test_x(e2, v2, v1, hy, hz)) return false;
    if (!detail::axis_test_y(e2, v2, v1, hx, hz)) return false;
    if (!detail::axis_test_z(e2, v2, v1, hx, hy)) return false;

    return true;
}

inline Vec3 compute_triangle_normal(const Vec3& v0, const Vec3& v1, const Vec3& v2) {
    Vec3 edge1 = v1 - v0;
    Vec3 edge2 = v2 - v0;
    Vec3 normal = edge1.cross(edge2);
    double len = normal.norm();
    if (len > 1e-8) {
        normal = normal / len;
    }
    return normal;
}

// ============================================================================
// VoxelGrid
// ============================================================================

class VoxelGrid {
public:
    VoxelGrid(double cell_size = 0.25, Vec3 origin = Vec3::zero())
        : cell_size_(cell_size), origin_(origin) {}

    // Coordinate transforms
    std::tuple<int, int, int> world_to_voxel(const Vec3& world_pos) const {
        Vec3 local = (world_pos - origin_) / cell_size_;
        return {
            static_cast<int>(std::floor(local.x)),
            static_cast<int>(std::floor(local.y)),
            static_cast<int>(std::floor(local.z))
        };
    }

    Vec3 voxel_to_world(int vx, int vy, int vz) const {
        return origin_ + Vec3(vx + 0.5, vy + 0.5, vz + 0.5) * cell_size_;
    }

    std::pair<ChunkKey, std::tuple<int, int, int>> voxel_to_chunk(int vx, int vy, int vz) const {
        auto div_floor = [](int a, int b) { return a >= 0 ? a / b : (a - b + 1) / b; };
        auto mod_floor = [](int a, int b) { return ((a % b) + b) % b; };

        int cx = div_floor(vx, CHUNK_SIZE);
        int cy = div_floor(vy, CHUNK_SIZE);
        int cz = div_floor(vz, CHUNK_SIZE);
        int lx = mod_floor(vx, CHUNK_SIZE);
        int ly = mod_floor(vy, CHUNK_SIZE);
        int lz = mod_floor(vz, CHUNK_SIZE);

        return {{cx, cy, cz}, {lx, ly, lz}};
    }

    // Access
    uint8_t get(int vx, int vy, int vz) const {
        auto [chunk_key, local] = voxel_to_chunk(vx, vy, vz);
        auto it = chunks_.find(chunk_key);
        if (it == chunks_.end()) return VOXEL_EMPTY;
        return it->second.get(std::get<0>(local), std::get<1>(local), std::get<2>(local));
    }

    void set(int vx, int vy, int vz, uint8_t value) {
        auto [chunk_key, local] = voxel_to_chunk(vx, vy, vz);

        if (value == VOXEL_EMPTY) {
            auto it = chunks_.find(chunk_key);
            if (it != chunks_.end()) {
                it->second.set(std::get<0>(local), std::get<1>(local), std::get<2>(local), 0);
                if (it->second.is_empty()) {
                    chunks_.erase(it);
                }
            }
        } else {
            chunks_[chunk_key].set(std::get<0>(local), std::get<1>(local), std::get<2>(local), value);
        }
    }

    // Properties
    double cell_size() const { return cell_size_; }
    const Vec3& origin() const { return origin_; }
    size_t chunk_count() const { return chunks_.size(); }

    int voxel_count() const {
        int count = 0;
        for (const auto& [key, chunk] : chunks_) {
            count += chunk.non_empty_count();
        }
        return count;
    }

    // Iterate all non-empty voxels
    std::vector<std::tuple<int, int, int, uint8_t>> iter_non_empty() const {
        std::vector<std::tuple<int, int, int, uint8_t>> result;
        result.reserve(voxel_count());

        for (const auto& [chunk_key, chunk] : chunks_) {
            int base_x = std::get<0>(chunk_key) * CHUNK_SIZE;
            int base_y = std::get<1>(chunk_key) * CHUNK_SIZE;
            int base_z = std::get<2>(chunk_key) * CHUNK_SIZE;

            for (auto [lx, ly, lz, vtype] : chunk.iter_non_empty()) {
                result.emplace_back(base_x + lx, base_y + ly, base_z + lz, vtype);
            }
        }
        return result;
    }

    void clear() {
        chunks_.clear();
        surface_normals_.clear();
    }

    // ========================================================================
    // Voxelization
    // ========================================================================

    int voxelize_mesh(
        const std::vector<Vec3>& vertices,
        const std::vector<std::tuple<int, int, int>>& triangles,
        uint8_t voxel_type = VOXEL_SOLID
    ) {
        double half = cell_size_ / 2.0;
        Vec3 half_size(half, half, half);
        double epsilon = cell_size_ * 0.01;
        int count = 0;

        for (const auto& tri : triangles) {
            Vec3 v0 = vertices[std::get<0>(tri)];
            Vec3 v1 = vertices[std::get<1>(tri)];
            Vec3 v2 = vertices[std::get<2>(tri)];

            // Triangle AABB
            Vec3 tri_min(
                std::min({v0.x, v1.x, v2.x}) - epsilon,
                std::min({v0.y, v1.y, v2.y}) - epsilon,
                std::min({v0.z, v1.z, v2.z}) - epsilon
            );
            Vec3 tri_max(
                std::max({v0.x, v1.x, v2.x}) + epsilon,
                std::max({v0.y, v1.y, v2.y}) + epsilon,
                std::max({v0.z, v1.z, v2.z}) + epsilon
            );

            auto [vmin_x, vmin_y, vmin_z] = world_to_voxel(tri_min);
            auto [vmax_x, vmax_y, vmax_z] = world_to_voxel(tri_max);

            for (int vx = vmin_x; vx <= vmax_x; vx++) {
                for (int vy = vmin_y; vy <= vmax_y; vy++) {
                    for (int vz = vmin_z; vz <= vmax_z; vz++) {
                        Vec3 center = voxel_to_world(vx, vy, vz);
                        if (triangle_aabb_intersect(v0, v1, v2, center, half_size)) {
                            set(vx, vy, vz, voxel_type);
                            count++;
                        }
                    }
                }
            }
        }
        return count;
    }

    // ========================================================================
    // Fill interior (flood fill from outside)
    // ========================================================================

    int fill_interior(uint8_t fill_value = VOXEL_SOLID) {
        if (chunks_.empty()) return 0;

        // Compute bounds
        int min_x = INT_MAX, min_y = INT_MAX, min_z = INT_MAX;
        int max_x = INT_MIN, max_y = INT_MIN, max_z = INT_MIN;

        for (const auto& [key, chunk] : chunks_) {
            int cx = std::get<0>(key) * CHUNK_SIZE;
            int cy = std::get<1>(key) * CHUNK_SIZE;
            int cz = std::get<2>(key) * CHUNK_SIZE;
            min_x = std::min(min_x, cx);
            min_y = std::min(min_y, cy);
            min_z = std::min(min_z, cz);
            max_x = std::max(max_x, cx + CHUNK_SIZE - 1);
            max_y = std::max(max_y, cy + CHUNK_SIZE - 1);
            max_z = std::max(max_z, cz + CHUNK_SIZE - 1);
        }

        // Expand bounds by 1
        min_x--; min_y--; min_z--;
        max_x++; max_y++; max_z++;

        // BFS from corner to mark outside
        std::unordered_map<VoxelKey, bool, ChunkKeyHash> outside;
        std::queue<VoxelKey> queue;

        VoxelKey start = {min_x, min_y, min_z};
        queue.push(start);
        outside[start] = true;

        const std::array<std::tuple<int, int, int>, 6> neighbors = {{
            {1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}, {0, 0, 1}, {0, 0, -1}
        }};

        while (!queue.empty()) {
            auto [x, y, z] = queue.front();
            queue.pop();

            for (const auto& [dx, dy, dz] : neighbors) {
                int nx = x + dx, ny = y + dy, nz = z + dz;

                if (nx < min_x || nx > max_x) continue;
                if (ny < min_y || ny > max_y) continue;
                if (nz < min_z || nz > max_z) continue;

                VoxelKey nkey = {nx, ny, nz};
                if (outside.count(nkey)) continue;
                if (get(nx, ny, nz) != VOXEL_EMPTY) continue;

                outside[nkey] = true;
                queue.push(nkey);
            }
        }

        // Fill everything not outside and not solid
        int filled = 0;
        for (int x = min_x; x <= max_x; x++) {
            for (int y = min_y; y <= max_y; y++) {
                for (int z = min_z; z <= max_z; z++) {
                    VoxelKey key = {x, y, z};
                    if (!outside.count(key) && get(x, y, z) == VOXEL_EMPTY) {
                        set(x, y, z, fill_value);
                        filled++;
                    }
                }
            }
        }

        return filled;
    }

    // ========================================================================
    // Mark surface voxels
    // ========================================================================

    int mark_surface(uint8_t surface_value = VOXEL_SURFACE) {
        const std::array<std::tuple<int, int, int>, 6> neighbors = {{
            {1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}, {0, 0, 1}, {0, 0, -1}
        }};

        std::vector<VoxelKey> surface_coords;

        for (auto [vx, vy, vz, vtype] : iter_non_empty()) {
            for (const auto& [dx, dy, dz] : neighbors) {
                if (get(vx + dx, vy + dy, vz + dz) == VOXEL_EMPTY) {
                    surface_coords.emplace_back(vx, vy, vz);
                    break;
                }
            }
        }

        for (const auto& [x, y, z] : surface_coords) {
            set(x, y, z, surface_value);
        }

        return static_cast<int>(surface_coords.size());
    }

    // ========================================================================
    // Clear by type
    // ========================================================================

    int clear_by_type(uint8_t type_to_clear = VOXEL_SOLID) {
        std::vector<VoxelKey> to_clear;

        for (auto [vx, vy, vz, vtype] : iter_non_empty()) {
            if (vtype == type_to_clear) {
                to_clear.emplace_back(vx, vy, vz);
            }
        }

        for (const auto& [x, y, z] : to_clear) {
            set(x, y, z, VOXEL_EMPTY);
        }

        return static_cast<int>(to_clear.size());
    }

    // ========================================================================
    // Compute surface normals
    // ========================================================================

    int compute_surface_normals(
        const std::vector<Vec3>& vertices,
        const std::vector<std::tuple<int, int, int>>& triangles
    ) {
        // Collect surface voxels
        std::unordered_map<VoxelKey, bool, ChunkKeyHash> surface_voxels;
        for (auto [vx, vy, vz, vtype] : iter_non_empty()) {
            if (vtype == VOXEL_SURFACE) {
                surface_voxels[{vx, vy, vz}] = true;
            }
        }

        if (surface_voxels.empty()) return 0;

        // Track which voxels got normals
        std::unordered_map<VoxelKey, bool, ChunkKeyHash> voxels_with_normals;

        double half = cell_size_ / 2.0;
        Vec3 half_size(half, half, half);
        double epsilon = cell_size_ * 0.01;

        for (const auto& tri : triangles) {
            Vec3 v0 = vertices[std::get<0>(tri)];
            Vec3 v1 = vertices[std::get<1>(tri)];
            Vec3 v2 = vertices[std::get<2>(tri)];

            Vec3 tri_normal = compute_triangle_normal(v0, v1, v2);

            Vec3 tri_min(
                std::min({v0.x, v1.x, v2.x}) - epsilon,
                std::min({v0.y, v1.y, v2.y}) - epsilon,
                std::min({v0.z, v1.z, v2.z}) - epsilon
            );
            Vec3 tri_max(
                std::max({v0.x, v1.x, v2.x}) + epsilon,
                std::max({v0.y, v1.y, v2.y}) + epsilon,
                std::max({v0.z, v1.z, v2.z}) + epsilon
            );

            auto [vmin_x, vmin_y, vmin_z] = world_to_voxel(tri_min);
            auto [vmax_x, vmax_y, vmax_z] = world_to_voxel(tri_max);

            for (int vx = vmin_x; vx <= vmax_x; vx++) {
                for (int vy = vmin_y; vy <= vmax_y; vy++) {
                    for (int vz = vmin_z; vz <= vmax_z; vz++) {
                        VoxelKey key = {vx, vy, vz};
                        if (!surface_voxels.count(key)) continue;

                        Vec3 center = voxel_to_world(vx, vy, vz);
                        if (triangle_aabb_intersect(v0, v1, v2, center, half_size)) {
                            // Add triangle normal to the list (no averaging)
                            surface_normals_[key].push_back(tri_normal);
                            voxels_with_normals[key] = true;
                        }
                    }
                }
            }
        }

        return static_cast<int>(voxels_with_normals.size());
    }

    // Surface normals access (list of normals per voxel)
    const std::unordered_map<VoxelKey, std::vector<Vec3>, ChunkKeyHash>& surface_normals() const {
        return surface_normals_;
    }

    // Get first normal for backwards compatibility
    Vec3 get_surface_normal(int vx, int vy, int vz) const {
        auto it = surface_normals_.find({vx, vy, vz});
        if (it != surface_normals_.end() && !it->second.empty()) {
            return it->second[0];
        }
        return Vec3::zero();
    }

    // Get all normals for a voxel
    const std::vector<Vec3>& get_surface_normals(int vx, int vy, int vz) const {
        static const std::vector<Vec3> empty;
        auto it = surface_normals_.find({vx, vy, vz});
        if (it != surface_normals_.end()) {
            return it->second;
        }
        return empty;
    }

    bool has_surface_normal(int vx, int vy, int vz) const {
        return surface_normals_.count({vx, vy, vz}) > 0;
    }

private:
    double cell_size_;
    Vec3 origin_;
    std::unordered_map<ChunkKey, VoxelChunk, ChunkKeyHash> chunks_;
    std::unordered_map<VoxelKey, std::vector<Vec3>, ChunkKeyHash> surface_normals_;
};

} // namespace voxels
} // namespace termin
