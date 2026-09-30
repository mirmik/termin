#include "guard_c.h"

#include <float.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <tcbase/tc_log.h>
#include <tgfx/resources/tc_mesh.h>
#include <tgfx/resources/tc_mesh_registry.h>
#include <tgfx/resources/tc_primitive_mesh.h>

static int g_raycast_error_log_count = 0;
static char g_last_raycast_error[256];

static void capture_raycast_log(tc_log_level level, const char* message) {
    if (level == TC_LOG_ERROR) {
        ++g_raycast_error_log_count;
        snprintf(g_last_raycast_error, sizeof(g_last_raycast_error), "%s", message ? message : "");
    }
}

static tc_mesh make_triangle_mesh(float* vertices, uint32_t* indices) {
    tc_mesh mesh;
    memset(&mesh, 0, sizeof(mesh));
    mesh.header.is_loaded = 1;
    mesh.vertices = vertices;
    mesh.vertex_count = 3;
    mesh.indices = indices;
    mesh.index_count = 3;
    mesh.layout = tc_vertex_layout_pos();
    mesh.draw_mode = TC_DRAW_TRIANGLES;
    return mesh;
}

static tc_mesh_ray make_default_ray(void) {
    const tc_mesh_ray ray = {
        .origin = {0.25f, 0.25f, 1.0f},
        .direction = {0.0f, 0.0f, -1.0f},
        .t_min = 0.0f,
        .t_max = 10.0f,
    };
    return ray;
}

static int hit_is_finite(const tc_mesh_hit* hit) {
    return isfinite(hit->t) && isfinite(hit->position.x) && isfinite(hit->position.y) && isfinite(hit->position.z) &&
           isfinite(hit->normal.x) && isfinite(hit->normal.y) && isfinite(hit->normal.z) &&
           isfinite(hit->barycentric.x) && isfinite(hit->barycentric.y) && isfinite(hit->barycentric.z);
}

