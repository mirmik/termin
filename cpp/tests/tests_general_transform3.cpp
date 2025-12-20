#include "guard/guard.h"
#include "termin/geom/general_transform3.hpp"
#include "termin/geom/general_transform3_pool.hpp"
#include <cmath>

using guard::Approx;
using termin::geom::GeneralPose3;
using termin::geom::GeneralTransform3;
using termin::geom::GeneralTransform3Pool;
using termin::geom::TransformHandle;
using termin::geom::Quat;
using termin::geom::Vec3;

// ==================== Basic Tests ====================

TEST_CASE("GeneralTransform3 default construction")
{
    GeneralTransform3 t;
    const auto& pose = t.local_pose();
    CHECK_EQ(pose.lin.x, 0.0);
    CHECK_EQ(pose.lin.y, 0.0);
    CHECK_EQ(pose.lin.z, 0.0);
    CHECK_EQ(pose.scale.x, 1.0);
    CHECK_EQ(pose.scale.y, 1.0);
    CHECK_EQ(pose.scale.z, 1.0);
}

TEST_CASE("GeneralTransform3 construction with pose")
{
    GeneralPose3 pose(Quat::identity(), Vec3{1.0, 2.0, 3.0}, Vec3{2.0, 2.0, 2.0});
    GeneralTransform3 t(pose, "test");

    CHECK_EQ(t.name, "test");
    CHECK_EQ(t.local_pose().lin.x, 1.0);
    CHECK_EQ(t.local_pose().lin.y, 2.0);
    CHECK_EQ(t.local_pose().lin.z, 3.0);
    CHECK_EQ(t.local_pose().scale.x, 2.0);
}

TEST_CASE("GeneralTransform3 global pose without parent")
{
    GeneralPose3 pose(Quat::identity(), Vec3{1.0, 2.0, 3.0}, Vec3{2.0, 2.0, 2.0});
    GeneralTransform3 t(pose);

    const auto& global = t.global_pose();
    CHECK_EQ(global.lin.x, 1.0);
    CHECK_EQ(global.lin.y, 2.0);
    CHECK_EQ(global.lin.z, 3.0);
    CHECK_EQ(global.scale.x, 2.0);
}

// ==================== Scale Inheritance Tests ====================

TEST_CASE("GeneralTransform3 child inherits parent scale")
{
    GeneralTransform3 parent(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{2.0, 2.0, 2.0}));
    GeneralTransform3 child(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{1.0, 1.0, 1.0}));
    parent.add_child(&child);

    const auto& child_global = child.global_pose();
    CHECK_EQ(child_global.scale.x, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(child_global.scale.y, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(child_global.scale.z, Approx(2.0).epsilon(1e-12));
}

TEST_CASE("GeneralTransform3 scale multiplies through hierarchy")
{
    GeneralTransform3 parent(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{2.0, 2.0, 2.0}));
    GeneralTransform3 child(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{3.0, 3.0, 3.0}));
    GeneralTransform3 grandchild(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{1.0, 1.0, 1.0}));

    parent.add_child(&child);
    child.add_child(&grandchild);

    const auto& grandchild_global = grandchild.global_pose();
    CHECK_EQ(grandchild_global.scale.x, Approx(6.0).epsilon(1e-12));
    CHECK_EQ(grandchild_global.scale.y, Approx(6.0).epsilon(1e-12));
    CHECK_EQ(grandchild_global.scale.z, Approx(6.0).epsilon(1e-12));
}

TEST_CASE("GeneralTransform3 non-uniform scale inheritance")
{
    GeneralTransform3 parent(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{2.0, 3.0, 4.0}));
    GeneralTransform3 child(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{1.0, 2.0, 0.5}));
    parent.add_child(&child);

    const auto& child_global = child.global_pose();
    CHECK_EQ(child_global.scale.x, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(child_global.scale.y, Approx(6.0).epsilon(1e-12));
    CHECK_EQ(child_global.scale.z, Approx(2.0).epsilon(1e-12));
}

// ==================== Position with Scale Tests ====================

