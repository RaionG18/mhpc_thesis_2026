set terminal gif animate delay 8 size 700,700
set output output_dir . "/simulation.gif"

# Variables frame_count and output_dir are passed via -e from visualize.sh
frames_directory = output_dir . "/frames"
predictions_file = output_dir . "/predictions_batch.csv"

unset key
unset xtics
unset ytics
set view map
set size square
set palette rgb 33,13,10
set cbrange [0:1]

do for [i=0:frame_count-1] {
    pred  = system(sprintf("awk -F, 'NR==%d{print $2}' %s", i+2, predictions_file))
    score = system(sprintf("awk -F, 'NR==%d{print $3}' %s", i+2, predictions_file))

    pred_color = (pred eq "hotspot") ? "#ff4444" : "#1ac11a"

    set label 1 sprintf("Frame: %d / %d", i, frame_count-1) \
        at screen 0.03, 0.97 left tc rgb "black" font ",11"
    set label 2 sprintf("t = %d steps", i) \
        at screen 0.03, 0.94 left tc rgb "black" font ",11"
    set label 3 sprintf("%s  (%.4f)", pred, real(score)) \
        at screen 0.03, 0.05 left tc rgb pred_color font ",13"

    plot sprintf("%s/frame_%04d.dat", frames_directory, i) matrix with image

    unset label
}
