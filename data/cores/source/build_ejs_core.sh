#!/bin/bash
# Patched EmulatorJS mupen64plus_next core (GLideN64 + mupen64plus-rsp-hle) that reads CRUCODE1 tags.
#   ports/emu/ucode-tags/build_ejs_core.sh <work dir> <stock mupen64plus_next-wasm.data> <out .data>
# Needs the emsdk at D:/n64work/emsdk (EMSDK env overrides), Git Bash, GNU make, python + py7zr.
# Only the WebGL2 (non-legacy, no threads) variant is built: that is what EmulatorJS 4.2.x loads on
# browsers with WebGL2. -j2 keeps it inside the RAM budget (~25 min core + ~10 min RetroArch link).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
W="${1:?work dir}"; STOCK="${2:?stock core .data}"; OUT="${3:?out .data}"
NX_REV=4a3925d2861f17719586dffb178c1dd5339d3a68      # EmulatorJS/mupen64plus-libretro-nx (develop)
RA_REV=97f2cfa65d01d57406e4ce9459242c8ada7c7e3b      # EmulatorJS/RetroArch
source "${EMSDK:-/d/n64work/emsdk}/emsdk_env.sh" >/dev/null 2>&1
mkdir -p "$W"; cd "$W"
fetch() { [ -d "$2" ] || { git clone -q -c core.autocrlf=false "https://github.com/$1.git" "$2" && git -C "$2" checkout -q "$3"; }; }
fetch EmulatorJS/mupen64plus-libretro-nx mupen64plus-libretro-nx $NX_REV
fetch EmulatorJS/RetroArch RetroArch $RA_REV
grep -q crucode mupen64plus-libretro-nx/GLideN64/src/GBI.cpp || \
  git -C mupen64plus-libretro-nx apply --whitespace=nowarn "$HERE/mupen64plus-libretro-nx.patch"
( cd mupen64plus-libretro-nx && emmake make -j2 platform=emscripten > ../nx_build.log 2>&1 ) || { tail -20 nx_build.log; exit 1; }
cp mupen64plus-libretro-nx/mupen64plus_next_libretro_emscripten.bc RetroArch/libretro_emscripten.a
( cd RetroArch && emmake make -f Makefile.emulatorjs HAVE_7ZIP=1 HAVE_CHD=1 HAVE_THREADS=0 PTHREAD_POOL_SIZE=0 ASYNC=1 \
    HAVE_OPENGLES3=1 STACK_SIZE=134217728 INITIAL_HEAP=536870912 HAVE_AL=0 HAVE_RWEBAUDIO=1 LIGHT_DEBUG=0 \
    TARGET=mupen64plus_next_libretro.js LD=emcc -j2 > ../ra_build.log 2>&1 ) || { tail -20 ra_build.log; exit 1; }
python "$HERE/pack_ejs_core.py" "$STOCK" RetroArch/mupen64plus_next_libretro.js RetroArch/mupen64plus_next_libretro.wasm "$OUT"
