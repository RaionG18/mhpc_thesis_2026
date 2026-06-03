#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

source "$ROOT/config.sh"

OBSERVER_DIR="$ROOT/../observer"
LIBIOTRACE="$OBSERVER_DIR/libiotrace.so"

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
mkdir -p output traces

echo ""
echo "=== Batch ==="
run_batch

echo ""
echo "=== Stream ==="
run_stream

echo ""
echo "=== Summarize ==="
python "$OBSERVER_DIR/summarize_trace.py" traces/batch.log
python "$OBSERVER_DIR/summarize_trace.py" traces/stream.log
