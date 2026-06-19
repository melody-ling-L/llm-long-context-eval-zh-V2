#!/usr/bin/env python3
"""Patch 04_report_v2.ipynb source for eval_valid口径, clear stale outputs, re-execute."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_PATH = ROOT / "notebooks/v2/04_report_v2.ipynb"
EXEC_PATH = ROOT / "results/v2/report/04_report_v2.executed.ipynb"


def _replace_in_cell(cell: dict, old: str, new: str) -> bool:
    src = "".join(cell.get("source", []))
    if old not in src:
        return False
    cell["source"] = src.replace(old, new).splitlines(keepends=True)
    return True


def patch_notebook(nb: dict) -> None:
    cells = nb["cells"]

    # --- cell 1: badcase on eval_valid + save primary summary ---
    c1 = cells[1]
    replacements_c1 = [
        (
            "    niah_badcases = df[(df['task'] == 'niah') & (df['is_badcase'] == 1)].copy()\n"
            "    niah_badcase_summary = summarize_badcase_taxonomy(niah_df)\n"
            "    niah_badcase_summary_overall = summarize_badcase_taxonomy(niah_df, group_cols=['badcase_taxonomy'])\n",
            "    niah_badcases = niah_valid_df[niah_valid_df['is_badcase'] == 1].copy()\n"
            "    niah_badcase_summary = summarize_badcase_taxonomy(niah_valid_df)\n"
            "    niah_badcase_summary_overall = summarize_badcase_taxonomy(\n"
            "        niah_valid_df, group_cols=['badcase_taxonomy']\n"
            "    )\n",
        ),
    ]
    for old, new in replacements_c1:
        _replace_in_cell(c1, old, new)

    src1 = "".join(c1["source"])
    anchor = "        representative_badcases.to_csv(processed_dir / 'badcase_examples.csv', index=False, encoding='utf-8-sig')\n"
    if anchor in src1 and "summary_by_model_niah_valid_only" not in src1:
        c1["source"] = src1.replace(
            anchor,
            anchor
            + "\n    if not model_summary.empty:\n"
            + "        model_summary.to_csv(\n"
            + "            processed_dir / 'summary_by_model_niah_valid_only.csv',\n"
            + "            index=False, encoding='utf-8-sig',\n"
            + "        )\n"
            + "    if not call_status_summary.empty:\n"
            + "        call_status_summary.to_csv(\n"
            + "            processed_dir / 'summary_call_status.csv', index=False, encoding='utf-8-sig'\n"
            + "        )\n",
        ).splitlines(keepends=True)

    # --- cell 12: taxonomy label + Kimi recommendations ---
    c12 = cells[12]
    _replace_in_cell(
        c12,
        "        print('整体 badcase taxonomy（包含 Contains miss 与 EM-only miss）：')\n",
        "        print('整体 badcase taxonomy（eval_valid 主口径，含 Contains miss 与 EM-only miss）：')\n",
    )
    _replace_in_cell(
        c12,
        """    if KIMI_DATA_STATUS != 'valid':
        recommendations.append(
            'Kimi 本轮 NIAH 数据因 API 账户额度耗尽而无效（32K 全部 prompt_tokens=0，8K/16K 也有空响应污染）。'
            '充值后需全长度重跑；runner 已新增 error 列，下次可直接区分 402/429/超时与模型答错。'
            '不能据此写“Kimi 长文能力差”——事后复现已确认模型能力正常。'
        )
    elif not length_summary.empty:
        kimi_32k = length_summary[(length_summary['model'] == 'kimi') & (length_summary['context_length'] == 32000)]
        if not kimi_32k.empty:
            kimi_row = kimi_32k.iloc[0]
            recommendations.append(
                'Kimi 在 32K 下 Contains=%.1f%%，95%% CI=[%.1f, %.1f]；若 api_failed 比例高，优先排查账户额度与 API 错误，而非模型能力。'
                % (kimi_row['contains_pct'], kimi_row['contains_ci_low_pct'], kimi_row['contains_ci_high_pct'])
            )
""",
        """    if not call_status_summary.empty:
        kimi_status = call_status_summary[call_status_summary['model'] == 'kimi']
        if not kimi_status.empty and int(kimi_status.iloc[0]['content_filter']) > 0:
            cf = int(kimi_status.iloc[0]['content_filter'])
            recommendations.append(
                f'Kimi 有 {cf} 条 content_filter（Moonshot 平台审核拦截），已从 eval_valid 主口径排除；'
                '报告 headline 不应使用含审核失败的 350 行全量平均。'
            )
    if not length_summary.empty:
        kimi_32k = length_summary[(length_summary['model'] == 'kimi') & (length_summary['context_length'] == 32000)]
        if not kimi_32k.empty:
            kimi_row = kimi_32k.iloc[0]
            recommendations.append(
                'Kimi 在 32K eval_valid 样本上 Contains=%.1f%%，95%% CI=[%.1f, %.1f]；'
                '早期「32K 崩塌」来自余额耗尽（prompt_tokens=0），重跑后已恢复。'
                % (kimi_row['contains_pct'], kimi_row['contains_ci_low_pct'], kimi_row['contains_ci_high_pct'])
            )
