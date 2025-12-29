.PHONY: venv install dev lint clean

VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

dev:
	$(VENV)/bin/uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf $(VENV) __pycache__ .pytest_cache
