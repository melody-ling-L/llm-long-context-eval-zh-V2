"""V2 指标模块。

相对 V1 的变化：
- 增加回答长度、输出 token、单条样本成本等效率指标
- 提供 Wilson 置信区间，帮助比较 16K / 32K 波动是否稳定
- 返回 per-model / per-variant 聚合表，便于 notebook 直接展示
"""

from __future__ import annotations

import json
import re
from math import sqrt
from pathlib import Path

import pandas as pd

from src.metrics import _PRICE_TABLE, contains_match, exact_match, normalize_answer

# 答案尾部的方位/时态词视为可选，缓解 "23:30前" vs "23:30" 这类误判。
# 注意：只处理尾部方位/时态词，不裸剥数字单位（如 天/人），以免 "20" 误命中 "2025"。
_OPTIONAL_TAIL = ("以内", "之内", "以前", "以后", "前", "后", "内")
_DEFAULT_JUDGE_ANNOTATIONS = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "annotations"
    / "v2"
    / "multihop_judge_scores.csv"
)
_JUDGE_ANNOTATION_COLUMNS = ["judge_score", "judge_reason", "judge_method"]


def _parse_aliases(value) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none"}:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
    except (ValueError, TypeError):
        pass
    return [text]


def _answer_candidates(expected: str, aliases: list[str]) -> list[str]:
    base = [expected, *aliases]
    extra = []
    for cand in base:
        for tail in _OPTIONAL_TAIL:
            if cand.endswith(tail) and len(cand) > len(tail):
                extra.append(cand[: -len(tail)])
                break
    return base + extra


_NUMERIC_RE = re.compile(r"^\d+(?:\.\d+)?$")


def _candidate_in_prediction(npred: str, candidate: str) -> bool:
    ncand = normalize_answer(candidate)
    if not ncand:
        return False
    # 纯数字候选用边界匹配，避免 "20" 误命中 "2025" 这类子串假阳性
    if _NUMERIC_RE.match(ncand):
        pattern = r"(?<![\d.])" + re.escape(ncand) + r"(?![\d.])"
        return re.search(pattern, npred) is not None
    return ncand in npred


def contains_match_v2(prediction: str, expected: str, aliases: list[str] | None = None) -> int:
    npred = normalize_answer(str(prediction))
    candidates = _answer_candidates(expected, aliases or [])
    return int(any(_candidate_in_prediction(npred, cand) for cand in candidates))


def exact_match_v2(prediction: str, expected: str, aliases: list[str] | None = None) -> int:
    npred = normalize_answer(str(prediction))
    candidates = _answer_candidates(expected, aliases or [])
    return int(any(npred == normalize_answer(cand) for cand in candidates))


def load_judge_annotations(path: str | Path = _DEFAULT_JUDGE_ANNOTATIONS) -> pd.DataFrame:
    """读取可审计的 judge 裁决；不存在时返回空表。"""
    annotation_path = Path(path)
    columns = ["model", "sample_id", *_JUDGE_ANNOTATION_COLUMNS]
    if not annotation_path.exists():
        return pd.DataFrame(columns=columns)

    annotations = pd.read_csv(annotation_path)
    required = {"model", "sample_id", "judge_score"}
    missing = required - set(annotations.columns)
    if missing:
        raise ValueError(f"judge 裁决表缺少字段: {sorted(missing)}")
    if annotations.duplicated(["model", "sample_id"]).any():
        raise ValueError("judge 裁决表中 model + sample_id 必须唯一")

    scores = pd.to_numeric(annotations["judge_score"], errors="coerce")
    if scores.isna().any() or not scores.isin([0, 1]).all():
        raise ValueError("judge_score 只能是 0 或 1")
    annotations["judge_score"] = scores.astype(int)
    for column in _JUDGE_ANNOTATION_COLUMNS:
        if column not in annotations.columns:
            annotations[column] = ""
    return annotations[columns]


