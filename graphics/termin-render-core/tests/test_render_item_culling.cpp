#include <cassert>
#include <cmath>
#include <limits>
#include <type_traits>

#include <termin/render/render_item_culling.hpp>
#include <termin/render/render_item_source.hpp>

namespace {
    using namespace termin;

    tc_render_item bounded(tc_vec3 minimum, tc_vec3 maximum) {
        tc_render_item item{};
        item.kind = TC_RENDER_ITEM_KIND_MESH;
        item.world_bounds = {minimum, maximum};
        item.bounds_state = TC_RENDER_ITEM_BOUNDS_VALID;
        return item;
    }

    bool sees(const RenderItemCullingView& view, tc_vec3 point) {
        RenderItemCullingCounters counters;
        return view.visible(bounded(point, point), counters);
    }

    void test_clip_planes_and_support() {
        const RenderItemCullingView view(Mat44f::identity(), Mat44f::identity());
        assert(sees(view, {0, 0, 0.5}));
        // All six planes, closed boundaries and boxes containing the frustum.
        assert(sees(view, {-1, 0, 0.5}));
        assert(sees(view, {1, 0, 0.5}));
        assert(sees(view, {0, -1, 0.5}));
        assert(sees(view, {0, 1, 0.5}));
        assert(sees(view, {0, 0, 0}));
        assert(sees(view, {0, 0, 1}));
        assert(!sees(view, {-1.01, 0, 0.5}));
        assert(!sees(view, {1.01, 0, 0.5}));
        assert(!sees(view, {0, -1.01, 0.5}));
        assert(!sees(view, {0, 1.01, 0.5}));
        assert(!sees(view, {0, 0, -0.01}));
        assert(!sees(view, {0, 0, 1.01}));
        RenderItemCullingCounters counters;
        assert(view.visible(bounded({-10, -10, -10}, {10, 10, 10}), counters));
        assert(view.visible(bounded({0.9, 0, 0}, {5, 5, 5}), counters));
        assert(!view.visible(bounded({2, 0, 0}, {5, 5, 5}), counters));
        assert(counters.candidates == 3 && counters.tested == 3 && counters.culled == 1);
    }

    void test_camera_projections() {
        constexpr float pi = 3.14159265358979323846f;
        const Mat44f projection = Mat44f::perspective(pi / 2, 1, 1, 10);
        const RenderItemCullingView perspective(Mat44f::identity(), projection);
        assert(sees(perspective, {0, 2, 0}));
        assert(sees(perspective, {2, 2, 0}));
        assert(!sees(perspective, {2.1, 2, 0}));
        assert(!sees(perspective, {0, 2, 2.1}));
        assert(!sees(perspective, {0, 0.5, 0}));
        assert(!sees(perspective, {0, 11, 0}));
        assert(!sees(perspective, {0, -2, 0}));
        assert(sees(perspective, {0, 1, 0}));
        assert(sees(perspective, {0, 10, 0}));

        const RenderItemCullingView orthographic(Mat44f::identity(), Mat44f::orthographic(-2, 2, -3, 3, 1, 10));
        assert(sees(orthographic, {2, 1, 3}));
        assert(sees(orthographic, {-2, 10, -3}));
        assert(!sees(orthographic, {2.1, 2, 0}));
        assert(!sees(orthographic, {0, 2, 3.1}));
        assert(!sees(orthographic, {0, 0.5, 0}));
        assert(!sees(orthographic, {0, 11, 0}));

        const Mat44f rotated = Mat44f::look_at({10, 20, 30}, {11, 20, 30});
        const RenderItemCullingView camera(rotated, projection);
        assert(sees(camera, {12, 20, 30}));
        assert(!sees(camera, {8, 20, 30}));
        assert(!sees(camera, {12, 23, 30}));
    }

    void test_stereo_and_safety() {
        StereoRenderViews stereo;
        stereo.left.view = Mat44::identity().with_translation({2, 0, 0});
        stereo.right.view = Mat44::identity().with_translation({-2, 0, 0});
        const RenderItemCullingView view(stereo);
        assert(sees(view, {-2, 0, 0.5}));
        assert(sees(view, {2, 0, 0.5}));
        assert(!sees(view, {0, 0, 0.5}));

        tc_render_item item = bounded({100, 100, 100}, {101, 101, 101});
        RenderItemCullingCounters counters;
        assert(view.visible(item, counters, false));
        item.bounds_state = TC_RENDER_ITEM_BOUNDS_MISSING;
        assert(view.visible(item, counters));
        item.bounds_state = TC_RENDER_ITEM_BOUNDS_UNSUPPORTED;
        assert(view.visible(item, counters));
        item.bounds_state = TC_RENDER_ITEM_BOUNDS_INVALID;
        assert(view.visible(item, counters));
        item.bounds_state = TC_RENDER_ITEM_BOUNDS_VALID;
        item.world_bounds.min_point.x = std::numeric_limits<double>::quiet_NaN();
        assert(view.visible(item, counters));
        assert(counters.candidates == 5 && counters.without_bounds == 5 && counters.tested == 0);

        item = bounded({100, 100, 100}, {101, 101, 101});
        set_render_item_culling_enabled(false);
        assert(view.visible(item, counters));
        assert(counters.tested == 0 && counters.culled == 0);
        set_render_item_culling_enabled(true);
        assert(!view.visible(item, counters));
        Mat44f invalid = Mat44f::identity();
        invalid(0, 0) = std::numeric_limits<float>::infinity();
        const RenderItemCullingView invalid_view(invalid, Mat44f::identity());
        assert(invalid_view.visible(item, counters));
    }

