"""
Generate comparison plots from a metrics CSV produced by extract_metrics.py.
Saves all figures to results/plots/ (or --out directory).

Plots
-----
01_io_volume        Total read/write bytes — batch vs stream (latest run)
02_file_vs_pipe     Write destination breakdown — file vs pipe (latest run)
03_elapsed_vs_size  Elapsed time as problem size varies (all runs)
04_io_vs_time       Write volume vs elapsed time scatter (all runs)
05_bytes_per_call   I/O efficiency — bytes per syscall (latest run)
06_io_growth_loglog I/O growth with problem size on log-log scale (all runs)
"""
import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

COLORS = {"batch": "#4C72B0", "stream": "#DD8452"}
MODES  = ["batch", "stream"]

FILE_COLOR = "#4878CF"
PIPE_COLOR = "#E8735A"


def fmt_bytes(v, _=None):
    if v >= 1e9:
        return f"{v/1e9:.1f} GB"
    if v >= 1e6:
        return f"{v/1e6:.1f} MB"
    return f"{v/1e3:.0f} KB"


def load(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["timestamp"])
    df["read_bytes_per_call"]  = (
        df["total_read_bytes"] / df["read_calls"].replace(0, float("nan"))
    )
    df["write_bytes_per_call"] = (
        df["total_write_bytes"] / df["write_calls"].replace(0, float("nan"))
    )
    return df


def latest_run(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["run_id"] == df["run_id"].max()]


def save(fig, path: Path):
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path.name}")


# ── Plot 1 ─────────────────────────────────────────────────────────────────────
def plot_io_volume(df: pd.DataFrame, out: Path):
    data   = latest_run(df)
    cols   = ["total_read_bytes", "total_write_bytes"]
    labels = ["Read", "Write"]
    width  = 0.35
    x      = range(len(cols))

    fig, ax = plt.subplots(figsize=(7, 4))
    for i, mode in enumerate(MODES):
        row = data[data["mode"] == mode]
        if row.empty:
            continue
        vals   = [row.iloc[0][c] for c in cols]
        offset = (i - 0.5) * width
        ax.bar([xi + offset for xi in x], vals, width,
               label=mode.capitalize(), color=COLORS[mode])

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Bytes")
    ax.set_title("Total I/O Volume: Batch vs Stream")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_bytes))
    ax.legend()
    ax.grid(axis="y", alpha=0.4)
    fig.tight_layout()
    save(fig, out / "01_io_volume.png")


# ── Plot 2 ─────────────────────────────────────────────────────────────────────
def plot_file_vs_pipe(df: pd.DataFrame, out: Path):
    data = latest_run(df)

    file_vals, pipe_vals = [], []
    for mode in MODES:
        row = data[data["mode"] == mode]
        file_vals.append(row.iloc[0]["file_write_bytes"] if not row.empty else 0)
        pipe_vals.append(row.iloc[0]["pipe_write_bytes"] if not row.empty else 0)

    mode_labels = [m.capitalize() for m in MODES]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar(mode_labels, file_vals, label="File writes", color=FILE_COLOR)
    ax.bar(mode_labels, pipe_vals, bottom=file_vals, label="Pipe writes",
           color=PIPE_COLOR)

    ax.set_ylabel("Bytes written")
    ax.set_title("Write Destination: File vs Pipe")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_bytes))
    ax.legend()
    ax.grid(axis="y", alpha=0.4)
    fig.tight_layout()
    save(fig, out / "02_file_vs_pipe.png")


# ── Plot 3 ─────────────────────────────────────────────────────────────────────
def plot_elapsed_vs_size(df: pd.DataFrame, out: Path):
    fig, ax = plt.subplots(figsize=(7, 4))
    for mode in MODES:
        sub = (df[df["mode"] == mode]
               .groupby("size")["elapsed_seconds"]
               .mean()
               .reset_index())
        ax.plot(sub["size"], sub["elapsed_seconds"], marker="o",
                label=mode.capitalize(), color=COLORS[mode])

    sizes = sorted(df["size"].unique())
    ax.set_xlabel("Grid size (N×N)")
    ax.set_ylabel("Elapsed time (s)")
    ax.set_title("Scalability: Elapsed Time vs Problem Size")
    if len(sizes) > 1:
        ax.set_xticks(sizes)
    ax.legend()
    ax.grid(alpha=0.4)
    fig.tight_layout()
    save(fig, out / "03_elapsed_vs_size.png")


