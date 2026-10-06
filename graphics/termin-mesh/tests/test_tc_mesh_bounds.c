#include "guard_c.h"

#include <math.h>
#include <stdint.h>
#include <string.h>
#include <tcbase/tc_log.h>
#include <tgfx/resources/tc_mesh.h>
#include <tgfx/resources/tc_mesh_registry.h>

static unsigned bounds_error_logs;

static void capture_bounds_log(tc_log_level level, const char* message) {
    if (level == TC_LOG_ERROR && strstr(message, "tc_mesh_get_submesh_bounds:")) {
        ++bounds_error_logs;
    }
}

static tc_mesh* make_mesh(void) {
    tc_mesh_init();
    const tc_mesh_handle handle = tc_mesh_create("bounds-test");
    tc_mesh* mesh = tc_mesh_get(handle);
    const float vertices[] = {-9, 2, 3, 4, -5, 6, 7, 8, -1, 90, 100, 110};
    const uint32_t indices[] = {0, 1, 2};
    const tc_vertex_layout layout = tc_vertex_layout_pos();
    if (!mesh || !tc_mesh_set_data(mesh, vertices, 4, &layout, indices, 3, "bounds test")) {
        return NULL;
    }
    return mesh;
}

static void check_bounds(tc_aabb bounds,
                         double min_x, double min_y, double min_z,
                         double max_x, double max_y, double max_z) {
    GUARD_C_CHECK(tc_aabb_is_valid(bounds));
    GUARD_C_CHECK_NEAR_DOUBLE(min_x, bounds.min_point.x, 0);
    GUARD_C_CHECK_NEAR_DOUBLE(min_y, bounds.min_point.y, 0);
    GUARD_C_CHECK_NEAR_DOUBLE(min_z, bounds.min_point.z, 0);
    GUARD_C_CHECK_NEAR_DOUBLE(max_x, bounds.max_point.x, 0);
    GUARD_C_CHECK_NEAR_DOUBLE(max_y, bounds.max_point.y, 0);
    GUARD_C_CHECK_NEAR_DOUBLE(max_z, bounds.max_point.z, 0);
}

GUARD_C_TEST(test_bounds_referenced_vertices_and_signed_offsets) {
    tc_mesh* mesh = make_mesh();
    GUARD_C_REQUIRE(mesh != NULL);
    const uint32_t indices[] = {0, 1, 2, 1, 2, 3};
    GUARD_C_REQUIRE(tc_mesh_set_indices(mesh, indices, 6));
    const tc_submesh sections[] = {
        {.first_index = 0, .index_count = 3, .vertex_offset = 1},
        {.first_index = 3, .index_count = 3, .vertex_offset = -1},
    };
    GUARD_C_REQUIRE(tc_mesh_set_submeshes(mesh, sections, 2));
    tc_aabb bounds;
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    check_bounds(bounds, 4, -5, -1, 90, 100, 110);
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 1, &bounds));
    check_bounds(bounds, -9, -5, -1, 7, 8, 6);
    GUARD_C_CHECK_FALSE(tc_mesh_get_submesh_bounds(mesh, 2, &bounds));
    GUARD_C_CHECK_FALSE(tc_mesh_get_submesh_bounds(mesh, 0, NULL));
    tc_mesh_shutdown();
    return 0;
}

