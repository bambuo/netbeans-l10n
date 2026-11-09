#!/usr/bin/env python3
"""Build worklist v2 for the final localization push.

Buckets:
  A. untranslated bundles actually shipped in the built IDE
     (519 minus test-data, nbbuild/installer, and modules not in the build)
  B. historical same-as-English keys worth translating (~186 candidates)
  C. kept long doc values needing prose translation (Twig/Latte/Smarty docs)

Output (stdout):
  #SUMMARY lines
  REUSE<TAB>en<TAB>zh       (auto-reusable value mappings)
  WORK<TAB>en               (unique values to translate)
  SCOPE<TAB>git_rel         (bundles to create/update in apply phase)
"""
import glob
import io
import os
import re
import subprocess
from collections import Counter, defaultdict

LC = "/Users/johana/Codes/github/netbeans-l10n/l10n-check"
TREE = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/src/zh_CN"
REPO = "/Users/johana/Codes/github/netbeans"
BUILD = "/Users/johana/Codes/github/netbeans/nbbuild/netbeans"
LOCALE = "zh_CN"

TECH = re.compile(r'^[A-Za-z0-9_./:@$&{}()\[\]<>=|+,#~;!?*"\x27\\:-]*$')


def props(path):
    out, buf = {}, ""
    for raw in io.open(path, encoding="utf-8", errors="replace"):
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
        if k:
            out[k] = full[i:].lstrip(" \t=:") if i < len(full) else ""
    return out


def en_name(fn):
    return fn[:-len("_" + LOCALE + ".properties")] + ".properties"


def main():
    # reuse index: en_value -> zh_value (majority), from the whole tree
    votes = defaultdict(Counter)
    n_pairs = 0
    for root, dirs, files in os.walk(TREE):
        for fn in files:
            if not fn.endswith("_" + LOCALE + ".properties"):
                continue
            zh_p = os.path.join(root, fn)
            rel = os.path.relpath(zh_p, TREE)
            en_rel = rel[: rel.rfind("/") + 1] + en_name(fn)
            en_p = os.path.join(REPO, en_rel)
            if not os.path.exists(en_p):
                continue
            ep, zp = props(en_p), props(zh_p)
            for k, ev in ep.items():
                zv = zp.get(k)
                if zv is not None and zv != ev and ev.strip():
                    votes[ev][zv] += 1
                    n_pairs += 1
    reuse = {ev: c.most_common(1)[0][0] for ev, c in votes.items()}

    # shipped module jars in the built IDE
    shipped = set()
    for cluster in os.listdir(BUILD):
        mdir = os.path.join(BUILD, cluster, "modules")
        if os.path.isdir(mdir):
            for fn in os.listdir(mdir):
                if fn.endswith(".jar"):
                    shipped.add((cluster, fn[:-4]))

    def cnb_dashes(m):
        if m.startswith("org-") or m.startswith("com-"):
            return m
        return "org-netbeans-modules-" + m.replace(".", "-")

    # bucket A: untranslated bundles shipped in the IDE
    # module jar for bundle <c>/<m>/src/<pkg>/Bundle.properties is <c>/modules/<cnb>.jar
    scope_a = []
    gi = set(subprocess.run(["git", "-C", REPO, "ls-files"],
                            capture_output=True, text=True, check=True).stdout.split())
    for p in sorted(gi):
        if os.path.basename(p) != "Bundle.properties" or "/test/" in "/" + p:
            continue
        comps = p.split("/")
        if len(comps) < 4 or comps[2] != "src":
            continue
        c, m = comps[0], comps[1]
        zh_rel = p[: p.rfind("/") + 1] + os.path.basename(p).replace(".properties", "_" + LOCALE + ".properties")
        if os.path.exists(os.path.join(TREE, zh_rel)):
            continue
        if (c, cnb_dashes(m)) not in shipped:
            continue
        scope_a.append(p)

    work = Counter()
    reused = 0
    for p in scope_a:
        ep = props(os.path.join(REPO, p))
        for k, ev in ep.items():
            if not ev.strip():
                continue
            if ev in reuse:
                reused += 1
            elif not TECH.match(ev) and len(ev) > 2:
                work[ev] += 1

    # bucket B: historical placeholders worth translating
    n_b = 0
    for line in io.open(LC + "/untranslated_scan.tsv", encoding="utf-8"):
        rel, k, ev = line.rstrip("\n").split("\t")
        if ev in reuse or len(ev) <= 6 or " " not in ev or TECH.match(ev):
            continue
        n_b += 1
        if ev in reuse:
            continue
        work[ev] += 1

    # bucket C: kept long doc values needing prose translation
    kept_docs = 0
    for line in io.open(LC + "/trans_long.tsv", encoding="utf-8"):
        p = line.rstrip("\n").split("\t")
        if len(p) < 2 or p[0] != p[-1] or "<p>" not in p[0]:
            continue
        kept_docs += 1
        for m in re.finditer(r"<p>(.*?)</p>", p[0], re.S):
            ev = m.group(1)
            if ev.strip() and ev not in reuse and not TECH.match(ev):
                work[ev] += 1

    print("#SUMMARY reuse_pairs=%d reuse_values=%d" % (n_pairs, len(reuse)))
    print("#SUMMARY scope_a_bundles=%d bucketA_reused_keys=%d" % (len(scope_a), reused))
    print("#SUMMARY bucketB_candidates=%d bucketC_kept_docs=%d" % (n_b, kept_docs))
    print("#SUMMARY unique_values_to_translate=%d" % len(work))
    print("#SUMMARY total_translatable_keys=%d" % sum(work.values()))
    for ev, zh in sorted(reuse.items()):
        print("REUSE\t%s\t%s" % (ev, zh))
    for ev, n in work.most_common():
        print("WORK\t%s\t%d" % (ev, n))
    for p in scope_a:
        print("SCOPE\t%s" % p)


if __name__ == "__main__":
    main()
