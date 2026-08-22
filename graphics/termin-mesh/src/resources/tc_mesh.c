// tc_mesh.c - Mesh reference counting and UUID computation
#include "tgfx/resources/tc_mesh.h"
#include "tgfx/resources/tc_mesh_registry.h"
#include <float.h>
#include <geom/tc_vec3f.h>
#include <limits.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tcbase/tc_log.h>

// ============================================================================
// Reference counting
// ============================================================================

void tc_mesh_add_ref(tc_mesh* mesh) {
    if (mesh) {
        mesh->header.ref_count++;
    }
}

bool tc_mesh_release(tc_mesh* mesh) {
    if (!mesh) {
        return false;
    }
    if (mesh->header.ref_count == 0) {
        tc_log(TC_LOG_WARN,
               "[tc_mesh_release] uuid=%s name=%s refcount already zero!",
               mesh->header.uuid,
               mesh->header.name ? mesh->header.name : "(null)");
        return false;
    }

    mesh->header.ref_count--;

    if (mesh->header.ref_count == 0) {
        tc_mesh_remove(mesh->header.uuid);
        return true;
    }
    return false;
}

// ============================================================================
// UUID computation (FNV-1a hash)
// ============================================================================

static uint64_t fnv1a_hash(const uint8_t* data, size_t len) {
    uint64_t hash = 14695981039346656037ULL;
    for (size_t i = 0; i < len; i++) {
        hash ^= data[i];
        hash *= 1099511628211ULL;
    }
    return hash;
}

void tc_mesh_compute_uuid(
    const void* vertices, size_t vertex_size, const uint32_t* indices, size_t index_count, char* uuid_out) {
    // Hash vertices
    uint64_t h1 = fnv1a_hash((const uint8_t*)vertices, vertex_size);

    // Hash indices
    uint64_t h2 = fnv1a_hash((const uint8_t*)indices, index_count * sizeof(uint32_t));

    // Combine hashes
    uint64_t combined = h1 ^ (h2 * 1099511628211ULL);

    // Format as hex string (16 chars)
    snprintf(uuid_out, 40, "%016llx", (unsigned long long)combined);
}

// ============================================================================
// Mesh queries
// ============================================================================

static bool tc_mesh_vec3f_normalize(tc_vec3f* v) {
    return v && tc_vec3f_try_normalized(*v, 1.0e-10f, v);
}

static bool tc_mesh_vec3f_is_zero_metric(tc_vec3f metric) {
    return fabsf(metric.x) <= 1e-8f && fabsf(metric.y) <= 1e-8f && fabsf(metric.z) <= 1e-8f;
}

static tc_vec3f tc_mesh_make_metric(tc_vec3f metric) {
    if (tc_mesh_vec3f_is_zero_metric(metric)) {
        return tc_vec3f_one();
    }
    return tc_vec3f_new(fabsf(metric.x) > 1e-8f ? fabsf(metric.x) : 1e-8f,
                        fabsf(metric.y) > 1e-8f ? fabsf(metric.y) : 1e-8f,
                        fabsf(metric.z) > 1e-8f ? fabsf(metric.z) : 1e-8f);
}

static bool tc_mesh_vec3f_try_metric_direction(tc_vec3f direction,
                                               tc_vec3f metric,
                                               tc_vec3f* out_direction) {
    tc_vec3f original_direction;
    tc_vec3f metric_direction;
    if (!out_direction || !tc_vec3f_try_normalized(direction, 1.0e-10f, &original_direction) ||
        !tc_vec3f_try_cwise_product(original_direction, metric, &metric_direction) ||
        !tc_mesh_vec3f_normalize(&metric_direction)) {
        return false;
    }
    *out_direction = metric_direction;
    return true;
}

static bool tc_mesh_vec3f_try_metric_normal(tc_vec3f normal, tc_vec3f metric, tc_vec3f* out_normal) {
    if (!out_normal || !tc_vec3f_is_finite(metric) || metric.x <= 0.0f || metric.y <= 0.0f ||
        metric.z <= 0.0f) {
        return false;
    }

    tc_vec3f original_normal;
    if (!tc_vec3f_try_normalized(normal, 1.0e-10f, &original_normal)) {
        return false;
    }
    const tc_vec3f inverse_metric = tc_vec3f_new(1.0f / metric.x, 1.0f / metric.y, 1.0f / metric.z);
    tc_vec3f metric_normal;
    if (!tc_vec3f_is_finite(inverse_metric) ||
        !tc_vec3f_try_cwise_product(original_normal, inverse_metric, &metric_normal) ||
        !tc_mesh_vec3f_normalize(&metric_normal)) {
        return false;
    }
    *out_normal = metric_normal;
    return true;
}

static bool tc_mesh_vec3f_try_metric_edge_direction(
    tc_vec3f a, tc_vec3f b, tc_vec3f metric, tc_vec3f* out_direction) {
    if (!out_direction || !tc_vec3f_is_finite(a) || !tc_vec3f_is_finite(b)) {
        return false;
    }
    const tc_vec3f direction = tc_vec3f_sub(b, a);
    if (!tc_vec3f_is_finite(direction)) {
        return false;
    }
    return tc_mesh_vec3f_try_metric_direction(direction, metric, out_direction);
}

static bool tc_mesh_vec3f_try_mesh_normal(
    tc_vec3f a, tc_vec3f b, tc_vec3f c, tc_vec3f* out_normal) {
    if (!out_normal || !tc_vec3f_is_finite(a) || !tc_vec3f_is_finite(b) || !tc_vec3f_is_finite(c)) {
        return false;
    }
    const tc_vec3f ab = tc_vec3f_sub(b, a);
    const tc_vec3f ac = tc_vec3f_sub(c, a);
    tc_vec3f normal = tc_vec3f_cross(ab, ac);
    if (!tc_vec3f_is_finite(ab) || !tc_vec3f_is_finite(ac) || !tc_vec3f_is_finite(normal) ||
        !tc_mesh_vec3f_normalize(&normal)) {
        return false;
    }
    *out_normal = normal;
    return true;
}

