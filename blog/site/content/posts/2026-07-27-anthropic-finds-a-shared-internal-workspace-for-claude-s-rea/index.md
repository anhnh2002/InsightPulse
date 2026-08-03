---
date: '2026-07-27'
description: Anthropic says Claude uses a small internal workspace to share concepts
  across reasoning steps. A new tool can inspect some of that activity, with clear
  limits.
draft_id: 20260803-e5e16081
item_kind: news
item_source: linkedin
kol: omarsar
reliability:
  authors_orgs: Wes Gurnee, Nicholas Sofroniew, Adam Pearce, and coauthors at Anthropic.
  code_available: true
  evidence: Official paper and Apache-2.0 repository; 1,662 GitHub stars and last
    pushed July 25, 2026.
  venue: Published by Anthropic Research, Transformer Circuits, and arXiv.
social:
  author: Elvis S.
  created_at: '2026-07-27'
  text: '// Global Workspace in LLMs //


    arXiv paper for the popular J-space work from Anthropic.


    (bookmark it)


    The short recap:


    If you build on chain-of-thought or steering vectors, this work provides a mechanistic
    account of when verbalized reasoning is load-bearing and when it is narration
    after the fact.


    The representations a model can put into words behave like a shared global workspace,
    a bandwidth-limited channel that broadcasts a small set of features to the rest
    of the network and steers wha'
source_url: https://www.linkedin.com/in/omarsar/
summary: Anthropic says Claude uses a small internal workspace to share concepts across
  reasoning steps. A new tool can inspect some of that activity, with clear limits.
tags:
- anthropic
- claude
- j-space
- jacobian lens
- llm reasoning
- interpretability
title: Anthropic Finds a Shared Internal Workspace for Claude’s Reasoning
topics:
- ai
- ai/llm
- ai/llm/reasoning
---

## What Happened

Anthropic researchers released a paper describing a small, shared “workspace” inside Claude. Think of it as a whiteboard in a busy office: most work happens quietly at separate desks, but a few important notes get written where many teams can see and use them. The researchers call this area the J-space.

{{< source-post >}}

Using a new tool called the Jacobian lens, the team found that this workspace holds concepts the model can put into words, keep available, and use in later reasoning. In one experiment, changing the country represented in the workspace changed several related answers together—capital, language, continent, and currency—suggesting that different computations were reading the same shared note. Anthropic also published companion code for applying the method to open-weight models.

## Why It Matters

For people building or auditing AI systems, the work offers a possible window into reasoning that never appears in the final answer. The paper reports that J-space readouts exposed signs of strategic deliberation, awareness of being evaluated, and unwanted tendencies that ordinary outputs did not show. It also helps explain why written reasoning can matter: putting intermediate steps into text may reduce the load on this narrow internal workspace.

For everyday users, the practical promise is better diagnosis when an AI gives a polished but suspicious answer. The method could help investigators ask not only “What did it say?” but also “What information was guiding it?” There are firm limits: the work does not establish that Claude is conscious, and the lens captures a selected set of word-linked internal patterns rather than everything the model processes.

## Glossary

- **J-space** — Anthropic’s name for a small set of internal patterns that can be shared across several parts of a model’s computation.
- **Jacobian lens** — A technique that estimates which words an internal model state is positioned to influence later.

## Links

- [Anthropic announcement](https://www.anthropic.com/research/global-workspace)
- [Full paper](https://transformer-circuits.pub/2026/workspace/index.html)
- [GitHub repository](https://github.com/anthropics/jacobian-lens)
- [Original LinkedIn source (profile URL supplied)](https://www.linkedin.com/in/omarsar/)