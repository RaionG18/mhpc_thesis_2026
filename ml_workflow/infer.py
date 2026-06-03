import csv
import math
import sys


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def score(row):
    max_temp = float(row["max"])
    hot_area = float(row["hot_area"])
    gradient_energy = float(row["gradient_energy"])

    z = (
        8.0 * max_temp
        + 0.03 * hot_area
        + 0.5 * gradient_energy
        - 5.0
    )

    return sigmoid(z)


def main():
    reader = csv.DictReader(sys.stdin)
    writer = csv.writer(sys.stdout)
    writer.writerow(["frame_id", "prediction", "score"])

    for row in reader:
        s = score(row)
        prediction = "hotspot" if s >= 0.5 else "normal"
        writer.writerow([row["frame_id"], prediction, f"{s:.6f}"])
        sys.stdout.flush()


if __name__ == "__main__":
    main()
