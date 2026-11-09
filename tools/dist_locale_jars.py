#!/usr/bin/env python3
"""Distribute the generated zh_CN locale JARs into an assembled .app.

The generator (LocaleJarGenerator) already names every JAR with the module's
real code-name-base, using the cnb-map.properties table. This script therefore
only has to place each JAR next to the cluster that owns that module, and skip
JARs whose module is not part of the build (quarantined/dead modules).

Guess-based renaming is deliberately NOT done here: several modules share a
package prefix (api.templates vs modules.templates, terminal vs terminal.nb,
editor.settings.lib vs editor.settings.storage), so a package vote picks the
wrong module and overwrites a correct overlay.
"""
import os
import shutil
import sys

from paths import GEN_JARS as JARS, BUILD


def index_clusters():
    """Map code-name-base -> cluster that actually ships that module."""
    owner = {}
    for cluster in sorted(os.listdir(BUILD)):
        mdir = os.path.join(BUILD, cluster, "modules")
        if not os.path.isdir(mdir):
            continue
        for fn in sorted(os.listdir(mdir)):
            if fn.endswith(".jar"):
                owner.setdefault(fn[:-4], cluster)
    return owner


def main():
    nb_home = sys.argv[1]  # <app>/Contents/Resources/NetBeans/netbeans
    owner = index_clusters()

    placed = skipped = 0
    skip_log = []
    for fn in sorted(os.listdir(JARS)):
        if not fn.endswith("_zh_CN.jar"):
            continue
        cnb = fn[: -len("_zh_CN.jar")]
        cluster = owner.get(cnb)
        if cluster is None:
            skipped += 1
            skip_log.append(fn)
            continue
        dest_dir = os.path.join(nb_home, cluster, "modules", "locale")
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(os.path.join(JARS, fn), os.path.join(dest_dir, fn))
        placed += 1

    print("#SUMMARY locale_jars_placed=%d skipped=%d" % (placed, skipped))
    for fn in skip_log[:12]:
        print("SKIP %s (module not in this build)" % fn)


if __name__ == "__main__":
    main()
