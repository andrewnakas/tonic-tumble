"""CLEAN ROOM: original Tonic Tumble characters, drawn procedurally and animated by frame index.

Every anime set (sprite size and frame count are structural facts from the decomp) gets one
of our own characters. Sprites stand on the bottom row (the game's anchor table puts the
anchor at the bottom centre). Each set shares one 16-colour TLUT (256 for the hero), so a
character keeps to a small palette: outline, body ramp, accent ramp, belly, white, black.
"""
import math

import numpy as np

from games.drmario64.art.draw import INK, Canvas, mix, shade, star

# anime set -> character (select-grid order of the decomp's CHARANIMEMODE enum)
SETS = {"m": "Dr. Fenna", "n": "Grudge", "h": "Prickle", "i": "Loom", "j": "Satin", "d": "Pomme",
        "e": "Wobble", "f": "Inko", "a": "Rotor", "b": "Clod", "c": "Anvil-Bot", "g": "Prof. Murk",
        "k": "Jinx", "l": "Night Grudge", "o": "Chrome Fenna", "mario": "Dr. Fenna"}

WHITE, BLACK = (252, 250, 240), (30, 24, 40)

DESIGNS = {
    "Prickle":   dict(shape="bean", body=(96, 186, 92), belly=(200, 236, 150), acc=(250, 120, 170), feat=["spikes", "flower"], eyes="dot"),
    "Loom":      dict(shape="round", body=(186, 150, 220), belly=(240, 222, 250), acc=(250, 190, 90), feat=["yarn", "needles"], eyes="big"),
    "Satin":     dict(shape="seg", body=(246, 230, 150), belly=(255, 250, 220), acc=(130, 200, 230), feat=["moth"], eyes="big"),
    "Pomme":     dict(shape="apple", body=(226, 64, 70), belly=(255, 170, 160), acc=(90, 170, 70), feat=["leaf"], eyes="dot"),
    "Wobble":    dict(shape="dome", body=(250, 160, 70), belly=(255, 220, 170), acc=(255, 240, 120), feat=["drips"], eyes="big"),
    "Inko":      dict(shape="squid", body=(110, 140, 200), belly=(190, 210, 240), acc=(240, 110, 120), feat=["tentacles"], eyes="big"),
    "Rotor":     dict(shape="round", body=(70, 150, 230), belly=(230, 240, 255), acc=(255, 200, 40), feat=["propeller", "beak", "wings"], eyes="dot"),
    "Clod":      dict(shape="rock", body=(196, 168, 120), belly=(230, 210, 170), acc=(120, 170, 90), feat=["moss"], eyes="mono"),
    "Anvil-Bot": dict(shape="box", body=(200, 70, 60), belly=(200, 205, 215), acc=(250, 210, 60), feat=["antenna", "bolts"], eyes="visor"),
    "Prof. Murk": dict(shape="frog", body=(90, 150, 80), belly=(220, 230, 160), acc=(60, 50, 80), feat=["tophat", "monocle"], eyes="big"),
    "Jinx":      dict(shape="cat", body=(60, 56, 80), belly=(150, 140, 180), acc=(250, 200, 60), feat=["ears", "bell", "wand"], eyes="big"),
}
HUMANS = {
    "Dr. Fenna":    dict(skin=(250, 206, 168), hair=(40, 160, 160), coat=(248, 248, 244), acc=(255, 140, 60), legs=(60, 70, 110)),
    "Chrome Fenna": dict(skin=(200, 208, 220), hair=(120, 130, 150), coat=(225, 230, 238), acc=(150, 170, 200), legs=(90, 96, 110)),
    "Grudge":       dict(skin=(236, 190, 150), hair=(210, 50, 40), coat=(40, 40, 52), acc=(250, 220, 60), legs=(70, 50, 90), rival=True),
    "Night Grudge": dict(skin=(190, 196, 236), hair=(70, 60, 140), coat=(30, 30, 60), acc=(200, 40, 70), legs=(40, 30, 70), rival=True, cape=True),
}