static bool tc_mesh_closest_point_on_segment_metric(
    tc_vec3f point, tc_vec3f a, tc_vec3f b, tc_vec3f metric, tc_vec3f* out_point, float* out_distance) {
    if (!out_point || !out_distance) {
        return false;
    }
    tc_vec3f point_m;
    tc_vec3f a_m;
    tc_vec3f b_m;
    if (!tc_vec3f_try_cwise_product(point, metric, &point_m) ||
        !tc_vec3f_try_cwise_product(a, metric, &a_m) || !tc_vec3f_try_cwise_product(b, metric, &b_m)) {
        return false;
    }
    tc_vec3f ab_m = tc_vec3f_sub(b_m, a_m);
    tc_vec3f ap_m = tc_vec3f_sub(point_m, a_m);
    if (!tc_vec3f_is_finite(ab_m) || !tc_vec3f_is_finite(ap_m)) {
        return false;
    }
    float denom = tc_vec3f_dot(ab_m, ab_m);
    float t = 0.0f;
    if (!isfinite(denom) || denom < 0.0f) {
        return false;
    }
    if (denom > 1e-12f) {
        const float numerator = tc_vec3f_dot(ap_m, ab_m);
        if (!isfinite(numerator)) {
            return false;
        }
        t = numerator / denom;
        if (!isfinite(t)) {
            return false;
        }
        if (t < 0.0f)
            t = 0.0f;
        if (t > 1.0f)
            t = 1.0f;
    }

    tc_vec3f ab = tc_vec3f_sub(b, a);
    tc_vec3f candidate = tc_vec3f_add(a, tc_vec3f_scale(ab, t));
    tc_vec3f candidate_m;
    if (!tc_vec3f_is_finite(ab) || !tc_vec3f_is_finite(candidate) ||
        !tc_vec3f_try_cwise_product(candidate, metric, &candidate_m)) {
        return false;
    }
    tc_vec3f delta_m = tc_vec3f_sub(candidate_m, point_m);
    const float distance_sq = tc_vec3f_dot(delta_m, delta_m);
    if (!tc_vec3f_is_finite(delta_m) || !isfinite(distance_sq) || distance_sq < 0.0f) {
        return false;
    }
    const float distance = sqrtf(distance_sq);
    if (!isfinite(distance)) {
        return false;
    }
    *out_point = candidate;
    *out_distance = distance;
    return true;
}

static bool tc_mesh_closest_point_on_triangle(
    tc_vec3f point, tc_vec3f a, tc_vec3f b, tc_vec3f c, tc_vec3f* out_point, float* out_distance) {
    if (!out_point || !out_distance || !tc_vec3f_is_finite(point) || !tc_vec3f_is_finite(a) ||
        !tc_vec3f_is_finite(b) || !tc_vec3f_is_finite(c)) {
        return false;
    }
    tc_vec3f candidate;
    tc_vec3f ab = tc_vec3f_sub(b, a);
    tc_vec3f ac = tc_vec3f_sub(c, a);
    tc_vec3f ap = tc_vec3f_sub(point, a);
    float d1 = tc_vec3f_dot(ab, ap);
    float d2 = tc_vec3f_dot(ac, ap);
    if (!tc_vec3f_is_finite(ab) || !tc_vec3f_is_finite(ac) || !tc_vec3f_is_finite(ap) || !isfinite(d1) ||
        !isfinite(d2)) {
        return false;
    }
    if (d1 <= 0.0f && d2 <= 0.0f) {
        candidate = a;
    } else {
        tc_vec3f bp = tc_vec3f_sub(point, b);
        float d3 = tc_vec3f_dot(ab, bp);
        float d4 = tc_vec3f_dot(ac, bp);
        if (!tc_vec3f_is_finite(bp) || !isfinite(d3) || !isfinite(d4)) {
            return false;
        }
        if (d3 >= 0.0f && d4 <= d3) {
            candidate = b;
        } else {
            float vc = d1 * d4 - d3 * d2;
            if (!isfinite(vc)) {
                return false;
            }
            if (vc <= 0.0f && d1 >= 0.0f && d3 <= 0.0f) {
                float v = d1 / (d1 - d3);
                if (!isfinite(v)) {
                    return false;
                }
                candidate = tc_vec3f_add(a, tc_vec3f_scale(ab, v));
            } else {
                tc_vec3f cp = tc_vec3f_sub(point, c);
                float d5 = tc_vec3f_dot(ab, cp);
                float d6 = tc_vec3f_dot(ac, cp);
                if (!tc_vec3f_is_finite(cp) || !isfinite(d5) || !isfinite(d6)) {
                    return false;
                }
                if (d6 >= 0.0f && d5 <= d6) {
                    candidate = c;
                } else {
                    float vb = d5 * d2 - d1 * d6;
                    if (!isfinite(vb)) {
                        return false;
                    }
                    if (vb <= 0.0f && d2 >= 0.0f && d6 <= 0.0f) {
                        float w = d2 / (d2 - d6);
                        if (!isfinite(w)) {
                            return false;
                        }
                        candidate = tc_vec3f_add(a, tc_vec3f_scale(ac, w));
                    } else {
                        float va = d3 * d6 - d5 * d4;
                        if (!isfinite(va)) {
                            return false;
                        }
                        if (va <= 0.0f && (d4 - d3) >= 0.0f && (d5 - d6) >= 0.0f) {
                            tc_vec3f bc = tc_vec3f_sub(c, b);
                            const float denominator = (d4 - d3) + (d5 - d6);
                            if (!tc_vec3f_is_finite(bc) || !isfinite(denominator) || denominator == 0.0f) {
                                return false;
                            }
                            float w = (d4 - d3) / denominator;
                            if (!isfinite(w)) {
                                return false;
                            }
                            candidate = tc_vec3f_add(b, tc_vec3f_scale(bc, w));
                        } else {
                            const float denominator = va + vb + vc;
                            if (!isfinite(denominator) || denominator == 0.0f) {
                                return false;
                            }
                            float denom = 1.0f / denominator;
                            float v = vb * denom;
                            float w = vc * denom;
                            if (!isfinite(denom) || !isfinite(v) || !isfinite(w)) {
                                return false;
                            }
                            tc_vec3f sum = tc_vec3f_add(a, tc_vec3f_scale(ab, v));
                            if (!tc_vec3f_is_finite(sum)) {
                                return false;
                            }
                            candidate = tc_vec3f_add(sum, tc_vec3f_scale(ac, w));
                        }
                    }
                }
            }
        }
    }

    tc_vec3f delta = tc_vec3f_sub(candidate, point);
    const float distance_sq = tc_vec3f_dot(delta, delta);
    if (!tc_vec3f_is_finite(candidate) || !tc_vec3f_is_finite(delta) || !isfinite(distance_sq) ||
        distance_sq < 0.0f) {
        return false;
    }
    const float distance = sqrtf(distance_sq);
    if (!isfinite(distance)) {
        return false;
    }
    *out_point = candidate;
    *out_distance = distance;
    return true;
}

