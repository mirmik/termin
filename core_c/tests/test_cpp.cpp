// test_cpp.cpp - C++ wrapper tests
#include <iostream>
#include <cmath>
#include "../include/termin_core.hpp"

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n"; \
            return 1; \
        } \
    } while(0)

constexpr double EPSILON = 1e-9;

// Example custom component
class MyComponent : public tc::Component {
public:
    TC_COMPONENT(MyComponent)

    int value = 0;
    bool started = false;
    bool updated = false;

    void start() override {
        started = true;
    }

    void update(float dt) override {
        (void)dt;
        updated = true;
        value++;
    }
};

int test_vec3() {
    std::cout << "Testing tc::Vec3...\n";

    tc::Vec3 a(1, 2, 3);
    tc::Vec3 b(4, 5, 6);

    auto sum = a + b;
    TEST_ASSERT(std::abs(sum.x - 5.0) < EPSILON, "vec3 add");

    auto cross = a.cross(b);
    TEST_ASSERT(std::abs(cross.x - (-3.0)) < EPSILON, "vec3 cross");

    auto norm = a.normalized();
    TEST_ASSERT(std::abs(norm.length() - 1.0) < EPSILON, "vec3 normalize");

    std::cout << "  Vec3: PASS\n";
    return 0;
}

int test_quat() {
    std::cout << "Testing tc::Quat...\n";

    auto q = tc::Quat::identity();
    TEST_ASSERT(std::abs(q.w - 1.0) < EPSILON, "quat identity");

    // Rotate (1,0,0) by 90 degrees around Y
    auto rot = tc::Quat::from_axis_angle(tc::Vec3::up(), M_PI / 2.0);
    auto v = rot * tc::Vec3(1, 0, 0);
    TEST_ASSERT(std::abs(v.z - (-1.0)) < 0.01, "quat rotate");

    std::cout << "  Quat: PASS\n";
    return 0;
}

int test_transform() {
    std::cout << "Testing tc::Transform...\n";

    tc::Transform t;
    t.set_position(tc::Vec3(1, 2, 3));

    auto pos = t.position();
    TEST_ASSERT(std::abs(pos.x - 1.0) < EPSILON, "transform position");

    t.translate(tc::Vec3(1, 0, 0));
    pos = t.position();
    TEST_ASSERT(std::abs(pos.x - 2.0) < EPSILON, "transform translate");

    std::cout << "  Transform: PASS\n";
    return 0;
}

int test_entity() {
    std::cout << "Testing tc::Entity...\n";

    tc::Entity e("TestEntity");

    TEST_ASSERT(e.name() == "TestEntity", "entity name");
    TEST_ASSERT(e.uuid().length() == 36, "entity uuid");
    TEST_ASSERT(e.visible() == true, "entity visible");

    e.set_visible(false);
    TEST_ASSERT(e.visible() == false, "entity set visible");

    // Test pose
    e.set_local_pose(tc::GeneralPose3(
        tc::Vec3(10, 20, 30),
        tc::Quat::identity(),
        tc::Vec3::one()
    ));

    auto pose = e.local_pose();
    TEST_ASSERT(std::abs(pose.position.x - 10.0) < EPSILON, "entity pose");

    std::cout << "  Entity: PASS\n";
    return 0;
}

int test_entity_hierarchy() {
    std::cout << "Testing tc::Entity hierarchy...\n";

    tc::Entity parent("Parent");
    tc::Entity child("Child");

    parent.set_local_pose(tc::GeneralPose3(
        tc::Vec3(10, 0, 0),
        tc::Quat::identity(),
        tc::Vec3::one()
    ));

    child.set_local_pose(tc::GeneralPose3(
        tc::Vec3(5, 0, 0),
        tc::Quat::identity(),
        tc::Vec3::one()
    ));

    child.set_parent(&parent);

    TEST_ASSERT(child.parent() == parent.raw(), "child has parent");
    TEST_ASSERT(parent.children_count() == 1, "parent has child");

    auto global = child.global_pose();
    TEST_ASSERT(std::abs(global.position.x - 15.0) < EPSILON, "child global pos");

    std::cout << "  Entity hierarchy: PASS\n";
    return 0;
}

int test_component() {
    std::cout << "Testing tc::Component...\n";

    // Component lifetime is managed by C++ code (not by Entity)
    auto comp = std::make_unique<MyComponent>();

    {
        tc::Entity e("WithComponent");
        e.add_component(comp.get());

        TEST_ASSERT(e.component_count() == 1, "component added");
        TEST_ASSERT(comp->value == 0, "component initial value");

        // Simulate lifecycle
        tc_component_start(comp->raw());
        TEST_ASSERT(comp->started == true, "component started");

        e.update(0.016f);
        TEST_ASSERT(comp->updated == true, "component updated");
        TEST_ASSERT(comp->value == 1, "component value incremented");

        // Entity destroyed here, but doesn't free component (is_native=false)
    }

    // Component still valid, freed by unique_ptr when test ends
    TEST_ASSERT(comp->value == 1, "component still valid after entity destroyed");

    std::cout << "  Component: PASS\n";
    return 0;
}

int test_registry() {
    std::cout << "Testing tc::registry...\n";

    size_t initial = tc::registry::count();

    {
        tc::Entity e1("E1");
        tc::Entity e2("E2");

        TEST_ASSERT(tc::registry::count() == initial + 2, "registry count");

        auto* found = tc::registry::find_by_uuid(std::string(e1.uuid()));
        TEST_ASSERT(found == e1.raw(), "find by uuid");
    }

    // Entities destroyed, count should be back
    TEST_ASSERT(tc::registry::count() == initial, "registry cleanup");

    std::cout << "  Registry: PASS\n";
    return 0;
}

int test_entity_handle() {
    std::cout << "Testing tc::EntityHandle...\n";

    std::string uuid;
    {
        tc::Entity e("HandleTest");
        uuid = std::string(e.uuid());

        tc::EntityHandle h(e);
        TEST_ASSERT(h.is_valid(), "handle valid");
        TEST_ASSERT(h.get() == e.raw(), "handle get");
    }

    // Entity destroyed
    tc::EntityHandle h2(uuid);
    TEST_ASSERT(h2.is_valid(), "handle still has uuid");
    TEST_ASSERT(h2.get() == nullptr, "handle get returns null after destroy");

    std::cout << "  EntityHandle: PASS\n";
    return 0;
}

int main() {
    std::cout << "=== Termin Core C++ Tests ===\n";
    std::cout << "Version: " << tc::version() << "\n\n";

    tc::init();

    int result = 0;

    result |= test_vec3();
    result |= test_quat();
    result |= test_transform();
    result |= test_entity();
    result |= test_entity_hierarchy();
    result |= test_component();
    result |= test_registry();
    result |= test_entity_handle();

    tc::shutdown();

    std::cout << "\n";
    if (result == 0) {
        std::cout << "=== ALL C++ TESTS PASSED ===\n";
    } else {
        std::cout << "=== SOME TESTS FAILED ===\n";
    }

    return result;
}
