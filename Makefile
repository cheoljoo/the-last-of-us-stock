PYTHON := uv run python

.PHONY: install fetch backtest dashboard daily orders publish clean all test

install:
	uv sync

fetch:
	$(PYTHON) scripts/run_backtest.py --fetch

backtest:
	$(PYTHON) scripts/run_backtest.py

# 매일 실행하면 최신 데이터로 백테스트가 업데이트됩니다
dashboard:
	$(PYTHON) scripts/generate_dashboard.py

daily: fetch backtest dashboard
	@echo "=== Daily update complete ==="
	@echo "Dashboard: reports/html/index.html"

orders:
	$(PYTHON) scripts/daily_orders.py

publish:
	bash scripts/publish.sh

clean:
	rm -rf reports/html/* reports/data/*

all: install daily

test:
	uv run pytest tests/ -v