static bool tc_mesh_triangle_indices(const tc_mesh* mesh, uint32_t tri, uint32_t out[3]) {
    if (!mesh || !out || !mesh->indices || mesh->draw_mode != TC_DRAW_TRIANGLES ||
        (size_t)tri > (SIZE_MAX - 2u) / 3u) {
        return false;
    }
    size_t first = (size_t)tri * 3;
    if (first + 2 >= mesh->index_count) {
        return false;
    }
    out[0] = mesh->indices[first];
    out[1] = mesh->indices[first + 1];
    out[2] = mesh->indices[first + 2];
    return out[0] < mesh->vertex_count && out[1] < mesh->vertex_count && out[2] < mesh->vertex_count;
}

static bool tc_mesh_triangle_normals(const tc_mesh* mesh,
                                     uint32_t tri,
                                     tc_vec3f metric,
                                     tc_vec3f* out_mesh_normal,
                                     tc_vec3f* out_metric_normal) {
    tc_vec3f a;
    tc_vec3f b;
    tc_vec3f c;
    tc_vec3f a_m;
    tc_vec3f b_m;
    tc_vec3f c_m;
    tc_vec3f mesh_normal;
    tc_vec3f metric_normal;
    // Surface traversal stores original vertices, but all accepted triangles
    // must also be representable after applying the measurement metric.
    if (!out_mesh_normal || !out_metric_normal || !tc_mesh_get_triangle3f(mesh, tri, &a, &b, &c) ||
        !tc_mesh_vec3f_try_mesh_normal(a, b, c, &mesh_normal) ||
        !tc_mesh_vec3f_try_metric_normal(mesh_normal, metric, &metric_normal) ||
        !tc_vec3f_try_cwise_product(a, metric, &a_m) || !tc_vec3f_try_cwise_product(b, metric, &b_m) ||
        !tc_vec3f_try_cwise_product(c, metric, &c_m)) {
        return false;
    }
    *out_mesh_normal = mesh_normal;
    *out_metric_normal = metric_normal;
    return true;
}

typedef struct tc_mesh_edge_adjacency {
    uint64_t hash;
    int64_t key[6];
    uint32_t a;
    uint32_t b;
    uint32_t tris[2];
    uint32_t count;
} tc_mesh_edge_adjacency;

static bool tc_mesh_quantize_coord(float value, int64_t* out_quantized) {
    if (!out_quantized || !isfinite(value)) {
        return false;
    }
    const double inv_epsilon = 100000.0;
    const double scaled = (double)value * inv_epsilon;
    const double safe_min = nextafter((double)LLONG_MIN, 0.0);
    const double safe_max = nextafter((double)LLONG_MAX, 0.0);
    if (!isfinite(scaled) || scaled < safe_min || scaled > safe_max) {
        return false;
    }
    const long long rounded = llround(scaled);
    if (rounded < INT64_MIN || rounded > INT64_MAX) {
        return false;
    }
    *out_quantized = (int64_t)rounded;
    return true;
}

static bool tc_mesh_endpoint_less(const int64_t a[3], const int64_t b[3]) {
    if (a[0] != b[0])
        return a[0] < b[0];
    if (a[1] != b[1])
        return a[1] < b[1];
    return a[2] < b[2];
}

static uint64_t tc_mesh_hash_edge_key(const int64_t key[6]) {
    uint64_t hash = 14695981039346656037ULL;
    for (size_t i = 0; i < 6; ++i) {
        uint64_t value = (uint64_t)key[i];
        for (int byte = 0; byte < 8; ++byte) {
            hash ^= (uint8_t)((value >> (byte * 8)) & 0xFFu);
            hash *= 1099511628211ULL;
        }
    }
    return hash;
}

static bool
tc_mesh_make_geometric_edge_key(const tc_mesh* mesh, uint32_t a, uint32_t b, int64_t out_key[6], uint64_t* out_hash) {
    tc_vec3f pa;
    tc_vec3f pb;
    if (!tc_mesh_get_position3f(mesh, a, &pa) || !tc_mesh_get_position3f(mesh, b, &pb)) {
        return false;
    }

    int64_t qa[3];
    int64_t qb[3];
    if (!tc_vec3f_is_finite(pa) || !tc_vec3f_is_finite(pb) || !tc_mesh_quantize_coord(pa.x, &qa[0]) ||
        !tc_mesh_quantize_coord(pa.y, &qa[1]) || !tc_mesh_quantize_coord(pa.z, &qa[2]) ||
        !tc_mesh_quantize_coord(pb.x, &qb[0]) || !tc_mesh_quantize_coord(pb.y, &qb[1]) ||
        !tc_mesh_quantize_coord(pb.z, &qb[2])) {
        return false;
    }

    const int64_t* first = qa;
    const int64_t* second = qb;
    if (tc_mesh_endpoint_less(qb, qa)) {
        first = qb;
        second = qa;
    }
    out_key[0] = first[0];
    out_key[1] = first[1];
    out_key[2] = first[2];
    out_key[3] = second[0];
    out_key[4] = second[1];
    out_key[5] = second[2];
    *out_hash = tc_mesh_hash_edge_key(out_key);
    return true;
}

static tc_mesh_edge_adjacency*
tc_mesh_find_edge_record(tc_mesh_edge_adjacency* edges, size_t edge_count, const int64_t key[6], uint64_t hash) {
    for (size_t i = 0; i < edge_count; ++i) {
        if (edges[i].hash == hash && memcmp(edges[i].key, key, sizeof(int64_t) * 6) == 0) {
            return &edges[i];
        }
    }
    return NULL;
}

