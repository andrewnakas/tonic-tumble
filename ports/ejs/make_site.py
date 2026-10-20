"""Assemble the web site: EmulatorJS runtime + patched mupen64plus_next core + our page + clean ROM.

    python ports/ejs/make_site.py <clean rom .z64> <emulatorjs dir> <site dir> --core <patched core .data>
        [--core-src <dir with the ucode-tags patch files>]

The clean ROM carries CRUCODE1 microcode placeholders (cleanroom.ucode), so the site ships the
EmulatorJS core built with n64cleanrecomp ports/emu/ucode-tags (mupen64plus-libretro-nx.patch). The stock
legacy (WebGL1) core cannot run the ROM and is left out; libunrar is left out (the ROM is not an archive).
Refuses a ROM whose SHA1 is the retail one (never publish retail data).
"""
import argparse
import hashlib
import os
import shutil
import sys

RETAIL_SHA1 = "a130d3622ce40e0158db2da4247101f6e92206fc"
HERE = os.path.dirname(os.path.abspath(__file__))
ROM_NAME = "tonictumble.z64"
DROP = ["data/cores/mupen64plus_next-legacy-wasm.data", "data/compression/libunrar.js",
        "data/compression/libunrar.wasm"]

NOTICE = """# Tonic Tumble: credits and third-party notices

Tonic Tumble is an original game built on the **AngheloAlf/drmario64 decomp**
(https://github.com/AngheloAlf/drmario64, MIT License, Copyright (c) 2023 AngheloAlf). The program in
`tonictumble.z64` is compiled from that decompilation (including its decompiled libultra). Every picture,
tune, sound, 3D shape and line of text was generated for this project; no data from the original game ships.
Source of the clean-room pipeline: https://github.com/andrewnakas/drmario64-cleanroom (MIT License).

The ROM boots with an original IPL3 stub (CC0) and carries small tagged RSP microcode placeholders
(CRUCODE1, CC0) instead of microcode, so it runs only in the patched emulator core bundled here (not on
real hardware or low-level emulators).

## Third-party software in this site

| Component | Files | Licence | Source |
|---|---|---|---|
| EmulatorJS 4.2.3 | `data/` (loader, emulator, css, localization, 7z/zip extractors) | GPL-3.0 (`data/LICENSE.EmulatorJS`) | https://github.com/EmulatorJS/EmulatorJS |
| mupen64plus-libretro-nx (mupen64plus-next core: mupen64plus-core, rsp-hle, GLideN64), built for EmulatorJS with the CRUCODE1 tag patch | `data/cores/mupen64plus_next-wasm.data` | GPL-2.0 | upstream https://github.com/EmulatorJS/mupen64plus-libretro-nx @4a3925d; our changes: `data/cores/source/mupen64plus-libretro-nx.patch` + `crucode.h` |
| RetroArch (libretro frontend linked into the core by EmulatorJS) | same file | GPL-3.0 | https://github.com/EmulatorJS/RetroArch |
| nipplejs (touch joystick, in EmulatorJS) | `data/src/nipplejs.js` | MIT | https://github.com/yoannmoinet/nipplejs |
| socket.io client (in EmulatorJS) | `data/src/socket.io.min.js` | MIT | https://github.com/socketio/socket.io |

Fonts used to draw the in-game lettering (rendered into the ROM's textures): Rubik, Lilita One,
M PLUS Rounded 1c, Press Start 2P (SIL Open Font License 1.1) and Luckiest Guy (Apache-2.0); licence texts are in
the source repository under `games/drmario64/fonts/`.

To get the exact source of the core: check out the upstream commit above, apply the patch from
`data/cores/source/`, and build with `build_ejs_core.sh` (also in `data/cores/source/`).
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("ejs")
    ap.add_argument("site")
    ap.add_argument("--core", required=True, help="patched mupen64plus_next-wasm.data")
    ap.add_argument("--core-src", default=None, help="dir with mupen64plus-libretro-nx.patch, crucode.h, build_ejs_core.sh")
    a = ap.parse_args()
    data = open(a.rom, "rb").read()
    if hashlib.sha1(data).hexdigest() == RETAIL_SHA1:
        sys.exit("refusing: that is the retail ROM")
    site = a.site
    if os.path.exists(site):
        for n in os.listdir(site):
            if n == ".git":
                continue
            p = os.path.join(site, n)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    os.makedirs(site, exist_ok=True)
    shutil.copytree(os.path.join(a.ejs, "data"), os.path.join(site, "data"), dirs_exist_ok=True)
    for rel in DROP:
        p = os.path.join(site, rel)
        if os.path.exists(p):
            os.remove(p)
    shutil.copyfile(a.core, os.path.join(site, "data", "cores", "mupen64plus_next-wasm.data"))
    if a.core_src:
        dst = os.path.join(site, "data", "cores", "source")
        os.makedirs(dst, exist_ok=True)
        for n in ("mupen64plus-libretro-nx.patch", "crucode.h", "build_ejs_core.sh", "pack_ejs_core.py", "README.md"):
            if os.path.exists(os.path.join(a.core_src, n)):
                shutil.copyfile(os.path.join(a.core_src, n), os.path.join(dst, n))
    shutil.copyfile(os.path.join(a.ejs, "LICENSE"), os.path.join(site, "data", "LICENSE.EmulatorJS"))
    shutil.copyfile(os.path.join(HERE, "index.html"), os.path.join(site, "index.html"))
    open(os.path.join(site, ROM_NAME), "wb").write(data)
    open(os.path.join(site, "THIRD_PARTY.md"), "w", encoding="utf-8", newline="\n").write(NOTICE)
    open(os.path.join(site, ".nojekyll"), "w").close()
    total = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(site) for f in fs)
    print(f"site: {site} ({total // 1024} KB), rom sha1 {hashlib.sha1(data).hexdigest()[:12]}")


if __name__ == "__main__":
    main()
