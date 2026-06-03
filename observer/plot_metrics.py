"""
Generate trend plots from a metrics CSV produced by extract_metrics.py.

One experiment = one swept parameter (size or steps), so every plot uses that
parameter as the x-axis with batch/stream as series, aggregated across
repetitions (mean ± std error bars). Figures scale naturally as more sweep
values or repetitions are added. Saved to results/plots/ (or --out).

Plots
-----
<sweep>_write_volume   Total bytes written vs swept parameter
<sweep>_file_vs_pipe   Write destination (file vs pipe) vs swept parameter
<sweep>_elapsed        Elapsed wall-clock time vs swept parameter
<sweep>_io_growth      Total bytes written vs swept parameter (log-log)
"""
import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

COLORS = {"batch": "#4C72B0", "stream": "#DD8452"}
MODES  = ["batch", "stream"]
XLABEL = {"size": "Grid size (N×N)", "steps": "Simulation steps"}


def fmt_bytes(v, _=None):
    if v >= 1e9:
        return f"{v/1e9:.1f} GB"
    if v >= 1e6:
        return f"{v/1e6:.1f} MB"
    if v >= 1e3:
        return f"{v/1e3:.0f} KB"
    return f"{v:.0f} B"


def detect_xparam(df):
    sweep = str(df["sweep"].iloc[0])
    if sweep in ("size", "steps"):
        return sweep
    # Fallback (e.g. sweep="manual"): use whichever column actually varies.
    if df["steps"].nunique() > df["size"].nunique():
        return "steps"
    return "size"


def aggregate(df, xparam, col):
    """Mean/std of `col` per (mode, xparam) across repetitions."""
    g = (df.groupby(["mode", xparam])[col]
         .agg(["mean", "std"])
         .reset_index())
    g["std"] = g["std"].fillna(0.0)
    return g


def trend(ax, df, xparam, col):
    for mode in MODES:
        g = aggregate(df[df["mode"] == mode], xparam, col).sort_values(xparam)
        if g.empty:
            continue
        ax.errorbar(g[xparam], g["mean"], yerr=g["std"], marker="o",
                    capsize=3, label=mode.capitalize(), color=COLORS[mode])
    ax.set_xlabel(XLABEL.get(xparam, xparam))
    ax.grid(alpha=0.4)


def save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path.name}")


# ── Plots ──────────────────────────────────────────────────────────────────────
def plot_write_volume(df, xparam, out):
    fig, ax = plt.subplots(figsize=(7, 4))
    trend(ax, df, xparam, "total_write_bytes")
    ax.set_ylabel("Total bytes written")
    ax.set_title("Write Volume vs Problem Size")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_bytes))
    ax.legend()
    save(fig, out / f"{xparam}_write_volume.png")


def plot_file_vs_pipe(df, xparam, out):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, mode in zip(axes, MODES):
        sub = df[df["mode"] == mode]
        for col, color, label in [
            ("file_write_bytes", "#4878CF", "File"),
            ("pipe_write_bytes", "#E8735A", "Pipe"),
        ]:
            g = aggregate(sub, xparam, col).sort_values(xparam)
            if g.empty:
                continue
            ax.errorbar(g[xparam], g["mean"], yerr=g["std"], marker="o",
                        capsize=3, label=label, color=color)
        ax.set_title(mode.capitalize())
        ax.set_xlabel(XLABEL.get(xparam, xparam))
        ax.grid(alpha=0.4)
        ax.legend()
    axes[0].set_ylabel("Bytes written")
    axes[0].yaxis.set_major_formatter(mticker.FuncFormatter(fmt_bytes))
    fig.suptitle("Write Destination: File vs Pipe")
    fig.tight_layout()
    save(fig, out / f"{xparam}_file_vs_pipe.png")


def plot_elapsed(df, xparam, out):
    fig, ax = plt.subplots(figsize=(7, 4))
    trend(ax, df, xparam, "elapsed_seconds")
    ax.set_ylabel("Elapsed time (s)")
    ax.set_title("Wall-clock Time vs Problem Size")
    ax.legend()
    save(fig, out / f"{xparam}_elapsed.png")


def plot_io_growth(df, xparam, out):
    fig, ax = plt.subplots(figsize=(7, 4))
    trend(ax, df, xparam, "total_write_bytes")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_ylabel("Total bytes written")
    ax.set_title("I/O Growth vs Problem Size (log-log)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt_bytes))
    xs = sorted(df[xparam].unique())
    if len(xs) > 1:
        ax.set_xticks(xs)
        ax.get_xaxis().set_major_formatter(mticker.ScalarFormatter())
    ax.legend()
    save(fig, out / f"{xparam}_io_growth.png")


def main():
    parser = argparse.ArgumentParser(description="Trend plots from a metrics CSV.")
    parser.add_argument("metrics", type=Path, help="Path to metrics.csv")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output directory (default: <metrics_dir>/plots)")
    args = parser.parse_args()

    if not args.metrics.exists():
        print(f"Error: {args.metrics} not found", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(args.metrics)
    if df.empty:
        print("No data in metrics file.", file=sys.stderr)
        sys.exit(1)

    xparam = detect_xparam(df)
    out = args.out or args.metrics.parent / "plots"
    out.mkdir(parents=True, exist_ok=True)

    print(f"Generating metric plots (sweep={xparam}):")
    plot_write_volume(df, xparam, out)
    plot_file_vs_pipe(df, xparam, out)
    plot_elapsed(df, xparam, out)
    plot_io_growth(df, xparam, out)
    print(f"\nPlots saved to {out}/")


if __name__ == "__main__":
    main()
