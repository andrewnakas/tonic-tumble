"""Contact sheet of textures as the game displays them, decoded from an uncompressed ROM image.

    python -m games.drmario64.look <uncompressed rom(.gz)> <out.png> [name regex] [--scale 2] [--width 1600]

Works on the dirty baserom_uncompressed (dev look, never published) or on our clean image.
"""
import gzip
import json
import os
import re
import sys

import numpy as np

from cleanroom.gfx import png, texfmt as tf
from cleanroom.find_text import contact_sheet
from games.drmario64.extract_spec import FMT, pal_rgba

SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec")


def load_rom(path):
    return (gzip.open(path) if path.endswith(".gz") else open(path, "rb")).read()


def decode(rom, d, pals):
    fmt, siz = FMT[d["fmt"]]
    raw = rom[d["off"]:d["off"] + d["bytes"]]
    if "pal" in d:
        p = pals[d["pal"]]
        return tf.decode(raw, d["w"], d["h"], tf.CI, siz, pal_rgba(rom[p["off"]:p["off"] + p["size"]]))
    if d["disp"].startswith("i"):
        im = tf.decode(raw, d["w"], d["h"], tf.I, siz).copy()
        im[..., 3] = 255
        return im
    return tf.decode(raw, d["w"], d["h"], fmt, siz)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    opts = dict(zip([a[2:] for a in argv[1:] if a.startswith("--")], [None] * 9))
    scale = int(argv[argv.index("--scale") + 1]) if "--scale" in argv else 2
    width = int(argv[argv.index("--width") + 1]) if "--width" in argv else 1600
    for k in ("--scale", "--width"):
        if k in argv:
            args.remove(argv[argv.index(k) + 1])
    rom, out = load_rom(args[0]), args[1]
    rx = re.compile(args[2]) if len(args) > 2 else None
    texs = json.load(open(os.path.join(SPEC, "textures.json")))
    pals = json.load(open(os.path.join(SPEC, "palettes.json")))
    items = [(n, decode(rom, d, pals)) for n, d in texs.items() if not rx or rx.search(n)]
    sheet, place = contact_sheet(items, scale=scale, width=width, pad=4)
    png.write(out, sheet) if hasattr(png, "write") else png.save(out, sheet)
    print(f"{len(items)} textures -> {out} {sheet.shape[1]}x{sheet.shape[0]}")


if __name__ == "__main__":
    main(sys.argv)
