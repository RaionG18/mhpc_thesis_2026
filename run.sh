# !/bin/bash

# Run with varying sizes
./ml_workflow/run.sh --size 32
./ml_workflow/run.sh --size 64
./ml_workflow/run.sh --size 128
./ml_workflow/run.sh --size 256

# Run with varying steps
./ml_workflow/run.sh --size 128 --steps 50
./ml_workflow/run.sh --size 128 --steps 200
./ml_workflow/run.sh --size 128 --steps 400