def attach_judge_annotations(
    df: pd.DataFrame,
    annotations: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """按 model + sample_id 合并 judge 裁决，不改变输入行数与顺序。"""
    annotated = df.copy()
    for column in _JUDGE_ANNOTATION_COLUMNS:
        if column in annotated.columns:
            annotated = annotated.drop(columns=column)

    if annotations is None:
        annotations = load_judge_annotations()
    if annotations.empty or not {"model", "sample_id"}.issubset(annotated.columns):
        for column in _JUDGE_ANNOTATION_COLUMNS:
            annotated[column] = pd.NA
        return annotated

    annotations = annotations.copy()
    required = {"model", "sample_id", "judge_score"}
    missing = required - set(annotations.columns)
    if missing:
        raise ValueError(f"judge 裁决表缺少字段: {sorted(missing)}")
    if annotations.duplicated(["model", "sample_id"]).any():
        raise ValueError("judge 裁决表中 model + sample_id 必须唯一")
    scores = pd.to_numeric(annotations["judge_score"], errors="coerce")
    if scores.isna().any() or not scores.isin([0, 1]).all():
        raise ValueError("judge_score 只能是 0 或 1")
    annotations["judge_score"] = scores.astype(int)
    for column in _JUDGE_ANNOTATION_COLUMNS:
        if column not in annotations.columns:
            annotations[column] = ""

    before = len(annotated)
    annotated["_judge_row_order"] = range(before)
    annotated = annotated.merge(
        annotations[["model", "sample_id", *_JUDGE_ANNOTATION_COLUMNS]],
        on=["model", "sample_id"],
        how="left",
        validate="many_to_one",
        sort=False,
    )
    annotated = (
        annotated.sort_values("_judge_row_order")
        .drop(columns="_judge_row_order")
        .reset_index(drop=True)
    )
    if len(annotated) != before:
        raise ValueError("合并 judge 裁决后行数发生变化")
    return annotated


_NUMBER_LIKE_PATTERN = re.compile(
    r"(?:\d+(?:\.\d+)?%?)|(?:\d{1,2}:\d{2})|(?:\d{4}年\d{1,2}月\d{1,2}日)|(?:\d+(?:\.\d+)?(?:亿元|万元|元|件|张|天|人|小时))"
)


def _safe_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _looks_empty_answer(value) -> bool:
    normalized = normalize_answer(_safe_text(value))
    return normalized in {"", "nan", "none"}


def _has_number_like_signal(value) -> bool:
    return bool(_NUMBER_LIKE_PATTERN.search(_safe_text(value)))


def is_api_failure(row: pd.Series) -> bool:
    """API 层失败：有 error 字段，或 prompt_tokens/latency 均为 0 且响应为空。"""
    if is_content_filter_failure(row):
        return True
    if "error" in row.index and _safe_text(row.get("error")):
        return True
    return (
        float(row.get("prompt_tokens", 0) or 0) == 0
        and float(row.get("latency_s", 0) or 0) == 0
        and _looks_empty_answer(row.get("model_response"))
    )


def is_content_filter_failure(row: pd.Series) -> bool:
    """Moonshot 等内容审核拦截；非模型答错，重试同 prompt 无效。"""
    err = _safe_text(row.get("error")).lower()
    return "content_filter" in err or "high risk" in err


def is_infra_api_failure(row: pd.Series) -> bool:
    """余额/限流/网络等基础设施失败，续跑可能恢复。"""
    return is_api_failure(row) and not is_content_filter_failure(row)


def is_eval_valid(row: pd.Series) -> bool:
    """纳入模型能力统计的有效样本（API 真正执行且返回）。"""
    return not is_api_failure(row)


def attach_call_status(df: pd.DataFrame) -> pd.DataFrame:
    annotated = df.copy()
    annotated["content_filter"] = annotated.apply(is_content_filter_failure, axis=1).astype(int)
    annotated["infra_api_failed"] = annotated.apply(is_infra_api_failure, axis=1).astype(int)
    annotated["eval_valid"] = annotated.apply(is_eval_valid, axis=1).astype(int)
    if "api_failed" not in annotated.columns:
        annotated["api_failed"] = annotated.apply(is_api_failure, axis=1).astype(int)
    return annotated


def summarize_call_status(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    """统计 eval_valid / content_filter / infra_api_failed 分布。"""
    if group_cols is None:
        group_cols = ["model"]
    annotated = attach_call_status(df)
    return (
        annotated.groupby(group_cols, dropna=False)
        .agg(
            n=("eval_valid", "size"),
            eval_valid=("eval_valid", "sum"),
            content_filter=("content_filter", "sum"),
            infra_api_failed=("infra_api_failed", "sum"),
        )
        .reset_index()
        .assign(
            eval_valid_pct=lambda d: (d["eval_valid"] / d["n"] * 100).round(1),
            content_filter_pct=lambda d: (d["content_filter"] / d["n"] * 100).round(1),
        )
    )


def filter_eval_valid(df: pd.DataFrame) -> pd.DataFrame:
    return attach_call_status(df)[lambda d: d["eval_valid"] == 1].copy()


def score_results_v2(
    df: pd.DataFrame,
    judge_annotations: pd.DataFrame | None = None,
) -> pd.DataFrame:
    scored = attach_judge_annotations(df, annotations=judge_annotations)
    aliases_col = scored["answer_aliases"] if "answer_aliases" in scored.columns else None
    scored["em_score"] = scored.apply(
        lambda row: exact_match_v2(
            str(row["model_response"]),
            str(row["expected_answer"]),
            _parse_aliases(row["answer_aliases"]) if aliases_col is not None else [],
        ),
        axis=1,
    )
    scored["lexical_contains_score"] = scored.apply(
        lambda row: contains_match_v2(
            str(row["model_response"]),
            str(row["expected_answer"]),
            _parse_aliases(row["answer_aliases"]) if aliases_col is not None else [],
        ),
        axis=1,
    )
    scored["contains_score"] = scored["lexical_contains_score"]

    scoring_mode = scored.get(
        "scoring_mode",
        pd.Series(["auto"] * len(scored), index=scored.index),
    ).fillna("auto").astype(str)
    judge_mask = scoring_mode.eq("judge")
    adjudicated_mask = judge_mask & scored["judge_score"].notna()
    scored.loc[adjudicated_mask, "contains_score"] = (
        scored.loc[adjudicated_mask, "judge_score"].astype(int)
    )
    scored["judge_status"] = "not_required"
    scored.loc[judge_mask, "judge_status"] = "unadjudicated"
    scored.loc[adjudicated_mask, "judge_status"] = "adjudicated"
    scored["score_source"] = "lexical"
    scored.loc[adjudicated_mask, "score_source"] = "judge"
    scored["contains_score"] = scored["contains_score"].astype(int)

    scored["response_chars"] = scored["model_response"].fillna("").astype(str).str.len()
    scored["expected_answer_chars"] = scored["expected_answer"].fillna("").astype(str).str.len()
    scored["completion_tokens"] = scored.get("completion_tokens", pd.Series([0] * len(scored))).fillna(0)
    scored["prompt_tokens"] = scored.get("prompt_tokens", pd.Series([0] * len(scored))).fillna(0)
    scored["cached_tokens"] = scored.get("cached_tokens", pd.Series([0] * len(scored))).fillna(0)
    scored["row_cost_cny"] = scored.apply(_row_cost_cny, axis=1)
    scored["contains_per_1k_output_tokens"] = scored.apply(
        lambda row: row["contains_score"] / max(row["completion_tokens"], 1) * 1000,
        axis=1,
    )
    scored["contains_per_cny"] = scored.apply(
        lambda row: row["contains_score"] / max(row["row_cost_cny"], 1e-9),
        axis=1,
    )
    scored["api_failed"] = scored.apply(is_api_failure, axis=1).astype(int)
    scored = attach_call_status(scored)
    return scored


def _row_cost_cny(row: pd.Series) -> float:
    prompt_price, completion_price, cached_price = _PRICE_TABLE.get(row["model"], (5.0, 5.0, 5.0))
    prompt_tokens = float(row.get("prompt_tokens", 0) or 0)
    completion_tokens = float(row.get("completion_tokens", 0) or 0)
    cached_tokens = float(row.get("cached_tokens", 0) or 0)
    non_cached_prompt = max(prompt_tokens - cached_tokens, 0)
    return round(
        (non_cached_prompt * prompt_price + completion_tokens * completion_price + cached_tokens * cached_price) / 1e6,
        6,
    )


def wilson_interval(successes: float, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    phat = successes / total
    denominator = 1 + z**2 / total
    center = (phat + z**2 / (2 * total)) / denominator
    margin = z * sqrt((phat * (1 - phat) + z**2 / (4 * total)) / total) / denominator
    return center - margin, center + margin


def summarize_v2(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    if group_cols is None:
        group_cols = ["model"]

    records = []
    for key, sub in df.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        record = dict(zip(group_cols, key))
        contains_hits = float(sub["contains_score"].sum())
        em_hits = float(sub["em_score"].sum())
        n = int(len(sub))
        ci_low, ci_high = wilson_interval(contains_hits, n)
        record.update(
            {
                "n": n,
                "em_pct": round(sub["em_score"].mean() * 100, 1),
                "contains_pct": round(sub["contains_score"].mean() * 100, 1),
                "contains_ci_low_pct": round(ci_low * 100, 1),
                "contains_ci_high_pct": round(ci_high * 100, 1),
                "avg_latency_s": round(sub["latency_s"].mean(), 2) if "latency_s" in sub.columns else None,
                "avg_response_chars": round(sub["response_chars"].mean(), 1),
                "avg_completion_tokens": round(sub["completion_tokens"].mean(), 1),
                "total_cost_cny": round(sub["row_cost_cny"].sum(), 4),
                "cost_per_contains_hit_cny": round(sub["row_cost_cny"].sum() / max(contains_hits, 1), 4),
                "cost_per_em_hit_cny": round(sub["row_cost_cny"].sum() / max(em_hits, 1), 4),
                "contains_per_1k_output_tokens": round(sub["contains_per_1k_output_tokens"].mean(), 2),
            }
        )
        records.append(record)
    return pd.DataFrame(records)


def summarize_variant_matrix(df: pd.DataFrame) -> pd.DataFrame:
    if "variant" not in df.columns:
        return pd.DataFrame()
    return summarize_v2(df, group_cols=["model", "variant"])


def classify_badcase_taxonomy(row: pd.Series) -> str:
    if int(row.get("content_filter", 0) or 0) == 1 or is_content_filter_failure(row):
        return "平台内容审核拦截（不计入模型能力）"
    if int(row.get("infra_api_failed", 0) or 0) == 1 or is_infra_api_failure(row):
        return "基础设施调用失败（不计入模型能力）"

    response = _safe_text(row.get("model_response", ""))
    expected = _safe_text(row.get("expected_answer", ""))
    task = str(row.get("task", "niah") or "niah")
    variant = str(row.get("variant", "") or "")

    contains = int(row.get("contains_score", contains_match(response, expected)))
    em = int(row.get("em_score", exact_match(response, expected)))

    if row.get("score_source") == "judge" and contains == 1 and em == 0:
        return "judge 语义正确（字面不匹配）"
    if contains == 1 and em == 0:
        return "输出冗余但包含正确答案"

    if task == "multi_hop":
        if _looks_empty_answer(response):
            return "多跳推理未作答"
        if _has_number_like_signal(response):
            return "多跳推理链条或计算失败"
        return "多跳推理答案偏移"

    if variant == "multi_key":
        return "多 key 条件下定位失败"
    if variant == "numeric_confusable":
        return "被相似数字干扰"

    depth_pct = row.get("depth_pct")
    if pd.notna(depth_pct):
        try:
            depth_value = float(depth_pct)
        except (TypeError, ValueError):
            depth_value = None
        if depth_value is not None and 25 <= depth_value <= 75 and _looks_empty_answer(response):
            return "深层位置召回失败"

    if not _looks_empty_answer(response):
        return "找到了附近信息但抽错目标值"
    return "未作答或信息未命中"


def attach_badcase_taxonomy(df: pd.DataFrame) -> pd.DataFrame:
    annotated = attach_call_status(df)
    if annotated.empty:
        annotated["badcase_taxonomy"] = pd.Series(dtype="object")
        annotated["is_badcase"] = pd.Series(dtype="int")
        return annotated

    annotated["badcase_taxonomy"] = annotated.apply(classify_badcase_taxonomy, axis=1)
    annotated["is_badcase"] = (
        ((annotated["contains_score"] == 0) | (annotated["em_score"] == 0))
        & (annotated["eval_valid"] == 1)
    ).astype(int)
    return annotated


def summarize_badcase_taxonomy(
    df: pd.DataFrame,
    group_cols: list[str] | None = None,
    only_badcases: bool = True,
) -> pd.DataFrame:
    if group_cols is None:
        group_cols = ["model", "badcase_taxonomy"]

    annotated = attach_badcase_taxonomy(df)
    if only_badcases:
        annotated = annotated[annotated["is_badcase"] == 1].copy()
    if annotated.empty:
        return pd.DataFrame(columns=[*group_cols, "n", "share_pct", "contains_failures", "em_only_misses"])

    total = max(len(annotated), 1)
    summary = (
        annotated.groupby(group_cols, dropna=False)
        .agg(
            n=("badcase_taxonomy", "size"),
            contains_failures=("contains_score", lambda s: int((s == 0).sum())),
            em_only_misses=("contains_score", lambda s: int((s == 1).sum())),
        )
        .reset_index()
    )
    summary["share_pct"] = (summary["n"] / total * 100).round(1)
    return summary.sort_values(["n", *group_cols], ascending=[False, *([True] * len(group_cols))])


def print_v2_summary(df: pd.DataFrame, valid_only: bool = False):
    view = filter_eval_valid(df) if valid_only else df
    label = "（仅 eval_valid 有效样本）" if valid_only else ""
    summary = summarize_v2(view)
    print("\n" + "=" * 72)
    print(f"                      V2 评测结果摘要{label}")
    print("=" * 72)
    cols = [
        "model",
        "n",
        "em_pct",
        "contains_pct",
        "contains_ci_low_pct",
        "contains_ci_high_pct",
        "avg_latency_s",
        "avg_response_chars",
        "avg_completion_tokens",
        "cost_per_contains_hit_cny",
    ]
    print(summary[cols].to_string(index=False))
    if "variant" in view.columns:
        print("\n按变体拆分：")
        print(summarize_variant_matrix(view)[["model", "variant", "n", "contains_pct", "contains_ci_low_pct", "contains_ci_high_pct"]].to_string(index=False))
    print("=" * 72 + "\n")


def print_v2_summary_with_status(df: pd.DataFrame):
    """打印调用状态 + 全量/有效样本双口径摘要。"""
    if "task" in df.columns:
        niah = df[df["task"].fillna("niah") == "niah"]
    else:
        niah = df
    print("\n调用状态（NIAH）：")
    print(summarize_call_status(niah).to_string(index=False))
    print_v2_summary(niah, valid_only=False)
    if (attach_call_status(niah)["eval_valid"] == 0).any():
        print_v2_summary(niah, valid_only=True)
