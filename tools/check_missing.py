#!/usr/bin/env python3
"""Check missing zh_CN localization keys.

Maps translated files under netbeans-l10n-zip/src/zh_CN to English master
bundles in the apache/netbeans repo via basename + longest path-suffix match,
then compares properties keys both ways.
"""
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

from paths import L10N as SRC, DATA as OUT, REPO
LOCALE = sys.argv[1] if len(sys.argv) > 1 else "zh_CN"
if not re.fullmatch(r"[A-Za-z0-9_]+", LOCALE):
    sys.exit("invalid locale name")
DIR = os.path.realpath(os.path.join(SRC, LOCALE))

MIN_SUFFIX = 3  # path components required for a confident match


def props(path):
    """Parse .properties -> {key: value}; handles comments and continuations."""
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


def suffix(a, b):
    """Longest common path-component suffix length."""
    ac, bc = a.split("/"), b.split("/")
    n = 0
    while n < len(ac) and n < len(bc) and ac[-1 - n] == bc[-1 - n]:
        n += 1
    return n


def en_name(fn):
    """Bundle_zh_CN.properties -> Bundle.properties, else None."""
    m = re.match(r"^(.+)_%s(\.[A-Za-z0-9]+)$" % re.escape(LOCALE), fn)
    return m.group(1) + m.group(2) if m else None


# ---- index the git repo ----
gf = subprocess.run(["git", "-C", REPO, "ls-files"],
                    capture_output=True, text=True, check=True).stdout.split()
gset = set(gf)
by_base = defaultdict(list)
for p in gf:
    if p.endswith(".properties"):
        by_base[os.path.basename(p)].append(p)

# ---- walk the l10n tree, collect candidate mappings ----
stale = []
amb = []
all_nls = set()
items = []
n_trans = 0
for root, dirs, files in os.walk(DIR):
    for fn in files:
        en = en_name(fn)
        if not en or not en.endswith(".properties"):
            continue
        n_trans += 1
        rel = os.path.relpath(os.path.join(root, fn), DIR).replace(os.sep, "/")
        nl = rel[: rel.rfind("/") + 1] + en  # path as if no locale
        all_nls.add(nl)
        if nl in gset:
            items.append((nl, en, rel, True))
        elif by_base.get(en):
            items.append((nl, en, rel, False))
        else:
            stale.append(nl)

# ---- one-to-one greedy assignment, longest suffix first ----
mapped = []
by_git = {}   # git_path -> l10n rel (with locale)
claimed = set()
pending = []
for nl, en, rel, direct in items:
    if direct:
        mapped.append((nl, nl))
        claimed.add(nl)
        by_git[nl] = rel
        continue
    top = nl.split("/")[0]
    scored = sorted(((suffix(nl, c), c.split("/")[0] == top, -len(c), c)
                     for c in by_base[en]), reverse=True)
    if scored and scored[0][0] >= MIN_SUFFIX:
        pending.append((scored[0][0], nl, en, rel))
    else:
        stale.append(nl)
pending.sort(key=lambda x: -x[0])
for _, nl, en, rel in pending:
    top = nl.split("/")[0]
    scored = sorted(((suffix(nl, c), c.split("/")[0] == top, -len(c), c)
                     for c in by_base[en] if c not in claimed), reverse=True)
    if not scored or scored[0][0] < MIN_SUFFIX:
        stale.append(nl)
        continue
    s0, e0, _, c0 = scored[0]
    ntie = sum(1 for x in scored if x[0] == s0 and x[1] == e0)
    if s0 < 4 and e0 == 0:
        stale.append(nl)  # 3-comp suffix across different topdirs is too generic
        continue
    if ntie == 1:
        mapped.append((nl, c0))
        claimed.add(c0)
        by_git[c0] = rel
    else:
        amb.append((nl, [x[3] for x in scored if x[0] == s0 and x[1] == e0]))

# ---- compare keys per mapped pair ----
files_out = []
miss = extra = same = ok = 0
for nl, gp in mapped:
    e = props(os.path.join(REPO, gp))
    z = props(os.path.join(DIR, by_git[gp]))
    m_keys = {k: e[k] for k in e if k not in set(z)}
    x_keys = [k for k in z if k not in set(e)]
    sv = sum(1 for k in e if k in z and z[k] == e[k])
    miss += len(m_keys)
    extra += len(x_keys)
    same += sv
    if not m_keys and not x_keys:
        ok += 1
        continue
    files_out.append({
        "l10n": nl,
        "git": gp,
        "missing": m_keys,
        "extra": x_keys,
        "same": sv,
        "en": len(e),
    })

files_out.sort(key=lambda r: (-len(r["missing"]), r["git"]))
have_all = all_nls
# ---- reverse: git bundles with no translation file at all ----
untrans = []
for p in gf:
    if os.path.basename(p) != "Bundle.properties" or p in by_git:
        continue
    if "/test/" in "/" + p or "/testdata/" in "/" + p:
        continue  # test data is never localized
    c = p.split("/")
    cands = [c]
    if "src" in c:
        i = c.index("src")
        if i >= 1:
            cands.append(c[:i] + [c[i - 1]] + c[i + 1:])
    hit = False
    fn_en, ext = os.path.splitext(p)
    for cd in cands:
        q = "/".join(cd[:-1]) + "/" + cd[-1].replace(ext, "_zh_CN" + ext)
        if q in have_all:
            hit = True
            break
    if not hit:
        untrans.append(p)
untrans.sort()
# ---- per-topdir stats ----
stats = defaultdict(lambda: [0, 0, 0])
for r in files_out:
    st = stats[r["l10n"].split("/")[0]]
    st[0] += 1
    st[1] += len(r["missing"])
for s in stale:
    stats[s.split("/")[0]][2] += 1

# ---- emit JSON to stdout (redirect to file from shell) ----
data = {
    "locale": LOCALE,
    "totals": {
        "translated_files": n_trans,
        "mapped_files": len(mapped),
        "in_sync_files": ok,
        "files_with_missing": len(files_out),
        "missing_keys": miss,
        "stale_keys": extra,
        "untranslated_keys_same_as_en": same,
        "stale_files": len(stale),
        "ambiguous_files": len(amb),
        "git_bundles_no_translation": len(untrans),
    },
    "files": files_out,
    "stale_files_list": stale,
    "ambiguous": amb,
    "untranslated_bundles": untrans,
}
print(json.dumps(data, ensure_ascii=False, indent=1))
