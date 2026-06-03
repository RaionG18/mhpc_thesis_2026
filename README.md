# MHPC Thesis: Streaming I/O Observation for HPC/ML Workflows

This repository contains an experimental workflow and I/O observer for studying
how streaming execution affects data movement in HPC/ML-style pipelines.

The current reference workflow is:

```text
2D heat simulation -> feature extraction -> ML inference
```

The same workflow can be executed in two modes:

```text
batch:     simulation -> file -> feature extraction -> file -> inference
streaming: simulation -> pipe -> feature extraction -> pipe -> inference
```

The goal is to compare both modes using traces of `read()`, `write()`,
`open()`, `openat()`, and `close()` operations collected through an
`LD_PRELOAD`-based observer.

## Repository layout

```text
.
├── environment.yml
├── run.sh
├── plot.sh
├── ml_workflow/
│   ├── heat_sim.py
│   ├── extract_features.py
│   ├── infer.py
│   ├── config.sh
│   ├── run.sh
│   ├── dump_frames.py
│   └── animate_simulation.gnuplot
└── observer/
    ├── iotrace.c
    ├── Makefile
    ├── summarize_trace.py
    ├── extract_metrics.py
    └── plot_metrics.py
```

## Requirements

The Python environment is described in `environment.yml`.

```bash
conda env create -f environment.yml
conda activate mhpc_thesis
```

The observer also requires a C compiler and standard Linux development tools:

```bash
gcc
make
```

Optional tools:

```bash
gnuplot
```

`gnuplot` is only needed for the simulation GIF.

## Build the observer

From the repository root:

```bash
make -C observer
```

This builds:

```text
observer/libiotrace.so
```

The shared library is loaded with `LD_PRELOAD` when running the workflow.

## Run one experiment

To run one batch/streaming comparison:

```bash
./ml_workflow/run.sh
```

Default parameters are defined in:

```text
ml_workflow/config.sh
```

Current defaults:

```bash
SIM_STEPS=100
SIM_SIZE=64
SIM_ALPHA=0.2
```

Parameters can be overridden from the command line:

```bash
./ml_workflow/run.sh --steps 100 --size 128 --alpha 0.2
```

The script runs both modes:

```text
batch
stream
```

and produces:

```text
ml_workflow/output/
ml_workflow/traces/
ml_workflow/results/metrics.csv
```

## Run the experiment suite

From the repository root:

```bash
./run.sh
```

This runs multiple experiments with different grid sizes and timestep counts.

## Generate plots

After running experiments:

```bash
./plot.sh
```

The generated plots are saved to:

```text
ml_workflow/results/plots/
```

Current plots include:

```text
01_io_volume.png
02_file_vs_pipe.png
03_elapsed_vs_size.png
04_io_vs_time.png
05_bytes_per_call.png
06_io_growth_loglog.png
```

## Workflow stages

### `heat_sim.py`

Simulates 2D heat diffusion on a square grid.

It writes binary frames to `stdout`. Each frame contains:

```text
frame_id, width, height, float32 temperature matrix
```

Example:

```bash
python ml_workflow/heat_sim.py --steps 100 --size 64 > frames.bin
```

### `extract_features.py`

Reads binary simulation frames from `stdin` and writes CSV features to
`stdout`.

Extracted features include:

```text
mean
max
std
hot_area
gradient_energy
center_x
center_y
```

Example:

```bash
python ml_workflow/extract_features.py < frames.bin > features.csv
```

### `infer.py`

Reads feature rows from `stdin` and writes predictions to `stdout`.

The current inference stage uses a simple fixed linear scoring rule. It is
intentionally lightweight so that the first experiments focus on workflow
behavior and I/O movement rather than model accuracy.

Example:

```bash
python ml_workflow/infer.py < features.csv > predictions.csv
```

## Batch vs streaming execution

Batch mode uses intermediate files:

```bash
python heat_sim.py > output/frames.bin
python extract_features.py < output/frames.bin > output/features.csv
python infer.py < output/features.csv > output/predictions_batch.csv
```

Streaming mode connects stages through pipes:

```bash
python heat_sim.py | python extract_features.py | python infer.py > output/predictions_stream.csv
```

## I/O observer

The observer is implemented in:

```text
observer/iotrace.c
```

It intercepts:

```text
read()
write()
open()
openat()
close()
```

Each trace row has the following structure:

```text
timestamp,pid,op,fd,count,result,path
```

Example:

```text
123456789,1001,write,1,4096,4096,pipe:[12345]
```

The observer also resolves `stdin`, `stdout`, and `stderr` through
`/proc/self/fd`, which helps identify files or pipes opened by the shell
before the process starts.

## Trace summaries

To summarize a trace:

```bash
python observer/summarize_trace.py ml_workflow/traces/batch.log
python observer/summarize_trace.py ml_workflow/traces/stream.log
```

Summaries include:

```text
Totals
By PID
By PID and FD
By Path
```

## Metrics extraction

`extract_metrics.py` converts trace logs into experiment-level metrics and
appends them to `metrics.csv`.

It is called automatically by `ml_workflow/run.sh`.

Metrics include:

```text
elapsed_seconds
total_read_bytes
total_write_bytes
file_write_bytes
pipe_write_bytes
read_calls
write_calls
```

These metrics are used by `plot_metrics.py`.

## Simulation animation

To generate a GIF of the heat simulation, first create `frames.bin`:

```bash
cd ml_workflow
python heat_sim.py --steps 100 --size 64 > frames.bin
```

Convert the binary frames to text matrices:

```bash
python dump_frames.py < frames.bin
```

Then run gnuplot:

```bash
gnuplot -e "frame_count=100" animate_simulation.gnuplot
```

This creates:

```text
simulation.gif
```

## Current limitations

The current observer is intentionally simple.

It does not yet intercept:

```text
pipe()
pipe2()
dup()
dup2()
mmap()
io_uring
direct syscalls that bypass libc wrappers
statically linked binaries
```

It is useful for the current Python-based workflow because the relevant I/O
passes through libc functions that can be intercepted with `LD_PRELOAD`.

## Suggested next steps

The next useful milestone is timeline analysis:

```text
time to first prediction
per-process active intervals
overlap between simulation, feature extraction, and inference
```

This would help quantify not only total runtime and I/O volume, but also the
latency advantage of streaming execution.
