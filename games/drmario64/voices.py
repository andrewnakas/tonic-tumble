"""Voice lines for Dr. Mario 64 on top of cleanroom.voice.voices (Piper placeholders).

    python -m games.drmario64.voices build     # speak every line in voice_lines.json into games/drmario64/voices/
    python -m games.drmario64.voices check

Slots are libmus waves ("wave<index>"): length and nominal rate from spec/samples.json.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["CLEANROOM_GAME"] = HERE

from cleanroom.voice import voices as V  # noqa: E402


def _slots():
    return {f"wave{d['i']}": d for d in json.load(open(os.path.join(HERE, "spec", "samples.json")))}


V.HERE = HERE
V.CACHE = os.path.join(HERE, "voices")
V.WORK = os.path.join(V.CACHE, "_raw")
V.slots = _slots
V._name = lambda p: p


def supplied(d):
    """audio.write hook: our voice take for a slot, or None."""
    return V.cached(f"wave{d['i']}")


if __name__ == "__main__":
    {"build": lambda: V.build(sys.argv[2:] or None), "check": V.check}[sys.argv[1]]()
