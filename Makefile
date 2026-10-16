.PHONY: demo test screenshots
demo:
	./run.sh
test:
	python3 -m venv .venv 2>/dev/null || true
	.venv/bin/pip install -q -r requirements-dev.txt
	.venv/bin/python -m pytest -q
screenshots:
	node scripts/screenshot.mjs