    void test_affine_bounds() {
        const tc_aabb local{{-1, -2, -3}, {4, 5, 6}};
        Mat44f model = Mat44f::identity();
        model(0, 0) = -2;
        model(1, 1) = 3;
        model(2, 2) = 0.5f;
        model(1, 0) = 1.25f;
        model(2, 1) = -0.75f;
        model(3, 0) = 42;
        model(3, 1) = -5;
        tc_aabb world;
        assert(transform_render_item_bounds(local, model, world));
        tc_vec3 corners[8];
        tc_aabb_get_corners(local, corners);
        tc_aabb expected{{INFINITY, INFINITY, INFINITY}, {-INFINITY, -INFINITY, -INFINITY}};
        for (const auto& corner : corners) {
            const Vec3f transformed = model.transform_point({float(corner.x), float(corner.y), float(corner.z)});
            tc_aabb_extend(&expected, {transformed.x, transformed.y, transformed.z});
            assert(tc_aabb_contains(world, {transformed.x, transformed.y, transformed.z}));
        }
        assert(world.min_point.x == expected.min_point.x && world.max_point.x == expected.max_point.x);
        assert(world.min_point.y == expected.min_point.y && world.max_point.y == expected.max_point.y);
        assert(world.min_point.z == expected.min_point.z && world.max_point.z == expected.max_point.z);
        model(0, 3) = 0.01f;
        assert(!transform_render_item_bounds(local, model, world));
        assert(world.min_point.x == expected.min_point.x); // Failure does not publish partial output.
    }

    class BoundsSource final : public RenderItemSource {
    protected:
        const char* source_name() const noexcept override { return "BoundsSource"; }
        bool collect_items(const RenderItemSourceRequest&, RenderItemCollection& collection,
                           RenderItemSnapshotCounters&) override {
            collection.items.push_back(prototype);
            return true;
        }
    public:
        tc_render_item prototype{};
    };

    void test_snapshot_refresh() {
        tc_mesh_init();
        const tc_mesh_handle handle = tc_mesh_create("culling-test");
        tc_mesh* mesh = tc_mesh_get(handle);
        const tc_vertex_layout layout = tc_vertex_layout_pos();
        float vertices[] = {-1, 0, 0, 1, 0, 0, 0, 2, 0};
        const uint32_t indices[] = {0, 1, 2};
        assert(tc_mesh_set_data(mesh, vertices, 3, &layout, indices, 3, "culling-test"));
        BoundsSource source;
        source.prototype.kind = TC_RENDER_ITEM_KIND_MESH;
        source.prototype.flags = TC_RENDER_ITEM_FLAG_CONSERVATIVE_MESH_BOUNDS;
        source.prototype.payload.mesh.mesh_handle = handle;
        RenderItemSnapshot snapshot;
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_VALID);
        assert(snapshot.item(0)->world_bounds.min_point.x == -1);

