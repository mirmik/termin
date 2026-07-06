#include "guard_c.h"

#include "core/tc_component.h"
#include "core/tc_input_component.h"

static const tc_input_vtable g_test_input_vtable = {
    NULL,
    NULL,
    NULL,
    NULL,
};

GUARD_C_TEST(test_input_source_mask_defaults_and_updates) {
    tc_component component;
    tc_component_init(&component, NULL);
    GUARD_C_REQUIRE(tc_input_capability_attach(&component, &g_test_input_vtable));
    GUARD_C_CHECK_EQ_UINT(TC_INPUT_SOURCE_RUNTIME, tc_component_get_input_source_mask(&component));
    GUARD_C_CHECK(tc_component_accepts_input_source(&component, TC_INPUT_SOURCE_RUNTIME));
    GUARD_C_CHECK_FALSE(tc_component_accepts_input_source(&component, TC_INPUT_SOURCE_EDITOR));

    GUARD_C_REQUIRE(tc_component_set_input_source_mask(
        &component,
        TC_INPUT_SOURCE_RUNTIME | TC_INPUT_SOURCE_EDITOR
    ));
    GUARD_C_CHECK(tc_component_accepts_input_source(&component, TC_INPUT_SOURCE_EDITOR));

    tc_component_clear_capabilities(&component);
    return 0;
}

int main(int argc, char** argv) {
    GUARD_C_BEGIN_ARGS(argc, argv);
    GUARD_C_RUN(test_input_source_mask_defaults_and_updates);
    return GUARD_C_END();
}
