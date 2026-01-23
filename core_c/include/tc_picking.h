// tc_picking.h - Entity picking utilities (ID <-> RGB conversion with cache)
#ifndef TC_PICKING_H
#define TC_PICKING_H

#include "tc_types.h"

#ifdef __cplusplus
extern "C" {
#endif

// Convert entity pick ID to RGB color (0-255 range).
// Also caches the mapping for reverse lookup.
TC_API void tc_picking_id_to_rgb(int id, int* r, int* g, int* b);

// Convert entity pick ID to RGB color (0.0-1.0 range).
// Also caches the mapping for reverse lookup.
TC_API void tc_picking_id_to_rgb_float(int id, float* r, float* g, float* b);

// Convert RGB color back to entity pick ID.
// Returns 0 if not found in cache.
TC_API int tc_picking_rgb_to_id(int r, int g, int b);

// Clear the picking cache.
TC_API void tc_picking_cache_clear(void);

#ifdef __cplusplus
}
#endif

#endif // TC_PICKING_H
