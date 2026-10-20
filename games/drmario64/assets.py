"""CLEAN ROOM: spec + our generators -> a bin/us-shaped asset tree for build_decomp.

    python -m games.drmario64.assets <spec_local dir> <assets out dir> [--only regex] [--skip-audio]

Writes every texture as the PNG the decomp's asset C files include (indexed PNGs with
our palettes for CI, grey for intensity, RGBA otherwise; same names, formats and sizes
as listed in spec/textures.json + spec/png_paths.json), the vertex arrays from
geometry.py, the audio bank/songs/effects from music.py + audio.py, our IPL3 stub,
and text overrides from text.py. Nothing here reads the retail ROM. The RSP microcode is
written as CRUCODE1 placeholder stubs (cleanroom.ucode, spec/ucode.json); the ROM needs an
emulator core patched to read the tags (n64cleanrecomp ports/emu/ucode-tags).
"""
import json
import os
import re
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image

from games.drmario64 import generate
from games.drmario64.generate import make_palette, quantise, texture_image

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec")


def _pal_png(path, idx, pal, nent):
    """Indexed PNG with exactly nent palette entries (pigment64 writes them as the TLUT)."""
    im = Image.fromarray(idx.astype(np.uint8), "P")
    pal = np.asarray(pal, np.uint8)[:nent]
    if len(pal) < nent:
        pal = np.concatenate([pal, np.repeat(pal[-1:], nent - len(pal), 0)])
    im.putpalette(pal[:, :3].reshape(-1).tolist(), rawmode="RGB")
    im.info["transparency"] = bytes(pal[:, 3].tolist())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, transparency=bytes(pal[:, 3].tolist()), bits=4 if nent == 16 else 8)


def write_textures(out, only=None, log=print):
    texs = json.load(open(os.path.join(SPEC, "textures.json")))
    paths = json.load(open(os.path.join(SPEC, "png_paths.json")))
    from games.drmario64 import hooks  # noqa: F401  (registers drawn assets)
    from games.drmario64 import tiles
    orient = os.path.join(out, "tex_orient.json")         # written by geometry.write
    if not os.path.exists(orient):
        orient = os.path.join(HERE, "art", "tex_orient.json")   # snapshot for standalone runs
    generate.ORIENT.clear()
    generate.ORIENT.update(json.load(open(orient)))
    names = [n for n in texs if not only or only.search(n)]
    for n in tiles.STRIPS:
        if n not in names:
            continue
        d = texs[n]
        idx = tiles.strip(n, d["w"], d["h"])
        _pal_png(os.path.join(out, paths[n]), idx, tiles_palette(n), 16 if d["fmt"] == "ci4" else 256)
    images = {n: texture_image(n, texs[n]) for n in names if n not in tiles.STRIPS}
    groups = {}
    for n in images:
        if "pal" in texs[n]:
            groups.setdefault(texs[n]["pal"], []).append(n)
    from games.drmario64 import labels
    for users in groups.values():
        nent = 16 if all(texs[u]["fmt"] in ("ci4", "i4") for u in users) else 256
        reserved = [c for u in users for c in labels.RESERVED.get(u, [])]
        pal = make_palette([images[u] for u in users], nent, reserved)
        for u in users:
            ne = 16 if texs[u]["fmt"] in ("ci4", "i4") else 256
            q = quantise(images[u], pal[:ne])
            if texs[u]["fmt"] in ("i4", "i8"):     # intensity data the game reads as indices into the shared TLUT
                p = os.path.join(out, paths[u])
                os.makedirs(os.path.dirname(p), exist_ok=True)
                Image.fromarray((q * (17 if texs[u]["fmt"] == "i4" else 1)).astype(np.uint8), "L").save(p)
            else:
                _pal_png(os.path.join(out, paths[u]), q, pal, ne)
    for n, im in images.items():
        d = texs[n]
        if "pal" in d:
            continue
        p = os.path.join(out, paths[n])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        fmt = d["fmt"]
        if fmt in ("ci4", "ci8"):          # CI data the game draws as intensity: indices = levels
            lev = 16 if fmt == "ci4" else 256
            g = np.asarray(im[..., 0], np.float32) if im.ndim == 3 else np.asarray(im, np.float32)
            idx = np.clip(np.round(g / 255 * (lev - 1)), 0, lev - 1)
            ramp = np.stack([np.linspace(0, 255, lev)] * 3 + [np.full(lev, 255)], 1)
            _pal_png(p, idx, ramp, lev)
        elif fmt in ("i4", "i8"):
            Image.fromarray(np.asarray(im[..., 0] if im.ndim == 3 else im, np.uint8), "L").save(p)
        elif fmt in ("ia4", "ia8", "ia16"):
            Image.fromarray(np.stack([im[..., 0], im[..., 3]], -1).astype(np.uint8), "LA").save(p)
        else:
            Image.fromarray(np.asarray(im, np.uint8), "RGBA").save(p)
    log(f"  textures {len(names)} ({len(groups)} shared palettes)")
    return len(names)


def tiles_palette(n):
    from games.drmario64 import tiles
    return np.clip(np.round(np.asarray(tiles.strip_palette(n), np.float32)), 0, 255).astype(np.uint8)


def write_ipl3(out):
    """Our IPL3 stub (ipl3/ipl3.s), assembled and padded to the 0xFC0-byte slot."""
    pre = os.environ.get("MIPS_PREFIX", r"C:/Users/andre/.local/mips64/bin/mips64-elf-")
    tmp = os.path.join(out, "_ipl3")
    os.makedirs(tmp, exist_ok=True)
    src = os.path.join(HERE, "ipl3", "ipl3.s")
    subprocess.run([pre + "gcc", "-c", "-march=vr4300", "-mabi=32", "-EB", "-mno-abicalls", "-fno-PIC", "-G0",
                    src, "-o", os.path.join(tmp, "ipl3.o")], check=True)
    subprocess.run([pre + "ld", "-EB", "-Ttext=0xA4000040", "-e", "ipl3_start", "-o", os.path.join(tmp, "ipl3.elf"),
                    os.path.join(tmp, "ipl3.o")], check=True)
    subprocess.run([pre + "objcopy", "-O", "binary", "-j", ".text", os.path.join(tmp, "ipl3.elf"),
                    os.path.join(tmp, "ipl3.bin")], check=True)
    code = open(os.path.join(tmp, "ipl3.bin"), "rb").read()
    assert len(code) <= 0xFC0
    open(os.path.join(out, "ipl3.databin.bin"), "wb").write(code.ljust(0xFC0, b"\0"))
    shutil.rmtree(tmp)


def main(argv):
    local, out = argv[1], argv[2]
    only = re.compile(argv[argv.index("--only") + 1]) if "--only" in argv else None
    os.makedirs(out, exist_ok=True)
    from games.drmario64 import geometry
    print(f"  vertex arrays {geometry.write(local, out)}")    # first: textures read tex_orient.json
    write_textures(out, only)
    write_ipl3(out)
    from cleanroom import ucode     # RSP microcode: CRUCODE1 placeholder stubs, never the retail blobs
    print(f"  ucode stubs {ucode.write_stubs(json.load(open(os.path.join(SPEC, 'ucode.json'))), out)}")
    if "--skip-audio" not in argv:
        from games.drmario64 import music
        print("  " + music.write_all(local, out))
    from games.drmario64 import text
    print("  " + text.write_overrides(out))


if __name__ == "__main__":
    main(sys.argv)
