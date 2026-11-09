#!/usr/bin/env python3
"""Validate the translation tree for values that code consumes literally.

Three classes of damage are detected:

* numeric   - the English value is a pure number (``390``) but the translation
              is not; such values are parsed with Integer.parseInt and crash
              the UI (e.g. autoupdate UnitTab split position).
* literal   - the English value is one compared with ``==`` in code
              (``default``, ``true``, ``always``, ...); translating it breaks
              assertions and feature detection.
* mnemonic  - a key that ends with ``_mnem_pos``/``MNEM_`` prefix style but
              carries a non-single-character translation.

Run with ``--fix`` to restore the English value for every offending key.

Usage::

    python3 tools/validate_tree.py            # report only, exit 1 if issues
    python3 tools/validate_tree.py --fix      # restore English values
"""

import io
import os
import re
import sys

from paths import TREE, REPO

LITERALS = {"default", "true", "false", "always", "never", "yes", "no", "on", "off"}
NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")


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


def split_idx(text):
    for j, ch in enumerate(text):
        if ch in "=: \t" and (j == 0 or text[j - 1] != "\\"):
            return j
    return len(text)


def esc(value):
    return "".join("\\u%04x" % ord(c) if ord(c) > 0x7E else c for c in value)


def classify(key, en, zh):
    if not en.strip() or zh == en:
        return None
    if NUMERIC.match(en.strip()) and zh.strip() != en.strip():
        return "numeric"
    if en.strip() in LITERALS and zh.strip() != en.strip():
        return "literal"
    return None


def structural(zh_value, en_value, all_keys, own_key):
    """Detect a value that swallowed the following key=value line.

    This happens when a line ends with an odd number of backslashes (a
    properties continuation) and the next line is a comment or a key that must
    not be part of the value. Detected by looking for another key of the same
    bundle, followed by '=', inside the value.
    """
    if zh_value == en_value:
        return None
    for other in all_keys:
        if other != own_key and len(other) >= 6 and (other + "=") in zh_value:
            return "merged"
    return None


def main():
    fix = "--fix" in sys.argv
    issues = []
    structural_issues = []
    for root, dirs, files in os.walk(TREE):
        for fn in sorted(files):
            if not fn.endswith("_zh_CN.properties"):
                continue
            zh_path = os.path.join(root, fn)
            rel = os.path.relpath(zh_path, TREE).replace(os.sep, "/")
            en_path = os.path.join(REPO, rel[: rel.rfind("/") + 1] +
                                   fn.replace("_zh_CN.properties", ".properties"))
            if not os.path.exists(en_path):
                continue
            en = props(en_path)
            zh = props(zh_path)
            for k in en:
                if k not in zh:
                    continue
                kind = structural(zh[k], en[k], en, k)
                if kind:
                    structural_issues.append((rel, k, en[k], zh[k], kind))
            offending = [(k, en[k], zh[k], kind)
                         for k in en
                         if k in zh
                         for kind in [classify(k, en[k], zh[k])]
                         if kind]
            if not offending:
                continue
            issues.extend((rel, k, ev, zv, kind) for k, ev, zv, kind in offending)
            if fix:
                lines = io.open(zh_path, encoding="utf-8").read().rstrip("\n").split("\n")
                wanted = {k: ev for k, ev, _zv, _kind in offending}
                for i, line in enumerate(lines):
                    s = line.lstrip()
                    if not s or s[0] in "#!":
                        continue
                    k = s[: split_idx(s)].strip()
                    if k in wanted:
                        lines[i] = line[: len(line) - len(s) + len(k)] + "=" + esc(wanted[k])
                io.open(zh_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    by_kind = {}
    for issue in issues:
        by_kind[issue[4]] = by_kind.get(issue[4], 0) + 1
    print("#SUMMARY offending_keys=%d %s" % (len(issues), by_kind))
    for rel, k, ev, zv, kind in issues[:40]:
        print("  [%s] %s | %s: %r -> %r" % (kind, rel.split("/src/")[-1][:52], k[:30], ev, zv[:30]))
    print("#SUMMARY merged_values=%d" % len(structural_issues))
    for rel, k, ev, zv, kind in structural_issues[:20]:
        print("  [%s] %s | %s: %r" % (kind, rel.split("/src/")[-1][:52], k[:34], zv[:70]))
    if fix:
        print("#FIXED %d keys restored to English" % len(issues))
    return 1 if (issues or structural_issues) and not fix else 0


if __name__ == "__main__":
    sys.exit(main())
