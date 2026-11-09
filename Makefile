.PHONY: install lint test benchmark-data evaluate demo run
install:
	pip install -e ".[dev,ui]"
lint:
	black --check src tests scripts streamlit_app
	pylint src scripts streamlit_app
	bandit -q -r src scripts
test:
	pytest --cov --cov-report=term --cov-fail-under=80
benchmark-data:
	python3 scripts/fetch_benchmark_data.py
evaluate: benchmark-data
	python3 -m communitylens.evaluation.forecast_eval data/benchmark_dow30.parquet
	python3 -m communitylens.evaluation.injection_eval
demo: benchmark-data
	python3 scripts/build_demo_data.py
run:
	CL_STATIC_DIR=frontend uvicorn --factory communitylens.api.main:build_app --port 8000