        vertices[0] = -8;
        assert(tc_mesh_set_vertices(mesh, vertices, 3, &layout));
        assert(snapshot.item(0)->world_bounds.min_point.x == -1);
        source.prototype.flags |= TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX;
        Mat44f::identity().with_translation({20, 0, 0}).copy_column_major_to(source.prototype.model_matrix);
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->world_bounds.min_point.x == 12);

        source.prototype.flags |= TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES;
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_UNSUPPORTED);
        source.prototype.flags = 0;
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_UNSUPPORTED);
        source.prototype.flags = TC_RENDER_ITEM_FLAG_CONSERVATIVE_MESH_BOUNDS;
        source.prototype.payload.mesh.mesh_handle = tc_mesh_handle_invalid();
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_MISSING);
        assert(tc_mesh_destroy(handle));
        tc_mesh_shutdown();
    }

    void assert_bounds(const tc_render_item& item, tc_vec3 minimum, tc_vec3 maximum) {
        assert(item.bounds_state == TC_RENDER_ITEM_BOUNDS_VALID);
        assert(item.world_bounds.min_point.x == minimum.x && item.world_bounds.max_point.x == maximum.x);
        assert(item.world_bounds.min_point.y == minimum.y && item.world_bounds.max_point.y == maximum.y);
        assert(item.world_bounds.min_point.z == minimum.z && item.world_bounds.max_point.z == maximum.z);
    }

    void test_undeformed_skinned_bounds_policy() {
        tc_mesh_init();
        const tc_mesh_handle handle = tc_mesh_create("skinned-culling-test");
        tc_mesh* mesh = tc_mesh_get(handle);
        const tc_vertex_layout layout = tc_vertex_layout_pos();
        float vertices[] = {-1, 0, 0, 1, 0, 0, 0, 2, 0,
                            10, 0, 0, 12, 0, 0, 10, 2, 0};
        const uint32_t indices[] = {0, 1, 2, 3, 4, 5};
        const tc_submesh submeshes[] = {
            {.first_index = 0, .index_count = 3},
            {.first_index = 3, .index_count = 3},
        };
        assert(tc_mesh_set_data(mesh, vertices, 6, &layout, indices, 6, "skinned-culling-test"));
        assert(tc_mesh_set_submeshes(mesh, submeshes, 2));

        float bone_matrix[16];
        Mat44f::identity().copy_column_major_to(bone_matrix);
        BoundsSource source;
        source.prototype.kind = TC_RENDER_ITEM_KIND_MESH;
        source.prototype.flags = TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES |
                                 TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX |
                                 TC_RENDER_ITEM_FLAG_UNDEFORMED_SKINNED_MESH_BOUNDS;
        source.prototype.payload.mesh.mesh_handle = handle;
        source.prototype.payload.mesh.skinning_matrices = bone_matrix;
        source.prototype.payload.mesh.skinning_matrix_count = 1;
        Mat44f model = Mat44f::identity();
        model(0, 0) = -2;
        model(1, 1) = 3;
        model(2, 2) = 0.5f;
        model(3, 0) = 20;
        model(3, 1) = -5;
        model(3, 2) = 0.5f;
        model.copy_column_major_to(source.prototype.model_matrix);
        RenderItemSnapshot snapshot;
        assert(source.publish(snapshot, {}));
        assert_bounds(*snapshot.item(0), {18, -5, 0.5}, {22, 1, 0.5});
        assert((snapshot.item(0)->flags & TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES) != 0u);
        assert((snapshot.item(0)->flags & TC_RENDER_ITEM_FLAG_CONSERVATIVE_MESH_BOUNDS) == 0u);
        assert(snapshot.item(0)->payload.mesh.skinning_matrices == bone_matrix);
        assert(snapshot.item(0)->payload.mesh.skinning_matrix_count == 1);

        // Pose affects rendering, but this explicitly approximate policy never
        // evaluates bone matrices while computing its culling bounds.
        bone_matrix[12] = 1000;
        RenderItemSnapshot moved_pose;
        assert(source.publish(moved_pose, {}));
        assert_bounds(*moved_pose.item(0), {18, -5, 0.5}, {22, 1, 0.5});
        assert(moved_pose.item(0)->payload.mesh.skinning_matrices[12] == 1000);

        const uint32_t geometry_version = mesh->header.version;
        const RenderItemCullingView main_camera(Mat44f::identity(), Mat44f::identity());
        const RenderItemCullingView near_cascade(Mat44f::identity().with_translation({-20, 0, 0}), Mat44f::identity());
        const RenderItemCullingView distant_cascade(Mat44f::identity().with_translation({-50, 0, 0}), Mat44f::identity());
        RenderItemCullingCounters main_counters, near_counters, distant_counters;
        assert(!main_camera.visible(*moved_pose.item(0), main_counters));
        assert(near_cascade.visible(*moved_pose.item(0), near_counters));
        assert(!distant_cascade.visible(*moved_pose.item(0), distant_counters));
        assert(main_counters.tested == 1 && main_counters.culled == 1);
        assert(near_counters.tested == 1 && near_counters.culled == 0);
        assert(distant_counters.tested == 1 && distant_counters.culled == 1);
        assert(mesh->header.version == geometry_version);
        assert_bounds(*moved_pose.item(0), {18, -5, 0.5}, {22, 1, 0.5});
        RenderItemCullingCounters custom_vertex_counters;
        assert(main_camera.visible(*moved_pose.item(0), custom_vertex_counters, false));
        assert(custom_vertex_counters.tested == 0 && custom_vertex_counters.without_bounds == 1);

        // Bounds are selected per submesh; the other geometry never inflates
        // the first submesh's box. Reflection/nonuniform scaling still apply.
        source.prototype.payload.mesh.submesh_index = 1;
        assert(source.publish(snapshot, {}));
        assert_bounds(*snapshot.item(0), {-4, -5, 0.5}, {0, 1, 0.5});
        source.prototype.payload.mesh.submesh_index = 0;
        vertices[0] = -8;
        assert(tc_mesh_set_vertices(mesh, vertices, 6, &layout));
        assert_bounds(*moved_pose.item(0), {18, -5, 0.5}, {22, 1, 0.5});
        assert(source.publish(snapshot, {}));
        assert_bounds(*snapshot.item(0), {18, -5, 0.5}, {36, 1, 0.5});
        // The existing cache requires a version bump for direct buffer edits.
        static_cast<float*>(mesh->vertices)[0] = -9;
        assert(source.publish(snapshot, {}));
        assert_bounds(*snapshot.item(0), {18, -5, 0.5}, {36, 1, 0.5});
        tc_mesh_bump_version(mesh);
        assert(source.publish(snapshot, {}));
        assert_bounds(*snapshot.item(0), {18, -5, 0.5}, {38, 1, 0.5});
        model(3, 0) = 40;
        model.copy_column_major_to(source.prototype.model_matrix);
        assert(source.publish(snapshot, {}));
        assert_bounds(*snapshot.item(0), {38, -5, 0.5}, {58, 1, 0.5});

        // Custom producers retain their previous unsupported policy until
        // explicitly choosing the undeformed skinned approximation.
        source.prototype.flags &= ~TC_RENDER_ITEM_FLAG_UNDEFORMED_SKINNED_MESH_BOUNDS;
        source.prototype.flags |= TC_RENDER_ITEM_FLAG_CONSERVATIVE_MESH_BOUNDS;
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_UNSUPPORTED);
        source.prototype.flags &= ~TC_RENDER_ITEM_FLAG_CONSERVATIVE_MESH_BOUNDS;
        source.prototype.flags |= TC_RENDER_ITEM_FLAG_UNDEFORMED_SKINNED_MESH_BOUNDS;
        source.prototype.flags &= ~TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES;
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_UNSUPPORTED);
        source.prototype.flags |= TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES;

        model(0, 0) = std::numeric_limits<float>::infinity();
        model.copy_column_major_to(source.prototype.model_matrix);
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_INVALID);
        RenderItemCullingCounters invalid_counters;
        assert(main_camera.visible(*snapshot.item(0), invalid_counters));
        model = Mat44f::identity();
        model(0, 3) = 0.01f;
        model.copy_column_major_to(source.prototype.model_matrix);
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_INVALID);
        assert(main_camera.visible(*snapshot.item(0), invalid_counters));
        Mat44f::identity().copy_column_major_to(source.prototype.model_matrix);
        static_cast<float*>(mesh->vertices)[0] = std::numeric_limits<float>::quiet_NaN();
        tc_mesh_bump_version(mesh);
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_MISSING);
        assert(main_camera.visible(*snapshot.item(0), invalid_counters));
        source.prototype.payload.mesh.mesh_handle = tc_mesh_handle_invalid();
        assert(source.publish(snapshot, {}));
        assert(snapshot.item(0)->bounds_state == TC_RENDER_ITEM_BOUNDS_MISSING);
        assert(main_camera.visible(*snapshot.item(0), invalid_counters));
        assert(invalid_counters.without_bounds == 4 && invalid_counters.tested == 0);
        assert(tc_mesh_destroy(handle));
        tc_mesh_shutdown();
    }

    void test_diagnostics() {
        clear_render_item_culling_diagnostics();
        RenderItemCullingCounters counters;
        counters.candidates = 4;
        counters.culled = 2;
        publish_render_item_culling_counters("target-a", "ColorPass", -1, counters);
        counters.candidates = 9;
        publish_render_item_culling_counters("target-a", "ColorPass", -1, counters);
        publish_render_item_culling_counters("target-b", "ShadowPass", 0, counters);
        const auto records = get_render_item_culling_diagnostics();
        assert(records.size() == 2);
        assert(records[0].counters.candidates == 9);
        assert(records[1].view_index == 0 && records[1].target == "target-b");
        clear_render_item_culling_diagnostics();
        assert(get_render_item_culling_diagnostics().empty());
    }
}

int main() {
    static_assert(std::is_standard_layout_v<tc_render_item>);
    static_assert(std::is_standard_layout_v<termin::RenderItemCullingCounters>);
    test_clip_planes_and_support();
    test_camera_projections();
    test_stereo_and_safety();
    test_affine_bounds();
    test_snapshot_refresh();
    test_undeformed_skinned_bounds_policy();
    test_diagnostics();
}