static bool tc_mesh_add_prepared_edge_record(tc_mesh_edge_adjacency* edges,
                                             size_t* edge_count,
                                             size_t edge_capacity,
                                             const int64_t key[6],
                                             uint64_t hash,
                                             uint32_t a,
                                             uint32_t b,
                                             uint32_t tri) {
    if (!edges || !edge_count || !key) {
        return false;
    }
    tc_mesh_edge_adjacency* edge = tc_mesh_find_edge_record(edges, *edge_count, key, hash);
    if (!edge) {
        if (*edge_count >= edge_capacity) {
            return false;
        }
        edge = &edges[*edge_count];
        (*edge_count)++;
        edge->hash = hash;
        memcpy(edge->key, key, sizeof(edge->key));
        edge->a = a;
        edge->b = b;
        edge->tris[0] = tri;
        edge->tris[1] = 0;
        edge->count = 1;
        return true;
    }
    if (edge->count < 2) {
        edge->tris[edge->count] = tri;
    }
    edge->count++;
    return true;
}

static bool tc_mesh_is_boundary_edge(const tc_mesh* mesh,
                                     const tc_mesh_edge_adjacency* edges,
                                     size_t edge_count,
                                     const bool* accepted,
                                     uint32_t tri,
                                     uint32_t a,
                                     uint32_t b) {
    int64_t key[6];
    uint64_t hash = 0;
    if (!tc_mesh_make_geometric_edge_key(mesh, a, b, key, &hash)) {
        return false;
    }
    const tc_mesh_edge_adjacency* edge =
        tc_mesh_find_edge_record((tc_mesh_edge_adjacency*)edges, edge_count, key, hash);
    if (!edge) {
        return true;
    }
    size_t count = edge->count < 2 ? edge->count : 2;
    for (size_t i = 0; i < count; ++i) {
        uint32_t neighbor = edge->tris[i];
        if (neighbor != tri && accepted[neighbor]) {
            return false;
        }
    }
    return true;
}

bool tc_mesh_get_position3f(const tc_mesh* mesh, uint32_t vertex_index, tc_vec3f* out_position) {
    if (!mesh || !out_position || !mesh->vertices || vertex_index >= mesh->vertex_count) {
        return false;
    }

    const tc_vertex_attrib* pos = tc_vertex_layout_find(&mesh->layout, "position");
    if (!pos || pos->type != TC_ATTRIB_FLOAT32 || pos->size < 3) {
        return false;
    }

    const uint8_t* base = (const uint8_t*)mesh->vertices;
    const float* p = (const float*)(base + ((size_t)vertex_index * mesh->layout.stride) + pos->offset);
    *out_position = tc_vec3f_new(p[0], p[1], p[2]);
    return true;
}

bool tc_mesh_get_triangle3f(
    const tc_mesh* mesh, uint32_t triangle_index, tc_vec3f* out_a, tc_vec3f* out_b, tc_vec3f* out_c) {
    if (!mesh || !out_a || !out_b || !out_c || !mesh->indices) {
        return false;
    }
    if (mesh->draw_mode != TC_DRAW_TRIANGLES) {
        return false;
    }

    if ((size_t)triangle_index > (SIZE_MAX - 2u) / 3u) {
        return false;
    }
    size_t first_index = (size_t)triangle_index * 3;
    if (first_index + 2 >= mesh->index_count) {
        return false;
    }

    uint32_t i0 = mesh->indices[first_index];
    uint32_t i1 = mesh->indices[first_index + 1];
    uint32_t i2 = mesh->indices[first_index + 2];

    return tc_mesh_get_position3f(mesh, i0, out_a) && tc_mesh_get_position3f(mesh, i1, out_b) &&
           tc_mesh_get_position3f(mesh, i2, out_c);
}

static bool tc_mesh_hit_is_finite(const tc_mesh_hit* hit) {
    return hit && isfinite(hit->t) && tc_vec3f_is_finite(hit->position) && tc_vec3f_is_finite(hit->normal) &&
           tc_vec3f_is_finite(hit->barycentric);
}

