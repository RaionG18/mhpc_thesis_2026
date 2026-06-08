"""
Reconstruct a per-process timeline from a trace log and derive timeline
metrics: time-to-first-prediction (TTFP) and stage overlap.

Each pipeline stage is a separate process (PID). The trace's `start`/`exit`
events (emitted by libiotrace's constructor/destructor) bound each process's
lifespan, and the `start` event carries the command line so we can map a PID
to its stage. CLOCK_MONOTONIC is system-wide on Linux, so timestamps from
different processes are directly comparable.

Outputs (appended within one experiment):
  <results-dir>/timeline_stages.csv   one row per stage per run
  <results-dir>/timeline_summary.csv  one row per run
"""
import argparse
import csv
from pathlib import Path

TRACE_FIELDS = ["timestamp", "pid", "op", "fd", "count", "result", "path"]

STAGE_FIELDS = [
    "sweep", "rep", "mode", "size", "steps", "stage", "pid",
    "start_offset", "end_offset", "duration",
    "first_output_offset", "first_row_offset",
]

SUMMARY_FIELDS = [
    "sweep", "rep", "mode", "size", "steps", "n_stages",
    "ttfp", "ttfp_first_row",
    "wall_clock", "busy_sum", "overlap_ratio", "max_concurrency",
]

NS_PER_S = 1e9


def stage_from_cmdline(cmd):
    """Derive a stage name from a command line, e.g.
    'python heat_sim.py --steps 100' -> 'heat_sim'. Generic across workflows:
    picks the first argument that looks like a script."""
    tokens = cmd.split()
    for tok in tokens:
        if tok.endswith(".py"):
            return Path(tok).stem
    return tokens[-1] if tokens else "unknown"


def parse_trace(trace_path):
    """Return {pid: {start_ts, end_ts, first_ts, last_ts, cmd, stdout_writes}}."""
    procs = {}

    with open(trace_path, newline="") as f:
        reader = csv.DictReader(f, fieldnames=TRACE_FIELDS)
        for row in reader:
            pid = row.get("pid")
            op  = (row.get("op") or "").strip()
            if pid is None or not op:
                continue

            try:
                ts = int(row["timestamp"])
            except (TypeError, ValueError):
                continue

            p = procs.setdefault(pid, {
                "start_ts": None, "end_ts": None,
                "first_ts": ts, "last_ts": ts,
                "cmd": "", "stdout_writes": [],
            })
            p["first_ts"] = min(p["first_ts"], ts)
            p["last_ts"]  = max(p["last_ts"], ts)

            if op == "start":
                p["start_ts"] = ts
                p["cmd"] = (row.get("path") or "").strip()
            elif op == "exit":
                p["end_ts"] = ts
            elif op == "write":
                try:
                    result = int(row["result"])
                except (TypeError, ValueError):
                    continue
                if row.get("fd") == "1" and result > 0:
                    p["stdout_writes"].append(ts)

    return procs


def build_stages(procs):
    """Keep only pipeline stages (processes whose cmdline names a script),
    resolving start/end timestamps with sensible fallbacks."""
    stages = []
    for pid, p in procs.items():
        if not p["cmd"] or ".py" not in p["cmd"]:
            continue
        start = p["start_ts"] if p["start_ts"] is not None else p["first_ts"]
        end   = p["end_ts"]   if p["end_ts"]   is not None else p["last_ts"]
        writes = sorted(p["stdout_writes"])
        stages.append({
            "pid": pid,
            "stage": stage_from_cmdline(p["cmd"]),
            "start": start,
            "end": end,
            "first_output": writes[0] if writes else None,
            "first_row": writes[1] if len(writes) > 1 else None,
        })
    return stages


def max_concurrency(intervals):
    """Maximum number of stages simultaneously active (sweep line)."""
    events = []
    for start, end in intervals:
        events.append((start, 1))
        events.append((end, -1))
    events.sort(key=lambda e: (e[0], -e[1]))

    current = peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def main():
    parser = argparse.ArgumentParser(
        description="Extract timeline metrics (TTFP, overlap) from a trace log."
    )
    parser.add_argument("trace",         type=Path, help="Trace log file")
    parser.add_argument("--mode",        required=True, help="batch or stream")
    parser.add_argument("--size",        type=int, required=True)
    parser.add_argument("--steps",       type=int, required=True)
    parser.add_argument("--sweep",       required=True, help="Swept parameter name (size|steps)")
    parser.add_argument("--rep",         type=int, default=1, help="Repetition index")
    parser.add_argument("--results-dir", type=Path, default=Path("results"),
                        help="Directory for timeline_stages.csv / timeline_summary.csv")
    args = parser.parse_args()

    procs = parse_trace(args.trace)
    stages = build_stages(procs)

    if not stages:
        print(f"Warning: no pipeline stages found in {args.trace}")
        return

    t0 = min(s["start"] for s in stages)

    def offset(ts):
        return None if ts is None else round((ts - t0) / NS_PER_S, 6)

    # Final stage = last to finish (in a pipeline it consumes everything else).
    final_stage = max(stages, key=lambda s: s["end"])

    args.results_dir.mkdir(parents=True, exist_ok=True)
    stages_csv  = args.results_dir / "timeline_stages.csv"
    summary_csv = args.results_dir / "timeline_summary.csv"

    # ── Per-stage rows ──────────────────────────────────────────────────────
    write_header = not stages_csv.exists() or stages_csv.stat().st_size == 0
    with open(stages_csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=STAGE_FIELDS)
        if write_header:
            writer.writeheader()
        for s in sorted(stages, key=lambda s: s["start"]):
            writer.writerow({
                "sweep":               args.sweep,
                "rep":                 args.rep,
                "mode":                args.mode,
                "size":                args.size,
                "steps":               args.steps,
                "stage":               s["stage"],
                "pid":                 s["pid"],
                "start_offset":        offset(s["start"]),
                "end_offset":          offset(s["end"]),
                "duration":            round((s["end"] - s["start"]) / NS_PER_S, 6),
                "first_output_offset": offset(s["first_output"]),
                "first_row_offset":    offset(s["first_row"]),
            })

    # ── Summary row ─────────────────────────────────────────────────────────
    intervals  = [(s["start"], s["end"]) for s in stages]
    durations  = [(end - start) / NS_PER_S for start, end in intervals]
    wall_clock = (max(e for _, e in intervals) - t0) / NS_PER_S
    busy_sum   = sum(durations)

    summary = {
        "sweep":           args.sweep,
        "rep":             args.rep,
        "mode":            args.mode,
        "size":            args.size,
        "steps":           args.steps,
        "n_stages":        len(stages),
        "ttfp":            offset(final_stage["first_output"]),
        "ttfp_first_row":  offset(final_stage["first_row"]),
        "wall_clock":      round(wall_clock, 6),
        "busy_sum":        round(busy_sum, 6),
        "overlap_ratio":   round(busy_sum / wall_clock, 4) if wall_clock > 0 else 0,
        "max_concurrency": max_concurrency(intervals),
    }

    write_header = not summary_csv.exists() or summary_csv.stat().st_size == 0
    with open(summary_csv, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(summary)

    print(f"Timeline written: {stages_csv.name}, {summary_csv.name}  "
          f"(mode={args.mode}, ttfp={summary['ttfp']}s, "
          f"overlap={summary['overlap_ratio']})")


if __name__ == "__main__":
    main()
