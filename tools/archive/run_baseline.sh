#!/bin/bash
# Compile the checked-in LocaleJarGenerator and run it on the current (old
# hg-layout) zh_CN translation tree to produce the behavior baseline jars.
set -e
LC="/Users/johana/Codes/github/netbeans-l10n"
mkdir -p "$LC/l10n-check/baseline/classes"
SRC="$LC/locale_zh_CN/src/main/java/org/netbeans/l10n/LocaleJarGenerator.java"
javac -d "$LC/l10n-check/baseline/classes" "$SRC"
java -cp "$LC/l10n-check/baseline/classes" org.netbeans.l10n.LocaleJarGenerator \
     "$LC/netbeans-l10n-zip/src" zh_CN "$LC/l10n-check/old-jars"
echo "BASELINE_DONE"
