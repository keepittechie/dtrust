
.PHONY: all tier1 validate render clean

OUT?=build/report.json
HTML?=build/report.html
MD?=build/report.md
ROOTFS?=/
MAX_SECONDS?=15

all: tier1 validate render

tier1:
	@mkdir -p build
	python3 dtrust_cli.py --tier 1 --rootfs $(ROOTFS) --out $(OUT) --max-seconds $(MAX_SECONDS)

validate:
	python3 scripts/validate.py $(OUT)

render:
	python3 render_report.py --in $(OUT) --out $(MD)
	python3 render_report.py --in $(OUT) --out $(HTML)

clean:
	rm -rf build


tier2:
	@mkdir -p build
	python3 dtrust_cli.py --tier 2 --rootfs $(ROOTFS) --out build/tier2.json --max-seconds $(MAX_SECONDS)

score1:
	python3 score-dtrust-report.py build/report.json

score2:
	python3 score-dtrust-report.py build/tier2.json


render1:
	python3 render_jinja.py build/report.json md build/report.md
	python3 render_jinja.py build/report.json html build/report.html

render2:
	python3 render_jinja.py build/tier2.json md build/tier2.md
	python3 render_jinja.py build/tier2.json html build/tier2.html


score-json1:
	@mkdir -p build
	python3 score-dtrust-report.py build/report.json > build/report.score.json

score-json2:
	@mkdir -p build
	python3 score-dtrust-report.py build/tier2.json > build/tier2.score.json

render_pretty1:
	@mkdir -p build
	python3 render_pretty.py --in build/report.json --out build/report_pretty.html --score build/report.score.json

render_pretty2:
	@mkdir -p build
	python3 render_pretty.py --in build/tier2.json --out build/tier2_pretty.html --score build/tier2.score.json

.PHONY: tier2 clean

BUILD := build
OUTDIR := reports/demo

tier2:
	@mkdir -p $(BUILD) $(OUTDIR)
	python3 dtrust_cli.py --tier 2 --rootfs / --out $(BUILD)/tier2.json
	python3 render_tier2_html.py $(BUILD)/tier2.json $(OUTDIR)/tier2_pretty.html
	@echo "Wrote: $(OUTDIR)/tier2_pretty.html"

clean:
	@rm -rf $(BUILD) $(OUTDIR)
