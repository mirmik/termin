#include "guard/guard.h"
#include "tc_inspect_cpp.hpp"

namespace {

struct InspectTestBase {
    int base_value = 0;
};

struct InspectTestDerived : public InspectTestBase {
    float gain = 0.0f;
    bool action_called = false;
};

} // namespace

TEST_CASE("InspectRegistry add/get/set and inheritance")
{
    auto& reg = tc::InspectRegistry::instance();

    reg.unregister_type("InspectTestBase");
    reg.unregister_type("InspectTestDerived");

    tc::register_builtin_cpp_kinds();

    reg.add<InspectTestBase, int>("InspectTestBase", &InspectTestBase::base_value,
                                  "base_value", "Base Value", "int", 0.0, 100.0, 1.0);
    reg.add<InspectTestDerived, float>("InspectTestDerived", &InspectTestDerived::gain,
                                       "gain", "Gain", "float", 0.0, 10.0, 0.1);
    reg.set_type_parent("InspectTestDerived", "InspectTestBase");

    InspectTestDerived obj;
    obj.base_value = 7;
    obj.gain = 1.5f;

    CHECK_EQ(reg.all_fields_count("InspectTestDerived"), (size_t)2);

    tc_value base_v = reg.get_tc_value(&obj, "InspectTestDerived", "base_value");
    CHECK_EQ(base_v.type, TC_VALUE_INT);
    CHECK_EQ(base_v.data.i, 7);
    tc_value_free(&base_v);

    tc_value gain_v = reg.get_tc_value(&obj, "InspectTestDerived", "gain");
    CHECK_EQ(gain_v.type, TC_VALUE_FLOAT);
    CHECK_EQ(gain_v.data.f, guard::Approx(1.5).epsilon(1e-6));
    tc_value_free(&gain_v);

    tc_value set_base = tc_value_int(42);
    reg.set_tc_value(&obj, "InspectTestDerived", "base_value", set_base, TC_SCENE_HANDLE_INVALID);
    tc_value_free(&set_base);
    CHECK_EQ(obj.base_value, 42);

    tc_value set_gain = tc_value_float(3.25f);
    reg.set_tc_value(&obj, "InspectTestDerived", "gain", set_gain, TC_SCENE_HANDLE_INVALID);
    tc_value_free(&set_gain);
    CHECK_EQ(obj.gain, guard::Approx(3.25).epsilon(1e-6));

    reg.unregister_type("InspectTestDerived");
    reg.unregister_type("InspectTestBase");
}

TEST_CASE("InspectRegistry generic action callback invocation")
{
    auto& reg = tc::InspectRegistry::instance();

    reg.unregister_type("InspectTestDerived");

    reg.add_button(
        "InspectTestDerived",
        "do_action",
        "Do Action",
        [](void* obj, const tc::InspectContext&) {
            auto* derived = static_cast<InspectTestDerived*>(obj);
            if (!derived) return;
            derived->action_called = true;
        }
    );

    InspectTestDerived obj;
    CHECK_EQ(obj.action_called, false);

    reg.action_field(&obj, "InspectTestDerived", "do_action");
    CHECK_EQ(obj.action_called, true);

    reg.unregister_type("InspectTestDerived");
}
