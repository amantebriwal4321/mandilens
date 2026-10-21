#!/bin/sh
# Pull the arm64 OpenCV 5 wheel without Docker.
# Use this only if you cannot run: sam build --use-container
# After it runs, delete the BuildMethod metadata in template.yaml
# or the next sam build will try to rebuild the layer.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
DEST="$ROOT/layers/opencv/python"
rm -rf "$DEST"
mkdir -p "$DEST"
python3 -m pip install \
  --platform manylinux2014_aarch64 \
  --python-version 3.12 \
  --implementation cp \
  --only-binary=:all: \
  --target "$DEST" \
  -r "$ROOT/layers/opencv/requirements.txt"
echo "Layer wheels are in $DEST"
