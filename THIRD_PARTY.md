# Tonic Tumble: credits and third-party notices

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
