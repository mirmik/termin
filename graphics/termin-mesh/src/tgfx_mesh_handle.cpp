#include <tgfx/tgfx_mesh3.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>

#include <geom/tc_vec3f.h>

#include <cmath>
#include <limits>

namespace termin {

    namespace {

        bool try_narrow_float_lower_bound(double value, float& out) noexcept {
            constexpr double float_max = static_cast<double>(std::numeric_limits<float>::max());
            if (!std::isfinite(value) || value < -float_max || value > float_max) {
                return false;
            }

            float narrowed = static_cast<float>(value);
            if (!std::isfinite(narrowed)) {
                return false;
            }
            if (static_cast<double>(narrowed) < value) {
                narrowed = std::nextafter(narrowed, std::numeric_limits<float>::infinity());
            }
            out = narrowed;
            return true;
        }

        bool try_narrow_float_upper_bound(double value, float& out) noexcept {
            constexpr double float_max = static_cast<double>(std::numeric_limits<float>::max());
            if (!std::isfinite(value) || value < -float_max || value > float_max) {
                return false;
            }

            float narrowed = static_cast<float>(value);
            if (!std::isfinite(narrowed)) {
                return false;
            }
            if (static_cast<double>(narrowed) > value) {
                narrowed = std::nextafter(narrowed, -std::numeric_limits<float>::infinity());
            }
            out = narrowed;
            return true;
        }

        struct PackedSurfaceEdgeInputs {
            tc_vec3f point{};
            tc_vec3f up{};
            tc_vec3f metric{};
        };

        tc_mesh* surface_edge_mesh(const TcMesh& handle, const char* operation) {
            tc_mesh* mesh = handle.get();
            if (!mesh) {
                tc_log_error("[TcMesh] Cannot %s on an invalid or stale mesh handle", operation);
            }
            return mesh;
        }

        bool try_pack_surface_edge_direction(const Vec3& value, const char* name, tc_vec3f& out) {
            Vec3 unit;
            if (!value.try_normalized(unit, 0.0) || !unit.try_to_float(out)) {
                tc_log_error("[TcMesh] Surface-edge %s must be finite, non-degenerate, and representable as float",
                             name);
                return false;
            }
            return true;
        }

        bool validate_surface_edge_metric_product(const tc_vec3f& value,
                                                  const tc_vec3f& metric,
                                                  const char* name) {
            tc_vec3f product;
            if (!tc_vec3f_try_cwise_product(value, metric, &product)) {
                tc_log_error("[TcMesh] Surface-edge %s and metric overflow or underflow packed-float math", name);
                return false;
            }
            return true;
        }

        bool try_pack_surface_edge_inputs(const Vec3& point,
                                          const std::optional<Vec3>& up,
                                          const std::optional<Vec3>& metric,
                                          PackedSurfaceEdgeInputs& out) {
            if (!point.try_to_float(out.point)) {
                tc_log_error(
                    "[TcMesh] Surface-edge point cannot be narrowed to float without overflow or underflow");
                return false;
            }

            const Vec3 resolved_up = up.value_or(Vec3::unit_z());
            if (!try_pack_surface_edge_direction(resolved_up, "up direction", out.up)) {
                return false;
            }

            const Vec3 resolved_metric = metric.value_or(Vec3(1.0, 1.0, 1.0));
            constexpr double metric_floor = 1.0e-8;
            if (!resolved_metric.is_finite() || resolved_metric.min_component() < metric_floor ||
                !resolved_metric.try_to_float(out.metric)) {
                tc_log_error(
                    "[TcMesh] Surface-edge metric components must be finite, float-representable, and at least 1e-8");
                return false;
            }

            if (!validate_surface_edge_metric_product(out.point, out.metric, "point") ||
                !validate_surface_edge_metric_product(out.up, out.metric, "up direction")) {
                return false;
            }
            return true;
        }

