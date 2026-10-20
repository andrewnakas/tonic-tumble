"""DIRTY ROOM: retail ROM + decomp tree -> clean-room spec for Dr. Mario 64.

    python -m games.drmario64.extract_spec <dirty decomp tree> <spec dir> <spec_local dir>

spec/layout.json     ROM segments (compressed ranges, uncompressed offsets, levels)
spec/textures.json   per texture: rom offset, format, size, how the game displays it
                     (own palette / shared anime palette / intensity), 4x4 colour grid
                     (16x16 for >= 128 px), 2-bit alpha outline
spec/palettes.json   palette ranges (offset, bytes); colours are regenerated
spec_local/skeleton.bin.gz  the uncompressed ROM with every texture, palette and
                     sample byte zeroed: code + structural data only (never published)
"""
import gzip
import json
import os
import re
import sys

import numpy as np
import yaml

from cleanroom.gfx import texfmt as tf
from cleanroom.decomp.spec import grid as _grid, alpha2


def grid(rgba, n):
    """Colour grid of the visible pixels only (transparent texels often hold a key colour)."""
    a = (rgba[..., 3:4].astype(np.float32) >= 128)
    if a.all() or not a.any():
        return _grid(rgba, n)
    pre = rgba.astype(np.float32).copy()
    pre[..., :3] *= a
    g_rgb = np.asarray(_grid(pre.astype(np.float32), n), np.float32)
    cov = np.asarray(_grid(np.repeat(a.astype(np.float32) * 255, 4, -1), n), np.float32)[:, :1] / 255
    full = np.asarray(_grid(rgba, n), np.float32)
    out = full.copy()
    ok = cov[:, 0] > 0.02
    out[ok, :3] = g_rgb[ok, :3] / cov[ok]
    # empty cells: borrow the mean visible colour so interpolation does not bleed the key colour in
    vis = rgba[a[..., 0]][:, :3].mean(0)
    out[~ok, :3] = vis
    return [[int(round(v)) for v in c] for c in out]

FMT = {"ci4": (tf.CI, tf.B4), "ci8": (tf.CI, tf.B8), "i4": (tf.I, tf.B4), "i8": (tf.I, tf.B8),
       "ia4": (tf.IA, tf.B4), "ia8": (tf.IA, tf.B8), "ia16": (tf.IA, tf.B16),
       "rgba16": (tf.RGBA, tf.B16), "rgba32": (tf.RGBA, tf.B32)}


def read_csv(path):
    rows = [l.strip().split(",") for l in open(path) if l.strip()][1:]
    return [dict(name=r[0], cstart=int(r[1], 0), cend=int(r[2], 0), level=int(r[4]), tool=r[5]) for r in rows]


def layout(rom_len, csv):
    """Same walk as tools/compressor/rom_decompressor.py: compressed + raw ranges, sequential."""
    segs = sorted(csv, key=lambda s: s["cstart"])
    out, pos = [], 0
    for s in segs:
        if s["cstart"] != pos:
            out.append(dict(name="", cstart=pos, cend=s["cstart"], compressed=False))
        out.append(dict(s, compressed=True))
        pos = s["cend"]
    if pos != rom_len:
        out.append(dict(name="", cstart=pos, cend=rom_len, compressed=False))
    return out


def walk(node, items):
    if isinstance(node, list):
        if node and isinstance(node[0], int):
            items.append(dict(start=node[0], type=node[1] if len(node) > 1 else None,
                              name=node[2] if len(node) > 2 else None,
                              w=node[3] if len(node) > 4 else None, h=node[4] if len(node) > 4 else None))
        else:
            for n in node:
                walk(n, items)
    elif isinstance(node, dict):
        if "start" in node and isinstance(node["start"], int):
            items.append(dict(start=node["start"], type=node.get("type"), name=node.get("name"),
                              w=node.get("width"), h=node.get("height")))
        for k in ("subsegments", "segments"):
            if k in node:
                walk(node[k], items)


def titex_pairs(src_root):
    """Asset C: <tex symbol> -> (tlut symbol or None, TITEX format, file)."""
    out = {}
    pat = re.compile(r"TexturePtr (\w+)_texs\[2\] = \{\s*(\w+),\s*(\w+),\s*\};")
    for d, _, fs in os.walk(os.path.join(src_root, "src")):
        for f in fs:
            if not f.endswith(".c"):
                continue
            txt = open(os.path.join(d, f), encoding="utf-8", errors="replace").read()
            for m in pat.finditer(txt):
                base, tlut, tex = m.groups()
                fm = re.search(re.escape(base) + r"_info\[\] = \{[^}]*TITEX_FORMAT_(\d+)", txt)
                out[tex] = dict(tlut=None if tlut == "NULL" else tlut, base=base,
                                titex=int(fm.group(1)) if fm else None, file=os.path.relpath(os.path.join(d, f), src_root))
    return out


