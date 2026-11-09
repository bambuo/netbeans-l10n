#!/usr/bin/env python3
"""Global same-as-English rewrite (robust, snapshot-free).

Walks the zh_CN tree; for every key still carrying the English value it looks
up a translation by exact value, then by a normalized value (unescape \\:,
strip '&' mnemonics, drop trailing ':', collapse whitespace). Skips
DANGER literals that code compares with ==, and values whose leading/trailing
escaped spaces are significant.
"""
import glob
import io
import os
import re
import sys

from paths import TREE, REPO, TRANSLATIONS as LC

# Values that code consumes literally: translating them breaks the UI
# (Integer.parseInt on a translated number throws NumberFormatException).
DANGER = {"default", "true", "false", "always", "never", "yes", "no", "on", "off"}
NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")


def is_code_value(en):
    """True when the English value must never be translated."""
    e = en.strip()
    return e in DANGER or bool(NUMERIC.match(e))



def esc(value):
    return "".join("\\u%04x" % ord(c) if ord(c) > 0x7E else c for c in value)


def split_idx(text):
    for j, ch in enumerate(text):
        if ch in "=: \t" and (j == 0 or text[j - 1] != "\\"):
            return j
    return len(text)


def norm(v):
    v = v.replace("\\:", ":").replace("&", "")
    v = re.sub(r"\s+", " ", v).strip()
    return v.rstrip(":").strip()


def load_maps():
    exact, fuzzy = {}, {}
    files = sorted(glob.glob(LC + "/trans_*.tsv"))
    for n in range(2, 10):
        files += sorted(glob.glob(LC + "/trans%d_*.tsv" % n))
    for f in files:
        for line in io.open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line == "#END":
                continue
            p = line.split("\t")
            if len(p) < 2:
                continue
            en, zh = "\t".join(p[:-1]), p[-1]
            if en == zh:
                continue
            exact.setdefault(en, zh)
            k = norm(en)
            if k:
                fuzzy.setdefault(k, zh)
    lp = LC + "/trans_long.tsv"
    if os.path.exists(lp):
        for line in io.open(lp, encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) == 2 and p[0] != p[1]:
                exact.setdefault(p[0], p[1])
                fuzzy.setdefault(norm(p[0]), p[1])
    return exact, fuzzy


def props(path):
    """returns list of (kind, raw_line) plus dict key->value"""
    items, buf = [], ""
    for raw in io.open(path, encoding="utf-8", errors="replace"):
        line = raw.rstrip("\r\n")
        if not buf:
            s = line.strip()
            if not s:
                items.append(("blank", line))
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


def key_val(text):
    i = split_idx(text)
    return text[:i].strip(), (text[i:].lstrip(" \t=:") if i < len(text) else "")


def main():
    exact, fuzzy = load_maps()
    files = rewritten_files = 0
    keys = 0
    unresolved = []
    for root, dirs, names in os.walk(TREE):
        for fn in sorted(names):
            if not fn.endswith("_zh_CN.properties"):
                continue
            zh_p = os.path.join(root, fn)
            rel = os.path.relpath(zh_p, TREE)
            en_p = os.path.join(REPO, rel[: rel.rfind("/") + 1] +
                                fn.replace("_zh_CN.properties", ".properties"))
            if not os.path.exists(en_p):
                continue
            en_map = {}
            for kind, text in props(en_p):
                if kind == "logical":
                    k, v = key_val(text)
                    if k:
                        en_map[k] = v
            items = props(zh_p)
            changed = False
            for idx, (kind, text) in enumerate(items):
                if kind != "logical":
                    continue
                k, zv = key_val(text)
                ev = en_map.get(k)
                if ev is None or not ev.strip():
                    continue
                if zv.replace("&", "").strip() != ev.replace("&", "").strip():
                    continue
                if zv in DANGER or is_code_value(ev):
                    continue
                if ev.startswith("\\ ") or ev.endswith("\\ ") or zv != ev:
                    # significant whitespace or mnemonic skew: only take exact
                    zh = exact.get(ev)
                else:
                    zh = exact.get(ev) or fuzzy.get(norm(ev))
                if zh is None or zh == ev:
                    if ev.strip() and not re.match(
                            r'^[A-Za-z0-9_./:@$&{}()\[\]<>=|+,#~;!?*"\\:-]*$', ev):
                        unresolved.append((rel, k, ev))
                    continue
                lead = len(text) - len(text.lstrip())
                tail = text[split_idx(text):]
                sep = "="
                for ch in tail:
                    if ch in "=:":
                        sep = ch
                        break
                items[idx] = ("logical", text[: lead + len(k)] + sep + esc(zh))
                keys += 1
                changed = True
            if changed:
                files += 1
                out = []
                for kind, text in items:
                    out.append(text)
                io.open(zh_p, "w", encoding="utf-8").write("\n".join(out).rstrip("\n") + "\n")
    unresolved_visible = [u for u in unresolved if len(u[2]) <= 60]
    print("#SUMMARY files_rewritten=%d keys_rewritten=%d unresolved_same_as_en=%d unresolved_short=%d"
          % (files, keys, len(unresolved), len(unresolved_visible)))
    with io.open(LC + "/unresolved9.tsv", "w", encoding="utf-8") as f:
        for rel, k, ev in unresolved_visible:
            f.write("%s\t%s\t%s\n" % (rel, k, ev))


if __name__ == "__main__":
    main()