        bool try_pack_surface_edge_angle(double value, float& out) {
            if (!std::isfinite(value) || value < 0.0 || value > 90.0) {
                tc_log_error("[TcMesh] Surface-edge maximum angle must be finite and lie in [0, 90] degrees");
                return false;
            }
            return try_narrow_float_upper_bound(value, out);
        }

        std::optional<TcMeshSurfaceEdgeHit> unpack_surface_edge_hit(const tc_mesh_surface_edge_hit& hit) {
            if (!hit.point.is_finite() || !std::isfinite(hit.distance) || hit.distance < 0.0f || hit.side < -1 ||
                hit.side > 1) {
                tc_log_error("[TcMesh] Surface-edge backend returned an invalid hit");
                return std::nullopt;
            }
            return TcMeshSurfaceEdgeHit{
                hit.point.to_double(),
                {hit.indices[0], hit.indices[1]},
                static_cast<double>(hit.distance),
                hit.side,
            };
        }

    } // namespace

    static void set_mesh_submeshes(TcMesh& mesh, const TcMeshCreateInfo& create_info) {
        if (!create_info.submeshes || create_info.submesh_count == 0) {
            return;
        }

        tc_mesh* raw = mesh.get();
        if (raw && !tc_mesh_set_submeshes(raw, create_info.submeshes, create_info.submesh_count)) {
            tc_log_error("[TcMesh] Failed to set submeshes for '%s'", create_info.name.c_str());
        }
    }

