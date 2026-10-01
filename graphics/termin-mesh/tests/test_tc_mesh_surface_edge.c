#include "guard_c.h"

#include <float.h>
#include <geom/tc_vec3f.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <tcbase/tc_log.h>
#include <tgfx/resources/tc_mesh.h>

static int g_error_log_count = 0;
static char g_last_error[256];

static void capture_error_log(tc_log_level level, const char* message) {
    if (level == TC_LOG_ERROR) {
        ++g_error_log_count;
        snprintf(g_last_error, sizeof(g_last_error), "%s", message ? message : "");
    }
}

static void begin_log_capture(void) {
    g_error_log_count = 0;
    g_last_error[0] = '\0';
    tc_log_set_callback(capture_error_log);
}

static void end_log_capture(void) {
    tc_log_set_callback(NULL);
}

static tc_mesh make_mesh(float* vertices,
                         size_t vertex_count,
                         uint32_t* indices,
                         size_t index_count) {
    tc_mesh mesh;
    memset(&mesh, 0, sizeof(mesh));
    mesh.header.is_loaded = 1;
    mesh.vertices = vertices;
    mesh.vertex_count = vertex_count;
    mesh.indices = indices;
    mesh.index_count = index_count;
    mesh.layout = tc_vertex_layout_pos();
    mesh.draw_mode = TC_DRAW_TRIANGLES;
    return mesh;
}

static tc_mesh_surface_edge_query make_query(void) {
    const tc_mesh_surface_edge_query query = {
        .start_triangle = 0,
        .point = {0.1f, 0.5f, 0.0f},
        .normal = {0.0f, 0.0f, 1.0f},
        .up = {0.0f, 1.0f, 0.0f},
        .metric = {1.0f, 1.0f, 1.0f},
    };
    return query;
}

static int hit_is_finite(const tc_mesh_surface_edge_hit* hit) {
    return hit && isfinite(hit->point.x) && isfinite(hit->point.y) && isfinite(hit->point.z) &&
           isfinite(hit->distance);
}

static void check_left_edge_hit(const tc_mesh_surface_edge_hit* hit, float expected_distance) {
    GUARD_C_CHECK(hit_is_finite(hit));
    GUARD_C_CHECK_NEAR_DOUBLE(0.0, hit->point.x, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.5, hit->point.y, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.0, hit->point.z, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(expected_distance, hit->distance, 1e-6);
    GUARD_C_CHECK((hit->indices[0] == 0 && hit->indices[1] == 2) ||
                  (hit->indices[0] == 2 && hit->indices[1] == 0));
    GUARD_C_CHECK_EQ_INT(-1, hit->side);
}

static void make_hit_sentinel(tc_mesh_surface_edge_hit* hit, unsigned char bytes[sizeof(*hit)]) {
    memset(bytes, 0xA5, sizeof(*hit));
    memcpy(hit, bytes, sizeof(*hit));
}

static void check_rejected_call(int result,
                                const tc_mesh_surface_edge_hit* hit,
                                const unsigned char original[sizeof(*hit)],
                                const char* api_name,
                                int require_log) {
    GUARD_C_CHECK_FALSE(result);
    GUARD_C_CHECK(memcmp(hit, original, sizeof(*hit)) == 0);
    if (require_log) {
        GUARD_C_CHECK(g_error_log_count > 0);
        GUARD_C_CHECK(strstr(g_last_error, api_name) != NULL);
    } else {
        GUARD_C_CHECK_EQ_INT(0, g_error_log_count);
    }
}

#define EXPECT_REJECTED(call_, api_name_)                                                                              \
    do {                                                                                                                \
        tc_mesh_surface_edge_hit hit_;                                                                                  \
        unsigned char original_[sizeof(hit_)];                                                                          \
        make_hit_sentinel(&hit_, original_);                                                                            \
        begin_log_capture();                                                                                            \
        const int result_ = (call_);                                                                                    \
        end_log_capture();                                                                                              \
        check_rejected_call(result_, &hit_, original_, (api_name_), 1);                                                \
    } while (0)

#define EXPECT_SILENT_MISS(call_)                                                                                       \
    do {                                                                                                                \
        tc_mesh_surface_edge_hit hit_;                                                                                  \
        unsigned char original_[sizeof(hit_)];                                                                          \
        make_hit_sentinel(&hit_, original_);                                                                            \
        begin_log_capture();                                                                                            \
        const int result_ = (call_);                                                                                    \
        end_log_capture();                                                                                              \
        check_rejected_call(result_, &hit_, original_, "", 0);                                                        \
    } while (0)

GUARD_C_TEST(test_surface_edge_reports_rich_finite_hits_and_preserves_c_semantics) {
    float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
        1.0f, 1.0f, 0.0f,
    };
    uint32_t indices[] = {0, 1, 2, 2, 1, 3};
    const tc_mesh mesh = make_mesh(vertices, 4, indices, 6);
    tc_mesh_surface_edge_query query = make_query();
    tc_mesh_surface_edge_hit hit;

    GUARD_C_REQUIRE(tc_mesh_find_surface_edge_query(&mesh, &query, &hit));
    check_left_edge_hit(&hit, 0.1f);

    query.metric = (tc_vec3f){2.0f, 1.0f, 1.0f};
    GUARD_C_REQUIRE(tc_mesh_find_surface_edge_query(&mesh, &query, &hit));
    check_left_edge_hit(&hit, 0.2f);

    query.metric = tc_vec3f_zero();
    GUARD_C_REQUIRE(tc_mesh_find_surface_edge_query(&mesh, &query, &hit));
    check_left_edge_hit(&hit, 0.1f);

    query = make_query();
    query.edge_direction = (tc_vec3f){0.0f, 1000.0f, 0.0f};
    query.max_angle_degrees = -20.0f;
    GUARD_C_REQUIRE(tc_mesh_find_surface_edge_aligned(&mesh, &query, &hit));
    check_left_edge_hit(&hit, 0.1f);

    query.max_angle_degrees = 120.0f;
    GUARD_C_REQUIRE(tc_mesh_find_surface_edge_aligned(&mesh, &query, &hit));
    check_left_edge_hit(&hit, 0.1f);

    GUARD_C_REQUIRE(tc_mesh_find_nearest_surface_edge(
        &mesh, (tc_vec3f){0.1f, 0.5f, 0.0f}, (tc_vec3f){0.0f, 1.0f, 0.0f}, &hit));
    check_left_edge_hit(&hit, 0.1f);
    return 0;
}

