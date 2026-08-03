---
date: '2026-07-27'
description: Anthropic cho biết Claude dùng một workspace nội bộ nhỏ để chia sẻ khái
  niệm giữa các bước reasoning. Công cụ mới có thể quan sát một phần hoạt động này,
  nhưng vẫn có giới hạn rõ ràng.
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
summary: Anthropic cho biết Claude dùng một workspace nội bộ nhỏ để chia sẻ khái niệm
  giữa các bước reasoning. Công cụ mới có thể quan sát một phần hoạt động này, nhưng
  vẫn có giới hạn rõ ràng.
tags:
- anthropic
- claude
- j-space
- jacobian lens
- llm reasoning
- interpretability
title: Anthropic tìm thấy workspace chung bên trong reasoning của Claude
topics:
- ai
- ai/llm
- ai/llm/reasoning
---

## Chuyện gì đã xảy ra

Anthropic vừa công bố một nghiên cứu về phần xử lý “thầm lặng” bên trong Claude. Nói đơn giản là, giữa rất nhiều hoạt động diễn ra cùng lúc, model dường như có một chiếc bảng chung nhỏ. Thông tin quan trọng được đặt lên đó để nhiều phần khác cùng dùng. Nhóm nghiên cứu gọi vùng này là J-space.

{{< source-post >}}

Họ quan sát J-space bằng một phương pháp mới mang tên Jacobian lens. Khi đổi khái niệm quốc gia trên “chiếc bảng” từ France sang China, nhiều câu trả lời liên quan cũng đổi đồng bộ: thủ đô, ngôn ngữ, châu lục và tiền tệ. Điều đó cho thấy các phép xử lý khác nhau có thể đang đọc cùng một biểu diễn chung. Anthropic cũng mở mã nguồn công cụ để cộng đồng thử trên các model open-weight.

## Vì sao đáng chú ý

Với người xây hoặc kiểm tra hệ thống AI, đây có thể là một cửa sổ nhìn vào phần reasoning không xuất hiện trong câu trả lời cuối. Trong các bài audit, nhóm tác giả cho biết tín hiệu từ J-space làm lộ ra việc model đang cân nhắc chiến lược, nhận ra mình bị đánh giá, hoặc mang một xu hướng không mong muốn dù đầu ra vẫn trông bình thường. Nghiên cứu cũng gợi ý vì sao viết các bước trung gian có ích: model có thể đưa bớt việc ra ngoài bằng chữ, thay vì nhồi tất cả vào kênh nội bộ vốn hẹp.

Còn với người dùng, ý nghĩa thực tế nằm ở khâu điều tra sự cố. Khi một chatbot trả lời rất trơn tru nhưng đáng ngờ, người kiểm tra có thêm cách tìm xem thông tin nào đã dẫn dắt nó. Tuy vậy, kết quả này không chứng minh Claude có ý thức. Jacobian lens cũng chỉ đọc được một nhóm biểu diễn gắn với từ ngữ, chứ không phải toàn bộ những gì model đang xử lý.

## Thuật ngữ

- **J-space** — Tên Anthropic đặt cho một nhóm nhỏ các biểu diễn nội bộ có thể được nhiều phần trong quá trình tính toán của model cùng sử dụng.
- **Jacobian lens** — Phương pháp ước tính một trạng thái bên trong model đang có khả năng tác động đến những từ nào ở bước sau.

## Liên kết

- [Bài công bố của Anthropic](https://www.anthropic.com/research/global-workspace)
- [Bài nghiên cứu đầy đủ](https://transformer-circuits.pub/2026/workspace/index.html)
- [GitHub repository](https://github.com/anthropics/jacobian-lens)
- [Nguồn LinkedIn ban đầu (meta chỉ cung cấp URL hồ sơ)](https://www.linkedin.com/in/omarsar/)