bool tc_mesh_raycast(const tc_mesh* mesh, const tc_mesh_ray* ray, tc_mesh_hit* out_hit) {
    if (!mesh || !ray || !out_hit) {
        tc_log(TC_LOG_ERROR, "tc_mesh_raycast: mesh, ray, and out_hit are required");
        return false;
    }
    if (!tc_vec3f_is_finite(ray->origin)) {
        tc_log(TC_LOG_ERROR, "tc_mesh_raycast: ray origin must contain only finite values");
        return false;
    }

    tc_vec3f dir;
    if (!tc_vec3f_try_normalized(ray->direction, 1.0e-10f, &dir)) {
        tc_log(TC_LOG_ERROR, "tc_mesh_raycast: ray direction must be finite and non-degenerate");
        return false;
    }
    if (!isfinite(ray->t_min) || !isfinite(ray->t_max)) {
        tc_log(TC_LOG_ERROR,
               "tc_mesh_raycast: ray range must be finite (t_min=%.9g, t_max=%.9g)",
               (double)ray->t_min,
               (double)ray->t_max);
        return false;
    }
    if (ray->t_min > ray->t_max) {
        tc_log(TC_LOG_ERROR,
               "tc_mesh_raycast: ray range must satisfy t_min <= t_max (t_min=%.9g, t_max=%.9g)",
               (double)ray->t_min,
               (double)ray->t_max);
        return false;
    }
    if (mesh->draw_mode != TC_DRAW_TRIANGLES) {
        return false;
    }
    if (!tc_mesh_ensure_loaded_ptr((tc_mesh*)mesh)) {
        return false;
    }
    if (!mesh->indices || !mesh->vertices) {
        return false;
    }

    const tc_vertex_attrib* pos = tc_vertex_layout_find(&mesh->layout, "position");
    if (!pos || pos->type != TC_ATTRIB_FLOAT32 || pos->size < 3) {
        return false;
    }

    const float t_min = ray->t_min;
    const float t_max = ray->t_max;
    float best_t = t_max;
    tc_mesh_hit best_hit;
    memset(&best_hit, 0, sizeof(best_hit));
    // This stays a dedicated float C-ABI/storage specialization rather than
    // calling the double-precision Ray3 helper per packed vertex. Besides the
    // hot-loop representation, this API owns t_min/t_max and returns position,
    // normal, barycentric coordinates, triangle index and source indices.
    bool found = false;

    const size_t triangle_count = mesh->index_count / 3;
    const float epsilon = 1e-7f;

    for (size_t tri = 0; tri < triangle_count; ++tri) {
        const size_t base_index = tri * 3;
        const uint32_t i0 = mesh->indices[base_index];
        const uint32_t i1 = mesh->indices[base_index + 1];
        const uint32_t i2 = mesh->indices[base_index + 2];
        if (i0 >= mesh->vertex_count || i1 >= mesh->vertex_count || i2 >= mesh->vertex_count) {
            continue;
        }

        tc_vec3f v0;
        tc_vec3f v1;
        tc_vec3f v2;
        if (!tc_mesh_get_position3f(mesh, i0, &v0) || !tc_mesh_get_position3f(mesh, i1, &v1) ||
            !tc_mesh_get_position3f(mesh, i2, &v2)) {
            continue;
        }
        if (!tc_vec3f_is_finite(v0) || !tc_vec3f_is_finite(v1) || !tc_vec3f_is_finite(v2)) {
            continue;
        }

        tc_vec3f edge1 = tc_vec3f_sub(v1, v0);
        tc_vec3f edge2 = tc_vec3f_sub(v2, v0);
        tc_vec3f pvec = tc_vec3f_cross(dir, edge2);
        if (!tc_vec3f_is_finite(edge1) || !tc_vec3f_is_finite(edge2) || !tc_vec3f_is_finite(pvec)) {
            continue;
        }

        float det = tc_vec3f_dot(edge1, pvec);
        if (!isfinite(det) || fabsf(det) < epsilon) {
            continue;
        }

        float inv_det = 1.0f / det;
        tc_vec3f tvec = tc_vec3f_sub(ray->origin, v0);
        if (!isfinite(inv_det) || !tc_vec3f_is_finite(tvec)) {
            continue;
        }

        float u = tc_vec3f_dot(tvec, pvec) * inv_det;
        if (!isfinite(u) || u < 0.0f || u > 1.0f) {
            continue;
        }

        tc_vec3f qvec = tc_vec3f_cross(tvec, edge1);
        if (!tc_vec3f_is_finite(qvec)) {
            continue;
        }

        float v = tc_vec3f_dot(dir, qvec) * inv_det;
        if (!isfinite(v) || v < 0.0f || u + v > 1.0f) {
            continue;
        }

        float t = tc_vec3f_dot(edge2, qvec) * inv_det;
        if (!isfinite(t) || t < t_min || t > best_t) {
            continue;
        }

        tc_vec3f normal = tc_vec3f_cross(edge1, edge2);
        if (!tc_mesh_vec3f_normalize(&normal)) {
            continue;
        }

        tc_mesh_hit candidate;
        memset(&candidate, 0, sizeof(candidate));
        candidate.t = t;
        candidate.position = tc_vec3f_add(ray->origin, tc_vec3f_scale(dir, t));
        candidate.normal = normal;
        candidate.barycentric = tc_vec3f_new(1.0f - u - v, u, v);
        candidate.triangle_index = (uint32_t)tri;
        candidate.indices[0] = i0;
        candidate.indices[1] = i1;
        candidate.indices[2] = i2;
        if (!tc_mesh_hit_is_finite(&candidate)) {
            continue;
        }

        best_t = t;
        best_hit = candidate;
        found = true;
    }

    if (!found || !tc_mesh_hit_is_finite(&best_hit)) {
        return false;
    }

    *out_hit = best_hit;
    return true;
}

static bool tc_mesh_surface_edge_validate_vec3(
    const char* api_name, const char* field_name, tc_vec3f value, bool require_direction) {
    if (!tc_vec3f_is_finite(value)) {
        tc_log(TC_LOG_ERROR, "%s: %s must contain only finite values", api_name, field_name);
        return false;
    }
    if (require_direction) {
        tc_vec3f normalized;
        if (!tc_vec3f_try_normalized(value, 1.0e-10f, &normalized)) {
            tc_log(TC_LOG_ERROR, "%s: %s must be non-degenerate", api_name, field_name);
            return false;
        }
    }
    return true;
}

static bool tc_mesh_surface_edge_validate_query(const char* api_name,
                                                const tc_mesh* mesh,
                                                const tc_mesh_surface_edge_query* query,
                                                tc_mesh_surface_edge_hit* out_hit) {
    if (!mesh || !query || !out_hit) {
        tc_log(TC_LOG_ERROR, "%s: mesh, query, and out_hit are required", api_name);
        return false;
    }
    if (!tc_mesh_surface_edge_validate_vec3(api_name, "point", query->point, false) ||
        !tc_mesh_surface_edge_validate_vec3(api_name, "normal", query->normal, true) ||
        !tc_mesh_surface_edge_validate_vec3(api_name, "up", query->up, true) ||
        !tc_mesh_surface_edge_validate_vec3(api_name, "metric", query->metric, false)) {
        return false;
    }
    if (query->use_direction_filter) {
        if (!tc_mesh_surface_edge_validate_vec3(api_name, "edge_direction", query->edge_direction, true)) {
            return false;
        }
        if (!isfinite(query->max_angle_degrees)) {
            tc_log(TC_LOG_ERROR, "%s: max_angle_degrees must be finite", api_name);
            return false;
        }
    }
    return true;
}

static bool tc_mesh_surface_edge_validate_nearest(const char* api_name,
                                                  const tc_mesh* mesh,
                                                  tc_vec3f point,
                                                  tc_vec3f up,
                                                  tc_vec3f metric,
                                                  tc_mesh_surface_edge_hit* out_hit) {
    if (!mesh || !out_hit) {
        tc_log(TC_LOG_ERROR, "%s: mesh and out_hit are required", api_name);
        return false;
    }
    return tc_mesh_surface_edge_validate_vec3(api_name, "point", point, false) &&
           tc_mesh_surface_edge_validate_vec3(api_name, "up", up, true) &&
           tc_mesh_surface_edge_validate_vec3(api_name, "metric", metric, false);
}

static bool tc_mesh_surface_edge_hit_is_finite(const tc_mesh_surface_edge_hit* hit) {
    return hit && tc_vec3f_is_finite(hit->point) && isfinite(hit->distance);
}

