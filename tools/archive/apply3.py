#!/usr/bin/env python3
"""Apply build-output key harvest (worklist3.tsv ASSIGN lines) into the tree.

For each ASSIGN: locate tree file <tree_rel>, append the key with its zh value
(created with a standard header if missing). Values come from trans3_*.tsv,
then trans2_*.tsv, then REUSE from worklist2.tsv; otherwise keep English.
"""
import glob
import io
import os
import re
import sys

LC = "/Users/johana/Codes/github/netbeans-l10n/l10n-check"
TREE = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/src/zh_CN"
TECH = re.compile(r'^[A-Za-z0-9_./:@$&{}()\[\]<>=|+,#~;!?*"\x27\\:-]*$')


def esc(value):
    return "".join("\\u%04x" % ord(c) if ord(c) > 0x7E else c for c in value)


def key_of(t):
    i = len(t)
    for j, ch in enumerate(t):
        if ch in "=: \t" and (j == 0 or t[j - 1] != "\\"):
            i = j
            break
    return t[:i].strip()


def load_maps():
    m = {}
    for line in io.open(LC + "/worklist2.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if p[0] == "REUSE" and len(p) >= 3:
            m["\t".join(p[1:-1])] = p[-1]
    for f in sorted(glob.glob(LC + "/trans2_*.tsv")) + sorted(glob.glob(LC + "/trans3_*.tsv")) \
            + sorted(glob.glob(LC + "/trans4_*.tsv")) + sorted(glob.glob(LC + "/trans5_*.tsv")):
        for line in io.open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line == "#END":
                continue
            p = line.split("\t")
            if len(p) >= 2:
                m["\t".join(p[:-1])] = p[-1]
    return m


def main():
    m = load_maps()
    wl = sys.argv[1] if len(sys.argv) > 1 else LC + "/worklist3.tsv"
    ref = os.path.join(TREE, "java/maven/src/org/netbeans/modules/maven/Bundle_zh_CN.properties")
    header_lines = []
    for raw in io.open(ref, encoding="utf-8"):
        s = raw.strip()
        if s.startswith("#"):
            header_lines.append(raw.rstrip("\n"))
        if len(header_lines) >= 14:
            break

    done = auto = manual = keep = 0
    files_touched = {}
    for line in io.open(wl, encoding="utf-8"):
        if not line.startswith("ASSIGN\t"):
            continue
        p = line.rstrip("\n").split("\t")
        tree_rel, k, ev = p[3], p[4], "\t".join(p[5:])
        zh = m.get(ev)
        if zh is None or zh == ev:
            if ev.strip() and not TECH.match(ev) and len(ev) > 2:
                keep += 1
            zh = ev  # fallback
        else:
            manual += 1
        done += 1
        files_touched.setdefault(tree_rel, []).append((k, ev, zh))

    created = 0
    appended = 0
    for tree_rel, pairs in files_touched.items():
        zh_p = os.path.join(TREE, tree_rel)
        existing_keys = set()
        lines = []
        if os.path.exists(zh_p):
            lines = io.open(zh_p, encoding="utf-8").read().rstrip("\n").split("\n")
            for l in lines:
                if l.strip() and not l.strip().startswith("#"):
                    existing_keys.add(key_of(l))
        else:
            os.makedirs(os.path.dirname(zh_p), exist_ok=True)
            lines = list(header_lines) + [""]
            created += 1
        new_lines = []
        for k, ev, zh in pairs:
            if k in existing_keys:
                continue
            key_render = k + " " if k.endswith("\\") else k
            new_lines.append(key_render + "=" + esc(zh))
            appended += 1
        if new_lines:
            if lines and lines[-1] != "":
                lines.append("")
            lines.append("# Added from build output (generated @Messages keys)")
            lines.extend(new_lines)
            with io.open(zh_p, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

    print("#SUMMARY assigns=%d manual=%d reuse=%d keep_fallback=%d"
          % (done, manual, done - manual - keep, keep))
    print("#SUMMARY files_created=%d keys_appended=%d" % (created, appended))


if __name__ == "__main__":
    main()
