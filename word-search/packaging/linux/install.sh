#!/usr/bin/env bash
# התקנה למשתמש הנוכחי (בלי sudo): ~/.local/share/HebDocSearch + קיצור בתפריט היישומים.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${XDG_DATA_HOME:-$HOME/.local/share}/HebDocSearch"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/512x512/apps"
mkdir -p "$DEST" "$APPS" "$ICONS" "$HOME/.local/bin"
rm -rf "$DEST/app"
cp -R "$HERE/HebDocSearch" "$DEST/app"
cp "$HERE/icon.png" "$ICONS/hebdocsearch.png"
sed "s|@EXEC@|$DEST/app/HebDocSearch|" "$HERE/hebdocsearch.desktop" > "$APPS/hebdocsearch.desktop"
ln -sf "$DEST/app/HebDocSearch" "$HOME/.local/bin/hebdocsearch"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
echo "הותקן. אפשר להפעיל מתפריט היישומים (חיפוש במסמכים) או בפקודה: hebdocsearch"
if ! ldconfig -p 2>/dev/null | grep -q libxcb-cursor; then
  echo "שימו לב: Qt צריך את libxcb-cursor0 – בדביאן/אובונטו: sudo apt install libxcb-cursor0"
fi
