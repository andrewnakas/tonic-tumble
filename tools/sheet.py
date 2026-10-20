"""Montage PNGs into one sheet: python tools/sheet.py <out.png> <png|dir>... [--cols 4]"""
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from cleanroom.gfx import png  # noqa: E402


def main(argv):
    cols = int(argv[argv.index("--cols") + 1]) if "--cols" in argv else 4
    args = [a for i, a in enumerate(argv[2:], 2) if not a.startswith("--") and argv[i - 1] != "--cols"]
    files = []
    for a in args:
        files += sorted(glob.glob(os.path.join(a, "*.png")), key=lambda f: (len(f), f)) if os.path.isdir(a) else [a]
    ims = [png.read(f) for f in files]
    h = max(i.shape[0] for i in ims)
    w = max(i.shape[1] for i in ims)
    rows = (len(ims) + cols - 1) // cols
    out = np.zeros((rows * (h + 4), cols * (w + 4), 4), np.uint8)
    out[..., 3] = 255
    for k, im in enumerate(ims):
        y, x = (k // cols) * (h + 4), (k % cols) * (w + 4)
        if im.shape[2] == 3:
            im = np.concatenate([im, np.full(im.shape[:2] + (1,), 255, np.uint8)], -1)
        out[y:y + im.shape[0], x:x + im.shape[1]] = im
    png.write(argv[1], out)
    print(f"{len(ims)} images -> {argv[1]}")


if __name__ == "__main__":
    main(sys.argv)