GUARD_C_TEST(test_bounds_cache_and_geometry_mutations) {
    tc_mesh* mesh = make_mesh();
    GUARD_C_REQUIRE(mesh != NULL);
    tc_aabb bounds;
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    check_bounds(bounds, -9, -5, -1, 7, 8, 6);
    // Direct edits require an explicit version bump. A cache hit must not scan.
    ((float*)mesh->vertices)[0] = -20;
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    GUARD_C_CHECK_NEAR_DOUBLE(-9, bounds.min_point.x, 0);
    tc_mesh_bump_version(mesh);
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    GUARD_C_CHECK_NEAR_DOUBLE(-20, bounds.min_point.x, 0);
    tc_mesh_clear_bounds_cache(mesh);
    GUARD_C_CHECK(mesh->_bounds_cache == NULL);
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    GUARD_C_CHECK_NEAR_DOUBLE(-20, bounds.min_point.x, 0);

    const float vertices[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};
    const tc_vertex_layout layout = tc_vertex_layout_pos();
    GUARD_C_REQUIRE(tc_mesh_set_vertices(mesh, vertices, 4, &layout));
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    check_bounds(bounds, 1, 2, 3, 7, 8, 9);
    const uint32_t indices[] = {1, 2, 3};
    GUARD_C_REQUIRE(tc_mesh_set_indices(mesh, indices, 3));
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    check_bounds(bounds, 4, 5, 6, 10, 11, 12);
    const tc_submesh section = {.first_index = 1, .index_count = 1};
    GUARD_C_REQUIRE(tc_mesh_set_submeshes(mesh, &section, 1));
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    check_bounds(bounds, 7, 8, 9, 7, 8, 9);
    GUARD_C_REQUIRE(tc_mesh_ensure_default_submesh(mesh));
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    check_bounds(bounds, 4, 5, 6, 10, 11, 12);

    tc_mesh_data_builder builder;
    GUARD_C_REQUIRE(tc_mesh_data_builder_allocate(&builder, 1, &layout, 1, 1));
    const float point[] = {-1, -2, -3};
    memcpy(builder.vertices, point, sizeof(point));
    builder.indices[0] = 0;
    builder.submeshes[0].index_count = 1;
    GUARD_C_REQUIRE(tc_mesh_data_builder_commit(mesh, &builder, "replacement"));
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    check_bounds(bounds, -1, -2, -3, -1, -2, -3);
    tc_mesh_shutdown();
    return 0;
}

static void check_rejected_unchanged(tc_mesh* mesh) {
    tc_aabb bounds = tc_aabb_new(TC_VEC3(11, 12, 13), TC_VEC3(21, 22, 23));
    const tc_aabb original = bounds;
    GUARD_C_CHECK_FALSE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    GUARD_C_CHECK(memcmp(&bounds, &original, sizeof(bounds)) == 0);
}

GUARD_C_TEST(test_bounds_invalid_geometry_cached_and_logged_once) {
    tc_mesh* mesh = make_mesh();
    GUARD_C_REQUIRE(mesh != NULL);
    tc_log_set_callback(capture_bounds_log);
    bounds_error_logs = 0;
    mesh->indices[0] = UINT32_MAX;
    check_rejected_unchanged(mesh);
    check_rejected_unchanged(mesh);
    GUARD_C_CHECK_EQ_UINT(1, bounds_error_logs);
    mesh->indices[0] = 0;
    check_rejected_unchanged(mesh); // Failure is also cached until a version bump.
    tc_mesh_bump_version(mesh);
    tc_aabb bounds;
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    GUARD_C_CHECK_EQ_UINT(1, bounds_error_logs);

    mesh->submeshes[0].vertex_offset = -1;
    tc_mesh_bump_version(mesh);
    check_rejected_unchanged(mesh);
    GUARD_C_CHECK_EQ_UINT(2, bounds_error_logs);
    mesh->submeshes[0].vertex_offset = 0;
    mesh->submeshes[0].first_index = UINT32_MAX;
    tc_mesh_bump_version(mesh);
    check_rejected_unchanged(mesh);
    GUARD_C_CHECK_EQ_UINT(3, bounds_error_logs);
    mesh->submeshes[0].first_index = 0;
    ((float*)mesh->vertices)[1] = NAN;
    tc_mesh_bump_version(mesh);
    check_rejected_unchanged(mesh);
    check_rejected_unchanged(mesh);
    GUARD_C_CHECK_EQ_UINT(4, bounds_error_logs);
    ((float*)mesh->vertices)[1] = INFINITY;
    tc_mesh_bump_version(mesh);
    check_rejected_unchanged(mesh);
    GUARD_C_CHECK_EQ_UINT(5, bounds_error_logs);
    tc_log_set_callback(NULL);
    tc_mesh_shutdown();
    return 0;
}

