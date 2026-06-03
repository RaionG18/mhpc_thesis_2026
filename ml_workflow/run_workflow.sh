#!/bin/bash

OUT_DIRECTORY="./output"
FRAME_DIRECTORY="$OUT_DIRECTORY/frames"
PLOT_DIRECTORY="$OUT_DIRECTORY/plots"

if [ -d "$OUT_DIRECTORY" ]; then
    echo "The directory $OUT_DIRECTORY exists!"
else
    echo "Directory not found. Creating it now."
    mkdir -p "$OUT_DIRECTORY"
fi

echo "Running the ML workflow and saving outputs to $OUT_DIRECTORY"
echo "Step 1: Running the heat simulation and saving frames to $OUT_DIRECTORY/frames.bin"
python heat_sim.py --steps 100 --size 64 >$OUT_DIRECTORY/frames.bin

echo "Step 2: Extracting features from frames and saving to $OUT_DIRECTORY/features.csv"
python extract_features.py < $OUT_DIRECTORY/frames.bin > $OUT_DIRECTORY/features.csv

echo "Step 3: Running inference on extracted features and saving predictions to $OUT_DIRECTORY/predictions_batch.csv"
python infer.py < $OUT_DIRECTORY/features.csv > $OUT_DIRECTORY/predictions_batch.csv

echo "Step 4: Dumping frames to directory $OUT_DIRECTORY/frames"
rm -rf $OUT_DIRECTORY/frames
mkdir -p $OUT_DIRECTORY/frames

python dump_frames.py $FRAME_DIRECTORY < $OUT_DIRECTORY/frames.bin

frame_count=$(find $FRAME_DIRECTORY -maxdepth 1 -name 'frame_*.dat' | wc -l)

if [ "$frame_count" -eq 0 ]; then
    echo "No frames found"
    exit 1
fi

echo "Step 5: Creating simulation.gif from dumped frames"
gnuplot -e "frame_count=$frame_count; output_dir='$OUT_DIRECTORY'; plot_dir='$PLOT_DIRECTORY'" animate_simulation.gnuplot

echo "ML workflow completed. Outputs saved to $OUT_DIRECTORY"