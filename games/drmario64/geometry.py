"""Vertex arrays for the compiled build (2026-10 originality rebuild).

The decomp's asset C files (src/assets/**) hold the display lists: which vertex array is
loaded into which vertex-buffer slots and the triangle index lists (a mesh may stitch two
arrays together). The vertex arrays themselves (bin/us/assets/**/*.vtx.inc.c) are retail
data, so they are regenerated here.

Kept facts (spec/geometry.json): vertex count per array; per connected object (vertices
joined by the decomp's triangles) whether it is a flat axis-aligned sprite card (4
vertices) and, for cards, the box rounded to 2 units, the plane, which corner each vertex
sits on and which UV corner it maps to; for real meshes only the box rounded to 8 units.
UV boxes are rounded to whole texels (32), vertex colours to 64 levels, alpha to 4 levels.
Triangle order comes from the decomp source at build time.

Exemption: sprite cards are generic layout rectangles (a textured rectangle has no shape of
its own); they are rebuilt from the rounded box and are not part of the geometry gate.
Every real mesh gets a new shape: a spectral embedding of its own triangle graph (the low
Laplacian eigenvectors place each vertex from connectivity alone), restyled as a rounded,
flat-topped "pebble" volume turned a quarter turn about the vertical axis, fitted inside
the rounded box. UVs are a planar projection of the new shape onto the UV box; colours
come from a fixed light on the new normals.

    extract(dirty, spec, local)  DIRTY: spec/geometry.json + retail meshes in <gate>/geo
    write(local, out)            CLEAN: out/assets/<rel>.vtx.inc.c + out/geo clean meshes
    check(out)                   counts and triangle indices of the written arrays
"""
import json
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec")
SRC = os.environ.get("DRM64_SRC", "D:/n64work/drmario64/pristine")
GATE = os.environ.get("DRM64_GATE", "D:/n64work/drmario64/gate")
C_FILES = ["src/assets/title/title_all.c", "src/assets/coffee/coffee01.c", "src/assets/menu_bg/menu_bg.c",
           "src/assets/menu_bg/menu_bg2.c", "src/assets/game_etc/etc_lws.c"]
VTX_RE = re.compile(r"\{\{\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\},\s*(-?\d+),\s*\{\s*(-?\d+),\s*(-?\d+)\s*\},"
                    r"\s*\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}\}\}")


# ------------------------------------------------------------------ decomp source (topology)
def _calls(text):
    out = []
    for m in re.finditer(r"\b(gs\w+)\(", text):
        i, depth = m.end(), 1
        while depth:
            depth += (text[i] == "(") - (text[i] == ")")
            i += 1
        out.append((m.group(1), [a.strip() for a in re.split(r",(?![^(]*\))", text[m.end():i - 1])]))
    return out


def topology(src=SRC):
    """(arrays [rel, ...] in DL order, tris [[(rel, i), (rel, i), (rel, i)], ...]) from the decomp DLs."""
    arrays, tris = [], []
    for cf in C_FILES:
        text = open(os.path.join(src, cf), encoding="utf8").read()
        sym2path = dict(re.findall(r"Vtx (\w+)\[\] = \{\s*#include \"assets/([^\"]+)\.vtx\.inc\.c\"", text))
        slots, tex, scale = {}, None, (1.0, 1.0)
        for name, args in _calls(text):
            if name == "gsSPTexture":
                try:
                    scale = tuple(max(int(x, 0), 1) / 65536.0 for x in args[:2])
                except ValueError:
                    scale = (1.0, 1.0)
            elif name.startswith("gsDPLoadTextureBlock") or name.startswith("gsDPLoadTextureTile"):
                try:
                    tex = (int(args[2], 0), int(args[3], 0)) if name.endswith("_4b") else (int(args[3], 0), int(args[4], 0))
                    texsym = args[0].strip()
                except (ValueError, IndexError):
                    tex = None
            elif name == "gsSPVertex":
                sym = args[0].lstrip("&").split("[")[0].strip()
                base = int(args[0].split("[")[1].rstrip("]")) if "[" in args[0] else 0
                n, v0 = int(args[1], 0), int(args[2], 0)
                p = sym2path[sym]
                if p not in arrays:
                    arrays.append(p)
                for k in range(n):
                    slots[v0 + k] = (p, base + k)
            elif name in ("gsSP1Triangle", "gsSP2Triangles"):
                idx = [int(a, 0) for a in args]
                for g in [idx[0:3]] + ([idx[4:7]] if name == "gsSP2Triangles" else []):
                    tris.append([slots[v] for v in g])
                    for v in g:
                        if tex:   # UV units covering the texture once: texels * 32 / gsSPTexture scale
                            VTEX.setdefault(slots[v], (tex[0] * 32 / scale[0], tex[1] * 32 / scale[1]))
                            VTEXSYM.setdefault(slots[v], texsym)
    return arrays, tris


