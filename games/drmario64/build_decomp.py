"""CLEAN ROOM: compile the Dr. Mario 64 decomp (AngheloAlf/drmario64, MIT) into a ROM.

    python -m games.drmario64.build_decomp <decomp src> <assets dir> <out dir> [-j 2]

Code comes only from the decomp's C/asm sources, compiled with a modern mips64-elf GCC
(the decomp's "modern" flags: -march=vr4300 -mfix4300 -mabi=32; non-matching build:
KMC GCC 2.7.2 is Linux/mac only), so the program bytes differ from retail.
<assets dir> is a bin/us-shaped tree written by our generators (PNG textures,
vtx .inc.c, databins, rsp); nothing is read from the retail ROM here. Any decomp source
file can be replaced by <assets dir>/src_override/<same path> (our rewritten text).

Tools (override with env vars): mips64-elf gcc/ld/objcopy, pigment64, slinky-cli, and
the decomp's own python helpers (msg_reencoder, inc_from_bin, checksummer, rom_compressor).
"""
import argparse
import concurrent.futures as cf
import os
import re
import shutil
import subprocess
import sys

MIPS = os.environ.get("MIPS_PREFIX", r"C:/Users/andre/.local/mips64/bin/mips64-elf-")
TOOLS = {
    "gcc": MIPS + "gcc.exe",
    "ld": MIPS + "ld.exe",
    "objcopy": MIPS + "objcopy.exe",
    "pigment64": os.environ.get("PIGMENT64", r"D:/n64work/drmario64/tools_bin/bin/pigment64.exe"),
    "slinky": os.environ.get("SLINKY", r"D:/n64work/drmario64/tools_bin/bin/slinky-cli.exe"),
}
V = "us"
DEFS = ["-DVERSION_US=1", "-DSCOMMON_IN_COMMON=1", "-DNON_MATCHING", "-DPRESERVE_UB", "-DBUILD_VERSION=8",
        "-D_MIPS_SZLONG=32", "-D__USE_ISOC99", "-DNDEBUG", "-D_FINALROM", "-DF3DEX_GBI_2",
        "-DAVOID_DOUBLE_LIT_PROMOTION=1", "-DMODERN_CC"]
ARCH = ["-G0", "-EB", "-march=vr4300", "-mfix4300", "-mabi=32", "-mno-abicalls", "-fno-PIC", "-mdivide-breaks",
        "-mno-gpopt"]
CFLAGS = ARCH + ["-O2", "-nostdinc", "-ffreestanding", "-fno-builtin", "-funsigned-char", "-std=gnu89", "-w",
                 "-fno-zero-initialized-in-bss", "-fno-toplevel-reorder", "-fno-strict-aliasing", "-fwrapv",
                 "-fno-stack-protector", "-fno-tree-loop-distribute-patterns", "-fno-aggressive-loop-optimizations",
                 "-fno-delete-null-pointer-checks", "-fno-isolate-erroneous-paths-dereference", "-fno-asynchronous-unwind-tables",
                 "-Wno-incompatible-pointer-types", "-Wno-int-conversion", "-Wno-implicit-function-declaration",
                 "-Wno-implicit-int", "-Wno-return-mismatch"]
ASFLAGS = ARCH + ["-x", "assembler-with-cpp", "-D_LANGUAGE_ASSEMBLY", "-DMIPSEB", "-D_ULTRA64", "-D_MIPS_SIM=1",
                  "-nostdinc"]


# Portability patches for the non-matching build (code, not content). Each is (old, new) text.
PATCHES = {
    # The game switches stereo/mono by overwriting two instructions of libultra's
    # alEnvmixerPull at fixed offsets (+0x10C, +0x2EC) of the KMC-compiled function. In our
    # build those offsets hold other instructions, so the write corrupted the mixer. Keep
    # the (default) stereo path and drop the self-modifying write.
    "src/main_segment/audio/sound.c": [(
        "#if VERSION_US || VERSION_GW\n    if (setStereo) {",
        "#if 0\n    if (setStereo) {")],
    # Internal ROM name (20 chars, space padded): our title instead of the original one. GLideN64 keyed its
    # per-game settings on the old name; ports/ejs/patch_core.py re-keys that ini section to the new name.
    "src/rom_header/rom_header.c": [(
        '"DR.MARIO 64         "',
        '"TONIC TUMBLE        "')],
}


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode:
        raise RuntimeError(f"{' '.join(map(str, cmd))[:300]}\n{r.stderr.decode(errors='replace')[:3000]}")
    return r.stdout


