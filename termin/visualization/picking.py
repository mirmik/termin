
def id_to_rgb(pid: int):
    """pack int id (1..16M) into RGB [0,1]. 0 = 'ничего не попали'."""
    r = (pid & 0x000000FF) / 255.0
    g = ((pid & 0x0000FF00) >> 8) / 255.0
    b = ((pid & 0x00FF0000) >> 16) / 255.0
    return (r, g, b)

def rgb_to_id(r: float, g: float, b: float) -> int:
    ri = int(r * 255 + 0.5)
    gi = int(g * 255 + 0.5)
    bi = int(b * 255 + 0.5)
    return ri | (gi << 8) | (bi << 16)