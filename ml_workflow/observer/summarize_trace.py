import csv
import sys
from collections import defaultdict


def fd_name(fd):
    names = {
        "0": "stdin",
        "1": "stdout",
        "2": "stderr",
    }
    return names.get(fd, f"fd={fd}")


def get_column(row, *names):
    for name in names:
        if name in row:
            return row[name]
    return None


def add(stats, key, op, result):
    if result <= 0:
        return

    stats[key][op]["calls"] += 1
    stats[key][op]["bytes"] += result


def print_op_line(op, data):
    print(
        f"{op:<5} "
        f"calls={data[op]['calls']:>8} "
        f"bytes={data[op]['bytes']:>12}"
    )


def main():
    if len(sys.argv) != 2:
        print("usage: python summarize_trace.py TRACE.log")
        sys.exit(1)

    trace_path = sys.argv[1]

    totals = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "bytes": 0}))
    by_pid = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "bytes": 0}))
    by_pid_fd = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "bytes": 0}))

    with open(trace_path, newline="") as f:
        reader = csv.DictReader(
            f, fieldnames=["timestamp", "pid", "op", "fd", "count", "result"]
        )

        for row in reader:
            pid = get_column(row, "pid")
            op = get_column(row, "operation", "op")
            fd = get_column(row, "fd")
            result = get_column(row, "result")

            if pid is None or op is None or fd is None or result is None:
                continue

            result = int(result)

            add(totals, "all", op, result)
            add(by_pid, pid, op, result)
            add(by_pid_fd, (pid, fd), op, result)

    print("Totals")
    print("------")
    print_op_line("read", totals["all"])
    print_op_line("write", totals["all"])

    print()
    print("By PID")
    print("------")
    for pid in sorted(by_pid, key=int):
        data = by_pid[pid]
        print(
            f"pid={pid:<6} "
            f"read: calls={data['read']['calls']:>6} bytes={data['read']['bytes']:>10}  "
            f"write: calls={data['write']['calls']:>6} bytes={data['write']['bytes']:>10}"
        )

    print()
    print("By PID and FD")
    print("-------------")
    for pid, fd in sorted(by_pid_fd, key=lambda item: (int(item[0]), int(item[1]))):
        data = by_pid_fd[(pid, fd)]

        if data["read"]["calls"] == 0 and data["write"]["calls"] == 0:
            continue

        print(
            f"pid={pid:<6} "
            f"{fd_name(fd):<8} "
            f"read: calls={data['read']['calls']:>6} bytes={data['read']['bytes']:>10}  "
            f"write: calls={data['write']['calls']:>6} bytes={data['write']['bytes']:>10}"
        )


if __name__ == "__main__":
    main()
