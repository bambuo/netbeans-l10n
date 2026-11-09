#!/usr/bin/env python3
"""Apply the final localization push.

Bucket A: create NEW Bundle_zh_CN.properties for the SCOPE bundles listed in
worklist2.tsv (mirroring the English file structure, keys in en order).
Bucket B: rewrite historical same-as-English values in existing zh files
(rows in untranslated_scan.tsv) when a translation is available.

Values come from: REUSE lines in worklist2.tsv, then trans2_*.tsv (last wins).
Values without a translation are kept as the English text (logged).
"""
import glob
import io
import os
import re
import sys

LC = "/Users/johana/Codes/github/netbeans-l10n/l10n-check"
TREE = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/src/zh_CN"
REPO = "/Users/johana/Codes/github/netbeans"

TECH = re.compile(r'^[A-Za-z0-9_./:@$&{}()\[\]<>=|+,#~;!?*"\x27\\:-]*$')


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
        items.append(("logical", buf + line))  # preserve trailing escaped spaces
        buf = ""
    if buf:
        items.append(("logical", buf))
    return items


def key_of(t):
    return t[: split_idx(t)].strip()


def val_of(t):
    return t[split_idx(t):].lstrip(" \t=:")


def load_maps():
    m = {}
    for line in io.open(LC + "/worklist2.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if p[0] == "REUSE" and len(p) >= 3:
            m["\t".join(p[1:-1])] = p[-1]
    for f in sorted(glob.glob(LC + "/trans2_*.tsv")):
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
    # reference license header from an existing zh file
    ref = os.path.join(TREE, "java/maven/src/org/netbeans/modules/maven/Bundle_zh_CN.properties")
    header = []
    for kind, text in read_logical(ref):
        if kind == "comment" and len(header) < 14:
            header.append(text)
        elif header:
            break

    scope = [line.rstrip("\n").split("\t")[1]
             for line in io.open(LC + "/worklist2.tsv", encoding="utf-8")
             if line.startswith("SCOPE\t")]

    created = 0
    keys_new = 0
    fallback_new = 0
    for rel in scope:
        en_p = os.path.join(REPO, rel)
        zh_p = os.path.join(TREE, rel[: rel.rfind("/") + 1] +
                            os.path.basename(rel).replace(".properties", "_zh_CN.properties"))
        os.makedirs(os.path.dirname(zh_p), exist_ok=True)
        items = read_logical(en_p)
        out = list(header) + [""]
        for kind, text in items:
            if kind == "comment":
                out.append(text)
                continue
            k = key_of(text)
            ev = val_of(text)
            zh = m.get(ev)
            if zh is None or zh == ev:
                zh = ev  # keep-as-is
                if ev.strip() and not TECH.match(ev) and len(ev) > 2:
                    fallback_new += 1
            else:
                keys_new += 1
            rawkey = text[: split_idx(text)]  # keep escaped-space keys verbatim
            out.append(rawkey + "=" + esc(zh))
        with io.open(zh_p, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
        created += 1

    # bucket B: rewrite historical placeholders
    rewritten = 0
    b_scope = {}
    for line in io.open(LC + "/untranslated_scan.tsv", encoding="utf-8"):
        rel, k, ev = line.rstrip("\n").split("\t")
        zh = m.get(ev)
        if zh is not None and zh != ev:
            b_scope.setdefault(rel, []).append((k, ev, zh))
    for rel, pairs in b_scope.items():
        zh_p = os.path.join(TREE, rel[: rel.rfind("/") + 1] +
                            os.path.basename(rel).replace(".properties", "_zh_CN.properties"))
        if not os.path.exists(zh_p):
            continue
        lines = io.open(zh_p, encoding="utf-8").read().split("\n")
        for k, ev, zh in pairs:
            for i, l in enumerate(lines):
                if key_of(l.strip()) == k and "=" in l:
                    lines[i] = l[: split_idx(l)] + "=" + esc(zh)
                    rewritten += 1
                    break
        io.open(zh_p, "w", encoding="utf-8").write("\n".join(lines))

    print("#SUMMARY created_files=%d translated_keys_new=%d fallback_keep_new=%d"
          % (created, keys_new, fallback_new))
    print("#SUMMARY bucketB_rewritten=%d (of %d candidates)"
          % (rewritten, sum(len(v) for v in b_scope.values())))


if __name__ == "__main__":
    main()