GUARD_C_TEST(test_anisotropic_metric_uses_covector_normals_across_internal_diagonal) {
    // A unit parameter-space rectangle in the plane x+y=0, split along edge
    // (1,2). With M=(100,1,1), the query is 0.1 metric units from that internal
    // diagonal but 0.5 from either external Z edge. Treating normal as M*n
    // incorrectly disconnects the triangles and exposes the internal edge.
    float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, -1.0f, 0.0f,
        0.0f, 0.0f, 1.0f,
        1.0f, -1.0f, 1.0f,
    };
    uint32_t indices[] = {0, 1, 2, 2, 1, 3};
    const tc_mesh mesh = make_mesh(vertices, 4, indices, 6);
    const tc_vec3f point = {0.4f, -0.4f, 0.5f};
    const tc_vec3f normal = {-7.0f, -7.0f, 0.0f};
    const tc_vec3f up = {0.0f, 0.0f, 5.0f};
    const tc_vec3f metric = {100.0f, 1.0f, 1.0f};
    tc_mesh_surface_edge_hit hit;

    GUARD_C_REQUIRE(tc_mesh_find_surface_edge_metric(&mesh, 0, point, normal, up, metric, &hit));
    GUARD_C_CHECK(hit_is_finite(&hit));
    GUARD_C_CHECK_NEAR_DOUBLE(0.5, hit.distance, 1e-4);
    GUARD_C_CHECK_FALSE((hit.indices[0] == 1 && hit.indices[1] == 2) ||
                        (hit.indices[0] == 2 && hit.indices[1] == 1));

    GUARD_C_REQUIRE(tc_mesh_find_nearest_surface_edge_metric(&mesh, point, up, metric, &hit));
    GUARD_C_CHECK(hit_is_finite(&hit));
    GUARD_C_CHECK_NEAR_DOUBLE(0.5, hit.distance, 1e-4);
    GUARD_C_CHECK_FALSE((hit.indices[0] == 1 && hit.indices[1] == 2) ||
                        (hit.indices[0] == 2 && hit.indices[1] == 1));
    return 0;
}

