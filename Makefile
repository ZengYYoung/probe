test:
	pytest -q

coverage:
	pytest --cov=probe --cov-report=term

lint:
	ruff check .
