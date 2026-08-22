#pragma once

// TcMesh - RAII wrapper with handle-based access to tc_mesh
// Uses tc_mesh_handle with generation checking for safety

#include <tcbase/tc_log.h>
#include <tcbase/tc_value.h>
#include <tgfx/resources/tc_mesh.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <termin/geom/ray3.hpp>

#include <array>
#include <cstring>
#include <optional>
#include <string>
#include <tgfx/tgfx_api.h>
#include <vector>

namespace termin {

    // Forward declaration
    class Mesh3;

    struct TcMeshInterleavedDataView {
        const void* vertices = nullptr;
        size_t vertex_count = 0;
        const uint32_t* indices = nullptr;
        size_t index_count = 0;
        const tc_vertex_layout* layout = nullptr;
    };

    struct TcMeshCreateInfo {
        TcMeshInterleavedDataView data;
        const tc_submesh* submeshes = nullptr;
        size_t submesh_count = 0;
        std::string name;
        std::string uuid_hint;
        tc_draw_mode draw_mode = TC_DRAW_TRIANGLES;
    };

    /** Rich result of a mesh-local metric raycast. */
    struct TcMeshRayHit {
        double distance = 0.0;
        Vec3 position{};
        Vec3 normal{};
        Vec3 barycentric{};
        uint32_t triangle_index = 0;
        std::array<uint32_t, 3> indices{};
    };

    /** Rich result of a mesh-local surface-edge query. */
    struct TcMeshSurfaceEdgeHit {
        Vec3 point{};
        std::array<uint32_t, 2> indices{};
        double distance = 0.0;
        int32_t side = 0;
    };

    // TcMesh - GPU-ready mesh wrapper
    // Stores handle (index + generation) instead of raw pointer
    class TGFX_API TcMesh {
    public:
        tc_mesh_handle handle = tc_mesh_handle_invalid();

        TcMesh() = default;

        explicit TcMesh(tc_mesh_handle h)
            : handle(h) {
            if (tc_mesh* m = tc_mesh_get(handle)) {
                tc_mesh_add_ref(m);
            }
        }

        // Construct from raw pointer (finds handle for it)
        explicit TcMesh(tc_mesh* m) {
            if (m) {
                handle = tc_mesh_find(m->header.uuid);
                tc_mesh_add_ref(m);
            }
        }

        TcMesh(const TcMesh& other)
            : handle(other.handle) {
            if (tc_mesh* m = tc_mesh_get(handle)) {
                tc_mesh_add_ref(m);
            }
        }

        TcMesh(TcMesh&& other) noexcept
            : handle(other.handle) {
            other.handle = tc_mesh_handle_invalid();
        }

        TcMesh& operator=(const TcMesh& other) {
            if (this != &other) {
                if (tc_mesh* m = tc_mesh_get(handle)) {
                    tc_mesh_release(m);
                }
                handle = other.handle;
                if (tc_mesh* m = tc_mesh_get(handle)) {
                    tc_mesh_add_ref(m);
                }
            }
            return *this;
        }

        TcMesh& operator=(TcMesh&& other) noexcept {
            if (this != &other) {
                if (tc_mesh* m = tc_mesh_get(handle)) {
                    tc_mesh_release(m);
                }
                handle = other.handle;
                other.handle = tc_mesh_handle_invalid();
            }
            return *this;
        }

        ~TcMesh() {
            if (tc_mesh* m = tc_mesh_get(handle)) {
                tc_mesh_release(m);
            }
            handle = tc_mesh_handle_invalid();
        }

        // Get raw pointer (may return nullptr if handle is stale)
        tc_mesh* get() const {
            return tc_mesh_get(handle);
        }

        // For backwards compatibility
        tc_mesh* mesh_ptr() const {
            return get();
        }

        // Query (safe - returns defaults if handle is stale)
        bool is_valid() const {
            return tc_mesh_is_valid(handle);
        }

        const char* uuid() const {
            tc_mesh* m = get();
            return m ? m->header.uuid : "";
        }

        const char* name() const {
            tc_mesh* m = get();
            return (m && m->header.name) ? m->header.name : "";
        }

        uint32_t version() const {
            tc_mesh* m = get();
            return m ? m->header.version : 0;
        }

        size_t vertex_count() const {
            tc_mesh* m = get();
            return m ? m->vertex_count : 0;
        }

        size_t index_count() const {
            tc_mesh* m = get();
            return m ? m->index_count : 0;
        }

        size_t triangle_count() const {
            tc_mesh* m = get();
            return m ? m->index_count / 3 : 0;
        }

        uint16_t stride() const {
            tc_mesh* m = get();
            return m ? m->layout.stride : 0;
        }

        const tc_vertex_layout* layout() const {
            tc_mesh* m = get();
            return m ? &m->layout : nullptr;
        }

        tc_draw_mode draw_mode() const {
            tc_mesh* m = get();
            return m ? static_cast<tc_draw_mode>(m->draw_mode) : TC_DRAW_TRIANGLES;
        }

        size_t submesh_count() const {
            tc_mesh* m = get();
            return m ? tc_mesh_get_submesh_count(m) : 0;
        }

        const tc_submesh* submesh(size_t index) const {
            tc_mesh* m = get();
            return m ? tc_mesh_get_submesh(m, index) : nullptr;
        }

        bool set_submeshes(const std::vector<tc_submesh>& submeshes) {
            tc_mesh* m = get();
            if (!m)
                return false;
            return tc_mesh_set_submeshes(m, submeshes.data(), submeshes.size());
        }

        void set_draw_mode(tc_draw_mode mode) {
            if (tc_mesh* m = get()) {
                m->draw_mode = static_cast<uint8_t>(mode);
                if (m->submesh_count == 1) {
                    m->submeshes[0].draw_mode = static_cast<uint8_t>(mode);
                }
            }
        }

