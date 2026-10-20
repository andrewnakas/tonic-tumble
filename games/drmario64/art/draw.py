"""CLEAN ROOM: drawing helpers for the Tonic Tumble art (supersampled PIL canvases)."""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SS = 4
INK = (34, 26, 48)          # outline colour used everywhere


def h32(*parts):
    h = 2166136261
    for ch in "|".join(map(str, parts)).encode():
        h = ((h ^ ch) * 16777619) & 0xFFFFFFFF
    return h


def rng(*parts):
    return np.random.default_rng(h32(*parts))


class Canvas:
    """RGBA canvas at SS x resolution; coordinates are in output pixels (floats)."""

    def __init__(self, w, h, bg=(0, 0, 0, 0), ss=SS):
        self.w, self.h, self.ss = w, h, ss
        self.im = Image.new("RGBA", (w * ss, h * ss), tuple(bg) if len(bg) == 4 else tuple(bg) + (255,))
        self.d = ImageDraw.Draw(self.im)

    def _p(self, pts):
        return [(x * self.ss, y * self.ss) for x, y in pts]

    def ellipse(self, cx, cy, rx, ry, fill, outline=INK, width=1.0):
        box = [(cx - rx) * self.ss, (cy - ry) * self.ss, (cx + rx) * self.ss, (cy + ry) * self.ss]
        self.d.ellipse(box, fill=_c(fill), outline=_c(outline) if outline else None,
                       width=max(1, int(width * self.ss)) if outline else 0)

    def rect(self, x0, y0, x1, y1, fill, outline=INK, width=1.0, r=0):
        box = [x0 * self.ss, y0 * self.ss, x1 * self.ss, y1 * self.ss]
        self.d.rounded_rectangle(box, radius=r * self.ss, fill=_c(fill), outline=_c(outline) if outline else None,
                                 width=max(1, int(width * self.ss)) if outline else 0)

    def poly(self, pts, fill, outline=INK, width=1.0):
        self.d.polygon(self._p(pts), fill=_c(fill))
        if outline:
            p = self._p(pts)
            self.d.line(p + [p[0]], fill=_c(outline), width=max(1, int(width * self.ss)), joint="curve")

    def line(self, pts, fill=INK, width=1.0):
        self.d.line(self._p(pts), fill=_c(fill), width=max(1, int(width * self.ss)), joint="curve")

    def arc(self, cx, cy, rx, ry, a0, a1, fill=INK, width=1.0):
        box = [(cx - rx) * self.ss, (cy - ry) * self.ss, (cx + rx) * self.ss, (cy + ry) * self.ss]
        self.d.arc(box, a0, a1, fill=_c(fill), width=max(1, int(width * self.ss)))

    def text(self, xy, s, font, fill, anchor="mm"):
        self.d.text((xy[0] * self.ss, xy[1] * self.ss), s, font=font, fill=_c(fill), anchor=anchor)

    def array(self):
        """(h, w, 4) uint8, box-downsampled, colour premultiplied by coverage."""
        a = np.asarray(self.im, np.float32)
        H, W = self.h, self.w
        a = a.reshape(H, self.ss, W, self.ss, 4)
        al = a[..., 3:4]
        rgb = (a[..., :3] * al).sum((1, 3)) / np.maximum(al.sum((1, 3)), 1e-6)
        alpha = al.mean((1, 3))
        return np.clip(np.concatenate([rgb, alpha], -1), 0, 255).astype(np.uint8)


def _c(c):
    if c is None:
        return None
    c = tuple(int(v) for v in c)
    return c if len(c) == 4 else c + (255,)


def shade(c, k):
    """k < 1 darker, k > 1 lighter (towards white)."""
    c = np.asarray(c[:3], np.float32)
    if k <= 1:
        out = c * k
    else:
        out = c + (255 - c) * (k - 1)
    return tuple(int(v) for v in np.clip(out, 0, 255))


def mix(a, b, t):
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a[:3], b[:3]))


def vgrad(h, w, top, bottom):
    t = np.linspace(0, 1, h)[:, None, None]
    return np.asarray(top, np.float32) * (1 - t) + np.asarray(bottom, np.float32) * t + np.zeros((h, w, 3))


def to_rgba(rgb, a=None):
    h, w = rgb.shape[:2]
    out = np.zeros((h, w, 4), np.uint8)
    out[..., :3] = np.clip(rgb, 0, 255)
    out[..., 3] = 255 if a is None else np.clip(a, 0, 255)
    return out


def binarise(im, thr=128):
    im = im.copy()
    m = im[..., 3] >= thr
    im[..., 3] = np.where(m, 255, 0)
    return im


def smooth_noise(w, h, scale, seed, octaves=3):
    r = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        gw, gh = max(2, int(w / scale) + 2), max(2, int(h / scale) + 2)
        g = r.random((gh, gw)).astype(np.float32)
        im = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += amp * np.asarray(im, np.float32) / 255
        tot += amp
        amp *= 0.5
        scale = max(1.0, scale / 2)
    return out / tot


def star(cx, cy, r0, r1, n, rot=0.0):
    pts = []
    for k in range(2 * n):
        a = rot + math.pi * k / n
        r = r0 if k % 2 == 0 else r1
        pts.append((cx + r * math.sin(a), cy - r * math.cos(a)))
    return pts


def blur(arr, r):
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(r)), np.float32)
