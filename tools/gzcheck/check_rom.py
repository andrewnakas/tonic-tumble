"""Run the game's own inflate (gzcheck.exe) on every compressed segment of a built ROM.

    python tools/gzcheck/check_rom.py <rom.z64> <uncompressed image(.gz)> [gzcheck.exe]
"""
import gzip, os, struct, subprocess, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from games.drmario64 import romfile  # noqa: E402


def main(argv):
    rom = open(argv[1], "rb").read()
    unc = (gzip.open if argv[2].endswith(".gz") else open)(argv[2], "rb").read()
    exe = argv[3] if len(argv) > 3 else "D:/n64work/drmario64/gzcheck.exe"
    lay = romfile.layout()
    # current positions come from the boot tables / main end patch
    pos = romfile.positions(rom, lay)
    tmp = tempfile.mkdtemp()
    bad = []
    for s in lay["segments"]:
        if not s["compressed"]:
            continue
        a, b = pos[s["name"]]
        open(os.path.join(tmp, "c"), "wb").write(rom[a:b])
        open(os.path.join(tmp, "u"), "wb").write(unc[s["ustart"]:s["ustart"] + s["ulen"]])
        r = subprocess.run([exe, os.path.join(tmp, "c"), os.path.join(tmp, "u")], capture_output=True, text=True)
        if r.returncode:
            bad.append((s["name"], r.stdout.strip()))
    print(f"gzcheck: {sum(s['compressed'] for s in lay['segments'])} segments, {len(bad)} bad {bad[:6]}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
