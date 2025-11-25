
def hash_int(i):
    """A simple integer hash function."""
    i = ((i >> 16) ^ i) * 0x45d9f3b
    i = ((i >> 16) ^ i) * 0x45d9f3b
    i = (i >> 16) ^ i
    return i

id_by_rgb_cache = {}

def id_to_rgb(in_pid: int):
    """pack int id (1..16M) into RGB [0,1]. 0 = 'ничего не попали'."""
    pid = hash_int(in_pid) # для пестроты картинки

    r = (pid & 0x000000FF) / 255.0
    g = ((pid & 0x0000FF00) >> 8) / 255.0
    b = ((pid & 0x00FF0000) >> 16) / 255.0
    #print("Converted id", pid, "to color:", (r, g, b))  # --- DEBUG ---

    id_by_rgb_cache[(r, g, b)] = in_pid
    return (r, g, b)

def rgb_to_id(r: float, g: float, b: float) -> int:
    # ri = int(r * 255 + 0.5)
    # gi = int(g * 255 + 0.5)
    # bi = int(b * 255 + 0.5)
    # #print("Converted color", (r, g, b), "to id:", ri | (gi << 8) | (bi << 16))  # --- DEBUG ---
    # return ri | (gi << 8) | (bi << 16)
    key = (r, g, b)
    if key in id_by_rgb_cache:
        return id_by_rgb_cache[key]
    else:
        return 0
