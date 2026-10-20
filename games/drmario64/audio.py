"""Dr. Mario 64 samples: libmus "N64 PtrTablesV2" bank + wave table.

Dirty: `extract(rom, ptr_off, wave_off, spec)` writes spec/samples.json (per wave: length,
type, loop points, book shape, coarse spectral outline, median pitch) and zeroes every
sample byte, codebook and loop state in the skeleton.
Clean: `write(img, ptr_off, wave_off)` resynthesises each wave from its outline, encodes it
with our own codebook (same predictor count, so the bank keeps its size) and fills loop states.

ALWaveTable (libaudio): base, len, type (0 ADPCM, 1 raw16), flags, loop*, book*;
pointers are relative (base to the wave table, loop/book to the ptr file).
"""
import json
import os
import struct

import numpy as np

from cleanroom.audio import descriptor, vadpcm
from cleanroom.audio.pitch import median_f0
from cleanroom.decomp import gen

RATE = 22050   # nominal rate for outline/pitch (libmus pitches by basenote/detune; only ratios matter)
SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec")


def parse(rom, ptr):
    assert rom[ptr:ptr + 15] == b"N64 PtrTablesV2"
    count = struct.unpack(">i", rom[ptr + 0x20:ptr + 0x24])[0]
    bn, dt, wl = struct.unpack(">III", rom[ptr + 0x24:ptr + 0x30])
    waves = []
    for i in range(count):
        wp = struct.unpack(">I", rom[ptr + wl + 4 * i:ptr + wl + 4 * i + 4])[0]
        base, ln, typ, flags, loop, book = struct.unpack(">IIBBxxII", rom[ptr + wp:ptr + wp + 20])
        w = dict(i=i, ptr=wp, base=base, len=ln, type=typ, loop_off=loop, book_off=book,
                 basenote=rom[ptr + bn + i], detune=struct.unpack(">f", rom[ptr + dt + 4 * i:ptr + dt + 4 * i + 4])[0])
        if book and typ == 0:
            order, npred = struct.unpack(">ii", rom[ptr + book:ptr + book + 8])
            assert order == 2, (i, order)
            w["order"], w["npred"] = order, npred
        if loop:
            s, e, c = struct.unpack(">IIi", rom[ptr + loop:ptr + loop + 12])
            w["loop"] = [s, e, c]
        waves.append(w)
    return waves


def nsamples(w):
    return w["len"] // 9 * 16 if w["type"] == 0 else w["len"] // 2


def book_bytes(w):
    return 8 + w["order"] * w["npred"] * 8 * 2


def extract(rom, ptr, wave, spec_dir=SPEC):
    """rom: bytearray (the skeleton being built). Returns bytes zeroed."""
    waves = parse(rom, ptr)
    facts = []
    zero = 0
    for w in waves:
        raw = bytes(rom[wave + w["base"]:wave + w["base"] + w["len"]])
        n = nsamples(w)
        if w["type"] == 0:
            b = struct.unpack(">%dh" % (w["order"] * w["npred"] * 8), rom[ptr + w["book_off"] + 8:ptr + w["book_off"] + book_bytes(w)])
            pcm = vadpcm.decode(raw, {"order": w["order"], "npred": w["npred"], "book": list(b)}, n).astype(np.float64)
        else:
            pcm = np.frombuffer(raw[:n * 2], ">i2").astype(np.float64)
        d = {k: w[k] for k in ("i", "ptr", "base", "len", "type", "loop_off", "book_off", "basenote", "detune") }
        for k in ("order", "npred", "loop"):
            if k in w:
                d[k] = w[k]
        d["nframes"], d["rate"] = n, RATE
        d["desc"] = descriptor.describe(pcm, RATE)
        f0 = median_f0((pcm / 32768).astype(np.float32), RATE)
        if f0:
            d["f0"] = round(f0, 1)
        facts.append(d)
        rom[wave + w["base"]:wave + w["base"] + w["len"]] = bytes(w["len"])
        zero += w["len"]
        if w["type"] == 0:
            o = ptr + w["book_off"] + 8
            rom[o:o + book_bytes(w) - 8] = bytes(book_bytes(w) - 8)
        if w.get("loop") and w["type"] == 0:
            o = ptr + w["loop_off"] + 12
            rom[o:o + 32] = bytes(32)
    json.dump(facts, open(os.path.join(spec_dir, "samples.json"), "w"))
    return len(facts), zero


def synth(d, supplied=None):
    n = d["nframes"]
    x = supplied if supplied is not None else descriptor.synthesize(d["desc"], n, RATE, seed=gen.h32("drm64smp", d["i"]))
    x = np.asarray(x, np.float32)[:n]
    x = np.pad(x, (0, n - len(x)))
    if d.get("loop") and supplied is None and d["loop"][1] > d["loop"][0] + 32:
        x = descriptor.make_loop_seamless(x, d["loop"][0], min(d["loop"][1], n))
    dither = np.random.default_rng(gen.h32("drm64dither", d["i"])).integers(-1, 2, n)
    return np.clip(np.round(np.clip(x, -1, 1) * 32000) + dither, -32768, 32767).astype(np.int16)


def write(img, ptr, wave, hook=None, spec_dir=SPEC):
    facts = json.load(open(os.path.join(spec_dir, "samples.json")))
    for d in facts:
        pcm = synth(d, hook(d) if hook else None)
        if d["type"] != 0:
            data = pcm.astype(">i2").tobytes()[:d["len"]]
        else:
            preds = gen.two_predictors(pcm.astype(np.float64))
            preds = (preds * d["npred"])[:d["npred"]] if d["npred"] >= 2 else preds[:1]
            book = vadpcm.make_book(preds)
            data, _, dec = vadpcm.encode(pcm, book)
            data = bytes(data)[:d["len"]]
            data += bytes(d["len"] - len(data))
            o = ptr + d["book_off"]
            img[o:o + 8] = struct.pack(">ii", 2, d["npred"])
            img[o + 8:o + 8 + len(book["book"]) * 2] = struct.pack(">%dh" % len(book["book"]), *book["book"])
            if d.get("loop"):
                st = vadpcm.loop_state(dec, d["loop"][0])
                o = ptr + d["loop_off"] + 12
                img[o:o + 32] = struct.pack(">16h", *st)
        img[wave + d["base"]:wave + d["base"] + d["len"]] = data
    return len(facts)
