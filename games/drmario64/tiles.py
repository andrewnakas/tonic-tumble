"""CLEAN ROOM: bottle tiles (capsule halves, pills, viruses, pops) and their colour TLUTs.

The game draws one ci4 tile strip and recolours it with a 16-colour TLUT per colour (red, yellow,
blue; normal and dark). So the strips hold *indices* with a meaning we define, and every TLUT
follows the same scheme:
   0      transparent
   1..9   body ramp, dark -> light
   10-12  virus body: outline, mid, light
   13     black (pupils, mouth)      14  white (eyes, shine)      15  transparent
Which slot holds which tile kind was read off the strips (layout fact); the drawings are ours.
"""
import math

import numpy as np

RED, YELLOW, BLUE = (235, 45, 50), (250, 205, 30), (40, 110, 240)
# strip texture -> (tile size, dark?, kinds per slot)
KINDS8 = ["vtop", "vbot", "left", "right", "single", "pop", "pop_s", "virus0a", "virus0b", "virus1a", "virus1b",
          "virus2a", "virus2b", "pop", "pop_s", "bar"]
KINDS10 = ["vtop", "vbot", "left", "right", "single", "pop", "ring", "virus0a", "virus0b", "virus1a", "virus1b",
           "virus2a", "virus0a", "drop", "crown", "blank", "virus1b", "virus2b", "virus0b", "virus1a", "virus2a", "virus2b"]
STRIPS = {
    "game_item_titexdata_00_texs_tex": (8, False, KINDS8),
    "game_item_titexdata_01_texs_tex": (8, True, KINDS8),
    "game_item_titexdata_02_texs_tex": (10, False, KINDS10),
    "game_item_titexdata_03_texs_tex": (10, True, KINDS10),
}
TLUTS = {  # texture -> (hue, dark)
    "game_item_titexdata_04_texs_tlut": (BLUE, False), "game_item_titexdata_05_texs_tlut": (BLUE, True),
    "game_item_titexdata_06_texs_tlut": (YELLOW, False), "game_item_titexdata_07_texs_tlut": (YELLOW, True),
    "game_item_titexdata_08_texs_tlut": (BLUE, False), "game_item_titexdata_09_texs_tlut": (BLUE, True),
    "game_item_titexdata_10_texs_tlut": (YELLOW, False), "game_item_titexdata_11_texs_tlut": (YELLOW, True),
}


def palette(hue, dark):
    """16 RGBA entries following the index scheme above."""
    hue = np.asarray(hue, np.float32)
    k = 0.55 if dark else 1.0
    pal = np.zeros((16, 4), np.float32)
    for i in range(1, 10):
        t = (i - 1) / 8.0                      # 0 dark .. 1 light
        c = hue * (0.35 + 0.75 * t) if t < 0.8 else hue + (255 - hue) * (t - 0.8) * 3.0
        pal[i, :3] = np.clip(c, 0, 255) * k
        pal[i, 3] = 255
    pal[10, :3], pal[11, :3], pal[12, :3] = hue * 0.35 * k, hue * 0.8 * k, np.clip(hue * 1.1 + 40, 0, 255) * k
    pal[13, :3] = (15, 10, 20)
    pal[14, :3] = np.asarray((250, 250, 250)) * (0.7 if dark else 1.0)
    pal[10:15, 3] = 255
    return np.clip(np.round(pal), 0, 255).astype(np.uint8)


def _grid(s):
    y, x = np.mgrid[0:s, 0:s].astype(np.float32) + 0.5
    return x / s, y / s


def _ramp(inside, shade):
    """inside: bool mask; shade: 0..1 lightness -> indices 1..9."""
    idx = np.zeros(inside.shape, np.uint8)
    idx[inside] = np.clip(np.round(1 + shade[inside] * 8), 1, 9).astype(np.uint8)
    return idx


def capsule_half(s, side):
    """Half capsule with the round end at `side` (top/bottom/left/right)."""
    x, y = _grid(s)
    # work in a frame where the round end is at the top
    if side == "bottom":
        y = 1 - y
    elif side == "left":
        x, y = y, x
    elif side == "right":
        x, y = y, 1 - x
    r = 0.5
    inside = (np.abs(x - 0.5) <= 0.47) & ((y >= 0.5) | ((x - 0.5) ** 2 + (y - 0.5) ** 2 <= 0.47 ** 2))
    inside &= y <= 0.99
    cyl = 1 - np.abs(x - 0.38) / 0.62                      # lit from the upper left
    shade = np.clip(0.2 + 0.8 * cyl ** 1.5, 0, 1)
    shade = np.where(y > 0.9, shade * 0.6, shade)          # seam
    return _ramp(inside, shade)


def pill(s):
    x, y = _grid(s)
    d = np.hypot(x - 0.5, y - 0.5)
    inside = d <= 0.46
    shade = np.clip(1 - np.hypot(x - 0.36, y - 0.34) / 0.6, 0, 1)
    return _ramp(inside, 0.15 + 0.85 * shade)


