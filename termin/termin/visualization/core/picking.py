# picking.py - Entity picking utilities
# Uses C API for id<->rgb conversion to ensure consistency with C++ rendering

from termin._native import tc_picking_id_to_rgb, tc_picking_rgb_to_id, tc_picking_cache_clear

def id_to_rgb(in_pid: int):
    """Convert entity pick ID to RGB tuple (0.0-1.0 range).

    Also caches the mapping for reverse lookup via rgb_to_id.
    """
    r, g, b = tc_picking_id_to_rgb(in_pid)
    return (r / 255.0, g / 255.0, b / 255.0)

def rgb_to_id(r: float, g: float, b: float) -> int:
    """Convert RGB color back to entity pick ID.

    Returns 0 if not found in cache.
    """
    r_int = int(round(r * 255.0))
    g_int = int(round(g * 255.0))
    b_int = int(round(b * 255.0))
    return tc_picking_rgb_to_id(r_int, g_int, b_int)

def clear_cache():
    """Clear the picking cache."""
    tc_picking_cache_clear()
