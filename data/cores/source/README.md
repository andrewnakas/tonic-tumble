# CRUCODE1 microcode tags: emulator patches

Clean-room ROMs carry no retail RSP microcode. `cleanroom/ucode.py` writes small original placeholder
segments ("CRUCODE1" tag: RSP `break` + nop, magic, family name, segment kind, version, flags, size,
header crc32; format in the module docstring and `crucode.h`). HLE emulators never execute microcode,
they only identify it; these patches make them identify it from the tag first.

| File | Target | What changes |
|---|---|---|
| `crucode.h` | all | header-only tag reader (CC0); copied into each patched tree by the patch |
| `mupen64plus-rsp-hle.patch` | mupen64plus/mupen64plus-rsp-hle @8a7a472 (native) | tagged task -> family's alist/MusyX handler or gfx plugin; never the LLE fallback |
| `mupen64plus-video-rice.patch` | mupen64plus/mupen64plus-video-rice @f0a7b9f (native) | `DLParser_CheckUcode`: tag -> Rice ucode 0/1/5/7/3 + near-clip/reject flags |
| `mupen64plus-libretro-nx.patch` | EmulatorJS/mupen64plus-libretro-nx @4a3925d (EmulatorJS core) | rsp-hle as above; GLideN64 `loadMicrocode`: tag -> GBI type; libretro: tagged ROM forces GLideN64 + HLE RSP (ParaLLEl/angrylion/cxd4 cannot run stubs) |
| `N64Wasm.patch` | nbarkhina/N64Wasm @bfac222 | older rsp-hle dispatcher, Glide64 (checked every display list), gles2rice; tagged ROM turns off the angrylion/cxd4 (LLE) option |

Builds (Windows, Git Bash; long jobs in the background, `-j2`):

- `build_native.sh <work> [<m64p copy>]` - MSVC Build Tools 2022, Release x64 DLLs for mupen64plus 2.6.
- `build_ejs_core.sh <work> <stock mupen64plus_next-wasm.data> <out .data>` - core `.bc` (emsdk at
  `D:/n64work/emsdk`), linked through EmulatorJS/RetroArch `Makefile.emulatorjs`, packed by `pack_ejs_core.py`
  (WebGL2 variant only; the legacy/WebGL1 variant is the same command with `HAVE_OPENGLES3=0` + core `EMULATORJS_LEGACY=1`).
- `build_n64wasm.sh <work> <out>` - `n64wasm.js` + `n64wasm.wasm`, drop-in for the N64Wasm sites
  (`n64wasm_makefile.py` adapts the 2.0.7-era Makefile to the current emsdk).

Family names (`python -m cleanroom.ucode stub --help`, `FAMILIES` in the module): gfx `f3d f3dex f3dex2
f3dex2_rej f3dzex2_oot f3dzex2_mm l3d l3dex l3dex2 s2dex s2dex2 turbo3d zsortp`; audio `aspmain`
(= `libmus`) `aspmain_ge aspmain_bc naudio naudio_bk naudio_dk naudio_mp3 naudio_cbfd nead_* musyx1 musyx2`;
`boot`. Glide64 and Rice have no per-version S2DEX/F3DZEX modes, so those map to their nearest mode.

What cannot work: real hardware and flash carts (the RSP really runs microcode: a stub halts at its
`break`, the game sees the task finish and draws/plays nothing - plus the clean IPL3 is not CIC-signed),
LLE RSP emulation (cxd4, ParaLLEl RSP, ares, Ares/simple64/Project64 LLE modes, cen64), ParaLLEl-RDP or
angrylion setups that need an LLE RSP, and any unpatched HLE emulator (stock rsp-hle drops the audio
task as "unknown OSTask"; stock GLideN64 asserts/falls back on an unknown graphics ucode).