GUARD_C_TEST(test_surface_edge_welds_seam_split_coplanar_triangles) {
    // The shared diagonal has distinct indices and sub-quantization offsets.
    // It must remain internal after welding by the existing geometric key.
    float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
        0.000003f, 1.0f, 0.0f,
        1.0f, 0.000003f, 0.0f,
        1.0f, 1.0f, 0.0f,
    };
    uint32_t indices[] = {0, 1, 2, 3, 4, 5};
    const tc_mesh mesh = make_mesh(vertices, 6, indices, 6);
    tc_mesh_surface_edge_query query = make_query();
    query.point.x = 0.4f;
    tc_mesh_surface_edge_hit hit;
    for (uint32_t start = 0; start < 2; ++start) {
        query.start_triangle = start;
        GUARD_C_REQUIRE(tc_mesh_find_surface_edge_query(&mesh, &query, &hit));
        check_left_edge_hit(&hit, 0.4f);
    }
    query.edge_direction = tc_vec3f_unit_y();
    query.max_angle_degrees = 0.0f;
    GUARD_C_REQUIRE(tc_mesh_find_surface_edge_aligned(&mesh, &query, &hit));
    check_left_edge_hit(&hit, 0.4f);
    GUARD_C_REQUIRE(tc_mesh_find_nearest_surface_edge(&mesh, query.point, query.up, &hit));
    check_left_edge_hit(&hit, 0.4f);
    return 0;
}

GUARD_C_TEST(test_surface_edge_preserves_first_two_nonmanifold_neighbors) {
    float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
        0.0f, -1.0f, 0.0f,
        1.0f, 1.0f, 0.0f,
    };
    // All three CCW triangles share (0,1). Only the first two are stored as
    // neighbors, so traversal from either of them does not reach triangle 2.
    uint32_t indices[] = {0, 1, 2, 1, 0, 3, 0, 1, 4};
    const tc_mesh mesh = make_mesh(vertices, 5, indices, 9);
    tc_mesh_surface_edge_query query = make_query();
    query.point = (tc_vec3f){0.6f, 0.55f, 0.0f};
    tc_mesh_surface_edge_hit hit;
    for (uint32_t start = 0; start < 2; ++start) {
        query.start_triangle = start;
        GUARD_C_REQUIRE(tc_mesh_find_surface_edge_query(&mesh, &query, &hit));
        GUARD_C_CHECK_NEAR_DOUBLE(0.525, hit.point.x, 1e-6);
        GUARD_C_CHECK_NEAR_DOUBLE(0.475, hit.point.y, 1e-6);
        GUARD_C_CHECK_NEAR_DOUBLE(sqrt(0.01125), hit.distance, 1e-6);
        GUARD_C_CHECK_EQ_INT(1, hit.indices[0]);
        GUARD_C_CHECK_EQ_INT(2, hit.indices[1]);
    }
    // Starting on the third triangle can still reach the first two. Its
    // unshared (4,0) edge is then the nearest boundary of that larger surface.
    query.start_triangle = 2;
    GUARD_C_REQUIRE(tc_mesh_find_surface_edge_query(&mesh, &query, &hit));
    GUARD_C_CHECK_NEAR_DOUBLE(0.575, hit.point.x, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.575, hit.point.y, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(sqrt(0.00125), hit.distance, 1e-6);
    GUARD_C_CHECK_EQ_INT(4, hit.indices[0]);
    GUARD_C_CHECK_EQ_INT(0, hit.indices[1]);
    return 0;
}

