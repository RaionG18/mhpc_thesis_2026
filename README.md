# MHPC Thesis: I/O Interception for Streaming HPC/ML Workflows

This repository supports a thesis project about **intercepting I/O operations
in communicating processes** in order to study when streaming execution can
improve workflow behavior.

The project started from the following research direction:

> In streaming workflows, we can work on a way to intercept I/O operations of
> communicating processes and study how streaming can improve performance, or
> extend the interception logic to modern asynchronous I/O methods like
> `io_uring`.

This repository is the first experimental step toward that goal.

## Thesis direction

Modern HPC/ML workflows are often built from multiple communicating stages:

```text
simulation -> preprocessing -> feature extraction -> ML inference/training
```

These stages may communicate through files, pipes, sockets, or modern
asynchronous I/O mechanisms. In many workflows, stages exchange data through
complete intermediate files. That execution style is simple, but it may delay
downstream stages and create unnecessary storage traffic.

The broader thesis problem is:

> Can we observe I/O operations between communicating processes without
> modifying the workflow code, reconstruct how data moves through the
> workflow, and use that information to identify and evaluate opportunities
> for streaming execution?

## Main thesis question

**How can application-transparent I/O interception be used to observe
communication between processes in HPC/ML workflows, and to evaluate whether
replacing file-based intermediate exchange with streaming communication
improves performance, latency, or storage behavior?**

This question keeps the original focus on **I/O interception**. Streaming is
the optimization opportunity being studied, not the whole thesis by itself.

## Secondary research direction

A later extension of this work is:

**What changes are required for the interception logic to support modern
asynchronous I/O interfaces such as `io_uring`, where operations are submitted
and completed through shared queues rather than simple blocking `read()` and
`write()` calls?**

The current repository does not implement `io_uring` support yet. It builds
the baseline observer and experimental workflow needed before that extension.

## Research hypotheses

The current project is guided by three hypotheses:

1. **Passive I/O interception can reveal producer-consumer relationships**
   between stages of a multi-process HPC/ML workflow.

2. **Streaming execution can reduce intermediate file I/O and time to first
   useful result**, even when the total amount of processed data is unchanged.

3. **The same interception model will need to change for asynchronous I/O**,
   because interfaces such as `io_uring` separate operation submission,
   execution, and completion.

## Role of the current workflow

The workflow in this repository is not the final research contribution by
itself. It is a **controlled benchmark** used to test the observer.

The reference workflow is:

```text
2D heat simulation -> feature extraction -> ML inference
```

It was chosen because it resembles an HPC/ML pipeline:

- a simulation produces data over timesteps;
- a feature extractor reduces simulation fields into smaller ML inputs;
- an inference stage consumes those features and emits predictions;
- the workflow can be executed either through files or through pipes.

This gives us a simple way to compare two communication patterns:

```text
batch:     simulation -> file -> feature extraction -> file -> inference
streaming: simulation -> pipe -> feature extraction -> pipe -> inference
```

The observer should be able to detect this difference from I/O behavior.

## What this repository currently implements

This repository currently contains:

- an HPC/ML-style reference workflow;
- batch and streaming versions of the same workflow;
- an `LD_PRELOAD`-based I/O observer;
- I/O metrics extraction from traces (bytes and calls, file vs pipe);
- timeline analysis: time to first prediction and stage overlap;
- trend plots that scale across a parameter sweep.

## What this repository is testing

The current experiments test whether the observer can answer questions such
as:

- Which processes communicate through files?
- Which processes communicate through pipes?
- How many bytes are read and written by each stage?
- How much I/O goes through intermediate files in batch mode?
- How much I/O goes through pipes in streaming mode?
- Does streaming reduce elapsed time?
- Does streaming produce results earlier?
- Does streaming increase the number of smaller `read()` calls?

These questions are stepping stones toward a more general I/O interception
system for communicating workflows.

## What this repository is not doing yet

The current code does not yet:

