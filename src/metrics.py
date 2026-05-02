"""
指标计算模块

提供：
- normalize_answer()     标准化文本
- exact_match()          精确匹配
- contains_match()       包含匹配（更宽松，推荐主指标）
- score_results()        为整个 DataFrame 打分
- aggregate_by_position()  按 context_length × depth_pct 聚合
- aggregate_by_model()     按模型 × context_length 聚合
- print_summary()          控制台摘要输出
"""

import re
from pathlib import Path

import pandas as pd


# ──────────────────────────────────────────────
# 字符串标准化
# ──────────────────────────────────────────────

def normalize_answer(text: str) -> str:
    """去除空白、标点，统一半角，便于比较。"""
    if not isinstance(text, str):
        text = str(text)
    text = text.strip()
    # 全角→半角数字/字母
    text = text.translate(
        str.maketrans(
            "０１２３４５６７８９ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
            "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
            "0123456789abcdefghijklmnopqrstuvwxyz"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        )
    )
    # 移除所有空白
    text = re.sub(r"\s+", "", text)
    return text


# ──────────────────────────────────────────────
# 单样本评分
# ──────────────────────────────────────────────

def exact_match(prediction: str, ground_truth: str) -> int:
    """严格匹配：标准化后完全相同才得 1 分。"""
    return int(normalize_answer(prediction) == normalize_answer(ground_truth))


def contains_match(prediction: str, ground_truth: str) -> int:
    """宽松匹配：ground_truth 出现在 prediction 中即得 1 分。"""
    return int(normalize_answer(ground_truth) in normalize_answer(prediction))


# ──────────────────────────────────────────────
# DataFrame 批量评分
# ──────────────────────────────────────────────

def score_results(df: pd.DataFrame) -> pd.DataFrame:
    """
    为 DataFrame 每行添加 em_score 和 contains_score 列。

    输入 DataFrame 需要包含：
        model_response, expected_answer
    """
    df = df.copy()
    df["em_score"] = df.apply(
        lambda r: exact_match(str(r["model_response"]), str(r["expected_answer"])),
        axis=1,
    )
    df["contains_score"] = df.apply(
        lambda r: contains_match(str(r["model_response"]), str(r["expected_answer"])),
        axis=1,
    )
    return df


# 各模型单价（¥ / 1M tokens），区分 prompt / completion / cached
_PRICE_TABLE = {
    # (prompt, completion, cached)
    "deepseek": (1.0,   2.0,  0.1),
    "kimi":     (60.0, 60.0, 60.0),   # moonshot-v1-128k 实际价格
    "qwen":     (4.0,   4.0,  4.0),   # qwen-long
}


def calc_cost(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算真实 API 费用，返回 per-model 汇总 DataFrame。
    依赖列：model, prompt_tokens, completion_tokens, cached_tokens（可选）
    """
    rows = []
    for model, sub in df.groupby("model"):
        price = _PRICE_TABLE.get(model, (5.0, 5.0, 5.0))
        pt = sub["prompt_tokens"].sum() if "prompt_tokens" in sub.columns else sub.get("tokens_used", pd.Series([0])).sum()
        ct = sub["completion_tokens"].sum() if "completion_tokens" in sub.columns else 0
        ckt = sub["cached_tokens"].sum() if "cached_tokens" in sub.columns else 0
        # 非 cache 的 prompt tokens
        non_cached_pt = pt - ckt
        cost = (non_cached_pt * price[0] + ct * price[1] + ckt * price[2]) / 1e6
        rows.append({
            "model": model,
            "prompt_tokens": int(pt),
            "completion_tokens": int(ct),
            "cached_tokens": int(ckt),
            "cost_cny": round(cost, 4),
        })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────
# 聚合分析
# ──────────────────────────────────────────────

def aggregate_by_position(
    df: pd.DataFrame, score_col: str = "contains_score"
) -> pd.DataFrame:
    """
    按 context_length × depth_pct 聚合，生成热力图矩阵数据。
    返回列：model, context_length, depth_pct, <score_col>
    """
    grouped = (
        df.groupby(["model", "context_length", "depth_pct"])[score_col]
        .mean()
        .reset_index()
    )
    return grouped


def aggregate_by_model(
    df: pd.DataFrame, score_col: str = "contains_score"
) -> pd.DataFrame:
    """
    按模型 × context_length 聚合，用于折线图。
    返回列：model, context_length, <score_col>
    """
    grouped = (
        df.groupby(["model", "context_length"])[score_col]
        .mean()
        .reset_index()
    )
    return grouped


def position_bucket(depth_pct) -> str:
    """将 depth_pct 映射到开头/中间/结尾三段。"""
    if depth_pct is None:
        return "未知"
    pct = float(depth_pct)
    if pct <= 20:
        return "开头 (0-20%)"
    elif pct <= 70:
        return "中间 (20-70%)"
    else:
        return "结尾 (70-100%)"


def aggregate_by_position_bucket(
    df: pd.DataFrame, score_col: str = "contains_score"
) -> pd.DataFrame:
    """
    按模型 × 位置段（开头/中间/结尾）聚合，用于位置偏差柱状图。
    """
    df = df.copy()
    df["position_bucket"] = df["depth_pct"].apply(position_bucket)
    grouped = (
        df.groupby(["model", "position_bucket"])[score_col]
        .mean()
        .reset_index()
    )
    return grouped


# ──────────────────────────────────────────────
# 摘要输出
# ──────────────────────────────────────────────

def print_summary(df: pd.DataFrame):
    """在控制台打印各模型的整体准确率摘要。"""
    print("\n" + "=" * 50)
    print("        评测结果摘要")
    print("=" * 50)
    for model in sorted(df["model"].unique()):
        sub = df[df["model"] == model]
        em = sub["em_score"].mean() * 100
        contains = sub["contains_score"].mean() * 100
        n = len(sub)
        tokens = sub["tokens_used"].sum() if "tokens_used" in sub.columns else 0
        print(
            f"  {model:12s} | EM: {em:5.1f}%  Contains: {contains:5.1f}%"
            f"  n={n}  tokens={tokens:,}"
        )
    print("=" * 50 + "\n")


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────

def main():
    import yaml

    config = yaml.safe_load(open("configs/eval_config.yaml", encoding="utf-8"))

    raw_path = Path(config["results"]["raw_dir"]) / "raw_results.csv"
    if not raw_path.exists():
        print(f"⚠️  未找到原始结果文件: {raw_path}\n请先运行 eval_runner.py")
        return

    df = pd.read_csv(raw_path)
    df = score_results(df)
    print_summary(df)

    out_dir = Path(config["results"]["processed_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "scored_results.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"✅ 评分结果保存至: {out_path}")


if __name__ == "__main__":
    main()