static void check_triangle_hit(const tc_mesh_hit* hit, float expected_x, float expected_y) {
    GUARD_C_CHECK(hit_is_finite(hit));
    GUARD_C_CHECK_NEAR_DOUBLE(1.0, hit->t, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(expected_x, hit->position.x, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(expected_y, hit->position.y, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.0, hit->position.z, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.0, hit->normal.x, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.0, hit->normal.y, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(1.0, hit->normal.z, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(1.0, hit->barycentric.x + hit->barycentric.y + hit->barycentric.z, 1e-6);
    GUARD_C_CHECK_EQ_UINT(0, hit->triangle_index);
    GUARD_C_CHECK_EQ_UINT(0, hit->indices[0]);
    GUARD_C_CHECK_EQ_UINT(1, hit->indices[1]);
    GUARD_C_CHECK_EQ_UINT(2, hit->indices[2]);
}

static void set_vec3_component(tc_vec3f* value, unsigned component, float replacement) {
    switch (component) {
    case 0:
        value->x = replacement;
        break;
    case 1:
        value->y = replacement;
        break;
    default:
        value->z = replacement;
        break;
    }
}

static void expect_rejected(const tc_mesh* mesh, const tc_mesh_ray* ray, const char* case_name, int require_error_log) {
    unsigned char original_hit[sizeof(tc_mesh_hit)];
    memset(original_hit, 0xA5, sizeof(original_hit));

    tc_mesh_hit hit;
    memcpy(&hit, original_hit, sizeof(hit));

    g_raycast_error_log_count = 0;
    g_last_raycast_error[0] = '\0';
    tc_log_set_callback(capture_raycast_log);
    const int did_hit = tc_mesh_raycast(mesh, ray, &hit);
    tc_log_set_callback(NULL);

    const int hit_changed = memcmp(&hit, original_hit, sizeof(hit)) != 0;
    const int invalid_error_log = require_error_log && (g_raycast_error_log_count == 0 ||
                                                        strstr(g_last_raycast_error, "tc_mesh_raycast:") == NULL);
    if (did_hit || hit_changed || invalid_error_log) {
        fprintf(stderr,
                "raycast rejection case '%s' failed: did_hit=%d hit_changed=%d error_logs=%d last_error='%s'\n",
                case_name,
                did_hit,
                hit_changed,
                g_raycast_error_log_count,
                g_last_raycast_error);
    }
    GUARD_C_CHECK_FALSE(did_hit);
    GUARD_C_CHECK_FALSE(hit_changed);
    if (require_error_log) {
        GUARD_C_CHECK(g_raycast_error_log_count > 0);
        GUARD_C_CHECK(strstr(g_last_raycast_error, "tc_mesh_raycast:") != NULL);
    }
}

GUARD_C_TEST(test_raycast_reports_finite_rich_hits) {
    float vertices[] = {
        0.0f,
        0.0f,
        0.0f,
        1.0f,
        0.0f,
        0.0f,
        0.0f,
        1.0f,
        0.0f,
    };
    uint32_t indices[] = {0, 1, 2};
    const tc_mesh mesh = make_triangle_mesh(vertices, indices);

    tc_mesh_ray ray = make_default_ray();
    tc_mesh_hit hit;
    GUARD_C_REQUIRE(tc_mesh_raycast(&mesh, &ray, &hit));
    check_triangle_hit(&hit, 0.25f, 0.25f);
    GUARD_C_CHECK_NEAR_DOUBLE(0.5, hit.barycentric.x, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.25, hit.barycentric.y, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.25, hit.barycentric.z, 1e-6);

    ray.origin.x = 0.5f;
    ray.origin.y = 0.5f;
    GUARD_C_REQUIRE(tc_mesh_raycast(&mesh, &ray, &hit));
    check_triangle_hit(&hit, 0.5f, 0.5f);
    GUARD_C_CHECK_NEAR_DOUBLE(0.0, hit.barycentric.x, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.5, hit.barycentric.y, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.5, hit.barycentric.z, 1e-6);

    ray = make_default_ray();
    ray.t_min = 1.0f;
    ray.t_max = 1.0f;
    GUARD_C_REQUIRE(tc_mesh_raycast(&mesh, &ray, &hit));
    check_triangle_hit(&hit, 0.25f, 0.25f);

    ray = make_default_ray();
    ray.direction.z = -FLT_MAX;
    GUARD_C_REQUIRE(tc_mesh_raycast(&mesh, &ray, &hit));
    check_triangle_hit(&hit, 0.25f, 0.25f);

    ray = make_default_ray();
    ray.origin = (tc_vec3f){-0.75f, -0.75f, 1.0f};
    ray.direction = (tc_vec3f){FLT_MAX, FLT_MAX, -FLT_MAX};
    GUARD_C_REQUIRE(tc_mesh_raycast(&mesh, &ray, &hit));
    GUARD_C_CHECK(hit_is_finite(&hit));
    GUARD_C_CHECK_NEAR_DOUBLE(sqrt(3.0), hit.t, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.25, hit.position.x, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.25, hit.position.y, 1e-6);
    GUARD_C_CHECK_NEAR_DOUBLE(0.0, hit.position.z, 1e-6);
    return 0;
}

GUARD_C_TEST(test_raycast_rejects_non_finite_public_inputs_transactionally) {
    float vertices[] = {
        0.0f,
        0.0f,
        0.0f,
        1.0f,
        0.0f,
        0.0f,
        0.0f,
        1.0f,
        0.0f,
    };
    uint32_t indices[] = {0, 1, 2};
    const tc_mesh mesh = make_triangle_mesh(vertices, indices);
    const float non_finite_values[] = {NAN, INFINITY, -INFINITY};
    const char* const non_finite_names[] = {"NaN", "+infinity", "-infinity"};
    const char* const component_names[] = {"x", "y", "z"};

    for (unsigned component = 0; component < 3; ++component) {
        for (unsigned value_index = 0; value_index < 3; ++value_index) {
            char case_name[64];
            tc_mesh_ray ray = make_default_ray();
            set_vec3_component(&ray.origin, component, non_finite_values[value_index]);
            snprintf(case_name,
                     sizeof(case_name),
                     "origin.%s=%s",
                     component_names[component],
                     non_finite_names[value_index]);
            expect_rejected(&mesh, &ray, case_name, 1);

            ray = make_default_ray();
            set_vec3_component(&ray.direction, component, non_finite_values[value_index]);
            snprintf(case_name,
                     sizeof(case_name),
                     "direction.%s=%s",
                     component_names[component],
                     non_finite_names[value_index]);
            expect_rejected(&mesh, &ray, case_name, 1);
        }
    }

    for (unsigned value_index = 0; value_index < 3; ++value_index) {
        char case_name[64];
        tc_mesh_ray ray = make_default_ray();
        ray.t_min = non_finite_values[value_index];
        snprintf(case_name, sizeof(case_name), "t_min=%s", non_finite_names[value_index]);
        expect_rejected(&mesh, &ray, case_name, 1);

        ray = make_default_ray();
        ray.t_max = non_finite_values[value_index];
        snprintf(case_name, sizeof(case_name), "t_max=%s", non_finite_names[value_index]);
        expect_rejected(&mesh, &ray, case_name, 1);
    }
    return 0;
}

GUARD_C_TEST(test_raycast_rejects_degenerate_direction_and_reversed_range) {
    float vertices[] = {
        0.0f,
        0.0f,
        0.0f,
        1.0f,
        0.0f,
        0.0f,
        0.0f,
        1.0f,
        0.0f,
    };
    uint32_t indices[] = {0, 1, 2};
    const tc_mesh mesh = make_triangle_mesh(vertices, indices);

    tc_mesh_ray ray = make_default_ray();
    ray.direction = (tc_vec3f){0.0f, 0.0f, 0.0f};
    expect_rejected(&mesh, &ray, "zero direction", 1);

    ray = make_default_ray();
    ray.direction = (tc_vec3f){0.0f, 0.0f, -1e-30f};
    expect_rejected(&mesh, &ray, "degenerate direction", 1);

    ray = make_default_ray();
    ray.t_min = 2.0f;
    ray.t_max = 1.0f;
    expect_rejected(&mesh, &ray, "reversed t range", 1);
    return 0;
}

GUARD_C_TEST(test_raycast_never_publishes_non_finite_geometry) {
    float vertices[] = {
        0.0f,
        0.0f,
        0.0f,
        1.0f,
        0.0f,
        0.0f,
        0.0f,
        1.0f,
        0.0f,
    };
    uint32_t indices[] = {0, 1, 2};
    const tc_mesh mesh = make_triangle_mesh(vertices, indices);
    const tc_mesh_ray ray = make_default_ray();

    vertices[0] = NAN;
    expect_rejected(&mesh, &ray, "NaN vertex", 0);

    vertices[0] = INFINITY;
    expect_rejected(&mesh, &ray, "infinite vertex", 0);

    vertices[0] = FLT_MAX;
    vertices[1] = 0.0f;
    vertices[2] = 0.0f;
    vertices[3] = -FLT_MAX;
    vertices[4] = 0.0f;
    vertices[5] = 0.0f;
    vertices[6] = 0.0f;
    vertices[7] = FLT_MAX;
    vertices[8] = 0.0f;
    expect_rejected(&mesh, &ray, "finite vertices with overflowing intermediates", 0);
    return 0;
}

enum lazy_load_mode {
    LOAD_GROW,
    LOAD_FAIL,
    LOAD_DESTROY,
    LOAD_REPLACE,
    LOAD_CHANGE_UUID,
    LOAD_REBOOTSTRAP
};

typedef struct lazy_load_state {
    tc_mesh_handle target;
    tc_mesh_handle replacement;
    enum lazy_load_mode mode;
    int calls;
    bool moved;
    bool uuid_survived;
} lazy_load_state;

static bool mesh_test_loader(const char* uuid, void* user_data) {
    lazy_load_state* state = user_data;
    ++state->calls;
    const uintptr_t old_address = (uintptr_t)tc_mesh_get(state->target);
    // The initial pool holds 64 slots. Allocating 128 additional slots forces
    // growth; tc_pool allocates the new storage before releasing the old one.
    for (int i = 0; i < 128; ++i) {
        char extra_uuid[40];
        snprintf(extra_uuid, sizeof(extra_uuid), "mesh-loader-extra-%d", i);
        const tc_mesh_handle extra = tc_mesh_create(extra_uuid);
        GUARD_C_CHECK(tc_mesh_is_valid(extra));
    }
    state->moved = old_address != (uintptr_t)tc_mesh_get(state->target);
    // Read the loader argument after relocation, not just at callback entry.
    state->uuid_survived = strcmp(uuid, "mesh-loader-target") == 0;
    if (state->mode == LOAD_FAIL)
        return false;
    if (state->mode == LOAD_DESTROY || state->mode == LOAD_REPLACE) {
        GUARD_C_CHECK(tc_mesh_destroy(state->target));
        if (state->mode == LOAD_REPLACE)
            state->replacement = tc_mesh_declare(uuid, "replacement");
        return true;
    }
    if (state->mode == LOAD_REBOOTSTRAP) {
        tc_mesh_shutdown();
        tc_mesh_init();
        state->replacement = tc_mesh_declare(uuid, "replacement");
        return true;
    }
    tc_mesh* mesh = tc_mesh_get(state->target);
    if (state->mode == LOAD_CHANGE_UUID) {
        tc_resource_header_set_uuid(&mesh->header, "changed-identity", "mesh_test_loader");
        return true;
    }
    const float vertices[] = {0, 0, 0, 1, 0, 0, 0, 1, 0};
    const uint32_t indices[] = {0, 1, 2};
    const tc_vertex_layout layout = tc_vertex_layout_pos();
    const bool success = tc_mesh_set_data(mesh, vertices, 3, &layout, indices, 3, "lazy triangle");
    // ensure_loaded, rather than set_data, must publish the load state.
    mesh->header.is_loaded = 0;
    return success;
}

static lazy_load_state begin_lazy_mesh_test(enum lazy_load_mode mode) {
    tc_mesh_shutdown();
    tc_mesh_init();
    lazy_load_state state = {0};
    state.target = tc_mesh_declare("mesh-loader-target", "lazy triangle");
    state.replacement = tc_mesh_handle_invalid();
    state.mode = mode;
    return state;
}

static void end_lazy_mesh_test(void) {
    tc_resource_clear_loader();
    tc_log_set_callback(NULL);
    tc_mesh_shutdown();
}

GUARD_C_TEST(test_mesh_lazy_queries_reacquire_after_pool_growth) {
    for (int query_kind = 0; query_kind < 4; ++query_kind) {
        lazy_load_state state = begin_lazy_mesh_test(LOAD_GROW);
        tc_resource_set_loader(mesh_test_loader, &state);
        const tc_mesh_ray ray = make_default_ray();
        tc_mesh_hit hit;
        tc_mesh_surface_edge_hit edge;
        const tc_mesh_surface_edge_query query = {
            .start_triangle = 0,
            .point = {0.25f, 0.25f, 0},
            .normal = {0, 0, 1},
            .up = {0, 1, 0},
            .metric = {1, 1, 1},
        };
        if (query_kind == 0) {
            GUARD_C_CHECK(tc_mesh_ensure_loaded(state.target));
        } else if (query_kind == 1) {
            GUARD_C_CHECK(tc_mesh_raycast_handle(state.target, &ray, &hit));
            check_triangle_hit(&hit, 0.25f, 0.25f);
        } else if (query_kind == 2) {
            GUARD_C_CHECK(tc_mesh_find_surface_edge_query_handle(state.target, &query, &edge));
            GUARD_C_CHECK(isfinite(edge.distance));
        } else {
            GUARD_C_CHECK(tc_mesh_find_nearest_surface_edge_metric_handle(
                state.target, query.point, query.up, query.metric, &edge));
            GUARD_C_CHECK(isfinite(edge.distance));
        }
        GUARD_C_CHECK(state.moved);
        GUARD_C_CHECK(state.uuid_survived);
        GUARD_C_CHECK(tc_mesh_is_loaded(state.target));
        GUARD_C_CHECK(tc_mesh_ensure_loaded(state.target));
        GUARD_C_CHECK_EQ_INT(1, state.calls);
        end_lazy_mesh_test();
    }
    return 0;
}

GUARD_C_TEST(test_mesh_lazy_load_rejects_failure_disappearance_and_identity_change) {
    for (enum lazy_load_mode mode = LOAD_FAIL; mode <= LOAD_REBOOTSTRAP; ++mode) {
        lazy_load_state state = begin_lazy_mesh_test(mode);
        tc_resource_set_loader(mesh_test_loader, &state);
        g_raycast_error_log_count = 0;
        tc_log_set_callback(capture_raycast_log);
        tc_mesh_hit hit;
        memset(&hit, 0xA5, sizeof(hit));
        const tc_mesh_hit unchanged = hit;
        const tc_mesh_ray ray = make_default_ray();
        GUARD_C_CHECK_FALSE(tc_mesh_raycast_handle(state.target, &ray, &hit));
        GUARD_C_CHECK(memcmp(&hit, &unchanged, sizeof(hit)) == 0);
        GUARD_C_CHECK(state.moved);
        GUARD_C_CHECK(state.uuid_survived);
        GUARD_C_CHECK(g_raycast_error_log_count > 0);
        GUARD_C_CHECK(strstr(g_last_raycast_error, "mesh-loader-target") != NULL);
        if (mode == LOAD_FAIL || mode == LOAD_CHANGE_UUID) {
            GUARD_C_CHECK_FALSE(tc_mesh_is_loaded(state.target));
        } else {
            GUARD_C_CHECK_FALSE(tc_mesh_is_valid(state.target));
        }
        if (mode == LOAD_REPLACE || mode == LOAD_REBOOTSTRAP) {
            GUARD_C_CHECK(tc_mesh_is_valid(state.replacement));
            GUARD_C_CHECK_FALSE(tc_mesh_is_loaded(state.replacement));
            GUARD_C_CHECK_EQ_UINT(state.target.index, state.replacement.index);
            GUARD_C_CHECK(state.target.generation != state.replacement.generation);
        }
        end_lazy_mesh_test();
    }
    return 0;
}

GUARD_C_TEST(test_mesh_pointer_queries_require_resident_data_without_loading) {
    lazy_load_state state = begin_lazy_mesh_test(LOAD_GROW);
    tc_resource_set_loader(mesh_test_loader, &state);
    const tc_mesh_ray ray = make_default_ray();
    tc_mesh* mesh = tc_mesh_get(state.target);
    expect_rejected(mesh, &ray, "unloaded pointer query", 1);
    tc_mesh_surface_edge_hit edge;
    const tc_mesh_surface_edge_query query = {
        .point = {0.25f, 0.25f, 0}, .normal = {0, 0, 1}, .up = {0, 1, 0}, .metric = {1, 1, 1}};
    GUARD_C_CHECK_FALSE(tc_mesh_find_surface_edge_query(mesh, &query, &edge));
    GUARD_C_CHECK_FALSE(tc_mesh_find_nearest_surface_edge_metric(mesh, query.point, query.up, query.metric, &edge));
    GUARD_C_CHECK_EQ_INT(0, state.calls);
    GUARD_C_CHECK_FALSE(tc_mesh_is_loaded(state.target));
    tc_mesh* standalone = tc_primitive_plane_new(2, 2, 1, 1);
    GUARD_C_CHECK(standalone != NULL);
    if (standalone) {
        tc_mesh_hit hit;
        GUARD_C_CHECK(tc_mesh_raycast(standalone, &ray, &hit));
        GUARD_C_CHECK_EQ_INT(0, state.calls);
        free(standalone->vertices);
        free(standalone->indices);
        free(standalone);
    }
    end_lazy_mesh_test();
    return 0;
}

static void grow_mesh_pool(void) {
    for (int i = 0; i < 128; ++i)
        GUARD_C_CHECK(tc_mesh_is_valid(tc_mesh_create(NULL)));
}

static void grow_mesh_pool_on_log(tc_log_level level, const char* message) {
    if (level == TC_LOG_INFO && strstr(message, "DESTROYING mesh")) {
        tc_log_set_callback(NULL);
        grow_mesh_pool();
    }
}

static void grow_mesh_pool_on_info_log(tc_log_level level, const char* message) {
    if (level == TC_LOG_INFO && strstr(message, "[tc_mesh_get_all_info] pool_count=")) {
        tc_log_set_callback(NULL);
        grow_mesh_pool();
    }
}

static void grow_mesh_pool_on_destroy(uint32_t pool_index, void* user_data) {
    unsigned* hook_calls = user_data;
    (void)pool_index;
    ++*hook_calls;
    grow_mesh_pool();
}

GUARD_C_TEST(test_mesh_destroy_reacquires_after_log_and_hook_callbacks) {
    for (int use_hook = 0; use_hook < 2; ++use_hook) {
        lazy_load_state state = begin_lazy_mesh_test(LOAD_GROW);
        unsigned hook_calls = 0;
        if (use_hook)
            tc_mesh_registry_add_destroy_hook(grow_mesh_pool_on_destroy, &hook_calls);
        else
            tc_log_set_callback(grow_mesh_pool_on_log);
        GUARD_C_CHECK(tc_mesh_destroy(state.target));
        GUARD_C_CHECK_FALSE(tc_mesh_contains("mesh-loader-target"));
        GUARD_C_CHECK_FALSE(tc_mesh_is_valid(state.target));
        GUARD_C_CHECK_EQ_UINT(128, tc_mesh_count());
        if (use_hook) {
            GUARD_C_CHECK_EQ_UINT(1, hook_calls);
            tc_mesh_registry_remove_destroy_hook(grow_mesh_pool_on_destroy, &hook_calls);
        }
        end_lazy_mesh_test();
    }
    return 0;
}

GUARD_C_TEST(test_mesh_info_sizes_snapshot_after_log_callback) {
    begin_lazy_mesh_test(LOAD_GROW);
    tc_log_set_callback(grow_mesh_pool_on_info_log);
    size_t count = 0;
    tc_mesh_info* infos = tc_mesh_get_all_info(&count);
    GUARD_C_CHECK(infos != NULL);
    GUARD_C_CHECK_EQ_UINT(129, count);
    if (infos) {
        for (size_t i = 0; i < count; ++i)
            GUARD_C_CHECK(tc_mesh_is_valid(infos[i].handle));
        free(infos);
    }
    end_lazy_mesh_test();
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_raycast_reports_finite_rich_hits);
    GUARD_C_RUN(test_raycast_rejects_non_finite_public_inputs_transactionally);
    GUARD_C_RUN(test_raycast_rejects_degenerate_direction_and_reversed_range);
    GUARD_C_RUN(test_raycast_never_publishes_non_finite_geometry);
    GUARD_C_RUN(test_mesh_lazy_queries_reacquire_after_pool_growth);
    GUARD_C_RUN(test_mesh_lazy_load_rejects_failure_disappearance_and_identity_change);
    GUARD_C_RUN(test_mesh_pointer_queries_require_resident_data_without_loading);
    GUARD_C_RUN(test_mesh_destroy_reacquires_after_log_and_hook_callbacks);
    GUARD_C_RUN(test_mesh_info_sizes_snapshot_after_log_callback);
    tc_log_set_callback(NULL);
    return GUARD_C_END();
}