TEST_CASE("GeneralTransform3 parent scale affects child position")
{
    GeneralTransform3 parent(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{2.0, 2.0, 2.0}));
    GeneralTransform3 child(GeneralPose3(Quat::identity(), Vec3{1.0, 0.0, 0.0}, Vec3{1.0, 1.0, 1.0}));
    parent.add_child(&child);

    const auto& child_global = child.global_pose();
    CHECK_EQ(child_global.lin.x, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(child_global.lin.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(child_global.lin.z, Approx(0.0).epsilon(1e-12));
}

TEST_CASE("GeneralTransform3 parent translation and scale")
{
    GeneralTransform3 parent(GeneralPose3(Quat::identity(), Vec3{10.0, 0.0, 0.0}, Vec3{2.0, 2.0, 2.0}));
    GeneralTransform3 child(GeneralPose3(Quat::identity(), Vec3{1.0, 0.0, 0.0}, Vec3{1.0, 1.0, 1.0}));
    parent.add_child(&child);

    const auto& child_global = child.global_pose();
    // child [1,0,0] scaled by 2 -> [2,0,0], then parent adds [10,0,0] -> [12,0,0]
    CHECK_EQ(child_global.lin.x, Approx(12.0).epsilon(1e-12));
    CHECK_EQ(child_global.lin.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(child_global.lin.z, Approx(0.0).epsilon(1e-12));
}

TEST_CASE("GeneralTransform3 three level hierarchy position")
{
    GeneralTransform3 root(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{2.0, 2.0, 2.0}));
    GeneralTransform3 middle(GeneralPose3(Quat::identity(), Vec3{1.0, 0.0, 0.0}, Vec3{3.0, 3.0, 3.0}));
    GeneralTransform3 leaf(GeneralPose3(Quat::identity(), Vec3{1.0, 0.0, 0.0}, Vec3{1.0, 1.0, 1.0}));

    root.add_child(&middle);
    middle.add_child(&leaf);

    const auto& leaf_global = leaf.global_pose();
    CHECK_EQ(leaf_global.lin.x, Approx(8.0).epsilon(1e-12));
    CHECK_EQ(leaf_global.scale.x, Approx(6.0).epsilon(1e-12));
}

// ==================== Hierarchy Tests ====================

TEST_CASE("GeneralTransform3 add_child and unparent")
{
    GeneralTransform3 parent;
    GeneralTransform3 child;

    CHECK(parent.children.empty());
    CHECK(child.parent == nullptr);

    parent.add_child(&child);

    CHECK_EQ(parent.children.size(), 1u);
    CHECK_EQ(parent.children[0], &child);
    CHECK_EQ(child.parent, &parent);

    child.unparent();

    CHECK(parent.children.empty());
    CHECK(child.parent == nullptr);
}

TEST_CASE("GeneralTransform3 reparenting")
{
    GeneralTransform3 parent1(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{2.0, 2.0, 2.0}));
    GeneralTransform3 parent2(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{3.0, 3.0, 3.0}));
    GeneralTransform3 child(GeneralPose3(Quat::identity(), Vec3{1.0, 0.0, 0.0}, Vec3{1.0, 1.0, 1.0}));

    parent1.add_child(&child);
    CHECK_EQ(child.global_pose().lin.x, Approx(2.0).epsilon(1e-12));

    parent2.add_child(&child);  // reparent
    CHECK_EQ(child.global_pose().lin.x, Approx(3.0).epsilon(1e-12));
    CHECK(parent1.children.empty());
    CHECK_EQ(parent2.children.size(), 1u);
}

// ==================== Dirty Tracking Tests ====================

TEST_CASE("GeneralTransform3 dirty tracking")
{
    GeneralTransform3 parent;
    GeneralTransform3 child;
    parent.add_child(&child);

    // Force computation
    (void)child.global_pose();
    CHECK(!child.is_dirty());

    // Modify parent
    parent.set_local_pose(GeneralPose3::translation(1.0, 0.0, 0.0));
    CHECK(child.is_dirty());
}

// ==================== Transform Point/Vector Tests ====================

