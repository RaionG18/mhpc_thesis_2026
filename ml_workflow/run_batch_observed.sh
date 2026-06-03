#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

mkdir -p output traces
make -C observer
rm -f output/frames.bin output/features.csv output/predictions_batch.csv traces/batch.log

export LD_PRELOAD="$ROOT/observer/libiotrace.so"
export IOTRACE_LOG="$ROOT/traces/batch.log"

python heat_sim.py --steps 100 --size 64 > output/frames.bin
python extract_features.py < output/frames.bin > output/features.csv
python infer.py < output/features.csv > output/predictions_batch.csv

unset LD_PRELOAD
unset IOTRACE_LOG

echo "Created output/predictions_batch.csv"
echo "Created traces/batch.log"
