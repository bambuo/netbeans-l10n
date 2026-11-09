#!/usr/bin/env python3
r"""Apply zh_CN translations to the migrated translation tree.

Merges missing keys (from missing_zh_CN_post.json) into each
Bundle_zh_CN.properties, inserting them at the position matching the English
source file order (after the preceding key that exists in the zh file).
Existing zh lines are preserved verbatim.

Values come from (last wins): REUSE entries in worklist.tsv, trans_01..11.tsv,
trans_long.tsv. Values with non-ASCII are written as \uXXXX escapes.
"""
import glob
import io
import json
import os
import re

LC = "/Users/johana/Codes/github/netbeans-l10n/l10n-check"
TREE = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/src/zh_CN"
REPO = "/Users/johana/Codes/github/netbeans"
LOCALE = "zh_CN"


def esc(value):
    out = []
    for ch in value:
        o = ord(ch)
        if o > 0x7E:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    return "".join(out)


def read_logical(path):
    """Return list of (kind, text) logical lines; kind in comment/logical."""
    items = []
    buf = ""
    with io.open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
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
            full = (buf + line).strip()
            buf = ""
            items.append(("logical", full))
    if buf:
        items.append(("logical", buf.strip()))
    return items


def key_of(logical_line):
    i = len(logical_line)
    for j, ch in enumerate(logical_line):
        if ch in "=: \t" and (j == 0 or logical_line[j - 1] != "\\"):
            i = j
            break
    return logical_line[:i].strip()


def load_maps():
    m = {}
    files = sorted(glob.glob(LC + "/trans_[0-9]*.tsv")) + [LC + "/trans_long.tsv"]
    for f in files:
        if not os.path.exists(f):
            continue
        for line in io.open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line == "#END":
                continue
            p = line.split("\t")
            if len(p) < 2:
                print("SKIP malformed %s: %r" % (os.path.basename(f), line[:70]))
                continue
            en, zh = "\t".join(p[:-1]), p[-1]
            if en in m and m[en] != zh:
                print("CONFLICT %r: %r vs %r" % (en[:50], m[en][:40], zh[:40]))
            m[en] = zh
    for line in io.open(LC + "/worklist.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if p[0] == "REUSE" and len(p) >= 3:
            m.setdefault("\t".join(p[1:-1]), p[-1])
    return m


def main():
    d = json.load(io.open(LC + "/missing_zh_CN_post.json", encoding="utf-8"))
    tmap = load_maps()
    files_changed = 0
    keys_added = 0
    no_translation = []
    placeholder_warn = []
    for r in d["files"]:
        missing = r["missing"]
        if not missing:
            continue
        zh_rel = r["l10n"][: r["l10n"].rfind("/") + 1] + \
            os.path.basename(r["git"]).replace(".properties", "_" + LOCALE + ".properties")
        zh_path = os.path.join(TREE, zh_rel)
        en_path = os.path.join(REPO, r["git"])
        en_items = read_logical(en_path)
        zh_items = read_logical(zh_path)
        zh_keys = {key_of(t): i for i, (k, t) in enumerate(zh_items) if k == "logical"}

        inserts = []  # (zh_index_after_which, [ (key, value) ])
        pending = []
        last_anchor = -1
        for kind, text in en_items:
            if kind != "logical":
                continue
            k = key_of(text)
            if k in zh_keys:
                for key, val in pending:
                    inserts.append((zh_keys[k], (key, val)))
                    keys_added += 1
                pending = []
                last_anchor = zh_keys[k]
            elif k in missing:
                ev = missing[k]
                zv = tmap.get(ev)
                if zv is None:
                    no_translation.append((r["git"], k, ev[:60]))
                    zv = ev  # keep-as-is fallback
                pending.append((k, zv))
        # trailing missing keys: append at end
        tail_idx = len(zh_items) - 1
        for key, val in pending:
            inserts.append((tail_idx, (key, val)))
            keys_added += 1

        # repair previously (mis)filled values for missing keys
        def split_idx(text):
            for j, ch in enumerate(text):
                if ch in "=: \t" and (j == 0 or text[j - 1] != "\\"):
                    return j
            return len(text)

        repairs = {}
        for kind, text in zh_items:
            if kind != "logical":
                continue
            k = key_of(text)
            if k in missing:
                ev = missing[k]
                zv = tmap.get(ev, ev)
                cur = text[split_idx(text):].lstrip(" \t=:")
                want = esc(zv)
                if cur != want:
                    repairs[k] = text[:split_idx(text)] + "=" + want
        for i, (kind, text) in enumerate(zh_items):
            if kind == "logical":
                k = key_of(text)
                if k in repairs:
                    zh_items[i] = (kind, repairs[k])

        if not inserts and not repairs:
            continue
        by_idx = {}
        for idx, kv in inserts:
            by_idx.setdefault(idx, []).append(kv)
        new_items = []
        for i, (kind, text) in enumerate(zh_items):
            new_items.append((kind, text))
            if i in by_idx:
                for key, val in by_idx[i]:
                    new_items.append(("logical", key + "=" + esc(val)))
        with io.open(zh_path, "w", encoding="utf-8") as f:
            prev_comment = False
            for i, (kind, text) in enumerate(new_items):
                if kind == "comment":
                    f.write(text + "\n")
                else:
                    f.write(text + "\n")
        files_changed += 1

        # post-checks
        after = read_logical(zh_path)
        after_keys = set(key_of(t) for k, t in after if k == "logical")
        for k in missing:
            if k not in after_keys:
                print("STILL-MISSING %s %s" % (r["git"], k))
        for k, ev in missing.items():
            idx = None
            for i, (kind, t) in enumerate(after):
                if kind == "logical" and key_of(t) == k:
                    idx = t
                    break
            if idx is None:
                continue
            zv = idx.split("=", 1)[1] if "=" in idx else ""
            a = sorted(re.findall(r"\{\d+\}", ev))
            b = sorted(re.findall(r"\{\d+\}", zv))
            if a != b:
                placeholder_warn.append((r["git"], k))

    print("#SUMMARY files_changed=%d keys_added=%d" % (files_changed, keys_added))
    print("#SUMMARY no_translation_fallback=%d placeholder_warnings=%d"
          % (len(no_translation), len(placeholder_warn)))
    for g, k, e in no_translation[:40]:
        print("NO-TRANS %s %s %s" % (g, k, e))
    for g, k in placeholder_warn[:40]:
        print("PH-WARN %s %s" % (g, k))


if __name__ == "__main__":
    main()
