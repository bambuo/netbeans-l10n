#!/usr/bin/env python3
"""Final unified worklist: every UI-visible untranslated string.

Sources of English:
  A. git bundles whose zh overlay does not exist (any module, incl. core.*)
  B. same-as-English keys in existing overlays (menu titles, action labels...)
  C. built-jar-only keys (@Messages) missing from overlays

Shipped check: a bundle is in scope only if some dist jar actually contains
its resource path (pkg-based, no cnb name guessing).

Output worklist4.tsv:
  #SUMMARY lines / REUSE lines / WORK<TAB>en / SCOPE<TAB>git_rel / UPD<TAB>tree_rel<TAB>key<TAB>en
"""
import glob
import io
import os
import re
import subprocess
import zipfile
from collections import Counter, defaultdict

REPO = "/Users/johana/Codes/github/netbeans"
BUILD = "/Users/johana/Codes/github/netbeans/nbbuild/netbeans"
TREE = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/src/zh_CN"
LC = "/Users/johana/Codes/github/netbeans-l10n/l10n-check"

TECH = re.compile(r'^[A-Za-z0-9_./:@$&{}()\[\]<>=|+,#~;!?*"\x27\\:-]*$')
SKIP_KEYS = {"OpenIDE-Module-Name", "OpenIDE-Module-Short-Description",
             "OpenIDE-Module-Long-Description", "OpenIDE-Module-Display-Category"}


def props_text(t):
    out, buf = {}, ""
    for raw in t.split("\n"):
        line = raw.rstrip("\r")
        if not buf:
            s = line.strip()
            if not s or s[0] in "#!":
                continue
        tr = len(line) - len(line.rstrip("\\"))
        if tr % 2:
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


def props(path):
    return props_text(io.open(path, encoding="utf-8", errors="replace").read())


