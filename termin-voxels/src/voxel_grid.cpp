#include "termin/voxels/voxel_grid.hpp"

#include <algorithm>
#include <array>
#include <climits>
#include <cmath>
#include <queue>

namespace termin::voxels {

size_t ChunkKeyHash::operator()(const std::tuple<int, int, int> &key) const {
    auto h1 = std::hash<int>{}(std::get<0>(key));
    auto h2 = std::hash<int>{}(std::get<1>(key));
    auto h3 = std::hash<int>{}(std::get<2>(key));
    return h1 ^ (h2 << 1) ^ (h3 << 2);
}

namespace detail {

bool axis_test_x(const Vec3 &edge, const Vec3 &va, const Vec3 &vb, double hy, double hz) {
    double p0 = -edge.z * va.y + edge.y * va.z;
    double p1 = -edge.z * vb.y + edge.y * vb.z;
    double r = hy * std::abs(edge.z) + hz * std::abs(edge.y);
    return !(std::min(p0, p1) > r + EPSILON || std::max(p0, p1) < -r - EPSILON);
}
bool axis_test_y(const Vec3 &edge, const Vec3 &va, const Vec3 &vb, double hx, double hz) {
    double p0 = edge.z * va.x - edge.x * va.z;
    double p1 = edge.z * vb.x - edge.x * vb.z;
    double r = hx * std::abs(edge.z) + hz * std::abs(edge.x);
    return !(std::min(p0, p1) > r + EPSILON || std::max(p0, p1) < -r - EPSILON);
}
bool axis_test_z(const Vec3 &edge, const Vec3 &va, const Vec3 &vb, double hx, double hy) {
    double p0 = -edge.y * va.x + edge.x * va.y;
    double p1 = -edge.y * vb.x + edge.x * vb.y;
    double r = hx * std::abs(edge.y) + hy * std::abs(edge.x);
    return !(std::min(p0, p1) > r + EPSILON || std::max(p0, p1) < -r - EPSILON);
}
} // namespace detail

bool triangle_aabb_intersect(Vec3 v0, Vec3 v1, Vec3 v2, const Vec3 &box_center,
                             const Vec3 &box_half_size) {
    v0 = v0 - box_center;
    v1 = v1 - box_center;
    v2 = v2 - box_center;
    Vec3 e0 = v1 - v0, e1 = v2 - v1, e2 = v0 - v2;
    double hx = box_half_size.x, hy = box_half_size.y, hz = box_half_size.z;
    double min_x = std::min({v0.x, v1.x, v2.x}), max_x = std::max({v0.x, v1.x, v2.x});
    if (min_x > hx + detail::EPSILON || max_x < -hx - detail::EPSILON)
        return false;
    double min_y = std::min({v0.y, v1.y, v2.y}), max_y = std::max({v0.y, v1.y, v2.y});
    if (min_y > hy + detail::EPSILON || max_y < -hy - detail::EPSILON)
        return false;
    double min_z = std::min({v0.z, v1.z, v2.z}), max_z = std::max({v0.z, v1.z, v2.z});
    if (min_z > hz + detail::EPSILON || max_z < -hz - detail::EPSILON)
        return false;
    Vec3 normal = e0.cross(e1);
    double d = -normal.dot(v0);
    double r = hx * std::abs(normal.x) + hy * std::abs(normal.y) + hz * std::abs(normal.z);
    if (d > r + detail::EPSILON || d < -r - detail::EPSILON)
        return false;
    if (!detail::axis_test_x(e0, v0, v2, hy, hz) || !detail::axis_test_y(e0, v0, v2, hx, hz) ||
        !detail::axis_test_z(e0, v0, v2, hx, hy))
        return false;
    if (!detail::axis_test_x(e1, v1, v0, hy, hz) || !detail::axis_test_y(e1, v1, v0, hx, hz) ||
        !detail::axis_test_z(e1, v1, v0, hx, hy))
        return false;
    if (!detail::axis_test_x(e2, v2, v1, hy, hz) || !detail::axis_test_y(e2, v2, v1, hx, hz) ||
        !detail::axis_test_z(e2, v2, v1, hx, hy))
        return false;
    return true;
}

Vec3 compute_triangle_normal(const Vec3 &v0, const Vec3 &v1, const Vec3 &v2) {
    Vec3 normal = (v1 - v0).cross(v2 - v0);
    double len = normal.norm();
    if (len > 1e-8)
        normal = normal / len;
    return normal;
}

VoxelGrid::VoxelGrid(double cell_size, Vec3 origin, const std::string &name,
                     const std::string &source_path)
    : cell_size_(cell_size), origin_(origin), name_(name), source_path_(source_path) {}
const std::string &VoxelGrid::name() const { return name_; }
void VoxelGrid::set_name(const std::string &name) { name_ = name; }
const std::string &VoxelGrid::source_path() const { return source_path_; }
void VoxelGrid::set_source_path(const std::string &path) { source_path_ = path; }
std::tuple<int, int, int> VoxelGrid::world_to_voxel(const Vec3 &p) const {
    Vec3 local = (p - origin_) / cell_size_;
    return {static_cast<int>(std::floor(local.x)), static_cast<int>(std::floor(local.y)),
            static_cast<int>(std::floor(local.z))};
}
Vec3 VoxelGrid::voxel_to_world(int x, int y, int z) const {
    return origin_ + Vec3(x + 0.5, y + 0.5, z + 0.5) * cell_size_;
}
std::pair<ChunkKey, std::tuple<int, int, int>> VoxelGrid::voxel_to_chunk(int x, int y,
                                                                         int z) const {
    auto d = [](int a, int b) { return a >= 0 ? a / b : (a - b + 1) / b; };
    auto m = [](int a, int b) { return ((a % b) + b) % b; };
    return {{d(x, CHUNK_SIZE), d(y, CHUNK_SIZE), d(z, CHUNK_SIZE)},
            {m(x, CHUNK_SIZE), m(y, CHUNK_SIZE), m(z, CHUNK_SIZE)}};
}
uint8_t VoxelGrid::get(int x, int y, int z) const {
    auto [k, l] = voxel_to_chunk(x, y, z);
    auto i = chunks_.find(k);
    return i == chunks_.end() ? VOXEL_EMPTY
                              : i->second.get(std::get<0>(l), std::get<1>(l), std::get<2>(l));
}
void VoxelGrid::set(int x, int y, int z, uint8_t value) {
    auto [k, l] = voxel_to_chunk(x, y, z);
    if (value == VOXEL_EMPTY) {
        auto i = chunks_.find(k);
        if (i != chunks_.end()) {
            i->second.set(std::get<0>(l), std::get<1>(l), std::get<2>(l), 0);
            if (i->second.is_empty())
                chunks_.erase(i);
        }
    } else
        chunks_[k].set(std::get<0>(l), std::get<1>(l), std::get<2>(l), value);
}
double VoxelGrid::cell_size() const { return cell_size_; }
const Vec3 &VoxelGrid::origin() const { return origin_; }
size_t VoxelGrid::chunk_count() const { return chunks_.size(); }
int VoxelGrid::voxel_count() const {
    int n = 0;
    for (const auto &[k, c] : chunks_)
        n += c.non_empty_count();
    return n;
}
std::vector<std::tuple<int, int, int, uint8_t>> VoxelGrid::iter_non_empty() const {
    std::vector<std::tuple<int, int, int, uint8_t>> r;
    r.reserve(voxel_count());
    for (const auto &[k, c] : chunks_) {
        int bx = std::get<0>(k) * CHUNK_SIZE, by = std::get<1>(k) * CHUNK_SIZE,
            bz = std::get<2>(k) * CHUNK_SIZE;
        for (auto [x, y, z, t] : c.iter_non_empty())
            r.emplace_back(bx + x, by + y, bz + z, t);
    }
    return r;
}
void VoxelGrid::clear() {
    chunks_.clear();
    surface_normals_.clear();
}

int VoxelGrid::voxelize_mesh(const std::vector<Vec3> &vertices,
                             const std::vector<std::tuple<int, int, int>> &triangles,
                             uint8_t type) {
    double half = cell_size_ / 2, epsilon = cell_size_ * .01;
    Vec3 hs(half, half, half);
    int n = 0;
    for (const auto &t : triangles) {
        Vec3 a = vertices[std::get<0>(t)], b = vertices[std::get<1>(t)],
             c = vertices[std::get<2>(t)];
        Vec3 mn(std::min({a.x, b.x, c.x}) - epsilon, std::min({a.y, b.y, c.y}) - epsilon,
                std::min({a.z, b.z, c.z}) - epsilon),
            mx(std::max({a.x, b.x, c.x}) + epsilon, std::max({a.y, b.y, c.y}) + epsilon,
               std::max({a.z, b.z, c.z}) + epsilon);
        auto [x0, y0, z0] = world_to_voxel(mn);
        auto [x1, y1, z1] = world_to_voxel(mx);
        for (int x = x0; x <= x1; x++)
            for (int y = y0; y <= y1; y++)
                for (int z = z0; z <= z1; z++)
                    if (triangle_aabb_intersect(a, b, c, voxel_to_world(x, y, z), hs)) {
                        set(x, y, z, type);
                        n++;
                    }
    }
    return n;
}

int VoxelGrid::fill_interior(uint8_t value) {
    if (chunks_.empty())
        return 0;
    int minx = INT_MAX, miny = INT_MAX, minz = INT_MAX, maxx = INT_MIN, maxy = INT_MIN,
        maxz = INT_MIN;
    for (const auto &[k, c] : chunks_) {
        int x = std::get<0>(k) * CHUNK_SIZE, y = std::get<1>(k) * CHUNK_SIZE,
            z = std::get<2>(k) * CHUNK_SIZE;
        minx = std::min(minx, x);
        miny = std::min(miny, y);
        minz = std::min(minz, z);
        maxx = std::max(maxx, x + CHUNK_SIZE - 1);
        maxy = std::max(maxy, y + CHUNK_SIZE - 1);
        maxz = std::max(maxz, z + CHUNK_SIZE - 1);
    }
    minx--;
    miny--;
    minz--;
    maxx++;
    maxy++;
    maxz++;
    std::unordered_map<VoxelKey, bool, ChunkKeyHash> outside;
    std::queue<VoxelKey> q;
    VoxelKey start = {minx, miny, minz};
    q.push(start);
    outside[start] = true;
    const std::array<std::tuple<int, int, int>, 6> ns = {
        {{1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}, {0, 0, 1}, {0, 0, -1}}};
    while (!q.empty()) {
        auto [x, y, z] = q.front();
        q.pop();
        for (auto [dx, dy, dz] : ns) {
            int nx = x + dx, ny = y + dy, nz = z + dz;
            if (nx < minx || nx > maxx || ny < miny || ny > maxy || nz < minz || nz > maxz)
                continue;
            VoxelKey k = {nx, ny, nz};
            if (outside.count(k) || get(nx, ny, nz) != VOXEL_EMPTY)
                continue;
            outside[k] = true;
            q.push(k);
        }
    }
    int n = 0;
    for (int x = minx; x <= maxx; x++)
        for (int y = miny; y <= maxy; y++)
            for (int z = minz; z <= maxz; z++) {
                VoxelKey k = {x, y, z};
                if (!outside.count(k) && get(x, y, z) == VOXEL_EMPTY) {
                    set(x, y, z, value);
                    n++;
                }
            }
    return n;
}

int VoxelGrid::mark_surface(uint8_t value) {
    const std::array<std::tuple<int, int, int>, 6> ns = {
        {{1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}, {0, 0, 1}, {0, 0, -1}}};
    std::vector<VoxelKey> s;
    for (auto [x, y, z, t] : iter_non_empty())
        for (auto [dx, dy, dz] : ns)
            if (get(x + dx, y + dy, z + dz) == VOXEL_EMPTY) {
                s.emplace_back(x, y, z);
                break;
            }
    for (auto [x, y, z] : s)
        set(x, y, z, value);
    return static_cast<int>(s.size());
}
int VoxelGrid::clear_by_type(uint8_t type) {
    std::vector<VoxelKey> r;
    for (auto [x, y, z, t] : iter_non_empty())
        if (t == type)
            r.emplace_back(x, y, z);
    for (auto [x, y, z] : r)
        set(x, y, z, VOXEL_EMPTY);
    return static_cast<int>(r.size());
}

int VoxelGrid::compute_surface_normals(const std::vector<Vec3> &vertices,
                                       const std::vector<std::tuple<int, int, int>> &triangles) {
    std::unordered_map<VoxelKey, bool, ChunkKeyHash> s;
    for (auto [x, y, z, t] : iter_non_empty())
        if (t == VOXEL_SURFACE)
            s[{x, y, z}] = true;
    if (s.empty())
        return 0;
    std::unordered_map<VoxelKey, bool, ChunkKeyHash> got;
    double half = cell_size_ / 2, epsilon = cell_size_ * .01;
    Vec3 hs(half, half, half);
    for (const auto &t : triangles) {
        Vec3 a = vertices[std::get<0>(t)], b = vertices[std::get<1>(t)],
             c = vertices[std::get<2>(t)], normal = compute_triangle_normal(a, b, c);
        Vec3 mn(std::min({a.x, b.x, c.x}) - epsilon, std::min({a.y, b.y, c.y}) - epsilon,
                std::min({a.z, b.z, c.z}) - epsilon),
            mx(std::max({a.x, b.x, c.x}) + epsilon, std::max({a.y, b.y, c.y}) + epsilon,
               std::max({a.z, b.z, c.z}) + epsilon);
        auto [x0, y0, z0] = world_to_voxel(mn);
        auto [x1, y1, z1] = world_to_voxel(mx);
        for (int x = x0; x <= x1; x++)
            for (int y = y0; y <= y1; y++)
                for (int z = z0; z <= z1; z++) {
                    VoxelKey k = {x, y, z};
                    if (s.count(k) &&
                        triangle_aabb_intersect(a, b, c, voxel_to_world(x, y, z), hs)) {
                        surface_normals_[k].push_back(normal);
                        got[k] = true;
                    }
                }
    }
    return static_cast<int>(got.size());
}
const std::unordered_map<VoxelKey, std::vector<Vec3>, ChunkKeyHash> &
VoxelGrid::surface_normals() const {
    return surface_normals_;
}
Vec3 VoxelGrid::get_surface_normal(int x, int y, int z) const {
    auto i = surface_normals_.find({x, y, z});
    return i != surface_normals_.end() && !i->second.empty() ? i->second[0] : Vec3::zero();
}
const std::vector<Vec3> &VoxelGrid::get_surface_normals(int x, int y, int z) const {
    static const std::vector<Vec3> empty;
    auto i = surface_normals_.find({x, y, z});
    return i != surface_normals_.end() ? i->second : empty;
}
bool VoxelGrid::has_surface_normal(int x, int y, int z) const {
    return surface_normals_.count({x, y, z}) > 0;
}
void VoxelGrid::add_surface_normal(int x, int y, int z, const Vec3 &n) {
    surface_normals_[{x, y, z}].push_back(n);
}
void VoxelGrid::set_surface_normals(int x, int y, int z, const std::vector<Vec3> &n) {
    surface_normals_[{x, y, z}] = n;
}
uint8_t VoxelGrid::get_at_world(const Vec3 &p) const {
    auto [x, y, z] = world_to_voxel(p);
    return get(x, y, z);
}
void VoxelGrid::set_at_world(const Vec3 &p, uint8_t v) {
    auto [x, y, z] = world_to_voxel(p);
    set(x, y, z, v);
}
VoxelChunk *VoxelGrid::get_chunk(int x, int y, int z) {
    auto i = chunks_.find({x, y, z});
    return i != chunks_.end() ? &i->second : nullptr;
}
const VoxelChunk *VoxelGrid::get_chunk(int x, int y, int z) const {
    auto i = chunks_.find({x, y, z});
    return i != chunks_.end() ? &i->second : nullptr;
}
std::vector<std::pair<ChunkKey, const VoxelChunk *>> VoxelGrid::iter_chunks() const {
    std::vector<std::pair<ChunkKey, const VoxelChunk *>> r;
    r.reserve(chunks_.size());
    for (const auto &[k, c] : chunks_)
        r.emplace_back(k, &c);
    return r;
}
std::optional<std::pair<VoxelKey, VoxelKey>> VoxelGrid::bounds() const {
    if (chunks_.empty())
        return std::nullopt;
    int minx = INT_MAX, miny = INT_MAX, minz = INT_MAX, maxx = INT_MIN, maxy = INT_MIN,
        maxz = INT_MIN;
    for (const auto &[k, c] : chunks_) {
        minx = std::min(minx, std::get<0>(k));
        miny = std::min(miny, std::get<1>(k));
        minz = std::min(minz, std::get<2>(k));
        maxx = std::max(maxx, std::get<0>(k));
        maxy = std::max(maxy, std::get<1>(k));
        maxz = std::max(maxz, std::get<2>(k));
    }
    return std::make_pair(VoxelKey{minx * CHUNK_SIZE, miny * CHUNK_SIZE, minz * CHUNK_SIZE},
                          VoxelKey{(maxx + 1) * CHUNK_SIZE - 1, (maxy + 1) * CHUNK_SIZE - 1,
                                   (maxz + 1) * CHUNK_SIZE - 1});
}
std::optional<std::pair<Vec3, Vec3>> VoxelGrid::world_bounds() const {
    auto b = bounds();
    if (!b)
        return std::nullopt;
    auto [mn, mx] = *b;
    return std::make_pair(
        origin_ + Vec3(std::get<0>(mn), std::get<1>(mn), std::get<2>(mn)) * cell_size_,
        origin_ + Vec3(std::get<0>(mx) + 1, std::get<1>(mx) + 1, std::get<2>(mx) + 1) * cell_size_);
}
VoxelGrid VoxelGrid::extract_surface(uint8_t value) const {
    VoxelGrid r(cell_size_, origin_, name_.empty() ? "surface" : name_ + "_surface");
    const std::array<std::tuple<int, int, int>, 6> ns = {
        {{1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}, {0, 0, 1}, {0, 0, -1}}};
    for (auto [x, y, z, t] : iter_non_empty()) {
        bool empty = false;
        for (auto [dx, dy, dz] : ns)
            if (get(x + dx, y + dy, z + dz) == VOXEL_EMPTY) {
                empty = true;
                break;
            }
        if (empty)
            r.set(x, y, z, value);
    }
    return r;
}

} // namespace termin::voxels
