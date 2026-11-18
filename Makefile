# ============================================================================
#  GREAT / DAC-26 -- GenAI-Assisted RTL Hardware IP Redaction
#  Single-command driver for the full six-phase pipeline.
#
#    make all        set up the env (if needed) and run every phase end to end
#    make setup      create the conda environment
#    make list-designs  list the 42 design IDs available to the pipeline
#    make fetch      refresh the original benchmarks from pinned upstream sources
#    make asap7      download & prepare the ASAP7 PDK (open-source) for mapping
#    make phase0     ASAP7 tech-map + netlist knowledge graph (per design)
#    make tb         exhaustive phase-travelling testbench on ModelSim (per design)
#    make phase1 ... run one phase
#    make variants   build the B0/B1/B2 variant family + Pareto curve
#    make report     assemble the deliverable package
#    make test       run the deterministic-core test suite (no LLM needed)
#    make clean      remove pipeline outputs (keeps the LLM cache)
#    make distclean  also remove the LLM cache and setup stamp
# ============================================================================

SHELL      := /bin/bash
.DEFAULT_GOAL := help
ENV_NAME   := great_dac26
CONDA_BASE := $(shell conda info --base 2>/dev/null)
RUN        := source "$(CONDA_BASE)/etc/profile.d/conda.sh" && conda activate "$(ENV_NAME)" &&
PY         := $(RUN) python
S          := scripts

# Override on the command line, e.g.  make all DESIGN="-d aes_sbox -d chacha_qr"
EVAL_FLAGS ?=
DESIGN     ?=
export GREAT_MODEL ?= qwen3.8:latest

.PHONY: all setup fetch fetch-cep list-designs check asap7 phase0 netlist phase1 phase2 phase3 phase4 \
        phase4b phase5 phase6 phase6b phase6c phase6d phase6e attacks tb variants report test clean distclean help pipeline

help:
	@sed -n '2,/^# ===/{ /^# ===/d; p; }' Makefile

list-designs:
	@for rtl in examples/rtl/*.v; do basename "$$rtl" .v; done

# ---------------------------------------------------------------- environment
setup: env/.stamp
env/.stamp: env/environment.yml
	@if conda env list | grep -q '^$(ENV_NAME) '; then \
	   echo ">> updating conda env $(ENV_NAME)"; \
	   conda env update -n $(ENV_NAME) -f env/environment.yml --prune; \
	 else \
	   echo ">> creating conda env $(ENV_NAME)"; \
	   conda env create -f env/environment.yml -y; \
	 fi
	@touch $@

check: setup
	@echo ">> tool and model check"
	@$(PY) -c "from great import config as C; \
	print(' iverilog :', C.IVERILOG); print(' vvp      :', C.VVP); \
	print(' yosys    :', C.YOSYS); print(' verilator:', C.VERILATOR); \
	print(' model    :', C.LLM_MODEL); print(' host     :', C.OLLAMA_HOST)"
	@curl -sf $${OLLAMA_HOST:-http://localhost:11434}/api/tags >/dev/null \
	  && echo " ollama   : reachable" \
	  || (echo " ollama   : NOT REACHABLE -- start it with 'ollama serve'"; exit 1)
	@$(RUN) ollama list | grep -q "$$GREAT_MODEL" \
	  && echo " model    : present" \
	  || (echo " model    : '$$GREAT_MODEL' not pulled -- run 'ollama pull $$GREAT_MODEL'"; exit 1)

# Optional PSAT integration uses a locally extracted Ubuntu libfl runtime when
# present, so tests do not need changes to the host's system libraries.
TEST_RUNTIME := $(CURDIR)/tools/runtime-deps/usr/lib/x86_64-linux-gnu
TEST_PY = $(RUN) LD_LIBRARY_PATH="$(TEST_RUNTIME)$${LD_LIBRARY_PATH:+:$${LD_LIBRARY_PATH}}" python

test: setup
	$(TEST_PY) tests/test_core.py
	$(TEST_PY) tests/test_workstreams.py
	$(TEST_PY) -m unittest discover -s tests -p test_verification_harness.py -v
	$(TEST_PY) -m unittest discover -s tests -p test_posterior_coverage.py -v

fetch: setup
	$(PY) $(S)/fetch_examples.py

fetch-cep: setup
	$(PY) $(S)/fetch_cep.py

asap7: setup
	$(PY) $(S)/setup_asap7.py

# ------------------------------------------------------------------- pipeline
phase0: asap7 ; $(PY) $(S)/phase0_netlist.py     $(DESIGN)
netlist: phase0
phase1: phase0 check      ; $(PY) $(S)/phase1_profile.py     $(DESIGN)
phase2: phase1      ; $(PY) $(S)/phase2_sensitivity.py $(DESIGN)
phase3: phase2      ; $(PY) $(S)/phase3_strategy.py    $(DESIGN)
phase4: phase3      ; $(PY) $(S)/phase4_transform.py   $(DESIGN)
phase4b: phase4    ; $(PY) $(S)/phase4b_overhead.py    $(DESIGN) $(EVAL_FLAGS)
phase6c: phase5     ; $(PY) $(S)/phase6c_sat_attack.py   $(DESIGN) $(EVAL_FLAGS)
phase6d: phase4     ; $(PY) $(S)/phase6d_dana_attack.py  $(DESIGN) $(EVAL_FLAGS)
phase6e: phase6     ; $(PY) $(S)/phase6e_removal_attack.py $(DESIGN)
attacks: phase6c phase6d phase6e
phase5: phase4      ; $(PY) $(S)/phase5_verify.py      $(DESIGN)
phase6: phase5      ; $(PY) $(S)/phase6_leakage.py     $(DESIGN)
phase6b: phase6     ; $(PY) $(S)/phase6b_escalate.py   $(DESIGN)
tb: phase6b         ; $(PY) $(S)/tb_run.py             $(DESIGN)
variants: phase3    ; $(PY) $(S)/variants.py          $(DESIGN)
report: tb phase4b attacks ; $(PY) $(S)/report.py             $(DESIGN)

# Re-run a single phase without re-checking its predecessors:
#     make -o phase3 phase4
pipeline: report
all: setup report
	@echo
	@echo "================================================================"
	@echo " Pipeline complete."
	@echo "   report      : pipeline/report/REDACTION_REPORT.md"
	@echo "   deliverables: pipeline/report/deliverables/"
	@echo "   change logs : pipeline/phase*/[design].changelog.json"
	@echo "   GenAI logs  : pipeline/genai_logs/*.jsonl"
	@echo "   (optional)  : 'make variants' for the B0/B1/B2 Pareto curve"
	@echo "================================================================"

