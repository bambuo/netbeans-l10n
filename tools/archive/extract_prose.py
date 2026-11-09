#!/usr/bin/env python3
"""Extract translatable prose segments from long structured doc values.

For each value in work_long.txt, split into segments:
  <p style="font-weight: bold; font-size: 1.2em">TAG</p>   -> keep (tag name)
  <p style="font-weight: bold; font-size: 1.1em">Example</p> -> marker "Example"
  <pre><code>...</code></pre>                              -> keep verbatim
  <p>prose</p>                                             -> to translate
Everything else -> to translate (manual).

Outputs:
  prose_work.txt   unique prose segments (en), numbered
  long_structure.json  per-value segment structure for reassembly
"""
import io
import json
import re

LC = "/Users/johana/Codes/github/netbeans-l10n"
PAT_TAG = re.compile(r'<p style="font-weight: bold; font-size: 1\.2em">[^<]*</p>')
PAT_EX = re.compile(r'<p style="font-weight: bold; font-size: 1\.1em">Example</p>')
PAT_PRE = re.compile(r'<pre><code>.*?</code></pre>', re.S)
PAT_P = re.compile(r'<p>.*?</p>', re.S)
PAT_PATTR = re.compile(r'<p style="[^"]*">.*?</p>', re.S)


def main():
    values = []
    for line in io.open(LC + "/l10n-check/work_long.txt", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        values.append("\t".join(p[:-1]))

    prose_set = {}
    other_set = {}
    structure = []
    for vi, en in enumerate(values):
        segs = []
        pos = 0
        events = []
        for pat, kind in ((PAT_PRE, "pre"), (PAT_TAG, "tag"), (PAT_EX, "example"),
                          (PAT_PATTR, "pattr"), (PAT_P, "prose")):
            for m in pat.finditer(en):
                events.append((m.start(), m.end(), kind, m.group(0)))
        events.sort()
        last = 0
        for s, e, kind, text in events:
            if s < last:
                continue
            if s > last:
                segs.append(("raw", en[last:s]))
            segs.append((kind, text))
            last = e
        if last < len(en):
            segs.append(("raw", en[last:]))
        for i, (kind, text) in enumerate(segs):
            if kind == "tag":
                continue
            elif kind == "example":
                segs[i] = ("example", text)
            elif kind == "pre":
                continue
            elif kind == "prose":
                inner = text[3:-4]
                if inner not in prose_set:
                    prose_set[inner] = len(prose_set) + 1
                segs[i] = ("prose", inner)
            else:  # pattr / raw
                if kind == "pattr":
                    if "Example" in text:
                        continue  # handled? unlikely; fall through
                segs[i] = ("other", text)
                if text not in other_set:
                    other_set[text] = len(other_set) + 1
        structure.append({"vi": vi, "en": en, "segs": [list(s) for s in segs]})

    with io.open(LC + "/l10n-check/prose_work.txt", "w", encoding="utf-8") as f:
        for inner, idx in sorted(prose_set.items(), key=lambda kv: kv[1]):
            f.write("%d\t%s\n" % (idx, inner))
    with io.open(LC + "/l10n-check/other_work.txt", "w", encoding="utf-8") as f:
        for text, idx in sorted(other_set.items(), key=lambda kv: kv[1]):
            f.write("%d\t%s\n" % (idx, text))
    with io.open(LC + "/l10n-check/long_structure.json", "w", encoding="utf-8") as f:
        json.dump(structure, f, ensure_ascii=False, indent=0)
    print("#SUMMARY values=%d prose_unique=%d other_unique=%d" %
          (len(values), len(prose_set), len(other_set)))


if __name__ == "__main__":
    main()
