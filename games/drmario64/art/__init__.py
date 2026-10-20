"""CLEAN ROOM: Tonic Tumble art. `texture(name, d)` returns an RGBA image for any texture.

Uses only the texture's name, format, size, palette grouping and `cut` (coarse opaque
fraction). Fonts, word stacks and bottle tiles have their own hooks (fonts.py, stacks.py,
tiles.py); labels.py and portraits.py draw on top of the panels made here.
"""
import functools
import json
import os
import re

import numpy as np

from games.drmario64.art import chars, ui

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(HERE, "spec")


@functools.lru_cache(None)
def _spec():
    tex = json.load(open(os.path.join(SPEC, "textures.json")))
    paths = json.load(open(os.path.join(SPEC, "png_paths.json")))
    lay = json.load(open(os.path.join(SPEC, "art_layout.json")))
    sets = {}
    for n in tex:
        m = re.match(r"assets/anime/anime_(\w+?)/", paths[n])
        if m:
            sets.setdefault(m.group(1), []).append(n)
    frames = {}
    for k, names in sets.items():
        names.sort(key=lambda n: int(re.search(r"titexdata_(\d+)", n).group(1)) if "titexdata_" in n else 0)
        for i, n in enumerate(names):
            frames[n] = (k, i, len(names))
    letters = sorted(n for n, d in tex.items() if paths[n].startswith("assets/title/") and (d["w"], d["h"]) == (24, 74))
    # the title's bouncing character cards (ci8, D_0501CC20..D_0502C2C0): runs of same-size frames
    cast = sorted(n for n, d in tex.items() if n.startswith("D_05") and d["fmt"] == "ci8"
                  and 0x0501CC20 <= int(n[2:], 16) <= 0x0502C2C0)
    roster = ["Dr. Fenna", "Grudge", "Rotor", "Pomme", "Wobble", "Inko", "Prickle", "Jinx", "Loom", "Clod",
              "Satin", "Anvil-Bot", "Prof. Murk"]
    runs, prev = [], None
    for n in cast:
        size = (tex[n]["w"], tex[n]["h"])
        if size != prev:
            runs.append([])
        runs[-1].append(n)
        prev = size
    for k, run in enumerate(runs):
        for i, n in enumerate(run):
            frames[n] = ("title:" + roster[k % len(roster)], i * 2, max(5, len(run) * 2))
    return tex, paths, lay, frames, {n: i for i, n in enumerate(letters)}


def texture(name, d):
    tex, paths, lay, frames, letters = _spec()
    w, h, fmt, cut = d["w"], d["h"], d["fmt"], d.get("cut")
    path = paths.get(name, "")
    if name in frames:
        k, i, n = frames[name]
        if k.startswith("title:"):
            return chars.draw(k[6:], w, h, i, n, seed=i)
        if k in chars.SETS:
            return chars.draw(chars.SETS[k], w, h, i, n, seed=i)
        if k.startswith("virus_"):
            return chars.germ(k[-1], w, h, i, n)
        if k == "smog":
            return chars.smog(w, h, i, n)
    if name in letters:
        return ui.logo_letter(letters[name], w, h)
    if name == "title_bmp_00":
        return ui.wordmark(w, h, "TONIC TUMBLE")
    if path.startswith("assets/title/") and fmt == "i4" and (w, h) == (128, 14):
        return ui.small_text(w, h, "CLEAN-ROOM BUILD")
    if path.startswith("assets/title/") and fmt == "i4":    # title masks/shadows: left empty (no retail shapes)
        return np.zeros((h, w, 4), np.uint8)
    if name.endswith("_tlut") and (w, h) == (16, 16):
        return ui.ramp_tlut(name, w, h)
    if w <= 16 and h >= 128 and cut is None:
        return ui.strip_ramp(name, w, h)
    if name in lay:
        return ui.frame(name, w, h, lay[name]["windows"])
    m = re.match(r"assets/story/bg(\d+)/", path)
    if m:
        return ui.scene(name, w, h, int(m.group(1)))
    if fmt in ("i4", "i8") or d.get("disp") in ("i4", "i8"):
        return ui.intensity(name, w, h, cut)
    if path.startswith("assets/title/") and cut is None:
        return ui.pattern(name, w, h)
    if w >= 200 and h >= 100 and cut is None:
        return ui.scene(name, w, h, ui.h32(name) % 11)
    if cut is not None and cut < 0.8:
        return ui.sticker(name, w, h, cut)
    return ui.panel(name, w, h, cut)
