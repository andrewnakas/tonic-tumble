"""Registers the drawn (non-default) texture generators with generate.HOOKS."""
import functools
import os

from games.drmario64 import fonts
from games.drmario64 import labels, portraits, stacks, tiles
from games.drmario64.generate import HOOKS, POST_HOOKS

# the decomp source (code facts: font tables, text); pristine tree, no ROM data
SRC = os.environ.get("DRM64_SRC", "D:/n64work/drmario64/pristine")

fonts.E_EXTRA.update({65: ("·", 4)})


@functools.lru_cache(None)
def _font(name):
    if name == "main_segment/font/font_e_tex":
        return fonts.font_e(SRC)[0]
    if name == "main_segment/font/font_e2_tex":
        return fonts.font_e(SRC, two=True)[0]
    if name == "main_segment/font/font_a_tex":
        return fonts.font_jp(SRC)[0]
    if name == "main_segment/font/font_2_tex":
        return fonts.font_jp(SRC, two=True)[0]
    if name == "sDebugPrintFontTex":
        return fonts.debug_font()
    return None


def font_hook(name, d):
    im = _font(name)
    if im is not None:
        assert im.shape[:2] == (d["h"], d["w"]), (name, im.shape, d["w"], d["h"])
    return im


HOOKS.append(font_hook)
HOOKS.append(stacks.render)
HOOKS.append(lambda name, d: tiles.tlut_image(name) if name in tiles.TLUTS else None)


POST_HOOKS.append(lambda name, d, im: None if name in stacks.BY_NAME or name in portraits.LAYOUTS else labels.render(name, im))
POST_HOOKS.append(lambda name, d, im: portraits.render(name, im))
