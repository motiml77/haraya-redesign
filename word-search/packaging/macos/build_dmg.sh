#!/usr/bin/env bash
# יוצר קובץ dmg עם התוכנה וקיצור לתיקיית Applications (גרירה להתקנה).
# שימוש: build_dmg.sh <path/HebDocSearch.app> <out.dmg>
set -euo pipefail
APP="$1"; OUT="$2"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$OUT"
hdiutil create -volname "חיפוש במסמכים" -srcfolder "$STAGE" -ov -format UDZO "$OUT"
rm -rf "$STAGE"
