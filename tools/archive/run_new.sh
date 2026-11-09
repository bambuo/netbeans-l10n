#!/bin/bash
# Compile the updated LocaleJarGenerator and run it on the migrated
# (master-layout) zh_CN translation tree.
set -e
LC="/Users/johana/Codes/github/netbeans-l10n"
mkdir -p "$LC/l10n-check/new/classes"
SRC="$LC/locale_zh_CN/src/main/java/org/netbeans/l10n/LocaleJarGenerator.java"
javac -d "$LC/l10n-check/new/classes" "$SRC"
java -cp "$LC/l10n-check/new/classes" org.netbeans.l10n.LocaleJarGenerator \
     "$LC/netbeans-l10n-zip/src" zh_CN "$LC/l10n-check/new-jars"
echo "NEW_DONE"