TEST_CASE("GeneralTransform3 transform_point with scale")
{
    GeneralTransform3 t(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{2.0, 3.0, 4.0}));

    Vec3 result = t.transform_point(Vec3{1.0, 1.0, 1.0});

    CHECK_EQ(result.x, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(result.y, Approx(3.0).epsilon(1e-12));
    CHECK_EQ(result.z, Approx(4.0).epsilon(1e-12));
}

TEST_CASE("GeneralTransform3 direction helpers")
{
    GeneralTransform3 t(GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{2.0, 3.0, 4.0}));

    Vec3 fwd = t.forward();
    CHECK_EQ(fwd.x, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(fwd.y, Approx(3.0).epsilon(1e-12));
    CHECK_EQ(fwd.z, Approx(0.0).epsilon(1e-12));

    Vec3 rgt = t.right();
    CHECK_EQ(rgt.x, Approx(2.0).epsilon(1e-12));
    CHECK_EQ(rgt.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(rgt.z, Approx(0.0).epsilon(1e-12));

    Vec3 u = t.up();
    CHECK_EQ(u.x, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(u.y, Approx(0.0).epsilon(1e-12));
    CHECK_EQ(u.z, Approx(4.0).epsilon(1e-12));
}

// ==================== Pool Tests ====================

TEST_CASE("GeneralTransform3Pool create and destroy")
{
    GeneralTransform3Pool pool(16);

    CHECK_EQ(pool.size(), 0u);
    CHECK_EQ(pool.capacity(), 16u);

    TransformHandle h = pool.create(GeneralPose3::identity(), "test");
    CHECK(!h.is_null());
    CHECK(pool.is_valid(h));
    CHECK_EQ(pool.size(), 1u);

    GeneralTransform3* t = pool.get(h);
    CHECK(t != nullptr);
    CHECK_EQ(t->name, "test");

    pool.destroy(h);
    CHECK(!pool.is_valid(h));
    CHECK_EQ(pool.size(), 0u);
    CHECK(pool.get(h) == nullptr);
}

TEST_CASE("GeneralTransform3Pool handle invalidation")
{
    GeneralTransform3Pool pool(16);

    TransformHandle h1 = pool.create();
    pool.destroy(h1);

    TransformHandle h2 = pool.create();  // reuses slot

    CHECK_EQ(h1.index, h2.index);  // same slot
    CHECK_NEQ(h1.generation, h2.generation);  // different generation
    CHECK(!pool.is_valid(h1));  // old handle invalid
    CHECK(pool.is_valid(h2));   // new handle valid
}

TEST_CASE("GeneralTransform3Pool hierarchy")
{
    GeneralTransform3Pool pool(16);

    TransformHandle parent_h = pool.create(
        GeneralPose3(Quat::identity(), Vec3::zero(), Vec3{2.0, 2.0, 2.0}), "parent");
    TransformHandle child_h = pool.create(
        GeneralPose3(Quat::identity(), Vec3{1.0, 0.0, 0.0}, Vec3{1.0, 1.0, 1.0}), "child");

    GeneralTransform3* parent = pool.get(parent_h);
    GeneralTransform3* child = pool.get(child_h);

    parent->add_child(child);

    CHECK_EQ(child->global_pose().lin.x, Approx(2.0).epsilon(1e-12));
}

TEST_CASE("GeneralTransform3Pool destroy_by_ptr")
{
    GeneralTransform3Pool pool(16);

    TransformHandle h = pool.create();
    GeneralTransform3* ptr = pool.get(h);

    CHECK(pool.is_valid_ptr(ptr));

    pool.destroy_by_ptr(ptr);

    CHECK(!pool.is_valid(h));
    CHECK(!pool.is_valid_ptr(ptr));
}

TEST_CASE("GeneralTransform3Pool handle_from_ptr")
{
    GeneralTransform3Pool pool(16);

    TransformHandle h = pool.create(GeneralPose3::identity(), "test");
    GeneralTransform3* ptr = pool.get(h);

    TransformHandle h2 = pool.handle_from_ptr(ptr);

    CHECK_EQ(h.index, h2.index);
    CHECK_EQ(h.generation, h2.generation);
}
