# GREAT / DAC-26

GREAT is a Verilog hardware IP redaction pipeline. It maps RTL to ASAP7,
profiles the design with Ollama, selects and applies redactions, verifies the
result, and produces a report with implementation cost and leakage measurements.

## Run the pipeline

Install Conda and Ollama. Start Ollama and make the selected model available
locally. `GREAT_MODEL` defaults to `qwen3.8:latest`. The ModelSim testbench
stage uses a local ModelSim installation. On a clean checkout, `make asap7`
downloads the standard-cell library.

```sh
make setup
make list-designs
make test
make phase0 DESIGN='-d aes_sbox'
make all DESIGN='-d aes_sbox -d generic_fifos_local'
```

Omit `DESIGN` to process all 42 designs. Individual phase targets run their
prerequisites, so `make report` also runs the earlier phases. Use `make help`
for the main targets. The report and delivered RTL are generated under
`pipeline/report/`. `make clean` removes phase results, reports, testbenches,
and GenAI logs. `make distclean` also clears the LLM cache and setup stamp.

## Benchmark corpus

All 42 pipeline inputs are in [examples/rtl](examples/rtl). The
[design catalog](examples/designs.json) records the evaluated cohort, source
revisions where available, and SHA-256 hashes for the evaluated inputs.

| Cohort | Designs |
| --- | ---: |
| Original benchmarks | 13 |
| OpenCores dataset 1 | 17 |
| OpenCores dataset 2 | 5 |
| Local RTL dataset | 7 |

The OpenCores FIFO uses the ID `generic_fifos`. The independent local FIFO uses
`generic_fifos_local` and retains its original Verilog module name.
`examples/deps/` contains supporting Verilog modules.

[Original benchmark citations](examples/CITATIONS.md) and
[license texts](examples/licenses) cover the original benchmark imports.
Dataset provenance is listed in the catalog. Redistribution terms for the
dataset RTL and a license for the project code still need to be confirmed
before public release.

This bundle contains source files and benchmark inputs. Generated results,
logs, local tool installations, and manuscript artifacts are excluded.
