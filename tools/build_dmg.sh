#!/bin/bash
# Assemble a drag-style "Apache NetBeans.app" from the built IDE tree and
# produce an arm64 DMG. Mirrors nbbuild/installer/mac/newbuild/netBeans/nbide/build.xml.
#
# All paths derive from this script's location, so the repository can be moved.
# The upstream NetBeans checkout defaults to ~/Codes/github/netbeans and can be
# overridden with NB_SRC.
set -e
NB_REPO="${NB_SRC:-/Users/johana/Codes/github/netbeans}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/tools"
DIST="$ROOT/dist"
STAGE="$DIST/stage"
APPNAME="Apache NetBeans"
APPDIR="$STAGE/$APPNAME.app"
LAUNCHER="$NB_REPO/nb/ide.launcher/macosx/.build/release/NetBeansLauncher"
NBHOME="$NB_REPO/nbbuild/netbeans"
DMG="$DIST/Apache-NetBeans-arm64.dmg"

echo "== 检查构建产物 =="
for c in platform ide java nb; do
  [ -d "$NBHOME/$c" ] || { echo "缺少 cluster: $c — 先完成 ant build"; exit 1; }
done
mkdir -p "$DIST"

rm -rf "$STAGE"
mkdir -p "$APPDIR/Contents/MacOS" "$APPDIR/Contents/Resources"

echo "== 复制 IDE 内容（双层布局：NetBeans/netbeans） =="
mkdir -p "$APPDIR/Contents/Resources/NetBeans"
cp -RPp "$NBHOME" "$APPDIR/Contents/Resources/NetBeans/netbeans"

echo "== 清理 Windows 可执行文件 =="
find "$APPDIR/Contents/Resources/NetBeans/netbeans/bin" -name "*.exe" -delete 2>/dev/null || true

echo "== 注入 zh_CN locale jars =="
python3 "$TOOLS/dist_locale_jars.py" "$APPDIR/Contents/Resources/NetBeans/netbeans"

echo "== 生成 Info.plist =="
VERSION=$(ls "$APPDIR/Contents/Resources/NetBeans/netbeans/platform" | head -1 | sed 's/platform//;s/^0*//' 2>/dev/null)
VERSION=${VERSION:-dev}
sed -e "s|@APPNAME@|$APPNAME|" \
    -e "s|@APPVERSION@|$VERSION|" \
    -e "s|@EXENAME@|netbeans|" \
    -e "s|@VERSION@|$VERSION|" \
    -e "s|@ICONFILENAME@|netbeans.icns|" \
    -e "s|@NB_ID@|org.apache.netbeans|" \
    "$NB_REPO/nbbuild/installer/mac/newbuild/netBeans/nbide/Info.plist" > "$APPDIR/Contents/Info.plist"

echo "== 图标与启动器 =="
ICNS=$(find "$APPDIR/Contents/Resources/NetBeans/netbeans/nb" -name "netbeans.icns" | head -1)
[ -n "$ICNS" ] && cp "$ICNS" "$APPDIR/Contents/Resources/netbeans.icns"
cp "$LAUNCHER" "$APPDIR/Contents/MacOS/netbeans"
chmod 755 "$APPDIR/Contents/MacOS/netbeans"

echo "== nbexec 检测补丁（捆绑优先[如有] + 用户级 JVM 兜底） =="
python3 - "$APPDIR/Contents/Resources/NetBeans/netbeans/platform/lib/nbexec" <<'PYEOF'
import sys
p = sys.argv[1]
src = open(p, encoding="utf-8").read()
if "zh_CN DMG patch" in src:
    print("already patched")
    sys.exit(0)
marker = 'if [ -z "$jdkhome" ] ; then\n'
bundled = ('if [ -z "$jdkhome" ] ; then\n'
           '    # zh_CN DMG patch: bundled JDK takes priority\n'
           '    if [ -x "$plathome/../../jdk/Contents/Home/bin/java" ]; then\n'
           '        jdkhome="$plathome/../../jdk/Contents/Home"\n'
           '    fi\n')
assert marker in src, "outer jdkhome check not found"
src = src.replace(marker, bundled, 1)
marker2 = '            # Fallback to PATH based value\n'
userscan = ('            # zh_CN DMG patch: user-level JVMs are invisible to java_home\n'
            '            if [ -z "$jdkhome" ]; then\n'
            '                for d in "$HOME"/Library/Java/JavaVirtualMachines/* /Library/Java/JavaVirtualMachines/*; do\n'
            '                    if [ -x "$d/Contents/Home/bin/java" ]; then jdkhome="$d/Contents/Home"; break; fi\n'
            '                    if [ -x "$d/bin/java" ]; then jdkhome="$d"; break; fi\n'
            '                done\n'
            '            fi\n'
            '            # Fallback to PATH based value\n')
assert marker2 in src, "path fallback marker not found"
src = src.replace(marker2, userscan, 1)
open(p, "w", encoding="utf-8").write(src)
print("patched ok")
PYEOF

echo "== 拖拽式 DMG =="
ln -sf /Applications "$STAGE/Applications"
hdiutil create -volname "$APPNAME" -srcfolder "$STAGE" -format UDZO -o "$DMG" -ov
echo "== 完成 =="
ls -lh "$DMG"
