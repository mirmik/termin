#include "core/tc_entity_pool.h"

#include <geom/tc_affine3.h>
#include <geom/tc_quat.h>

#include <math.h>
#include <stdio.h>

#define CHECK(condition)                                                                                               \
    do {                                                                                                               \
        if (!(condition)) {                                                                                            \
            fprintf(stderr, "CHECK failed at %s:%d: %s\n", __FILE__, __LINE__, #condition);                            \
            return 1;                                                                                                  \
        }                                                                                                              \
    } while (0)

static int near(double actual, double expected) {
    return fabs(actual - expected) <= 1e-12;
}

static int vec_near(tc_vec3 actual, tc_vec3 expected) {
    return near(actual.x, expected.x) && near(actual.y, expected.y) && near(actual.z, expected.z);
}

static int basis_near(tc_basis3d actual, tc_basis3d expected) {
    return vec_near(actual.x, expected.x) && vec_near(actual.y, expected.y) && vec_near(actual.z, expected.z);
}

static void set_pose(tc_entity_pool* pool, tc_entity_id entity, tc_vec3 position, tc_quat rotation, tc_vec3 scale) {
    const double p[3] = {position.x, position.y, position.z};
    const double r[4] = {rotation.x, rotation.y, rotation.z, rotation.w};
    const double s[3] = {scale.x, scale.y, scale.z};
    tc_entity_pool_set_local_pose(pool, entity, p, r, s);
}

static int test_classification_and_exact_shear(void) {
    tc_entity_pool* pool = tc_entity_pool_create(2);
    CHECK(pool != NULL);

    tc_entity_id parent = tc_entity_pool_alloc(pool, "parent");
    tc_entity_id child = tc_entity_pool_alloc(pool, "child");
    CHECK(tc_entity_pool_set_parent_checked(pool, child, parent));

    CHECK(tc_entity_pool_get_world_transform_kind(pool, parent) == TC_TRANSFORM_RIGID);

    set_pose(pool, parent, (tc_vec3){3.0, 4.0, 5.0}, (tc_quat){0.0, 0.0, 0.0, 1.0}, (tc_vec3){2.0, 1.0, 0.5});
    const double half_sqrt2 = sqrt(0.5);
    set_pose(
        pool, child, (tc_vec3){1.0, 2.0, 3.0}, (tc_quat){0.0, 0.0, half_sqrt2, half_sqrt2}, (tc_vec3){1.0, 3.0, 1.0});

    tc_affine3d expected = tc_affine3d_mul(
        tc_affine3d_trs((tc_vec3){3.0, 4.0, 5.0}, (tc_quat){0.0, 0.0, 0.0, 1.0}, (tc_vec3){2.0, 1.0, 0.5}),
        tc_affine3d_trs(
            (tc_vec3){1.0, 2.0, 3.0}, (tc_quat){0.0, 0.0, half_sqrt2, half_sqrt2}, (tc_vec3){1.0, 3.0, 1.0}));
    tc_affine3d actual;
    tc_entity_pool_get_world_affine(pool, child, &actual);

    CHECK(tc_entity_pool_get_world_transform_kind(pool, parent) == TC_TRANSFORM_AXIS_SCALED);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, child) == TC_TRANSFORM_AFFINE);
    CHECK(vec_near(actual.translation, expected.translation));
    CHECK(basis_near(actual.basis, expected.basis));

    double scale[3] = {10.0, 20.0, 30.0};
    CHECK(!tc_entity_pool_try_get_decomposed_global_scale(pool, child, scale));
    CHECK(scale[0] == 10.0 && scale[1] == 20.0 && scale[2] == 30.0);

    double matrix[16];
    double expected_matrix[16];
    tc_entity_pool_get_world_matrix(pool, child, matrix);
    tc_affine3d_to_matrix4(expected, expected_matrix);
    for (int i = 0; i < 16; ++i) {
        CHECK(near(matrix[i], expected_matrix[i]));
    }

    tc_entity_pool_destroy(pool);
    return 0;
}

