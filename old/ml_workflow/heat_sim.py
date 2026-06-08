import argparse
import struct
import sys
from array import array


def make_grid(n):
    grid = [[0.0 for _ in range(n)] for _ in range(n)]

    c = n // 2
    for y in range(c - 4, c + 5):
        for x in range(c - 4, c + 5):
            grid[y][x] = 1.0

    return grid


def step(grid, alpha):
    n = len(grid)
    new_grid = [[0.0 for _ in range(n)] for _ in range(n)]

    for y in range(1, n - 1):
        for x in range(1, n - 1):
            center = grid[y][x]
            neighbors = (
                grid[y - 1][x]
                + grid[y + 1][x]
                + grid[y][x - 1]
                + grid[y][x + 1]
            )
            new_grid[y][x] = center + alpha * (neighbors - 4.0 * center)

    return new_grid


def write_frame(frame_id, grid):
    n = len(grid)
    sys.stdout.buffer.write(struct.pack("III", frame_id, n, n))

    values = array("f")
    for row in grid:
        values.extend(row)

    values.tofile(sys.stdout.buffer)
    sys.stdout.buffer.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--size", type=int, default=64)
    parser.add_argument("--alpha", type=float, default=0.2)
    args = parser.parse_args()

    grid = make_grid(args.size)

    for frame_id in range(args.steps):
        write_frame(frame_id, grid)
        grid = step(grid, args.alpha)


if __name__ == "__main__":
    main()
