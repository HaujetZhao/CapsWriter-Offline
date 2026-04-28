#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON=".venv/bin/python"
DIST="$ROOT/dist"
RELEASE="$ROOT/release"
WITH_TRAY=false

for arg in "$@"; do
    case "$arg" in
        --with-tray) WITH_TRAY=true ;;
    esac
done

mkdir -p "$RELEASE"

echo "===== Building CapsWriter-Offline (Server + Client) ====="
$PYTHON -m PyInstaller --clean --noconfirm build-linux.spec

name="CapsWriter-Offline"
src="$DIST/$name"

if [ ! -d "$src" ]; then
    echo "ERROR: $src not found"
    exit 1
fi

rm -f "$src/models" 2>/dev/null

if [ "$WITH_TRAY" = true ]; then
    echo ""
    echo "===== Stripping PySide6 for tray support ====="
    $PYTHON "$ROOT/strip_pyside6.py" "$src/internal"
fi

echo ""
echo "===== Creating release archive ====="

archive="$RELEASE/${name}-Linux-$(date +%Y%m%d).zip"
rm -f "$archive"
cd "$DIST"
zip -r -9 "$archive" "$(basename "$src")" \
    -x "*/__pycache__/*" "*/.git/*" "*.pyc"
cd "$ROOT"

echo ""
echo "===== Done ====="
echo "  $(du -sh "$archive" | cut -f1)  $archive"
ls -lh dist/CapsWriter-Offline/start_*
