"""CLEAN ROOM: re-typeset the words baked into menu/HUD textures.

Inputs: tex_labels.json (the words) and spec/label_boxes.json (per box: position; its colour
columns are no longer used). The background is our panel art (art/); each box gets a pad in a
colour taken from our panel, then the text in our font with a 1 px edge in our own colours. Syntax in the words: see labels_import.py.
"""
import functools
import json
import os
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "fonts", "LilitaOne-Regular.ttf")
JP_FONT = os.path.join(HERE, "fonts", "MPLUSRounded1c-ExtraBold.ttf")
SS = 4

# colours that CI palettes must keep for readable labels: texture -> list of rgb
RESERVED = {}


@functools.lru_cache(None)
def _data():
    words = json.load(open(os.path.join(HERE, "tex_labels.json"), encoding="utf-8"))
    boxes = json.load(open(os.path.join(HERE, "spec", "label_boxes.json")))
    per = {}
    for key, text in words.items():
        tex, k = key.split("#")
        per.setdefault(tex, []).append((k, text))
    return per, boxes


def _font(size, text):
    jp = any(ord(c) > 0x2000 for c in text)
    return ImageFont.truetype(JP_FONT if jp else FONT, max(4, int(size)))


def _cap_height(size_px):
    return size_px


def _parse(text):
    opt = {"h": "c", "v": "c", "size": None, "merge": False, "ext": None}
    m = re.match(r"^\{(\d+)\}", text)
    if m:
        opt["size"] = int(m.group(1))
        text = text[m.end():]
    while text[:1] in "<>^_+" and len(text) > 1:
        c, text = text[0], text[1:]
        if c == "<":
            opt["h"] = "l"
        elif c == ">":
            opt["h"] = "r"
        elif c == "^":
            opt["v"] = "t"
        elif c == "_":
            opt["v"] = "b"
        elif c == "+":
            opt["merge"] = True
    if "@" in text:
        text, ext = text.rsplit("@", 1)
        opt["ext"] = ext
    return text, opt


def _draw_text(layer_ink, layer_edge, text, x, y, w, h, opt):
    """Draw one cell of text (may contain | line breaks) into supersampled masks; returns ink bbox."""
    lines = text.split("|")
    n = len(lines)
    lh = h / n
    size = opt["size"] or lh * 1.15   # font size in px ~ cap height / 0.72; ink box ~ cap height
    boxes = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        sz = size
        f = _font(sz * SS, line)
        d = ImageDraw.Draw(layer_ink)
        x0, y0, x1, y1 = d.textbbox((0, 0), line, font=f)
        # fit width (leave 1 px each side), squeeze no more than 20% before shrinking
        room = (w - 2) * SS
        sx = 1.0
        if x1 - x0 > room:
            sx = max(0.8, room / (x1 - x0))
            if (x1 - x0) * sx > room:
                f = _font(sz * SS * room / ((x1 - x0) * sx), line)
                x0, y0, x1, y1 = d.textbbox((0, 0), line, font=f)
        tw, th = (x1 - x0) * sx, y1 - y0
        cy = (y + lh * i) * SS
        if opt["v"] == "t" and n == 1:
            ty = y * SS + SS
        elif opt["v"] == "b" and n == 1:
            ty = (y + h) * SS - th - SS
        else:
            ty = cy + (lh * SS - th) / 2
        if opt["h"] == "l":
            tx = (x + 1) * SS
        elif opt["h"] == "r":
            tx = (x + w - 1) * SS - tw
        else:
            tx = x * SS + (w * SS - tw) / 2
        # render the line alone, squeeze horizontally, paste into the layers
        tmp = Image.new("L", (int(x1 - x0) + 4 * SS, int(y1 - y0) + 4 * SS), 0)
        ImageDraw.Draw(tmp).text((2 * SS - x0, 2 * SS - y0), line, font=f, fill=255)
        if sx != 1.0:
            tmp = tmp.resize((max(1, int(tmp.width * sx)), tmp.height), Image.LANCZOS)
        edge = tmp.filter(__import__("PIL.ImageFilter", fromlist=["x"]).MaxFilter(2 * SS + 1))
        px, py = int(tx - 2 * SS), int(ty - 2 * SS)
        layer_edge.paste(255, (px, py), edge)
        layer_ink.paste(255, (px, py), tmp)
        boxes.append((px, py, px + tmp.width, py + tmp.height))
    return boxes