GUARD_C_TEST(test_surface_edge_large_plane_has_only_outer_boundaries_with_bounded_cpu_time) {
    enum { cells = 256, side = cells + 1 };
    const size_t vertex_count = (size_t)side * side;
    const size_t triangle_count = (size_t)cells * cells * 2u;
    float* vertices = (float*)malloc(vertex_count * 3u * sizeof(float));
    uint32_t* indices = (uint32_t*)malloc(triangle_count * 3u * sizeof(uint32_t));
    if (!vertices || !indices) {
        free(vertices);
        free(indices);
        GUARD_C_FAIL("failed to allocate deterministic plane fixture");
    }
    for (uint32_t y = 0; y < side; ++y) {
        for (uint32_t x = 0; x < side; ++x) {
            const size_t vertex = (size_t)y * side + x;
            vertices[vertex * 3u] = (float)x;
            vertices[vertex * 3u + 1u] = (float)y;
            vertices[vertex * 3u + 2u] = 0.0f;
        }
    }
    size_t index_count = 0;
    for (uint32_t y = 0; y < cells; ++y) {
        for (uint32_t x = 0; x < cells; ++x) {
            const uint32_t a = y * side + x;
            indices[index_count++] = a;
            indices[index_count++] = a + 1u;
            indices[index_count++] = a + side + 1u;
            indices[index_count++] = a;
            indices[index_count++] = a + side + 1u;
            indices[index_count++] = a + side;
        }
    }
    size_t boundary_count = 0;
    for (size_t tri = 0; tri < triangle_count; ++tri) {
        for (size_t e = 0; e < 3; ++e) {
            const uint32_t a = indices[tri * 3u + e];
            const uint32_t b = indices[tri * 3u + (e + 1u) % 3u];
            const uint32_t ax = a % side, ay = a / side;
            const uint32_t bx = b % side, by = b / side;
            if ((ax == bx && (ax == 0 || ax == cells)) ||
                (ay == by && (ay == 0 || ay == cells))) {
                ++boundary_count;
            }
        }
    }
    GUARD_C_CHECK_EQ_INT(131072, triangle_count);
    GUARD_C_CHECK_EQ_INT(1024, boundary_count);
    const tc_mesh mesh = make_mesh(vertices, vertex_count, indices, index_count);
    const tc_vec3f points[] = {
        {0.25f, 105.375f, 0.0f},
        {255.75f, 150.125f, 0.0f},
        {130.5f, 0.25f, 0.0f},
        {78.25f, 255.75f, 0.0f},
    };
    const tc_vec3f expected[] = {
        {0.0f, 105.375f, 0.0f},
        {256.0f, 150.125f, 0.0f},
        {130.5f, 0.0f, 0.0f},
        {78.25f, 256.0f, 0.0f},
    };
    tc_mesh_surface_edge_hit hits[6] = {0};
    bool results[6];
    tc_mesh_surface_edge_query query = make_query();
    const clock_t started = clock();
    for (size_t i = 0; i < 4; ++i) {
        query.point = points[i];
        results[i] = tc_mesh_find_surface_edge_query(&mesh, &query, &hits[i]);
    }
    query.point = points[0];
    query.edge_direction = tc_vec3f_unit_y();
    query.max_angle_degrees = 0.0f;
    results[4] = tc_mesh_find_surface_edge_aligned(&mesh, &query, &hits[4]);
    results[5] = tc_mesh_find_nearest_surface_edge(&mesh, query.point, query.up, &hits[5]);
    const clock_t finished = clock();
    free(vertices);
    free(indices);

    for (size_t i = 0; i < 6; ++i) {
        GUARD_C_CHECK(results[i]);
        if (!results[i]) {
            continue;
        }
        const size_t boundary = i < 4 ? i : 0;
        GUARD_C_CHECK(hit_is_finite(&hits[i]));
        GUARD_C_CHECK_NEAR_DOUBLE(expected[boundary].x, hits[i].point.x, 1e-5);
        GUARD_C_CHECK_NEAR_DOUBLE(expected[boundary].y, hits[i].point.y, 1e-5);
        GUARD_C_CHECK_NEAR_DOUBLE(0.0, hits[i].point.z, 1e-6);
        GUARD_C_CHECK_NEAR_DOUBLE(0.25, hits[i].distance, 1e-5);
        for (size_t endpoint = 0; endpoint < 2; ++endpoint) {
            const uint32_t vertex = hits[i].indices[endpoint];
            GUARD_C_CHECK(vertex < vertex_count);
            if (boundary == 0 || boundary == 1) {
                GUARD_C_CHECK_EQ_INT(boundary == 0 ? 0 : cells, vertex % side);
            } else {
                GUARD_C_CHECK_EQ_INT(boundary == 2 ? 0 : cells, vertex / side);
            }
        }
    }
    GUARD_C_CHECK(started != (clock_t)-1 && finished != (clock_t)-1 && finished >= started);
    // A generous ten-second clock bound accommodates slow builds while
    // rejecting the previous quadratic scan on this mesh.
    if (started != (clock_t)-1 && finished != (clock_t)-1 && finished >= started) {
        const double elapsed = (double)(finished - started) / CLOCKS_PER_SEC;
        printf("surface-edge plane: triangles=%zu boundary_edges=%zu queries=6 clock_seconds=%.6f\n",
               triangle_count, boundary_count, elapsed);
        GUARD_C_CHECK(elapsed < 10.0);
    }
    return 0;
}

