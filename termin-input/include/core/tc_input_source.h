#ifndef TC_INPUT_SOURCE_H
#define TC_INPUT_SOURCE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum tc_input_source {
    TC_INPUT_SOURCE_RUNTIME = 1u << 0u,
    TC_INPUT_SOURCE_EDITOR  = 1u << 1u,
} tc_input_source;

#ifdef __cplusplus
}
#endif

#endif
