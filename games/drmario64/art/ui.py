"""CLEAN ROOM: Tonic Tumble panels, stickers, patterns, scenes, logo and frames.

Inputs per texture: name, format, size, and one coarse number `cut` (the opaque fraction,
rounded to 0.1, for textures that use transparency). Shapes, colours and patterns are ours.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from games.drmario64.art.draw import INK, Canvas, h32, mix, rng, shade, smooth_noise, star, to_rgba

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_LOGO = os.path.join(HERE, "fonts", "LuckiestGuy-Regular.ttf")
FONT_UI = os.path.join(HERE, "fonts", "LilitaOne-Regular.ttf")

MINT, TEAL, CORAL, CREAM = (120, 215, 190), (40, 150, 160), (250, 120, 110), (255, 244, 220)
SUN, PLUM, SKY, LEAF = (255, 205, 80), (110, 70, 140), (150, 205, 245), (110, 190, 90)
THEME = [MINT, TEAL, CORAL, SUN, PLUM, SKY, LEAF, (240, 160, 200)]


def pick(name, k=0):
    return THEME[h32(name, k) % len(THEME)]


# ------------------------------------------------------------------ panels and stickers
def panel(name, w, h, cut=None):
    """A rounded panel (opaque or with corner cut-outs) with a soft gradient and dot pattern."""
    c = pick(name)
    cv = Canvas(w, h, bg=(0, 0, 0, 0) if cut is not None else shade(c, 0.55) + (255,))
    r = min(w, h) * (0.35 if cut is not None and cut < 0.95 else 0.18)
    inset = 0.5 if cut is None or cut >= 0.95 else max(0.5, min(w, h) * 0.04)
    cv.rect(inset, inset, w - inset, h - inset, shade(c, 1.15), outline=shade(c, 0.45),
            width=max(1.0, min(w, h) / 24), r=r)
    im = cv.array().astype(np.float32)
    if cut is None:
        im[..., 3] = 255
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    light = 1.08 - 0.22 * yy / max(1, h)
    im[..., :3] *= light[..., None]
    step = max(4, min(w, h) // 6)
    dots = ((xx + (yy // step % 2) * step / 2) % step - step / 2) ** 2 + (yy % step - step / 2) ** 2 < (step * 0.15) ** 2
    im[dots, :3] = im[dots, :3] * 0.92 + 255 * 0.08
    return np.clip(im, 0, 255).astype(np.uint8)


def sticker(name, w, h, cut):
    """Cut-out shapes sized so roughly `cut` of the texture is opaque."""
    r = rng("sticker", name)
    kind = h32(name, "kind") % 5
    c = pick(name)
    cv = Canvas(w, h)
    cx, cy = w / 2, h / 2
    s = math.sqrt(max(0.05, cut))
    rx, ry = w * 0.5 * s * 1.05, h * 0.5 * s * 1.05
    if kind == 0:      # cloud puffs
        for k in range(5):
            a = 2 * math.pi * k / 5
            cv.ellipse(cx + math.cos(a) * rx * 0.45, cy + math.sin(a) * ry * 0.4, rx * 0.55, ry * 0.55, shade(c, 1.4), outline=shade(c, 0.6))
        cv.ellipse(cx, cy, rx * 0.6, ry * 0.6, shade(c, 1.45), outline=None)
    elif kind == 1:    # star
        cv.poly(star(cx, cy, min(rx, ry) * 1.15, min(rx, ry) * 0.55, 5 + h32(name) % 3, r.random()), c, outline=shade(c, 0.5))
    elif kind == 2:    # flower
        n = 6
        for k in range(n):
            a = 2 * math.pi * k / n
            cv.ellipse(cx + math.cos(a) * rx * 0.5, cy + math.sin(a) * ry * 0.5, rx * 0.42, ry * 0.42, c, outline=shade(c, 0.5))
        cv.ellipse(cx, cy, rx * 0.4, ry * 0.4, SUN, outline=shade(SUN, 0.6))
    elif kind == 3:    # pill capsule
        cv.rect(cx - rx, cy - ry * 0.6, cx + rx, cy + ry * 0.6, c, outline=shade(c, 0.45), r=min(rx, ry) * 0.6)
        cv.rect(cx, cy - ry * 0.6, cx + rx, cy + ry * 0.6, pick(name, 1), outline=shade(c, 0.45), r=min(rx, ry) * 0.6)
        cv.ellipse(cx - rx * 0.5, cy - ry * 0.25, rx * 0.25, ry * 0.12, (255, 255, 255, 160), outline=None)
    else:              # badge
        cv.ellipse(cx, cy, rx, ry, c, outline=shade(c, 0.45), width=max(1, min(w, h) / 20))
        cv.ellipse(cx, cy, rx * 0.7, ry * 0.7, shade(c, 1.3), outline=None)
        cv.poly(star(cx, cy, min(rx, ry) * 0.5, min(rx, ry) * 0.22, 4, 0.4), CREAM, outline=None)
    return cv.array()


def intensity(name, w, h, cut):
    """Grey masks/glows: soft blobs, rings, sparkles or bands (intensity in every channel)."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx, ny = (xx + 0.5) / w * 2 - 1, (yy + 0.5) / h * 2 - 1
    kind = h32(name, "ikind") % 4
    c = 0.5 if cut is None else cut
    if kind == 0:
        v = np.clip((1.0 + c * 0.6 - np.hypot(nx, ny)) * 2.2, 0, 1)
    elif kind == 1:
        d = np.hypot(nx, ny)
        v = np.clip(1 - np.abs(d - 0.65) * (6 - 4 * c), 0, 1)
    elif kind == 2:
        v = np.clip(1 - np.minimum(np.abs(nx) * 3.5 + np.abs(ny), np.abs(ny) * 3.5 + np.abs(nx)) / (0.6 + c), 0, 1)
    else:
        v = np.clip(0.5 + 0.5 * np.sin((nx * 2.5 + ny * 1.5) * math.pi) * (1 - 0.5 * np.abs(ny)), 0, 1) * min(1, 0.4 + c)
    g = (v * 255).astype(np.uint8)
    return np.stack([g, g, g, g], -1)


