import csv
import sys
from collections import defaultdict


def main():
    if len(sys.argv) != 2:
        print("Usage: python observer/summarize_trace.py <trace.log>")
        sys.exit(1)

    totals = defaultdict(lambda: {"calls": 0, "bytes": 0})
    by_pid = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "bytes": 0}))

    with open(sys.argv[1], newline="") as f:
        reader = csv.reader(f)
        for timestamp_ns, pid, op, fd, count, result in reader:
            result = int(result)
            bytes_done = result if result > 0 else 0

            totals[op]["calls"] += 1
            totals[op]["bytes"] += bytes_done
            by_pid[pid][op]["calls"] += 1
            by_pid[pid][op]["bytes"] += bytes_done

    print("Totals")
    print("------")
    for op in sorted(totals):
        print(f"{op:5} calls={totals[op]['calls']:8} bytes={totals[op]['bytes']:12}")

    print()
    print("By PID")
    print("------")
    for pid in sorted(by_pid, key=int):
        parts = []
        for op in sorted(by_pid[pid]):
            stats = by_pid[pid][op]
            parts.append(f"{op}: calls={stats['calls']} bytes={stats['bytes']}")
        print(f"pid={pid}  " + "  ".join(parts))


if __name__ == "__main__":
    main()
