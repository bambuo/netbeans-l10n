"""Central path configuration for the NetBeans zh_CN localization tooling.

Every path is derived from this file's own location, so the repository can be
moved or renamed without editing any script. The upstream NetBeans checkout is
the only external dependency and can be overridden with the NB_SRC environment
variable.

Layout this module describes::

    netbeans-l10n/
    ├── l10n/<locale>/…            translation trees (master layout)
    │   └── legacy/zh_CN/…         quarantined, no-longer-shipped modules
    ├── modules/<locale>/          language-pack build modules (Maven/Ant)
    ├── harness/                   Ant build assets (l10nantext, antsrc, …)
    ├── tools/                     these scripts + translations/
    ├── data/                      generated reports      (gitignored)
    └── dist/                      built .nbm / .dmg      (gitignored)
"""

import os

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)

#: upstream apache/netbeans checkout (build output is needed by some tools)
REPO = os.environ.get("NB_SRC", "/Users/johana/Codes/github/netbeans")
#: built IDE clusters
BUILD = os.path.join(REPO, "nbbuild", "netbeans")

#: translation trees
L10N = os.path.join(ROOT, "l10n")
TREE = os.path.join(L10N, "zh_CN")
LEGACY = os.path.join(L10N, "legacy", "zh_CN")

#: language-pack module and its generated artifacts
MODULES = os.path.join(ROOT, "modules")
ZH_MODULE = os.path.join(MODULES, "zh_CN")
ZH_RESOURCES = os.path.join(ZH_MODULE, "src", "main", "resources")
CNB_MAP = os.path.join(ZH_RESOURCES, "cnb-map.properties")
GEN_JARS = os.path.join(ZH_MODULE, "target", "l10n-jars", "modules", "locale")
NBM = os.path.join(ZH_MODULE, "target", "nbm",
                   "org-apache-netbeans-l10n-zh-CN-1.0.nbm")

#: tool data
TRANSLATIONS = os.path.join(TOOLS, "translations")
DATA = os.path.join(ROOT, "data")
DIST = os.path.join(ROOT, "dist")

#: DMG assembly area (rebuilt by tools/build_dmg.sh)
STAGE = os.path.join(DIST, "stage")
APP_NB = os.path.join(STAGE, "Apache NetBeans.app", "Contents", "Resources",
                      "NetBeans", "netbeans")
DMG = os.path.join(DIST, "Apache-NetBeans-arm64.dmg")
LAUNCHER = os.path.join(REPO, "nb", "ide.launcher", "macosx", ".build",
                        "release", "NetBeansLauncher")