- automatically transform a batch workflow into a streaming workflow;
- reconstruct full pipe topology using `pipe()`, `dup()`, and `dup2()`;
- support `io_uring`;
- intercept `mmap()`;
- trace statically linked binaries;
- handle direct syscalls that bypass libc wrappers;
- provide a complete system-wide tracer.

These limitations are intentional at this stage. The current goal is to
establish a minimal, measurable baseline.

## Repository layout

```text
.
├── environment.yml
├── run.sh                      # experiment orchestrator (one sweep per run)
├── plot.sh                     # regenerate all plots from results/
├── ml_workflow/
│   ├── heat_sim.py
│   ├── extract_features.py
│   ├── infer.py
│   ├── config.sh               # default sweep parameters
│   ├── run.sh                  # single run (one size/steps point, batch + stream)
│   ├── visualize.sh            # render simulation GIF (optional, needs gnuplot)
│   ├── dump_frames.py
│   └── animate_simulation.gnuplot
└── observer/
    ├── iotrace.c
    ├── Makefile
    ├── extract_metrics.py
    ├── extract_timeline.py
    ├── plot_metrics.py
    └── plot_timeline.py
```

`ml_workflow/results/` holds generated CSVs and plots. It is wiped at the start
of every experiment and is git-ignored.

## Reference workflow

### 1. Heat simulation

`ml_workflow/heat_sim.py` simulates 2D heat diffusion on a square grid.

It emits one binary frame per timestep:

```text
frame_id, width, height, float32 temperature matrix
```

Example:

```bash
python ml_workflow/heat_sim.py --steps 100 --size 64 > frames.bin
```

### 2. Feature extraction

`ml_workflow/extract_features.py` reads simulation frames and emits one CSV
row of features per frame.

Current features include:

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

### 3. ML inference

`ml_workflow/infer.py` reads feature rows and emits predictions.

The current inference stage uses a lightweight fixed scoring rule. This keeps
the first experiments focused on workflow behavior and I/O movement rather
than model quality.

Example:

```bash
python ml_workflow/infer.py < features.csv > predictions.csv
```

## Execution modes

### Batch mode

Batch mode writes complete intermediate files before the next stage runs:

```bash
python heat_sim.py > output/frames.bin
python extract_features.py < output/frames.bin > output/features.csv
python infer.py < output/features.csv > output/predictions_batch.csv
```

### Streaming mode

Streaming mode connects stages with pipes:

```bash
python heat_sim.py | python extract_features.py | python infer.py > output/predictions_stream.csv
```

In the thesis, this difference is used to test whether the observer can
distinguish file-based communication from streaming communication.

## Requirements

Create the Python environment:

```bash
conda env create -f environment.yml
conda activate mhpc_thesis
```

Build tools required for the observer:

```bash
gcc
make
```

Optional:

```bash
gnuplot
```

`gnuplot` is only needed for generating the simulation GIF.

## Build the observer

From the repository root:

```bash
make -C observer
```

This builds:

```text
observer/libiotrace.so
```

The workflow scripts load this library with `LD_PRELOAD`.

## Run an experiment

The main entry point is the experiment orchestrator at the repository root.
**One experiment = one swept parameter**, run with repetitions. It wipes
`ml_workflow/results/`, runs the sweep in both batch and streaming modes, and
regenerates all plots:

```bash
./run.sh                                          # size sweep, 3 reps (default)
./run.sh --sweep size  --values 32,64,128,256 --reps 3
./run.sh --sweep steps --values 50,100,200,400 --size 128
```

Default parameters live in `ml_workflow/config.sh`:

```bash
SIM_STEPS=100
SIM_SIZE=64
SIM_ALPHA=0.2
```

Results accumulate (within the one experiment) into:

```text
ml_workflow/results/metrics.csv
ml_workflow/results/timeline_stages.csv
ml_workflow/results/timeline_summary.csv
ml_workflow/results/plots/
```

### Single run

To run one parameter point (both modes, one repetition) without a sweep — for
a quick check — use the single-run script. It appends to `results/` without
cleaning it:

