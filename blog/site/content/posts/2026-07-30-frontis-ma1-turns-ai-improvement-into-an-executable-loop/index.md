---
date: '2026-07-30'
description: OpenMLE lets an AI agent write, run, repair, and recombine machine-learning
  programs, then learn from measurable results. Its strongest setup substantially
  improved reported scores on two compact benchmarks.
draft_id: 20260803-07a28066
item_kind: paper
item_source: linkedin
kol: dair-ai
paper:
  abs_url: https://arxiv.org/abs/2607.28568
  abstract: 'Recursive self-improvement (RSI) requires AI systems that improve the
    process of building AI (i.e., AI4AI); machine learning engineering (MLE) offers
    a concrete, executable testbed for studying this capability. We introduce OpenMLE,
    an open full-stack system for RSI research in MLE, spanning verifiable task environments
    with execution feedback (OpenMLE-Gym), operator learning (OpenMLE-RL), and long-horizon
    search (OpenMLE-Evo). On this stack we post-train Frontis-MA1 (35B) as a meta-evolution
    agent for MLE, aligning post-training and inference around four atomic program-evolution
    operators (Draft, Improve, Debug, Crossover): the same operators are trained via
    execution-grounded SFT and RL on data deduplicated against all evaluation benchmarks,
    then composed into long-horizon search, coupling learning and evolution in a single
    loop. On MLE-Bench Lite under a 12-hour per-task budget on one RTX 4090 capped
    at 12 GB VRAM, Frontis-MA1 (35B) improves Medal Average from 39.39% to 60.61%
    over its base model with OpenMLE-Evo, and reaches 71.21% with OpenMLE-Evo-Max
    (benchmark-independent experience priors and asynchronous search), exceeding GPT-5.5
    + Codex and approaching GPT-5.6 Sol and the 2.8T Kimi K3. On held-out NatureBench
    Lite, both components transfer: with the framework fixed, swapping in the trained
    model raises Match-SOTA from 50% to 70%; with the model fixed, swapping in OpenMLE-Evo
    raises it from 20% to 50%. We release the model weights and the full OpenMLE stack
    to enable reproducible research on executable AI4AI toward RSI. Code: https://github.com/FrontisAI/OpenRSI'
  arxiv_id: '2607.28568'
  authors:
  - Junlin Yang
  - Che Jiang
  - Yu Fu
  - Tianwei Luo
  - Can Ren
  - Weizhi Wang
  - Kaikai Zhao
  - Hongyi Liu
  - Yuxin Zuo
  - Yuru Wang
  - Yuchen Fan
  - Kai Tian
  - Zhenzhao Yuan
  - Xiaojian Lin
  - Li Sheng
  - Rushi Qiang
  - Guoli Jia
  - Xingtai Lv
  - Ermo Hua
  - Dianqiao Lei
  - Youbang Sun
  - Ning Ding
  - Bowen Zhou
  - Kaiyan Zhang
  pdf_url: https://arxiv.org/pdf/2607.28568
  published: '2026-07-30'
  title: 'Frontis-MA1: Training an AI4AI Model towards Recursive Self-Improvement
    in Machine Learning Engineering'
reliability:
  authors_orgs: Junlin Yang and 23 coauthors; affiliations are not provided in the
    supplied files.
  code_available: true
  code_url: https://github.com/FrontisAI/OpenRSI
  evidence: Reported results on MLE-Bench Lite and held-out NatureBench Lite, including
    model and framework component swaps.
  venue: arXiv:2607.28568 [cs.CL], submitted 30 July 2026.
source_url: ''
summary: OpenMLE lets an AI agent write, run, repair, and recombine machine-learning
  programs, then learn from measurable results. Its strongest setup substantially
  improved reported scores on two compact benchmarks.
tags:
- frontis-ma1
- openmle
- recursive self-improvement
- machine-learning engineering
- program evolution
- ai agents
title: Frontis-MA1 Turns AI Improvement into an Executable Loop
topics:
- ai
- ai/llm
- ai/llm/agents
---

## The Big Idea

