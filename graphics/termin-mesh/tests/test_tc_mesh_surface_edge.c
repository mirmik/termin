#include "guard_c.h"

#include <float.h>
#include <geom/tc_vec3f.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
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
    GUARD_C_RUN(test_surface_edge_required_pointer_matrix_is_logged_and_transactional);
    GUARD_C_RUN(test_surface_edge_rejects_invalid_numeric_matrix_with_logs);
    GUARD_C_RUN(test_surface_edge_ordinary_miss_is_silent_and_transactional);
    GUARD_C_RUN(test_surface_edge_skips_nonfinite_and_unsafe_geometry);
    GUARD_C_RUN(test_nearest_surface_edge_skips_finite_overflowing_intermediates);
    tc_log_set_callback(NULL);
    return GUARD_C_END();
}
