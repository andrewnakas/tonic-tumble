"""DIRTY ROOM (2026-10 originality rebuild): extra structural facts for the compiled build.

    python -m games.drmario64.extract_more <dirty decomp tree> <spec dir> <spec_local dir> [part ...]

parts (default all):
  paths     spec/png_paths.json   texture name -> bin/us PNG path (file layout of the decomp)
  rsp       spec_local/rsp/       the four RSP microcode blobs (never committed; publishing blocker)
  music     spec/music.json       per song: tempo, length, loop, channel roles/registers, instrument
                                  tables (music.extract); retail notes as MIDI under <dirty>/../gate/
  geometry  spec/geometry.json    per vertex array: count, bbox, topology from the decomp DLs
  text      <dirty>/../gate/text  retail strings for the originality gate (never committed)
Only facts leave this script; the retail data stays on the dirty side.
"""
import glob
import json
import os
import shutil
import sys


def paths(dirty, spec, local):
    root = os.path.join(dirty, "bin", "us")
    tex = json.load(open(os.path.join(spec, "textures.json")))
    by = {}
    for p in glob.glob(os.path.join(root, "**", "*.png"), recursive=True):
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        by[os.path.basename(rel).rsplit(".", 2)[0]] = rel
    out = {n: by[os.path.basename(n)] for n in tex}
    json.dump(out, open(os.path.join(spec, "png_paths.json"), "w"), indent=0, sort_keys=True)
    return f"png paths {len(out)}"


def rsp(dirty, spec, local):
    d = os.path.join(local, "rsp")
    os.makedirs(d, exist_ok=True)
    n = 0
    for p in glob.glob(os.path.join(dirty, "bin", "us", "rsp", "*.bin")):
        shutil.copy(p, d)
        n += 1
    return f"rsp blobs {n} -> {d}"


def code(dirty, spec, local):
    """Retail executable code (boot text 0x1000-0xED90, main_segment text 0x11A70-0x6FF20 of
    the uncompressed image, per the decomp's splat yaml) for the originality code check."""
    r = open(os.path.join(dirty, "config/us/baserom_uncompressed.us.z64"), "rb").read()
    d = os.path.join(os.path.dirname(os.path.abspath(dirty)), "gate", "code")
    os.makedirs(d, exist_ok=True)
    blob = r[0x1000:0xED90] + r[0x11A70:0x6FF20]
    open(os.path.join(d, "retail_text.bin"), "wb").write(blob)
    return f"retail code {len(blob) // 1024} KB -> {d}"


def main(argv):
    dirty, spec, local = argv[1:4]
    parts = argv[4:] or ["paths", "rsp", "code", "music", "geometry", "text"]
    for part in parts:
        if part in ("paths", "rsp", "code"):
            print(" ", globals()[part](dirty, spec, local))
        else:
            mod = __import__(f"games.drmario64.{part}", fromlist=["extract"])
            print(" ", mod.extract(dirty, spec, local))


if __name__ == "__main__":
    main(sys.argv)
