PY ?= .venv/bin/python
PORT ?= 8741

.PHONY: test run eval samples validate

test:
	$(PY) -m pytest

run:
	$(PY) -m uvicorn mandilens.api.app:app --app-dir src --host 0.0.0.0 --port $(PORT)

eval:
	$(PY) scripts/evaluate.py

samples:
	$(PY) scripts/make_samples.py

validate:
	sam validate --lint --template-file template.yaml
