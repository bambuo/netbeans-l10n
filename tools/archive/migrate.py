#!/usr/bin/env python3
"""Plan the zh_CN l10n tree migration from the hg-era layout
(<cluster>/<module>/<module>/pkg/...) to the current netbeans master layout
(<cluster>/<module>/src/<pkg>/...).

Rules (first hit wins), every target validated against the netbeans git index:
  1. {c}/{m}/{m}/rest   -> {c}/{m}/src/rest          (standard dup layout)
  2. same, but {m} -> m.replace('-','.')             (module renamed to dots)
  3. identity {c}/{m}/rest                            (ext/docs/branding trees)
  4. other/ aliases:
       other/installer/** -> nbbuild/installer/**
       other/nbi/**       -> nbbuild/installer/**
       other/ide.branding -> nb/ide.branding
Unresolved files are quarantined to netbeans-l10n-zip/legacy/zh_CN/<rel>.
Output (stdout, TSV):  M<TAB>src<TAB>dst / QDIR<TAB>dir / Q<TAB>src<TAB>reason
plus  #SUMMARY <name>=<n>  lines.
"""
import os
import re
import subprocess

LC = "/Users/johana/Codes/github/netbeans-l10n"
REPO = "/Users/johana/Codes/github/netbeans"
TREE = LC + "/netbeans-l10n-zip/src/zh_CN"
LOCALE = "zh_CN"

def strip_locale(fn):
    """Bundle_zh_CN.properties -> Bundle.properties; None if no suffix."""
    m = re.match(r"^(.+)_%s(\.[A-Za-z0-9]+)$" % LOCALE, fn)
    return m.group(1) + m.group(2) if m else None


def main():
    gi = set(subprocess.run(["git", "-C", REPO, "ls-files"],
                            capture_output=True, text=True, check=True).stdout.split())
    gi_prefix2 = set("/".join(p.split("/")[:2]) for p in gi)
    files = []
    for root, dirs, names in os.walk(TREE):
        for fn in names:
            rel = os.path.relpath(os.path.join(root, fn), TREE)
            files.append(rel.replace(os.sep, "/"))
    files.sort()

    plan = []          # (kind, src, dst, rule)
    for rel in files:
        fn = rel.rsplit("/", 1)[-1]
        en = strip_locale(fn)
        if en is None:
            plan.append(("Q", rel, "", "no-locale-suffix"))
            continue
        comps = rel.split("/")
        if len(comps) < 4:
            plan.append(("Q", rel, "", "too-shallow"))
            continue
        c, mod, t = comps[0], comps[1], comps[2]
        rest = comps[3:]
        m2 = mod.replace("-", ".")
        cands = []  # (rule, candidate comps incl. original filename)
        if t == mod:
            cands.append(("r1", [c, mod, "src"] + rest))
            cands.append(("r2", [c, m2, "src"] + rest))
        cands.append(("r3", comps))
        cands.append(("r4a", [c, m2] + comps[2:]))
        if c == "other":
            top = comps[1]
            if top in ("installer", "nbi"):
                cands.append(("r4b", ["nbbuild", "installer"] + comps[2:]))
            elif top == "ide.branding":
                cands.append(("r4c", ["nb", "ide.branding"] + comps[2:]))
        hit = None
        for rule, cc in cands:
            target = "/".join(cc)
            en_target = "/".join(cc[:-1]) + "/" + en
            if en_target in gi:
                hit = (rule, target)
                break
        if hit:
            plan.append(("M", rel, hit[1], hit[0]))
        elif t == mod and ((c + "/" + mod) in gi_prefix2 or (c + "/" + m2) in gi_prefix2):
            # module lives in git but this subpackage/file has no English file
            # (generated or removed content). Keep the overlay entry: map by
            # module-level validation only, preserving baseline jar behavior.
            mx = mod if (c + "/" + mod) in gi_prefix2 else m2
            plan.append(("M", rel, "/".join([c, mx, "src"] + rest), "r2m"))
        else:
            plan.append(("Q", rel, "", "no-git-target"))

    # duplicate targets: only one file may land at each destination
    seen_dst = {}
    dedup = []
    for item in plan:
        if item[0] == "M":
            d = item[2]
            if d in seen_dst:
                dedup.append(("Q", item[1], "", "dup-target:" + seen_dst[d]))
                continue
            seen_dst[d] = item[1]
        dedup.append(item)
    plan = dedup

    # consolidate whole-module quarantine: module dir (c/m) with only Q files
    mapped_mods = set("/".join(s.split("/")[:2]) for k, s, _, _ in plan if k == "M")
    q_mods = set("/".join(s.split("/")[:2]) for k, s, _, _ in plan if k == "Q")
    qdirs = sorted(d for d in q_mods if d not in mapped_mods)
    qdir_prefixes = [d + "/" for d in qdirs]

        # emit plan: M lines, then QDIR for whole-module quarantine, then Q leftovers
    for k, s, d, rule in plan:
        if k == "M":
            print("M\t%s\t%s\t%s" % (s, d, rule))
    for d in qdirs:
        print("QDIR\t%s\t\t%s" % (d, "whole-module-dead"))
    for k, s, d, rule in plan:
        if k == "Q" and not any(s.startswith(p) for p in qdir_prefixes):
            print("Q\t%s\t\t%s" % (s, rule))

    counts = {}
    for k, s, d, rule in plan:
        key = k if k == "M" else ("Q" if k == "Q" else k)
        ck = rule if k == "M" else "quarantine"
        counts[ck] = counts.get(ck, 0) + 1
    qdir_files = sum(1 for k, s, _, _ in plan if k == "Q"
                     and any(s.startswith(p) for p in qdir_prefixes))
    for name in sorted(counts):
        print("#SUMMARY %s=%d" % (name, counts[name]))
    print("#SUMMARY qdir_modules=%d" % len(qdirs))
    print("#SUMMARY qdir_files=%d" % qdir_files)
    print("#SUMMARY total_files=%d" % len(files))


if __name__ == "__main__":
    main()
