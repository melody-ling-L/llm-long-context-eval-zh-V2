"""
可视化模块

提供：
- plot_niah_heatmap()                 NIAH 热力图（静态，matplotlib/seaborn）
- plot_niah_heatmap_interactive()     NIAH 交互式热力图（plotly，notebook 友好）
- plot_accuracy_by_length()           跨模型准确率 vs 上下文长度折线图
- plot_accuracy_by_length_with_ci()   跨模型准确率 vs 上下文长度折线图（含 95% CI）
- plot_position_bias()                "Lost in the Middle" 位置偏差柱状图
"""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns

# ── 中文字体 ──────────────────────────────────
matplotlib.rcParams["font.sans-serif"] = [
    "PingFang SC",
    "Hiragino Sans GB",
    "Microsoft YaHei",
    "SimHei",
    "Arial Unicode MS",
    "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = PROJECT_ROOT / "results/figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

MODEL_DISPLAY_NAMES = {
    "deepseek": "DeepSeek-V3 (API: deepseek-chat)",
    "kimi": "Kimi (Moonshot, API: moonshot-v1-128k)",
    "kimi26": "Kimi 2.6 (API: kimi2.6-320K)",
    "qwen": "Qwen-Long (API: qwen-long)",
}


def _resolve_figures_dir(figures_dir: str | Path | None = None) -> Path:
    path = FIGURES_DIR if figures_dir is None else Path(figures_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_model_name(model: str) -> str:
    return MODEL_DISPLAY_NAMES.get(str(model), str(model))


def _prepare_niah_df(df: pd.DataFrame, eval_valid_only: bool = True) -> pd.DataFrame:
    """绘图用 NIAH 子集；默认仅 eval_valid（排除 content_filter / infra 失败）。"""
    sub = df.copy()
    if "task" in sub.columns:
        sub = sub[sub["task"].fillna("niah") == "niah"]
    if eval_valid_only:
        from src.metrics_v2 import filter_eval_valid

        sub = filter_eval_valid(sub)
    return sub


# ──────────────────────────────────────────────
# 1. NIAH 热力图（静态）
# ──────────────────────────────────────────────

def plot_niah_heatmap(
    df: pd.DataFrame,
    model: str,
    score_col: str = "contains_score",
    save: bool = True,
    figures_dir: str | Path | None = None,
    eval_valid_only: bool = True,
) -> plt.Figure:
    """
    绘制单个模型的 NIAH 热力图。
    行 = context_length，列 = depth_pct，颜色 = 准确率。
    """
    sub = _prepare_niah_df(df, eval_valid_only=eval_valid_only)
    sub = sub[sub["model"] == model].copy()
    model_label = format_model_name(model)
    pivot = sub.pivot_table(
        index="context_length",
        columns="depth_pct",
        values=score_col,
        aggfunc="mean",
    )

    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(
        pivot * 100,
        annot=True,
        fmt=".0f",
        cmap="RdYlGn",
        vmin=0,
        vmax=100,
        linewidths=0.5,
        ax=ax,
        cbar_kws={"label": "准确率 (%)"},
    )
    suffix = "（eval_valid）" if eval_valid_only else "（全量）"
    ax.set_title(
        f"NIAH 热力图 — {model_label}{suffix}\n"
        f"（列: Needle 插入深度 %，行: 上下文字符长度，格值: Contains Accuracy %）",
        fontsize=13,
        pad=14,
    )
    ax.set_xlabel("Needle 插入深度 (%)", fontsize=11)
    ax.set_ylabel("上下文长度 (chars)", fontsize=11)
    plt.tight_layout()

    if save:
        path = _resolve_figures_dir(figures_dir) / f"niah_heatmap_{model}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"✅ 已保存: {path}")

    return fig


# ──────────────────────────────────────────────
# 2. NIAH 交互式热力图（Plotly）
# ──────────────────────────────────────────────

def plot_niah_heatmap_interactive(
    df: pd.DataFrame,
    model: str,
    score_col: str = "contains_score",
    save_html: bool = True,
    figures_dir: str | Path | None = None,
    eval_valid_only: bool = True,
) -> go.Figure:
    """
    生成 Plotly 交互式热力图，支持 hover 查看详情。
    在 Jupyter Notebook 中直接展示，也可导出 HTML。
    """
    sub = _prepare_niah_df(df, eval_valid_only=eval_valid_only)
    sub = sub[sub["model"] == model].copy()
    model_label = format_model_name(model)
    pivot = (
        sub.pivot_table(
            index="context_length",
            columns="depth_pct",
            values=score_col,
            aggfunc="mean",
        )
        * 100
    )

    fig = px.imshow(
        pivot,
        text_auto=".0f",
        color_continuous_scale="RdYlGn",
        zmin=0,
        zmax=100,
        title=f"NIAH 交互式热力图 — {model_label}" + ("（eval_valid）" if eval_valid_only else ""),
        labels={
            "x": "Needle 插入深度 (%)",
            "y": "上下文长度 (chars)",
            "color": "准确率 (%)",
        },
        aspect="auto",
    )
    fig.update_layout(width=950, height=480)
    fig.update_coloraxes(colorbar_title="准确率 (%)")

    if save_html:
        path = _resolve_figures_dir(figures_dir) / f"niah_heatmap_{model}_interactive.html"
        fig.write_html(str(path))
        print(f"✅ 已保存交互式图表: {path}")

    return fig


# ──────────────────────────────────────────────
# 3. 准确率 vs 上下文长度（跨模型折线图）
# ──────────────────────────────────────────────

def plot_accuracy_by_length(
    df: pd.DataFrame,
    score_col: str = "contains_score",
    save: bool = True,
    figures_dir: str | Path | None = None,
    eval_valid_only: bool = True,
) -> plt.Figure:
    """
    跨模型准确率随上下文长度变化的折线图。
    """
    plot_df = _prepare_niah_df(df, eval_valid_only=eval_valid_only)
    grouped = (
        plot_df.groupby(["model", "context_length"])[score_col]
        .mean()
        .reset_index()
    )
    grouped[score_col] = grouped[score_col] * 100

    fig, ax = plt.subplots(figsize=(10, 6))
    markers = ["o", "s", "^", "D", "v"]
    for idx, (model, sub) in enumerate(grouped.groupby("model")):
        sub = sub.sort_values("context_length")
        ax.plot(
            sub["context_length"],
            sub[score_col],
            marker=markers[idx % len(markers)],
            label=format_model_name(model),
            linewidth=2.2,
            markersize=8,
        )

    ax.set_xlabel("上下文长度 (chars)", fontsize=12)
    ax.set_ylabel("准确率 (%) — Contains Match", fontsize=12)
    ax.set_title(
        "跨模型 NIAH 准确率 vs 上下文长度" + ("（eval_valid）" if eval_valid_only else ""),
        fontsize=14,
    )
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 108)
    plt.tight_layout()

    if save:
        path = _resolve_figures_dir(figures_dir) / "accuracy_by_length.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"✅ 已保存: {path}")

    return fig


def plot_accuracy_by_length_with_ci(
    summary_df: pd.DataFrame,
    save: bool = True,
    figures_dir: str | Path | None = None,
) -> plt.Figure:
    """
    使用汇总后的长度级结果绘制准确率均值与 95% CI。
    适合直接判断 16K / 32K 的回升是否具有统计意义。
    """
    required_cols = {
        "model",
        "context_length",
        "contains_pct",
        "contains_ci_low_pct",
        "contains_ci_high_pct",
    }
    missing_cols = required_cols - set(summary_df.columns)
    if missing_cols:
        raise ValueError(f"summary_df 缺少必要列: {sorted(missing_cols)}")

    plot_df = summary_df.copy()
    plot_df = plot_df.sort_values(["model", "context_length"])

    fig, ax = plt.subplots(figsize=(10, 6))
    markers = ["o", "s", "^", "D", "v"]

    for idx, (model, sub) in enumerate(plot_df.groupby("model")):
        sub = sub.sort_values("context_length")
        x = sub["context_length"].to_numpy()
        y = sub["contains_pct"].to_numpy(dtype=float)
        lower = y - sub["contains_ci_low_pct"].to_numpy(dtype=float)
        upper = sub["contains_ci_high_pct"].to_numpy(dtype=float) - y

        ax.errorbar(
            x,
            y,
            yerr=np.vstack([lower, upper]),
            marker=markers[idx % len(markers)],
            linewidth=2.2,
            markersize=7,
            capsize=4,
            label=format_model_name(model),
        )

    ax.set_xlabel("上下文长度 (chars)", fontsize=12)
    ax.set_ylabel("准确率 (%) — Contains Match", fontsize=12)
    ax.set_title(
        "跨模型 NIAH 准确率 vs 上下文长度（含 95% CI，eval_valid）",
        fontsize=14,
    )
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 108)
    plt.tight_layout()

    if save:
        path = _resolve_figures_dir(figures_dir) / "accuracy_by_length_with_ci.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"✅ 已保存: {path}")

    return fig