GUARD_C_TEST(test_surface_edge_required_pointer_matrix_is_logged_and_transactional) {
    float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
    };
    uint32_t indices[] = {0, 1, 2};
    const tc_mesh mesh = make_mesh(vertices, 3, indices, 3);
    const tc_mesh_surface_edge_query query = make_query();

    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(NULL, &query, &hit_), "tc_mesh_find_surface_edge_query");
    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(&mesh, NULL, &hit_), "tc_mesh_find_surface_edge_query");
    EXPECT_REJECTED(tc_mesh_find_surface_edge_aligned(&mesh, NULL, &hit_), "tc_mesh_find_surface_edge_aligned");
    EXPECT_REJECTED(tc_mesh_find_surface_edge(
                        NULL, 0, query.point, query.normal, query.up, &hit_),
                    "tc_mesh_find_surface_edge");
    EXPECT_REJECTED(tc_mesh_find_surface_edge_metric(
                        NULL, 0, query.point, query.normal, query.up, query.metric, &hit_),
                    "tc_mesh_find_surface_edge_metric");
    EXPECT_REJECTED(tc_mesh_find_nearest_surface_edge(NULL, query.point, query.up, &hit_),
                    "tc_mesh_find_nearest_surface_edge");
    EXPECT_REJECTED(tc_mesh_find_nearest_surface_edge_metric(NULL, query.point, query.up, query.metric, &hit_),
                    "tc_mesh_find_nearest_surface_edge_metric");

    begin_log_capture();
    GUARD_C_CHECK_FALSE(tc_mesh_find_surface_edge_query(&mesh, &query, NULL));
    end_log_capture();
    GUARD_C_CHECK(g_error_log_count > 0);
    GUARD_C_CHECK(strstr(g_last_error, "tc_mesh_find_surface_edge_query") != NULL);

    begin_log_capture();
    GUARD_C_CHECK_FALSE(tc_mesh_find_nearest_surface_edge(&mesh, query.point, query.up, NULL));
    end_log_capture();
    GUARD_C_CHECK(g_error_log_count > 0);
    GUARD_C_CHECK(strstr(g_last_error, "tc_mesh_find_nearest_surface_edge") != NULL);
    return 0;
}

GUARD_C_TEST(test_surface_edge_rejects_invalid_numeric_matrix_with_logs) {
    float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
    };
    uint32_t indices[] = {0, 1, 2};
    const tc_mesh mesh = make_mesh(vertices, 3, indices, 3);
    tc_mesh_surface_edge_query query = make_query();

    query.point.x = NAN;
    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_), "tc_mesh_find_surface_edge_query");
    query = make_query();
    query.normal.z = INFINITY;
    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_), "tc_mesh_find_surface_edge_query");
    query = make_query();
    query.up.y = -INFINITY;
    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_), "tc_mesh_find_surface_edge_query");
    query = make_query();
    query.metric.x = NAN;
    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_), "tc_mesh_find_surface_edge_query");
    query = make_query();
    query.normal = tc_vec3f_zero();
    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_), "tc_mesh_find_surface_edge_query");
    query = make_query();
    query.up = (tc_vec3f){0.0f, 1.0e-30f, 0.0f};
    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_), "tc_mesh_find_surface_edge_query");

    query = make_query();
    query.use_direction_filter = true;
    query.edge_direction = tc_vec3f_zero();
    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_), "tc_mesh_find_surface_edge_query");
    query = make_query();
    query.use_direction_filter = true;
    query.edge_direction = tc_vec3f_unit_y();
    query.max_angle_degrees = NAN;
    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_), "tc_mesh_find_surface_edge_query");
    query.max_angle_degrees = INFINITY;
    EXPECT_REJECTED(tc_mesh_find_surface_edge_aligned(&mesh, &query, &hit_), "tc_mesh_find_surface_edge_aligned");

    query = make_query();
    query.start_triangle = 1;
    EXPECT_REJECTED(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_), "tc_mesh_find_surface_edge_query");

    EXPECT_REJECTED(tc_mesh_find_surface_edge(
                        &mesh, 0, (tc_vec3f){NAN, 0.0f, 0.0f}, query.normal, query.up, &hit_),
                    "tc_mesh_find_surface_edge");
    EXPECT_REJECTED(tc_mesh_find_surface_edge_metric(
                        &mesh, 0, query.point, query.normal, query.up, (tc_vec3f){INFINITY, 1.0f, 1.0f}, &hit_),
                    "tc_mesh_find_surface_edge_metric");
    EXPECT_REJECTED(tc_mesh_find_nearest_surface_edge(
                        &mesh, query.point, tc_vec3f_zero(), &hit_),
                    "tc_mesh_find_nearest_surface_edge");
    EXPECT_REJECTED(tc_mesh_find_nearest_surface_edge_metric(
                        &mesh, query.point, query.up, (tc_vec3f){1.0f, NAN, 1.0f}, &hit_),
                    "tc_mesh_find_nearest_surface_edge_metric");
    return 0;
}

