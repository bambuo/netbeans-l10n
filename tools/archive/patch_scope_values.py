#!/usr/bin/env python3
"""Re-visit SCOPE-created overlay files and rewrite keys whose translation
arrived after the file was created (values changed from English fallback)."""
import glob
import io
import os
import re
import sys

LC = "/Users/johana/Codes/github/netbeans-l10n/l10n-check"
TREE = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/src/zh_CN"
REPO = "/Users/johana/Codes/github/netbeans"
DANGER_LITERALS = {"default", "true", "false", "always", "never", "yes", "no", "on", "off"}



def esc(value):
    return "".join("\\u%04x" % ord(c) if ord(c) > 0x7E else c for c in value)


def split_idx(text):
    for j, ch in enumerate(text):
        if ch in "=: \t" and (j == 0 or text[j - 1] != "\\"):
            return j
    return len(text)


def load_maps():
    m = {}
    for f in sorted(glob.glob(LC + "/trans_*.tsv")) + \
            sorted(glob.glob(LC + "/trans2_*.tsv")) + \
            sorted(glob.glob(LC + "/trans3_*.tsv")) + \
            sorted(glob.glob(LC + "/trans4_*.tsv")) + \
            sorted(glob.glob(LC + "/trans5_*.tsv")):
        for line in io.open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line == "#END":
                continue
            p = line.split("\t")
            if len(p) >= 2:
                m["\t".join(p[:-1])] = p[-1]
    lp = LC + "/trans_long.tsv"
    if os.path.exists(lp):
        for line in io.open(lp, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) == 2:
                m[p[0]] = p[1]
    for line in io.open(LC + "/worklist2.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if p[0] == "REUSE" and len(p) >= 3:
            m.setdefault("\t".join(p[1:-1]), p[-1])
    return m


def main():
    m = load_maps()
    rewritten = 0
    files = 0
    for line in io.open(LC + "/worklist4.tsv", encoding="utf-8"):
        if not line.startswith("SCOPE\t"):
            continue
        rel = line.rstrip("\n").split("\t")[1]
        en_p = os.path.join(REPO, rel)
        zh_p = os.path.join(TREE, rel[: rel.rfind("/") + 1] +
                            os.path.basename(rel).replace(".properties", "_zh_CN.properties"))
        if not os.path.exists(zh_p):
            continue
        lines = io.open(zh_p, encoding="utf-8").read().rstrip("\n").split("\n")
        changed = False
        for i, l in enumerate(lines):
            if not l.strip() or l.strip().startswith("#"):
                continue
            k = l[: split_idx(l)].strip()
            ev = l[split_idx(l):].lstrip(" \t=:")
            if not ev.strip() or ev not in m or ev in DANGER_LITERALS:
                continue
            zh = m[ev]
            if zh != ev:
                lines[i] = l[: split_idx(l)] + "=" + esc(zh)
                rewritten += 1
                changed = True
        if changed:
            files += 1
            io.open(zh_p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("#SUMMARY late_translations_files=%d values_rewritten=%d" % (files, rewritten))


if __name__ == "__main__":
    main()
