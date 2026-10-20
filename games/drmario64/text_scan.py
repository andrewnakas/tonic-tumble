"""String-literal scanner for the decomp sources (shared by text.py).

scan(path) -> list of dicts {start, end, raw, value, us, line, decl}
  start/end: byte offsets of the literal (with quotes) in the file text
  raw:   literal body as written (escapes kept)
  value: decoded body (C escapes resolved, \\x.. kept as chars)
  us:    True if the literal sits in code compiled for the US build
         (VERSION_US=1, VERSION_CN=VERSION_GW=0; other conditions count as compiled)
  decl:  ordinal of the enclosing top-level declaration (literals joined by ';')
Preprocessor lines are not scanned (#include/#define strings are never touched).
"""
import re

VERS = {"VERSION_US": 1, "VERSION_CN": 0, "VERSION_GW": 0}


def _eval(expr):
    """1 / 0 for version-only expressions, None if anything else is involved."""
    e = re.sub(r"//.*|/\*.*?\*/", "", expr).strip()
    e = re.sub(r"defined\s*\(?\s*(\w+)\s*\)?", lambda m: m.group(1), e)
    ids = set(re.findall(r"[A-Za-z_]\w*", e))
    if ids - set(VERS):
        return None
    for k, v in VERS.items():
        e = re.sub(r"\b%s\b" % k, str(v), e)
    e = e.replace("&&", " and ").replace("||", " or ").replace("!", " not ")
    try:
        return 1 if eval(e, {"__builtins__": {}}) else 0
    except Exception:
        return None


def scan(path, text=None):
    if text is None:
        text = open(path, encoding="utf8").read()
    out = []
    stack = []   # each: [active_parent, state(1/0/None), taken(bool)]

    def active():
        return all(s[1] != 0 for s in stack)

    i, n, line, decl, depth = 0, len(text), 1, 0, 0
    bol = True
    while i < n:
        c = text[i]
        if bol:
            m = re.match(r"[ \t]*#[ \t]*(\w+)(.*)", text[i:text.find("\n", i) if "\n" in text[i:] else n])
            if m:
                # directive line (with continuation)
                j = i
                while True:
                    k = text.find("\n", j)
                    if k < 0:
                        k = n
                    if text[k - 1:k] == "\\":
                        j = k + 1
                        continue
                    break
                body = text[i:k]
                kw = m.group(1)
                rest = re.sub(r"\\\n", " ", body.split(kw, 1)[1])
                if kw in ("if", "ifdef", "ifndef"):
                    if kw == "if":
                        st = _eval(rest)
                    else:
                        name = rest.strip().split()[0] if rest.strip() else ""
                        st = (VERS[name] if kw == "ifdef" else 1 - VERS[name]) if name in VERS else None
                    stack.append([True, st, st == 1])
                elif kw == "elif" and stack:
                    s = stack[-1]
                    if s[2]:
                        s[1] = 0
                    else:
                        st = _eval(rest)
                        s[1] = st
                        s[2] = st == 1
                elif kw == "else" and stack:
                    s = stack[-1]
                    s[1] = 0 if s[2] else (1 if s[1] == 0 else None)
                    s[2] = True
                elif kw == "endif" and stack:
                    stack.pop()
                line += body.count("\n")
                i = k
                continue
        bol = False
        if c == "\n":
            line += 1
            bol = True
            i += 1
            continue
        if text.startswith("//", i):
            k = text.find("\n", i)
            i = n if k < 0 else k
            continue
        if text.startswith("/*", i):
            k = text.find("*/", i + 2)
            line += text[i:k].count("\n")
            i = n if k < 0 else k + 2
            continue
        if c == "'":
            j = i + 1
            while j < n and text[j] != "'":
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            raw = text[i + 1:j]
            out.append(dict(start=i, end=j + 1, raw=raw, value=decode(raw), us=active(), line=line, decl=decl))
            i = j + 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == ";" and depth == 0:
            decl += 1
        i += 1
    return out


def decode(raw):
    return re.sub(r"\\(x[0-9a-fA-F]{1,2}|[0-7]{1,3}|.)", lambda m: {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "'": "'"}.get(
        m.group(1), chr(int(m.group(1)[1:], 16)) if m.group(1)[0] == "x" else (chr(int(m.group(1), 8)) if m.group(1)[0].isdigit() else m.group(1))), raw)


def encode(value):
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
