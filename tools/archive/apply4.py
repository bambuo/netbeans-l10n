#!/usr/bin/env python3
"""Apply the platform/final localization push from worklist4.tsv.

SCOPE lines -> create new overlay files (value = map chain or keep English).
UPD lines   -> rewrite same-as-English values in existing overlay files.
Map chain (last wins): REUSE(worklist2) -> trans_* -> trans2_* -> trans3_* -> trans4_*.
"""
import glob
import io
import os
import re

LC = "/Users/johana/Codes/github/netbeans-l10n/l10n-check"
TREE = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/src/zh_CN"
REPO = "/Users/johana/Codes/github/netbeans"
DANGER_LITERALS = {"default", "true", "false", "always", "never", "yes", "no", "on", "off"}
SKIP_KEYS = {"OpenIDE-Module-Display-Category"}


def esc(value):
    return "".join("\\u%04x" % ord(c) if ord(c) > 0x7E else c for c in value)


def split_idx(text):
    for j, ch in enumerate(text):
        if ch in "=: \t" and (j == 0 or text[j - 1] != "\\"):
            return j
    return len(text)


def read_logical(path):
    items = []
    buf = ""
    for raw in io.open(path, encoding="utf-8", errors="replace"):
        line = raw.rstrip("\r\n")
        if not buf:
            s = line.strip()
            if not s:
                continue
            if s[0] in "#!":
                items.append(("comment", line))
                continue
        t = len(line) - len(line.rstrip("\\"))
        if t % 2:
            buf += line[:-1]
            continue
        items.append(("logical", buf + line))
        buf = ""
    if buf:
        items.append(("logical", buf))
    return items


def key_of(t):
    return t[: split_idx(t.lstrip())].strip()


def load_maps():
    m = {}
    for line in io.open(LC + "/worklist2.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if p[0] == "REUSE" and len(p) >= 3:
            m.setdefault("\t".join(p[1:-1]), p[-1])
    for f in sorted(glob.glob(LC + "/trans_*.tsv")) + \
            sorted(glob.glob(LC + "/trans2_*.tsv")) + \
            sorted(glob.glob(LC + "/trans3_*.tsv")) + \
            sorted(glob.glob(LC + "/trans4_*.tsv")) + \
            sorted(glob.glob(LC + "/trans5_*.tsv")):
        if "/trans_long" in f:
            continue
        for line in io.open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line == "#END":
                continue
            p = line.split("\t")
            if len(p) >= 2:
                m["\t".join(p[:-1])] = p[-1]
    # trans_long 的条目 (en 整行值)
    lp = LC + "/trans_long.tsv"
    if os.path.exists(lp):
        for line in io.open(lp, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) == 2:
                m[p[0]] = p[1]
    return m


def main():
    m = load_maps()
    ref = os.path.join(TREE, "java/maven/src/org/netbeans/modules/maven/Bundle_zh_CN.properties")
    header = []
    for raw in io.open(ref, encoding="utf-8"):
        s = raw.strip()
        if s.startswith("#"):
            header.append(raw.rstrip("\n"))
        if len(header) >= 14:
            break

    created = created_keys = 0
    updated = 0
    for line in io.open(LC + "/worklist4.tsv", encoding="utf-8"):
        if line.startswith("SCOPE\t"):
            rel = line.rstrip("\n").split("\t")[1]
            en_p = os.path.join(REPO, rel)
            zh_p = os.path.join(TREE, rel[: rel.rfind("/") + 1] +
                                os.path.basename(rel).replace(".properties", "_zh_CN.properties"))
            if os.path.exists(zh_p):
                continue
            items = read_logical(en_p)
            out = list(header) + [""]
            for kind, text in items:
                if kind == "comment":
                    out.append(text)
                    continue
                k = key_of(text)
                ev = text[split_idx(text):].lstrip(" \t=:")
                zh = m.get(ev)
                if zh is None:
                    zh = ev
                if k in SKIP_KEYS:
                    continue
                out.append(k + "=" + esc(zh))
                created_keys += 1
            os.makedirs(os.path.dirname(zh_p), exist_ok=True)
            with io.open(zh_p, "w", encoding="utf-8") as f:
                f.write("\n".join(out) + "\n")
            created += 1
        elif line.startswith("UPD\t"):
            p = line.rstrip("\n").split("\t")
            rel, k, ev = p[1], p[2], "\t".join(p[3:])
            zh = m.get(ev)
            if zh is None or zh == ev:
                continue
            zh_p = os.path.join(TREE, rel)
            if not os.path.exists(zh_p):
                continue
            lines = io.open(zh_p, encoding="utf-8").read().rstrip("\n").split("\n")
            for i, l in enumerate(lines):
                if l.strip() and not l.strip().startswith("#") and key_of(l) == k:
                    lines[i] = l[: split_idx(l)] + "=" + esc(zh)
                    updated += 1
                    break
            io.open(zh_p, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    print("#SUMMARY scope_files_created=%d scope_keys=%d upd_values_rewritten=%d"
          % (created, created_keys, updated))


if __name__ == "__main__":
    main()
