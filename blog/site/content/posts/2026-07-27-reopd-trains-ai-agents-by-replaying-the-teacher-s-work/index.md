---
date: '2026-07-27'
description: Microsoft Research and the University of Amsterdam introduced ReOPD,
  a method that trains AI agents from recorded examples instead of repeatedly running
  tools. Its reported gains come from a social post; no paper or code link was supplied
  with this item.
draft_id: 20260803-cc3a11cd
item_kind: news
item_source: linkedin
kol: dair-ai
reliability:
  authors_orgs: The social post attributes the work to Microsoft Research and the
    University of Amsterdam.
  code_available: false
  evidence: No paper, detailed results, or public code repository was included in
    the supplied item.
  venue: DAIR.AI LinkedIn post; the paper venue was not provided.
social:
  author: DAIR.AI
  created_at: '2026-07-27'
  text: "Very cool paper from Microsoft.\n\nThe idea is to train agents on replayed
    teacher trajectories instead of live environment rollouts.\n\nOn-policy distillation
    for agentic tasks is expensive because every update needs fresh student rollouts
    through the environment plus teacher queries at each visited history. \n\nNew
    research from Microsoft Research and the University of Amsterdam introduces ReOPD,
    which reuses pre-collected teacher trajectories as replayed prefixes. The student
    acts at selected steps"
source_url: https://www.linkedin.com/company/dair-ai/posts/
summary: Microsoft Research and the University of Amsterdam introduced ReOPD, a method
  that trains AI agents from recorded examples instead of repeatedly running tools.
  Its reported gains come from a social post; no paper or code link was supplied with
  this item.
tags:
- reopd
- agent training
- knowledge distillation
- teacher trajectories
- microsoft research
- university of amsterdam
title: ReOPD Trains AI Agents by Replaying the Teacher’s Work
topics:
- ai
- ai/llm
- ai/llm/training
---

## What Happened

Researchers from Microsoft Research and the University of Amsterdam introduced ReOPD, according to a DAIR.AI post on LinkedIn. The simple idea is to let a student AI agent practice from a recording of a teacher agent’s work. It can learn from selected moments without sending either agent back through the live task every time.

{{< source-post >}}

That recording-based setup targets a costly part of agent training. Conventional training can require a fresh run through an environment after every update, along with repeated questions to the teacher. ReOPD instead replays stored teacher trajectories and gives the student detailed guidance at individual steps.

> The post says ReOPD uses zero tool calls during student training and runs at least 4× faster per rollout.

## Why It Matters

For teams building agents that write Python or search for information, fewer live runs could mean shorter experiments and lower tool or infrastructure costs. For users, the practical effect—if the results hold up—could be capable agents that are cheaper and faster to improve.

There is a catch in teaching from multi-step examples. As training histories become more like the student’s own behavior, the teacher may be pushed into unfamiliar situations where its answers are less dependable. The researchers call this the “prefix trap.” ReOPD responds by favoring earlier steps, where that mismatch is smaller. DAIR.AI reports that the method preserved or improved accuracy across Python-based math and search tasks, with several teacher and student sizes. The supplied item does not include the paper, detailed results, an independent evaluation, or a code repository, so those claims could not be checked here.

## Glossary

- **Trajectory** — The recorded sequence of observations, decisions, and actions an agent takes while completing a task.

## Links

- Announcement/page — No direct paper or announcement link was supplied.
- GitHub repository — No repository link was supplied.
- [Original DAIR.AI LinkedIn post](https://www.linkedin.com/company/dair-ai/posts/)