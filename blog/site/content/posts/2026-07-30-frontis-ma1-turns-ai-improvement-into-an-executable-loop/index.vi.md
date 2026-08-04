---
date: '2026-07-30'
description: OpenMLE cho AI agent viết, chạy, sửa và ghép các chương trình machine
  learning, rồi học từ kết quả đo được. Cấu hình mạnh nhất cải thiện rõ rệt điểm số
  được báo cáo trên hai benchmark bản gọn.
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
summary: OpenMLE cho AI agent viết, chạy, sửa và ghép các chương trình machine learning,
  rồi học từ kết quả đo được. Cấu hình mạnh nhất cải thiện rõ rệt điểm số được báo
  cáo trên hai benchmark bản gọn.
tags:
- frontis-ma1
- openmle
- recursive self-improvement
- machine-learning engineering
- program evolution
- ai agents
title: Frontis-MA1 biến việc cải thiện AI thành một vòng lặp chạy được
topics:
- ai
- ai/llm
- ai/llm/agents
---

## Ý tưởng chính

Một team data science thường làm việc theo vòng lặp: viết code, chạy thử, nhìn điểm, sửa lỗi, giữ lại cách làm tốt rồi thử tiếp. Một AI agent có thể viết code khá nhanh. Nhưng để tự điều hành cả chuỗi thí nghiệm kéo dài nhiều giờ, nó cần biết lúc nào nên sửa, lúc nào nên làm lại, và quan trọng nhất là phải nghe kết quả chạy thật thay vì tự tin vào câu trả lời của mình.

OpenMLE biến bài toán đó thành một môi trường có thể chạy và chấm điểm. Trên nền này, nhóm tác giả huấn luyện Frontis-MA1, model 35 tỷ tham số chuyên thực hiện bốn động tác: Draft, Improve, Debug và Crossover. Nói đơn giản là viết bản đầu, nâng cấp, sửa lỗi, rồi ghép phần hay từ nhiều phương án.

Điểm đáng chú ý không chỉ nằm ở việc giải benchmark. Machine learning engineering ở đây đóng vai trò như một phòng thí nghiệm cho câu hỏi lớn hơn: AI có thể cải thiện chính quy trình dùng để tạo ra AI hay không?

## Cách hoạt động

Hãy hình dung một bếp thử món. Frontis-MA1 đưa ra công thức. Hệ thống nấu thật, chấm thật. Công thức nào có tín hiệu tốt mới được đem ra chỉnh tiếp.

```mermaid
flowchart LR
    A[Bài toán machine learning] --> B[Draft một chương trình]
    B --> C[Chạy và chấm điểm]
    C --> D{Chọn bước tiếp theo}
    D -->|Improve| E[Tinh chỉnh phương án tốt]
    D -->|Debug| F[Sửa chương trình lỗi]
    D -->|Crossover| G[Ghép các phần hữu ích]
    E --> C
    F --> C
    G --> C
    C --> H[Giữ kết quả mạnh nhất]
```

OpenMLE-Gym cung cấp những task có thể chạy code và kiểm tra kết quả. OpenMLE-RL dùng chính feedback đó để huấn luyện model. Theo abstract, dữ liệu huấn luyện đã được loại các mẫu trùng với toàn bộ benchmark đánh giá. Mục tiêu là hạn chế chuyện model từng thấy trước đề thi.

Khi làm bài, OpenMLE-Evo không yêu cầu agent nghĩ ra một đáp án hoàn hảo ngay lần đầu. Nó xâu chuỗi bốn động tác thành một cuộc tìm kiếm dài, giống như quản lý cả danh mục thí nghiệm. Bản OpenMLE-Evo-Max còn dùng kinh nghiệm không phụ thuộc benchmark và cho một số nhánh tìm kiếm chạy bất đồng bộ.

## Kết quả

Trên MLE-Bench Lite, mỗi task được chạy tối đa 12 giờ với một RTX 4090 bị giới hạn ở 12 GB bộ nhớ. Medal Average tăng 21,22 điểm phần trăm khi chuyển từ base model sang Frontis-MA1 kết hợp OpenMLE-Evo. Bản Max tăng thêm 10,60 điểm. Hiểu nôm na, cấu hình cuối đạt khoảng 71 trên 100 điểm của thước đo medal tổng hợp, trong khi base model chỉ gần 39.

| Kết quả MLE-Bench Lite | Base model | Frontis-MA1 + OpenMLE-Evo | Frontis-MA1 + OpenMLE-Evo-Max |
|---|---:|---:|---:|
| Medal Average | 39,39% | 60,61% | 71,21% |

Abstract cho biết mức 71,21% vượt GPT-5.5 với Codex và tiến gần GPT-5.6 Sol cùng Kimi K3. Tuy nhiên, phần văn bản được cung cấp không có điểm số cụ thể của ba hệ thống này.

Nhóm tác giả còn thử trên NatureBench Lite, một bộ được giữ riêng, để tách tác dụng của model và framework. Giữ nguyên framework nhưng thay Frontis-MA1 vào giúp Match-SOTA tăng từ 50% lên 70%—tức thêm hai task trong mỗi mười task đạt ngang kết quả tốt nhất đã biết. Giữ nguyên model nhưng chuyển sang OpenMLE-Evo đưa con số từ 20% lên 50%—thêm ba task trong mỗi mười task.

| So sánh trên NatureBench Lite | Trước khi thay | Sau khi thay |
|---|---:|---:|
| Thay bằng Frontis-MA1, giữ nguyên framework | 50% | 70% |
| Thay bằng OpenMLE-Evo, giữ nguyên model | 20% | 50% |

Phạm vi bằng chứng hiện có là hai benchmark bản “Lite”, chưa phải hoạt động engineering ngoài đời không giới hạn. MLE-Bench Lite cũng cho mỗi task một ngân sách tính toán khá dài. Do paper.txt chỉ chứa abstract, ta chưa có số lượng task, khoảng bất định, phân tích lỗi hay ablation đầy đủ. Vì vậy, các con số trên phản ánh đúng kết quả benchmark mà nhóm tác giả báo cáo cho tổ hợp model và search này.

## Thuật ngữ

- **recursive self-improvement** — ý tưởng rằng AI có thể tham gia cải thiện chính công cụ và quy trình dùng để xây AI tốt hơn.
- **Crossover** — thao tác tìm kiếm tạo chương trình mới bằng cách ghép những phần hữu ích từ các chương trình trước.

## Liên kết

- [Trang arXiv](https://arxiv.org/abs/2607.28568)
- [PDF](https://arxiv.org/pdf/2607.28568)
- [GitHub repository](https://github.com/FrontisAI/OpenRSI)