Imagine hiring a data-science team for a competition. They write a solution, run it, inspect the score, repair mistakes, borrow the best parts from several attempts, and keep going for hours. An AI agent can already do pieces of that job. The hard part is making the whole cycle reliable—and making the agent better at improving its own work.

That matters beyond machine learning contests. Building an AI system is expensive partly because progress depends on many rounds of code, experiments, and judgment. If an agent can carry out those rounds with results that software can check, AI development becomes a practical laboratory for studying whether AI can improve the process used to build AI.

The paper introduces OpenMLE, an open stack for running that laboratory, and Frontis-MA1, a 35-billion-parameter model trained to use it. Its central idea is simple: teach the same four moves the agent will use during a long search—Draft, Improve, Debug, and Crossover—then let measured execution results guide which attempts survive.

## How It Works

Think of OpenMLE as a test kitchen. Frontis-MA1 proposes recipes, the kitchen actually cooks them, and a score—not the model's confidence—decides what deserves another iteration.

```mermaid
flowchart LR
    A[Machine-learning task] --> B[Draft a program]
    B --> C[Run and score it]
    C --> D{Choose the next move}
    D -->|Improve| E[Refine a promising program]
    D -->|Debug| F[Repair a failed program]
    D -->|Crossover| G[Combine useful parts]
    E --> C
    F --> C
    G --> C
    C --> H[Keep the strongest result]
```

OpenMLE-Gym supplies tasks where code can be executed and checked. OpenMLE-RL trains the model from this execution feedback. The training data were deduplicated against every evaluation benchmark, according to the abstract, to reduce the chance that the agent had already seen the test problems.

At evaluation time, OpenMLE-Evo composes the four moves into a long search rather than asking for one polished answer. A larger variant, OpenMLE-Evo-Max, adds experience gathered independently of the benchmarks and runs parts of the search asynchronously. The result is closer to managing a portfolio of experiments than chatting once with a coding assistant.

## What They Found

On MLE-Bench Lite, every task received up to 12 hours on one RTX 4090 limited to 12 GB of memory. The reported Medal Average rose by 21.22 percentage points from the base setup to Frontis-MA1 with OpenMLE-Evo. OpenMLE-Evo-Max added another 10.60 points. In plain language, the final setup earned about 71 points out of every 100 available under this aggregate medal measure, versus about 39 for the base model.

| MLE-Bench Lite result | Base model | Frontis-MA1 + OpenMLE-Evo | Frontis-MA1 + OpenMLE-Evo-Max |
|---|---:|---:|---:|
| Medal Average | 39.39% | 60.61% | 71.21% |

The abstract says the 71.21% result exceeded GPT-5.5 with Codex and approached GPT-5.6 Sol and Kimi K3, although it does not provide their exact scores in the supplied text.

A held-out set, NatureBench Lite, was used to separate the value of the trained model from the value of the search framework. Keeping the framework fixed and changing the model raised Match-SOTA from 50% to 70%—two more tasks in every ten matched the best-known result. Keeping the model fixed and changing the search framework raised it from 20% to 50%—three more tasks in every ten.

| NatureBench Lite comparison | Before swap | After swap |
|---|---:|---:|
| Swap in the trained Frontis-MA1 model; keep framework fixed | 50% | 70% |
| Swap in OpenMLE-Evo; keep model fixed | 20% | 50% |

These results cover two “Lite” benchmarks, not unrestricted real-world engineering. The main benchmark also permits a long per-task compute budget. The supplied paper text is abstract-only, so it does not expose task counts, uncertainty estimates, detailed failure cases, or full ablations. The claims should therefore be read as reported benchmark evidence for this specific model-and-search system.

## Glossary

- **recursive self-improvement** — the idea that an AI system can help improve the tools and processes used to build better AI systems.
- **Crossover** — a search operation that creates a new program by combining useful parts of earlier programs.

## Links

- [arXiv page](https://arxiv.org/abs/2607.28568)
- [PDF](https://arxiv.org/pdf/2607.28568)
- [GitHub repository](https://github.com/FrontisAI/OpenRSI)