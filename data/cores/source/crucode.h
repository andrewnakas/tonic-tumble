/* crucode.h - recognise clean-room RSP microcode placeholder tags ("CRUCODE1").
 *
 * Written for the n64cleanrecomp harness (cleanroom/ucode.py defines the format); CC0 / public domain.
 * A tagged segment (text or data) starts with:
 *   0x00 u32 0x0000000D, u32 0      RSP break + nop
 *   0x08 "CRUCODE1"
 *   0x10 family[16]                 e.g. "f3dex2", "s2dex", "aspmain", "naudio"
 *   0x20 seg[4]                     "TEXT" / "DATA" / "BOOT"
 *   0x24 u16 version (major*100+minor), 0x26 u16 flags, 0x28 u32 size, 0x2C u32 crc32(0x08..0x2B)
 * All fields big-endian. RDRAM in mupen64plus-based emulators is an array of host-endian 32-bit words,
 * so bytes are read through the word that holds them. */
#ifndef CRUCODE_H
#define CRUCODE_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define CRUCODE_FLAG_NON  1u
#define CRUCODE_FLAG_REJ  2u
#define CRUCODE_FLAG_FIFO 4u
#define CRUCODE_FLAG_XBUS 8u
#define CRUCODE_FLAG_LP   16u

typedef struct {
    char family[17];
    char seg[5];
    uint16_t version;
    uint16_t flags;
    uint32_t size;
} crucode_info_t;

static inline uint8_t crucode_rd8(const void *rdram, uint32_t addr)
{
    const uint32_t *w = (const uint32_t *)rdram;
    return (uint8_t)(w[addr >> 2] >> (24 - 8 * (addr & 3)));
}

/* Probe one segment address. rdram_size = bytes of RDRAM behind `rdram`. Returns 1 and fills *out on a tag. */
static inline int crucode_probe(const void *rdram, uint32_t rdram_size, uint32_t addr, crucode_info_t *out)
{
    static const char magic[8] = {'C', 'R', 'U', 'C', 'O', 'D', 'E', '1'};
    uint8_t h[0x30];
    uint32_t i;
    if (rdram == NULL)
        return 0;
    addr &= 0x1FFFFFFFu;
    if (rdram_size < 0x30 || addr > rdram_size - 0x30)
        return 0;
    for (i = 8; i < 16; i++)
        if (crucode_rd8(rdram, addr + i) != (uint8_t)magic[i - 8])
            return 0;
    for (i = 0; i < 0x30; i++)
        h[i] = crucode_rd8(rdram, addr + i);
    if (out) {
        memcpy(out->family, h + 0x10, 16);
        out->family[16] = 0;
        memcpy(out->seg, h + 0x20, 4);
        out->seg[4] = 0;
        out->version = (uint16_t)((h[0x24] << 8) | h[0x25]);
        out->flags = (uint16_t)((h[0x26] << 8) | h[0x27]);
        out->size = ((uint32_t)h[0x28] << 24) | ((uint32_t)h[0x29] << 16) | ((uint32_t)h[0x2A] << 8) | h[0x2B];
    }
    return 1;
}

/* Text segment first, then the data segment. */
static inline int crucode_probe_task(const void *rdram, uint32_t rdram_size, uint32_t uc_start, uint32_t uc_dstart,
                                     crucode_info_t *out)
{
    return crucode_probe(rdram, rdram_size, uc_start, out) || crucode_probe(rdram, rdram_size, uc_dstart, out);
}

static inline int crucode_is(const crucode_info_t *t, const char *family)
{
    return strcmp(t->family, family) == 0;
}

static inline int crucode_is_audio(const crucode_info_t *t)
{
    return strncmp(t->family, "aspmain", 7) == 0 || strncmp(t->family, "naudio", 6) == 0 ||
           strncmp(t->family, "nead_", 5) == 0 || strncmp(t->family, "musyx", 5) == 0 || crucode_is(t, "libmus");
}

static inline int crucode_is_gfx(const crucode_info_t *t)
{
    return !crucode_is_audio(t) && !crucode_is(t, "boot");
}

/* Does a ROM image (z64, v64 or n64 byte order) contain any tag?  Matches break+nop+magic on 4-byte steps. */
static inline int crucode_rom_tagged(const void *rom_, size_t size)
{
    static const uint8_t z64[16] = {0, 0, 0, 0x0D, 0, 0, 0, 0, 'C', 'R', 'U', 'C', 'O', 'D', 'E', '1'};
    uint8_t v64[16], n64[16];
    const uint8_t *rom = (const uint8_t *)rom_;
    size_t i;
    for (i = 0; i < 16; i++) {
        v64[i] = z64[i ^ 1];
        n64[i] = z64[i ^ 3];
    }
    if (rom == NULL || size < 16)
        return 0;
    for (i = 0; i + 16 <= size; i += 4) {
        if (rom[i + 8] != 'C' && rom[i + 8] != 'R' && rom[i + 8] != 'U')
            continue;
        if (!memcmp(rom + i, z64, 16) || !memcmp(rom + i, v64, 16) || !memcmp(rom + i, n64, 16))
            return 1;
    }
    return 0;
}

#endif
