#include <assert.h>

#include <termin/nodegraph/view_c_api.h>

int main(void) {
    tc_nodegraph_view_handle view = tc_nodegraph_view_handle_invalid();
    tc_nodegraph_view_config config = {0};
    config.struct_size = sizeof(config);
    assert(tc_nodegraph_view_handle_is_invalid(view));
    assert(config.struct_size == sizeof(tc_nodegraph_view_config));
    return 0;
}
