#!/usr/bin/env bash
# Single run: one (size, steps) point, both batch and stream, one repetition.
# Appends metrics + timeline rows to results/. Does NOT clean results/ — the
# experiment orchestrator (../run.sh) owns the results lifecycle.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

source "$ROOT/config.sh"

SWEEP="manual"   # which parameter the caller is sweeping (size|steps|manual)
REP=1            # repetition index

while [[ $# -gt 0 ]]; do
    case $1 in
        --steps) SIM_STEPS="$2"; shift 2 ;;
        --size)  SIM_SIZE="$2";  shift 2 ;;
        --alpha) SIM_ALPHA="$2"; shift 2 ;;
        --sweep) SWEEP="$2";     shift 2 ;;
        --rep)   REP="$2";       shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

OBSERVER_DIR="$ROOT/../observer"
LIBIOTRACE="$OBSERVER_DIR/libiotrace.so"
RESULTS="$ROOT/results"
METRICS="$RESULTS/metrics.csv"

elapsed_seconds() {
    local start=$1
    local end
    end=$(date +%s%N)
    awk "BEGIN {printf \"%.3f\", ($end - $start) / 1e9}"
}

run_batch() {
    export LD_PRELOAD="$LIBIOTRACE"
    export IOTRACE_LOG="$ROOT/traces/batch.log"

    python heat_sim.py --steps "$SIM_STEPS" --size "$SIM_SIZE" --alpha "$SIM_ALPHA" \
        > output/frames.bin
    python extract_features.py < output/frames.bin > output/features.csv
    python infer.py < output/features.csv > output/predictions_batch.csv

    unset LD_PRELOAD IOTRACE_LOG
}

run_stream() {
    export LD_PRELOAD="$LIBIOTRACE"
    export IOTRACE_LOG="$ROOT/traces/stream.log"

    python heat_sim.py --steps "$SIM_STEPS" --size "$SIM_SIZE" --alpha "$SIM_ALPHA" \
        | python extract_features.py \
        | python infer.py \
        > output/predictions_stream.csv

    unset LD_PRELOAD IOTRACE_LOG
}

make -C "$OBSERVER_DIR" >/dev/null
rm -rf output traces
mkdir -p output traces "$RESULTS"

echo "--- size=$SIM_SIZE steps=$SIM_STEPS rep=$REP (sweep=$SWEEP) ---"

_t0=$(date +%s%N)
run_batch
BATCH_ELAPSED=$(elapsed_seconds "$_t0")

_t0=$(date +%s%N)
run_stream
STREAM_ELAPSED=$(elapsed_seconds "$_t0")

echo "    batch=${BATCH_ELAPSED}s stream=${STREAM_ELAPSED}s"

for mode in batch stream; do
    [[ $mode == batch ]] && elapsed=$BATCH_ELAPSED || elapsed=$STREAM_ELAPSED

    python "$OBSERVER_DIR/extract_metrics.py" "traces/$mode.log" \
        --mode "$mode" --steps "$SIM_STEPS" --size "$SIM_SIZE" \
        --elapsed "$elapsed" --sweep "$SWEEP" --rep "$REP" --output "$METRICS"

    python "$OBSERVER_DIR/extract_timeline.py" "traces/$mode.log" \
        --mode "$mode" --steps "$SIM_STEPS" --size "$SIM_SIZE" \
        --sweep "$SWEEP" --rep "$REP" --results-dir "$RESULTS"
done