# ---------------------------------------------------------------------- clean
clean:
	rm -rf pipeline/phase* pipeline/report pipeline/genai_logs pipeline/testbench
distclean: clean
	rm -rf pipeline/.llm_cache env/.stamp

# Legacy acquisition and diagnostics for local dataset workspaces.
DATASET_FLAGS  ?=
DATASET2_FLAGS ?=
DATASET3_ROOT  ?= verilog_ip_partial
DATASET3_FLAGS ?=

.PHONY: fetch-dataset filter-dataset prepare-dataset check-dataset dataset-status test-dataset dataset-tools \
        fetch-dataset2 validate-dataset2 dataset2-status test-dataset2 \
        prepare-dataset3 dataset3-status test-dataset3

fetch-dataset: setup
	$(PY) $(S)/dataset.py fetch $(DATASET_FLAGS)

filter-dataset: setup
	$(PY) $(S)/dataset.py filter $(DATASET_FLAGS)

check-dataset: setup
	$(PY) $(S)/dataset.py check-inputs $(DATASET_FLAGS)

prepare-dataset: setup dataset-tools
	$(PY) $(S)/dataset.py prepare $(DATASET_FLAGS)

dataset-tools: setup
	$(PY) $(S)/setup_dataset_tools.py

dataset-status:
	python3 $(S)/dataset.py status $(DATASET_FLAGS)

test-dataset: setup
	$(PY) -m unittest discover -s tests -p 'test_dataset.py' -v

fetch-dataset2: setup
	$(PY) $(S)/dataset2_manual.py --download-only $(DATASET2_FLAGS)

validate-dataset2: setup dataset-tools
	$(PY) $(S)/dataset2_manual.py --skip-download --validate-only $(DATASET2_FLAGS)

dataset2-status:
	python3 $(S)/dataset2.py status

test-dataset2: setup
	$(PY) -m unittest discover -s tests -p 'test_dataset2.py' -v

prepare-dataset3: setup
	$(PY) $(S)/dataset3.py prepare --root "$(DATASET3_ROOT)" $(DATASET3_FLAGS)

dataset3-status:
	python3 $(S)/dataset3.py status --root "$(DATASET3_ROOT)" $(DATASET3_FLAGS)

test-dataset3: setup
	$(PY) -m unittest discover -s tests -p 'test_dataset3.py' -v