def pal_rgba(raw):
    v = np.frombuffer(raw[: len(raw) // 2 * 2], ">u2").astype(np.int64)
    p = np.zeros((len(v), 4), np.uint8)
    p[:, 0] = ((v >> 11) & 31) * 255 // 31
    p[:, 1] = ((v >> 6) & 31) * 255 // 31
    p[:, 2] = ((v >> 1) & 31) * 255 // 31
    p[:, 3] = (v & 1) * 255
    return p


def main(argv):
    tree, spec, local = argv[1], argv[2], argv[3]
    os.makedirs(spec, exist_ok=True)
    os.makedirs(local, exist_ok=True)
    rom = bytearray(open(os.path.join(tree, "config/us/baserom_uncompressed.us.z64"), "rb").read())
    crom = open(os.path.join(tree, "config/us/baserom.us.z64"), "rb").read()
    csv = read_csv(os.path.join(tree, "tools/compressor/compress_segments.us.csv"))
    segs = layout(len(crom), csv)
    upos = 0
    for s in segs:
        s["ustart"] = upos
        if s["compressed"]:
            import zlib
            d = zlib.decompressobj(-zlib.MAX_WBITS).decompress(crom[s["cstart"]:s["cend"]])
            s["ulen"] = len(d)
        else:
            s["ulen"] = s["cend"] - s["cstart"]
        upos += (s["ulen"] + 15) & ~15
    assert upos == len(rom), (hex(upos), hex(len(rom)))

    cfg = yaml.safe_load(open(os.path.join(tree, "config/us/drmario64.us.yaml")))
    items = []
    walk(cfg["segments"], items)
    items = sorted({(i["start"], i["type"] or "", i["name"] or ""): i for i in items}.values(),
                   key=lambda i: (i["start"], i["type"] != "palette"))
    starts = sorted({i["start"] for i in items} | {len(rom)})
    nxt = {s: starts[k + 1] for k, s in enumerate(starts[:-1])}

    pairs = titex_pairs(tree)
    pals = {}
    for i in items:
        if i["type"] == "palette":
            size = min(nxt[i["start"]] - i["start"], 512)
            pals[i["name"]] = dict(off=i["start"], size=size)
    # anime files: every frame uses frame 0's palette (char_anime.c: pal = &texArray[0])
    anime_pal = {}
    for tex, p in pairs.items():
        if p["file"].replace("\\", "/").startswith("src/assets/anime/") and p["tlut"]:
            key = p["base"].rsplit("_titexdata_", 1)[0]
            if p["base"].endswith("_titexdata_00"):
                anime_pal[key] = p["tlut"]
    tlut_to_pal = {}
    for name, p in pals.items():
        tlut_to_pal[os.path.basename(name)] = name

    texs, n_disp = {}, {}
    for i in items:
        t = i["type"]
        if t not in FMT or not i["w"]:
            continue
        fmt, siz = FMT[t]
        w, h = int(i["w"]), int(i["h"])
        nbytes = tf.texel_bytes(w, h, siz)
        raw = bytes(rom[i["start"]:i["start"] + nbytes])
        sym = os.path.basename(i["name"])
        pal = None
        disp = t
        if fmt == tf.CI and i["name"] in pals:
            pal = i["name"]
        elif sym in pairs:
            p = pairs[sym]
            key = p["base"].rsplit("_titexdata_", 1)[0]
            if p["tlut"] and p["tlut"].replace("_tlut", "_tex") in tlut_to_pal:
                pal = tlut_to_pal[p["tlut"].replace("_tlut", "_tex")]
            elif key in anime_pal and anime_pal[key].replace("_tlut", "_tex") in tlut_to_pal:
                pal = tlut_to_pal[anime_pal[key].replace("_tlut", "_tex")]
        if pal and siz in (tf.B4, tf.B8):
            pr = rom[pals[pal]["off"]:pals[pal]["off"] + pals[pal]["size"]]
            rgba = tf.decode(raw, w, h, tf.CI, siz, pal_rgba(pr))
            disp = "ci4" if siz == tf.B4 else "ci8"
        else:
            pal = None
            rgba = tf.decode(raw, w, h, fmt, siz)
            if fmt == tf.CI:  # no palette known: show indices as intensity
                rgba = tf.decode(raw, w, h, tf.I, siz)
                disp = "i4" if siz == tf.B4 else "i8"
            if fmt == tf.I:
                rgba = rgba.copy()
                rgba[..., 3] = rgba[..., 0]
        n = 16 if max(w, h) >= 128 else 4
        d = dict(off=i["start"], fmt=t, disp=disp, w=w, h=h, bytes=nbytes, grid=grid(rgba, n))
        if pal:
            d["pal"] = pal
        if (rgba[..., 3] < 250).any():
            d["alpha2"] = alpha2(rgba[..., 3])
        texs[i["name"]] = d
        n_disp[disp] = n_disp.get(disp, 0) + 1

    # skeleton: zero every texture and palette byte, and the sample table
    zeroed = 0
    for d in texs.values():
        rom[d["off"]:d["off"] + d["bytes"]] = bytes(d["bytes"])
        zeroed += d["bytes"]
    for p in pals.values():
        rom[p["off"]:p["off"] + p["size"]] = bytes(p["size"])
        zeroed += p["size"]
    from games.drmario64 import audio
    ptr = next(i["start"] for i in items if i["name"] == "n64_ptr_tables_v2")
    wave = next(i["start"] for i in items if i["name"] == "n64_wave_tables")
    nsmp, zs = audio.extract(rom, ptr, wave, spec)
    print(f"samples {nsmp}, zeroed {zs // 1024} KB of wave table")
    json.dump(dict(segments=segs, rom_len=len(rom), crom_len=len(crom), ptr_tables=ptr, wave_tables=wave),
              open(os.path.join(spec, "layout.json"), "w"), indent=0)
    json.dump(texs, open(os.path.join(spec, "textures.json"), "w"))
    json.dump(pals, open(os.path.join(spec, "palettes.json"), "w"), indent=0)
    with gzip.open(os.path.join(local, "skeleton.bin.gz"), "wb") as f:
        f.write(rom)
    print(f"segments {len(segs)} ({sum(s['compressed'] for s in segs)} compressed), uncompressed {len(rom):#x}")
    print(f"textures {len(texs)} by display {n_disp}; palettes {len(pals)}; zeroed {zeroed // 1024} KB")
    unl = [n for n, d in texs.items() if d['fmt'].startswith('ci') and 'pal' not in d]
    print(f"ci without palette: {len(unl)} e.g. {unl[:4]}")


if __name__ == "__main__":
    main(sys.argv)
