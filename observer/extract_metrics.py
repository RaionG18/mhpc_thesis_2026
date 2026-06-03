import argparse
import csv
from datetime import datetime
from pathlib import Path


FIELDNAMES = [
    "run_id", "timestamp",
    "mode", "steps", "size", "elapsed_seconds",
    "total_read_bytes", "total_write_bytes",
    "file_write_bytes", "pipe_write_bytes",
    "read_calls", "write_calls",
]

TRACE_FIELDS = ["timestamp", "pid", "op", "fd", "count", "result", "path"]


def is_pipe(path):
    return not path or path.startswith("pipe:") or path.startswith("socket:")


def parse_trace(trace_path):
    metrics = {
        "total_read_bytes": 0,
        "total_write_bytes": 0,
        "file_write_bytes": 0,
        "pipe_write_bytes": 0,
        "read_calls": 0,
        "write_calls": 0,
    }

    with open(trace_path, newline="") as f:
        reader = csv.DictReader(f, fieldnames=TRACE_FIELDS)
        for row in reader:
            op   = row.get("op", "").strip()
            path = (row.get("path") or "").strip()
            try:
                result = int(row.get("result", 0))
            except ValueError:
                continue

            if result <= 0:
                continue

            if op == "read":
                metrics["total_read_bytes"] += result
                metrics["read_calls"] += 1
            elif op == "write":
                metrics["total_write_bytes"] += result
                metrics["write_calls"] += 1
                if is_pipe(path):
                    metrics["pipe_write_bytes"] += result
                else:
                    metrics["file_write_bytes"] += result

    return metrics


def main():
    parser = argparse.ArgumentParser(
        description="Extract I/O metrics from a trace log and append to a CSV."
    )
    parser.add_argument("trace",      type=Path, help="Trace log file")
    parser.add_argument("--mode",     required=True, help="batch or stream")
    parser.add_argument("--steps",    type=int, required=True)
    parser.add_argument("--size",     type=int, required=True)
    parser.add_argument("--elapsed",  type=float, required=True, help="Wall-clock seconds")
    parser.add_argument("--output",   type=Path, required=True, help="Output CSV file")
    parser.add_argument("--run-id",   required=True, help="Identifier shared by all modes in one run")
    args = parser.parse_args()

    now = datetime.now()
    io_metrics = parse_trace(args.trace)

    row = {
        "run_id":           args.run_id,
        "timestamp":        now.strftime("%Y-%m-%dT%H:%M:%S"),
        "mode":             args.mode,
        "steps":            args.steps,
        "size":             args.size,
        "elapsed_seconds":  round(args.elapsed, 3),
        **io_metrics,
    }

    write_header = not args.output.exists() or args.output.stat().st_size == 0
    with open(args.output, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    print(f"Metrics appended to {args.output}")


if __name__ == "__main__":
    main()
