#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

mkdir -p output traces
make -C observer
rm -f output/predictions_stream.csv traces/stream.log

export LD_PRELOAD="$ROOT/observer/libiotrace.so"
export IOTRACE_LOG="$ROOT/traces/stream.log"

python heat_sim.py --steps 100 --size 64 \
    | python extract_features.py \
    | python infer.py \
    > output/predictions_stream.csv

unset LD_PRELOAD
unset IOTRACE_LOG

echo "Created output/predictions_stream.csv"
echo "Created traces/stream.log"
