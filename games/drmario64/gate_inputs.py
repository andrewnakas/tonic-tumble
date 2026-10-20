"""CLEAN ROOM: code inputs for the originality gate, from our own build.

    python -m games.drmario64.gate_inputs <build out dir> <clean root>

Writes <clean root>/gate_code/clean_text.bin: the executable code of the ROM (.text of every
object in the boot and main segments, in link order) with the four RSP microcode blobs blanked
(they are retail microcode carried unchanged: a recorded publishing blocker, reported
separately), and <clean root>/gate_code/compiled/*.bin: the link-order .text runs of every object
our build compiled or assembled from the decomp's sources, which the gate accepts as "compiled
from decomp" even where a window equals retail bytes (tiny accessors encode the same under GCC
and KMC; libultra's hand-written .s assemble the same).
"""
import glob
import os
import subprocess
import sys

MIPS = os.environ.get("MIPS_PREFIX", r"C:/Users/andre/.local/mips64/bin/mips64-elf-")
UCODE = ("rspboot", "aspMain", "gspF3DEX2_fifo", "gspS2DEX_fifo")


def symbols(elf):
    out = subprocess.run([MIPS + "nm.exe", elf], capture_output=True, text=True).stdout
    return {p[2]: int(p[0], 16) for p in (l.split() for l in out.splitlines()) if len(p) == 3}


def main(argv):
    out, root = argv[1], argv[2]
    bd = os.path.join(out, "build", "us")
    elf = os.path.join(bd, "drmario64.us.elf")
    rom = open(os.path.join(bd, "drmario64.us.bin"), "rb").read()
    s = symbols(elf)
    d = os.path.join(root, "gate_code")
    os.makedirs(os.path.join(d, "asm"), exist_ok=True)
    text = bytearray()
    for seg in ("boot", "main_segment"):
        a, b = s[f"{seg}_TEXT_START"], s[f"{seg}_TEXT_END"]
        rom_off = s[f"{seg}_ROM_START"]
        chunk = bytearray(rom[rom_off:rom_off + (b - a)])
        for u in UCODE:
            if f"{u}TextStart" in s and a <= s[f"{u}TextStart"] < b:
                x, y = s[f"{u}TextStart"] - a, s[f"{u}TextEnd"] - a
                chunk[x:y] = bytes(y - x)
        text += chunk
    open(os.path.join(d, "clean_text.bin"), "wb").write(text)
    # compiled = the .text of every object our build compiled/assembled from decomp sources, as
    # contiguous link-order runs (a window may span two objects); the microcode objects are the
    # only gaps (their bytes come from .incbin, not from compilation)
    import re
    runs, cur, last_end = [], bytearray(), None
    for line in open(os.path.join(bd, "drmario64.us.map")):
        m = re.match(r"^ \.text\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S+\.o)$", line)
        if not m:
            continue
        addr, size, obj = int(m.group(1), 16), int(m.group(2), 16), m.group(3)
        if not size or addr < 0x80000000:
            continue
        seg = next((g for g in ("boot", "main_segment") if s[f"{g}_TEXT_START"] <= addr < s[f"{g}_TEXT_END"]), None)
        if seg is None:
            continue
        data = rom[s[f"{seg}_ROM_START"] + addr - s[f"{seg}_TEXT_START"]:][:size]
        if "/rsp/" in obj or (last_end is not None and addr != last_end):
            if cur:
                runs.append(bytes(cur))
            cur = bytearray()
        if "/rsp/" not in obj:
            cur += data
        last_end = addr + size
    if cur:
        runs.append(bytes(cur))
    import shutil
    shutil.rmtree(os.path.join(d, "asm"), ignore_errors=True)
    os.makedirs(os.path.join(d, "compiled"), exist_ok=True)
    for i, r in enumerate(runs):
        open(os.path.join(d, "compiled", f"run{i:02d}.bin"), "wb").write(r)
    n = len(runs)
    print(f"  gate code: {len(text) // 1024} KB of code (microcode blanked), {n} compiled text runs")


if __name__ == "__main__":
    main(sys.argv)