static int test_promotion_demotion_and_affine_descendant(void) {
    tc_entity_pool* pool = tc_entity_pool_create(3);
    CHECK(pool != NULL);
    tc_entity_id root = tc_entity_pool_alloc(pool, "root");
    tc_entity_id child = tc_entity_pool_alloc(pool, "child");
    tc_entity_id leaf = tc_entity_pool_alloc(pool, "leaf");
    CHECK(tc_entity_pool_set_parent_checked(pool, child, root));
    CHECK(tc_entity_pool_set_parent_checked(pool, leaf, child));

    const double half_sqrt2 = sqrt(0.5);
    // Rigid parent preserves the local decomposed tier.
    set_pose(
        pool, child, (tc_vec3){0.0, 0.0, 0.0}, (tc_quat){0.0, half_sqrt2, 0.0, half_sqrt2}, (tc_vec3){2.0, 2.0, 2.0});
    CHECK(tc_entity_pool_get_world_transform_kind(pool, child) == TC_TRANSFORM_SIMILARITY);
    const double nonuniform_child_scale[3] = {2.0, 3.0, 2.0};
    tc_entity_pool_set_local_scale(pool, child, nonuniform_child_scale);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, child) == TC_TRANSFORM_AXIS_SCALED);

    // Similarity commutes with local rotation, then adopts local axis scale.
    const double uniform_scale[3] = {2.0, 2.0, 2.0};
    tc_entity_pool_set_local_scale(pool, root, uniform_scale);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, child) == TC_TRANSFORM_AXIS_SCALED);

    set_pose(pool, root, (tc_vec3){0.0, 0.0, 0.0}, (tc_quat){0.0, 0.0, 0.0, 1.0}, (tc_vec3){2.0, 1.0, 1.0});
    set_pose(
        pool, child, (tc_vec3){0.0, 0.0, 0.0}, (tc_quat){0.0, half_sqrt2, 0.0, half_sqrt2}, (tc_vec3){1.0, 1.0, 1.0});
    CHECK(tc_entity_pool_get_world_transform_kind(pool, child) == TC_TRANSFORM_AFFINE);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, leaf) == TC_TRANSFORM_AFFINE);

    // Recompute from current inputs: uniformizing the ancestor demotes the branch.
    tc_entity_pool_set_local_scale(pool, root, uniform_scale);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, root) == TC_TRANSFORM_SIMILARITY);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, child) == TC_TRANSFORM_SIMILARITY);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, leaf) == TC_TRANSFORM_SIMILARITY);

    // Axis-scaled composition remains decomposed for an identity local rotation
    // and may naturally cancel all scale.
    const double axis_scale[3] = {2.0, 1.0, 1.0};
    const double identity_rotation[4] = {0.0, 0.0, 0.0, 1.0};
    const double cancel_scale[3] = {0.5, 1.0, 1.0};
    tc_entity_pool_set_local_scale(pool, root, axis_scale);
    tc_entity_pool_set_local_rotation(pool, child, identity_rotation);
    tc_entity_pool_set_local_scale(pool, child, cancel_scale);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, child) == TC_TRANSFORM_RIGID);

    tc_entity_pool_destroy(pool);
    return 0;
}

static int test_zero_negative_growth_and_reuse(void) {
    tc_entity_pool* pool = tc_entity_pool_create(1);
    CHECK(pool != NULL);
    tc_entity_id entities[12];
    for (int i = 0; i < 12; ++i) {
        entities[i] = tc_entity_pool_alloc(pool, "entity");
        CHECK(tc_entity_pool_get_world_transform_kind(pool, entities[i]) == TC_TRANSFORM_RIGID);
    }

    const double zero_scale[3] = {0.0, 0.0, 0.0};
    tc_entity_pool_set_local_scale(pool, entities[3], zero_scale);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, entities[3]) == TC_TRANSFORM_AXIS_SCALED);

    tc_entity_id freed = entities[7];
    tc_entity_pool_free(pool, freed);
    tc_entity_id reused = tc_entity_pool_alloc(pool, "reused");
    CHECK(reused.index == freed.index);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, reused) == TC_TRANSFORM_RIGID);
    tc_basis3d basis;
    tc_entity_pool_get_world_basis(pool, reused, &basis);
    CHECK(basis_near(basis, tc_basis3d_identity()));

    const double reflected_scale[3] = {-2.0, -2.0, -2.0};
    tc_entity_pool_set_local_scale(pool, reused, reflected_scale);
    CHECK(tc_entity_pool_get_world_transform_kind(pool, reused) == TC_TRANSFORM_AXIS_SCALED);
    double exact_scale[3];
    CHECK(tc_entity_pool_try_get_decomposed_global_scale(pool, reused, exact_scale));
    CHECK(exact_scale[0] == -2.0 && exact_scale[1] == -2.0 && exact_scale[2] == -2.0);

    tc_entity_pool_destroy(pool);
    return 0;
}

static int test_rigid_rotation_composition_uses_parent_then_child(void) {
    tc_entity_pool* pool = tc_entity_pool_create(2);
    CHECK(pool != NULL);

    const tc_entity_id parent = tc_entity_pool_alloc(pool, "rotation-parent");
    const tc_entity_id child = tc_entity_pool_alloc(pool, "rotation-child");
    CHECK(tc_entity_pool_set_parent_checked(pool, child, parent));

    const tc_quat parent_rotation = {0.5, 0.5, 0.5, 0.5};
    const tc_quat child_rotation = {-0.5, 0.5, -0.5, 0.5};
    set_pose(pool, parent, (tc_vec3){0.0, 0.0, 0.0}, parent_rotation, (tc_vec3){1.0, 1.0, 1.0});
    set_pose(pool, child, (tc_vec3){0.0, 0.0, 0.0}, child_rotation, (tc_vec3){1.0, 1.0, 1.0});

    const tc_quat expected = tc_quat_mul(parent_rotation, child_rotation);
    double actual[4] = {0.0, 0.0, 0.0, 0.0};
    tc_entity_pool_get_global_rotation(pool, child, actual);
    CHECK(near(actual[0], expected.x));
    CHECK(near(actual[1], expected.y));
    CHECK(near(actual[2], expected.z));
    CHECK(near(actual[3], expected.w));

    tc_entity_pool_destroy(pool);
    return 0;
}

int main(void) {
    CHECK(test_classification_and_exact_shear() == 0);
    CHECK(test_promotion_demotion_and_affine_descendant() == 0);
    CHECK(test_zero_negative_growth_and_reuse() == 0);
    CHECK(test_rigid_rotation_composition_uses_parent_then_child() == 0);
    return 0;
}
