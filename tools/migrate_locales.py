#!/usr/bin/env python3
"""Migrate other locales' trees to the zh_CN (master) layout.

The zh_CN tree is the structural reference:

    l10n/zh_CN/<cluster>/<module>/src/<package>/Bundle_zh_CN.properties
    l10n/zh_CN/nbbuild/installer/<...>/Bundle_zh_CN.properties

Other locales still use the hg-era layout, where a module directory is repeated
and may be named three different ways (short dashed, dotted, or full
code-name-base):

    l10n/de/ide/editor-lib/editor-lib/org/netbeans/editor/Bundle_de.properties
    l10n/de/ide/org-netbeans-modules-editor-lib/org-netbeans-modules-editor-lib/...

Resolution is therefore driven by the **package path**, looked up in the
reference tree, with the module directory used only to break ties. No
translation is added or changed; files whose module no longer exists are moved
to l10n/legacy/<locale>/ (git-ignored) so nothing is lost.

Usage::

    python3 tools/migrate_locales.py                  # dry run with statistics
    python3 tools/migrate_locales.py --apply          # perform the moves
    python3 tools/migrate_locales.py --locale de --apply
    python3 tools/migrate_locales.py --reasons        # show why files quarantine
"""

import io
import os
import sys
from collections import Counter, defaultdict

from paths import L10N, REPO

REFERENCE = "zh_CN"
LEGACY = os.path.join(L10N, "legacy")


def variants(module_dir):
    """All plausible names a module directory may carry.

    Legacy trees use the short dashed form (``editor-lib``), the dotted form
    (``editor.lib``), or the full code-name-base
    (``org-netbeans-modules-editor-lib`` / ``org-netbeans-api-templates``),
    while the reference tree uses the repository directory name
    (``editor.lib``, ``api.templates``).
    """
    out = {module_dir, module_dir.replace("-", ".")}
    out.add("org-netbeans-modules-" + module_dir)
    for prefix in ("org-netbeans-modules-", "org-netbeans-", "org-openide-",
                   "org-apache-", "org-"):
        if module_dir.startswith(prefix):
            rest = module_dir[len(prefix):]
            out.add(rest)
            out.add(rest.replace("-", "."))
    return out


def reference_index():
    """pkg -> {(cluster, module)}, (cluster, module) set, full dir set."""
    pkg2mods = defaultdict(set)
    pairs, dirs = set(), set()
    root = os.path.join(L10N, REFERENCE)
    for r, _d, files in os.walk(root):
        for fn in files:
            if not fn.endswith("_%s.properties" % REFERENCE):
                continue
            rel = os.path.relpath(os.path.join(r, fn), root).replace(os.sep, "/")
            d = rel[: rel.rfind("/")] if "/" in rel else ""
            dirs.add(d)
            c = d.split("/")
            if len(c) >= 3 and c[2] == "src":
                pkg = "/".join(c[3:])
                pkg2mods[pkg].add((c[0], c[1]))
                pairs.add((c[0], c[1]))
            elif len(c) >= 2:
                pairs.add((c[0], c[1]))
    return pkg2mods, pairs, dirs


def git_modules():
    """(cluster, module) pairs that still exist in the NetBeans checkout."""
    pairs = set()
    if not os.path.isdir(REPO):
        return pairs
    for cluster in os.listdir(REPO):
        cdir = os.path.join(REPO, cluster)
        if cluster.startswith(".") or not os.path.isdir(cdir):
            continue
        for module in os.listdir(cdir):
            if os.path.isdir(os.path.join(cdir, module, "src")):
                pairs.add((cluster, module))
    return pairs


def resolve(cluster, module_dir, pkg, pkg2mods, pairs, gmods):
    """Return (cluster, module) or (None, reason)."""
    want = variants(module_dir)
    # 1. package known in the reference tree, same cluster first
    cands = pkg2mods.get(pkg)
    if cands:
        same = [m for m in cands if m[0] == cluster]
        pool = same or list(cands)
        named = [m for m in pool if m[1] in want]
        if len(named) == 1:
            return named[0]
        if len(pool) == 1:
            return pool[0]
        if named:
            return sorted(named)[0]
        return None, "ambiguous-package:" + pkg
    # 2. module exists (module-level fallback: package may be new/removed)
    named = [m for m in pairs if m[1] in want and m[0] == cluster]
    if len(named) == 1:
        return named[0]
    if len(named) > 1:
        return None, "ambiguous-module:" + module_dir
    named = [m for m in pairs if m[1] in want]
    if len(named) == 1:
        return named[0]
    # 3. module exists in the checkout but zh_CN never translated it: still put
    #    it into the reference layout instead of discarding a valid translation
    named = [m for m in gmods if m[1] in want and m[0] == cluster]
    if len(named) == 1:
        return named[0]
    named = [m for m in gmods if m[1] in want]
    if len(named) == 1:
        return named[0]
    return None, "module-not-found:" + module_dir