def main():
    gi = set(subprocess.run(["git", "-C", REPO, "ls-files"],
                            capture_output=True, text=True, check=True).stdout.split())

    # dist jar entry index: "src-pkg/Bundle.properties" -> list of (cluster, cnb)
    pkg_jars = defaultdict(list)
    for cluster in sorted(os.listdir(BUILD)):
        mdir = os.path.join(BUILD, cluster, "modules")
        if not os.path.isdir(mdir):
            continue
        for fn in os.listdir(mdir):
            if not fn.endswith(".jar"):
                continue
            try:
                z = zipfile.ZipFile(os.path.join(mdir, fn))
            except Exception:
                continue
            for e in z.namelist():
                if e.endswith("/Bundle.properties"):
                    pkg = e[:-len("/Bundle.properties")]
                    pkg_jars[pkg].append((cluster, fn[:-4], e))
            z.close()

    # reuse index from the tree
    votes = defaultdict(Counter)
    for root, dirs, files in os.walk(TREE):
        for fn in files:
            if not fn.endswith("_zh_CN.properties"):
                continue
            zh_p = os.path.join(root, fn)
            rel = os.path.relpath(zh_p, TREE)
            en_rel = rel[: rel.rfind("/") + 1] + fn.replace("_zh_CN.properties", ".properties")
            en_p = os.path.join(REPO, en_rel)
            if not os.path.exists(en_p):
                continue
            ep, zp = props(en_p), props(zh_p)
            for k, ev in ep.items():
                zv = zp.get(k)
                if zv is not None and zv != ev and ev.strip():
                    votes[ev][zv] += 1
    reuse = {ev: c.most_common(1)[0][0] for ev, c in votes.items()}

    # 前几轮已判定保留(zh==en)的值: 不再列入人工清单
    keeps = set()
    for f in sorted(glob.glob(LC + "/trans_*.tsv")) + sorted(glob.glob(LC + "/trans2_*.tsv")) \
            + sorted(glob.glob(LC + "/trans3_*.tsv")):
        for line in io.open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line == "#END":
                continue
            p = line.split("\t")
            if len(p) >= 2 and p[0] == p[-1]:
                keeps.add(p[0])
    if os.path.exists(LC + "/untranslated_scan.tsv"):
        for line in io.open(LC + "/untranslated_scan.tsv", encoding="utf-8"):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 3:
                keeps.add(p[2])

    work = Counter()
    reused = 0
    scopes = []
    updates = []

    git_bundles = [p for p in gi
                   if p.endswith(("/Bundle.properties",)) and "/test/" not in "/" + p
                   and "/src/" in p]
    for p in sorted(git_bundles):
        comps = p.split("/")
        src_i = comps.index("src")
        pkg = "/".join(comps[src_i + 1:-1])
        tree_zh = os.path.join(TREE, p[: p.rfind("/") + 1] +
                               os.path.basename(p).replace(".properties", "_zh_CN.properties"))
        shipped = pkg in pkg_jars
        en = props(os.path.join(REPO, p))
        if not os.path.exists(tree_zh):
            if not shipped:
                continue
            scopes.append(p)
            for k, ev in en.items():
                if k in SKIP_KEYS or not ev.strip() or ev in keeps:
                    continue
                zh = reuse.get(ev)
                if zh is not None and zh != ev:
                    reused += 1
                elif not TECH.match(ev) and len(ev) > 2:
                    work[ev] += 1
        else:
            zh = props(tree_zh)
            for k, ev in en.items():
                if k in SKIP_KEYS:
                    continue
                zv = zh.get(k)
                if zv is not None and zv == ev and ev.strip() and ev not in keeps:
                    if not TECH.match(ev) and len(ev) > 2 and re.search(r"[A-Za-z]", ev):
                        z2 = reuse.get(ev)
                        if z2 is not None and z2 != ev:
                            reused += 1
                        else:
                            work[ev] += 1
                            updates.append((p[: p.rfind("/") + 1] +
                                            os.path.basename(p).replace(".properties", "_zh_CN.properties"),
                                            k, ev))

    # built-jar-only keys (@Messages) missing from overlays
    for pkg, jars in pkg_jars.items():
        for cluster, cnb, entry in jars:
            en_path = None
            for p in git_bundles:
                if p.endswith("/src/" + pkg + "/Bundle.properties"):
                    en_path = p
                    break
            if en_path is None:
                continue
            tree_zh = os.path.join(TREE, en_path[: en_path.rfind("/") + 1] +
                                   os.path.basename(en_path).replace(".properties", "_zh_CN.properties"))
            if not os.path.exists(tree_zh):
                continue
            en_keys = set()
            zh_keys = set()
            for cluster2, cnb2, e2 in jars:
                pass
            # 取该 bundle 的 en jar keys(来自任一同 pkg jar) 与 zh overlay keys
            z = zipfile.ZipFile(os.path.join(BUILD, cluster, "modules", cnb + ".jar"))
            en = props_text(z.read(entry).decode("utf-8", "replace"))
            z.close()
            zh_p = os.path.join(BUILD, cluster, "modules", "locale", cnb + "_zh_CN.jar")
            if os.path.exists(zh_p):
                zz = zipfile.ZipFile(zh_p)
                zh_e = entry[:-len("Bundle.properties")] + "Bundle_zh_CN.properties"
                if zh_e in zz.namelist():
                    zh_keys = set(props_text(zz.read(zh_e).decode("utf-8", "replace")))
                zz.close()
            for k, ev in en.items():
                if k in zh_keys or k in SKIP_KEYS or not ev.strip():
                    continue
                zh = reuse.get(ev)
                if zh is not None and zh != ev:
                    reused += 1
                elif not TECH.match(ev) and len(ev) > 2:
                    work[ev] += 1
                    updates.append((tree_zh[len(TREE) + 1:], k, ev))

    print("#SUMMARY reuse_values=%d reused_hits=%d" % (len(reuse), reused))
    print("#SUMMARY scope_new_bundles=%d update_keys=%d unique_values=%d total_work=%d"
          % (len(scopes), len(updates), len(work), sum(work.values())))
    for ev, zh in sorted(reuse.items()):
        print("REUSE\t%s\t%s" % (ev, zh))
    for ev, n in work.most_common():
        print("WORK\t%s\t%d" % (ev, n))
    for p in scopes:
        print("SCOPE\t%s" % p)
    for t, k, ev in updates:
        print("UPD\t%s\t%s\t%s" % (t, k, ev))


if __name__ == "__main__":
    main()
