"""
Generate timeline plots from the CSVs produced by extract_timeline.py.

One experiment = one swept parameter. The quantitative timeline story scales
with the sweep (TTFP and overlap vs the swept parameter, mean ± std across
repetitions); the Gantt is a single illustrative run at the largest value.
Saved to results/plots/ (or --out).

Plots
-----
<sweep>_ttfp       Time-to-first-prediction vs swept parameter
<sweep>_overlap    Stage overlap ratio vs swept parameter
gantt_<sweep><v>   Stage activity over time for one representative run
"""
import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

COLORS = {"batch": "#4C72B0", "stream": "#DD8452"}
MODES  = ["batch", "stream"]
XLABEL = {"size": "Grid size (N×N)", "steps": "Simulation steps"}


def detect_xparam(df):
    sweep = str(df["sweep"].iloc[0])
    if sweep in ("size", "steps"):
        return sweep
    if df["steps"].nunique() > df["size"].nunique():
        return "steps"
    return "size"


def aggregate(df, xparam, col):
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


def stage_colors(stage_names):
    palette = plt.get_cmap("tab10")
    return {name: palette(i % 10) for i, name in enumerate(stage_names)}


def save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path.name}")


# ── Trend plots ──────────────────────────────────────────────────────────────
def plot_ttfp(summary, xparam, out):
    fig, ax = plt.subplots(figsize=(7, 4))
    trend(ax, summary, xparam, "ttfp")
    ax.set_ylabel("Time to first prediction (s)")
    ax.set_title("Time to First Prediction vs Problem Size")
    ax.legend()
    save(fig, out / f"{xparam}_ttfp.png")


def plot_overlap(summary, xparam, out):
    fig, ax = plt.subplots(figsize=(7, 4))
    trend(ax, summary, xparam, "overlap_ratio")
    ax.axhline(1.0, color="black", linestyle=":", linewidth=1,
               label="sequential (=1)")
    ax.set_ylabel("Overlap ratio (busy_sum / wall_clock)")
    ax.set_title("Stage Overlap vs Problem Size")
    ax.legend()
    save(fig, out / f"{xparam}_overlap.png")


# ── Gantt (single representative run) ─────────────────────────────────────────
def plot_gantt(stages, summary, xparam, out):
    value = stages[xparam].max()           # largest problem = most dramatic
    rep = stages[stages[xparam] == value]["rep"].min()
    s_run = stages[(stages[xparam] == value) & (stages["rep"] == rep)]
    sum_run = summary[(summary[xparam] == value) & (summary["rep"] == rep)]

    # Canonical pipeline order: batch runs sequentially, so its start order is
    # the true stage order. Apply it to both panels (stream stages start nearly
    # simultaneously, so sorting stream by start time is noisy).
    order_src = "batch" if "batch" in s_run["mode"].values else s_run["mode"].iloc[0]
    ordered = (s_run[s_run["mode"] == order_src]
               .sort_values("start_offset")["stage"]
               .drop_duplicates().tolist())
    rank = {stage: i for i, stage in enumerate(ordered)}
    colors = stage_colors(ordered)

    modes = [m for m in MODES if m in s_run["mode"].values]
    fig, axes = plt.subplots(len(modes), 1, figsize=(9, 2.2 * len(modes)),
                             sharex=True, squeeze=False)
    axes = axes[:, 0]

    for ax, mode in zip(axes, modes):
        rows = (s_run[s_run["mode"] == mode].copy())
        rows["rank"] = rows["stage"].map(rank)
        rows = rows.sort_values("rank").reset_index(drop=True)
        for y, row in rows.iterrows():
            ax.barh(y, row["end_offset"] - row["start_offset"],
                    left=row["start_offset"], height=0.6,
                    color=colors[row["stage"]], edgecolor="black", linewidth=0.5)
            if pd.notna(row["first_output_offset"]):
                ax.plot(row["first_output_offset"], y, "v", color="black",
                        markersize=6, zorder=5)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels(rows["stage"])
        ax.invert_yaxis()
        ax.set_title(mode.capitalize(), loc="left", fontweight="bold")
        ax.grid(axis="x", alpha=0.3)

        ttfp = sum_run[sum_run["mode"] == mode]["ttfp"]
        if not ttfp.empty and pd.notna(ttfp.iloc[0]):
            ax.axvline(ttfp.iloc[0], color="crimson", linestyle="--", linewidth=1.5)
            ax.text(ttfp.iloc[0], -0.6, f" TTFP={ttfp.iloc[0]:.3f}s",
                    color="crimson", va="bottom", fontsize=8)

    axes[-1].set_xlabel("Time since pipeline start (s)")
    fig.suptitle(f"Stage Timeline — {xparam}={value}\n"
                 "(▼ = first output byte; bars = process lifespan)",
                 fontsize=11)
    fig.tight_layout()
    save(fig, out / f"gantt_{xparam}{value}.png")


def main():
    parser = argparse.ArgumentParser(
        description="Timeline plots from extract_timeline.py output."
    )
    parser.add_argument("results_dir", type=Path,
                        help="Directory containing timeline_*.csv")
    parser.add_argument("--out", type=Path, default=None,
                        help="Output directory (default: <results_dir>/plots)")
    args = parser.parse_args()

    stages_csv  = args.results_dir / "timeline_stages.csv"
    summary_csv = args.results_dir / "timeline_summary.csv"
    if not stages_csv.exists() or not summary_csv.exists():
        print(f"Error: timeline CSVs not found in {args.results_dir}", file=sys.stderr)
        sys.exit(1)

    stages  = pd.read_csv(stages_csv)
    summary = pd.read_csv(summary_csv)
    if summary.empty:
        print("No timeline data.", file=sys.stderr)
        sys.exit(1)

    xparam = detect_xparam(summary)
    out = args.out or args.results_dir / "plots"
    out.mkdir(parents=True, exist_ok=True)

    print(f"Generating timeline plots (sweep={xparam}):")
    plot_ttfp(summary, xparam, out)
    plot_overlap(summary, xparam, out)
    plot_gantt(stages, summary, xparam, out)
    print(f"\nPlots saved to {out}/")


if __name__ == "__main__":
    main()