def pattern(name, w, h):
    """Opaque surface patterns for the title scenery and backdrops."""
    kind = h32(name, "pat") % 6
    seed = h32(name, "n")
    n = smooth_noise(w, h, max(4, min(w, h) / 4), seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if kind == 0:      # meadow: stripes of greens with tiny flowers
        base = np.asarray(LEAF, np.float32) * (0.8 + 0.35 * n[..., None])
        f = (smooth_noise(w, h, 2, seed + 1) > 0.78)
        base[f] = (255, 240, 250)
    elif kind == 1:    # sky with soft bands
        t = yy / max(1, h - 1)
        base = (np.asarray(SKY, np.float32) * (1 - t[..., None]) + np.asarray(CREAM, np.float32) * t[..., None]) * (0.95 + 0.1 * n[..., None])
    elif kind == 2:    # tiles
        s = max(4, min(w, h) // 4)
        chk = ((xx // s + yy // s) % 2)[..., None]
        base = np.asarray(MINT, np.float32) * (1 - chk) + np.asarray(CREAM, np.float32) * chk
        base *= 0.92 + 0.12 * n[..., None]
    elif kind == 3:    # wood planks
        g = 0.5 + 0.5 * np.sin(yy * 0.9 + n * 6)
        base = np.asarray((200, 140, 90), np.float32) * (0.8 + 0.25 * g[..., None])
    elif kind == 4:    # pebbles
        v = smooth_noise(w, h, 3, seed + 2)
        base = np.asarray((190, 180, 200), np.float32) * (0.75 + 0.4 * v[..., None])
    else:              # waves
        g = 0.5 + 0.5 * np.sin(xx * 0.5 + np.sin(yy * 0.35) * 2)
        base = np.asarray(TEAL, np.float32) * (0.75 + 0.4 * g[..., None])
    return to_rgba(base)


def ramp_tlut(name, w, h):
    """TLUT stored as an image: a smooth ramp through two theme colours."""
    a, b = pick(name), pick(name, 3)
    n = w * h
    cols = [mix(shade(a, 0.4), a, min(1, 2 * i / n)) if i < n / 2 else mix(a, shade(b, 1.4), 2 * i / n - 1) for i in range(n)]
    arr = np.zeros((h, w, 4), np.uint8)
    arr.reshape(-1, 4)[:, :3] = cols
    arr[..., 3] = 255
    arr.reshape(-1, 4)[0, 3] = 0
    return arr


# ------------------------------------------------------------------ logo and wordmarks
def _text_layer(w, h, s, font_path, size, ss=4):
    f = ImageFont.truetype(font_path, int(size * ss))
    im = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = d.textbbox((0, 0), s, font=f)
    k = min(1.0, (w * ss * 0.94) / max(1, x1 - x0), (h * ss * 0.94) / max(1, y1 - y0))
    if k < 1:
        f = ImageFont.truetype(font_path, int(size * ss * k))
        x0, y0, x1, y1 = d.textbbox((0, 0), s, font=f)
    d.text(((w * ss - (x1 - x0)) / 2 - x0, (h * ss - (y1 - y0)) / 2 - y0), s, font=f, fill=255)
    return im


def wordmark(w, h, s, fill_top=SUN, fill_bot=CORAL, edge=PLUM):
    ss = 4
    lay = _text_layer(w, h, s, FONT_LOGO, h * 0.9)
    from PIL import ImageFilter
    edge_l = lay.filter(ImageFilter.MaxFilter(ss * 2 + 1))
    a = np.asarray(lay, np.float32).reshape(h, ss, w, ss).mean((1, 3)) / 255
    e = np.asarray(edge_l, np.float32).reshape(h, ss, w, ss).mean((1, 3)) / 255
    t = np.linspace(0, 1, h)[:, None, None]
    ink = np.asarray(fill_top, np.float32) * (1 - t) + np.asarray(fill_bot, np.float32) * t
    rgb = np.asarray(edge, np.float32) * np.ones((h, w, 3))
    rgb = rgb * (1 - a[..., None]) + ink * a[..., None]
    hl = np.clip(a - np.roll(a, 1, 0), 0, 1)[..., None]
    rgb = rgb * (1 - hl * 0.5) + 255 * hl * 0.5
    return to_rgba(rgb, np.maximum(a, e) * 255)


LOGO = "TONICTUMBLE"


def logo_letter(i, w, h):
    """One tall logo tile: a letter of TONIC TUMBLE on a bouncing capsule shape."""
    ch = LOGO[i % len(LOGO)]
    top, bot = (THEME[i % 4], shade(THEME[(i + 2) % 4], 0.85))
    im = wordmark(w, h, ch, fill_top=shade(top, 1.25), fill_bot=bot)
    return im


def small_text(w, h, s, ink=CREAM):
    lay = _text_layer(w, h, s, FONT_UI, h * 0.95)
    a = np.asarray(lay, np.float32).reshape(h, 4, w, 4).mean((1, 3))
    g = a.astype(np.uint8)
    return np.stack([g, g, g, g], -1)


# ------------------------------------------------------------------ scenes
SCENES = ["meadow", "seaside", "night", "desert", "snow", "lab", "volcano", "candy", "forest", "space", "garden"]


def scene(name, w, h, idx):
    kind = SCENES[idx % len(SCENES)]
    r = rng("scene", name)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    t = yy / max(1, h - 1)
    pal = {"meadow": (SKY, CREAM, LEAF), "seaside": ((120, 190, 240), (250, 230, 200), TEAL),
           "night": ((30, 30, 80), (90, 70, 140), (40, 60, 90)), "desert": ((250, 190, 120), (255, 230, 170), (220, 150, 90)),
           "snow": ((180, 210, 240), (250, 250, 255), (230, 240, 250)), "lab": ((200, 230, 225), (240, 250, 245), MINT),
           "volcano": ((90, 40, 60), (240, 120, 70), (70, 50, 60)), "candy": ((250, 200, 230), (255, 240, 200), (240, 150, 190)),
           "forest": ((160, 210, 170), (230, 240, 200), (60, 120, 70)), "space": ((15, 15, 40), (60, 30, 90), (90, 80, 120)),
           "garden": ((170, 220, 250), (255, 245, 220), (140, 200, 110))}[kind]
    sky = np.asarray(pal[0], np.float32) * (1 - t[..., None]) + np.asarray(pal[1], np.float32) * t[..., None]
    img = Image.fromarray(np.clip(sky, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img)
    if kind in ("night", "space"):
        for _ in range(60):
            x, y = r.random() * w, r.random() * h * 0.7
            d.point((x, y), fill=(255, 255, 230))
        d.ellipse([w * 0.75, h * 0.1, w * 0.75 + h * 0.18, h * 0.28], fill=(250, 240, 200))
    else:
        cxs = r.random() * w
        d.ellipse([cxs - h * 0.1, h * 0.08, cxs + h * 0.1, h * 0.28], fill=shade(SUN, 1.1))
        for _ in range(4):
            x, y = r.random() * w, r.random() * h * 0.35
            for k in range(3):
                d.ellipse([x + k * 12 - 14, y - 6, x + k * 12 + 14, y + 8], fill=(255, 255, 255, 230))
    # three layers of rolling ground in the scene colour
    g = np.asarray(pal[2], np.float32)
    for layer in range(3):
        base_y = h * (0.55 + 0.15 * layer)
        amp = h * (0.08 - 0.02 * layer)
        ph = r.random() * 6
        pts = [(x, base_y - amp * math.sin(x / w * (2 + layer) * math.pi + ph)) for x in range(0, w + 8, 8)]
        col = tuple(int(v) for v in np.clip(g * (0.8 + 0.15 * layer), 0, 255))
        d.polygon(pts + [(w, h), (0, h)], fill=col)
        if kind in ("forest", "garden", "meadow") and layer == 1:
            for _ in range(6):
                x = r.random() * w
                y = base_y - amp * math.sin(x / w * 3 * math.pi + ph)
                d.ellipse([x - 9, y - 22, x + 9, y - 2], fill=shade(col, 0.8))
                d.rectangle([x - 1.5, y - 4, x + 1.5, y + 2], fill=(120, 80, 50))
        if kind == "candy" and layer == 2:
            for _ in range(8):
                x = r.random() * w
                d.ellipse([x - 5, base_y - 5, x + 5, base_y + 5], fill=pick(f"{name}{x}"))
    arr = np.asarray(img, np.uint8).copy()
    arr[..., 3] = 255
    return arr


def frame(name, w, h, windows):
    """Screen frame: our tiled border pattern with transparent windows kept where the game shows the play area."""
    base = pattern(name + "frame", w, h).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    stripe = ((xx + yy) // 6) % 2 == 0
    base[stripe, :3] = base[stripe, :3] * 0.9
    for x0, y0, x1, y1 in windows:
        base[y0:y1, x0:x1, 3] = 0
        # rounded bezel around the window
        for k, col in ((3, shade(PLUM, 0.9)), (1, CREAM)):
            ys, ye, xs, xe = max(0, y0 - k), min(h, y1 + k), max(0, x0 - k), min(w, x1 + k)
            m = np.zeros((h, w), bool)
            m[ys:ye, xs:xe] = True
            m[y0:y1, x0:x1] = False
            base[m & (base[..., 3] > 0), :3] = col
    return np.clip(base, 0, 255).astype(np.uint8)


def strip_ramp(name, w, h):
    """Tall gradient strips (backdrop ramps): stepped bands, sky to cream to plum to teal."""
    cols = [SKY, CREAM, CORAL, PLUM, TEAL]
    t = np.linspace(0, 1, h)
    k = np.minimum((t * len(cols)).astype(int), len(cols) - 1)
    frac = (t * len(cols)) % 1
    nxt = np.minimum(k + 1, len(cols) - 1)
    c = np.asarray(cols, np.float32)
    rows = c[k] * (1 - frac[:, None] ** 4) + c[nxt] * frac[:, None] ** 4
    rows *= (0.78 + 0.22 * (np.sin(np.arange(h) / 5.0) > 0))[:, None]
    return to_rgba(np.repeat(rows[:, None, :], w, 1))