static bool tc_mesh_find_surface_edge_filtered(const char* api_name,
                                               const tc_mesh* mesh,
                                               const tc_mesh_surface_edge_query* query,
                                               tc_mesh_surface_edge_hit* out_hit) {
    if (!mesh || !query || !out_hit) {
        return false;
    }
    if (mesh->draw_mode != TC_DRAW_TRIANGLES) {
        return false;
    }
    if (!tc_mesh_ensure_loaded_ptr((tc_mesh*)mesh)) {
        return false;
    }
    if (!mesh->indices || !mesh->vertices) {
        return false;
    }

    size_t triangle_count = mesh->index_count / 3;
    if (query->start_triangle >= triangle_count) {
        tc_log(TC_LOG_ERROR,
               "%s: start_triangle is outside the mesh (start_triangle=%u, triangle_count=%zu)",
               api_name,
               query->start_triangle,
               triangle_count);
        return false;
    }

    tc_vec3f query_metric = tc_mesh_make_metric(query->metric);
    tc_vec3f point_m;
    tc_vec3f local_up_m;
    tc_vec3f n0_m;
    if (!tc_vec3f_try_cwise_product(query->point, query_metric, &point_m)) {
        tc_log(TC_LOG_ERROR, "%s: metric-space point overflows or underflows float representation", api_name);
        return false;
    }
    if (!tc_mesh_vec3f_try_metric_direction(query->up, query_metric, &local_up_m) ||
        !tc_mesh_vec3f_try_metric_normal(query->normal, query_metric, &n0_m)) {
        tc_log(TC_LOG_ERROR, "%s: metric collapses normal or up to a degenerate direction", api_name);
        return false;
    }
    tc_vec3f desired_edge_direction = tc_vec3f_zero();
    float min_edge_direction_dot = -1.0f;
    if (query->use_direction_filter) {
        if (!tc_mesh_vec3f_try_metric_direction(
                query->edge_direction, query_metric, &desired_edge_direction)) {
            tc_log(TC_LOG_ERROR, "%s: metric collapses edge_direction to a degenerate direction", api_name);
            return false;
        }
        float max_angle_degrees = query->max_angle_degrees;
        if (max_angle_degrees < 0.0f) {
            max_angle_degrees = 0.0f;
        }
        if (max_angle_degrees > 90.0f) {
            max_angle_degrees = 90.0f;
        }
        min_edge_direction_dot = cosf(max_angle_degrees * 0.01745329251994329577f);
        if (!isfinite(min_edge_direction_dot)) {
            return false;
        }
    }

    if (triangle_count > UINT32_MAX || triangle_count > SIZE_MAX / 3u) {
        tc_log(TC_LOG_ERROR, "%s: mesh topology is too large for surface-edge traversal", api_name);
        return false;
    }
    const size_t edge_capacity = triangle_count * 3u;
    if (edge_capacity > SIZE_MAX / sizeof(tc_mesh_edge_adjacency) ||
        triangle_count > SIZE_MAX / sizeof(tc_vec3f) || triangle_count > SIZE_MAX / sizeof(bool) ||
        triangle_count > SIZE_MAX / sizeof(uint32_t)) {
        tc_log(TC_LOG_ERROR, "%s: mesh topology allocation size overflows size_t", api_name);
        return false;
    }

    tc_mesh_edge_adjacency* edges = (tc_mesh_edge_adjacency*)calloc(edge_capacity, sizeof(tc_mesh_edge_adjacency));
    tc_vec3f* normals = (tc_vec3f*)calloc(triangle_count, sizeof(tc_vec3f));
    bool* has_normal = (bool*)calloc(triangle_count, sizeof(bool));
    bool* accepted = (bool*)calloc(triangle_count, sizeof(bool));
    uint32_t* queue = (uint32_t*)calloc(triangle_count, sizeof(uint32_t));
    if (!edges || !normals || !has_normal || !accepted || !queue) {
        tc_log(TC_LOG_ERROR, "%s: failed to allocate surface-edge traversal state", api_name);
        free(edges);
        free(normals);
        free(has_normal);
        free(accepted);
        free(queue);
        return false;
    }

    size_t edge_count = 0;
    for (uint32_t tri = 0; tri < (uint32_t)triangle_count; ++tri) {
        uint32_t idx[3];
        if (!tc_mesh_triangle_indices(mesh, tri, idx)) {
            continue;
        }
        int64_t checked_keys[3][6];
        uint64_t checked_hashes[3];
        tc_vec3f mesh_normal;
        tc_vec3f* metric_normal = &normals[tri];
        if (!tc_mesh_make_geometric_edge_key(mesh, idx[0], idx[1], checked_keys[0], &checked_hashes[0]) ||
            !tc_mesh_make_geometric_edge_key(mesh, idx[1], idx[2], checked_keys[1], &checked_hashes[1]) ||
            !tc_mesh_make_geometric_edge_key(mesh, idx[2], idx[0], checked_keys[2], &checked_hashes[2]) ||
            !tc_mesh_triangle_normals(mesh, tri, query_metric, &mesh_normal, metric_normal) ||
            edge_count > edge_capacity || edge_capacity - edge_count < 3u) {
            continue;
        }
        if (!tc_mesh_add_prepared_edge_record(edges,
                                              &edge_count,
                                              edge_capacity,
                                              checked_keys[0],
                                              checked_hashes[0],
                                              idx[0],
                                              idx[1],
                                              tri) ||
            !tc_mesh_add_prepared_edge_record(edges,
                                              &edge_count,
                                              edge_capacity,
                                              checked_keys[1],
                                              checked_hashes[1],
                                              idx[1],
                                              idx[2],
                                              tri) ||
            !tc_mesh_add_prepared_edge_record(edges,
                                              &edge_count,
                                              edge_capacity,
                                              checked_keys[2],
                                              checked_hashes[2],
                                              idx[2],
                                              idx[0],
                                              tri)) {
            continue;
        }
        has_normal[tri] = true;
    }

    if (!has_normal[query->start_triangle]) {
        free(edges);
        free(normals);
        free(has_normal);
        free(accepted);
        free(queue);
        return false;
    }

    const float normal_cos_threshold = 0.9063077870366499f;
    const float plane_distance_threshold = 0.05f;
    size_t queue_begin = 0;
    size_t queue_end = 0;
    accepted[query->start_triangle] = true;
    queue[queue_end++] = query->start_triangle;

    while (queue_begin < queue_end) {
        uint32_t tri = queue[queue_begin++];
        uint32_t idx[3];
        if (!tc_mesh_triangle_indices(mesh, tri, idx)) {
            continue;
        }

        for (int e = 0; e < 3; ++e) {
            uint32_t a = idx[e];
            uint32_t b = idx[(e + 1) % 3];
            int64_t edge_key[6];
            uint64_t edge_hash = 0;
            if (!tc_mesh_make_geometric_edge_key(mesh, a, b, edge_key, &edge_hash)) {
                continue;
            }
            tc_mesh_edge_adjacency* edge = tc_mesh_find_edge_record(edges, edge_count, edge_key, edge_hash);
            if (!edge) {
                continue;
            }
            size_t count = edge->count < 2 ? edge->count : 2;
            for (size_t i = 0; i < count; ++i) {
                uint32_t next = edge->tris[i];
                if (next == tri || accepted[next] || !has_normal[next]) {
                    continue;
                }
                tc_vec3f next_normal = normals[next];
                const float normal_dot = tc_vec3f_dot(next_normal, n0_m);
                if (!isfinite(normal_dot) || normal_dot < normal_cos_threshold) {
                    continue;
                }

                uint32_t next_idx[3];
                tc_vec3f v0;
                tc_vec3f v0_m;
                if (!tc_mesh_triangle_indices(mesh, next, next_idx) ||
                    !tc_mesh_get_position3f(mesh, next_idx[0], &v0) || !tc_vec3f_is_finite(v0) ||
                    !tc_vec3f_try_cwise_product(v0, query_metric, &v0_m)) {
                    continue;
                }
                tc_vec3f to_v0 = tc_vec3f_sub(v0_m, point_m);
                const float plane_distance = tc_vec3f_dot(to_v0, n0_m);
                if (!tc_vec3f_is_finite(to_v0) || !isfinite(plane_distance) ||
                    fabsf(plane_distance) > plane_distance_threshold) {
                    continue;
                }

                accepted[next] = true;
                queue[queue_end++] = next;
            }
        }
    }

    bool found = false;
    float best_distance = FLT_MAX;
    tc_vec3f best_point = tc_vec3f_zero();
    uint32_t best_a = 0;
    uint32_t best_b = 0;
    int32_t best_side = 0;

    const float up_dot = tc_vec3f_dot(n0_m, local_up_m);
    tc_vec3f up_part = tc_vec3f_scale(local_up_m, up_dot);
    tc_vec3f horizontal_normal = tc_vec3f_sub(n0_m, up_part);
    const float horizontal_length_sq = tc_vec3f_length_sq(horizontal_normal);
    bool has_tangent = isfinite(up_dot) && tc_vec3f_is_finite(up_part) && tc_vec3f_is_finite(horizontal_normal) &&
                       isfinite(horizontal_length_sq) && horizontal_length_sq > 1e-12f;
    tc_vec3f tangent = tc_vec3f_zero();
    if (has_tangent) {
        tc_mesh_vec3f_normalize(&horizontal_normal);
        tangent = tc_vec3f_cross(local_up_m, horizontal_normal);
        has_tangent = tc_mesh_vec3f_normalize(&tangent);
    }

    for (uint32_t tri = 0; tri < (uint32_t)triangle_count; ++tri) {
        if (!accepted[tri]) {
            continue;
        }
        uint32_t idx[3];
        if (!tc_mesh_triangle_indices(mesh, tri, idx)) {
            continue;
        }
        for (int e = 0; e < 3; ++e) {
            uint32_t ia = idx[e];
            uint32_t ib = idx[(e + 1) % 3];
            if (!tc_mesh_is_boundary_edge(mesh, edges, edge_count, accepted, tri, ia, ib)) {
                continue;
            }

            tc_vec3f a;
            tc_vec3f b;
            if (!tc_mesh_get_position3f(mesh, ia, &a) || !tc_mesh_get_position3f(mesh, ib, &b) ||
                !tc_vec3f_is_finite(a) || !tc_vec3f_is_finite(b)) {
                continue;
            }
            if (query->use_direction_filter) {
                tc_vec3f edge_dir;
                if (!tc_mesh_vec3f_try_metric_edge_direction(a, b, query_metric, &edge_dir)) {
                    continue;
                }
                const float direction_dot = fabsf(tc_vec3f_dot(edge_dir, desired_edge_direction));
                if (!isfinite(direction_dot) || direction_dot < min_edge_direction_dot) {
                    continue;
                }
            }

            tc_vec3f candidate;
            float distance = FLT_MAX;
            if (!tc_mesh_closest_point_on_segment_metric(
                    query->point, a, b, query_metric, &candidate, &distance) ||
                !tc_vec3f_is_finite(candidate) || !isfinite(distance)) {
                continue;
            }
            if (distance < best_distance) {
                int32_t candidate_side = 0;
                if (has_tangent) {
                    tc_vec3f candidate_m;
                    if (!tc_vec3f_try_cwise_product(candidate, query_metric, &candidate_m)) {
                        continue;
                    }
                    tc_vec3f delta = tc_vec3f_sub(candidate_m, point_m);
                    float s = tc_vec3f_dot(delta, tangent);
                    if (!tc_vec3f_is_finite(delta) || !isfinite(s)) {
                        continue;
                    } else if (s > 1e-5f) {
                        candidate_side = 1;
                    } else if (s < -1e-5f) {
                        candidate_side = -1;
                    }
                }
                best_distance = distance;
                best_point = candidate;
                best_a = ia;
                best_b = ib;
                best_side = candidate_side;
                found = true;
            }
        }
    }

    free(edges);
    free(normals);
    free(has_normal);
    free(accepted);
    free(queue);
    if (!found) {
        return false;
    }

    const tc_mesh_surface_edge_hit best_hit = {
        .point = best_point,
        .indices = {best_a, best_b},
        .distance = best_distance,
        .side = best_side,
    };
    if (!tc_mesh_surface_edge_hit_is_finite(&best_hit)) {
        return false;
    }
    *out_hit = best_hit;
    return true;
}

