"""Dr. Mario 64 music: libmus (Software Creations "MusicTools") songs, sound effects and bank.

DIRTY  extract(dirty, spec, local)   -> spec/music.json (structure only) and, for the
       originality gate, the retail notes as MIDI in <dirty>/../gate/music/ (never committed).
CLEAN  write_all(local, out)          -> out/segment_*.databin.bin (new songs),
       out/fxbank.databin.bin (new effects), out/n64_ptr_tables_v2/n64_wave_tables
       databins (bank rebuilt from facts, samples resynthesised by audio.py), and
       out/gate_music/*.mid (our songs parsed back from the bytes we wrote).

Kept per song (structure): tempo, intro/loop lengths (ticks), channel count, which
channels are drum channels, each channel's register (median/min/max note), note
count, instrument setup (song-local wave, envelope, pan, volume, reverb) and the
song's instrument tables (wave map, envelopes, drum map). Melodies, harmonies and
rhythms come from cleanroom.audio.compose (seeded, mood tags chosen here).

libmus channel stream: commands >= 0x80 with arguments, then notes:
note byte (96 = rest), velocity byte while velocity mode is on, length (1 byte, or
2 bytes with the top bit set) unless a fixed length is active.
"""
import json
import os
import statistics
import struct

import numpy as np

from cleanroom.audio import midi
from cleanroom.audio.compose import compose
from cleanroom.audio.notes import Note

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec")
REST = 96
ARGS = {0x80: -1, 0x81: "v", 0x82: 1, 0x83: 0, 0x84: 7, 0x85: 1, 0x86: 2, 0x87: 1, 0x88: 3, 0x89: 3, 0x8a: 0,
        0x8b: "v", 0x8c: 0, 0x8d: 1, 0x8e: 0, 0x8f: 1, 0x90: "v", 0x91: 0, 0x92: 0, 0x93: 0, 0x94: 0, 0x95: 1,
        0x96: 0, 0x97: 3, 0x98: 0, 0x99: 0, 0x9a: 0, 0x9b: 1, 0x9c: 1, 0x9d: 2, 0x9e: "v", 0x9f: 0, 0xa0: 1,
        0xa1: 6, 0xa2: 1, 0xa3: 2, 0xa4: 2, 0xa5: 2, 0xa6: 1, 0xa7: "v", 0xa8: 1, 0xa9: 1, 0xaa: 1, 0xab: "m",
        0xac: 0}
SETUP = {0x81: "wave", 0x84: "defa", 0x90: "env", 0x9c: "pan", 0xa6: "volume", 0xa2: "reverb", 0x9e: "drums",
         0xa8: "bendrange", 0x87: "endit", 0x82: "port", 0x9b: "velocity"}

# our choices per song (the seed and moods are ours; pairs share a seed: same tune, two tempos)
MOODS = {
    "segment_172D60": (11, ["bright", "busy"]), "segment_1750C0": (11, ["bright", "busy"]),
    "segment_177420": (12, ["calm", "dorian"]), "segment_179620": (12, ["calm"]),
    "segment_17B790": (13, ["happy"]), "segment_17C1E0": (14, ["calm", "major"]),
    "segment_17D130": (14, ["calm", "major"]), "segment_17E090": (15, ["tense", "fast"]),
    "segment_181840": (15, ["tense", "fast"]), "segment_184FF0": (16, ["heroic"]),
    "segment_186FF0": (16, ["heroic"]), "segment_188FF0": (17, ["sad"]), "segment_189D40": (18, ["dark", "busy"]),
    "segment_18CB40": (19, ["eerie"]), "segment_18DB90": (20, ["heroic", "fast"]),
    "segment_18F160": (20, ["heroic", "fast"]), "segment_1906E0": (21, ["triumphant"]),
    "segment_1911D0": (22, ["dark", "fast"]), "segment_1936C0": (23, ["happy"]),
    "segment_1937F0": (24, ["bright"]), "segment_194070": (25, ["happy"]),
    "segment_194150": (26, ["calm"]), "segment_194910": (27, ["busy", "happy"]), "segment_195290": (28, ["sad"]),
}


