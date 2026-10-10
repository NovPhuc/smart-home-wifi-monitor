PYTHON ?= python
export PYTHONPATH := src

install:
	$(PYTHON) -m pip install -r requirements.txt

synthetic:
	$(PYTHON) scripts/generate_synthetic_data.py
	$(PYTHON) scripts/prepare_data.py

train-room:
	$(PYTHON) scripts/train_room.py
	$(PYTHON) scripts/evaluate_room.py

train-anomaly:
	$(PYTHON) scripts/train_anomaly.py
	$(PYTHON) scripts/evaluate_anomaly.py

baselines:
	$(PYTHON) scripts/train_baselines.py

test:
	pytest -q

serve:
	$(PYTHON) server/app.py

scan-realtime:
	$(PYTHON) scripts/realtime_wifi_scanner.py

collect-labeled:
	$(PYTHON) scripts/collect_labeled_wifi.py $(ARGS)

.PHONY: install synthetic train-room train-anomaly baselines test serve scan-realtime collect-labeled
