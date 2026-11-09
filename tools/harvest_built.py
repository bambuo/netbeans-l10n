#!/usr/bin/env python3
"""Harvest missing keys from the BUILT module jars (authoritative runtime
bundles, including @Messages-generated keys absent from git sources).

For each module jar: every **/Bundle.properties entry is the English runtime
bundle. The zh overlay jar (modules/locale/<cnb>_zh_CN.jar) mirrors the same
entry paths with Bundle_zh_CN.properties. A key present in en but absent from
the zh overlay is a UI-visible untranslated string.

Outputs worklist3.tsv:
  #SUMMARY lines
  WORK<TAB>en_value
  ASSIGN<TAB>cluster<TAB>cnb<TAB>tree_rel<TAB>key<TAB>en_value
"""
import io
import os
import re
import zipfile
from collections import Counter, defaultdict

from paths import BUILD, APP_NB, TREE, TRANSLATIONS as LC

TECH = re.compile(r'^[A-Za-z0-9_./:@$&{}()\[\]<>=|+,#~;!?*"\x27\\:-]*$')


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


def main():
    if not os.path.isdir(APP_NB):
        raise SystemExit(
            "Missing assembled IDE at %s\n"
            "Run tools/build_dmg.sh first — it assembles the IDE and installs\n"
            "the generated locale JARs, which this tool compares against." % APP_NB)
    # 树文件按包路径索引: pkg -> tree_rel（权威映射，不依赖 cnb 命名规则）
    pkg2tree = {}
    for root, dirs, files in os.walk(TREE):
        for fn in files:
            if not fn.endswith("_zh_CN.properties"):
                continue
            rel = os.path.relpath(os.path.join(root, fn), TREE).replace(os.sep, "/")
            if "/src/" not in rel:
                continue
            pkg = rel.split("/src/", 1)[1][: -len("/Bundle_zh_CN.properties")]
            pkg2tree.setdefault(pkg, rel)

    work = Counter()
    assigns = []
    miss_keys = 0
    miss_by_mod = Counter()
    jars_scanned = 0
    for cluster in sorted(os.listdir(BUILD)):
        mdir = os.path.join(BUILD, cluster, "modules")
        ldir = os.path.join(APP_NB, cluster, "modules", "locale")
        if not os.path.isdir(mdir):
            continue
        zh_jars = {}
        if os.path.isdir(ldir):
            for fn in os.listdir(ldir):
                if fn.endswith("_zh_CN.jar"):
                    zh_jars[fn[:-len("_zh_CN.jar")]] = os.path.join(ldir, fn)
        for fn in sorted(os.listdir(mdir)):
            if not fn.endswith(".jar"):
                continue
            jars_scanned += 1
            cnb = fn[:-4]
            zh_jar = zh_jars.get(cnb)
            zh_bundles = {}
            if zh_jar:
                with zipfile.ZipFile(zh_jar) as zz:
                    for e in zz.namelist():
                        if e.endswith("_zh_CN.properties"):
                            zh_bundles[e] = props_text(zz.read(e).decode("utf-8", "replace"))
            with zipfile.ZipFile(os.path.join(mdir, fn)) as z:
                for e in sorted(z.namelist()):
                    if not e.endswith("/Bundle.properties") and e != "Bundle.properties":
                        continue
                    pkg = e[: e.rfind("/")] if "/" in e else ""
                    tree_rel = pkg2tree.get(pkg)
                    if not tree_rel:
                        continue  # 树里没有此 bundle 的 overlay
                    mod = tree_rel.split("/")[1]
                    zh_e = e[:-len("Bundle.properties")] + "Bundle_zh_CN.properties"
                    zp = zh_bundles.get(zh_e, {})
                    if not zp and zh_e not in zh_bundles:
                        continue  # whole bundle not translated at all -> bucket A covered these
                    en = props_text(z.read(e).decode("utf-8", "replace"))
                    missing = [k for k in en if k not in zp]
                    if not missing:
                        continue
                    for k in missing:
                        ev = en[k]
                        miss_keys += 1
                        miss_by_mod[cluster + "/" + mod] += 1
                        if ev.strip() and not TECH.match(ev) and len(ev) > 2:
                            work[ev] += 1
                            assigns.append((cluster, cnb, tree_rel, k, ev))
    print("#SUMMARY jars_scanned=%d missing_keys=%d" % (jars_scanned, miss_keys))
    print("#SUMMARY unique_values=%d assign_lines=%d" % (len(work), len(assigns)))
    print("#SUMMARY missing_by_module_top:")
    for m, c in miss_by_mod.most_common(15):
        print("#MOD %s: %d" % (m, c))
    for ev, n in work.most_common():
        print("WORK\t%s\t%d" % (ev, n))
    for a in assigns:
        print("ASSIGN\t%s\t%s\t%s\t%s\t%s" % a)


if __name__ == "__main__":
    main()
