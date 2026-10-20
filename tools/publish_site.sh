#!/bin/sh
# Rebuild the site from the clean ROM and push it to gh-pages. Refuses the retail ROM (make_site.py).
set -e
W=${W:-D:/n64work/drmario64}
cd "$(dirname "$0")/.."
CORE=${CORE:-D:/n64work/ucodeemu/out/mupen64plus_next-wasm.data}          # ucode-tags patched core
CORESRC=${CORESRC:-C:/Users/andre/OneDrive/Documents/n64cleanrecomp/ports/emu/ucode-tags}
python ports/ejs/make_site.py $W/cbuild/drmario64.z64 $W/emu/ejs $W/site --core $CORE --core-src $CORESRC
python ports/ejs/patch_core.py $W/site/tonictumble.z64 $W/site/data/cores $W/site/data/cores
cd $W/site && rm -rf .git
git init -q -b gh-pages 2>/dev/null || true
git remote get-url origin >/dev/null 2>&1 || git remote add origin https://github.com/andrewnakas/drmario64-cleanroom.git
git add -A
git -c user.name=andre -c user.email=treesixtyweather@gmail.com commit -qm "Site update: $(date +%F\ %H:%M)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" || true
git push -q -f origin gh-pages
