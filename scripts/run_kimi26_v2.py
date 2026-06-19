#!/usr/bin/env python3
"""跑 Kimi 2.6 (kimi2.6-320K) NIAH，并与已有 DeepSeek/Qwen/Kimi 结果合并评分。

用法：
    python scripts/run_kimi26_v2.py              # 全量 350 条 NIAH
    python scripts/run_kimi26_v2.py --smoke    # 单条连通性测试
    python scripts/run_kimi26_v2.py --analyze-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import importlib.util

from src.eval_runner import call_model, get_client
from src.eval_runner_v2 import run_eval_v2


def _analyze():
    spec = importlib.util.spec_from_file_location(
        "rerun_kimi_v2", ROOT / "scripts/rerun_kimi_v2.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._analyze()


def _smoke(config: dict) -> None:
    client, model_name = get_client("kimi26", config)
    ctx = "董事会批准 2025 年资本开支上限为 18.6 亿元，财务部草案曾讨论 17.9 亿元。"
    q = "董事会批准的资本开支上限是多少？"
    text, pt, ct, cache, latency, error = call_model(client, model_name, ctx, q, max_tokens=64)
    if error:
        raise RuntimeError(f"连通性失败: {error}")
    print(f"✅ kimi26 smoke OK — model={model_name}")
    print(f"   回答: {text}")
    print(f"   Prompt: {pt}  Completion: {ct}  Latency: {latency:.2f}s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()

    config = yaml.safe_load(open(ROOT / "configs/eval_config_v2.yaml", encoding="utf-8"))

    if args.smoke:
        _smoke(config)
        return

    if not args.analyze_only:
        print("开始跑 Kimi 2.6 NIAH（kimi2.6-320K @ re.94xy.cn）…")
        run_eval_v2(
            dataset_path=str(ROOT / "data/processed/v2/niah_dataset.jsonl"),
            model_keys=["kimi26"],
            config=config,
            output_dir=str(ROOT / "results/v2/raw"),
            resume=True,
        )

    _analyze()


if __name__ == "__main__":
    main()