GUARD_C_TEST(test_bounds_layout_support_and_unaligned_position) {
    tc_mesh* mesh = make_mesh();
    GUARD_C_REQUIRE(mesh != NULL);
    tc_log_set_callback(capture_bounds_log);
    bounds_error_logs = 0;
    mesh->layout.attribs[0].type = TC_ATTRIB_INT32;
    check_rejected_unchanged(mesh);
    check_rejected_unchanged(mesh);
    GUARD_C_CHECK_EQ_UINT(0, bounds_error_logs);
    mesh->layout.attribs[0].type = TC_ATTRIB_FLOAT32;
    mesh->layout.attribs[0].size = 4;
    tc_mesh_bump_version(mesh);
    check_rejected_unchanged(mesh);
    GUARD_C_CHECK_EQ_UINT(0, bounds_error_logs);
    mesh->layout.attribs[0].size = 3;
    mesh->layout.attribs[0].offset = 1;
    tc_mesh_bump_version(mesh);
    check_rejected_unchanged(mesh); // Position extends past stride.
    GUARD_C_CHECK_EQ_UINT(1, bounds_error_logs);

    unsigned char vertices[13 * 3] = {0};
    const float coordinates[] = {-4, 2, 3, 1, -5, 6, 7, 8, -9};
    for (size_t i = 0; i < 3; ++i) {
        memcpy(vertices + i * 13 + 1, coordinates + i * 3, 12);
    }
    tc_vertex_layout layout = tc_vertex_layout_pos();
    layout.stride = 13;
    layout.attribs[0].offset = 1;
    GUARD_C_REQUIRE(tc_mesh_set_vertices(mesh, vertices, 3, &layout));
    tc_aabb bounds;
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    check_bounds(bounds, -4, -5, -9, 7, 8, 6);
    tc_log_set_callback(NULL);
    tc_mesh_shutdown();
    return 0;
}

GUARD_C_TEST(test_bounds_unavailable_sections_do_not_poison_valid_sections) {
    tc_mesh* mesh = make_mesh();
    GUARD_C_REQUIRE(mesh != NULL);
    const tc_submesh sections[] = {
        {.first_index = 0, .index_count = 3},
        {.first_index = 0, .index_count = 3, .vertex_offset = -1},
    };
    GUARD_C_REQUIRE(tc_mesh_set_submeshes(mesh, sections, 2));
    tc_aabb bounds;
    GUARD_C_REQUIRE(tc_mesh_get_submesh_bounds(mesh, 0, &bounds));
    check_bounds(bounds, -9, -5, -1, 7, 8, 6);
    GUARD_C_CHECK_FALSE(tc_mesh_get_submesh_bounds(mesh, 1, &bounds));
    mesh->submeshes[0].index_count = 0;
    tc_mesh_bump_version(mesh);
    check_rejected_unchanged(mesh);
    mesh->header.is_loaded = 0;
    GUARD_C_CHECK_FALSE(tc_mesh_get_submesh_bounds(mesh, 1, &bounds));
    tc_mesh_shutdown();
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_bounds_referenced_vertices_and_signed_offsets);
    GUARD_C_RUN(test_bounds_cache_and_geometry_mutations);
    GUARD_C_RUN(test_bounds_invalid_geometry_cached_and_logged_once);
    GUARD_C_RUN(test_bounds_layout_support_and_unaligned_position);
    GUARD_C_RUN(test_bounds_unavailable_sections_do_not_poison_valid_sections);
    tc_log_set_callback(NULL);
    tc_mesh_shutdown();
    return GUARD_C_END();
}
