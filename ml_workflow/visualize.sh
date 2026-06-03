#!/usr/bin/env bash
# Render the heat simulation as an animated GIF with prediction overlays.
# Standalone visualization (no I/O tracing). Output: output/simulation.gif
#
#   ./visualize.sh [--steps N] [--size N] [--alpha F]
#
# Requires gnuplot.
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

OUT="$ROOT/output"
FRAMES="$OUT/frames"

rm -rf "$OUT"
mkdir -p "$FRAMES"

python heat_sim.py --steps "$SIM_STEPS" --size "$SIM_SIZE" --alpha "$SIM_ALPHA" \
    > "$OUT/frames.bin"
python extract_features.py < "$OUT/frames.bin" > "$OUT/features.csv"
python infer.py < "$OUT/features.csv" > "$OUT/predictions_batch.csv"

python dump_frames.py "$FRAMES" < "$OUT/frames.bin"

frame_count=$(find "$FRAMES" -maxdepth 1 -name 'frame_*.dat' | wc -l)
if [[ "$frame_count" -eq 0 ]]; then
    echo "No frames generated" >&2
    exit 1
fi

gnuplot -e "frame_count=$frame_count; output_dir='$OUT'" animate_simulation.gnuplot

echo "Created $OUT/simulation.gif"
