#!/bin/sh
# build gzcheck.exe from the decomp's own gzip sources: tools/gzcheck/build.sh <pristine tree> <out exe>
set -e
S=$1/src/gzip; T=$(mktemp -d)
cp -r "$(dirname "$0")"/shim/* "$T"/ && cp "$1/include/gzip.h" "$T"/
ZIG=${ZIG:-$HOME/.local/zig-x86_64-windows-0.16.0/zig.exe}
"$ZIG" cc -target x86-windows-gnu -O1 -w -I"$T" -include libultra.h -o "$2" "$(dirname "$0")/main.c" $S/gzip.c $S/unzip.c $S/inflate.c
rm -rf "$T"
