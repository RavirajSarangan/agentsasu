#!/usr/bin/env bash
# Fetch the sherpa-onnx speech engine into apps/mac/vendor.
#
# We use the exact library build the Python core ships with (PyPI sherpa-onnx-core),
# not the GitHub release build: the two are compiled differently and give slightly
# different transcripts, and both cores must behave identically. Checksums are pinned,
# so a changed download is rejected.
set -euo pipefail
VERSION=1.13.8
WHEEL_URL=https://files.pythonhosted.org/packages/8c/2a/2a47b423fe009bbbcb6d7eed7bcba755d6f9ae923b5664c7208128c32d06/sherpa_onnx_core-1.13.8-py3-none-macosx_11_0_arm64.whl
WHEEL_SHA=9312bbd46c93e31cecd3abda9cc8e71881d86cc3da3c35c7445ab04025b9fc3e
HDR_SHA=2a1b95084be8fd1deb3228fcad2fd3f7f0258b64582f7402281ec174c7b7f4ce
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/vendor/sherpa-onnx"
[ -f "$OUT/.wheel-$WHEEL_SHA" ] && [ -f "$OUT/include/c-api.h" ] && exit 0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL -o "$TMP/core.whl" "$WHEEL_URL"
curl -fsSL -o "$TMP/c-api.h" "https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/v$VERSION/sherpa-onnx/c-api/c-api.h"
echo "$WHEEL_SHA  $TMP/core.whl" | shasum -a 256 -c - >/dev/null
echo "$HDR_SHA  $TMP/c-api.h" | shasum -a 256 -c - >/dev/null
rm -rf "$OUT" && mkdir -p "$OUT/lib" "$OUT/include"
unzip -q -j "$TMP/core.whl" "*libsherpa-onnx-c-api.dylib" "*libonnxruntime.dylib" -d "$OUT/lib"
cp "$TMP/c-api.h" "$OUT/include/"
touch "$OUT/.wheel-$WHEEL_SHA"
echo "sherpa-onnx $VERSION (PyPI build) → $OUT"
