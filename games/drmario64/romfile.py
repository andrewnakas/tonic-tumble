"""Uncompressed image <-> N64 ROM for Dr. Mario 64 (layout kept: every segment stays in its slot).

    python -m games.drmario64.romfile roundtrip <dirty tree>     (dev check: rebuild retail from its own image)
"""
import json
import os
import struct
import sys

import crunch64
import ipl3checksum

TABLES = (0xF340, 0xF650)   # storyRomData .. _romDataTbl in boot_data.c (ROM offsets, 8-byte pairs)
MAIN_END_LUI = 0x1134   # lui a2,0x5 ; addiu a2,a2,-0x680 in boot_main (ROM offset)
SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec")


def layout():
    return json.load(open(os.path.join(SPEC, "layout.json")))


def build(unc, lay=None, level=None, fill=0xFF, pad_main=0, pad_after=None):
    """unc: uncompressed image bytes. Returns (rom bytes, report list of (segment, used, slot)).

    Everything before main_segment keeps its place; main_segment keeps its start and may grow
    (boot code loads its end with one lui/addiu pair, patched here). Every later segment is referenced only through the {start, end}
    tables in boot_data.c (uncompressed), so later segments are packed one after another
    and those pairs are rewritten."""
    lay = lay or layout()
    segs = lay["segments"]
    main = next(s for s in segs if s["name"] == "main_segment")
    blobs, report = [], []
    for s in segs:
        data = bytes(unc[s["ustart"]:s["ustart"] + s["ulen"]])
        if s["compressed"]:
            lv = s["level"] if level is None else level
            data = compress_checked(data, lv, s["tool"] == "gzip_smallmem")
            data += bytes(-len(data) % 16)
            report.append((s["name"], len(data), s["cend"] - s["cstart"]))
        blobs.append(data)
    out = bytearray()
    moved, raw_moved = {}, {}
    for s, data in zip(segs, blobs):
        if s is main:
            out += data + bytes(pad_main)   # may grow: its end is patched in boot_main below
            main_end = len(out)
            continue
        if s["cstart"] < main["cstart"]:
            slot = s["cend"] - s["cstart"]
            if len(data) > slot:
                raise ValueError(f"fixed segment {s['name'] or hex(s['cstart'])} is {len(data):#x} > slot {slot:#x}")
            out += data + bytes(slot - len(data))
            continue
        start = len(out)
        out += data + bytes((pad_after or {}).get(s["name"], 0))
        moved[(s["cstart"], s["cend"])] = (start, start + len(data))
        raw_moved[(s["cstart"], s["cend"])] = not s["compressed"]
    size = max(lay["crom_len"], (len(out) + 0xFFFFF) & ~0xFFFFF)
    out += bytes([fill]) * (size - len(out))
    # boot_data.c tables: arrays of {start, end}. Whole compressed segments match exactly; the
    # uncompressed audio/data region holds several blobs (wave table, ptr table, fxbank, songs)
    # whose pairs point inside it, so those are shifted with their region.
    patched = 0
    fixed = bytes(out[:main["cstart"]])
    lo_t, hi_t = TABLES
    for o in range(lo_t, hi_t, 8):
        a, b = struct.unpack(">II", fixed[o:o + 8])
        for (sa, sb), (na, nb) in moved.items():
            seg_raw = raw_moved.get((sa, sb))
            if (a, b) == (sa, sb):
                out[o:o + 8] = struct.pack(">II", na, nb)
            elif seg_raw and sa <= a < b <= sb:   # a blob inside an uncompressed region moves with it
                out[o:o + 8] = struct.pack(">II", a - sa + na, b - sa + na)
            else:
                continue
            patched += 1
            break
    report.append(("pairs patched", patched, len(moved)))
    # boot_main.c: SEGMENT_ROM_END(main_segment) as lui/addiu a2 (retail 0x4F980)
    assert out[MAIN_END_LUI:MAIN_END_LUI + 4] == bytes.fromhex("3c060005") and         out[MAIN_END_LUI + 4:MAIN_END_LUI + 8] == bytes.fromhex("24c6f980"), "boot_main layout changed"
    hi, lo = (main_end + 0x8000) >> 16, main_end & 0xFFFF
    out[MAIN_END_LUI + 2:MAIN_END_LUI + 4] = hi.to_bytes(2, "big")
    out[MAIN_END_LUI + 6:MAIN_END_LUI + 8] = lo.to_bytes(2, "big")
    return fix_crc(out), report