def plan_locale(locale, pkg2mods, pairs, gmods):
    root = os.path.join(L10N, locale)
    moves, quarantine = [], []
    candidates = []
    stats = Counter()
    for r, _d, files in os.walk(root):
        for fn in sorted(files):
            if not fn.endswith("_%s.properties" % locale):
                continue
            rel = os.path.relpath(os.path.join(r, fn), root).replace(os.sep, "/")
            parts = rel.split("/")
            stats["total"] += 1
            if len(parts) < 4:
                quarantine.append((rel, "too-shallow"))
                continue
            cluster, module, third = parts[0], parts[1], parts[2]

            if third == "src":
                stats["already_src"] += 1
                continue

            # installer assets keep their own tree, mirrored under nbbuild/;
            # the reference tree maps both other/installer and other/nbi there
            if cluster == "other" and module in ("installer", "nbi"):
                moves.append((rel, "nbbuild/installer/" + "/".join(parts[2:])))
                stats["installer"] += 1
                continue

            if third == module:
                pkg = parts[3:]
            elif third in ("ext", "locale", "netbeans") and len(parts) > 4:
                # wrapper layouts, e.g.
                #   {cluster}/{module}/ext/{library}/{pkg...}
                #   {cluster}/{module}/netbeans/{lib|core}/{cnb}/{pkg...}
                # locate the Java package root and take everything from there
                start = None
                for i in range(3, len(parts)):
                    if parts[i] in ("org", "com", "net", "javax", "api"):
                        start = i
                        break
                if start is None:
                    quarantine.append((rel, "company-package-not-found:" + third))
                    continue
                pkg = parts[start:]
                stats["wrapper_" + third] += 1
            else:
                quarantine.append((rel, "unrecognised-layout:" + third))
                continue

            resolved = resolve(cluster, module, "/".join(pkg[:-1]), pkg2mods, pairs, gmods)
            if resolved is None or resolved[0] is None:
                quarantine.append((rel, resolved[1] if resolved else "unresolved"))
                continue
            t_cluster, t_module = resolved
            target = "/".join([t_cluster, t_module, "src"] + pkg)
            candidates.append((rel, target, cluster == t_cluster))

    # several source trees can map to one target when a module moved cluster
    # (ide/javascript2.* -> webcommon/javascript2.*): keep the copy coming from
    # the target cluster, quarantine the stale one
    by_target = defaultdict(list)
    for rel, target, same_cluster in candidates:
        by_target[target].append((rel, same_cluster))
    for target, group in sorted(by_target.items()):
        group.sort(key=lambda g: (not g[1], g[0]))
        moves.append((group[0][0], target))
        stats["mapped"] += 1
        for rel, _same in group[1:]:
            quarantine.append((rel, "duplicate-target:" + group[0][0]))
            stats["duplicate"] += 1
    return moves, quarantine, stats


def apply_moves(locale, moves, quarantine):
    root = os.path.join(L10N, locale)
    legacy = os.path.join(LEGACY, locale)
    for rel, target in moves:
        dst = os.path.join(root, target)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(os.path.join(root, rel), dst)
    for rel, _reason in quarantine:
        dst = os.path.join(legacy, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(os.path.join(root, rel), dst)
    for r, _dirs, _files in os.walk(root, topdown=False):
        if r != root and not os.listdir(r):
            os.rmdir(r)


def main():
    apply = "--apply" in sys.argv
    show_reasons = "--reasons" in sys.argv
    only = None
    for i, a in enumerate(sys.argv):
        if a == "--locale" and i + 1 < len(sys.argv):
            only = sys.argv[i + 1]

    pkg2mods, pairs, _dirs = reference_index()
    gmods = git_modules()
    locales = sorted(d for d in os.listdir(L10N)
                     if os.path.isdir(os.path.join(L10N, d))
                     and d not in (REFERENCE, "legacy"))
    if only:
        locales = [only]

    grand = Counter()
    all_reasons = Counter()
    for locale in locales:
        moves, quarantine, stats = plan_locale(locale, pkg2mods, pairs, gmods)
        print("%-8s total=%-5d mapped=%-5d quarantine=%-5d installer=%-3d dup=%-2d"
              % (locale, stats["total"], stats["mapped"], len(quarantine),
                 stats["installer"], stats["duplicate"]))
        grand.update({k: stats[k] for k in ("total", "mapped", "installer", "duplicate")})
        grand["quarantine"] += len(quarantine)
        if show_reasons:
            for _rel, reason in quarantine:
                all_reasons[reason.split(":")[0]] += 1
        if apply:
            apply_moves(locale, moves, quarantine)
    print("#SUMMARY " + " ".join("%s=%d" % (k, v) for k, v in sorted(grand.items())))
    if show_reasons:
        print("#REASONS " + " ".join("%s=%d" % (k, v) for k, v in all_reasons.most_common()))
    if not apply:
        print("#DRY-RUN no files were moved (pass --apply)")


if __name__ == "__main__":
    main()
