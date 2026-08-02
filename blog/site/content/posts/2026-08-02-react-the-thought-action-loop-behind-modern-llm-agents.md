---
date: '2026-08-02'
description: ReAct interleaves language-model reasoning with tool actions and observations,
  improving groundedness and long-horizon control. Its influential design is compelling,
  though the original evidence relies on constrained benchmarks and a closed 540B
  model.
draft_id: 20260802-dbb550eb
item_kind: paper
kol: tom_doerr
paper:
  abs_url: https://arxiv.org/abs/2210.03629
  abstract: 'While large language models (LLMs) have demonstrated impressive capabilities
    across tasks in language understanding and interactive decision making, their
    abilities for reasoning (e.g. chain-of-thought prompting) and acting (e.g. action
    plan generation) have primarily been studied as separate topics. In this paper,
    we explore the use of LLMs to generate both reasoning traces and task-specific
    actions in an interleaved manner, allowing for greater synergy between the two:
    reasoning traces help the model induce, track, and update action plans as well
    as handle exceptions, while actions allow it to interface with external sources,
    such as knowledge bases or environments, to gather additional information. We
    apply our approach, named ReAct, to a diverse set of language and decision making
    tasks and demonstrate its effectiveness over state-of-the-art baselines, as well
    as improved human interpretability and trustworthiness over methods without reasoning
    or acting components. Concretely, on question answering (HotpotQA) and fact verification
    (Fever), ReAct overcomes issues of hallucination and error propagation prevalent
    in chain-of-thought reasoning by interacting with a simple Wikipedia API, and
    generates human-like task-solving trajectories that are more interpretable than
    baselines without reasoning traces. On two interactive decision making benchmarks
    (ALFWorld and WebShop), ReAct outperforms imitation and reinforcement learning
    methods by an absolute success rate of 34% and 10% respectively, while being prompted
    with only one or two in-context examples. Project site with code: https://react-lm.github.io'
  arxiv_id: '2210.03629'
  authors:
  - Shunyu Yao
  - Jeffrey Zhao
  - Dian Yu
  - Nan Du
  - Izhak Shafran
  - Karthik Narasimhan
  - Yuan Cao
  pdf_url: https://arxiv.org/pdf/2210.03629
  published: '2022-10-06'
  title: 'ReAct: Synergizing Reasoning and Acting in Language Models'
reliability:
  authors_orgs: Shunyu Yao and Karthik Narasimhan are listed with Princeton email
    addresses; Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, and Yuan Cao are listed
    with Google email addresses. Yao's work was completed during a Google internship.
  code_available: true
  license: MIT
  repo_archived: false
  repo_last_push: '2024-02-06'
  repo_stars: 4091
  repository: ysymyth/ReAct
  reproducibility: Prompts and code are public, but the main PaLM-540B model was not
    openly accessible.
  venue: GitHub metadata describes the paper as ICLR 2023; supplied paper metadata
    records an arXiv posting on 2022-10-06.
repo:
  description: '[ICLR 2023] ReAct: Synergizing Reasoning and Acting in Language Models'
  full_name: ysymyth/ReAct
  license: MIT
  pushed_at: '2024-02-06'
  stars: 4091
  url: https://github.com/ysymyth/ReAct
source_url: https://x.com/tom_doerr/status/writer-test-1
summary: ReAct interleaves language-model reasoning with tool actions and observations,
  improving groundedness and long-horizon control. Its influential design is compelling,
  though the original evidence relies on constrained benchmarks and a closed 540B
  model.
tags:
- react
- llm-agents
- tool-use
- chain-of-thought
- interactive-decision-making
- retrieval
title: 'ReAct: The Thought–Action Loop Behind Modern LLM Agents'
topics:
- ai
- ai/llm
- ai/llm/agents
---

## Summary

ReAct is a prompting framework that lets a language model alternate between free-form reasoning traces, task-specific actions, and observations from an external environment. Instead of forcing an LLM to solve a problem entirely from its parameters or to emit actions without an explicit plan, ReAct uses “thoughts” to decompose goals, track state, revise plans, and decide what information to retrieve; actions then ground the next round of reasoning in Wikipedia results or environment feedback.

The paper evaluates this pattern with frozen PaLM-540B on four quite different tasks: HotpotQA multi-hop question answering, FEVER fact verification, the ALFWorld text environment, and WebShop navigation. Reasoning is dense and regularly alternated with retrieval for the knowledge tasks, but sparse and model-timed for long-horizon decision making. The method itself is strikingly small: manually written few-shot trajectories teach the model a protocol rather than changing its weights.

The central result is not that verbal reasoning always wins. ReAct is more grounded than chain-of-thought but can be less flexible, and the strongest knowledge-task setup combines ReAct with chain-of-thought self-consistency. The broader idea—that an LLM agent should maintain an explicit working trace while repeatedly observing the consequences of tool calls—became foundational because it turns generation into a closed feedback loop.

## Key Contributions

