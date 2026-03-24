.PHONY: all tier1 tier2 tier3 validate1 validate2 validate3 score-json1 score-json2 score-json3 render1 render2 render3 render_pretty1 render_pretty2 render_pretty3 regression clean

BUILD ?= build
ROOTFS ?= /
MAX_SECONDS ?= 15

all: tier1 validate1 render1

tier1:
	@mkdir -p $(BUILD)
	python3 dtrust_cli.py --tier 1 --rootfs $(ROOTFS) --out $(BUILD)/tier1.json --max-seconds $(MAX_SECONDS)

tier2:
	@mkdir -p $(BUILD)
	python3 dtrust_cli.py --tier 2 --rootfs $(ROOTFS) --out $(BUILD)/tier2.json --max-seconds $(MAX_SECONDS)

tier3:
	@mkdir -p $(BUILD)
	python3 dtrust_cli.py --tier 3 --rootfs $(ROOTFS) --out $(BUILD)/tier3.json --max-seconds $(MAX_SECONDS)

validate1:
	python3 scripts/validate.py $(BUILD)/tier1.json

validate2:
	python3 scripts/validate.py $(BUILD)/tier2.json

validate3:
	python3 scripts/validate.py $(BUILD)/tier3.json

score-json1:
	@mkdir -p $(BUILD)
	python3 score-dtrust-report.py $(BUILD)/tier1.json > $(BUILD)/tier1.score.json

score-json2:
	@mkdir -p $(BUILD)
	python3 score-dtrust-report.py $(BUILD)/tier2.json > $(BUILD)/tier2.score.json

score-json3:
	@mkdir -p $(BUILD)
	python3 score-dtrust-report.py $(BUILD)/tier3.json > $(BUILD)/tier3.score.json

render1:
	@mkdir -p $(BUILD)
	python3 render_report.py --in $(BUILD)/tier1.json --out $(BUILD)/tier1.md
	python3 render_report.py --in $(BUILD)/tier1.json --out $(BUILD)/tier1.html

render2:
	@mkdir -p $(BUILD)
	python3 render_report.py --in $(BUILD)/tier2.json --out $(BUILD)/tier2.md
	python3 render_report.py --in $(BUILD)/tier2.json --out $(BUILD)/tier2.html

render3:
	@mkdir -p $(BUILD)
	python3 render_report.py --in $(BUILD)/tier3.json --out $(BUILD)/tier3.md
	python3 render_report.py --in $(BUILD)/tier3.json --out $(BUILD)/tier3.html

render_pretty1: score-json1
	@mkdir -p $(BUILD)
	python3 render_pretty.py --in $(BUILD)/tier1.json --out $(BUILD)/tier1_pretty.html --score $(BUILD)/tier1.score.json

render_pretty2: score-json2
	@mkdir -p $(BUILD)
	python3 render_pretty.py --in $(BUILD)/tier2.json --out $(BUILD)/tier2_pretty.html --score $(BUILD)/tier2.score.json

render_pretty3: score-json3
	@mkdir -p $(BUILD)
	python3 render_pretty.py --in $(BUILD)/tier3.json --out $(BUILD)/tier3_pretty.html --score $(BUILD)/tier3.score.json

regression:
	python3 scripts/regression_examples.py

clean:
	rm -rf $(BUILD)
