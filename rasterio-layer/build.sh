#!/usr/bin/env bash
# Build the rasterio Lambda layer zip with Docker.
#
# Usage: ./build.sh [x86_64|arm64] [python-version]
#   ./build.sh                 # x86_64, Python 3.12
#   ./build.sh arm64 3.13
#
# Output: dist/layer-<arch>-py<version>.zip
set -euo pipefail

ARCH="${1:-x86_64}"
PYTHON_VERSION="${2:-3.12}"

case "$ARCH" in
  x86_64) PLATFORM="linux/amd64" ;;
  arm64)  PLATFORM="linux/arm64" ;;
  *) echo "Unsupported architecture '$ARCH' (use x86_64 or arm64)" >&2; exit 1 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAG="rasterio-layer:py${PYTHON_VERSION}-${ARCH}"
OUT_DIR="$SCRIPT_DIR/dist"
OUT_ZIP="$OUT_DIR/layer-${ARCH}-py${PYTHON_VERSION}.zip"

mkdir -p "$OUT_DIR"

docker build \
  --platform "$PLATFORM" \
  --build-arg "PYTHON_VERSION=$PYTHON_VERSION" \
  -t "$TAG" \
  "$SCRIPT_DIR"

docker run --rm --platform "$PLATFORM" -v "$OUT_DIR:/out" "$TAG"
mv "$OUT_DIR/layer.zip" "$OUT_ZIP"

echo "Built $OUT_ZIP ($(du -h "$OUT_ZIP" | cut -f1))"
echo
echo "Publish with:"
echo "  aws lambda publish-layer-version --layer-name rasterio \\"
echo "    --zip-file fileb://$OUT_ZIP \\"
echo "    --compatible-runtimes python${PYTHON_VERSION} \\"
echo "    --compatible-architectures $ARCH"
