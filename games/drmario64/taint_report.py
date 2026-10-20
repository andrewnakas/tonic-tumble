"""DEV/DIRTY check for the compiled build: does any retail asset byte run survive in the clean ROM?

    python -m games.drmario64.taint_report <dirty tree> <clean uncompressed ROM> [--assets <clean assets dir>]

Retail asset windows: every texture, palette and sample range of the retail uncompressed image
(spec/textures.json, palettes.json, samples.json offsets), every retail song/effect databin and
every retail vertex array (bin/us/**/*.vtx.inc.c as 16-byte Vtx records). Every 32-byte
non-trivial window (stride 8) is looked up at every offset of the clean uncompressed ROM image;
a hit fails. With --assets, each clean PNG's RGBA is also compared with the retail PNG at the
same path (shared run >= 32 bytes fails).
Not scanned (recorded publishing blocker): the four RSP microcode blobs, which the build carries
unchanged because HLE emulators recognise only the original microcode.
"""
import glob
import json
import os
import re
import struct
import sys

from games.drmario64.audio import SPEC

WIN = 32


def grey_ramp(b):
    """A linear grey ramp in RGBA5551 (optionally followed by zero fill), e.g. the 16-step
    TLUT any build writes for intensity-style CI data: identical everywhere, not a copy."""
    v = struct.unpack(">16H", b)
    while v and v[-1] == 0:
        v = v[:-1]
    if len(v) < 4:
        return False
    lev = []
    for x in v:
        r, g, bl = x >> 11, (x >> 6) & 31, (x >> 1) & 31
        if not (r == g == bl):
            return False
        lev.append(r)
    steps = {b2 - a for a, b2 in zip(lev, lev[1:])}
    return min(steps) > 0 and max(steps) - min(steps) <= 1


def trivial(b):
    """Mostly one byte value (zero fill, padding, flat colour) or a linear grey ramp:
    not evidence of copying."""
    return len(set(b)) <= 6 or max(b.count(bytes([v])) for v in set(b)) >= 20 or grey_ramp(b)


def vtx_bytes(path):
    out = b""
    for m in re.finditer(r"\{\{\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\},\s*(-?\d+),\s*\{\s*(-?\d+),\s*(-?\d+)\s*\},\s*"
                         r"\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}\}\}", open(path).read()):
        x, y, z, f, s, t, r, g, b, a = (int(v) for v in m.groups())
        out += struct.pack(">hhhHhhBBBB", x, y, z, f & 0xFFFF, s, t, r & 255, g & 255, b & 255, a & 255)
    return out


def retail_blobs(dirty):
    ret = open(os.path.join(dirty, "config/us/baserom_uncompressed.us.z64"), "rb").read()
    texs = json.load(open(os.path.join(SPEC, "textures.json")))
    pals = json.load(open(os.path.join(SPEC, "palettes.json")))
    lay = json.load(open(os.path.join(SPEC, "layout.json")))
    smp = json.load(open(os.path.join(SPEC, "samples.json")))
    for n, d in texs.items():
        yield "tex:" + n, ret[d["off"]:d["off"] + d["bytes"]]
    for n, p in pals.items():
        yield "pal:" + n, ret[p["off"]:p["off"] + p["size"]]
    for d in smp:
        o = lay["wave_tables"] + d["base"]
        yield f"wave{d['i']}", ret[o:o + d["len"]]
    b = os.path.join(dirty, "bin", "us")
    for p in sorted(glob.glob(os.path.join(b, "segment_1*.databin.bin")) + [os.path.join(b, "fxbank.databin.bin")]):
        yield "seq:" + os.path.basename(p), open(p, "rb").read()
    for p in sorted(glob.glob(os.path.join(b, "assets", "**", "*.vtx.inc.c"), recursive=True)):
        yield "vtx:" + os.path.relpath(p, b), vtx_bytes(p)


def png_check(dirty, assets):
    import numpy as np
    from PIL import Image

    def rgba(path):
        return np.asarray(Image.open(path).convert("RGBA")).tobytes()
    fails, n = [], 0
    root = os.path.join(dirty, "bin", "us")
    for p in glob.glob(os.path.join(assets, "**", "*.png"), recursive=True):
        rel = os.path.relpath(p, assets)
        r = os.path.join(root, rel)
        if not os.path.exists(r):
            continue
        a, c = rgba(r), rgba(p)
        n += 1
        i, m = 0, min(len(a), len(c))
        while i < m:
            if a[i] != c[i]:
                i += 1
                continue
            j = i
            while j < m and a[j] == c[j]:
                j += 1
            if j - i >= WIN and not trivial(a[i:j]):
                fails.append((rel, i, j - i))
                break
            i = j
    return n, fails


def main(argv):
    dirty, image = argv[1], argv[2]
    cl = open(image, "rb").read()
    windows, kinds = {}, {}
    for name, blob in retail_blobs(dirty):
        kind = "wave" if name.startswith("wave") else name.split(":")[0]
        kinds[kind] = kinds.get(kind, 0) + 1
        for k in range(0, len(blob) - WIN + 1, 8):
            w = blob[k:k + WIN]
            if not trivial(w):
                windows.setdefault(w, name)
    hits = []
    for k in range(0, len(cl) - WIN + 1):
        w = cl[k:k + WIN]
        if w in windows:
            hits.append((k, windows[w]))
    print(f"taint: {len(windows)} retail asset windows ({', '.join(f'{v} {k}' for k, v in kinds.items())}) "
          f"scanned over the clean image ({len(cl) // 1024} KB): {len(hits)} failing")
    for k, name in hits[:10]:
        print(f"  FAIL window at {k:#x} matches {name}")
    pf = []
    if "--assets" in argv:
        n, pf = png_check(dirty, argv[argv.index("--assets") + 1])
        print(f"taint: {n} clean PNGs vs retail PNGs (RGBA, same path): {len(pf)} failing (run >= {WIN} B)")
        for f in pf[:10]:
            print("  FAIL", f)
    print("  not scanned (publishing blocker): RSP microcode rspboot/aspMain/F3DEX2/S2DEX, carried unchanged")
    return 1 if hits or pf else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
