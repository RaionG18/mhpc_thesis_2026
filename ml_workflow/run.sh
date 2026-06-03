#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

source "$ROOT/config.sh"

while [[ $# -gt 0 ]]; do
    case $1 in
        --steps) SIM_STEPS="$2"; shift 2 ;;
        --size)  SIM_SIZE="$2";  shift 2 ;;
        --alpha) SIM_ALPHA="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

OBSERVER_DIR="$ROOT/../observer"
LIBIOTRACE="$OBSERVER_DIR/libiotrace.so"
METRICS="$ROOT/results/metrics.csv"
RUN_ID=$(date +%Y%m%d_%H%M%S)

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

echo "=== Build ==="
make -C "$OBSERVER_DIR"

echo "=== Clean ==="
rm -rf output traces
mkdir -p output traces results

echo ""
echo "=== Batch (steps=$SIM_STEPS size=$SIM_SIZE alpha=$SIM_ALPHA) ==="
_t0=$(date +%s%N)
run_batch
BATCH_ELAPSED=$(elapsed_seconds "$_t0")
echo "elapsed: ${BATCH_ELAPSED}s"

echo ""
echo "=== Stream (steps=$SIM_STEPS size=$SIM_SIZE alpha=$SIM_ALPHA) ==="
_t0=$(date +%s%N)
run_stream
STREAM_ELAPSED=$(elapsed_seconds "$_t0")
echo "elapsed: ${STREAM_ELAPSED}s"

echo ""
echo "=== Summarize ==="
python "$OBSERVER_DIR/summarize_trace.py" traces/batch.log
python "$OBSERVER_DIR/summarize_trace.py" traces/stream.log

echo ""
echo "=== Metrics ==="
python "$OBSERVER_DIR/extract_metrics.py" traces/batch.log \
    --mode batch --steps "$SIM_STEPS" --size "$SIM_SIZE" --elapsed "$BATCH_ELAPSED" \
    --run-id "$RUN_ID" --output "$METRICS"
python "$OBSERVER_DIR/extract_metrics.py" traces/stream.log \
    --mode stream --steps "$SIM_STEPS" --size "$SIM_SIZE" --elapsed "$STREAM_ELAPSED" \
    --run-id "$RUN_ID" --output "$METRICS"
