#!/usr/bin/env python3
"""Rewrite same-as-English values located by menu_sweep.tsv rows (rel/key/ev).
Map lookup by English value across all trans batches."""
import glob
import io
import os
import sys

TREE = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/src/zh_CN"
LC = "/Users/johana/Codes/github/netbeans-l10n/l10n-check"
DANGER = {"default", "true", "false", "always", "never", "yes", "no", "on", "off"}


def esc(value):
    return "".join("\\u%04x" % ord(c) if ord(c) > 0x7E else c for c in value)


def split_idx(text):
    for j, ch in enumerate(text):
        if ch in "=: \t" and (j == 0 or text[j - 1] != "\\"):
            return j
    return len(text)


def key_of(t):
    tt = t.lstrip()
    return tt[: split_idx(tt)].strip()


def load_maps():
    m = {}
    for f in sorted(glob.glob(LC + "/trans_*.tsv")) + \
            sorted(glob.glob(LC + "/trans2_*.tsv")) + \
            sorted(glob.glob(LC + "/trans3_*.tsv")) + \
            sorted(glob.glob(LC + "/trans4_*.tsv")) + \
            sorted(glob.glob(LC + "/trans5_*.tsv")) + \
            sorted(glob.glob(LC + "/trans6_*.tsv")) + \
            sorted(glob.glob(LC + "/trans7_*.tsv")) + \
            sorted(glob.glob(LC + "/trans8_*.tsv")):
        for line in io.open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line == "#END":
                continue
            p = line.split("\t")
            if len(p) >= 2:
                m.setdefault("\t".join(p[:-1]), p[-1])
    lp = LC + "/trans_long.tsv"
    if os.path.exists(lp):
        for line in io.open(lp, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) == 2:
                m.setdefault(p[0], p[1])
    for line in io.open(LC + "/worklist2.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if p[0] == "REUSE" and len(p) >= 3:
            m.setdefault("\t".join(p[1:-1]), p[-1])
    return m


def main():
    m = load_maps()
    by_file = {}
    for line in io.open(LC + "/menu_sweep.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        rel, k, ev = p[0], p[1], p[2]
        by_file.setdefault(rel, []).append((k, ev))
    files = rewritten = kept = 0
    for rel, pairs in by_file.items():
        zh_p = os.path.join(TREE, rel)
        if not os.path.exists(zh_p):
            continue
        lines = io.open(zh_p, encoding="utf-8").read().rstrip("\n").split("\n")
        changed = False
        for k, ev in pairs:
            if ev in DANGER:
                continue
            zh = m.get(ev)
            if zh is None or zh == ev:
                kept += 1
                continue
            for i, l in enumerate(lines):
                if not l.strip() or l.strip().startswith("#"):
                    continue
                if key_of(l) == k:
                    lines[i] = l[: split_idx(l.lstrip())] + "=" + esc(zh)
                    rewritten += 1
                    changed = True
                    break
        if changed:
            files += 1
            io.open(zh_p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("#SUMMARY files=%d values_rewritten=%d kept_english=%d"
          % (files, rewritten, kept))


if __name__ == "__main__":
    main()
