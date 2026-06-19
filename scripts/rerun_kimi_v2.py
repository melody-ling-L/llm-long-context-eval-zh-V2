#!/usr/bin/env python3
"""删除旧 Kimi NIAH 结果 → 重跑 → 与 DeepSeek/Qwen 合并评分与出图。

用法（在项目根目录）：
    python scripts/rerun_kimi_v2.py          # 重跑 + 评分 + 图表
    python scripts/rerun_kimi_v2.py --analyze-only   # 仅重新评分/出图（raw 已有 kimi）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval_runner_v2 import run_eval_v2
from src.metrics_v2 import (
    filter_eval_valid,
    print_v2_summary_with_status,
    score_results_v2,
    summarize_call_status,
    summarize_v2,
    summarize_variant_matrix,
)

RAW_PATH = ROOT / "results/v2/raw/raw_results.csv"
DATASET_PATH = ROOT / "data/processed/v2/niah_dataset.jsonl"
PROCESSED_DIR = ROOT / "results/v2/processed"
FIGURES_DIR = ROOT / "results/v2/figures"


def _purge_kimi_niah() -> int:
    df = pd.read_csv(RAW_PATH)
    mask = (df["model"] == "kimi") & (df.get("task", "niah").fillna("niah") == "niah")
    removed = int(mask.sum())
    df[~mask].to_csv(RAW_PATH, index=False, encoding="utf-8-sig")
    return removed


def _run_kimi(config: dict) -> None:
    run_eval_v2(
        dataset_path=str(DATASET_PATH),
        model_keys=["kimi"],
        config=config,
        output_dir=str(RAW_PATH.parent),
        resume=True,
    )


def _analyze() -> pd.DataFrame:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    df_raw = pd.read_csv(RAW_PATH)
    if "task" not in df_raw.columns:
        df_raw["task"] = "niah"
    df_raw["task"] = df_raw["task"].fillna("niah")

    df = score_results_v2(df_raw)
    df_niah = df[df["task"] == "niah"].copy()
    df.to_csv(PROCESSED_DIR / "scored_results.csv", index=False, encoding="utf-8-sig")

    model_summary = summarize_v2(df_niah)
    valid_niah = filter_eval_valid(df_niah)
    model_summary_valid = summarize_v2(valid_niah)
    call_status = summarize_call_status(df_niah)
    call_status_by_length = summarize_call_status(df_niah, group_cols=["model", "context_length"])
    variant_summary = summarize_variant_matrix(valid_niah)
    length_summary = summarize_v2(valid_niah, group_cols=["model", "context_length"])

    model_summary.to_csv(PROCESSED_DIR / "summary_by_model.csv", index=False, encoding="utf-8-sig")
    model_summary_valid.to_csv(PROCESSED_DIR / "summary_by_model_niah_valid_only.csv", index=False, encoding="utf-8-sig")
    call_status.to_csv(PROCESSED_DIR / "summary_call_status.csv", index=False, encoding="utf-8-sig")
    call_status_by_length.to_csv(PROCESSED_DIR / "summary_call_status_by_length.csv", index=False, encoding="utf-8-sig")
    variant_summary.to_csv(PROCESSED_DIR / "summary_by_model_variant.csv", index=False, encoding="utf-8-sig")
    length_summary.to_csv(PROCESSED_DIR / "summary_by_model_length.csv", index=False, encoding="utf-8-sig")

    print("\n" + "=" * 72)
    print("三模型 NIAH 对比 — 主口径：eval_valid 有效样本（排除 content_filter / infra 失败）")
    print("=" * 72)
    print(model_summary_valid[["model", "n", "em_pct", "contains_pct", "contains_ci_low_pct", "contains_ci_high_pct"]].to_string(index=False))

    print("\n调用状态：")
    print(call_status.to_string(index=False))

    print("\n按上下文长度（eval_valid）：")
    pivot = length_summary.pivot(index="model", columns="context_length", values="contains_pct").round(1)
    print(pivot.to_string())

    kimi_status = call_status[call_status["model"] == "kimi"]
    if not kimi_status.empty:
        row = kimi_status.iloc[0]
        print(
            f"\nKimi: eval_valid {int(row['eval_valid'])}/{int(row['n'])}，"
            f"content_filter {int(row['content_filter'])}（平台审核，不计入模型能力），"
            f"infra_failed {int(row['infra_api_failed'])}"
        )

    print_v2_summary_with_status(df_niah)

    try:
        import matplotlib
        import matplotlib.pyplot as plt
        from src.visualize import (
            plot_accuracy_by_length,
            plot_accuracy_by_length_with_ci,
            plot_depth_accuracy_curve,
            plot_efficiency_tradeoff,
            plot_multihop_by_hops,
            plot_niah_heatmap,
            plot_niah_heatmap_interactive,
            plot_position_bias,
        )

        matplotlib.rcParams["font.sans-serif"] = [
            "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "SimHei", "Arial Unicode MS",
        ]
        matplotlib.rcParams["axes.unicode_minus"] = False

        for model in sorted(df_niah["model"].unique()):
            plot_niah_heatmap(df_niah, model, save=True, figures_dir=FIGURES_DIR, eval_valid_only=True)
            plot_niah_heatmap_interactive(df_niah, model, save_html=True, figures_dir=FIGURES_DIR, eval_valid_only=True)
            plt.close("all")

        plot_accuracy_by_length(df_niah, save=True, figures_dir=FIGURES_DIR, eval_valid_only=True)
        plot_accuracy_by_length_with_ci(length_summary, save=True, figures_dir=FIGURES_DIR)
        plot_position_bias(df_niah, save=True, figures_dir=FIGURES_DIR, eval_valid_only=True)
        plot_depth_accuracy_curve(df_niah, save=True, figures_dir=FIGURES_DIR, eval_valid_only=True)
        plot_efficiency_tradeoff(model_summary_valid, save=True, figures_dir=FIGURES_DIR)
        mh = df[df["task"] == "multi_hop"]
        if not mh.empty:
            plot_multihop_by_hops(mh, save=True, figures_dir=FIGURES_DIR)
        plt.close("all")
        print(f"✅ 图表: {FIGURES_DIR}")
    except ImportError as exc:
        print(f"⚠️  跳过图表生成（缺少依赖: {exc}），请运行 notebooks/v2/03_analysis_visualization_v2.ipynb")

    print(f"\n✅ 评分: {PROCESSED_DIR / 'scored_results.csv'}")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analyze-only", action="store_true", help="跳过重跑，仅评分与出图")
    args = parser.parse_args()

    config = yaml.safe_load(open(ROOT / "configs/eval_config_v2.yaml", encoding="utf-8"))

    if not args.analyze_only:
        removed = _purge_kimi_niah()
        print(f"已清除旧 Kimi NIAH 行: {removed}")
        print("开始重跑 Kimi（MOONSHOT_API_KEY → moonshot-v1-128k）…")
        _run_kimi(config)

    _analyze()


if __name__ == "__main__":
    main()