def our_colours(base, x, y, w, h):
    """Ink/edge/plate from our own panel under the box (light ink on dark panels and vice versa)."""
    H, W = base.shape[:2]
    reg = base[max(0, y):min(H, y + h), max(0, x):min(W, x + w), :3].reshape(-1, 3)
    plate = reg.mean(0) if len(reg) else np.array([120, 215, 190], np.float32)
    lum = plate @ np.array([0.3, 0.59, 0.11])
    if lum < 140:
        return (255, 246, 220), tuple(int(v) for v in plate * 0.35), tuple(int(v) for v in plate)
    return (70, 40, 100), (255, 250, 235), tuple(int(v) for v in np.minimum(255, plate * 1.05))


def render(name, base):
    """base: (h, w, 4) uint8 default rendering. Returns the labelled image or None."""
    per, allboxes = _data()
    if name not in per:
        return None
    im = base.astype(np.float32).copy()
    H, W = im.shape[:2]
    bx = allboxes[name]
    items = []
    consumed = set()
    for k, text in per[name]:
        text, opt = _parse(text)
        x, y, w, h = bx[k][:4]
        ink, edge, plate = our_colours(base, x, y, w, h)
        if opt["ext"] is not None and opt["ext"] in bx:
            ox, oy, ow, oh = bx[opt["ext"]][:4]
            x2, y2 = max(x + w, ox + ow), max(y + h, oy + oh)
            x, y = min(x, ox), min(y, oy)
            w, h = x2 - x, y2 - y
            consumed.add(opt["ext"])
        items.append([k, text, opt, [x, y, w, h], ink, edge, plate])
    # '+' merges: union with the overlapping box, words appended
    for it in [i for i in items if i[2]["merge"]]:
        x, y, w, h = it[3]
        for other in items:
            if other is it or other[2]["merge"]:
                continue
            ox, oy, ow, oh = other[3]
            if x < ox + ow and ox < x + w and y < oy + oh and oy < y + h:
                x2, y2 = max(x + w, ox + ow), max(y + h, oy + oh)
                nx, ny = min(x, ox), min(y, oy)
                other[3] = [nx, ny, x2 - nx, y2 - ny]
                other[1] = other[1] + " " + it[1]
                break
        consumed.add(it[0])
    ink_l = Image.new("L", (W * SS, H * SS), 0)
    reserved = []
    for k, text, opt, (x, y, w, h), ink, edge, plate in items:
        if k in consumed:
            continue
        ink_l = Image.new("L", (W * SS, H * SS), 0)
        edge_l = Image.new("L", (W * SS, H * SS), 0)
        cells = text.split("||")
        cw = w / len(cells)
        for i, cell in enumerate(cells):
            _draw_text(ink_l, edge_l, cell, x + cw * i, y, cw, h, opt)
        a_ink = np.asarray(ink_l, np.float32).reshape(H, SS, W, SS).mean((1, 3)) / 255
        a_edge = np.asarray(edge_l, np.float32).reshape(H, SS, W, SS).mean((1, 3)) / 255
        # plate pad: the box area, softened toward its border
        pad = np.zeros((H, W), np.float32)
        pad[max(0, y):y + h, max(0, x):x + w] = 1.0
        pad = np.minimum(pad, a_edge * 0 + pad)
        from scipy import ndimage
        pad = ndimage.uniform_filter(pad, 3)
        rgb = im[..., :3]
        pl = np.asarray(plate, np.float32)
        rgb[:] = rgb * (1 - pad[..., None] * 0.7) + pl * pad[..., None] * 0.7
        rgb[:] = rgb * (1 - a_edge[..., None]) + np.asarray(edge, np.float32) * a_edge[..., None]
        rgb[:] = rgb * (1 - a_ink[..., None]) + np.asarray(ink, np.float32) * a_ink[..., None]
        reserved += [tuple(ink), tuple(edge), tuple(plate)]
    RESERVED[name] = reserved
    return np.clip(im, 0, 255).astype(np.uint8)