GZCHECK = os.environ.get("GZCHECK", "D:/n64work/drmario64/gzcheck.exe")


def _zlib(data, level, strategy=0):
    import zlib
    c = zlib.compressobj(level, zlib.DEFLATED, -15, 9, strategy)
    return c.compress(data) + c.flush() + struct.pack("<II", zlib.crc32(data), len(data))


def game_inflates(comp, data):
    """True if the game's own inflate (tools/gzcheck, built from the decomp) restores `data`.
    Its Huffman tables live in a fixed 16 KB arena; many valid streams overflow it."""
    import subprocess
    import tempfile
    d = tempfile.mkdtemp(dir=os.environ.get("TEMP"))
    c, u = os.path.join(d, "c"), os.path.join(d, "u")
    open(c, "wb").write(comp)
    open(u, "wb").write(data)
    r = subprocess.run([GZCHECK, c, u], capture_output=True, text=True)
    os.remove(c), os.remove(u), os.rmdir(d)
    return r.returncode == 0 and r.stdout.startswith("OK")


def compress_checked(data, level, small_mem=True):
    import zlib
    tries = [(lambda lv=lv: crunch64.gzip.compress(data, lv, small_mem=small_mem)) for lv in dict.fromkeys((level, 9, 8, 7, 6, 5, 4))]
    tries += [(lambda lv=lv: _zlib(data, lv)) for lv in (9, 6, 3, 1)]
    tries += [lambda: _zlib(data, 9, zlib.Z_FIXED), lambda: _zlib(data, 0)]
    for t in tries:
        try:
            comp = bytes(t())
        except RuntimeError:
            continue
        if game_inflates(comp, data):
            return comp
    raise ValueError("no stream the game's inflate accepts")


def positions(rom, lay=None):
    """Segment name -> (start, end) in a ROM we built: read back from the boot tables."""
    lay = lay or layout()
    ret = {}
    main = next(s for s in lay["segments"] if s["name"] == "main_segment")
    hi, lo = struct.unpack(">H", rom[MAIN_END_LUI + 2:MAIN_END_LUI + 4])[0], struct.unpack(">h", rom[MAIN_END_LUI + 6:MAIN_END_LUI + 8])[0]
    ret["main_segment"] = (main["cstart"], (hi << 16) + lo)
    retail = {(s["cstart"], s["cend"]): s["name"] for s in lay["segments"]}
    orig = layout_retail_pairs()
    for o, (a, b) in orig.items():
        if (a, b) in retail and retail[(a, b)]:
            ret[retail[(a, b)]] = struct.unpack(">II", rom[o:o + 8])
    return ret


def layout_retail_pairs():
    return {int(k): tuple(v) for k, v in json.load(open(os.path.join(SPEC, "table_pairs.json"))).items()}


def fix_crc(rom):
    rom = bytearray(rom)
    cic = ipl3checksum.detectCIC(rom) or ipl3checksum.CICKind.CIC_6102_7101
    c1, c2 = ipl3checksum.calculateChecksum(rom, cic)
    rom[0x10:0x14] = c1.to_bytes(4, "big")
    rom[0x14:0x18] = c2.to_bytes(4, "big")
    return bytes(rom)


def main(argv):
    if argv[1] == "roundtrip":
        tree = argv[2]
        unc = open(os.path.join(tree, "config/us/baserom_uncompressed.us.z64"), "rb").read()
        ret = open(os.path.join(tree, "config/us/baserom.us.z64"), "rb").read()
        rom, rep = build(unc)
        diff = [i for i in range(0, len(rom), 0x1000) if rom[i:i + 0x1000] != ret[i:i + 0x1000]]
        print(f"roundtrip: {'OK identical' if rom == ret else f'{len(diff)} differing 4K blocks (alignment garbage expected), first {diff[:5]}'}; {rep[-1]}")


if __name__ == "__main__":
    main(sys.argv)