```bash
./ml_workflow/run.sh --size 128 --steps 100
```

## Generate plots

`run.sh` invokes `plot.sh` automatically. To regenerate plots from the current
`results/` without re-running the experiment:

```bash
./plot.sh
```

Plots are written to `ml_workflow/results/plots/`. Each one uses the swept
parameter as the x-axis with batch/stream as series, aggregated across
repetitions (mean ± std error bars):

- `<sweep>_write_volume` — total bytes written;
- `<sweep>_file_vs_pipe` — file vs pipe write traffic;
- `<sweep>_elapsed` — wall-clock time;
- `<sweep>_io_growth` — bytes written (log-log);
- `<sweep>_ttfp` — time to first prediction;
- `<sweep>_overlap` — stage overlap ratio;
- `gantt_<sweep><value>` — stage timeline for one representative run.

## I/O observer

The observer is implemented in:

```text
observer/iotrace.c
```

It currently intercepts:

```text
read()
write()
open()
openat()
close()
```

Each trace row records:

```text
timestamp,pid,op,fd,count,result,path
```

Example:

```text
123456789,1001,write,1,4096,4096,pipe:[12345]
```

The observer also resolves `stdin`, `stdout`, and `stderr` using
`/proc/self/fd`, which helps identify files and pipes opened by the shell
before the Python process starts.

In addition, it emits `start` and `exit` pseudo-events per process. The `start`
event carries the process command line (read from `/proc/self/cmdline`), which
lets the timeline analysis bound each process's lifespan and map it to its
pipeline stage.

## Metrics extraction

`observer/extract_metrics.py` converts a trace into one experiment-level row
per (mode). Each row records the sweep context and the I/O metrics:

```text
sweep, rep, mode, steps, size, elapsed_seconds,
total_read_bytes, total_write_bytes,
file_write_bytes, pipe_write_bytes,
read_calls, write_calls
```

Rows are appended to `ml_workflow/results/metrics.csv` and plotted by
`observer/plot_metrics.py`.

## Timeline analysis

`observer/extract_timeline.py` reconstructs a per-process timeline from a
trace. Because each pipeline stage is a separate process and the observer emits
`start`/`exit` events with the command line, it can bound and identify each
stage. It derives:

- **time to first prediction (TTFP)** — when the final stage produces its first
  output byte;
- **stage overlap ratio** — `busy_sum / wall_clock` (≈1 for sequential batch,
  >1 for pipelined streaming);
- **max concurrency** — peak number of simultaneously active stages.

Output goes to `ml_workflow/results/timeline_stages.csv` and
`timeline_summary.csv`, and is plotted by `observer/plot_timeline.py`.

## Simulation animation

To render the heat simulation as an animated GIF with prediction overlays
(requires `gnuplot`):

```bash
./ml_workflow/visualize.sh --steps 100 --size 64
```

This creates `ml_workflow/output/simulation.gif`.

## Next milestones

The next milestones should reconnect directly to the original thesis idea:

1. **Timeline analysis** ✅ *(done)*  
   Measures time to first prediction and overlap between workflow stages.

2. **Communication reconstruction**  
   Intercept `pipe()`, `pipe2()`, `dup()`, and `dup2()` to reconstruct which
   process writes to which process.

3. **Streaming opportunity detection**  
   Detect patterns where one process writes an intermediate file that another
   process later reads sequentially, which suggests a possible streaming
   replacement.

4. **Asynchronous I/O extension**  
   Study how the observer would need to change for `io_uring`, where I/O
   operations are submitted asynchronously and completions are observed later.

## Current thesis framing

A concise version of the thesis framing is:

> This thesis investigates application-transparent I/O interception as a way
> to observe communication between processes in HPC/ML workflows, identify
> file-based producer-consumer patterns that may benefit from streaming
> execution, and establish a path toward supporting modern asynchronous I/O
> mechanisms such as `io_uring`.