# ── Plot 4 ─────────────────────────────────────────────────────────────────────
def plot_io_vs_time(df: pd.DataFrame, out: Path):
    fig, ax = plt.subplots(figsize=(6, 4))
    for mode in MODES:
        sub = df[df["mode"] == mode]
        ax.scatter(sub["total_write_bytes"], sub["elapsed_seconds"],
                   label=mode.capitalize(), color=COLORS[mode], alpha=0.8, s=60)

    ax.set_xlabel("Total bytes written")
    ax.set_ylabel("Elapsed time (s)")
    ax.set_title("I/O Volume vs Elapsed Time")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(fmt_bytes))
    ax.legend()
    ax.grid(alpha=0.4)
    fig.tight_layout()
    save(fig, out / "04_io_vs_time.png")


# ── Plot 5 ─────────────────────────────────────────────────────────────────────
def plot_bytes_per_call(df: pd.DataFrame, out: Path):
    data   = latest_run(df)
    cols   = ["read_bytes_per_call", "write_bytes_per_call"]
    labels = ["Read", "Write"]
    width  = 0.35
    x      = range(len(cols))

    fig, ax = plt.subplots(figsize=(7, 4))
    for i, mode in enumerate(MODES):
        row = data[data["mode"] == mode]
        if row.empty:
            continue
        vals   = [row.iloc[0][c] for c in cols]
        offset = (i - 0.5) * width
        ax.bar([xi + offset for xi in x], vals, width,
               label=mode.capitalize(), color=COLORS[mode])

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Bytes per call")
    ax.set_title("I/O Efficiency: Average Bytes per Syscall")
    ax.legend()
    ax.grid(axis="y", alpha=0.4)
    fig.tight_layout()
    save(fig, out / "05_bytes_per_call.png")


# ── Plot 6 ─────────────────────────────────────────────────────────────────────
def plot_io_growth(df: pd.DataFrame, out: Path):
    fig, ax = plt.subplots(figsize=(7, 4))
    for mode in MODES:
        sub = (df[df["mode"] == mode]
               .groupby("size")["total_write_bytes"]
               .mean()
               .reset_index())
        ax.plot(sub["size"], sub["total_write_bytes"], marker="o",
                label=mode.capitalize(), color=COLORS[mode])

    sizes = sorted(df["size"].unique())
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("Grid size (N×N)")
    ax.set_ylabel("Total bytes written")
    ax.set_title("I/O Growth vs Problem Size (log-log)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_bytes))
    if len(sizes) > 1:
        ax.set_xticks(sizes)
        ax.get_xaxis().set_major_formatter(mticker.ScalarFormatter())
    ax.legend()
    ax.grid(alpha=0.4, which="both")
    fig.tight_layout()
    save(fig, out / "06_io_growth_loglog.png")


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Generate plots from a metrics CSV."
    )
    parser.add_argument("metrics", type=Path, help="Path to metrics.csv")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output directory (default: <metrics_dir>/plots)")
    args = parser.parse_args()

    if not args.metrics.exists():
        print(f"Error: {args.metrics} not found", file=sys.stderr)
        sys.exit(1)

    out = args.out or args.metrics.parent / "plots"
    out.mkdir(parents=True, exist_ok=True)

    df = load(args.metrics)
    if df.empty:
        print("No data in metrics file.", file=sys.stderr)
        sys.exit(1)

    print("Generating plots:")
    plot_io_volume(df, out)
    plot_file_vs_pipe(df, out)
    plot_elapsed_vs_size(df, out)
    plot_io_vs_time(df, out)
    plot_bytes_per_call(df, out)
    plot_io_growth(df, out)
    print(f"\nAll plots saved to {out}/")


if __name__ == "__main__":
    main()