# ---------------------------------------------------------------- parsing (both sides)

def play(d, p0, vel=True, maxev=60000):
    """Interpret one channel stream. -> (events, loop) ; events (t, 'note', key, len, vel)
    or (t, 'cmd', op, args); loop = (start, end) ticks of an infinite for/next, or None."""
    p, out, fixed, ign, t, stack = p0, [], 0, False, 0, []
    while len(out) < maxev:
        c = d[p]
        if c >= 0x80:
            a, q = ARGS[c], p + 1
            if a == -1:
                out.append((t, "stop"))
                return out, None
            n = 1 + (d[q] >> 7) if a == "v" else (2 + (d[q + 1] >> 7) if a == "m" else a)
            args = bytes(d[q:q + n])
            p = q + n
            if c == 0x8b:
                fixed = ((args[0] & 0x7f) << 8 | args[1]) if args[0] & 0x80 else args[0]
            elif c == 0xac:
                fixed = 0
            elif c == 0x8c:
                ign = True
            elif c == 0x99:
                vel = True
            elif c == 0x9a:
                vel = False
            elif c == 0x95:
                stack.append([args[0], p, t])
            elif c == 0x96:
                s = stack[-1]
                if s[0] == 0xff:
                    out.append((t, "loopend"))
                    return out, (s[2], t)
                s[0] -= 1
                if s[0] == 0:
                    stack.pop()
                else:
                    p = s[1]
                continue
            elif c == 0xa1:
                out.append((t, "goto"))
                return out, None
            out.append((t, "cmd", c, args))
            continue
        key, v = d[p], None
        p += 1
        if vel:
            v = d[p]
            p += 1
            if v >= 0x80:
                vel, v = False, v & 0x7f
        if fixed and not ign:
            ln = fixed
        else:
            ign = False
            ln = d[p]
            p += 1
            if ln >= 0x80:
                ln = (ln & 0x7f) << 8 | d[p]
                p += 1
        out.append((t, "note", key, ln, v))
        t += ln
    return out, None


def header(d):
    ver, nch, nw = struct.unpack(">Iii", d[:12])
    ptr = struct.unpack(">7I", d[12:40])
    lst = lambda o: list(struct.unpack(">%dI" % nch, d[o:o + 4 * nch]))
    return dict(ver=ver, nch=nch, nw=nw, ptr=ptr, data=lst(ptr[0]), vol=lst(ptr[1]), pb=lst(ptr[2]))


def song_notes(d):
    """[Note] of a song (drum-mode notes keep their drum index as key), division 48."""
    h = header(d)
    notes = []
    for ch in range(h["nch"]):
        if not h["data"][ch]:
            continue
        ev, _ = play(d, h["data"][ch])
        for e in ev:
            if e[1] == "note" and e[2] != REST:
                notes.append(Note(e[0], ch, e[2], e[4] or 100, e[3]))
    return sorted(notes)


def to_mid(d, path):
    h = header(d)
    mt, _ = play(d, h["ptr"][6])
    tempo = next((e[3][0] for e in mt if e[1] == "cmd" and e[2] == 0x85), 120)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(midi.write(song_notes(d), 48, int(round(60e6 / max(tempo, 1)))))


# ---------------------------------------------------------------- dirty side

def _vol_median(d, off):
    """Median of a continuous-volume stream (RLE: value | 0x80 then run length)."""
    vals, p = [], off
    for _ in range(400):
        if p >= len(d):
            break
        v = d[p]
        p += 1
        if v > 127:
            r = d[p]
            p += 1
            if r > 127:
                p += 1
            vals.append(v & 0x7f)
        else:
            vals.append(v)
    return int(statistics.median(vals)) if vals else 100