GUARD_C_TEST(test_surface_edge_ordinary_miss_is_silent_and_transactional) {
    float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
        1.0f, 1.0f, 0.0f,
    };
    uint32_t indices[] = {0, 1, 2, 2, 1, 3};
    const tc_mesh mesh = make_mesh(vertices, 4, indices, 6);
    tc_mesh_surface_edge_query query = make_query();
    query.use_direction_filter = true;
    query.edge_direction = (tc_vec3f){1.0f, 1.0f, 0.0f};
    query.max_angle_degrees = 0.0f;

    EXPECT_SILENT_MISS(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_));
    return 0;
}

GUARD_C_TEST(test_surface_edge_skips_nonfinite_and_unsafe_geometry) {
    float vertices[] = {
        0.0f, 0.0f, 0.0f,
        1.0f, 0.0f, 0.0f,
        0.0f, 1.0f, 0.0f,
        NAN, 0.0f, 0.0f,
        2.0f, 0.0f, 0.0f,
        2.0f, 1.0f, 0.0f,
    };
    uint32_t indices[] = {0, 1, 2, 3, 4, 5};
    tc_mesh mesh = make_mesh(vertices, 6, indices, 6);
    tc_mesh_surface_edge_query query = make_query();
    tc_mesh_surface_edge_hit hit;

    GUARD_C_REQUIRE(tc_mesh_find_surface_edge_query(&mesh, &query, &hit));
    GUARD_C_CHECK(hit_is_finite(&hit));

    vertices[9] = 1.0e14f;
    GUARD_C_REQUIRE(tc_mesh_find_surface_edge_query(&mesh, &query, &hit));
    GUARD_C_CHECK(hit_is_finite(&hit));

    mesh.indices = &indices[3];
    mesh.index_count = 3;
    query.point = (tc_vec3f){2.0f, 0.25f, 0.0f};
    EXPECT_SILENT_MISS(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_));

    vertices[9] = INFINITY;
    EXPECT_SILENT_MISS(tc_mesh_find_surface_edge_query(&mesh, &query, &hit_));
    return 0;
}

GUARD_C_TEST(test_nearest_surface_edge_skips_finite_overflowing_intermediates) {
    float vertices[] = {
        -1.0e13f, 0.0f, 0.0f,
        1.0e13f, 0.0f, 0.0f,
        0.0f, 1.0e13f, 0.0f,
    };
    uint32_t indices[] = {0, 1, 2};
    const tc_mesh mesh = make_mesh(vertices, 3, indices, 3);

    EXPECT_SILENT_MISS(tc_mesh_find_nearest_surface_edge(
        &mesh, (tc_vec3f){0.0f, 0.25f, 0.0f}, (tc_vec3f){0.0f, 1.0f, 0.0f}, &hit_));
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_surface_edge_reports_rich_finite_hits_and_preserves_c_semantics);
    GUARD_C_RUN(test_anisotropic_metric_uses_covector_normals_across_internal_diagonal);
    GUARD_C_RUN(test_surface_edge_welds_seam_split_coplanar_triangles);
    GUARD_C_RUN(test_surface_edge_preserves_first_two_nonmanifold_neighbors);
    GUARD_C_RUN(test_surface_edge_large_plane_has_only_outer_boundaries_with_bounded_cpu_time);
    GUARD_C_RUN(test_surface_edge_required_pointer_matrix_is_logged_and_transactional);
    GUARD_C_RUN(test_surface_edge_rejects_invalid_numeric_matrix_with_logs);
    GUARD_C_RUN(test_surface_edge_ordinary_miss_is_silent_and_transactional);
    GUARD_C_RUN(test_surface_edge_skips_nonfinite_and_unsafe_geometry);
    GUARD_C_RUN(test_nearest_surface_edge_skips_finite_overflowing_intermediates);
    tc_log_set_callback(NULL);
    return GUARD_C_END();
}
