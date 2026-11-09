#!/usr/bin/env python3
"""Remove the misplaced appends written by apply3 run 1 (cluster/cluster paths).

Reconstructs the exact junk paths from worklist3.tsv ASSIGN lines, splits each
affected file at the marker comment and keeps only the pre-marker content.
Files whose pre-marker content is just the generated header are deleted.
"""
import io
import os

LC = "/Users/johana/Codes/github/netbeans-l10n/l10n-check"
TREE = "/Users/johana/Codes/github/netbeans-l10n/netbeans-l10n-zip/src/zh_CN"
MARKER = "# Added from build output (generated @Messages keys)"
HEADER_SAMPLE = os.path.join(TREE, "java/maven/src/org/netbeans/modules/maven/Bundle_zh_CN.properties")

# 14 行许可头作为"仅含头"的判定基准
with io.open(HEADER_SAMPLE, encoding="utf-8") as f:
    head_lines = [l.rstrip("\n") for l in f.readlines()[:14]]


def is_header_only(before_lines):
    body = [l for l in before_lines if l.strip() != ""]
    head_body = [l for l in head_lines if l.strip() != ""]
    return body == head_body or not body


def main():
    junk_paths = set()
    for line in io.open(LC + "/worklist3.tsv", encoding="utf-8"):
        if not line.startswith("ASSIGN\t"):
            continue
        p = line.rstrip("\n").split("\t")
        cluster = p[1]
        pkg = p[3].split("/", 3)
        # run-1 的错误 tree_rel: <cluster>/<cluster>/src/<pkg>/Bundle_zh_CN.properties
        # p[3] = <cluster>/<错误mod>/src/<pkg>/Bundle_zh_CN.properties, 错误mod == cluster
        pkg_part = "/".join(pkg[3:])[:-len("/Bundle_zh_CN.properties")]
        junk_paths.add(os.path.join(TREE, cluster, cluster, "src", pkg_part,
                                    "Bundle_zh_CN.properties"))
    removed_files = 0
    stripped_files = 0
    removed_empty_dirs = set()
    for jp in sorted(junk_paths):
        if not os.path.exists(jp):
            continue
        text = io.open(jp, encoding="utf-8").read()
        if MARKER not in text:
            continue
        before = text.split(MARKER)[0].rstrip("\n").split("\n")
        while before and before[-1] == "":
            before.pop()
        if is_header_only(before):
            os.remove(jp)
            removed_files += 1
            removed_empty_dirs.add(os.path.dirname(jp))
        else:
            io.open(jp, "w", encoding="utf-8").write("\n".join(before) + "\n")
            stripped_files += 1
    # 清理空目录
    for d in sorted(removed_empty_dirs, key=len, reverse=True):
        while d.startswith(TREE) and d != TREE:
            try:
                os.rmdir(d)
            except OSError:
                break
            d = os.path.dirname(d)
    print("#SUMMARY junk_files_removed=%d junk_appends_stripped=%d" % (removed_files, stripped_files))


if __name__ == "__main__":
    main()