def song_facts(name, d):
    h = header(d)
    mt, mloop = play(d, h["ptr"][6])
    tempos = [e[3][0] for e in mt if e[1] == "cmd" and e[2] == 0x85]
    fx = next((e[3][0] for e in mt if e[1] == "cmd" and e[2] == 0xaa), None)
    chans = []
    for ch in range(h["nch"]):
        if not h["data"][ch]:
            chans.append(None)
            continue
        ev, loop = play(d, h["data"][ch])
        setup, drum_notes, notes = {}, [], []
        drums = False
        for e in ev:
            if e[1] == "cmd":
                if e[2] == 0x9e:
                    drums = True
                elif e[2] == 0x9f:
                    drums = False
                if not notes and e[2] in SETUP and SETUP[e[2]] not in setup:
                    setup[SETUP[e[2]]] = list(e[3])
            elif e[1] == "note" and e[2] != REST:
                (drum_notes if drums else notes).append(e[2])
        c = dict(n=len(notes), ndrum=len(drum_notes), setup=setup,
                 end=ev[-1][0], loop=list(loop) if loop else None)
        if h["vol"][ch]:
            c["volume_median"] = _vol_median(d, h["vol"][ch])
        if notes:
            c["register"] = [int(np.percentile(notes, 10)), int(statistics.median(notes)), int(np.percentile(notes, 90))]
        if drum_notes:
            vals, cnt = np.unique(drum_notes, return_counts=True)
            c["drum_slots"] = [int(v) for v in vals[np.argsort(-cnt)][:4]]   # most used drum-map slots
        chans.append(c)
    p = h["ptr"]
    marks = sorted({x for x in list(p) + h["data"] + h["vol"] + h["pb"] if x} | {len(d)})
    nxt = lambda o: min(x for x in marks if x > o)
    env = list(d[p[3]:p[3] + (nxt(p[3]) - p[3]) // 7 * 7]) if p[3] else []
    drum_n = (nxt(p[4]) - p[4]) // 6 if p[4] else 0
    return dict(name=name, size=len(d), ver=h["ver"], nch=h["nch"], nw=h["nw"], tempos=tempos, changefx=fx,
                master_loop=list(mloop) if mloop else None, master_end=mt[-1][0],
                wave_table=list(struct.unpack(">%dH" % h["nw"], d[p[5]:p[5] + 2 * h["nw"]])),
                env_table=env, drum_table=[list(struct.unpack(">HHBB", d[p[4] + 6 * i:p[4] + 6 * i + 6]))
                                           for i in range(drum_n)],
                channels=chans)


def fx_facts(d):
    ncomp, neff, nw, flags, ptra, wt = struct.unpack(">iiiIII", d[:24])
    effs = []
    for i in range(neff):
        off, pri = struct.unpack(">Ii", d[24 + 8 * i:32 + 8 * i])
        if not off:
            effs.append(None)
            continue
        ev, loop = play(d, off, vel=False, maxev=400)
        setup, notes = {}, []
        for e in ev:
            if e[1] == "cmd" and not notes and e[2] in SETUP and SETUP[e[2]] not in setup:
                setup[SETUP[e[2]]] = list(e[3])
            elif e[1] == "note":
                notes.append((e[2], e[3]))
        keys = [k for k, _ in notes if k != REST]
        effs.append(dict(priority=pri, setup=setup, n=len(notes), total=sum(l for _, l in notes),
                         register=[min(keys), int(statistics.median(keys)), max(keys)] if keys else None,
                         loop=bool(loop), cmds=sorted({e[2] for e in ev if e[1] == "cmd"})))
    return dict(ncomp=ncomp, neff=neff, nw=nw, flags=flags, size=len(d),
                wave_table=list(struct.unpack(">%dH" % nw, d[wt:wt + 2 * nw])), effects=effs)


def bank_facts(ptr_bin, wave_bin):
    d = ptr_bin
    count = struct.unpack(">i", d[0x20:0x24])[0]
    bn, dt, wl = struct.unpack(">III", d[0x24:0x30])
    waves = []
    for i in range(count):
        wp = struct.unpack(">I", d[wl + 4 * i:wl + 4 * i + 4])[0]
        base, ln, typ, flags, loop, book = struct.unpack(">IIBBxxII", d[wp:wp + 20])
        waves.append(dict(flags=flags))
    return dict(size=len(d), wave_size=len(wave_bin), name=d[:16].hex(), flags=struct.unpack(">I", d[16:20])[0],
                wbk=d[20:32].hex(), offsets=[bn, dt, wl], wave_flags=[w["flags"] for w in waves])


def extract(dirty, spec, local):
    import glob
    b = os.path.join(dirty, "bin", "us")
    gate = os.path.join(os.path.dirname(os.path.abspath(dirty)), "gate", "music")
    songs = {}
    for p in sorted(glob.glob(os.path.join(b, "segment_1*.databin.bin"))):
        name = os.path.basename(p)[:-len(".databin.bin")]
        d = open(p, "rb").read()
        songs[name] = song_facts(name, d)
        to_mid(d, os.path.join(gate, name + ".mid"))
    fx = fx_facts(open(os.path.join(b, "fxbank.databin.bin"), "rb").read())
    bank = bank_facts(open(os.path.join(b, "n64_ptr_tables_v2.databin.bin"), "rb").read(),
                      open(os.path.join(b, "n64_wave_tables.databin.bin"), "rb").read())
    json.dump(dict(songs=songs, fx=fx, bank=bank), open(os.path.join(spec, "music.json"), "w"), indent=0)
    return f"music facts: {len(songs)} songs, {fx['neff']} effects; retail MIDI -> {gate}"


# ---------------------------------------------------------------- clean side

def _len_bytes(n):
    assert 0 < n <= 0x7fff
    return bytes([n]) if n < 0x80 else bytes([0x80 | n >> 8, n & 0xff])


def _rests(total, vel=True):
    out = b""
    while total > 0:
        n = min(total, 0x7fff)
        out += bytes([REST]) + (b"\x00" if vel else b"") + _len_bytes(n)
        total -= n
    return out


def _events(notes, t0, t1, vel=True):
    """Monophonic note list -> stream bytes covering [t0, t1)."""
    out, t = b"", t0
    notes = sorted(n for n in notes if t0 <= n.time < t1)
    for i, n in enumerate(notes):
        if n.time > t:
            out += _rests(n.time - t, vel)
            t = n.time
        if n.time < t:
            continue
        nxt = notes[i + 1].time if i + 1 < len(notes) else t1
        dur = max(1, min(n.dur, nxt - n.time, t1 - n.time))
        out += bytes([n.key]) + (bytes([max(1, min(127, n.vel))]) if vel else b"") + _len_bytes(min(dur, 0x7fff))
        t = n.time + min(dur, 0x7fff)
    if t < t1:
        out += _rests(t1 - t, vel)
    return out


def _vidx(args):
    """libmus variable index (1 byte, or 2 with the top bit set) -> int."""
    return ((args[0] & 0x7f) << 8 | args[1]) if args[0] & 0x80 else args[0]


def _venc(v):
    return [v] if v < 0x80 else [0x80 | v >> 8, v & 0xff]


def _derange(rng, n):
    """Seeded permutation with no fixed point (n > 1), so no table keeps its old numbering."""
    p = [int(x) for x in rng.permutation(n)]
    if n > 1:
        for i in range(n):
            if p[i] == i:
                j = (i + 1) % n
                p[i], p[j] = p[j], p[i]
    return p


class Tables:
    """Our own encoding of a song's instrument tables: the local wave and envelope
    numbering is a seeded permutation (same instruments, different numbers), so the
    tables and every reference to them are re-encoded rather than copied."""

    def __init__(self, f, seed):
        rng = np.random.default_rng(seed)
        nw = len(f["wave_table"])
        self.wp = _derange(rng, nw)
        ne = len(f.get("env_table", [])) // 7
        self.ep = _derange(rng, ne) if ne else []
        self.wt = [0] * nw
        for i, w in enumerate(f["wave_table"]):
            self.wt[self.wp[i]] = w
        env = f.get("env_table", [])
        self.env = [0] * len(env)
        for i in range(ne):
            self.env[7 * self.ep[i]:7 * self.ep[i] + 7] = env[7 * i:7 * i + 7]
        self.drums = [[self.wp[e[0]] if e[0] < nw else e[0], self.ep[e[1]] if e[1] < ne else e[1], e[2], e[3]]
                      for e in f.get("drum_table", [])]

    def setup(self, setup):
        s = dict(setup)
        if "wave" in s:
            w = _vidx(s["wave"])
            s["wave"] = _venc(self.wp[w] if w < len(self.wp) else w)
        if "env" in s and self.ep:
            e = _vidx(s["env"])
            s["env"] = _venc(self.ep[e] if e < len(self.ep) else e)
        return s


def _setup_bytes(setup, drums):
    out = b""
    for op, key in ((0x81, "wave"), (0x84, "defa"), (0x90, "env"), (0x9c, "pan"), (0xa6, "volume"),
                    (0xa2, "reverb"), (0xa8, "bendrange")):
        if key in setup:
            out += bytes([op]) + bytes(setup[key])
    if drums is not None:
        out += bytes([0x9e]) + bytes(drums)
    return out


def _fit_register(notes, reg):
    """Shift a channel's notes by octaves so its median sits near the kept register."""
    if not notes or not reg:
        return notes
    med = statistics.median(n.key for n in notes)
    shift = 12 * round((reg[1] - med) / 12)
    lo, hi = max(1, reg[0] - 12), min(95, reg[2] + 12)
    out = []
    for n in notes:
        k = n.key + shift
        while k < lo:
            k += 12
        while k > hi:
            k -= 12
        out.append(n._replace(key=int(min(95, max(1, k)))))
    return out


def roles_for(f):
    """Role per channel from structure: drum channels, the lowest melodic line is bass,
    the busiest high line is lead, the rest counter/arp/pad in turn."""
    roles = [None] * f["nch"]
    mel = [i for i, c in enumerate(f["channels"]) if c and c["n"] > 0 and c["n"] >= c["ndrum"]]
    drum = [i for i, c in enumerate(f["channels"]) if c and c["ndrum"] > c["n"]]
    for i in drum:
        roles[i] = "drums"
    if mel:
        bass = min(mel, key=lambda i: f["channels"][i]["register"][1])
        roles[bass] = "bass"
        rest = [i for i in mel if i != bass]
        if rest:
            lead = max(rest, key=lambda i: (f["channels"][i]["n"] * (f["channels"][i]["register"][1] > 30)))
            roles[lead] = "lead"
            cyc = ["counter", "arp", "pad"]
            for k, i in enumerate([i for i in rest if i != lead]):
                roles[i] = cyc[k % 3]
    for i, c in enumerate(f["channels"]):
        if c and roles[i] is None:
            roles[i] = "pad"
    return roles


def song_span(f):
    """(intro, span) ticks for looping songs, (length, None) for jingles."""
    loops = [tuple(c["loop"]) for c in f["channels"] if c and c["loop"]]
    if loops:
        intro = min(l[0] for l in loops)
        return intro, max(l[1] - l[0] for l in loops)
    return max(f["master_end"], max((c["end"] for c in f["channels"] if c), default=96)), None


def compose_song(f, body):
    """Compose intro + one loop body of `body` ticks (the body repeats to fill the loop)."""
    seed, moods = MOODS.get(f["name"], (99, ["calm"]))
    intro, span = song_span(f)
    if span is None:
        length, loop = intro, None
    else:
        length, loop = intro + body, intro
    roles = roles_for(f)
    want = sorted({r for r in roles if r})
    # bpm is fixed here so the fast/slow pairs share one tune; the real tempo goes in the master track
    song = compose(bpm=120, length=length, loop=loop if loop else None, channels=len(want), roles=want,
                   moods=moods, seed=seed, division=48)
    by_role = {}
    for n in song.notes:
        by_role.setdefault(song.roles[n.ch], []).append(n)
    return song, roles, by_role, length, loop


def _mono(notes):
    """Keep one note per onset (highest for lead-like lines) and drop overlaps."""
    out, last = [], None
    for n in sorted(notes, key=lambda n: (n.time, -n.key)):
        if last is not None and n.time == last.time:
            continue
        out.append(n)
        last = n
    return out


def _drum_lines(notes, f, chans):
    """compose() drums use keys 36/38/42/46; give each drum channel one voice mapped to the
    channel's own most-used drum-map slots (kick, snare, hats in order of use)."""
    voices = {36: [], 38: [], 42: [], 46: []}
    for n in notes:
        voices.setdefault(n.key, []).append(n)
    order = [voices[36], voices[38], voices[42] + voices[46]]
    lines = {}
    for k, ch in enumerate(chans):
        slots = f["channels"][ch].get("drum_slots") or [0]
        src = order[k % 3] if len(chans) > 1 else sorted(voices[36] + voices[38] + voices[42], key=lambda n: n.time)
        if k >= 3:   # extra drum channels: sparse accents on their own slots
            src = [n for i, n in enumerate(voices[42]) if i % (4 + k) == 0]
        slot_of = {36: 0, 38: 1, 42: 2, 46: 2}
        lines[ch] = [n._replace(key=slots[min(slot_of.get(n.key, 0) if len(chans) == 1 else (k % len(slots)),
                                               len(slots) - 1)], dur=max(1, n.dur)) for n in _mono(src)]
    return lines


MAX_SONG = 14256   # the largest retail song: the game sizes its song buffers from the ROM table


def write_song(f):
    """Smallest repeat count whose song fits the slot of the retail song (else the buffer)."""
    intro, span = song_span(f)
    if span is None:
        return _write_song(f, None, 1)
    reps = [r for r in range(1, 9) if span % r == 0 and span // r >= 1536 and (span // r) % 48 == 0] or [1]
    best = None
    for r in reps:
        data, song = _write_song(f, span // r, r)
        if len(data) <= f["size"]:
            return data, song
        if len(data) <= MAX_SONG and best is None:
            best = (data, song)
    return best or (data, song)


def _write_song(f, body, reps):
    song, roles, by_role, length, loop = compose_song(f, body)
    nch = f["nch"]
    drum_chans = [i for i, r in enumerate(roles) if r == "drums"]
    lines = _drum_lines(by_role.get("drums", []), f, drum_chans) if drum_chans else {}
    pad_k = 0
    for ch, r in enumerate(roles):
        if r is None or r == "drums":
            continue
        src = by_role.get(r, [])
        if r == "pad":       # one chord tone per pad channel
            groups = {}
            for n in src:
                groups.setdefault(n.time, []).append(n)
            src = [sorted(g, key=lambda n: n.key)[pad_k % len(g)] for g in groups.values()]
            pad_k += 1
        lines[ch] = _fit_register(_mono(src), f["channels"][ch].get("register"))
    # assemble: header, pointer lists, tables, master track, channel streams
    from cleanroom.decomp.gen import h32
    tb = Tables(f, h32("drm64tables", f["name"]))
    hdr_size = 40 + 16
    lists_off = hdr_size
    data_list_off, vol_list_off, pb_list_off = lists_off, lists_off + 4 * nch, lists_off + 8 * nch
    wt_off = lists_off + 12 * nch
    wt = struct.pack(">%dH" % len(tb.wt), *tb.wt)
    drum_off = wt_off + len(wt)
    drum_off += drum_off & 1
    dt = b"".join(struct.pack(">HHBB", *e) for e in tb.drums)
    env_off = drum_off + len(dt)
    env = bytes(tb.env)
    body_off = env_off + len(env)
    body_off = (body_off + 3) & ~3
    bpm = f["tempos"][0] if f["tempos"] else 120
    master = bytes([0x85, min(255, bpm)]) + (bytes([0xaa, f["changefx"]]) if f["changefx"] is not None else b"")
    rep_on, rep_off = (b"\x95" + bytes([reps]), b"\x96") if reps > 1 else (b"", b"")
    if loop is not None:
        master += _rests(loop) if loop else b""
        master += b"\x95\xff\x99" + _rests((length - loop) * reps) + b"\x96"
    else:
        master += _rests(length) + b"\x80"
    streams = [master]
    for ch in range(nch):
        c = f["channels"][ch]
        if c is None:
            streams.append(None)
            continue
        setup = tb.setup(c["setup"])
        drums = setup.pop("drums", None) if roles[ch] == "drums" else None
        setup.pop("drums", None)
        if "volume" not in setup:
            setup["volume"] = [c.get("volume_median", 100)]
        s = _setup_bytes(setup, drums)
        notes = lines.get(ch, [])
        if loop is not None:
            s += _events(notes, 0, loop) if loop else b""
            s += b"\x95\xff\x99" + rep_on + _events(notes, loop, length) + rep_off + b"\x96"
        else:
            s += _events(notes, 0, length) + b"\x80"
        streams.append(s)
    body, offs = b"", []
    for s in streams:
        offs.append(body_off + len(body) if s is not None else 0)
        body += s or b""
    master_off = offs[0]
    data_offs = offs[1:]
    out = bytearray(struct.pack(">Iii", f["ver"], nch, len(f["wave_table"])))
    out += struct.pack(">7I", data_list_off, vol_list_off, pb_list_off, env_off if env else 0,
                       drum_off if dt else 0, wt_off, master_off)
    out += bytes(16)
    out += struct.pack(">%dI" % nch, *data_offs) + bytes(8 * nch)
    out += wt
    out += bytes(drum_off - len(out))
    out += dt + env
    out += bytes(body_off - len(out))
    out += body
    out += bytes((-len(out)) % 16)
    return bytes(out), song


def write_fx(fx, seed=77):
    """New effects: same instrument setup, priority, note count and total length; new pitches
    and rhythm (seeded walks inside the effect's register)."""
    rng = np.random.default_rng(seed)
    neff = fx["neff"]
    head = 24 + 8 * neff
    tb = Tables(dict(wave_table=fx["wave_table"]), seed + 1)
    wt = struct.pack(">%dH" % fx["nw"], *tb.wt)
    datas = []
    for e in fx["effects"]:
        if e is None:
            datas.append(None)
            continue
        s = _setup_bytes(tb.setup({k: v for k, v in e["setup"].items() if k != "drums"}), None)
        n, total = max(1, e["n"]), max(1, e["total"])
        reg = e["register"] or [40, 48, 56]
        lo, hi = reg[0], max(reg[0] + 1, reg[2])
        if reg[2] - reg[0] < 3:     # one-pitch blips: move them off the kept pitch
            off = int(rng.choice([-5, -4, -3, 3, 4, 5]))
            lo, hi = lo + off, hi + off
        cuts = np.sort(rng.choice(np.arange(1, total), size=min(n - 1, total - 1), replace=False)) if total > 1 and n > 1 else []
        bounds = [0] + [int(c) for c in cuts] + [total]
        key = int(rng.integers(lo, hi + 1))
        for a, b in zip(bounds, bounds[1:]):
            key = int(np.clip(key + rng.choice([-5, -3, -2, 2, 3, 4, 7]), lo, hi))
            ln = b - a
            while ln > 0:
                m = min(ln, 0x7fff)
                s += bytes([key]) + _len_bytes(m)
                ln -= m
        s += b"\x95\xff" + bytes([REST]) + _len_bytes(0x7fff) + b"\x96" if e["loop"] else b"\x80"
        datas.append(s)
    body_off = head + len(wt)
    body_off = (body_off + 3) & ~3
    out = bytearray(struct.pack(">iiiIII", fx["ncomp"], neff, fx["nw"], fx["flags"], 0, head))
    body = b""
    for e, s in zip(fx["effects"], datas):
        if s is None:
            out += struct.pack(">Ii", 0, 0)
        else:
            out += struct.pack(">Ii", body_off + len(body), e["priority"])
            body += s
    out += wt
    out += bytes(body_off - len(out))
    out += body
    out += bytes((-len(out)) % 16)
    return bytes(out)


def write_bank(bank, samples):
    """Pointer bank rebuilt from facts (header, tuning, wave headers, book/loop shapes);
    audio.write fills codebooks, loop states and the resynthesised samples."""
    d = bytearray(bank["size"])
    d[0:16] = bytes.fromhex(bank["name"])
    d[16:20] = struct.pack(">I", bank["flags"])
    d[20:32] = bytes.fromhex(bank["wbk"])
    bn, dt, wl = bank["offsets"]
    d[0x20:0x30] = struct.pack(">iIII", len(samples), bn, dt, wl)
    for s, fl in zip(samples, bank["wave_flags"]):
        i = s["i"]
        d[bn + i] = s["basenote"]
        d[dt + 4 * i:dt + 4 * i + 4] = struct.pack(">f", s["detune"])
        d[wl + 4 * i:wl + 4 * i + 4] = struct.pack(">I", s["ptr"])
        d[s["ptr"]:s["ptr"] + 20] = struct.pack(">IIBBxxII", s["base"], s["len"], s["type"], fl,
                                                s["loop_off"], s["book_off"])
        if s.get("loop"):
            d[s["loop_off"]:s["loop_off"] + 12] = struct.pack(">IIi", *s["loop"])
    return d


def write_all(local, out, hook=None):
    import hashlib
    from games.drmario64 import audio
    m = json.load(open(os.path.join(SPEC, "music.json")))
    gate = os.path.join(out, "gate_music")
    os.makedirs(gate, exist_ok=True)
    over = []
    for name, f in m["songs"].items():
        data, _ = write_song(f)
        if len(data) > f["size"]:
            over.append(f"{name} {len(data)}/{f['size']}")
        open(os.path.join(out, name + ".databin.bin"), "wb").write(data)
        to_mid(data, os.path.join(gate, name + ".mid"))
    open(os.path.join(out, "fxbank.databin.bin"), "wb").write(write_fx(m["fx"]))
    samples = json.load(open(os.path.join(SPEC, "samples.json")))
    key = hashlib.sha1(json.dumps(m["bank"]).encode() + open(os.path.join(SPEC, "samples.json"), "rb").read()
                       + open(audio.__file__, "rb").read() + open(__file__, "rb").read()[:0]).hexdigest()[:12]
    cache = os.path.join(local, f"bank_{key}.bin")
    if os.path.exists(cache):
        blob = open(cache, "rb").read()
        ptr, wav = blob[:m["bank"]["size"]], blob[m["bank"]["size"]:]
    else:
        img = write_bank(m["bank"], samples) + bytearray(m["bank"]["wave_size"])
        from games.drmario64 import voices
        audio.write(img, 0, m["bank"]["size"], hook=voices.supplied)
        open(cache, "wb").write(bytes(img))
        ptr, wav = bytes(img[:m["bank"]["size"]]), bytes(img[m["bank"]["size"]:])
    open(os.path.join(out, "n64_ptr_tables_v2.databin.bin"), "wb").write(ptr)
    open(os.path.join(out, "n64_wave_tables.databin.bin"), "wb").write(wav)
    return f"songs {len(m['songs'])} composed" + (f" (over retail size: {over})" if over else "") + \
        f", {m['fx']['neff']} effects, bank {len(samples)} waves"
