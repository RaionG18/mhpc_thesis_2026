#!/usr/bin/env bash
# Experiment orchestrator: one sweep per experiment.
#
#   ./run.sh                                  # size sweep, default values
#   ./run.sh --sweep size  --values 32,64,128,256 --reps 3
#   ./run.sh --sweep steps --values 50,100,200,400 --size 128
#
# Wipes results/ (one experiment = one clean dataset), runs the chosen sweep
# with repetitions, then regenerates all plots.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

source "$ROOT/ml_workflow/config.sh"

SWEEP="size"
VALUES=""
REPS=3
FIXED_SIZE="$SIM_SIZE"
FIXED_STEPS="$SIM_STEPS"

while [[ $# -gt 0 ]]; do
    case $1 in
        --sweep)  SWEEP="$2";       shift 2 ;;
        --values) VALUES="$2";      shift 2 ;;
        --reps)   REPS="$2";        shift 2 ;;
        --size)   FIXED_SIZE="$2";  shift 2 ;;
        --steps)  FIXED_STEPS="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [[ "$SWEEP" != "size" && "$SWEEP" != "steps" ]]; then
    echo "Error: --sweep must be 'size' or 'steps'" >&2
    exit 1
fi

# Default sweep values if none given.
if [[ -z "$VALUES" ]]; then
    [[ "$SWEEP" == "size" ]] && VALUES="32,64,128,256" || VALUES="50,100,200,400"
fi
IFS=',' read -ra SWEEP_VALUES <<< "$VALUES"

RESULTS="$ROOT/ml_workflow/results"

echo "=== Experiment: sweep=$SWEEP values=$VALUES reps=$REPS ==="
echo "    fixed: size=$FIXED_SIZE steps=$FIXED_STEPS"

echo "=== Clean results ==="
rm -rf "$RESULTS"
mkdir -p "$RESULTS"

echo "=== Build observer ==="
make -C "$ROOT/observer"

echo "=== Sweep ==="
for value in "${SWEEP_VALUES[@]}"; do
    for rep in $(seq 1 "$REPS"); do
        if [[ "$SWEEP" == "size" ]]; then
            ./ml_workflow/run.sh --size "$value" --steps "$FIXED_STEPS" \
                --sweep size --rep "$rep"
        else
            ./ml_workflow/run.sh --size "$FIXED_SIZE" --steps "$value" \
                --sweep steps --rep "$rep"
        fi
    done
done

echo ""
echo "=== Plots ==="
./plot.sh

echo ""
echo "=== Done. Results in $RESULTS ==="