- Introduces a unified thought–action–observation interface in which language reasoning becomes part of an agent’s augmented action space.
- Demonstrates the same prompting pattern across four domains using only 1–6 in-context examples: HotpotQA, FEVER, ALFWorld, and WebShop.
- On FEVER, ReAct scores 60.9 versus 56.3 for chain-of-thought; on HotpotQA it scores 27.4 versus 29.4, showing that grounding improves one benchmark without universally improving accuracy.
- In a manual analysis of 200 HotpotQA trajectories, hallucinated facts appeared in 14% of successful chain-of-thought cases versus 6% for ReAct; hallucination accounted for 56% of chain-of-thought failures, while uninformative search accounted for 23% of ReAct failures.
- Combining ReAct with chain-of-thought self-consistency reaches the performance of 21 self-consistency samples with only 3–5 samples, according to the paper.
- On 134 unseen ALFWorld games, the best ReAct prompt reaches 71% success, versus 45% for action-only prompting and 37% for BUTLER; even the worst ReAct trial reaches 48%. Across six controlled prompt trials, its relative gain over action-only prompting averages 62%.
- On WebShop’s 500-test-instruction evaluation, one-shot ReAct improves the previous best success rate by 10 absolute percentage points. The paper’s headline improvements over trained imitation or reinforcement-learning baselines are 34 points on ALFWorld and 10 points on WebShop.
- Bootstrapping 3,000 successful trajectories to fine-tune PaLM-8B and PaLM-62B reverses the poor small-model few-shot result: fine-tuned ReAct becomes the best of the four tested formats, and PaLM-62B ReAct exceeds all PaLM-540B prompting variants.

## My Take

### Strengths

I think ReAct’s lasting contribution is architectural clarity, not a particular benchmark score. It identifies a useful control loop—reason, call a tool, inspect reality, update the plan—and expresses it in a format that is easy to prototype without training. The controlled action-only ablations are persuasive: on ALFWorld, removing thoughts from otherwise matched demonstrations produces large, consistent losses.

I also value that the paper exposes conflicting objectives rather than presenting reasoning traces as magic. External lookup reduces unsupported factual invention, while rigid alternation can introduce loops and reasoning errors. The hybrid with self-consistent chain-of-thought is a pragmatic acknowledgement that parametric knowledge and retrieval each fail differently.

### Weaknesses

The evidence is much narrower than the “general paradigm” framing suggests. All four environments expose textual, highly constrained action spaces; Wikipedia offers only three actions, ALFWorld is synthetic, and WebShop is a benchmark where “buy” has no real-world consequence. Nothing here establishes reliability under open-ended browsing, changing tools, authentication, irreversible actions, adversarial content, or multi-user state.

The main model is the unavailable 540B-parameter PaLM, which makes exact reproduction impossible. Prompt trajectories are manually authored, prompt counts are tiny, and the headline ALFWorld result is the best of six trials rather than an average. The paper does report the worst trial, but selecting the best prompt overstates what a user should expect from an arbitrary prompt.

Claims of interpretability and trustworthiness also run ahead of the evaluation. Readable reasoning is useful for debugging, but it is not necessarily faithful to the computation that produced an action. The human study is a manual error analysis of sampled trajectories, not a rigorous test that users can predict failures or safely supervise the agent. Meanwhile, ReAct still loops, follows bad retrieval, and depends on model-generated text as working memory. On longer tasks, that trace consumes context and compounds errors.

Finally, the comparisons are historically informative but not clean measures of sample efficiency. ReAct inherits vast pretraining knowledge from PaLM-540B, whereas imitation and reinforcement-learning baselines are counted mainly by task-specific trajectories. Saying that a few demonstrations beat methods trained on thousands of instances is true within the reported setup, but it is not evidence that the total learning cost is lower.

### Potential Applications

The pattern is a strong fit for research assistants that alternate between hypothesis formation and database search, coding agents that inspect test output before revising code, support systems that query structured records, and workflow agents that must track multi-step state. I would use ReAct where actions are observable, reversible, and permission-bounded, with the trace treated as a debuggable scratchpad rather than proof of correctness.

### Next Directions

The obvious next step is to replace unconstrained “thought” text with typed state: explicit goals, evidence with provenance, uncertainty, tool results, and termination conditions. That would make loops and unsupported claims easier to detect while reducing context growth.

I would also want evaluations on tool errors, prompt injection, stale observations, long horizons, and irreversible actions, plus cost and latency curves rather than success rate alone. Stronger work should compare hidden versus visible scratchpads, test whether explanations are causally faithful, and separate planning quality from retrieval quality. Training a policy across many tools may improve robustness, but only if paired with permissions, rollback, and independent verification.

## Reliability

The authors are Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, and Yuan Cao. The paper lists Yao and Narasimhan with Princeton email addresses, the other five authors with Google email addresses, and notes that Yao’s work was done during a Google internship; the acknowledgments name the Google Brain team and Princeton NLP Group.

The supplied record dates the arXiv posting to October 6, 2022. The GitHub metadata describes the work as ICLR 2023. Code and prompts are available in the public `ysymyth/ReAct` repository, which the supplied metadata records at 4,091 stars, MIT licensed, not archived, and last pushed on February 6, 2024. The paper nevertheless states that its principal PaLM model was not openly accessible, so code availability does not make the headline experiments fully reproducible.

I give the qualitative idea and the controlled action-only ablations substantial weight: the results span four benchmarks and include useful failure analysis. I give the exact performance claims moderate weight because the main model is closed, demonstrations are hand-built, prompt selection matters, and the environments are constrained. Readers should treat ReAct as a highly influential design pattern with solid early evidence, not as proof that visible reasoning makes deployed agents reliable.

## Links

- [arXiv page](https://arxiv.org/abs/2210.03629)
- [PDF](https://arxiv.org/pdf/2210.03629)
- [GitHub repository](https://github.com/ysymyth/ReAct)
- [Original social post](https://x.com/tom_doerr/status/writer-test-1)
- [Project page](https://react-lm.github.io/)