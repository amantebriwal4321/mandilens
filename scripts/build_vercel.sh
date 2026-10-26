#!/usr/bin/env bash
# Builds a static site in dist/ that calls the deployed Lambda API.
set -euo pipefail
API="${MANDILENS_API:?set MANDILENS_API to the API Gateway base, e.g. https://xxx.execute-api.ap-south-1.amazonaws.com/prod}"
rm -rf dist && mkdir -p dist/static dist/samples
cp web/index.html dist/index.html
cp web/app.js web/styles.css dist/static/
printf 'window.MANDILENS_API = "%s";\n' "$API" > dist/static/config.js
cp samples/*.png dist/samples/
python3 - <<'PY'
import json, pathlib
names = sorted(p.name for p in pathlib.Path("samples").glob("*.png"))
pathlib.Path("dist/samples.json").write_text(json.dumps({"samples": [{"name": n, "url": f"/samples/{n}"} for n in names]}))
PY
echo "dist/ ready for $API"
