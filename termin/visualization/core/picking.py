
def hash_int(i):
    """A simple integer hash function."""
    i = ((i >> 16) ^ i) * 0x45d9f3b
    i = ((i >> 16) ^ i) * 0x45d9f3b
    i = (i >> 16) ^ i
    return i

# Use integer keys (0-255) to avoid float precision issues between C++ and Python
id_by_rgb_cache = {}

def id_to_rgb(in_pid: int):
    """pack int id (1..16M) into RGB [0,1]. 0 = 'ничего не попали'."""
    pid = hash_int(in_pid) # для пестроты картинки

    r_int = pid & 0x000000FF
    g_int = (pid & 0x0000FF00) >> 8
    b_int = (pid & 0x00FF0000) >> 16

    # Store with integer key to avoid float precision issues
    id_by_rgb_cache[(r_int, g_int, b_int)] = in_pid

    return (r_int / 255.0, g_int / 255.0, b_int / 255.0)

def rgb_to_id(r: float, g: float, b: float) -> int:
    # Convert floats back to integers (0-255)
    r_int = int(round(r * 255.0))
    g_int = int(round(g * 255.0))
    b_int = int(round(b * 255.0))

    key = (r_int, g_int, b_int)
    if key in id_by_rgb_cache:
        return id_by_rgb_cache[key]
    else:
        return 0
