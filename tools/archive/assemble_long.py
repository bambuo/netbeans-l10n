#!/usr/bin/env python3
"""Reassemble full zh values for the 214 long doc values from segment
translations (trans_p*.tsv, keyed by prose index) and value-level maps."""
import glob
import io
import json
import re

LC = "/Users/johana/Codes/github/netbeans-l10n/l10n-check"


def load_value_maps():
    m = {}
    for f in sorted(glob.glob(LC + "/trans_*.tsv")):
        if "/trans_p" in f:
            continue
        for line in io.open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line == "#END":
                continue
            p = line.split("\t")
            if len(p) != 2:
                print("SKIP malformed: %s: %r" % (f, line[:80]))
                continue
            en, zh = p
            if en in m and m[en] != zh:
                print("CONFLICT %r: %r vs %r" % (en[:50], m[en][:40], zh[:40]))
            m[en] = zh
    return m


def main():
    vm = load_value_maps()
    idx2en = {}
    for line in io.open(LC + "/prose_work.txt", encoding="utf-8"):
        p = line.rstrip("\n").split("\t", 1)
        idx2en[int(p[0])] = p[1]
    pmap = {}
    for f in sorted(glob.glob(LC + "/trans_p*.tsv")):
        for line in io.open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line == "#END":
                continue
            p = line.split("\t", 1)
            if len(p) != 2:
                print("SKIP malformed prose: %s: %r" % (f, line[:60]))
                continue
            idx, zh = int(p[0]), p[1]
            pmap[idx] = zh

    structure = json.load(io.open(LC + "/long_structure.json", encoding="utf-8"))
    out = []
    missing_prose = 0
    for item in structure:
        en = item["en"]
        parts = []
        for kind, text in item["segs"]:
            if kind == "tag" or kind == "pre":
                parts.append(text)
            elif kind == "example":
                parts.append(text.replace(">Example<", ">示例<"))
            elif kind == "prose":
                idx = None
                for i, e in idx2en.items():
                    if e == text:
                        idx = i
                        break
                if idx is not None and idx in pmap:
                    parts.append("<p>" + pmap[idx] + "</p>")
                else:
                    missing_prose += 1
                    parts.append("<p>" + text + "</p>")
            else:  # other
                parts.append(vm.get(text, text))
        zh = "".join(parts)
        if "\t" in en or "\t" in zh:
            print("TAB in value, skip: %r" % en[:60])
            continue
        out.append((en, zh))
    # dedupe by en (long list may repeat? no) and check against vm
    with io.open(LC + "/trans_long.tsv", "w", encoding="utf-8") as f:
        for en, zh in out:
            f.write(en + "\t" + zh + "\n")
    kept_prose = sum(1 for en, zh in out if en == zh)
    print("#SUMMARY long_values=%d fully_kept_as_is=%d missing_prose=%d"
          % (len(out), kept_prose, missing_prose))


if __name__ == "__main__":
    main()
