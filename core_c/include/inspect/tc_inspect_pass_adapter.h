// tc_inspect_pass_adapter.h - Render pass-level inspect adapter API
#ifndef TC_INSPECT_PASS_ADAPTER_H
#define TC_INSPECT_PASS_ADAPTER_H

#include "inspect/tc_inspect.h"

#ifdef __cplusplus
extern "C" {
#endif

struct tc_pass;

// Pass field access (unified API for native and external passes).
// Works with tc_pass* directly, handles both C++ and Python passes.
TC_API tc_value tc_pass_inspect_get(struct tc_pass* p, const char* path);
TC_API void tc_pass_inspect_set(struct tc_pass* p, const char* path, tc_value value, tc_scene_handle scene);

#ifdef __cplusplus
}
#endif

#endif // TC_INSPECT_PASS_ADAPTER_H