def pose(f, n):
    """Five actions spread over the set (idle, hop, cheer, slump, surprise) with a cycle each."""
    act = min(4, f * 5 // max(1, n))
    start = (act * n + 4) // 5
    ph = (f - start) / max(1, (n // 5))
    s = math.sin(2 * math.pi * ph)
    p = dict(act=act, bob=0.0, arm=0.0, eyes="open", mouth="smile", squash=1.0, lean=0.0)
    if act == 0:
        p.update(bob=0.5 * s, arm=0.25 * s, eyes="closed" if (f % 7) == 3 else "open")
    elif act == 1:
        p.update(bob=-abs(s) * 3.0, squash=1.0 + 0.08 * math.cos(2 * math.pi * ph), arm=0.6, mouth="grin")
    elif act == 2:
        p.update(arm=1.0, bob=-abs(s) * 1.5, mouth="grin", eyes="happy", lean=0.15 * s)
    elif act == 3:
        p.update(arm=-0.8, squash=0.94, eyes="closed", mouth="frown", lean=0.1 * s)
    else:
        p.update(arm=0.8 * s, eyes="wide", mouth="o", bob=-0.6 * abs(s))
    return p


# ------------------------------------------------------------------ faces
def eyes(cv, cx, cy, sep, r, style, mood):
    if style == "visor":
        cv.rect(cx - sep - r, cy - r * 0.7, cx + sep + r, cy + r * 0.7, (40, 220, 230), width=0.8, r=r * 0.5)
        if mood != "closed":
            cv.rect(cx - sep * 0.6, cy - r * 0.35, cx - sep * 0.6 + r, cy + r * 0.2, WHITE, outline=None)
        return
    if style == "mono":
        cv.ellipse(cx, cy, r * 1.3, r * 1.3 if mood != "closed" else r * 0.3, WHITE, width=0.8)
        if mood != "closed":
            cv.ellipse(cx + 0.3, cy + 0.3, r * 0.6, r * 0.6, BLACK, outline=None)
        return
    for sx in (-1, 1):
        x = cx + sx * sep
        if mood == "closed":
            cv.arc(x, cy, r, r * 0.7, 200, 340, INK, 0.9)
        elif mood == "happy":
            cv.arc(x, cy + r * 0.4, r, r * 0.9, 200, 340, INK, 1.0)
        else:
            rr = r * (1.3 if mood == "wide" else 1.0)
            if style == "big":
                cv.ellipse(x, cy, rr, rr * 1.15, WHITE, width=0.7)
                cv.ellipse(x + 0.2 * sx, cy + 0.2, rr * 0.55, rr * 0.65, BLACK, outline=None)
                cv.ellipse(x + 0.2 * sx - rr * 0.2, cy - rr * 0.3, rr * 0.2, rr * 0.2, WHITE, outline=None)
            else:
                cv.ellipse(x, cy, rr * 0.55, rr * 0.7, BLACK, outline=None)
                cv.ellipse(x - rr * 0.15, cy - rr * 0.25, rr * 0.18, rr * 0.18, WHITE, outline=None)


def mouth(cv, cx, cy, w, kind, inside=(200, 60, 80)):
    if kind == "smile":
        cv.arc(cx, cy - w * 0.4, w, w * 0.7, 30, 150, INK, 0.9)
    elif kind == "grin":
        cv.poly([(cx - w, cy - w * 0.2), (cx + w, cy - w * 0.2), (cx, cy + w * 0.8)], inside, width=0.8)
    elif kind == "frown":
        cv.arc(cx, cy + w * 0.5, w * 0.8, w * 0.6, 210, 330, INK, 0.9)
    else:
        cv.ellipse(cx, cy + w * 0.1, w * 0.45, w * 0.55, inside, width=0.8)


# ------------------------------------------------------------------ creatures
def creature(cv, w, h, d, p, seed=0):
    S = min(w, h * 0.95)
    sq = p["squash"]
    base = h - 1.0 + p["bob"] * 0  # feet stay on the ground; body bobs
    cx = w / 2 + p["lean"] * S * 0.3
    body_h = S * 0.62 * sq
    body_w = S * 0.36 / max(sq, 0.8)
    cy = base - S * 0.08 - body_h / 2 + p["bob"]
    B, L, A = d["body"], d["belly"], d["acc"]
    shape, feat = d["shape"], d["feat"]
    # feet
    if shape not in ("squid", "dome", "seg"):
        for sx in (-1, 1):
            cv.ellipse(cx + sx * body_w * 0.5, base - S * 0.05, S * 0.11, S * 0.06, shade(B, 0.7), width=0.8)
    # back features
    if "wings" in feat:
        flap = p["arm"]
        for sx in (-1, 1):
            cv.poly([(cx + sx * body_w * 0.8, cy), (cx + sx * body_w * 1.7, cy - S * 0.15 - flap * S * 0.1),
                     (cx + sx * body_w * 1.4, cy + S * 0.12)], shade(B, 1.25), width=0.8)
    if "moth" in feat:
        for sx in (-1, 1):
            cv.ellipse(cx + sx * body_w * 1.1, cy - body_h * 0.25 - p["arm"] * 2, body_w * 0.75, body_h * 0.35,
                       shade(A, 1.2), width=0.8)
            cv.ellipse(cx + sx * body_w * 1.1, cy - body_h * 0.25 - p["arm"] * 2, body_w * 0.3, body_h * 0.12,
                       shade(A, 0.8), outline=None)
    if "tentacles" in feat:
        for k in range(5):
            t = (k - 2) / 2
            sway = math.sin(k + p["arm"] * 2) * S * 0.04
            x0 = cx + t * body_w * 0.8
            cv.line([(x0, cy + body_h * 0.2), (x0 + sway + t * S * 0.08, base - S * 0.08), (x0 + sway * 2 + t * S * 0.12, base - 1)],
                    INK, 2.6)
            cv.line([(x0, cy + body_h * 0.2), (x0 + sway + t * S * 0.08, base - S * 0.08), (x0 + sway * 2 + t * S * 0.12, base - 1)],
                    shade(B, 0.85), 1.4)
    # body
    if shape == "round" or shape == "frog":
        cv.ellipse(cx, cy, body_w * 1.15, body_h * 0.55, B, width=1.0)
        cv.ellipse(cx, cy + body_h * 0.12, body_w * 0.75, body_h * 0.36, L, outline=None)
    elif shape == "bean":
        cv.rect(cx - body_w, cy - body_h * 0.6, cx + body_w, cy + body_h * 0.5, B, r=body_w, width=1.0)
        cv.rect(cx - body_w * 0.55, cy - body_h * 0.1, cx + body_w * 0.55, cy + body_h * 0.42, L, outline=None, r=body_w * 0.5)
    elif shape == "box":
        cv.rect(cx - body_w * 1.1, cy - body_h * 0.55, cx + body_w * 1.1, cy + body_h * 0.5, B, r=2, width=1.0)
        cv.rect(cx - body_w * 0.7, cy + body_h * 0.02, cx + body_w * 0.7, cy + body_h * 0.4, L, r=1, width=0.7)
    elif shape == "dome":
        cv.poly([(cx - body_w * 1.3, base - 1)] + [(cx + body_w * 1.3 * math.cos(a), cy + body_h * 0.1 - body_h * 0.6 * math.sin(a))
                                                   for a in np.linspace(math.pi, 0, 14)] + [(cx + body_w * 1.3, base - 1)], B, width=1.0)
        cv.ellipse(cx - body_w * 0.5, cy - body_h * 0.2, body_w * 0.35, body_h * 0.12, shade(B, 1.4), outline=None)
    elif shape == "squid":
        cv.poly([(cx, cy - body_h * 0.7), (cx + body_w * 1.1, cy - body_h * 0.05), (cx + body_w * 0.9, cy + body_h * 0.25),
                 (cx - body_w * 0.9, cy + body_h * 0.25), (cx - body_w * 1.1, cy - body_h * 0.05)], B, width=1.0)
    elif shape == "apple":
        cv.ellipse(cx - body_w * 0.45, cy, body_w * 0.8, body_h * 0.5, B, width=1.0)
        cv.ellipse(cx + body_w * 0.45, cy, body_w * 0.8, body_h * 0.5, B, width=1.0)
        cv.ellipse(cx, cy + 1, body_w * 0.9, body_h * 0.45, B, outline=None)
        cv.ellipse(cx - body_w * 0.5, cy - body_h * 0.22, body_w * 0.2, body_h * 0.1, shade(B, 1.5), outline=None)
    elif shape == "rock":
        r = np.random.default_rng(seed)
        pts = [(cx + body_w * (1.15 + 0.15 * r.random()) * math.cos(a), cy + body_h * (0.5 + 0.06 * r.random()) * math.sin(a))
               for a in np.linspace(0, 2 * math.pi, 9)[:-1]]
        cv.poly(pts, B, width=1.0)
        cv.poly([(x * 0.6 + cx * 0.4, y * 0.6 + (cy + body_h * 0.1) * 0.4) for x, y in pts], L, outline=None)
    elif shape == "seg":
        for k in range(3):
            cv.ellipse(cx + (k - 1) * body_w * 0.15, base - S * 0.1 - k * body_h * 0.3 + p["bob"] * k * 0.5,
                       body_w * (1.0 - 0.1 * k), body_h * 0.22, B if k % 2 == 0 else L, width=0.9)
        cy = base - S * 0.1 - 2.4 * body_h * 0.3 + p["bob"]
    elif shape == "cat":
        cv.ellipse(cx, cy + body_h * 0.1, body_w * 1.0, body_h * 0.5, B, width=1.0)
        cv.ellipse(cx, cy + body_h * 0.2, body_w * 0.55, body_h * 0.3, L, outline=None)
        tail = p["arm"]
        cv.line([(cx + body_w * 0.9, cy + body_h * 0.3), (cx + body_w * 1.6, cy - tail * S * 0.1),
                 (cx + body_w * 1.4, cy - body_h * 0.4)], INK, 2.8)
        cv.line([(cx + body_w * 0.9, cy + body_h * 0.3), (cx + body_w * 1.6, cy - tail * S * 0.1),
                 (cx + body_w * 1.4, cy - body_h * 0.4)], B, 1.6)
    # arms
    if shape not in ("squid", "dome", "seg", "apple"):
        for sx in (-1, 1):
            ang = (0.3 + 0.9 * p["arm"]) * sx
            x0, y0 = cx + sx * body_w * 1.0, cy + body_h * 0.05
            x1, y1 = x0 + sx * S * 0.12 * math.cos(ang * 0.8), y0 - S * 0.14 * math.sin(abs(ang))
            cv.line([(x0, y0), (x1, y1)], INK, 2.4)
            cv.line([(x0, y0), (x1, y1)], shade(B, 0.9), 1.2)
            cv.ellipse(x1, y1, S * 0.045, S * 0.045, shade(B, 1.1), width=0.7)
    # head features + face
    top = cy - body_h * 0.55
    fy = cy - body_h * 0.12 if shape not in ("squid",) else cy - body_h * 0.05
    if shape == "frog":
        for sx in (-1, 1):
            cv.ellipse(cx + sx * body_w * 0.55, top + body_h * 0.02, body_w * 0.42, body_w * 0.42, B, width=1.0)
        fy = top + body_h * 0.02
    if "spikes" in feat:
        for k in range(6):
            t = (k - 2.5) / 2.5
            x = cx + t * body_w * 0.9
            y = top + body_h * 0.08 + abs(t) * body_h * 0.25
            cv.poly([(x - 1.2, y + 1), (x + t * 2, y - S * 0.07), (x + 1.2, y + 1)], shade(B, 1.3), width=0.6)
    if "flower" in feat:
        fx, fyy = cx + body_w * 0.3, top + 1
        for k in range(5):
            a = 2 * math.pi * k / 5 + p["arm"]
            cv.ellipse(fx + math.cos(a) * S * 0.05, fyy + math.sin(a) * S * 0.05, S * 0.04, S * 0.04, A, width=0.5)
        cv.ellipse(fx, fyy, S * 0.03, S * 0.03, (255, 230, 90), outline=None)
    if "leaf" in feat:
        cv.line([(cx, top + body_h * 0.05), (cx + 1, top - S * 0.06)], (110, 70, 40), 1.4)
        cv.ellipse(cx + S * 0.07, top - S * 0.05, S * 0.08, S * 0.035, A, width=0.7)
    if "drips" in feat:
        for k in (-1, 0.4):
            cv.ellipse(cx + k * body_w, base - S * 0.12, S * 0.03, S * 0.05, shade(B, 1.2), outline=None)
    if "propeller" in feat:
        cv.line([(cx, top + 1), (cx, top - S * 0.08)], INK, 1.2)
        spin = p["arm"] + p["bob"]
        cv.ellipse(cx + S * 0.1 * math.cos(spin), top - S * 0.09, S * 0.12 * abs(math.cos(spin)) + 1, S * 0.035, A, width=0.6)
    if "antenna" in feat:
        cv.line([(cx, top + 1), (cx + p["lean"] * 4, top - S * 0.1)], INK, 1.2)
        cv.ellipse(cx + p["lean"] * 4, top - S * 0.11, S * 0.04, S * 0.04, A, width=0.6)
    if "ears" in feat:
        for sx in (-1, 1):
            cv.poly([(cx + sx * body_w * 0.25, top + body_h * 0.12), (cx + sx * body_w * 0.75, top - S * 0.08),
                     (cx + sx * body_w * 0.95, top + body_h * 0.2)], B, width=0.9)
    if "tophat" in feat:
        cv.rect(cx - body_w * 0.55, top - S * 0.2, cx + body_w * 0.55, top - S * 0.02, A, r=0.5, width=0.8)
        cv.rect(cx - body_w * 0.85, top - S * 0.04, cx + body_w * 0.85, top + S * 0.0, A, r=0.5, width=0.8)
        cv.rect(cx - body_w * 0.55, top - S * 0.08, cx + body_w * 0.55, top - S * 0.05, (200, 60, 70), outline=None)
    if "yarn" in feat:
        yx, yy = cx - body_w * 1.2, base - S * 0.1
        cv.ellipse(yx, yy, S * 0.08, S * 0.08, A, width=0.7)
        cv.arc(yx, yy, S * 0.05, S * 0.08, 0, 180, shade(A, 0.7), 0.6)
    if "needles" in feat:
        cv.line([(cx - body_w * 0.6, top + 2), (cx - body_w * 1.1, top - S * 0.1)], (180, 120, 70), 1.0)
        cv.line([(cx + body_w * 0.6, top + 2), (cx + body_w * 1.1, top - S * 0.1)], (180, 120, 70), 1.0)
    er = max(1.4, S * 0.07)
    eyes(cv, cx, fy, body_w * 0.42, er, d["eyes"], p["eyes"])
    if "monocle" in feat and p["eyes"] != "closed":
        cv.ellipse(cx + body_w * 0.42, fy, er * 1.6, er * 1.6, None, outline=(230, 190, 60), width=0.7)
    if "beak" in feat:
        cv.poly([(cx - S * 0.05, fy + er * 1.2), (cx + S * 0.05, fy + er * 1.2), (cx, fy + er * 2.6)], A, width=0.7)
    else:
        mouth(cv, cx, fy + er * 2.0, max(1.2, S * 0.06), p["mouth"])
    if "bolts" in feat:
        for sx in (-1, 1):
            cv.ellipse(cx + sx * body_w * 1.1, cy - body_h * 0.2, S * 0.035, S * 0.035, (190, 190, 200), width=0.5)
    if "bell" in feat:
        cv.ellipse(cx, cy + body_h * 0.12, S * 0.045, S * 0.045, A, width=0.6)
    if "wand" in feat:
        x1 = cx - body_w * 1.6
        y1 = cy - body_h * 0.2 - p["arm"] * S * 0.1
        cv.line([(cx - body_w * 1.0, cy + body_h * 0.05), (x1, y1)], (120, 80, 40), 1.0)
        cv.poly(star(x1, y1, S * 0.08, S * 0.035, 5, p["arm"]), A, width=0.5)
    if "moss" in feat:
        cv.ellipse(cx - body_w * 0.4, top + body_h * 0.1, body_w * 0.35, S * 0.04, A, outline=None)


# ------------------------------------------------------------------ humans (doctor and rival)
def human(cv, w, h, d, p, hero_scale=1.0):
    S = min(w * 1.25, h * 0.98)
    base = h - 1.0
    cx = w / 2 + p["lean"] * S * 0.2
    sq = p["squash"]
    head_r = S * 0.17
    leg_h = S * 0.2
    torso_h = S * 0.33 * sq
    hip = base - leg_h + p["bob"] * 0.3
    sh = hip - torso_h + p["bob"]
    hy = sh - head_r * 0.85
    coat, skin, hair, acc = d["coat"], d["skin"], d["hair"], d["acc"]
    if d.get("cape"):
        cv.poly([(cx - S * 0.12, sh), (cx + S * 0.12, sh), (cx + S * 0.3 + p["arm"] * 2, base - 2),
                 (cx - S * 0.3 - p["arm"] * 2, base - 2)], (140, 20, 50), width=0.9)
    # legs
    for sx in (-1, 1):
        step = p["arm"] * sx * S * 0.03 if p["act"] == 1 else 0
        cv.rect(cx + sx * S * 0.07 - S * 0.04 + step, hip - 1, cx + sx * S * 0.07 + S * 0.04 + step, base - S * 0.04,
                d["legs"], width=0.8, r=1)
        cv.ellipse(cx + sx * S * 0.08 + step, base - S * 0.035, S * 0.07, S * 0.04, BLACK if not d.get("rival") else acc, width=0.7)
    # torso / coat
    flare = S * 0.05
    cv.poly([(cx - S * 0.12, sh), (cx + S * 0.12, sh), (cx + S * 0.14 + flare, hip + S * 0.04),
             (cx - S * 0.14 - flare, hip + S * 0.04)], coat, width=1.0)
    if d.get("rival"):
        cv.line([(cx - S * 0.12, sh + S * 0.08), (cx + S * 0.12, sh + S * 0.16)], acc, 1.3)  # sash
    else:
        cv.line([(cx, sh + 1), (cx, hip + S * 0.03)], shade(coat, 0.75), 0.8)
        cv.rect(cx + S * 0.03, sh + S * 0.07, cx + S * 0.08, sh + S * 0.12, (120, 200, 220), width=0.5)  # pocket
        cv.poly([(cx - S * 0.07, sh), (cx + S * 0.07, sh), (cx, sh + S * 0.07)], acc, width=0.6)  # scarf knot
    # arms
    for sx in (-1, 1):
        a = p["arm"] if sx > 0 else (p["arm"] if p["act"] == 2 else -0.3 * p["arm"])
        x0, y0 = cx + sx * S * 0.12, sh + S * 0.04
        ex, ey = x0 + sx * S * 0.09, y0 + S * 0.1 - a * S * 0.14
        hx, hy2 = ex + sx * S * 0.04, ey + S * 0.08 - a * S * 0.2
        cv.line([(x0, y0), (ex, ey), (hx, hy2)], INK, S * 0.09 + 1.2)
        cv.line([(x0, y0), (ex, ey), (hx, hy2)], coat, S * 0.09)
        cv.ellipse(hx, hy2, S * 0.04, S * 0.04, skin, width=0.6)
        if sx > 0 and not d.get("rival"):      # the doctor holds a capsule
            cv.rect(hx - S * 0.02, hy2 - S * 0.09, hx + S * 0.035, hy2 - S * 0.01, (240, 80, 90), width=0.6, r=S * 0.025)
    # head
    cv.ellipse(cx, hy, head_r * 0.95, head_r, skin, width=1.0)
    if d.get("rival"):        # spiky swept hair, goggles on the forehead
        pts = [(cx - head_r, hy - head_r * 0.1)]
        for k in range(6):
            t = k / 5
            pts.append((cx - head_r + 2 * head_r * t + head_r * 0.25, hy - head_r * (1.5 if k % 2 == 0 else 0.9)))
        pts.append((cx + head_r, hy - head_r * 0.2))
        cv.poly(pts, hair, width=0.9)
        cv.rect(cx - head_r * 0.8, hy - head_r * 0.55, cx + head_r * 0.8, hy - head_r * 0.2, (90, 200, 230), width=0.7, r=1)
    else:                     # bob cut with a bun
        cv.ellipse(cx, hy - head_r * 1.05, head_r * 0.45, head_r * 0.4, hair, width=0.9)
        cv.poly([(cx - head_r * 1.05, hy + head_r * 0.4), (cx - head_r * 0.95, hy - head_r * 0.7),
                 (cx, hy - head_r * 1.05), (cx + head_r * 0.95, hy - head_r * 0.7), (cx + head_r * 1.05, hy + head_r * 0.4),
                 (cx + head_r * 0.6, hy - head_r * 0.3), (cx - head_r * 0.6, hy - head_r * 0.3)], hair, width=0.9)
    er = max(1.2, head_r * 0.2)
    eyes(cv, cx, hy + head_r * 0.1, head_r * 0.38, er, "big" if S > 40 else "dot", p["eyes"])
    if not d.get("rival"):    # round glasses
        for sx in (-1, 1):
            cv.ellipse(cx + sx * head_r * 0.38, hy + head_r * 0.1, er * 1.7, er * 1.7, None, outline=(60, 60, 80), width=0.6)
    mouth(cv, cx, hy + head_r * 0.6, max(1.0, head_r * 0.25), p["mouth"])


def draw(char, w, h, f, n, seed=0):
    cv = Canvas(w, h)
    p = pose(f, n)
    if char in HUMANS:
        human(cv, w, h, HUMANS[char], p)
    else:
        creature(cv, w, h, DESIGNS[char], p, seed)
    return cv.array()


def portrait(char, w, h, bg=None):
    """Head-and-shoulders card: the character drawn large and cropped to the top."""
    big = draw(char, w * 2, int(h * 2.4), 0, 5)
    H, W = big.shape[:2]
    from PIL import Image
    crop = Image.fromarray(big).crop((W // 2 - w, 0, W // 2 + w, int(h * 2))).resize((w, h), Image.LANCZOS)
    im = np.asarray(crop, np.float32)
    bgc = np.asarray(bg or card_colour(char), np.float32)
    t = np.linspace(0, 1, h)[:, None, None]
    back = bgc * (1.1 - 0.25 * t)
    a = im[..., 3:4] / 255
    return np.clip(im[..., :3] * a + back * (1 - a), 0, 255)


def card_colour(char):
    if char in HUMANS:
        return shade(HUMANS[char]["acc"], 1.35)
    if char in DESIGNS:
        return shade(DESIGNS[char]["belly"], 1.1)
    return (150, 150, 160)


# ------------------------------------------------------------------ viruses (germ mascots) and smog
GERM = {"r": (236, 70, 80), "y": (250, 200, 50), "b": (70, 120, 240)}


def germ(kind, w, h, f, n):
    """r: spiky sun-germ with one eye; y: square jelly with antenna; b: three-lobed blob."""
    cv = Canvas(w, h)
    c = GERM[kind]
    ph = 2 * math.pi * f / max(1, n)
    cx, cy = w / 2, h / 2 + math.sin(ph) * 1.0
    r = min(w, h) * 0.34
    if kind == "r":
        cv.poly(star(cx, cy, r * 1.25, r * 0.85, 9, ph * 0.3), c, width=1.0)
        cv.ellipse(cx, cy, r * 0.75, r * 0.75, shade(c, 1.25), outline=None)
        cv.ellipse(cx, cy - 1, r * 0.45, r * 0.45 * (0.2 if f % 5 == 4 else 1), WHITE, width=0.8)
        cv.ellipse(cx + math.sin(ph) * 1.5, cy - 1, r * 0.2, r * 0.2, BLACK, outline=None)
    elif kind == "y":
        sq = 1 + 0.08 * math.sin(ph * 2)
        cv.line([(cx, cy - r * sq), (cx + math.sin(ph) * 3, cy - r * 1.6)], INK, 1.0)
        cv.ellipse(cx + math.sin(ph) * 3, cy - r * 1.6, 2.0, 2.0, shade(c, 0.8), width=0.6)
        cv.rect(cx - r / sq, cy - r * sq, cx + r / sq, cy + r * 0.9, c, r=r * 0.45, width=1.0)
        for sx in (-1, 1):
            cv.rect(cx + sx * r * 0.35 - 1.2, cy - r * 0.3, cx + sx * r * 0.35 + 1.2, cy + r * 0.1, BLACK, outline=None, r=1)
        cv.line([(cx - r * 0.3, cy + r * 0.45), (cx + r * 0.3, cy + r * 0.45)], INK, 1.0)
    else:
        for k in range(3):
            a = ph * 0.2 + 2 * math.pi * k / 3 - math.pi / 2
            cv.ellipse(cx + math.cos(a) * r * 0.5, cy + math.sin(a) * r * 0.5, r * 0.62, r * 0.62, c, width=1.0)
        cv.ellipse(cx, cy, r * 0.62, r * 0.62, c, outline=None)
        for k in range(3):
            a = 2 * math.pi * k / 3 - math.pi / 2
            cv.ellipse(cx + math.cos(a) * r * 0.42, cy + math.sin(a) * r * 0.42, 1.8, 1.8, WHITE, width=0.5)
    return cv.array()


def smog(w, h, f, n):
    """Intensity puffs that grow and fade."""
    t = f / max(1, n - 1)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    out = np.zeros((h, w), np.float32)
    for k in range(5):
        a = 2 * math.pi * k / 5 + 0.7
        rr = (0.15 + 0.35 * t) * min(w, h)
        x, y = w / 2 + math.cos(a) * rr * 0.8, h / 2 + math.sin(a) * rr * 0.8
        out = np.maximum(out, np.clip(1 - np.hypot(xx - x, yy - y) / (rr * 0.7 + 2), 0, 1))
    out *= (1.0 - 0.7 * t)
    v = np.clip(out * 330, 0, 255)
    return np.stack([v, v, v, v], -1).astype(np.uint8)
