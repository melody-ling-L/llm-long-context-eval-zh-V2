"""
可视化模块

提供：
- plot_niah_heatmap()              NIAH 热力图（静态，matplotlib/seaborn）
- plot_niah_heatmap_interactive()  NIAH 交互式热力图（plotly，notebook 友好）
- plot_accuracy_by_length()        跨模型准确率 vs 上下文长度折线图
- plot_position_bias()             "Lost in the Middle" 位置偏差柱状图
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


def _resolve_figures_dir(figures_dir: str | Path | None = None) -> Path:
    path = FIGURES_DIR if figures_dir is None else Path(figures_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


# ──────────────────────────────────────────────
# 1. NIAH 热力图（静态）
# ──────────────────────────────────────────────

def plot_niah_heatmap(
    df: pd.DataFrame,
    model: str,
    score_col: str = "contains_score",
    save: bool = True,
    figures_dir: str | Path | None = None,
) -> plt.Figure:
    """
    绘制单个模型的 NIAH 热力图。
    行 = context_length，列 = depth_pct，颜色 = 准确率。
    """
    sub = df[df["model"] == model].copy()
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
    ax.set_title(
        f"NIAH 热力图 — {model}\n"
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
) -> go.Figure:
    """
    生成 Plotly 交互式热力图，支持 hover 查看详情。
    在 Jupyter Notebook 中直接展示，也可导出 HTML。
    """
    sub = df[df["model"] == model].copy()
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
        title=f"NIAH 交互式热力图 — {model}",
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
) -> plt.Figure:
    """
    跨模型准确率随上下文长度变化的折线图。
    """
    grouped = (
        df.groupby(["model", "context_length"])[score_col]
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
            label=model,
            linewidth=2.2,
            markersize=8,
        )

    ax.set_xlabel("上下文长度 (chars)", fontsize=12)
    ax.set_ylabel("准确率 (%) — Contains Match", fontsize=12)
    ax.set_title("跨模型 NIAH 准确率 vs 上下文长度", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 108)
    plt.tight_layout()

    if save:
        path = _resolve_figures_dir(figures_dir) / "accuracy_by_length.png"
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
) -> plt.Figure:
    """
    将 depth_pct 分为开头/中间/结尾三段，
    对比各模型在不同位置的准确率，验证 "Lost in the Middle" 现象。
    """
    df = df.copy()
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
            label=model,
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
    ax.set_title('"Lost in the Middle" — 位置偏差分析', fontsize=14)
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
