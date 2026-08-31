#!/bin/bash
# Build FasterCode for macOS (Apple Silicon / arm64 and Intel / x86_64).
#
# Usage:  ./fastercode_macos.sh [python]
#   python -- interpreter to build against (default: python3).
#             Its version determines the resulting FasterCode.cpython-3XX-darwin.so.
#
# Requires: Xcode command line tools, Cython and setuptools in the interpreter.

set -euo pipefail

PYTHON="${1:-python3}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ARCH="$(uname -m)"

echo ""
echo ":: Building FasterCode for macOS ($ARCH) with $PYTHON"
echo ""

case "$ARCH" in
    arm64)  ARCH_FLAGS=(-arch arm64 -mcpu=apple-m1) ;;
    x86_64) ARCH_FLAGS=(-arch x86_64 -march=x86-64 -mtune=generic) ;;
    *)      ARCH_FLAGS=() ;;
esac

OBJS=(lc board data eval hash loop makemove movegen movegen_piece_to search util pgn parser polyglot)

cd "$HERE/src/irina"
rm -f ./*.o
cc -Wall -O2 -fPIC -fno-strict-aliasing "${ARCH_FLAGS[@]}" \
    -c "${OBJS[@]/%/.c}" -DNDEBUG
ar rcs libirina.a "${OBJS[@]/%/.o}"
mv -f libirina.a ..
rm -f ./*.o

cd "$HERE/src"
cat Faster_Irina.pyx Faster_Polyglot.pyx > FasterCode.pyx

ARCHFLAGS="-arch $ARCH" "$PYTHON" setup_macos.py build_ext --inplace --verbose

echo ""
echo ":: Building Complete"
ls -1 "$HERE"/src/FasterCode*.so
echo ""
