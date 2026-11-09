#!/usr/bin/env python3
"""Audit the legacy quarantine for live-module overlays whose keys are absent
from the migrated tree. Uses cnb -> (cluster, module dir) mapping from the
migrated tree (post-migration tree mirrors git cluster/module names)."""
import io
import os

LEGACY = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/legacy/zh_CN"
TREE = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/src/zh_CN"
REPO = "/Users/johana/Codes/github/netbeans"


def props_lines(path):
    out = {}
    if not os.path.exists(path):
        return out
    buf = ""
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


def main():
    # git 文件索引: (cluster, moddir) -> [rel paths]
    git_by_mod = {}
    git_set = set()
    for root, dirs, files in os.walk(REPO):
        pass
    # 用 git ls-files 更快
    import subprocess
    gi = subprocess.run(["git", "-C", REPO, "ls-files"],
                        capture_output=True, text=True, check=True).stdout.split()
    for p in gi:
        git_set.add(p)
        c = p.split("/")
        if len(c) >= 3 and p.endswith(".properties"):
            git_by_mod.setdefault(c[0] + "/" + c[1], []).append(p)

    cnb2mod = {}
    for cluster in os.listdir(TREE):
        cdir = os.path.join(TREE, cluster)
        if not os.path.isdir(cdir):
            continue
        for mod in os.listdir(cdir):
            if not os.path.isdir(os.path.join(cdir, mod)):
                continue
            cnb = mod if mod.startswith(("org-", "com-")) else \
                "org-netbeans-modules-" + mod.replace(".", "-")
            cnb2mod.setdefault(cnb, (cluster, mod))

    n_audited = n_heavy = 0
    out = []
    for root, dirs, files in os.walk(LEGACY):
        for fn in files:
            if not fn.endswith("_zh_CN.properties"):
                continue
            lp = os.path.join(root, fn)
            rel = os.path.relpath(lp, LEGACY).replace(os.sep, "/")
            comps = rel.split("/")
            if len(comps) < 4:
                continue
            cnb = comps[1]
            pair = cnb2mod.get(cnb)
            if not pair:
                continue
            cluster, mod = pair
            en_base = fn.replace("_zh_CN.properties", ".properties")
            cands = [p for p in git_by_mod.get(cluster + "/" + mod, [])
                     if p.endswith("/" + en_base)]
            if not cands:
                continue
            # 最长尾匹配
            tail = comps[2:]
            def suffix_len(p):
                pc = p.split("/")
                n = 0
                while n < len(pc) and n < len(tail) and pc[-1 - n] == tail[-1 - n]:
                    n += 1
                return n
            cands.sort(key=suffix_len, reverse=True)
            en_path = cands[0]
            if suffix_len(en_path) < 1:
                continue
            n_audited += 1
            leg = props_lines(lp)
            tree_file = os.path.join(TREE, en_path[: en_path.rfind("/") + 1] +
                                     os.path.basename(en_path).replace(".properties", "_zh_CN.properties"))
            cur = props_lines(tree_file)
            skip = {"OpenIDE-Module-Name", "OpenIDE-Module-Short-Description",
                    "OpenIDE-Module-Long-Description", "OpenIDE-Module-Display-Category"}
            missing = [k for k in leg if k not in cur and k not in skip]
            if leg and len(missing) >= max(3, 0.3 * len(leg)):
                n_heavy += 1
                out.append((en_path, len(missing), len(leg)))
    print("#SUMMARY audited=%d missing_heavy=%d" % (n_audited, n_heavy))
    for en_path, nm, nl in sorted(out, key=lambda x: -x[1])[:80]:
        print("MISS\t%s\t%d/%d" % (en_path, nm, nl))


if __name__ == "__main__":
    main()