    bool TcMesh::set_from_mesh3(const Mesh3& mesh, const tc_vertex_layout* custom_layout) {
        tc_mesh* m = get();
        if (!m) {
            return false;
        }

        if (mesh.vertices.empty()) {
            return false;
        }

        // Keep the default mesh layout compatible with PBR shaders. Missing tangents
        // stay zero-filled in the interleaved buffer below.
        tc_vertex_layout layout;
        if (custom_layout) {
            layout = *custom_layout;
        } else {
            layout = tc_vertex_layout_pos_normal_uv_tangent();
        }

        // Build interleaved vertex buffer
        size_t num_verts = mesh.vertices.size();
        size_t stride = layout.stride;
        std::vector<uint8_t> buffer(num_verts * stride, 0);

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&layout, "normal");
        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&layout, "uv");
        const tc_vertex_attrib* tan_attr = tc_vertex_layout_find(&layout, "tangent");

        for (size_t i = 0; i < num_verts; i++) {
            uint8_t* dst = buffer.data() + i * stride;

            if (pos_attr) {
                float* p = reinterpret_cast<float*>(dst + pos_attr->offset);
                p[0] = mesh.vertices[i].x;
                p[1] = mesh.vertices[i].y;
                p[2] = mesh.vertices[i].z;
            }

            if (norm_attr && i < mesh.normals.size()) {
                float* n = reinterpret_cast<float*>(dst + norm_attr->offset);
                n[0] = mesh.normals[i].x;
                n[1] = mesh.normals[i].y;
                n[2] = mesh.normals[i].z;
            }

            if (uv_attr && i < mesh.uvs.size()) {
                float* u = reinterpret_cast<float*>(dst + uv_attr->offset);
                u[0] = mesh.uvs[i].x;
                u[1] = mesh.uvs[i].y;
            }

            if (tan_attr && i < mesh.tangents.size()) {
                float* t = reinterpret_cast<float*>(dst + tan_attr->offset);
                t[0] = mesh.tangents[i].x;
                t[1] = mesh.tangents[i].y;
                t[2] = mesh.tangents[i].z;
                t[3] = mesh.tangents[i].w;
            }
        }

        return tc_mesh_set_data(m,
                                buffer.data(),
                                num_verts,
                                &layout,
                                mesh.triangles.data(),
                                mesh.triangles.size(),
                                mesh.name.empty() ? nullptr : mesh.name.c_str());
    }

    std::optional<TcMeshRayHit>
    TcMesh::raycast(const Ray3& ray, double min_distance, double max_distance) const {
        tc_mesh* mesh = get();
        if (!mesh) {
            tc_log_error("[TcMesh] Cannot raycast an invalid or stale mesh handle");
            return std::nullopt;
        }
        if (!std::isfinite(min_distance) || !std::isfinite(max_distance) || min_distance > max_distance) {
            tc_log_error("[TcMesh] Raycast range must be a finite closed interval (min=%.17g, max=%.17g)",
                         min_distance,
                         max_distance);
            return std::nullopt;
        }
        if (!ray.origin.is_finite()) {
            tc_log_error("[TcMesh] Raycast origin must contain only finite values");
            return std::nullopt;
        }

        Vec3 direction;
        if (!ray.direction.try_normalized(direction)) {
            tc_log_error("[TcMesh] Raycast direction must be finite and non-degenerate");
            return std::nullopt;
        }

        tc_mesh_ray packed_ray{};
        if (!ray.origin.try_to_float(packed_ray.origin) || !direction.try_to_float(packed_ray.direction)) {
            tc_log_error(
                "[TcMesh] Raycast origin or normalized direction cannot be narrowed to float without overflow or underflow");
            return std::nullopt;
        }
        if (!try_narrow_float_lower_bound(min_distance, packed_ray.t_min) ||
            !try_narrow_float_upper_bound(max_distance, packed_ray.t_max)) {
            tc_log_error("[TcMesh] Raycast range is outside the finite float magnitude range (min=%.17g, max=%.17g)",
                         min_distance,
                         max_distance);
            return std::nullopt;
        }
        if (packed_ray.t_min > packed_ray.t_max) {
            tc_log_error("[TcMesh] Raycast range contains no representable float distances (min=%.17g, max=%.17g)",
                         min_distance,
                         max_distance);
            return std::nullopt;
        }

        tc_mesh_hit packed_hit{};
        if (!tc_mesh_raycast(mesh, &packed_ray, &packed_hit)) {
            return std::nullopt;
        }

        return TcMeshRayHit{
            static_cast<double>(packed_hit.t),
            packed_hit.position.to_double(),
            packed_hit.normal.to_double(),
            packed_hit.barycentric.to_double(),
            packed_hit.triangle_index,
            {packed_hit.indices[0], packed_hit.indices[1], packed_hit.indices[2]},
        };
    }

    std::optional<TcMeshSurfaceEdgeHit>
    TcMesh::find_surface_edge(uint32_t start_triangle,
                              const Vec3& point,
                              const Vec3& normal,
                              std::optional<Vec3> up,
                              std::optional<Vec3> metric) const {
        tc_mesh* mesh = surface_edge_mesh(*this, "find a surface edge");
        if (!mesh) {
            return std::nullopt;
        }

        PackedSurfaceEdgeInputs packed;
        tc_mesh_surface_edge_query query{};
        if (!try_pack_surface_edge_inputs(point, up, metric, packed) ||
            !try_pack_surface_edge_direction(normal, "normal", query.normal)) {
            return std::nullopt;
        }
        query.start_triangle = start_triangle;
        query.point = packed.point;
        query.up = packed.up;
        query.metric = packed.metric;

        tc_mesh_surface_edge_hit hit{};
        if (!tc_mesh_find_surface_edge_query(mesh, &query, &hit)) {
            return std::nullopt;
        }
        return unpack_surface_edge_hit(hit);
    }

    std::optional<TcMeshSurfaceEdgeHit>
    TcMesh::find_surface_edge_aligned(uint32_t start_triangle,
                                      const Vec3& point,
                                      const Vec3& normal,
                                      const Vec3& edge_direction,
                                      double max_angle_degrees,
                                      std::optional<Vec3> up,
                                      std::optional<Vec3> metric) const {
        tc_mesh* mesh = surface_edge_mesh(*this, "find an aligned surface edge");
        if (!mesh) {
            return std::nullopt;
        }
        PackedSurfaceEdgeInputs packed;
        tc_mesh_surface_edge_query query{};
        if (!try_pack_surface_edge_angle(max_angle_degrees, query.max_angle_degrees)) {
            return std::nullopt;
        }
        if (!try_pack_surface_edge_inputs(point, up, metric, packed) ||
            !try_pack_surface_edge_direction(normal, "normal", query.normal) ||
            !try_pack_surface_edge_direction(edge_direction, "edge direction", query.edge_direction)) {
            return std::nullopt;
        }
        if (!validate_surface_edge_metric_product(query.edge_direction, packed.metric, "edge direction")) {
            return std::nullopt;
        }

        query.start_triangle = start_triangle;
        query.point = packed.point;
        query.up = packed.up;
        query.metric = packed.metric;
        query.use_direction_filter = true;

        tc_mesh_surface_edge_hit hit{};
        if (!tc_mesh_find_surface_edge_query(mesh, &query, &hit)) {
            return std::nullopt;
        }
        return unpack_surface_edge_hit(hit);
    }

    std::optional<TcMeshSurfaceEdgeHit> TcMesh::find_nearest_surface_edge(const Vec3& point,
                                                                          std::optional<Vec3> up,
                                                                          std::optional<Vec3> metric) const {
        tc_mesh* mesh = surface_edge_mesh(*this, "find the nearest surface edge");
        if (!mesh) {
            return std::nullopt;
        }

        PackedSurfaceEdgeInputs packed;
        if (!try_pack_surface_edge_inputs(point, up, metric, packed)) {
            return std::nullopt;
        }

        tc_mesh_surface_edge_hit hit{};
        if (!tc_mesh_find_nearest_surface_edge_metric(mesh, packed.point, packed.up, packed.metric, &hit)) {
            return std::nullopt;
        }
        return unpack_surface_edge_hit(hit);
    }

    TcMesh TcMesh::from_mesh3(const Mesh3& mesh,
                              const std::string& override_name,
                              const std::string& override_uuid,
                              const tc_vertex_layout* custom_layout) {
        if (mesh.vertices.empty()) {
            return TcMesh();
        }

        // Use override_uuid if provided, otherwise use mesh.uuid
        std::string uuid_str = override_uuid.empty() ? mesh.uuid : override_uuid;

        // Check if already in registry
        if (!uuid_str.empty()) {
            tc_mesh_handle h = tc_mesh_find(uuid_str.c_str());
            if (!tc_mesh_handle_is_invalid(h)) {
                return TcMesh(h);
            }
        }

        // Keep the default mesh layout compatible with PBR shaders. Missing tangents
        // stay zero-filled in the interleaved buffer below.
        tc_vertex_layout layout;
        if (custom_layout) {
            layout = *custom_layout;
        } else {
            layout = tc_vertex_layout_pos_normal_uv_tangent();
        }

        // Build interleaved vertex buffer
        size_t num_verts = mesh.vertices.size();
        size_t stride = layout.stride;
        std::vector<uint8_t> buffer(num_verts * stride, 0);

        const tc_vertex_attrib* pos_attr = tc_vertex_layout_find(&layout, "position");
        const tc_vertex_attrib* norm_attr = tc_vertex_layout_find(&layout, "normal");
        const tc_vertex_attrib* uv_attr = tc_vertex_layout_find(&layout, "uv");
        const tc_vertex_attrib* tan_attr = tc_vertex_layout_find(&layout, "tangent");

        for (size_t i = 0; i < num_verts; i++) {
            uint8_t* dst = buffer.data() + i * stride;

            // Position
            if (pos_attr) {
                float* p = reinterpret_cast<float*>(dst + pos_attr->offset);
                p[0] = mesh.vertices[i].x;
                p[1] = mesh.vertices[i].y;
                p[2] = mesh.vertices[i].z;
            }

            // Normal
            if (norm_attr && i < mesh.normals.size()) {
                float* n = reinterpret_cast<float*>(dst + norm_attr->offset);
                n[0] = mesh.normals[i].x;
                n[1] = mesh.normals[i].y;
                n[2] = mesh.normals[i].z;
            }

            // UV
            if (uv_attr && i < mesh.uvs.size()) {
                float* u = reinterpret_cast<float*>(dst + uv_attr->offset);
                u[0] = mesh.uvs[i].x;
                u[1] = mesh.uvs[i].y;
            }

            // Tangent
            if (tan_attr && i < mesh.tangents.size()) {
                float* t = reinterpret_cast<float*>(dst + tan_attr->offset);
                t[0] = mesh.tangents[i].x;
                t[1] = mesh.tangents[i].y;
                t[2] = mesh.tangents[i].z;
                t[3] = mesh.tangents[i].w;
            }
        }

        // Compute UUID from data if not provided
        if (uuid_str.empty()) {
            char computed_uuid[TC_UUID_SIZE];
            tc_mesh_compute_uuid(
                buffer.data(), buffer.size(), mesh.triangles.data(), mesh.triangles.size(), computed_uuid);
            uuid_str = computed_uuid;
        }

        // Get or create mesh in registry
        tc_mesh_handle h = tc_mesh_get_or_create(uuid_str.c_str());
        tc_mesh* m = tc_mesh_get(h);
        if (!m) {
            return TcMesh();
        }

        // Set data if mesh is new (vertex_count == 0)
        if (m->vertex_count == 0) {
            std::string mesh_name = override_name.empty() ? mesh.name : override_name;
            tc_mesh_set_data(m,
                             buffer.data(),
                             num_verts,
                             &layout,
                             mesh.triangles.data(),
                             mesh.triangles.size(),
                             mesh_name.empty() ? nullptr : mesh_name.c_str());
        }

        return TcMesh(h);
    }

    TcMesh TcMesh::from_interleaved(const TcMeshCreateInfo& create_info) {
        const TcMeshInterleavedDataView& data = create_info.data;

        if (data.vertices == nullptr || data.vertex_count == 0 || data.layout == nullptr) {
            return TcMesh();
        }

        // Use uuid_hint if provided, otherwise compute from data
        std::string uuid_str = create_info.uuid_hint;

        // Check if already in registry
        if (!uuid_str.empty()) {
            tc_mesh_handle h = tc_mesh_find(uuid_str.c_str());
            if (!tc_mesh_handle_is_invalid(h)) {
                TcMesh mesh(h);
                set_mesh_submeshes(mesh, create_info);
                return mesh;
            }
        }

        // Compute UUID from data if not provided
        if (uuid_str.empty()) {
            size_t vertices_size = data.vertex_count * data.layout->stride;
            char computed_uuid[TC_UUID_SIZE];
            tc_mesh_compute_uuid(data.vertices, vertices_size, data.indices, data.index_count, computed_uuid);
            uuid_str = computed_uuid;
        }

        // Get or create mesh in registry
        tc_mesh_handle h = tc_mesh_get_or_create(uuid_str.c_str());
        tc_mesh* m = tc_mesh_get(h);
        if (!m) {
            return TcMesh();
        }

        // Set data if mesh is new (vertex_count == 0)
        if (m->vertex_count == 0) {
            tc_mesh_set_data(m,
                             data.vertices,
                             data.vertex_count,
                             data.layout,
                             data.indices,
                             data.index_count,
                             create_info.name.empty() ? nullptr : create_info.name.c_str());
            m->draw_mode = static_cast<uint8_t>(create_info.draw_mode);
        }

        TcMesh mesh(h);
        if (!mesh.is_valid()) {
            return mesh;
        }

        set_mesh_submeshes(mesh, create_info);
        return mesh;
    }

} // namespace termin
