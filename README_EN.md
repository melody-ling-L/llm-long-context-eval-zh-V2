# LLM Long-Context Evaluation Framework

> A 4-dimension evaluation framework quantifying the **"Lost in the Middle"** phenomenon in Chinese LLMs

---

## Overview

This project evaluates how well leading LLMs (DeepSeek-V3, Kimi, Qwen-Long) actually utilize their claimed long-context windows:
- Models claim 128K context — do they truly *use* it?
- Does accuracy drop when information is buried in the **middle** of a document?

---

## Evaluation Dimensions

| Dimension | Description | Key Metric |
|---|---|---|
| **NIAH** | Needle in a Haystack — insert key facts at varying depths | Accuracy @depth × length |
| **Multi-hop Reasoning** | Information scattered across the document, requires synthesis | Multi-hop Accuracy |
| **Position Bias** | Accuracy difference for info at beginning / middle / end | Position Bias Score |
| **Cross-model Comparison** | DeepSeek-V3 vs Kimi vs Qwen-Long | Δ Accuracy |

---

## Results

*(To be filled after experiments)*

---

## References

- [Lost in the Middle (Liu et al., 2023)](https://arxiv.org/abs/2307.03172)
- [RULER: What's the Real Context Window of Your LLM? (Hsieh et al., 2024)](https://arxiv.org/abs/2404.06654)
- [Needle in a Haystack (Kamradt, 2023)](https://github.com/gkamradt/LLMTest_NeedleInAHaystack)