VTEXSYM = {}  # (rel, index) -> texture symbol bound when its first triangle is drawn
VTEX = {}   # (rel, index) -> UV extent (s, t) of the texture its first triangle is drawn with (decomp DLs)


def objects(nodes, tris):
    parent = {v: v for v in nodes}

    def f(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, c in tris:
        parent[f(a)] = f(b)
        parent[f(b)] = f(c)
    comp = {}
    for v in nodes:
        comp.setdefault(f(v), []).append(v)
    return list(comp.values())


# ------------------------------------------------------------------ vtx files
def read_vtx(path):
    return [tuple(int(x) for x in m.groups()) for m in VTX_RE.finditer(open(path).read())]


def fmt_vtx(rows):
    return "".join("    {{{ %5d, %5d, %5d }, %d, { %5d, %5d }, { %3d, %3d, %3d, %3d }}},\n" % r for r in rows)


def _rnd(x, q):
    return (np.round(np.asarray(x, np.float64) / q) * q).astype(int).tolist()


def _rect(p):
    """4 points forming a rectangle in any plane -> (i, k, l, j) with i the origin corner,
    k/l its neighbours, j opposite; else None."""
    if len(p) != 4:
        return None
    for i, j in ((0, 1), (0, 2), (0, 3)):
        k, l = [x for x in range(4) if x not in (i, j)]
        if np.abs(p[i] + p[j] - p[k] - p[l]).max() <= 1.5 and \
                abs(np.linalg.norm(p[i] - p[j]) - np.linalg.norm(p[k] - p[l])) <= 2.0:
            return i, k, l, j
    return None


def _key(comp):
    return f"{comp[0][0]}__{comp[0][1]}"


def _plane_area(p2, tris):
    s = 0.0
    for a, b, c in tris:
        s += (p2[b, 0] - p2[a, 0]) * (p2[c, 1] - p2[a, 1]) - (p2[c, 0] - p2[a, 0]) * (p2[b, 1] - p2[a, 1])
    return s


# ------------------------------------------------------------------ dirty side
def extract(dirty, spec=SPEC, local=None):
    src = dirty if os.path.isdir(os.path.join(dirty, "src", "assets")) else SRC
    arrays, tris = topology(src)
    root = os.path.join(dirty, "bin", "us", "assets")
    rows = {rel: read_vtx(os.path.join(root, rel + ".vtx.inc.c")) for rel in arrays}
    nodes = [(rel, i) for rel in arrays for i in range(len(rows[rel]))]
    comps = sorted(objects(nodes, tris), key=lambda c: (arrays.index(c[0][0]), c[0][1]))
    tri_of = {}
    for t in tris:
        tri_of.setdefault(t[0], []).append(t)
    facts = {"arrays": {rel: len(rows[rel]) for rel in arrays}, "objects": []}
    count = {"rect": 0, "flat": 0, "mesh": 0}
    os.makedirs(os.path.join(GATE, "geo"), exist_ok=True)
    for comp in comps:
        comp = sorted(comp, key=lambda v: (arrays.index(v[0]), v[1]))
        r = [rows[rel][i] for rel, i in comp]
        p = np.asarray([x[:3] for x in r], float)
        uv = np.asarray([x[4:6] for x in r], float)
        idx = {v: k for k, v in enumerate(comp)}
        ct = [[idx[x] for x in t] for v in comp for t in tri_of.get(v, [])]
        o = {"v": [[rel, i] for rel, i in comp],
             "uvbox": _rnd([uv[:, 0].min(), uv[:, 1].min(), uv[:, 0].max(), uv[:, 1].max()], 32),
             "col": _rnd([x[6:9] for x in r], 64), "alpha": _rnd([x[9] for x in r], 85)}
        rect = _rect(p)
        flat = [ax for ax in range(3) if np.ptp(p[:, ax]) == 0]
        if rect:
            i, k, l, j = rect
            code = {i: (0, 0), k: (1, 0), l: (0, 1), j: (1, 1)}
            o["rect"] = {"o": _rnd(p[i], 2), "ea": _rnd(p[k] - p[i], 2), "eb": _rnd(p[l] - p[i], 2),
                         "corner": [code[n] for n in range(4)],
                         "uvcorner": [[int(uv[n, 0] == uv[:, 0].max()), int(uv[n, 1] == uv[:, 1].max())] for n in range(4)]}
            # texture placement: uv = c + sa*du + sb*dv over the card's corners (keeps flips/turns)
            S = np.asarray([[1, *code[n]] for n in range(4)], float)
            sol = np.linalg.lstsq(S, uv, rcond=None)[0]
            o["rect"]["uv"] = [_rnd(sol[0], 8), _rnd(sol[1], 8), _rnd(sol[2], 8)]
            count["rect"] += 1
        elif flat and len(comp) >= 3 and ct:
            ax = flat[0]
            a, b = [q for q in range(3) if q != ax]
            p2 = p[:, [a, b]]
            orient = []
            for col in (0, 1):
                cor = [np.corrcoef(p2[:, m], uv[:, col])[0, 1] if np.ptp(p2[:, m]) and np.ptp(uv[:, col]) else 0
                       for m in (0, 1)]
                m = int(np.argmax(np.abs(cor)))
                orient.append([m, 1 if cor[m] >= 0 else -1])
            o["flat"] = {"axis": ax, "const": _rnd(p[0, ax], 2),
                         "box": _rnd([p2[:, 0].min(), p2[:, 1].min(), p2[:, 0].max(), p2[:, 1].max()], 8),
                         "wind": 1 if _plane_area(p2, ct) >= 0 else -1, "uv": orient}
            # texture placement: affine uv = c + M (a, b) (keeps the sprite's turn/flip on its card)
            S = np.concatenate([np.ones((len(p2), 1)), p2], 1)
            sol = np.linalg.lstsq(S, uv, rcond=None)[0]
            M = sol[1:].T
            if abs(np.linalg.det(M)) > 1e-3:
                o["flat"]["uvm"] = [[round(float(x) * 4) / 4 for x in row] for row in M]
                o["flat"]["uvc"] = _rnd(sol[0], 8)
            count["flat"] += 1
        else:
            o["box"] = [_rnd(p.min(0), 8), _rnd(p.max(0), 8)]
            if ct:
                count["mesh"] += 1
                g = os.path.join(GATE, "geo", _key(comp) + ".json")
                os.makedirs(os.path.dirname(g), exist_ok=True)
                json.dump({"verts": p.tolist(), "tris": ct}, open(g, "w"))
        facts["objects"].append(o)
    json.dump(facts, open(os.path.join(spec, "geometry.json"), "w"), separators=(",", ":"))
    return (f"geometry: {len(arrays)} arrays, {len(nodes)} vertices; {count['rect']} rectangle cards, "
            f"{count['flat']} flat cut-outs (rebuilt as cards), {count['mesh']} meshes (retail -> {GATE}/geo)")


# ------------------------------------------------------------------ clean side
def _boundary_cycle(nv, tris):
    cnt = {}
    for t in tris:
        for x, y in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            e = (min(x, y), max(x, y))
            cnt[e] = cnt.get(e, 0) + 1
    edges = [e for e, c in cnt.items() if c == 1]
    adj = {}
    for x, y in edges:
        adj.setdefault(x, []).append(y)
        adj.setdefault(y, []).append(x)
    if not adj or any(len(v) != 2 for v in adj.values()):
        return None
    start = min(adj)
    cyc, prev, cur = [start], None, start
    while True:
        nxt = [y for y in adj[cur] if y != prev][0]
        if nxt == start:
            break
        cyc.append(nxt)
        prev, cur = cur, nxt
        if len(cyc) > nv:
            return None
    return cyc if len(cyc) == len(adj) else None


def _tutte(nv, tris, cyc, corners):
    """Boundary cycle spread round a quadrilateral (corners on the cycle's quarter points),
    interior vertices at the average of their neighbours."""
    if len(corners) == 4 and not hasattr(corners[0], "__len__"):
        x0, y0, x1, y1 = corners
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    x0, y0 = np.min(corners, 0)
    x1, y1 = np.max(corners, 0)
    m = len(cyc)
    q = [round(k * m / 4) for k in range(4)] + [m]
    pos = np.zeros((nv, 2))
    fixed = np.zeros(nv, bool)
    for s in range(4):
        a, b = q[s], q[s + 1]
        ca, cb = np.array(corners[s], float), np.array(corners[(s + 1) % 4], float)
        for k in range(a, b):
            t = (k - a) / max(b - a, 1)
            pos[cyc[k]] = ca + t * (cb - ca)
            fixed[cyc[k]] = True
    nb = [set() for _ in range(nv)]
    for t in tris:
        for x, y in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            nb[x].add(y)
            nb[y].add(x)
    free = [v for v in range(nv) if not fixed[v]]
    if free:
        ix = {v: n for n, v in enumerate(free)}
        A = np.zeros((len(free), len(free)))
        B = np.zeros((len(free), 2))
        for v in free:
            A[ix[v], ix[v]] = max(len(nb[v]), 1)
            for w in nb[v]:
                if fixed[w]:
                    B[ix[v]] += pos[w]
                else:
                    A[ix[v], ix[w]] -= 1
            if not nb[v]:
                B[ix[v]] = [(x0 + x1) / 2, (y0 + y1) / 2]
        sol = np.linalg.lstsq(A, B, rcond=None)[0]
        pos[free] = sol
    return pos


def _embed(nv, tris, seed):
    """Positions in [-1, 1]^3 from the triangle graph alone (Laplacian eigenmap) + our styling."""
    rng = np.random.default_rng(seed)
    if nv <= 3 or not tris:
        ang = np.arange(nv) * 2 * np.pi / max(nv, 1) + seed
        return np.stack([np.cos(ang), np.sin(ang), np.zeros(nv)], 1)
    A = np.zeros((nv, nv))
    for a, b, c in tris:
        for x, y in ((a, b), (b, c), (c, a)):
            A[x, y] = A[y, x] = 1
    deg = A.sum(1)
    deg[deg == 0] = 1
    L = np.eye(nv) - A / np.sqrt(deg[:, None] * deg[None, :])
    _, vec = np.linalg.eigh(L)
    e = np.zeros((nv, 3))
    k = min(3, nv - 1)
    e[:, :k] = vec[:, 1:1 + k]
    e -= e.mean(0)
    s = np.abs(e).max(0)
    s[s < 1e-9] = 1
    e /= s
    r = np.linalg.norm(e, axis=1, keepdims=True)
    r[r < 1e-9] = 1
    shell = e / r * (0.6 + 0.4 * np.clip(r, 0, 1))
    shell[:, 1] *= np.where(shell[:, 1] > 0, 0.7, 1.0)
    ang = np.pi / 2 + 0.3 * np.sin(seed)
    c, s_ = np.cos(ang), np.sin(ang)
    shell[:, 0], shell[:, 2] = shell[:, 0] * c - shell[:, 2] * s_, shell[:, 0] * s_ + shell[:, 2] * c
    out = shell + rng.uniform(-0.05, 0.05, shell.shape)
    out -= (out.max(0) + out.min(0)) / 2
    sc = np.abs(out).max(0)
    sc[sc < 1e-9] = 1
    return out / sc


def _blades(nv, tris, lo, hi, seed):
    """Objects made of loose triangles (tufts, spikes): vertices used by several triangles
    or listed first are roots on a wavy line along the long horizontal axis (ordered by the
    graph's Fiedler vector); the others are tips raised and leaning. Up is +Y."""
    rng = np.random.default_rng(seed)
    use = np.zeros(nv, int)
    for t in tris:
        use[list(t)] += 1
    tip = np.zeros(nv, bool)
    for t in tris:
        if not any(tip[v] for v in t):
            cand = [v for v in t if use[v] == 1]
            tip[cand[-1] if cand else t[2]] = True
    A = np.zeros((nv, nv))
    for a, b, c in tris:
        for x, y in ((a, b), (b, c), (c, a)):
            A[x, y] = A[y, x] = 1
    A += 0.05                                           # keeps loose pieces in one ordering
    L = np.diag(A.sum(1)) - A
    f = np.linalg.eigh(L)[1][:, 1]
    order = np.argsort(np.argsort(f + 1e-6 * np.arange(nv))) / max(nv - 1, 1)
    ext = np.maximum(hi - lo, 1.0)
    h = [0, 2] if ext[0] >= ext[2] else [2, 0]        # long, depth horizontal axes
    p = np.zeros((nv, 3))
    p[:, h[0]] = lo[h[0]] + order * ext[h[0]]
    p[:, h[1]] = (lo[h[1]] + hi[h[1]]) / 2 + 0.4 * ext[h[1]] * np.sin(2 * np.pi * 1.5 * order + seed)
    p[:, 1] = lo[1]
    for t in tris:
        base = [v for v in t if not tip[v]]
        for v in t:
            if tip[v] and base:
                p[v] = p[base].mean(0)
                p[v, h[0]] += rng.uniform(-0.06, 0.06) * ext[h[0]]
                p[v, 1] = lo[1] + max(ext[1], 0.25 * ext[h[0]]) * rng.uniform(0.55, 1.0)
    return np.round(p)


def _normals(p, tris):
    nrm = np.zeros_like(p)
    for a, b, c in tris:
        nrm[[a, b, c]] += np.cross(p[b] - p[a], p[c] - p[a])
    ln = np.linalg.norm(nrm, axis=1, keepdims=True)
    ln[ln < 1e-9] = 1
    return nrm / ln


def _shade(o, i, g=None):
    if g is None:
        return tuple(min(255, x) for x in o["col"][i])
    return (g, g, g)


def _flat_mapped(f, comp, ct, cyc, o, uvbox, stats):
    """Flat cut-out rebuilt as a card: the preimage of its texture region (uv box, clamped
    to the bound texture) under the kept affine texture placement; vertices spread over it."""
    ax = f["axis"]
    a, b = [q for q in range(3) if q != ax]
    M, c = np.asarray(f["uvm"], float), np.asarray(f["uvc"], float)
    u0, v0, u1, v1 = uvbox
    tex = VTEX.get(comp[0])
    if tex:
        u0, u1 = max(u0, 0), min(u1, round(tex[0]))
        v0, v1 = max(v0, 0), min(v1, round(tex[1]))
        if u1 <= u0 or v1 <= v0:
            u0, v0, u1, v1 = 0, 0, round(tex[0]), round(tex[1])
    Mi = np.linalg.inv(M)
    cuv = np.array([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], float)
    corners = (cuv - c) @ Mi.T
    if cyc is None:
        stats["fallback"] += 1
        e = (_embed(len(comp), ct, len(comp))[:, :2] + 1) / 2
        p2 = corners[0] + e[:, :1] * (corners[1] - corners[0]) + e[:, 1:] * (corners[3] - corners[0])
    else:
        p2 = _tutte(len(comp), ct, cyc, corners)
        if (_plane_area(p2, ct) >= 0) != (f["wind"] >= 0):
            p2 = _tutte(len(comp), ct, cyc[::-1], corners)
    p2 = np.round(p2)
    uv = np.round(c + p2 @ M.T)
    uv[:, 0] = np.clip(uv[:, 0], u0, u1)
    uv[:, 1] = np.clip(uv[:, 1], v0, v1)
    out = []
    for n in range(len(comp)):
        pos = [0, 0, 0]
        pos[ax], pos[a], pos[b] = f["const"], int(p2[n, 0]), int(p2[n, 1])
        out.append((*pos, 0, int(uv[n, 0]), int(uv[n, 1]), *_shade(o, n), min(255, o["alpha"][n])))
    return out


def build(facts, tris):
    rows = {rel: [None] * n for rel, n in facts["arrays"].items()}
    tri_of = {}
    for t in tris:
        tri_of.setdefault(tuple(t[0]), []).append(t)
    meshes, stats = {}, {"fallback": 0}
    for oi, o in enumerate(facts["objects"]):
        comp = [tuple(v) for v in o["v"]]
        u0, v0, u1, v1 = o["uvbox"]
        idx = {v: n for n, v in enumerate(comp)}
        ct = [[idx[tuple(x)] for x in t] for v in comp for t in tri_of.get(v, [])]
        if "rect" in o:
            k = o["rect"]
            org, ea, eb = (np.asarray(k[x], float) for x in ("o", "ea", "eb"))
            for n, (rel, vi) in enumerate(comp):
                sa, sb = k["corner"][n]
                pos = np.round(org + sa * ea + sb * eb).astype(int)
                if "uv" in k:
                    c_, du, dv = (np.asarray(x, float) for x in k["uv"])
                    uv = np.round(c_ + sa * du + sb * dv).astype(int).tolist()
                else:
                    uv = [u1 if k["uvcorner"][n][0] else u0, v1 if k["uvcorner"][n][1] else v0]
                rows[rel][vi] = (*pos.tolist(), 0, *uv, *_shade(o, n), min(255, o["alpha"][n]))
            continue
        if "flat" in o:
            f = o["flat"]
            ax = f["axis"]
            a, b = [q for q in range(3) if q != ax]
            box = f["box"]
            cyc = _boundary_cycle(len(comp), ct)
            if "uvm" in f:
                rows_ = _flat_mapped(f, comp, ct, cyc, o, (u0, v0, u1, v1), stats)
                for n, (rel, vi) in enumerate(comp):
                    rows[rel][vi] = rows_[n]
                continue
            if cyc is None:
                stats["fallback"] += 1
                e = _embed(len(comp), ct, oi)[:, :2]
                p2 = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]) + e * \
                    np.array([(box[2] - box[0]) / 2, (box[3] - box[1]) / 2])
            else:
                p2 = _tutte(len(comp), ct, cyc, box)
                if (_plane_area(p2, ct) >= 0) != (f["wind"] >= 0):
                    p2 = _tutte(len(comp), ct, cyc[::-1], box)
            p2 = np.round(p2)
            span = np.maximum([box[2] - box[0], box[3] - box[1]], 1)
            t = (p2 - [box[0], box[1]]) / span
            for n, (rel, vi) in enumerate(comp):
                pos = [0, 0, 0]
                pos[ax], pos[a], pos[b] = f["const"], int(p2[n, 0]), int(p2[n, 1])
                uv = []
                for col, (m, sg) in enumerate(f["uv"]):
                    tt = t[n, m] if sg > 0 else 1 - t[n, m]
                    lo_, hi_ = (u0, u1) if col == 0 else (v0, v1)
                    uv.append(int(round(lo_ + tt * (hi_ - lo_))))
                rows[rel][vi] = (*pos, 0, *uv, *_shade(o, n), min(255, o["alpha"][n]))
            continue
        lo, hi = np.asarray(o["box"][0], float), np.asarray(o["box"][1], float)
        seed = (sum(map(ord, comp[0][0])) * 131 + comp[0][1] * 7 + oi) % 100003
        if _boundary_cycle(len(comp), ct) is None and ct:
            p = _blades(len(comp), ct, lo, hi, seed)        # loose triangles: our own tuft layout
        else:
            e = _embed(len(comp), ct, seed)
            ctr, half = (lo + hi) / 2, np.maximum((hi - lo) / 2, 1.0)
            half = np.maximum(half, 0.22 * half.max())    # styling: no paper-thin slabs, chunky pieces
            p = np.round(ctr + e * half * 0.92)
        light = np.clip(_normals(p, ct) @ np.array([0.35, 0.8, 0.45]), -1, 1) * 0.35 + 0.65
        axes = np.argsort(-np.ptp(p, axis=0))[:2]
        span = np.maximum(np.ptp(p[:, axes], axis=0), 1)
        t = (p[:, axes] - p[:, axes].min(0)) / span
        for n, (rel, vi) in enumerate(comp):
            g = int(np.clip(40 + 200 * light[n], 0, 255))
            rows[rel][vi] = (int(p[n, 0]), int(p[n, 1]), int(p[n, 2]), 0, int(round(u0 + t[n, 0] * (u1 - u0))),
                             int(round(v0 + t[n, 1] * (v1 - v0))), *_shade(o, n, g), min(255, o["alpha"][n]))
        if ct:
            meshes[_key(comp)] = {"verts": p.tolist(), "tris": ct}
    return rows, meshes, stats


