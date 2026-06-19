#!/usr/bin/env python3
"""补跑 Kimi multi_hop（32 条）并刷新评分汇总与图表。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.eval_runner_v2 import run_eval_v2
from src.metrics_v2 import score_results_v2, summarize_v2

DATASET = ROOT / "data/processed/v2/multihop_dataset.jsonl"
RAW_PATH = ROOT / "results/v2/raw/raw_results.csv"
PROCESSED = ROOT / "results/v2/processed"


def main() -> int:
    if not DATASET.exists():
        raise FileNotFoundError(
            "缺少 multi_hop 数据集，请先运行: python src/data_prep_v2.py"
        )

    config = yaml.safe_load(open(ROOT / "configs/eval_config_v2.yaml", encoding="utf-8"))
    print("🚀 补跑 Kimi multi_hop...")
    run_eval_v2(
        dataset_path=str(DATASET),
        model_keys=["kimi"],
        config=config,
        output_dir=str(RAW_PATH.parent),
        resume=True,
    )

    df = score_results_v2(pd.read_csv(RAW_PATH))
    df.to_csv(PROCESSED / "scored_results.csv", index=False, encoding="utf-8-sig")
    mh = df[df["task"] == "multi_hop"]
    summarize_v2(mh, group_cols=["model", "hops"]).to_csv(
        PROCESSED / "summary_multihop_by_hops.csv", index=False, encoding="utf-8-sig"
    )
    summarize_v2(df, group_cols=["model", "task"]).to_csv(
        PROCESSED / "summary_by_model_task.csv", index=False, encoding="utf-8-sig"
    )

    subprocess.run([sys.executable, str(ROOT / "scripts/regenerate_v2_figures.py")], check=True)
    print("✅ Kimi multi_hop 完成，汇总与图表已更新")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
