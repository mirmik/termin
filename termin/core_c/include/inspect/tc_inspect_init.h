// tc_inspect_init.h - Layered init API for inspect/kind runtime
#ifndef TC_INSPECT_INIT_H
#define TC_INSPECT_INIT_H

#include "tc_value.h"

#ifdef __cplusplus
extern "C" {
#endif

// Core inspect/kind init (generic only, no scene/render domain registrations).
TC_API void tc_inspect_kind_core_init(void);

// Scene/component adapter init (domain kinds and adapter wiring).
TC_API void tc_inspect_component_adapter_init(void);

// Render/pass adapter init.
TC_API void tc_inspect_pass_adapter_init(void);

// Python adapter init.
TC_API void tc_inspect_python_adapter_init(void);

// Backward-compatible full init wrapper.
TC_API void tc_init_full(void);

#ifdef __cplusplus
}
#endif

#endif // TC_INSPECT_INIT_H