class Build:
    def __init__(self, src, assets, out, jobs=2):
        self.src, self.assets, self.out, self.jobs = src, assets, out, jobs
        self.bd = os.path.join(out, "build", V)
        self.compat = os.path.join(out, "compat")
        self.inc = ["-I" + self.compat] + ["-I" + os.path.join(src, p) for p in
                    ("lib/ultralib/include", "lib/ultralib/include/PR", "lib/libmus/include",
                     "lib/ultralib/include/gcc", "include")]
        self.inc += ["-I" + assets, "-I" + os.path.join(self.bd, "bin", V), "-I" + self.bd, "-I" + out, "-I" + src]

    def path(self, rel):
        """Source lookup: our override tree first, then the decomp."""
        o = os.path.join(self.assets, "src_override", rel)
        return o if os.path.exists(o) else os.path.join(self.src, rel)

    # ------------------------------------------------------------ compile
    def cc(self, rel, obj):
        src = self.path(rel)
        if rel in PATCHES:
            text = open(src, encoding="utf8").read()
            for old, new in PATCHES[rel]:
                assert old in text, (rel, old[:60])
                text = text.replace(old, new)
            src = obj[:-2] + ".patched.c"
            open(src, "w", encoding="utf8").write(text)
        d = os.path.dirname(rel)
        inc = self.inc + ["-I" + os.path.join(self.src, d), "-I" + os.path.join(self.bd, d)]
        if rel.startswith("lib/"):
            inc += ["-I" + os.path.join(self.src, "lib/ultralib/src"), "-I" + os.path.join(self.src, "lib/libmus/src")]
        pre = run([TOOLS["gcc"], "-E", *ARCH, "-nostdinc", *DEFS, "-D_LANGUAGE_C", *inc, "-x", "c", src], cwd=self.src)
        text = pre.decode("utf8")
        try:
            data = text.encode("shift_jis")       # the US build's string encoding (OUT_ENCODING)
        except UnicodeEncodeError:
            data = text.encode("cp932", errors="replace")
        ipath = obj[:-2] + ".i"
        open(ipath, "wb").write(data)
        common = "-fno-common" if re.search(r"(COMMON|scommon)\.c$|src/buffers/", rel) else "-fcommon"
        opt = [os.environ["LIB_OPT"]] if rel.startswith(os.environ.get("LIB_OPT_PREFIX", "#none#")) and "LIB_OPT" in os.environ else []
        run([TOOLS["gcc"], *CFLAGS, common, *opt, "-c", "-x", "cpp-output", ipath, "-o", obj], cwd=self.src)

    def asm(self, src, obj, extra=()):
        d = os.path.dirname(src)
        inc = self.inc + ["-I" + d, "-I" + os.path.join(self.src, "lib/ultralib/src"), *extra]
        inc += ["-Wa,-I" + os.path.join(self.src, "include"), "-Wa,-I" + self.assets, "-Wa,-I" + self.src]
        if src.replace("\\", "/").endswith(tuple(f"src/rsp/{n}.s" for n in ("rspboot", "aspMain", "f3dex2", "s2dex"))):
            # RSP DMA needs 8-byte aligned microcode; KMC's --force-n64align gave that, GAS does not
            text = open(src, encoding="utf8").read()
            text = re.sub(r'(\.section\s+\.[a-z]+[^\n]*\n)', r"\1.balign 16\n", text)
            src = obj[:-2] + ".aligned.s"
            open(src, "w", encoding="utf8").write(text)
        run([TOOLS["gcc"], *ASFLAGS, *DEFS, *inc, "-c", src, "-o", obj], cwd=self.assets)

    # ------------------------------------------------------------ generated inputs
    def pngs(self):
        jobs = []
        for root, dirs, files in os.walk(self.assets):
            dirs[:] = [x for x in dirs if x != "src_override"]
            for f in files:
                if f.endswith(".png"):
                    p = os.path.join(root, f)
                    rel = os.path.relpath(p, self.assets).replace("\\", "/")
                    jobs.append((p, os.path.join(self.bd, "bin", V, rel[:-4] + ".inc"), f[:-4].rsplit(".", 1)[-1]))

        def one(j):
            p, o, fmt = j
            os.makedirs(os.path.dirname(o), exist_ok=True)
            if fmt in ("ci4", "ci8"):
                run([TOOLS["pigment64"], "to-bin", "--c-array", "--format", "palette", "-o",
                     o[:-len(fmt) - 5] + ".palette.inc", p])
            run([TOOLS["pigment64"], "to-bin", "--c-array", "--format", fmt, "-o", o, p])
        with cf.ThreadPoolExecutor(self.jobs * 2) as ex:
            list(ex.map(one, jobs))
        return len(jobs)

    def msgs(self):
        n = 0
        for root, _, files in os.walk(os.path.join(self.src, "src")):
            for f in files:
                if f.endswith(".msg"):
                    rel = os.path.relpath(os.path.join(root, f), self.src).replace("\\", "/")
                    o = os.path.join(self.bd, rel + ".inc")
                    os.makedirs(os.path.dirname(o), exist_ok=True)
                    pre = run([TOOLS["gcc"], "-E", "-P", *ARCH, "-nostdinc", *DEFS, "-D_LANGUAGE_C", *self.inc,
                               "-I" + os.path.dirname(os.path.join(self.src, rel)), "-x", "c", self.path(rel)])
                    open(o[:-4] + ".i", "wb").write(b"# 1 \"x\"\n" + pre)
                    run([sys.executable, "-X", "utf8", os.path.join(self.src, "tools/buildtools/msg_reencoder.py"),
                         o[:-4] + ".i", o, "Shift-JIS"])
                    n += 1
        return n

    def data_wrappers(self):
        """asm/us/data/<name>.s: .incbin wrappers for the databins (our own text)."""
        d = os.path.join(self.out, "asm", V, "data")
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(self.assets):
            if f.endswith(".databin.bin"):
                name = f[:-len(".databin.bin")]
                open(os.path.join(d, name + ".s"), "w").write(
                    '.include "macro.inc"\n\n.section .data, "wa"\n\nnonmatching __%s_databin\n\n'
                    'dlabel __%s_databin\n.incbin "%s"\nenddlabel __%s_databin\n' % (name, name, f, name))

    def write_compat(self):
        """KMC's gcc/stdarg.h walks the stack by hand; modern GCC uses its builtins."""
        va = "\n".join(["#ifndef _STDARG_H", "#define _STDARG_H", "#ifndef __GNUC_VA_LIST", "#define __GNUC_VA_LIST",
                        "typedef __builtin_va_list __gnuc_va_list;", "#endif", "typedef __gnuc_va_list va_list;",
                        "#define va_start(ap, last) __builtin_va_start(ap, last)",
                        "#define va_arg(ap, t) __builtin_va_arg(ap, t)",
                        "#define va_end(ap) __builtin_va_end(ap)", "#define va_copy(d, s) __builtin_va_copy(d, s)",
                        "#endif", ""])
        for rel in ("stdarg.h", "gcc/stdarg.h"):
            os.makedirs(os.path.dirname(os.path.join(self.compat, rel)), exist_ok=True)
            open(os.path.join(self.compat, rel), "w").write(va)

    # ------------------------------------------------------------ main
    def build(self):
        os.makedirs(self.bd, exist_ok=True)
        self.write_compat()
        ld = os.path.join(self.bd, f"drmario64.{V}.ld")
        shutil.copy(os.path.join(self.src, "config/slinky.yaml"), os.path.join(self.out, "slinky.yaml"))
        run([TOOLS["slinky"], "--custom-options", f"version={V}", "--custom-options", "scommon_in_common=true",
             "--custom-options", "modding=false", "-o", ld, "slinky.yaml"], cwd=self.out)
        objs = [l.strip() for l in open(os.path.join(self.bd, f"drmario64.{V}.o_files.list")) if l.strip().endswith(".o")]
        self.data_wrappers()
        print(f"  pngs -> inc: {self.pngs()}   msg files: {self.msgs()}")
        work = []
        for o in objs:
            rel = o[len(f"build/{V}/"):-2]
            obj = os.path.join(self.out, o)
            os.makedirs(os.path.dirname(obj), exist_ok=True)
            if rel.startswith("asm/"):
                work.append(("data", os.path.join(self.out, rel + ".s"), obj))
            elif os.path.exists(self.path(rel + ".c")):
                work.append(("cc", rel + ".c", obj))
            elif os.path.exists(self.path(rel + ".s")):
                work.append(("asm", self.path(rel + ".s"), obj))
            else:
                raise FileNotFoundError(rel)
        lws = [w for w in work if w[1].endswith("game_etc/etc_lws.c")]
        rest = [w for w in work if w not in lws]
        if not lws:
            lws = [("cc", "src/assets/game_etc/etc_lws.c", os.path.join(self.bd, "src/assets/game_etc/etc_lws.o"))]
        errors = []

        def one(w):
            kind, rel, obj = w
            try:
                if kind == "cc":
                    self.cc(rel, obj)
                else:
                    self.asm(rel, obj)
            except Exception as e:  # noqa
                errors.append((rel, str(e)))
        # game_etc: etc_lws is linked alone into a subsegment that etc.c includes
        for w in lws:
            one(w)
            self.subseg(w[2])
        with cf.ThreadPoolExecutor(self.jobs) as ex:
            list(ex.map(one, rest))
        if errors:
            for rel, e in errors[:6]:
                print("  FAIL", rel, e[:1500])
            raise SystemExit(f"{len(errors)} compile errors")
        elf = os.path.join(self.bd, f"drmario64.{V}.elf")
        run([TOOLS["ld"], "-EB", "-Map", elf[:-4] + ".map", "-T", ld, "--emit-relocs", "-o", elf] + objs, cwd=self.out)
        binp = elf[:-4] + ".bin"
        run([TOOLS["objcopy"], "-O", "binary", elf, binp])
        return elf, binp

    def subseg(self, obj):
        sub = obj[:-2] + ".subseg"
        run([TOOLS["ld"], "-EB", "-T", os.path.join(self.src, "linker_scripts/subseg_05.ld"),
             "-o", obj[:-2] + ".subelf", obj])
        run([TOOLS["objcopy"], "-O", "binary", obj[:-2] + ".subelf", sub])
        inc = os.path.join(self.bd, "src/assets/game_etc/etc_lws.subseg.inc")
        run([sys.executable, "-X", "utf8", os.path.join(self.src, "tools/buildtools/inc_from_bin.py"), sub, inc])

    def rom(self, elf, binp, out_rom):
        """Decomp's own packer: gzip the compressed segments (crunch64), patch ROM
        start/end relocations, pad, then the CIC checksum. No 'reuse_original' rows:
        every compressed segment is compressed from our build."""
        py = [sys.executable, "-X", "utf8"]
        unc = binp[:-4] + "_uncompressed.z64"
        run(py + [os.path.join(self.src, "tools/checksummer.py"), binp, unc])
        csv = os.path.join(self.out, "compress_segments.us.csv")
        rows = open(os.path.join(self.src, "tools/compressor/compress_segments.us.csv")).read().splitlines()
        assert not any(r.endswith("reuse_original") for r in rows)
        open(csv, "w").write("\n".join(rows) + "\n")
        cbin = binp[:-4] + "_compressed.bin"
        run(py + [os.path.join(self.src, "tools/compressor/rom_compressor.py"), unc, cbin, elf, csv, V, "--pad-rom"],
            cwd=self.out)
        run(py + [os.path.join(self.src, "tools/checksummer.py"), cbin, out_rom])
        return out_rom


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("assets")
    ap.add_argument("out")
    ap.add_argument("-j", type=int, default=2)
    a = ap.parse_args(argv[1:])
    b = Build(os.path.abspath(a.src), os.path.abspath(a.assets), os.path.abspath(a.out), a.j)
    elf, binp = b.build()
    rom = b.rom(elf, binp, os.path.join(b.out, "drmario64.z64"))
    print(f"  elf {elf}\n  rom {rom} ({os.path.getsize(rom)} B)")


if __name__ == "__main__":
    main(sys.argv)
