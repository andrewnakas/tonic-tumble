"""Clean fonts for Dr. Mario 64, drawn with OFL/Apache fonts (see fonts/) into the game's glyph slots.

Slot -> character comes from the decomp's own tables in src/main_segment/font.c
(font_e_tbl/font_e2_tbl: ASCII -> slot and advance width; char_code_tbl: Shift-JIS -> slot).

  font_e_tex   10x12 cells, ASCII          (glyph)
  font_e2_tex  20x12 cells, ASCII          (glyph | outline), drawn in two passes
  font_2_tex   24x12 cells, kana/kanji     (glyph | outline)
  font_a_tex   12x12 cells, kana/kanji     (glyph)
  sDebugPrintFontTex  160x48, 8x8 ASCII debug font
"""
import os
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
LATIN = os.path.join(FONT_DIR, "Rubik.ttf")
ROUNDED = os.path.join(FONT_DIR, "MPLUSRounded1c-ExtraBold.ttf")
PIXEL = os.path.join(FONT_DIR, "PressStart2P-Regular.ttf")

# font_e slots the ASCII table does not reach (the decomp's table maps these codes to the
# placeholder slot); characters read off the slot order next to their neighbours.
E_EXTRA = {}
# what the game shows in the slot of these codes
SUBST = {"*": "®", "\\": "¥", "_": "–"}


def _font_c(src_root):
    return open(os.path.join(src_root, "src/main_segment/font.c"), encoding="utf-8").read()


def ascii_table(src_root, name):
    txt = _font_c(src_root)
    body = txt[txt.index(f"struct_800A6F70 {name}[0x80] = {{"):]
    body = body[:body.index("};")]
    out = {}
    for m in re.finditer(r"/\* 0x([0-9A-F]{2}) .*?\*/ \{ (0x[0-9A-F]+|\d+), (0x[0-9A-F]+|\d+) \}", body):
        out[int(m.group(1), 16)] = (int(m.group(2), 0), int(m.group(3), 0))
    return out


def sjis_slots(src_root):
    txt = _font_c(src_root)
    body = txt[txt.index("u16 char_code_tbl[0x1860] = {"):]
    body = body[body.index("{") + 1:body.index("};")]
    tbl = [int(v, 0) for v in re.findall(r"0x[0-9A-Fa-f]+|\d+", body)]
    slots = {}
    for n, idx in enumerate(tbl):
        if idx in slots or idx == 0:
            continue
        hi, lo = n >> 8, n & 0xFF
        if 0x01 <= hi <= 0x1F:
            b = bytes([hi + 0x80, lo])
        elif 0x20 <= hi <= 0x2F:
            b = bytes([hi + 0xC0, lo])
        else:
            continue
        try:
            slots[idx] = b.decode("shift_jis")
        except UnicodeDecodeError:
            pass
    counts = {}
    for idx in tbl:
        counts[idx] = counts.get(idx, 0) + 1
    placeholder = max(counts, key=counts.get)
    slots.pop(placeholder, None)
    return slots, placeholder


def glyph(ch, w, h, font=LATIN, size=None, adv=None, bold=0):
    """White-on-black glyph mask (float 0..1) of cell w x h, left aligned within `adv` px."""
    adv = adv or w
    size = size or h
    ss = 4
    f = ImageFont.truetype(font, int(size * ss))
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    x0, y0, x1, y1 = probe.textbbox((0, 0), ch, font=f)
    gh = y1 - y0
    if gh > (h - 1) * ss:
        f = ImageFont.truetype(font, max(4, int(size * ss * (h - 1) * ss / gh)))
    asc, desc = f.getmetrics()
    big = Image.new("L", (w * ss * 3, h * ss), 0)
    d = ImageDraw.Draw(big)
    d.text((w * ss, (h * ss - (asc + desc)) // 2), ch, font=f, fill=255, stroke_width=bold * ss // 2)
    bb = big.getbbox()
    img = Image.new("L", (w * ss, h * ss), 0)
    if bb:
        crop = big.crop((bb[0], 0, bb[2], h * ss))
        room = (adv - 1) * ss
        if crop.width > room:   # narrow advance: squeeze horizontally, keep the height
            crop = crop.resize((max(ss, room), h * ss), Image.LANCZOS)
        img.paste(crop, ((room - crop.width) // 2, 0))
    a = np.asarray(img, np.float32).reshape(h, ss, w, ss).mean((1, 3)) / 255.0
    return np.clip(a * 1.25, 0, 1)


def outline(mask, r=1):
    p = np.pad(mask, r)
    h, w = mask.shape
    out = np.zeros_like(mask)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r + 1:
                out = np.maximum(out, p[r + dy:r + dy + h, r + dx:r + dx + w])
    return out


def _to_rgba(a):
    # 4 ink levels: crisp at 12 px and compresses well (main_segment has a fixed ROM slot)
    v = (np.round(np.clip(a, 0, 1) * 3) * 85).astype(np.uint8)
    return np.stack([v, v, v, v], -1)


def font_e(src_root, cells=94, two=False):
    tbl = ascii_table(src_root, "font_e2_tbl" if two else "font_e_tbl")
    slot_ch = {}
    for code, (idx, wid) in tbl.items():
        if idx and wid != 0xFF and code >= 0x20 and idx not in slot_ch:
            slot_ch[idx] = (SUBST.get(chr(code), chr(code)), wid)
    for idx, v in E_EXTRA.items():
        slot_ch.setdefault(idx, v)
    cw = 10
    out = np.zeros((cells * 12, cw * (2 if two else 1)), np.float32)
    for idx, (ch, wid) in slot_ch.items():
        k = idx - 1
        if not 0 <= k < cells:
            continue
        g = glyph(ch, cw, 12, LATIN, size=12, adv=min(cw, max(3, wid)), bold=1)
        out[k * 12:(k + 1) * 12, :cw] = g
        if two:
            out[k * 12:(k + 1) * 12, cw:] = outline(g, 1)
    return _to_rgba(out), slot_ch


def font_jp(src_root, cells=322, two=False):
    slots, _ = sjis_slots(src_root)
    cw = 12
    out = np.zeros((cells * 12, cw * (2 if two else 1)), np.float32)
    for idx, ch in slots.items():
        k = idx - 1
        if not 0 <= k < cells:
            continue
        g = glyph(ch, cw, 12, ROUNDED, size=12)
        out[k * 12:(k + 1) * 12, :cw] = g
        if two:
            out[k * 12:(k + 1) * 12, cw:] = outline(g, 1)
    return _to_rgba(out), slots


def debug_font(w=160, h=48):
    """8x8 cells, 20 per row, ASCII from 0x20."""
    out = np.zeros((h, w), np.float32)
    for k in range((w // 8) * (h // 8)):
        ch = chr(0x20 + k)
        if ch.isprintable():
            y, x = (k // (w // 8)) * 8, (k % (w // 8)) * 8
            out[y:y + 8, x:x + 8] = glyph(ch, 8, 8, PIXEL, size=7)
    return _to_rgba(out)