""",
    )

    # --- cell 13: writing outline markdown ---
    c13 = cells[13]
    src13 = "".join(c13["source"])
    c13["source"] = src13.replace(
        "- **Kimi 本轮数据无效**：因 API 额度耗尽，32K 全部 api_failed，8K/16K 也有污染。标注\"待重跑\"，不写\"长文能力差\"。\n",
        "- **Kimi 主口径用 eval_valid**：31 条 content_filter 不计入能力；有效 319 格 Contains≈94.4%，32K 为 100%。勿用全量 350 行（86.0%）作 headline。\n",
    ).replace(
        "- 单独写 taxonomy 排名，至少点出“输出冗余但包含正确答案”“被相似数字干扰”“多 key 条件下定位失败”三类主导错误。\n",
        "- 单独写 taxonomy 排名（eval_valid）：当前主导为“输出冗余但包含正确答案”（66.1%）与“被相似数字干扰”（33.9%）。\n",
    ).replace(
        "- 若某模型 32K 全灭且 prompt_tokens=0，先查 API 额度/error 列，再查 prompt 模板与截断逻辑。\n",
        "- 若 32K 全灭且 prompt_tokens=0，先查 API 额度/error 列；Kimi 重跑后 32K 已恢复，content_filter 需单独分层。\n",
    ).splitlines(keepends=True)

    # --- cell 14: auto summary ---
    c14 = cells[14]
    _replace_in_cell(
        c14,
        """        if KIMI_DATA_STATUS != 'valid':
            print(
                f'   技术备注: {format_model_name("kimi")} 本轮数据因 API 额度耗尽而无效，'
                '32K 全部 prompt_tokens=0（请求未执行），不能解读为模型长文能力差。待充值后全长度重跑。'
            )
        else:
            kimi_32k = stability_focus[
                (stability_focus['model'] == 'kimi')
                & (stability_focus['context_length'] == 32000)
            ]
            if not kimi_32k.empty:
                kimi_row = kimi_32k.iloc[0]
                print(
                    f'   技术备注: {format_model_name("kimi")} 在 32000 chars 下 Contains={kimi_row["contains_pct"]:.1f}%，'
                    f'95% CI=[{kimi_row["contains_ci_low_pct"]:.1f}, {kimi_row["contains_ci_high_pct"]:.1f}]。'
                )
""",
        """        kimi_32k = stability_focus[
            (stability_focus['model'] == 'kimi')
            & (stability_focus['context_length'] == 32000)
        ]
        if not kimi_32k.empty:
            kimi_row = kimi_32k.iloc[0]
            print(
                f'   技术备注: {format_model_name("kimi")} 在 32000 chars eval_valid 下 Contains={kimi_row["contains_pct"]:.1f}%，'
                f'95% CI=[{kimi_row["contains_ci_low_pct"]:.1f}, {kimi_row["contains_ci_high_pct"]:.1f}]。'
                '早期 0% 来自余额耗尽，非模型塌陷。'
            )
        if not call_status_summary.empty:
            kimi_st = call_status_summary[call_status_summary['model'] == 'kimi']
            if not kimi_st.empty and int(kimi_st.iloc[0]['content_filter']) > 0:
                print(
                    f'   口径备注: Kimi {int(kimi_st.iloc[0]["content_filter"])} 条 content_filter 已从能力统计排除。'
                )
""",
    )

    # Clear code cell outputs only (markdown cells must not have outputs)
    for cell in cells:
        if cell["cell_type"] == "code":
            cell["outputs"] = []
            cell["execution_count"] = None


def main() -> int:
    nb = json.loads(NB_PATH.read_text(encoding="utf-8"))
    patch_notebook(nb)
    NB_PATH.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Patched {NB_PATH}")

    # Regenerate figures first
    subprocess.run([sys.executable, str(ROOT / "scripts/regenerate_v2_figures.py")], check=True)

    EXEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "jupyter",
        "nbconvert",
        "--to",
        "notebook",
        "--execute",
        str(NB_PATH),
        "--output",
        EXEC_PATH.name,
        "--output-dir",
        str(EXEC_PATH.parent),
        "--ExecutePreprocessor.timeout=600",
    ]
    print("Executing notebook...")
    subprocess.run(cmd, cwd=str(ROOT), check=True)
    print(f"Executed report -> {EXEC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
