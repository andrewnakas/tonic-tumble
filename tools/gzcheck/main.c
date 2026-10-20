/* gzcheck: run the game's own inflate (src/gzip from the decomp) on a compressed segment.
 * usage: gzcheck <compressed file> <expected uncompressed file>   -> prints OK / FAIL */
#include <stdio.h>
#include <stdlib.h>
#include "libultra.h"
size_t expand_gzip(RomOffset segmentRom, void *dstAddr, size_t segmentSize);
static u8 *rom;
void *DmaData_RomToRam(RomOffset off, void *dst, size_t n) { memcpy(dst, rom + off, n); return (u8 *)dst + n; }
static u8 *load(const char *p, long *n) {
    FILE *f = fopen(p, "rb"); if (!f) exit(2);
    fseek(f, 0, SEEK_END); *n = ftell(f); fseek(f, 0, SEEK_SET);
    u8 *b = calloc(1, *n + 0x4000); fread(b, 1, *n, f); fclose(f); return b;
}
int main(int argc, char **argv) {
    long cn, un;
    rom = load(argv[1], &cn);
    u8 *want = load(argv[2], &un);
    u8 *out = calloc(1, un + 0x10000);
    size_t got = expand_gzip(0, out, (size_t)cn);
    int ok = got == (size_t)un && !memcmp(out, want, un);
    printf("%s %zu/%ld\n", ok ? "OK" : "FAIL", got, un);
    return ok ? 0 : 1;
}
