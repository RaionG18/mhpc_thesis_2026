import os
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


def write_frame(path, width, height, values):
    with open(path, "w") as f:
        for y in range(height):
            row = values[y * width:(y + 1) * width]
            f.write(" ".join(str(v) for v in row))
            f.write("\n")


def main():

    # Read argument for frames directory
    if len(sys.argv) < 2:
        print("Usage: python dump_frames.py <frames_directory>")
        sys.exit(1)
    frames_directory = sys.argv[1]

    os.makedirs(frames_directory, exist_ok=True)

    while True:
        frame = read_frame()
        if frame is None:
            break

        frame_id, width, height, values = frame
        path = f"{frames_directory}/frame_{frame_id:04d}.dat"
        write_frame(path, width, height, values)


if __name__ == "__main__":
    main()
