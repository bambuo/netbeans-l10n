#!/usr/bin/env python3
"""Build the translation worklist for the missing zh_CN keys.

1. Index existing translations: en_value -> zh_value (majority vote across
   the whole tree, only pairs where zh differs from en).
2. For every missing key in missing_zh_CN_post.json: if its en value has an
   existing zh translation, auto-reuse it.
3. Emit the remaining unique en values (one per line) as the manual worklist.

Outputs (stdout):
  #SUMMARY lines + worklist to stdout is too big; writes nothing itself.
Prints stats; the worklist goes to file via shell redirect using marker lines:
  REUSE<TAB>en<TAB>zh      (auto-reused value mapping, TSV)
  WORK<TAB>en              (value needing manual translation)
"""
import json
import os
import re
from collections import Counter, defaultdict

LC = "/Users/johana/Codes/github/netbeans-l10n"
TREE = LC + "/netbeans-l10n-zip/src/zh_CN"
REPO = "/Users/johana/Codes/github/netbeans"
DATA = LC + "/l10n-check/missing_zh_CN_post.json"
LOCALE = "zh_CN"


def props(path):
    out, buf = {}, ""
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            if not buf:
                s = line.strip()
                if not s or s[0] in "#!":
                    continue
            t = len(line) - len(line.rstrip("\\"))
            if t % 2:
                buf += line[:-1]
                continue
            full = (buf + line).strip()
            buf = ""
            i = len(full)
            for j, ch in enumerate(full):
                if ch in "=: \t" and (j == 0 or full[j - 1] != "\\"):
                    i = j
                    break
            k = full[:i].strip()
            v = full[i:].lstrip(" \t=:") if i < len(full) else ""
            if k:
                out[k] = v
    return out


def main():
    d = json.load(open(DATA, encoding="utf-8"))
    files = d["files"]
    total_missing = sum(len(r["missing"]) for r in files)

    # index existing translations by en value (majority vote)
    votes = defaultdict(Counter)
    for r in files:
        en_rel = r["git"]
        zh_rel = r["l10n"][: r["l10n"].rfind("/") + 1] + \
            os.path.basename(en_rel).replace(".properties", "_" + LOCALE + ".properties")
        zh_full = os.path.join(TREE, zh_rel)
        en_full = os.path.join(REPO, en_rel)
        if not (os.path.exists(zh_full) and os.path.exists(en_full)):
            continue
        ep, zp = props(en_full), props(zh_full)
        for k, ev in ep.items():
            zv = zp.get(k)
            if zv is not None and zv != ev and ev:
                votes[ev][zv] += 1

    reuse = {}
    conflicts = 0
    for ev, c in votes.items():
        if len(c) > 1:
            conflicts += 1
        reuse[ev] = c.most_common(1)[0][0]

    reused_keys = 0
    work = Counter()
    for r in files:
        for k, ev in r["missing"].items():
            if ev in reuse:
                reused_keys += 1
            elif ev:
                work[ev] += 1

    print("#SUMMARY missing_keys=%d" % total_missing)
    print("#SUMMARY auto_reusable_keys=%d" % reused_keys)
    print("#SUMMARY unique_values_to_translate=%d" % len(work))
    print("#SUMMARY reuse_value_conflicts=%d" % conflicts)
    for ev, zh in sorted(reuse.items()):
        print("REUSE\t%s\t%s" % (ev, zh))
    for ev, n in work.most_common():
        print("WORK\t%s\t%d" % (ev, n))


if __name__ == "__main__":
    main()