# ──────────────────────────────────────────────
# 4. "Lost in the Middle" 位置偏差柱状图
# ──────────────────────────────────────────────

def plot_position_bias(
    df: pd.DataFrame,
    score_col: str = "contains_score",
    save: bool = True,
    figures_dir: str | Path | None = None,
    eval_valid_only: bool = True,
) -> plt.Figure:
    """
    将 depth_pct 分为开头/中间/结尾三段，
    对比各模型在不同位置的准确率，验证 "Lost in the Middle" 现象。
    """
    df = _prepare_niah_df(df, eval_valid_only=eval_valid_only).copy()
    bins = [-1, 20, 70, 101]
    labels = ["开头\n(0-20%)", "中间\n(20-70%)", "结尾\n(70-100%)"]
    df["position"] = pd.cut(df["depth_pct"], bins=bins, labels=labels)

    grouped = (
        df.groupby(["model", "position"], observed=True)[score_col]
        .mean()
        .reset_index()
    )
    grouped[score_col] = grouped[score_col] * 100

    models = sorted(grouped["model"].unique())
    positions = labels
    x = np.arange(len(positions))
    width = 0.8 / max(len(models), 1)

    fig, ax = plt.subplots(figsize=(10, 6))
    colors = plt.cm.Set2.colors

    for i, model in enumerate(models):
        sub = grouped[grouped["model"] == model]
        vals = []
        for pos in positions:
            row = sub[sub["position"] == pos]
            vals.append(float(row[score_col].values[0]) if len(row) > 0 else 0.0)
        bars = ax.bar(
            x + i * width - (len(models) - 1) * width / 2,
            vals,
            width * 0.9,
            label=format_model_name(model),
            color=colors[i % len(colors)],
        )
        # 在柱顶标数字
        for bar, val in zip(bars, vals):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1,
                f"{val:.0f}%",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(positions, fontsize=12)
    ax.set_ylabel("准确率 (%) — Contains Match", fontsize=12)
    ax.set_title(
        '"Lost in the Middle" — 位置偏差分析（eval_valid）',
        fontsize=14,
    )
    ax.legend(fontsize=11)
    ax.set_ylim(0, 120)
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    if save:
        path = _resolve_figures_dir(figures_dir) / "position_bias.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"✅ 已保存: {path}")

    return fig


