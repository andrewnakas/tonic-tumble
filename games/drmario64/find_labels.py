"""DIRTY ROOM: find text boxes inside textures and make numbered crop sheets for transcription.

    python -m games.drmario64.find_labels <uncompressed baserom> <out dir> [name regex]

Writes <out>/label_boxes.json: {texture: [[x, y, w, h, ink rgb, edge rgb, plate rgb], ...]}
(positions and three coarse colours per box are the kept facts), and sheets
<out>/crops_NN.png with each box enlarged and numbered, so the words can be typed into
games/drmario64/tex_labels.json as {"<texture>#<box index>": "text"}.
Nothing here is published; tex_labels.json holds only words, spec/label_boxes.json only boxes and colours.
"""
import json
import os
import re
import sys

import numpy as np
from scipy import ndimage

from cleanroom.gfx import png
from games.drmario64.look import decode, SPEC


def boxes_for(im):
    rgb = im[..., :3].astype(np.float32)
    a = ndimage.binary_erosion(im[..., 3] >= 128, iterations=1)
    sat = rgb.max(-1) - rgb.min(-1)
    lum = rgb.mean(-1)
    # plate = the local low-saturation surface; ink = strongly saturated pixels, or very bright/dark
    # pixels on a mid-tone plate (white/black lettering)
    bg = np.stack([ndimage.median_filter(rgb[..., c], size=15) for c in range(3)], -1)
    bgsat = bg.max(-1) - bg.min(-1)
    mask = a & (((sat > 100) & (bgsat < 90)) | ((np.abs(lum - bg.mean(-1)) > 80) & (sat < 60)))
    joined = ndimage.binary_dilation(mask, structure=np.ones((2, 5), bool))
    lab, n = ndimage.label(joined)
    H, W = mask.shape
    out = []
    for sl in ndimage.find_objects(lab):
        ys, xs = sl
        h, w = ys.stop - ys.start, xs.stop - xs.start
        if not (5 <= h <= 40 and w >= 5) or (h > 0.8 * H and w > 0.8 * W and H * W > 900):
            continue
        m = mask[sl]
        if m.sum() < 10 or m.mean() > 0.8 or (h < 8 and w > 6 * h):   # plate edges, rules
            continue
        box = rgb[sl]
        inkpx = box[m]
        ink = np.median(inkpx, 0)
        ring = ndimage.binary_dilation(m, iterations=1) & ~m
        edge = box[ring].mean(0) if ring.any() else np.zeros(3)
        plate = bg[sl][~m].mean(0) if (~m).any() else np.array([128, 128, 128])
        out.append([int(xs.start), int(ys.start), int(w), int(h),
                    [int(v) for v in ink], [int(v) for v in edge], [int(v) for v in plate]])
    out.sort(key=lambda b: (b[1] // 4, b[0]))
    return out


def label_png(text, h=9):
    """Tiny number label as an RGBA array (PIL default font)."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (8 * len(text) + 4, h + 4), (255, 255, 0, 255))
    ImageDraw.Draw(img).text((2, 1), text, fill=(0, 0, 0, 255))
    return np.asarray(img)


def main(argv):
    rom = open(argv[1], "rb").read()
    out = argv[2]
    rx = re.compile(argv[3]) if len(argv) > 3 else None
    os.makedirs(out, exist_ok=True)
    texs = json.load(open(os.path.join(SPEC, "textures.json")))
    pals = json.load(open(os.path.join(SPEC, "palettes.json")))
    found, crops = {}, []
    for name, d in texs.items():
        if rx and not rx.search(name):
            continue
        if "font" in name.lower() or name.startswith("anime_"):
            continue
        im = decode(rom, d, pals)
        if (im[..., 3] >= 128).mean() < 0.6:   # cut-out shapes: the kept alpha outline already carries them
            continue
        bx = boxes_for(im)
        if not bx:
            continue
        found[name] = bx
        for k, b in enumerate(bx):
            x, y, w, h = b[:4]
            c = im[max(0, y - 1):y + h + 1, max(0, x - 1):x + w + 1]
            crops.append((f"{len(crops)}", name, k, np.repeat(np.repeat(c, 3, 0), 3, 1)))
    json.dump(found, open(os.path.join(out, "label_boxes.json"), "w"))
    index = {c[0]: f"{c[1]}#{c[2]}" for c in crops}
    json.dump(index, open(os.path.join(out, "crop_index.json"), "w"), indent=0)
    # sheets: rows of numbered crops, max 1600 px wide, ~1000 px tall each
    sheets, row, rows, x, rowh = [], [], [], 0, 0
    W = 1600

    def flush_sheet():
        if not rows:
            return
        hh = sum(r[1] for r in rows) + 4 * len(rows)
        sh = np.zeros((hh, W, 4), np.uint8)
        sh[..., :3] = (40, 40, 60)
        sh[..., 3] = 255
        yy = 0
        for items, rh in rows:
            for xx, tile in items:
                th, tw = tile.shape[:2]
                tw = min(tw, W - xx)
                t = tile[:, :tw].astype(np.float32)
                al = t[..., 3:4] / 255
                sh[yy:yy + th, xx:xx + tw, :3] = (sh[yy:yy + th, xx:xx + tw, :3] * (1 - al) + t[..., :3] * al).astype(np.uint8)
            yy += rh + 4
        png.write(os.path.join(out, f"crops_{len(sheets):02d}.png"), sh)
        sheets.append(hh)
        rows.clear()

    total_h = 0
    for num, name, k, big in crops:
        lab = label_png(num)
        th = max(big.shape[0], lab.shape[0])
        tile = np.zeros((th, lab.shape[1] + big.shape[1] + 2, 4), np.uint8)
        tile[:lab.shape[0], :lab.shape[1]] = lab
        tile[:big.shape[0], lab.shape[1] + 2:] = big
        if x and x + tile.shape[1] > W:
            rows.append((row, rowh))
            total_h += rowh + 4
            row, x, rowh = [], 0, 0
            if total_h > 1000:
                flush_sheet()
                total_h = 0
        row.append((x, tile))
        x += tile.shape[1] + 12
        rowh = max(rowh, th)
    if row:
        rows.append((row, rowh))
    flush_sheet()
    print(f"{len(found)} textures with {len(crops)} boxes -> {len(sheets)} sheets in {out}")


if __name__ == "__main__":
    main(sys.argv)


def refit(rom, boxes_path):
    """Recompute the three colours of already-chosen boxes (positions unchanged)."""
    texs = json.load(open(os.path.join(SPEC, "textures.json")))
    pals = json.load(open(os.path.join(SPEC, "palettes.json")))
    boxes = json.load(open(boxes_path))
    for name, bx in boxes.items():
        im = decode(rom, texs[name], pals)
        rgb = im[..., :3].astype(np.float32)
        for k, b in bx.items():
            x, y, w, h = b[:4]
            box = rgb[y:y + h, x:x + w].reshape(-1, 3)
            lum = box.mean(1)
            sat = box.max(1) - box.min(1)
            plate = np.median(box[np.argsort(np.abs(lum - np.median(lum)))[:max(1, len(box) // 3)]], 0)
            score = sat + np.abs(lum - plate.mean())
            top = box[np.argsort(-score)[:max(1, len(box) // 6)]]
            ink = top[np.argsort(-(top.max(1) - top.min(1)))[:max(1, len(top) // 2)]].mean(0)
            edge = box[np.argsort(lum)[:max(1, len(box) // 8)]].mean(0)
            if abs(edge.mean() - ink.mean()) < 60:   # light outline on dark ink
                edge = box[np.argsort(-lum)[:max(1, len(box) // 8)]].mean(0)
            bx[k] = [x, y, w, h, [int(v) for v in ink], [int(v) for v in edge], [int(v) for v in plate]]
    json.dump(boxes, open(boxes_path, "w"), indent=0)