static bool tc_mesh_find_surface_edge_checked(const char* api_name,
                                              const tc_mesh* mesh,
                                              const tc_mesh_surface_edge_query* query,
                                              tc_mesh_surface_edge_hit* out_hit) {
    if (!tc_mesh_surface_edge_validate_query(api_name, mesh, query, out_hit)) {
        return false;
    }
    return tc_mesh_find_surface_edge_filtered(api_name, mesh, query, out_hit);
}

bool tc_mesh_find_surface_edge(const tc_mesh* mesh,
                               uint32_t start_triangle,
                               tc_vec3f point,
                               tc_vec3f normal,
                               tc_vec3f up,
                               tc_mesh_surface_edge_hit* out_hit) {
    tc_mesh_surface_edge_query query = {0};
    query.start_triangle = start_triangle;
    query.point = point;
    query.normal = normal;
    query.up = up;
    query.metric = tc_vec3f_one();
    return tc_mesh_find_surface_edge_checked("tc_mesh_find_surface_edge", mesh, &query, out_hit);
}

bool tc_mesh_find_surface_edge_metric(const tc_mesh* mesh,
                                      uint32_t start_triangle,
                                      tc_vec3f point,
                                      tc_vec3f normal,
                                      tc_vec3f up,
                                      tc_vec3f metric,
                                      tc_mesh_surface_edge_hit* out_hit) {
    tc_mesh_surface_edge_query query = {0};
    query.start_triangle = start_triangle;
    query.point = point;
    query.normal = normal;
    query.up = up;
    query.metric = metric;
    return tc_mesh_find_surface_edge_checked("tc_mesh_find_surface_edge_metric", mesh, &query, out_hit);
}

