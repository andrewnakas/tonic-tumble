"""Pack a rebuilt mupen64plus_next core into an EmulatorJS core archive (.data = 7z).

    python pack_ejs_core.py <stock mupen64plus_next-wasm.data> <core .js> <core .wasm> <out .data>

core.json / license.txt / build.json come from the stock archive; build.json gets a "cleanroom" note
so the site's THIRD_PARTY notice can point at the patch (ports/emu/ucode-tags).
"""
import io
import json
import os
import shutil
import sys
import tempfile

import py7zr


def main(stock, js, wasm, out):
    tmp = tempfile.mkdtemp(prefix="ejscore_")
    with py7zr.SevenZipFile(stock) as z:
        names = z.getnames()
        z.extractall(tmp)
    files = {n: open(os.path.join(tmp, n), "rb").read() for n in names if os.path.isfile(os.path.join(tmp, n))}
    shutil.rmtree(tmp)
    keep = {k: v for k, v in files.items() if not k.endswith((".js", ".wasm"))}
    build = json.loads(keep.get("build.json", b"{}"))
    build["cleanroom"] = ("mupen64plus-libretro-nx + CRUCODE1 microcode-tag patch "
                          "(n64cleanrecomp ports/emu/ucode-tags/mupen64plus-libretro-nx.patch)")
    keep["build.json"] = json.dumps(build, indent=4).encode()
    keep["mupen64plus_next_libretro.js"] = open(js, "rb").read()
    keep["mupen64plus_next_libretro.wasm"] = open(wasm, "rb").read()
    with py7zr.SevenZipFile(out, "w") as z:
        for name, data in keep.items():
            z.writef(io.BytesIO(data), name)
    print("packed %s: %s" % (out, ", ".join("%s %d KB" % (k, len(v) // 1024) for k, v in keep.items())))


if __name__ == "__main__":
    main(*sys.argv[1:5])
