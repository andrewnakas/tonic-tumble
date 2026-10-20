"""Practice pack for recording the voice lines (PERSONAL USE: reads the user's own ROM extraction,
writes outside the repo, never published). Same layout as cleanroom.voice.practice, so
cleanroom.voice.takes can cut the recordings.

    python -m games.drmario64.practice <dirty uncompressed baserom> <out dir>
"""
import json
import os
import struct
import sys
import wave

import numpy as np

from cleanroom.audio import vadpcm
from games.drmario64 import audio

HERE = os.path.dirname(os.path.abspath(__file__))
HZ = 22050


def main(argv):
    rom, out = open(argv[1], "rb").read(), argv[2]
    lay = json.load(open(os.path.join(HERE, "spec", "layout.json")))
    ptr, wv = lay["ptr_tables"], lay["wave_tables"]
    waves = {f"wave{w['i']}": w for w in audio.parse(rom, ptr)}
    L = [(k, v) for k, v in json.load(open(os.path.join(HERE, "voice_lines.json"), encoding="utf-8")).items() if not k.startswith("_")]
    os.makedirs(os.path.join(out, "clips"), exist_ok=True)

    def wr(path, x):
        with wave.open(path, "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(HZ)
            f.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())

    beep = (0.2 * np.sin(2 * np.pi * 880 * np.arange(int(0.08 * HZ)) / HZ)).astype(np.float32)
    tracks, lines = {}, ["Voice practice script: record in this order, 2-3 takes each, in character.",
                         "Play practice_<character>_call_and_response.wav and speak after each beep.", ""]
    for i, (k, v) in enumerate(L, 1):
        w = waves[k]
        raw = rom[wv + w["base"]:wv + w["base"] + w["len"]]
        b = struct.unpack(">%dh" % (w["order"] * w["npred"] * 8), rom[ptr + w["book_off"] + 8:ptr + w["book_off"] + 8 + w["order"] * w["npred"] * 16])
        x = vadpcm.decode(raw, {"order": w["order"], "npred": w["npred"], "book": list(b)}, audio.nsamples(w)).astype(np.float32) / 32768
        wr(os.path.join(out, "clips", f"{i:02d}_{k}.wav"), x)
        gap = np.zeros(int((len(x) / HZ * 1.5 + 1.5) * HZ), np.float32)
        tracks.setdefault(v["who"], []).extend([x, np.zeros(int(0.3 * HZ), np.float32), beep, gap])
        lines.append(f"{i:02d}  {v['who']:8s} {k:8s} max {len(x) / HZ:.2f}s  \"{v['text']}\"")
    for who, parts in tracks.items():
        wr(os.path.join(out, f"practice_{who}_call_and_response.wav"), np.concatenate(parts))
    lines += ["", "Put your recordings (one WAV per character, same order) in <out>/takes/ and tell Claude;",
              "they replace the Piper placeholders (games/drmario64/voices/wave*.wav) after trimming and the studio chain.",
              "These clips come from your own ROM: practice only, do not share or commit them."]
    open(os.path.join(out, "SCRIPT.txt"), "w", encoding="utf8").write("\n".join(lines))
    print(f"practice pack: {len(L)} clips, tracks {sorted(tracks)} -> {out}")


if __name__ == "__main__":
    main(sys.argv)
