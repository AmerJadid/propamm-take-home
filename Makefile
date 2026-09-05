.PHONY: help install part1 part2 sigma test lint
.DEFAULT_GOAL := help

help:
	@echo "make install   install dependencies"
	@echo "make part1     print the Part 1 test-case results"
	@echo "make part2     print the Part 2 results and write the chart"
	@echo "make sigma     re-measure BNBUSDT volatility from Binance (needs network)"
	@echo "make test      run the tests"
	@echo "make lint      check lint and formatting"

install:
	uv sync

part1:
	uv run python part1_pricing/pricing.py

part2:
	uv run python part2_refresh_model/refresh_model.py

sigma:
	uv run python part2_refresh_model/measure_sigma.py

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
