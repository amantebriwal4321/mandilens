# MandiLens

Photograph a tray of tomatoes next to a printed 50 mm marker. OpenCV 5 measures each fruit and grades it A, B, or C. An agent then decides whether to fix the photo, ask for a retake, send a fruit to a person, or route the lot.

Author: Aman Tebriwal, GitHub [amantebriwal4321](https://github.com/amantebriwal4321).

This is a solo entry for the OpenCV AI Competition 2026. The grades are house bands, not an AGMARK certificate.

## What you need

- Python 3.12
- A virtualenv

AWS is optional. The SAM template is in the repo and has been validated. Nothing here deploys, and the local demo does not need credentials.

## Run it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/make_samples.py
make run
```

Open http://127.0.0.1:8741

Drop a photo or use a sample tray. Soft focus, a dark shot, a missing marker, a red tray, and a cut off fruit are included so you can see the agent change its mind.

Print the marker from the page, or fetch `/api/marker.pdf`. The black square is 50 mm. The white quiet zone is not part of that 50 mm. Print at 100 percent and check it with a ruler before you trust millimetres from a real photo.

## Tests

```bash
.venv/bin/pip install -r requirements-dev.txt
make test
```

The tests paint trays with a known marker and known fruit, then run the same pipeline the API uses. `make eval` writes `docs/eval/results.json`. Those numbers are from the painted set, not from a mandi.

## HTTP API

- `GET /api/health` checks the process and reports the OpenCV version
- `POST /api/grade` takes a multipart photo, runs the agent, and returns the slip
- `POST /api/lots/{lot_id}/review` accepts or overrides low confidence fruit, then routes
- `GET /api/marker.pdf` returns the printable marker

A grade response has `status` of `routed`, `needs_review`, or `retake`, a `steps` trace, and per fruit diameter, ripeness, defect, grade, and confidence.

## Deploy later

The stack is `template.yaml`. It is API Gateway, four Lambda functions on arm64, an OpenCV 5 layer, a private S3 bucket that expires uploads after 7 days, and a DynamoDB table. Bedrock is wired and left off (`BEDROCK_ENABLED` is false) until the account can call Nova Lite. The rule planner calls the same tools.

One time, with Docker available so the arm64 layer builds:

```bash
sam build --use-container
sam deploy --guided
```

Copy `samconfig.toml.example` if you want the defaults (stack `mandilens`, region `ap-south-1`). Check the template without an account:

```bash
make validate
```

No Docker: `scripts/fetch_opencv_layer.sh` downloads the aarch64 wheel. If you use that script, remove the layer `BuildMethod` from the template before `sam build`, or the build will try to recreate the layer.

Lambda routes, once deployed:

- `POST /uploads` returns a presigned PUT
- `POST /inspect` runs the vision pipeline on an S3 key or a base64 image
- `POST /lots` runs the agent
- `POST /lots/{lot_id}/review` records a human decision
- `GET /health`

Do not point a public mandi at `AllowedOrigin=*` without thinking about it. Throttling is on. The bucket is not public.

## Layout

- `src/mandilens/pipeline` OpenCV 5 stages
- `src/mandilens/agent` the loop, the rule planner, and the Bedrock planner
- `src/mandilens/api` local FastAPI app and the web UI in `web/`
- `src/mandilens/aws` Lambda handlers
- `src/mandilens/synth.py` painted trays for tests and the demo
- `template.yaml` SAM
- `TECH_REPORT.md` the submission report
- `VIDEO_SCRIPT.md` the under 5 minute video

## License

MIT. See `LICENSE`.