        void bump_version() {
            if (tc_mesh* m = get()) {
                m->header.version++;
            }
        }

        // Trigger lazy load if mesh is declared but not loaded
        bool ensure_loaded() {
            return tc_mesh_ensure_loaded(handle);
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
            tc_value_dict_set(&d, "kind", tc_value_string("tc_mesh"));
            return d;
        }

        void deserialize_from(const tc_value* data, void* = nullptr) {
            if (tc_mesh* m = tc_mesh_get(handle)) {
                tc_mesh_release(m);
            }
            handle = tc_mesh_handle_invalid();

            if (!data)
                return;

            if (data->type == TC_VALUE_STRING && data->data.s && data->data.s[0]) {
                const char* mesh_name = data->data.s;
                if (strcmp(mesh_name, "(None)") == 0)
                    return;

                tc_mesh_handle h = tc_mesh_find_by_name(mesh_name);
                if (!tc_mesh_handle_is_invalid(h)) {
                    handle = h;
                    if (tc_mesh* m = tc_mesh_get(handle)) {
                        tc_mesh_add_ref(m);
                    }
                } else {
                    tc_log_error("[TcMesh] Mesh '%s' not found", mesh_name);
                }
                return;
            }

            if (data->type != TC_VALUE_DICT)
                return;

            tc_value* uuid_val = tc_value_dict_get(const_cast<tc_value*>(data), "uuid");
            if (uuid_val && uuid_val->type == TC_VALUE_STRING && uuid_val->data.s) {
                tc_mesh_handle h = tc_mesh_find(uuid_val->data.s);
                if (!tc_mesh_handle_is_invalid(h)) {
                    handle = h;
                    if (tc_mesh* m = tc_mesh_get(handle)) {
                        tc_mesh_add_ref(m);
                    }
                    ensure_loaded();
                    return;
                }
            }

            tc_value* name_val = tc_value_dict_get(const_cast<tc_value*>(data), "name");
            if (name_val && name_val->type == TC_VALUE_STRING && name_val->data.s) {
                const char* mesh_name = name_val->data.s;
                tc_mesh_handle h = tc_mesh_find_by_name(mesh_name);
                if (!tc_mesh_handle_is_invalid(h)) {
                    handle = h;
                    if (tc_mesh* m = tc_mesh_get(handle)) {
                        tc_mesh_add_ref(m);
                    }
                    ensure_loaded();
                } else {
                    tc_log_error("[TcMesh] Mesh '%s' not found", mesh_name);
                }
            }
        }

        // Populate existing TcMesh with data from Mesh3
        bool set_from_mesh3(const Mesh3& mesh, const tc_vertex_layout* custom_layout = nullptr);

        /**
         * Finds the nearest triangle hit in the closed metric-distance range.
         *
         * Direction magnitude is ignored. For a non-unit direction, position
         * is origin + normalized(direction) * distance rather than
         * ray.point_at(distance). Range endpoints are rounded inward at the
         * packed-float boundary. Invalid inputs are logged and return no hit.
         */
        [[nodiscard]] std::optional<TcMeshRayHit>
        raycast(const Ray3& ray, double min_distance = 0.0, double max_distance = 1000000.0) const;

        /**
         * Finds the nearest boundary edge of the connected surface containing
         * start_triangle. Direction magnitudes are ignored; metric contains
         * finite per-axis distance multipliers no smaller than 1e-8. Invalid
         * inputs are logged and return no hit. Points and tangent directions
         * transform by metric; normals transform by its inverse transpose.
         */
        [[nodiscard]] std::optional<TcMeshSurfaceEdgeHit>
        find_surface_edge(uint32_t start_triangle,
                          const Vec3& point,
                          const Vec3& normal,
                          std::optional<Vec3> up = std::nullopt,
                          std::optional<Vec3> metric = std::nullopt) const;

        /** Same query, restricted to unoriented edge directions within [0, 90] degrees. */
        [[nodiscard]] std::optional<TcMeshSurfaceEdgeHit>
        find_surface_edge_aligned(uint32_t start_triangle,
                                  const Vec3& point,
                                  const Vec3& normal,
                                  const Vec3& edge_direction,
                                  double max_angle_degrees,
                                  std::optional<Vec3> up = std::nullopt,
                                  std::optional<Vec3> metric = std::nullopt) const;

        /** Finds the nearest surface first when no starting triangle is available. */
        [[nodiscard]] std::optional<TcMeshSurfaceEdgeHit>
        find_nearest_surface_edge(const Vec3& point,
                                  std::optional<Vec3> up = std::nullopt,
                                  std::optional<Vec3> metric = std::nullopt) const;

        // Create TcMesh from Mesh3 (CPU mesh)
        static TcMesh from_mesh3(const Mesh3& mesh,
                                 const std::string& override_name = "",
                                 const std::string& override_uuid = "",
                                 const tc_vertex_layout* custom_layout = nullptr);

        // Create TcMesh from raw interleaved vertex data.
        static TcMesh from_interleaved(const TcMeshCreateInfo& create_info);

        // Get by UUID from registry
        static TcMesh from_uuid(const std::string& uuid) {
            tc_mesh_handle h = tc_mesh_find(uuid.c_str());
            if (tc_mesh_handle_is_invalid(h)) {
                return TcMesh();
            }
            return TcMesh(h);
        }

        // Get or create by UUID
        static TcMesh get_or_create(const std::string& uuid) {
            tc_mesh_handle h = tc_mesh_get_or_create(uuid.c_str());
            if (tc_mesh_handle_is_invalid(h)) {
                return TcMesh();
            }
            return TcMesh(h);
        }
    };

} // namespace termin
