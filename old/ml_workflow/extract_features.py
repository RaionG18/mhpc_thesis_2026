import csv
import math
import struct
import sys
from array import array


def read_exact(n):
    data = sys.stdin.buffer.read(n)
    if len(data) == 0:
        return None
    if len(data) != n:
        raise RuntimeError("incomplete frame")
    return data


def read_frame():
    header = read_exact(12)
    if header is None:
        return None

    frame_id, width, height = struct.unpack("III", header)
    count = width * height

    data = read_exact(count * 4)
    values = array("f")
    values.frombytes(data)

    return frame_id, width, height, values


def extract(frame_id, width, height, values):
    count = len(values)

    mean = sum(values) / count
    max_value = max(values)
    variance = sum((v - mean) ** 2 for v in values) / count
    std = math.sqrt(variance)

    threshold = 0.30
    hot_indices = [i for i, v in enumerate(values) if v > threshold]
    hot_area = len(hot_indices)

    if hot_indices:
        center_x = sum(i % width for i in hot_indices) / hot_area
        center_y = sum(i // width for i in hot_indices) / hot_area
    else:
        center_x = -1.0
        center_y = -1.0

    gradient_energy = 0.0
    for y in range(height - 1):
        for x in range(width - 1):
            i = y * width + x
            dx = values[i + 1] - values[i]
            dy = values[i + width] - values[i]
            gradient_energy += dx * dx + dy * dy

    return [
        frame_id,
        mean,
        max_value,
        std,
        hot_area,
        gradient_energy,
        center_x,
        center_y,
    ]


def main():
    writer = csv.writer(sys.stdout)
    writer.writerow([
        "frame_id",
        "mean",
        "max",
        "std",
        "hot_area",
        "gradient_energy",
        "center_x",
        "center_y",
    ])

    while True:
        frame = read_frame()
        if frame is None:
            break

        writer.writerow(extract(*frame))
        sys.stdout.flush()


if __name__ == "__main__":
    main()
