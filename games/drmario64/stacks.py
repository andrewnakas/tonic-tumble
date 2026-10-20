"""CLEAN ROOM: word stacks drawn through an alpha mask (menu_setup / game_ls selectors).

The game draws these with StretchAlphaTex: an rgba16 colour texture plus an i4 mask of the same
layout. Both are drawn here from one layout, so the letters and the mask always line up.
Layout facts read off the screen (which words, in which order); the colours are our theme.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from games.drmario64.labels import FONT

SS = 4
# Tonic Tumble theme colours (ours)
BLUE, YELLOW, RED, GREEN, ORANGE = (40, 150, 175), (255, 205, 80), (240, 100, 115), (110, 190, 90), (250, 140, 90)
LIME = (170, 230, 120)

# colour texture, mask texture, row height, rows [(text, ink)], underline
STACKS = [
    ("menu_setup_titexdata_07_texs_tex", "menu_setup_titexdata_00_texs_tex", 12,
     [(str(i % 10), LIME) for i in range(1, 11)], False),
    ("menu_setup_titexdata_08_texs_tex", "menu_setup_titexdata_01_texs_tex", 12,
     [("1P", RED), ("2P", BLUE), ("3P", YELLOW), ("4P", GREEN), ("COM1", BLUE), ("COM1", YELLOW),
      ("COM", GREEN), ("COM2", YELLOW), ("COM2", GREEN), ("COM3", GREEN), ("COM", BLUE)], False),
    ("menu_setup_titexdata_09_texs_tex", "menu_setup_titexdata_02_texs_tex", 16,
     [("EASY", BLUE), ("NORMAL", YELLOW), ("HARD", RED), ("S.HARD", RED)], True),
    ("menu_setup_titexdata_10_texs_tex", "menu_setup_titexdata_03_texs_tex", 16,
     [("EASY", BLUE), ("NORMAL", YELLOW), ("HARD", RED)], True),
    ("menu_setup_titexdata_11_texs_tex", "menu_setup_titexdata_04_texs_tex", 16, [("O K", ORANGE)], False),
    ("menu_setup_titexdata_12_texs_tex", "menu_setup_titexdata_05_texs_tex", 16,
     [("LOW", BLUE), ("MED", YELLOW), ("HI", RED)], True),
    ("menu_setup_titexdata_13_texs_tex", "menu_setup_titexdata_06_texs_tex", 16,
     [("LOW", BLUE), ("MED", YELLOW), ("HI", RED)], True),
    ("game_ls_titexdata_05_texs_tex", "game_ls_titexdata_03_texs_tex", 16,
     [("LOW", BLUE), ("MED", YELLOW), ("HI", RED)], True),
]
STACKS += [
    ("game_al_titexdata_13_texs_tex", "game_al_titexdata_18_texs_tex", 20, [(str(i % 10), LIME) for i in range(1, 11)], False),
    ("game_al_titexdata_14_texs_tex", "game_al_titexdata_19_texs_tex", 13, [("DEMO  RUN", ORANGE)], False),
    ("game_al_titexdata_15_texs_tex", "game_al_titexdata_20_texs_tex", 15, [("RERUN", BLUE)], False),
    ("game_al_titexdata_23_texs_tex", "game_al_titexdata_24_texs_tex", 11, [("PUSH ANY BUTTON", BLUE)], False),
    ("game_al_titexdata_27_texs_tex", "game_al_titexdata_28_texs_tex", 13, [("PUSH ANY BUTTON", BLUE)], False),
    ("title_bmp_01_tex", "title_bmp_02", 16, [("PUSH ANY BUTTON", RED)], False),
]
SHADOWS = {"title_bmp_02"}     # drawn as a dark drop shadow (ci4), not an intensity mask
BY_NAME = {}
for _c, _m, _rh, _rows, _ul in STACKS:
    BY_NAME[_c] = ("colour", _c, _m, _rh, _rows, _ul)
    BY_NAME[_m] = ("mask", _c, _m, _rh, _rows, _ul)


def _layers(w, h, rh, rows, underline):
    ink = Image.new("L", (w * SS, h * SS), 0)
    colour = Image.new("RGB", (w * SS, h * SS), (0, 0, 0))
    bar = Image.new("L", (w * SS, h * SS), 0)
    d = ImageDraw.Draw(ink)
    for i, (text, rgb) in enumerate(rows):
        y0 = i * rh
        size = (rh - (3 if underline else 1)) * SS * 1.2
        f = ImageFont.truetype(FONT, int(size))
        x0, t0, x1, t1 = d.textbbox((0, 0), text, font=f)
        room = (w - 2) * SS
        if x1 - x0 > room:
            f = ImageFont.truetype(FONT, int(size * room / (x1 - x0)))
            x0, t0, x1, t1 = d.textbbox((0, 0), text, font=f)
        tx = (w * SS - (x1 - x0)) / 2 - x0
        ty = y0 * SS + ((rh - (2 if underline else 0)) * SS - (t1 - t0)) / 2 - t0
        row = Image.new("L", (w * SS, h * SS), 0)
        ImageDraw.Draw(row).text((tx, ty), text, font=f, fill=255)
        ink.paste(255, (0, 0), row)
        colour.paste(rgb, (0, 0), row)
        if underline:
            ImageDraw.Draw(bar).rectangle([SS, (y0 + rh - 3) * SS, (w - 1) * SS, (y0 + rh - 1) * SS], fill=255)
    return ink, colour, bar


def render(name, d):
    if name not in BY_NAME:
        return None
    kind, c, m, rh, rows, underline = BY_NAME[name]
    w, h = d["w"], d["h"]
    ink, colour, bar = _layers(w, h, rh, rows, underline)
    outline = ink.filter(ImageFilter.MaxFilter(2 * SS + 1))
    down = lambda im: np.asarray(im, np.float32).reshape(h, SS, w, SS, -1).mean((1, 3)) if np.asarray(im).ndim == 3 \
        else np.asarray(im, np.float32).reshape(h, SS, w, SS).mean((1, 3))
    a_ink, a_out, a_bar = down(ink) / 255, down(outline) / 255, down(bar) / 255
    if kind == "mask" and m in SHADOWS:
        out = np.zeros((h, w, 4), np.uint8)
        out[..., :3] = (30, 20, 20)
        out[..., 3] = (np.maximum(a_out, a_bar) > 0.3) * 255
        return out
    if kind == "mask":
        v = np.clip(np.maximum(a_out, a_bar), 0, 1) * 255
        return np.repeat(v[..., None], 4, -1).astype(np.uint8)
    col = down(colour)
    rgb = np.zeros((h, w, 3), np.float32)                      # dark outline
    rgb = rgb * (1 - a_bar[..., None]) + np.array(RED, np.float32) * a_bar[..., None]
    rgb = rgb * (1 - a_ink[..., None]) + (col / np.maximum(a_ink[..., None], 1e-3)) * a_ink[..., None]
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255)
    out[..., 3] = (np.maximum(a_out, a_bar) > 0.3) * 255
    return out
