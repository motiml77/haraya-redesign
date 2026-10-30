#!/usr/bin/env bash
set -euo pipefail
BASE="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -rf "$BASE/HebDocSearch" "$BASE/applications/hebdocsearch.desktop" \
       "$BASE/icons/hicolor/512x512/apps/hebdocsearch.png" "$HOME/.local/bin/hebdocsearch"
echo "הוסר. מפת החיפוש נשארה ב-$BASE/HebWordSearch (אפשר למחוק ידנית)."