def pop(s, small=False):
    x, y = _grid(s)
    ang = np.arctan2(y - 0.5, x - 0.5)
    d = np.hypot(x - 0.5, y - 0.5)
    r = (0.28 if small else 0.44) * (0.75 + 0.25 * np.cos(ang * 5))
    inside = d <= r
    return _ramp(inside, np.clip(1 - d / 0.5, 0.5, 1))


def ring(s):
    x, y = _grid(s)
    d = np.hypot(x - 0.5, y - 0.5)
    return _ramp((d <= 0.46) & (d >= 0.32), np.full(d.shape, 0.9))


def bar(s):
    x, y = _grid(s)
    inside = (y >= 0.1) & (y <= 0.9)
    return _ramp(inside, np.clip(1 - y, 0.2, 1))


def virus(s, kind, frame):
    """Our three germ designs (match art/chars.germ): 0 spiky sun with one eye, 1 square jelly
    with an antenna, 2 three-lobed blob with three dot eyes. Two frames each."""
    x, y = _grid(s)
    idx = np.zeros((s, s), np.uint8)
    cx, cy = 0.5, 0.54
    r = np.hypot(x - cx, y - cy)
    ang = np.arctan2(y - cy, x - cx) + (0.35 if frame else 0.0)
    if kind == 0:
        body = r <= 0.30 + 0.12 * (np.cos(ang * 7) > 0.2)
        light = body & (r < 0.24)
    elif kind == 1:
        sq = 0.04 if frame else -0.02
        body = (np.abs(x - cx) < 0.36 - sq) & (np.abs(y - cy - 0.04) < 0.32 + sq)
        body |= (np.abs(x - (0.5 + (0.06 if frame else -0.06))) < 0.05) & (y > 0.04) & (y < 0.25)
        light = body & (y < cy - 0.05) & (np.abs(x - cx) < 0.25)
    else:
        body = np.zeros_like(r, bool)
        for k in range(3):
            a = 2 * np.pi * k / 3 - np.pi / 2 + (0.3 if frame else 0.0)
            body |= np.hypot(x - cx - 0.2 * np.cos(a), y - cy - 0.2 * np.sin(a)) < 0.26
        light = body & (r < 0.15)
    idx[body] = 11
    idx[light] = 12
    edge = body & ~np.roll(body, 1, 0) | body & ~np.roll(body, -1, 0) | body & ~np.roll(body, 1, 1) | body & ~np.roll(body, -1, 1)
    idx[edge] = 10
    if kind == 0:
        eye = np.hypot(x - cx, y - cy + 0.02) < 0.15
        idx[eye] = 14
        idx[np.hypot(x - cx - (0.04 if frame else -0.04), y - cy + 0.02) < 0.07] = 13
    elif kind == 1:
        for ex in (0.38, 0.62):
            idx[(np.abs(x - ex) < 0.045) & (np.abs(y - 0.52) < (0.03 if frame else 0.09))] = 13
        idx[(np.abs(x - 0.5) < 0.12) & (np.abs(y - 0.72) < 0.025)] = 13
    else:
        for k in range(3):
            a = 2 * np.pi * k / 3 - np.pi / 2 + (0.3 if frame else 0.0)
            idx[np.hypot(x - cx - 0.13 * np.cos(a), y - cy - 0.13 * np.sin(a)) < 0.06] = 14
    return idx


def tile(kind, s):
    if kind in ("vtop", "vbot", "left", "right"):
        return capsule_half(s, {"vtop": "top", "vbot": "bottom", "left": "left", "right": "right"}[kind])
    if kind == "single":
        return pill(s)
    if kind == "pop":
        return pop(s)
    if kind in ("pop_s", "drop"):
        return pop(s, small=True)
    if kind == "ring":
        return ring(s)
    if kind == "bar":
        return bar(s)
    if kind.startswith("virus"):
        return virus(s, int(kind[5]), kind[6] == "b")
    if kind == "crown":
        x, y = _grid(s)
        return _ramp((y > 0.45) & (y < 0.85) & (np.abs(x - 0.5) < 0.4) | (y >= 0.25) & (y <= 0.45) & (np.abs((x * 3) % 1 - 0.5) < 0.2),
                     np.full((s, s), 0.95))
    return np.zeros((s, s), np.uint8)


def strip(name, w, h):
    """Indices (h, w) for a strip texture."""
    s, dark, kinds = STRIPS[name]
    out = np.zeros((h, w), np.uint8)
    for k, kind in enumerate(kinds):
        if (k + 1) * s <= h:
            out[k * s:(k + 1) * s, :s] = tile(kind, s)
    return out


def strip_palette(name):
    return palette(RED, STRIPS[name][1])


def tlut_image(name):
    """TLUT textures are 4x4 rgba16 'images' holding the 16 entries row by row."""
    hue, dark = TLUTS[name]
    return palette(hue, dark).reshape(4, 4, 4)