def write(local, out):
    facts = json.load(open(os.path.join(SPEC, "geometry.json")))
    _, tris = topology(SRC)
    rows, meshes, _ = build(facts, tris)
    json.dump(orientation(rows), open(os.path.join(out, "tex_orient.json"), "w"), indent=0, sort_keys=True)
    for rel, r in rows.items():
        assert all(x is not None for x in r), rel
        p = os.path.join(out, "assets", rel + ".vtx.inc.c")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(fmt_vtx(r))
    for key, m in meshes.items():
        g = os.path.join(out, "geo", key + ".json")
        os.makedirs(os.path.dirname(g), exist_ok=True)
        json.dump(m, open(g, "w"))
    return len(rows)


def orientation(rows):
    """{texture symbol: {"flip_u", "flip_v"}} as the title/menu cameras show them: flip_v when
    texture rows run bottom-to-top on screen (v grows with +Y), flip_u when u runs right-to-left.
    For the art generators: draw such textures mirrored so they read upright in game."""
    acc = {}
    for rel, r in rows.items():
        for i, row in enumerate(r):
            sym = VTEXSYM.get((rel, i))
            if sym:
                acc.setdefault(sym, []).append(row)
    out = {}
    for sym, rs in acc.items():
        a = np.asarray(rs, float)
        if len(a) < 3 or np.ptp(a[:, 2]) > max(np.ptp(a[:, 0]), np.ptp(a[:, 1])):
            continue
        S = np.concatenate([np.ones((len(a), 1)), a[:, :2]], 1)
        sol = np.linalg.lstsq(S, a[:, 4:6], rcond=None)[0]
        out[sym] = {"flip_u": bool(sol[1, 0] < 0), "flip_v": bool(sol[2, 1] > 0)}
    return out


def check(out):
    facts = json.load(open(os.path.join(SPEC, "geometry.json")))
    _, tris = topology(SRC)
    n = {rel: len(read_vtx(os.path.join(out, "assets", rel + ".vtx.inc.c"))) for rel in facts["arrays"]}
    bad = [rel for rel, k in facts["arrays"].items() if n[rel] != k]
    bad += [str(t) for t in tris if any(v[1] >= n[v[0]] for v in t)]
    return bad

