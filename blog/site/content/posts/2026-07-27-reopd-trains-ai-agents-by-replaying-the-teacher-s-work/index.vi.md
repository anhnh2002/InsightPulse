---
date: '2026-07-27'
description: Microsoft Research và University of Amsterdam giới thiệu ReOPD, cách
  train AI agent từ những lần làm mẫu đã ghi sẵn thay vì liên tục gọi tool. Item này
  chỉ có bài đăng mạng xã hội, chưa kèm link paper hay code.
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
summary: Microsoft Research và University of Amsterdam giới thiệu ReOPD, cách train
  AI agent từ những lần làm mẫu đã ghi sẵn thay vì liên tục gọi tool. Item này chỉ
  có bài đăng mạng xã hội, chưa kèm link paper hay code.
tags:
- reopd
- agent training
- knowledge distillation
- teacher trajectories
- microsoft research
- university of amsterdam
title: ReOPD dạy AI agent bằng cách phát lại quá trình làm mẫu
topics:
- ai
- ai/llm
- ai/llm/training
---

## Chuyện gì đã xảy ra

DAIR.AI vừa chia sẻ trên LinkedIn một nghiên cứu của Microsoft Research và University of Amsterdam mang tên ReOPD. Nói đơn giản là thế này: thay vì bắt agent “thầy” và agent “học trò” chạy lại bài tập từ đầu sau mỗi lần cập nhật, nhóm nghiên cứu dùng lại các quá trình làm mẫu đã lưu sẵn. Agent học trò chỉ thử sức ở một số bước, còn tín hiệu hướng dẫn được lấy từ bản ghi.

{{< source-post >}}

Cách làm này nhắm thẳng vào phần tốn kém nhất khi train agent nhiều bước. Mỗi lượt chạy mới có thể kéo theo các lần gọi môi trường, gọi tool và hỏi lại agent thầy. Với ReOPD, phần luyện tập diễn ra trên dữ liệu phát lại.

> Theo bài đăng, ReOPD không gọi tool khi train agent học trò và mỗi rollout nhanh hơn ít nhất 4 lần.

## Vì sao đáng chú ý

Nếu bạn đang xây agent biết viết Python hoặc tìm kiếm thông tin, bớt các lượt chạy thật đồng nghĩa với vòng thử nghiệm ngắn hơn và chi phí hạ tầng thấp hơn. Người dùng cuối cũng có thể hưởng lợi gián tiếp: agent được cải thiện nhanh hơn mà không cần tăng tương ứng lượng tài nguyên dùng để train.

Đáng chú ý là dữ liệu phát lại cũng có một điểm khó. Khi quá trình luyện tập ngày càng giống cách agent học trò tự hành động, nó có thể đi vào những tình huống mà agent thầy không còn đưa ra hướng dẫn đáng tin cậy. Nhóm nghiên cứu gọi hiện tượng này là “prefix trap”. ReOPD ưu tiên các đoạn đầu của quá trình, nơi độ lệch còn thấp. DAIR.AI cho biết phương pháp giữ nguyên hoặc cải thiện độ chính xác trên bài toán toán học dùng Python và môi trường tìm kiếm, với nhiều cỡ agent thầy và học trò. Tuy vậy, item được cung cấp không có paper, bảng kết quả chi tiết, đánh giá độc lập hay repo code, nên chưa thể đối chiếu các con số này.

## Thuật ngữ

- **Trajectory** — Chuỗi quan sát, quyết định và hành động được ghi lại khi một agent hoàn thành nhiệm vụ.

## Liên kết

- Trang công bố/paper — Item không cung cấp link trực tiếp.
- GitHub repository — Item không cung cấp link repo.
- [Bài đăng LinkedIn gốc của DAIR.AI](https://www.linkedin.com/company/dair-ai/posts/)