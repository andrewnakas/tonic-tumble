"""Text for the originality rebuild: every player-visible string gets our own wording.

DIRTY  extract(dirty, spec, local)
    Retail US strings (one entry per message, lines joined) -> D:/n64work/drmario64/gate/text/retail.json
    (never committed). spec/text_slots.json keeps only structure per string id: message number,
    line index, the message's line count and its widest line (chars). No retail words.
CLEAN  write_overrides(out)
    out/src_override/<decomp path>: copy of the pristine decomp file with each US string replaced by
    our line from text/rewrites.json (by id); strings compiled only for CN/GW become "" so no retail
    wording survives in the override files. out/text_clean.json: every clean string for the gate.

String id = "<decomp path>:<ordinal of the literal in the file>" (all literals counted, preprocessor
lines excluded). The decomp sources are code (MIT); only the strings we replace come from rewrites.json.
"""
import json
import os
import re

from games.drmario64.text_scan import encode, scan

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec")
SRC = os.environ.get("DRM64_SRC", "D:/n64work/drmario64/pristine")
GATE = os.environ.get("DRM64_GATE", "D:/n64work/drmario64/gate/text")
REWRITES = os.path.join(HERE, "text", "rewrites.json")
LABELS = os.path.join(HERE, "tex_labels.json")

MSG_FILES = ["src/main_segment/dm_title_main.msg", "src/main_segment/dm_game_main.msg",
             "src/main_segment/dm_manual_main.msg", "src/main_segment/main_menu.msg",
             "src/main_segment/main_story.msg"]
C_FILES = ["src/main_segment/debug_menu.c"]
TEXTY = re.compile(r"[A-Za-z]{2}|[\u3000-\u9fff\uff00-\uffef]")


def literals(rel):
    """[(id, literal dict)] for every literal in the file, with player-visible text marked."""
    out = []
    for k, s in enumerate(scan(os.path.join(SRC, rel))):
        s["text"] = bool(TEXTY.search(s["value"])) if rel.endswith(".c") else bool(s["value"].strip())
        out.append((f"{rel}:{k}", s))
    return out


def messages(rel, lits, values=None):
    """US text literals grouped per declaration: {decl: [(id, value)]}."""
    msgs = {}
    for i, s in lits:
        if s["us"] and s["text"]:
            msgs.setdefault(s["decl"], []).append((i, values.get(i, s["value"]) if values else s["value"]))
    return msgs


def extract(dirty, spec=SPEC, local=None):
    os.makedirs(GATE, exist_ok=True)
    retail, slots = [], {}
    for rel in MSG_FILES + C_FILES:
        lits = literals(rel)
        for decl, items in messages(rel, lits).items():
            vals = [v for _, v in items]
            if rel.endswith(".msg"):
                retail.append(" ".join(vals))
            else:
                retail += vals
            width = max(len(v) for v in vals)
            for j, (i, v) in enumerate(items):
                slots[i] = {"msg": decl, "line": j, "lines": len(items), "width": width if rel.endswith(".msg") else len(v)}
    # label words baked into textures: the transcription we replaced (kept on the dirty side only)
    old = os.path.join(GATE, "retail_labels.json")
    if os.path.exists(old):
        retail += [w.replace("|", " ") for w in json.load(open(old, encoding="utf8")).values()]
    json.dump(retail, open(os.path.join(GATE, "retail.json"), "w", encoding="utf8"), ensure_ascii=False, indent=0)
    json.dump(slots, open(os.path.join(spec, "text_slots.json"), "w"), indent=0, sort_keys=True)
    return f"text: {len(retail)} retail strings -> {GATE}/retail.json; {len(slots)} slots"


def load_rewrites():
    return json.load(open(REWRITES, encoding="utf8"))


def write_overrides(out):
    rw = load_rewrites()
    clean, nrep, nblank = [], 0, 0
    for rel in MSG_FILES + C_FILES:
        path = os.path.join(SRC, rel)
        text = open(path, encoding="utf8").read()
        lits = literals(rel)
        pieces, pos = [], 0
        for i, s in lits:
            if i in rw:
                new = rw[i]
                nrep += 1
            elif not s["us"] and s["text"]:
                new = ""
                nblank += 1
            else:
                continue
            pieces.append(text[pos:s["start"]])
            pieces.append('"' + encode(new) + '"')
            pos = s["end"]
        pieces.append(text[pos:])
        dst = os.path.join(out, "src_override", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "w", encoding="utf8", newline="\n").write("".join(pieces))
        for decl, items in messages(rel, lits, rw).items():
            vals = [v for _, v in items]
            clean += [" ".join(vals)] if rel.endswith(".msg") else vals
    clean += [w.replace("|", " ") for w in json.load(open(LABELS, encoding="utf8")).values()]
    json.dump(clean, open(os.path.join(out, "text_clean.json"), "w", encoding="utf8"), ensure_ascii=False, indent=0)
    return f"text: {nrep} strings rewritten, {nblank} CN/GW-only strings blanked, {len(clean)} clean strings"


def check(rw=None):
    """Structure check of rewrites against spec/text_slots.json: every slot filled, widths kept,
    Shift-JIS encodable, no control characters smuggled in. Returns a list of problems."""
    rw = rw or load_rewrites()
    slots = json.load(open(os.path.join(SPEC, "text_slots.json")))
    bad = []
    for i, sl in slots.items():
        if i not in rw:
            bad.append(f"missing {i}")
            continue
        v = rw[i]
        is_c = i.split(":")[0].endswith(".c")
        if is_c and ("\n" in v or "\t" in v):
            if len(v) != sl["width"]:      # debug column layouts: same width
                bad.append(f"width changed {i}: {len(v)} != {sl['width']}: {v!r}")
        elif is_c:
            if len(v) > max(16, sl["width"]):   # short debug labels in pointer tables
                bad.append(f"too wide {i}: {len(v)}: {v!r}")
        elif len(v) > sl["width"]:
            bad.append(f"too wide {i}: {len(v)} > {sl['width']}: {v!r}")
        try:
            v.encode("shift_jis")
        except UnicodeEncodeError:
            bad.append(f"not Shift-JIS {i}: {v!r}")
        if ("~" in v and not is_c) or "%" in v:
            bad.append(f"control char {i}: {v!r}")
    for i in rw:
        if i not in slots:
            bad.append(f"unknown id {i}")
    return bad
