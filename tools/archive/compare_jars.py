#!/usr/bin/env python3
"""Behavioral equivalence gate: compare locale jars produced by the old
generator on the old layout against jars from the updated generator on the
migrated master layout. Expected differences: jars whose module was
quarantined (dead upstream modules). Everything else must be byte-identical.
"""
import io
import os
import re
import zipfile

LC = "/Users/johana/Codes/github/netbeans-l10n"
OLD = LC + "/l10n-check/old-jars/modules/locale"
NEW = LC + "/l10n-check/new-jars/modules/locale"
PLAN = LC + "/l10n-check/move_plan.tsv"


def expected_cnbs():
    cnbs = set()
    with open(PLAN, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if parts[0] != "M":
                continue
            m = parts[2].split("/")[1]
            if m.startswith("org-") or m.startswith("com-"):
                cnbs.add(m)
            else:
                cnbs.add("org-netbeans-modules-" + m.replace(".", "-"))
    return cnbs


def load(path):
    jars = {}
    for fn in os.listdir(path):
        if not fn.endswith(".jar"):
            continue
        with zipfile.ZipFile(os.path.join(path, fn)) as z:
            jars[fn] = {i.filename: z.read(i.filename) for i in z.infolist()}
    return jars


def main():
    old = load(OLD)
    new = load(NEW)
    exp = expected_cnbs()

    only_old = sorted(set(old) - set(new))
    only_new = sorted(set(new) - set(old))
    explained = [j for j in only_old if j.replace("_zh_CN.jar", "") not in exp]
    unexplained_lost = [j for j in only_old if j not in explained]
    extra = only_new

    print("#SUMMARY old_jars=%d new_jars=%d common=%d" % (len(old), len(new), len(set(old) & set(new))))
    print("#SUMMARY lost_jars_expected_dead=%d lost_jars_unexplained=%d extra_new_jars=%d"
          % (len(explained), len(unexplained_lost), len(extra)))
    for j in unexplained_lost:
        print("LOST-UNEXPLAINED " + j)
    for j in extra:
        print("EXTRA-NEW " + j)

    entry_diffs = 0
    byte_diffs = 0
    checked = 0
    for fn in sorted(set(old) & set(new)):
        oe, ne = old[fn], new[fn]
        checked += 1
        for name in sorted(set(oe) - set(ne)):
            print("ENTRY-MISSING %s %s" % (fn, name))
            entry_diffs += 1
        for name in sorted(set(ne) - set(oe)):
            print("ENTRY-EXTRA %s %s" % (fn, name))
            entry_diffs += 1
        for name in sorted(set(oe) & set(ne)):
            if oe[name] != ne[name]:
                print("BYTES-DIFFER %s %s" % (fn, name))
                byte_diffs += 1
    print("#SUMMARY common_jars_checked=%d entry_diffs=%d byte_diffs=%d"
          % (checked, entry_diffs, byte_diffs))


if __name__ == "__main__":
    main()