# ──────────────────────────────────────────────
# 多跳推理：按模型 × hops 的准确率
# ──────────────────────────────────────────────

def plot_multihop_by_hops(
    df_multihop: pd.DataFrame,
    score_col: str = "contains_score",
    save: bool = True,
    figures_dir: str | Path | None = None,
):
    """多跳推理 Contains 准确率：模型 × hops 分组柱状图。"""
    if df_multihop.empty:
        print("⚠️  无多跳数据，跳过 plot_multihop_by_hops")
        return None

    grouped = (
        df_multihop.groupby(["model", "hops"])[score_col]
        .agg(["mean", "size"])
        .reset_index()
    )
    grouped["mean"] *= 100

    models = sorted(grouped["model"].unique())
    hops_values = sorted(grouped["hops"].dropna().unique())
    x = np.arange(len(models))
    width = 0.8 / max(len(hops_values), 1)
    colors = ["#2a9d8f", "#e76f51", "#264653", "#e9c46a"]

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, hops in enumerate(hops_values):
        vals, ns = [], []
        for model in models:
            row = grouped[(grouped["model"] == model) & (grouped["hops"] == hops)]
            vals.append(float(row["mean"].iloc[0]) if not row.empty else 0.0)
            ns.append(int(row["size"].iloc[0]) if not row.empty else 0)
        offset = (i - (len(hops_values) - 1) / 2) * width
        bars = ax.bar(x + offset, vals, width, label=f"{int(hops)}-hop", color=colors[i % len(colors)])
        for bar, n in zip(bars, ns):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                    f"{bar.get_height():.0f}%\n(n={n})", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels([format_model_name(m) for m in models], fontsize=9)
    ax.set_ylabel("Contains 准确率 (%)")
    ax.set_title("多跳推理（嵌入长文）— 模型 × hops 准确率", fontsize=14)
    ax.set_ylim(0, 115)
    ax.legend(title="推理跳数", fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()

    if save:
        path = _resolve_figures_dir(figures_dir) / "multihop_by_hops.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"✅ 已保存: {path}")

    return fig


def plot_efficiency_tradeoff(
    summary_df: pd.DataFrame,
    save: bool = True,
    figures_dir: str | Path | None = None,
) -> plt.Figure:
    """准确率-成本-输出 token 三维效率图（基于 eval_valid 汇总）。"""
    plot_df = summary_df.sort_values("contains_pct", ascending=True).copy()
    plot_df["model"] = plot_df["model"].map(format_model_name)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    colors = ["#2a9d8f", "#e9c46a", "#e76f51", "#264653"]

    axes[0].barh(
        plot_df["model"],
        plot_df["cost_per_contains_hit_cny"],
        color=colors[: len(plot_df)],
    )
    axes[0].set_title("单位命中成本 (CNY / contains hit, eval_valid)")
    axes[0].set_xlabel("CNY")
    axes[0].grid(True, axis="x", alpha=0.25)

    axes[1].scatter(
        plot_df["avg_completion_tokens"],
        plot_df["contains_pct"],
        s=plot_df["avg_response_chars"].clip(lower=1) * 8,
        c=range(len(plot_df)),
        cmap="viridis",
        alpha=0.85,
    )
    for _, row in plot_df.iterrows():
        axes[1].text(
            row["avg_completion_tokens"] + 0.2,
            row["contains_pct"] + 0.2,
            row["model"],
            fontsize=9,
        )
    axes[1].set_title("准确率 vs 输出 token (eval_valid)")
    axes[1].set_xlabel("平均 completion tokens")
    axes[1].set_ylabel("Contains 准确率 (%)")
    axes[1].grid(True, alpha=0.25)
    plt.tight_layout()

    if save:
        path = _resolve_figures_dir(figures_dir) / "efficiency_tradeoff.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"✅ 已保存: {path}")
    return fig


def plot_depth_accuracy_curve(
    df: pd.DataFrame,
    save: bool = True,
    figures_dir: str | Path | None = None,
    eval_valid_only: bool = True,
) -> plt.Figure:
    """各模型 Contains 随 needle 深度变化曲线。"""
    plot_df = _prepare_niah_df(df, eval_valid_only=eval_valid_only)
    fig, ax = plt.subplots(figsize=(10, 5))
    for model, sub in plot_df.groupby("model"):
        depth_acc = sub.groupby("depth_pct")["contains_score"].mean().sort_index() * 100
        ax.plot(
            depth_acc.index,
            depth_acc.values,
            marker="o",
            linewidth=2,
            label=format_model_name(model),
        )

    ax.axvspan(20, 70, alpha=0.08, color="red")
    ax.set_xlabel("Needle 插入深度 (%)")
    ax.set_ylabel("Contains 准确率 (%)")
    ax.set_title("V2 准确率 vs Needle 深度（eval_valid）")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.set_ylim(0, 108)
    plt.tight_layout()

    if save:
        path = _resolve_figures_dir(figures_dir) / "depth_accuracy_curve.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        print(f"✅ 已保存: {path}")
    return fig


# ──────────────────────────────────────────────
# 主流程（批量生成所有图表）
# ──────────────────────────────────────────────

def main():
    import yaml

    config = yaml.safe_load(open("configs/eval_config.yaml", encoding="utf-8"))

    scored_path = Path(config["results"]["processed_dir"]) / "scored_results.csv"
    if not scored_path.exists():
        print(f"⚠️  未找到评分结果文件: {scored_path}\n请先运行 metrics.py")
        return

    df = pd.read_csv(scored_path)

    # 为每个模型生成热力图
    for model in df["model"].unique():
        plot_niah_heatmap(df, model)
        plot_niah_heatmap_interactive(df, model)

    plot_accuracy_by_length(df)
    plot_position_bias(df)

    print(f"\n🎨 所有图表已保存至 {FIGURES_DIR}/")


if __name__ == "__main__":
    main()