bool tc_mesh_find_surface_edge_query(const tc_mesh* mesh,
                                     const tc_mesh_surface_edge_query* query,
                                     tc_mesh_surface_edge_hit* out_hit) {
    return tc_mesh_find_surface_edge_checked("tc_mesh_find_surface_edge_query", mesh, query, out_hit);
}

bool tc_mesh_find_surface_edge_aligned(const tc_mesh* mesh,
                                       const tc_mesh_surface_edge_query* query,
                                       tc_mesh_surface_edge_hit* out_hit) {
    if (!query) {
        tc_log(TC_LOG_ERROR, "tc_mesh_find_surface_edge_aligned: query is required");
        return false;
    }
    tc_mesh_surface_edge_query aligned_query = *query;
    aligned_query.use_direction_filter = true;
    return tc_mesh_find_surface_edge_checked("tc_mesh_find_surface_edge_aligned", mesh, &aligned_query, out_hit);
}

static bool tc_mesh_find_nearest_surface_edge_checked(const char* api_name,
                                                      const tc_mesh* mesh,
                                                      tc_vec3f point,
                                                      tc_vec3f up,
                                                      tc_vec3f metric,
                                                      tc_mesh_surface_edge_hit* out_hit) {
    if (!tc_mesh_surface_edge_validate_nearest(api_name, mesh, point, up, metric, out_hit)) {
        return false;
    }
    if (mesh->draw_mode != TC_DRAW_TRIANGLES) {
        return false;
    }
    if (!tc_mesh_ensure_loaded_ptr((tc_mesh*)mesh)) {
        return false;
    }
    if (!mesh->indices || !mesh->vertices) {
        return false;
    }

    size_t triangle_count = mesh->index_count / 3;
    if (triangle_count > UINT32_MAX) {
        tc_log(TC_LOG_ERROR, "%s: mesh topology is too large for surface-edge traversal", api_name);
        return false;
    }
    tc_vec3f query_metric = tc_mesh_make_metric(metric);
    tc_vec3f point_m;
    if (!tc_vec3f_try_cwise_product(point, query_metric, &point_m)) {
        tc_log(TC_LOG_ERROR, "%s: metric-space point overflows or underflows float representation", api_name);
        return false;
    }

    bool found = false;
    uint32_t best_triangle = 0;
    float best_distance = FLT_MAX;
    tc_vec3f best_mesh_normal = tc_vec3f_zero();

    for (uint32_t tri = 0; tri < (uint32_t)triangle_count; ++tri) {
        tc_vec3f a;
        tc_vec3f b;
        tc_vec3f c;
        uint32_t idx[3];
        int64_t checked_key[6];
        uint64_t checked_hash = 0;
        if (!tc_mesh_triangle_indices(mesh, tri, idx) || !tc_mesh_get_triangle3f(mesh, tri, &a, &b, &c) ||
            !tc_vec3f_is_finite(a) || !tc_vec3f_is_finite(b) || !tc_vec3f_is_finite(c) ||
            !tc_mesh_make_geometric_edge_key(mesh, idx[0], idx[1], checked_key, &checked_hash) ||
            !tc_mesh_make_geometric_edge_key(mesh, idx[1], idx[2], checked_key, &checked_hash) ||
            !tc_mesh_make_geometric_edge_key(mesh, idx[2], idx[0], checked_key, &checked_hash)) {
            continue;
        }

        tc_vec3f a_m;
        tc_vec3f b_m;
        tc_vec3f c_m;
        if (!tc_vec3f_try_cwise_product(a, query_metric, &a_m) ||
            !tc_vec3f_try_cwise_product(b, query_metric, &b_m) ||
            !tc_vec3f_try_cwise_product(c, query_metric, &c_m)) {
            continue;
        }
        tc_vec3f closest;
        float distance = FLT_MAX;
        if (!tc_mesh_closest_point_on_triangle(point_m, a_m, b_m, c_m, &closest, &distance) ||
            !tc_vec3f_is_finite(closest) || !isfinite(distance) || distance >= best_distance) {
            continue;
        }

        tc_vec3f mesh_normal;
        tc_vec3f metric_normal;
        if (!tc_mesh_triangle_normals(mesh, tri, query_metric, &mesh_normal, &metric_normal)) {
            continue;
        }

        best_distance = distance;
        best_triangle = tri;
        best_mesh_normal = mesh_normal;
        found = true;
    }

    if (!found) {
        return false;
    }

    tc_mesh_surface_edge_query query = {0};
    query.start_triangle = best_triangle;
    query.point = point;
    query.normal = best_mesh_normal;
    query.up = up;
    query.metric = query_metric;
    return tc_mesh_find_surface_edge_filtered(api_name, mesh, &query, out_hit);
}

bool tc_mesh_find_nearest_surface_edge(const tc_mesh* mesh,
                                       tc_vec3f point,
                                       tc_vec3f up,
                                       tc_mesh_surface_edge_hit* out_hit) {
    return tc_mesh_find_nearest_surface_edge_checked(
        "tc_mesh_find_nearest_surface_edge", mesh, point, up, tc_vec3f_one(), out_hit);
}

bool tc_mesh_find_nearest_surface_edge_metric(
    const tc_mesh* mesh, tc_vec3f point, tc_vec3f up, tc_vec3f metric, tc_mesh_surface_edge_hit* out_hit) {
    return tc_mesh_find_nearest_surface_edge_checked(
        "tc_mesh_find_nearest_surface_edge_metric", mesh, point, up, metric, out_hit);
}
