import csv
import sys
from collections import defaultdict
from pathlib import Path


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


def write_op_line(f, op, data):
    f.write(
        f"{op:<5} "
        f"calls={data[op]['calls']:>8} "
        f"bytes={data[op]['bytes']:>12}\n"
    )


def main():
    if len(sys.argv) not in (2, 3):
        print("usage: python summarize_trace.py TRACE.log [OUTPUT.txt]")
        sys.exit(1)

    trace_path = Path(sys.argv[1])

    if len(sys.argv) == 3:
        out_path = Path(sys.argv[2])
    else:
        out_path = trace_path.with_name(trace_path.stem + "_summary.txt")

    totals    = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "bytes": 0}))
    by_pid    = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "bytes": 0}))
    by_pid_fd = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "bytes": 0}))
    by_path   = defaultdict(lambda: defaultdict(lambda: {"calls": 0, "bytes": 0}))

    fieldnames = ["timestamp", "pid", "op", "fd", "count", "result", "path"]

    with open(trace_path, newline="") as f:
        reader = csv.DictReader(f, fieldnames=fieldnames)

        for row in reader:
            pid    = get_column(row, "pid")
            op     = get_column(row, "op", "operation")
            fd     = get_column(row, "fd")
            result = get_column(row, "result")
            path   = (row.get("path") or "").strip()

            if pid is None or op is None or fd is None or result is None:
                continue

            if op not in ("read", "write"):
                continue

            result = int(result)

            add(totals, "all", op, result)
            add(by_pid, pid, op, result)
            add(by_pid_fd, (pid, fd), op, result)

            if path:
                add(by_path, path, op, result)

    with open(out_path, "w") as f:
        f.write("Totals\n")
        f.write("------\n")
        write_op_line(f, "read", totals["all"])
        write_op_line(f, "write", totals["all"])

        f.write("\nBy PID\n")
        f.write("------\n")
        for pid in sorted(by_pid, key=int):
            data = by_pid[pid]
            f.write(
                f"pid={pid:<6} "
                f"read: calls={data['read']['calls']:>6} bytes={data['read']['bytes']:>10}  "
                f"write: calls={data['write']['calls']:>6} bytes={data['write']['bytes']:>10}\n"
            )

        f.write("\nBy PID and FD\n")
        f.write("-------------\n")
        for pid, fd in sorted(by_pid_fd, key=lambda item: (int(item[0]), int(item[1]))):
            data = by_pid_fd[(pid, fd)]

            if data["read"]["calls"] == 0 and data["write"]["calls"] == 0:
                continue

            f.write(
                f"pid={pid:<6} "
                f"{fd_name(fd):<8} "
                f"read: calls={data['read']['calls']:>6} bytes={data['read']['bytes']:>10}  "
                f"write: calls={data['write']['calls']:>6} bytes={data['write']['bytes']:>10}\n"
            )

        if by_path:
            f.write("\nBy Path\n")
            f.write("-------\n")
            for path in sorted(by_path):
                data = by_path[path]
                f.write(f"{path}\n")
                f.write(
                    f"  read:  calls={data['read']['calls']:>6} "
                    f"bytes={data['read']['bytes']:>10}\n"
                )
                f.write(
                    f"  write: calls={data['write']['calls']:>6} "
                    f"bytes={data['write']['bytes']:>10}\n"
                )

    print(f"Summary written to {out_path}")


if __name__ == "__main__":
    main()
