# Taint report: drmario64 (Tonic Tumble)

`python -m games.drmario64.taint_report D:/n64work/drmario64/dirty <cbuild>/build/us/drmario64.us_uncompressed.z64 --assets <cassets>`

```
taint: 428899 retail asset windows (1205 tex, 393 pal, 190 wave, 25 seq, 323 vtx) scanned over the clean image (6410 KB): 0 failing
taint: 1205 clean PNGs vs retail PNGs (RGBA, same path): 0 failing (run >= 32 B)
  not scanned (publishing blocker): RSP microcode rspboot/aspMain/F3DEX2/S2DEX, carried unchanged
```

The last line above is a fixed message in `taint_report.py` from before commit 3479f7f. The ROM no longer carries retail
microcode. The microcode check on the same image (re-run 2026-10-20) gives:

`python -m cleanroom.ucode scan <cbuild>/build/us/drmario64.us_uncompressed.z64`

```
drmario64.us_uncompressed.z64 (z64, 6410 KB): 0 retail ucode segment(s) from ucode_known.json, 7 tag stub(s), 0 retail-looking ucode version string(s)
  tag    boot         BOOT @0x070ac0   208 bytes v0
  tag    aspmain      TEXT @0x070b90  3616 bytes v0
  tag    f3dex2       TEXT @0x0719b0  5008 bytes v208 fifo
  tag    s2dex        TEXT @0x072d40  6128 bytes v107 fifo
  tag    aspmain      DATA @0x097fe0   704 bytes v0
  tag    f3dex2       DATA @0x0982a0  1056 bytes v208 fifo
  tag    s2dex        DATA @0x0986c0   960 bytes v107 fifo
```
