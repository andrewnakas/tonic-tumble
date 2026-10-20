"""Give our ROM the emulator's Dr. Mario 64 settings (EEPROM 4 KB save type etc.).

mupen64plus looks ROMs up by MD5 in a database compiled into the core; an unknown
ROM gets no EEPROM (MK64 stalled at boot without it). The database has a hack entry whose
RefMD5 is the US game's, so it inherits every US setting: we point that entry at
our ROM's MD5 (same length, so a plain byte replacement in the wasm).

    python ports/ejs/patch_core.py <rom.z64> <cores dir in, e.g. data/cores> <cores dir out>
"""
import hashlib
import io
import os
import sys

import py7zr

SLOT = b"[36B3D908FB50E5521DEFBEB2C39F47B0]"      # "Dr. Mario 64 (U) [T+Jap1.0_Zoinkity]", RefMD5 = US
CORES = ["mupen64plus_next-wasm.data", "mupen64plus_next-legacy-wasm.data"]
GLN_OLD = b"[DR.MARIO%2064]\n"                       # GLideN64.custom.ini section (fbInfoDisabled=0, copyFromRDRAM=1)
GLN_NEW = b"[TONIC TUMBLE]\n\n"                      # same length; spaces match the trimmed header name


def patch(src, dst, md5):
    import tempfile
    tmp = tempfile.mkdtemp(prefix="core_")
    with py7zr.SevenZipFile(src) as z:
        names = [n for n in z.getnames()]
        z.extractall(tmp)
    files = {n: open(os.path.join(tmp, n), "rb").read() for n in names if os.path.isfile(os.path.join(tmp, n))}
    n = 0
    for name, data in files.items():
        if name.endswith(".wasm"):
            assert data.count(SLOT) == 1, f"{name}: slot not found"
            data = data.replace(SLOT, b"[" + md5.upper().encode() + b"]")
            # GLideN64's built-in per-game ini is keyed by the ROM header name; our ROM is named TONIC TUMBLE,
            # so the section that held this game's frame-buffer settings gets our name (same length).
            if data.count(GLN_OLD) == 1:
                data = data.replace(GLN_OLD, GLN_NEW)
            else:
                assert data.count(GLN_NEW) == 1, f"{name}: GLideN64 ini section not found"
            files[name] = data
            n += 1
    with py7zr.SevenZipFile(dst, "w") as z:
        for name, data in files.items():
            z.writef(io.BytesIO(data), name)
    return n


def main(argv):
    rom, cin, cout = argv[1:4]
    md5 = hashlib.md5(open(rom, "rb").read()).hexdigest()
    os.makedirs(cout, exist_ok=True)
    for c in CORES:
        if os.path.exists(os.path.join(cin, c)):
            patch(os.path.join(cin, c), os.path.join(cout, c), md5)
    print(f"patch_core: Dr. Mario 64 settings entry -> md5 {md5}")


if __name__ == "__main__":
    main(sys.argv)
