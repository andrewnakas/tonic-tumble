"""CLEAN ROOM: character portraits for the select screens: our own characters (art/chars.py)
drawn as head-and-shoulders cards, with captions using our names (names.json).

LAYOUTS: where portraits (and their name captions) sit inside the game's portrait textures
(cell positions are layout facts read off the screen). The frame/background of each texture
is our panel art.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from games.drmario64.art import chars
from games.drmario64.labels import FONT

# select-grid order (layout fact) with our characters
GRID = ["Dr. Fenna", "Grudge", "Prickle", "Loom", "Satin",
        "Pomme", "Wobble", "Inko", "Rotor", "Clod",
        "Anvil-Bot", "Prof. Murk", "Jinx", "?", "?"]

# texture -> (cells [(character, x, y, w, h, caption or None)], extra captions [(text, x, y, w, h, ink)])
LAYOUTS = {
    "menu_char_titexdata_05_texs_tex": (
        [(GRID[r * 5 + c], [14, 68, 122, 176, 229][c], [14, 68, 121][r], 38, 40, None if GRID[r * 5 + c] == "?" else GRID[r * 5 + c])
         for r in range(3) for c in range(5)],
        [("Pick a player!", 60, 0, 170, 12, (255, 230, 120))]),
    "menu_p4_titexdata_00_texs_tex": (
        [(f, 0, 35 * k, 48, 35, None) for k, f in enumerate(
            ["Dr. Fenna", "Grudge", "Satin", "Prickle", "Wobble", "Rotor", "Loom", "Pomme", "Clod", "Inko",
             "Anvil-Bot", "Prof. Murk", "Jinx", "Chrome Fenna", "Night Grudge"])], []),
    "menu_char_titexdata_03_texs_tex": ([("Chrome Fenna", 6, 3, 38, 38, "Chrome Fenna")], []),
    "menu_char_titexdata_04_texs_tex": ([("Night Grudge", 7, 3, 38, 38, "Night Grudge")], []),
}


def _question(w, h):
    img = Image.new("L", (w * 4, h * 4), 0)
    f = ImageFont.truetype(FONT, int(h * 4 * 0.9))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = d.textbbox((0, 0), "?", font=f)
    d.text(((w * 4 - (x1 - x0)) / 2 - x0, (h * 4 - (y1 - y0)) / 2 - y0), "?", font=f, fill=255)
    return np.asarray(img, np.float32).reshape(h, 4, w, 4).mean((1, 3)) / 255


def paint_face(name, w, h, seed=0):
    if name == "?":
        out = np.zeros((h, w, 3), np.float32) + np.array([70, 80, 110], np.float32)
        q = _question(w, h)
        return out * (1 - q[..., None]) + np.array([255, 230, 120]) * q[..., None]
    return chars.portrait(name, w, h)


def caption(im, text, x, y, w, h, ink=(255, 246, 220), edge=(60, 40, 90)):
    H, W = im.shape[:2]
    SS = 4
    layer = Image.new("L", (W * SS, H * SS), 0)
    f = ImageFont.truetype(FONT, int(h * SS * 1.1))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = d.textbbox((0, 0), text, font=f)
    if x1 - x0 > w * SS:
        f = ImageFont.truetype(FONT, int(h * SS * 1.1 * w * SS / (x1 - x0)))
        x0, y0, x1, y1 = d.textbbox((0, 0), text, font=f)
    d.text(((x + w / 2) * SS - (x1 - x0) / 2 - x0, (y + h / 2) * SS - (y1 - y0) / 2 - y0), text, font=f, fill=255)
    out_l = layer.filter(ImageFilter.MaxFilter(2 * SS + 1))
    a = np.asarray(layer, np.float32).reshape(H, SS, W, SS).mean((1, 3)) / 255
    o = np.asarray(out_l, np.float32).reshape(H, SS, W, SS).mean((1, 3)) / 255
    im[..., :3] = im[..., :3] * (1 - o[..., None]) + np.asarray(edge, np.float32) * o[..., None]
    im[..., :3] = im[..., :3] * (1 - a[..., None]) + np.asarray(ink, np.float32) * a[..., None]


def render(name, base):
    if name not in LAYOUTS:
        return None
    cells, extra = LAYOUTS[name]
    im = base.astype(np.float32).copy()
    for k, (face, x, y, w, h, cap) in enumerate(cells):
        if cap:                                                       # framed cells (select grids)
            im[max(0, y - 2):y + h + 2, max(0, x - 2):x + w + 2, :3] = (60, 40, 90)
            im[max(0, y - 1):y + h + 1, max(0, x - 1):x + w + 1, :3] = (250, 205, 80)
        hh = min(h, im.shape[0] - y)
        im[y:y + hh, x:x + w, :3] = paint_face(face, w, h, seed=k)[:hh]
        if cap:
            caption(im, cap, x - 7, y + h + 1, w + 14, 9)
    for text, x, y, w, h, ink in extra:
        caption(im, text, x, y, w, h, ink=ink)
    return np.clip(im, 0, 255).astype(np.uint8)
