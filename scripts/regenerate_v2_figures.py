#!/usr/bin/env python3
"""基于 eval_valid 主口径重生成 V2 全部图表。"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.metrics_v2 import filter_eval_valid, summarize_v2
from src.visualize import (
    format_model_name,
    plot_accuracy_by_length,
    plot_accuracy_by_length_with_ci,
    plot_depth_accuracy_curve,
    plot_efficiency_tradeoff,
    plot_multihop_by_hops,
    plot_niah_heatmap,
    plot_niah_heatmap_interactive,
    plot_position_bias,
)

FIGURES_DIR = ROOT / "results/v2/figures"
PROCESSED_DIR = ROOT / "results/v2/processed"


def main():
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    matplotlib = __import__("matplotlib")
    matplotlib.rcParams["font.sans-serif"] = [
        "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "SimHei", "Arial Unicode MS",
    ]
    matplotlib.rcParams["axes.unicode_minus"] = False

    scored = PROCESSED_DIR / "scored_results.csv"
    if not scored.exists():
        raise FileNotFoundError("请先运行 scripts/rerun_kimi_v2.py --analyze-only")

    import pandas as pd

    df = pd.read_csv(scored)
    niah = df[df["task"].fillna("niah") == "niah"]
    valid = filter_eval_valid(niah)
    model_summary = summarize_v2(valid)
    length_summary = summarize_v2(valid, group_cols=["model", "context_length"])

    for model in sorted(valid["model"].unique()):
        plot_niah_heatmap(df, model, figures_dir=FIGURES_DIR, eval_valid_only=True)
        plot_niah_heatmap_interactive(df, model, figures_dir=FIGURES_DIR, eval_valid_only=True)

    plot_accuracy_by_length(df, figures_dir=FIGURES_DIR, eval_valid_only=True)
    plot_accuracy_by_length_with_ci(length_summary, figures_dir=FIGURES_DIR)
    plot_position_bias(df, figures_dir=FIGURES_DIR, eval_valid_only=True)
    plot_depth_accuracy_curve(df, figures_dir=FIGURES_DIR, eval_valid_only=True)
    plot_efficiency_tradeoff(model_summary, figures_dir=FIGURES_DIR)

    mh = df[df["task"] == "multi_hop"]
    if not mh.empty:
        plot_multihop_by_hops(mh, figures_dir=FIGURES_DIR)

    plt.close("all")
    print(f"\n🎨 V2 图表已保存至 {FIGURES_DIR}/（主口径: eval_valid）")


if __name__ == "__main__":
    main()
