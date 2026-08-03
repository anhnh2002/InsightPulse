---
date: '2026-08-01'
description: Một ứng dụng web do cộng đồng phát triển có thể đọc toàn bộ PDF và hình
  ảnh, rồi xuất thành Markdown, trang web, Word hoặc dữ liệu có cấu trúc. Công cụ
  còn cố gắng giữ lại bảng biểu, hình ảnh, công thức và bố cục tài liệu.
draft_id: 20260802-abf8072f
item_kind: news
item_source: x
kol: tom_doerr
reliability:
  authors_orgs: Community developer rdumasia303; the underlying model is DeepSeek-OCR.
  code_available: true
  evidence: Public MIT-licensed repository with 1,879 stars; last push recorded on
    2026-03-31.
  venue: Published on GitHub and shared in a post by Tom Dörr on X.
repo:
  description: A quick vibe coded app for deepseek OCR
  full_name: rdumasia303/deepseek_ocr_app
  license: MIT
  pushed_at: '2026-03-31'
  stars: 1879
  url: https://github.com/rdumasia303/deepseek_ocr_app
social:
  author: Tom Dörr
  created_at: '2026-08-01T23:51:24+00:00'
  text: 'A modern DeepSeek OCR web application capable of processing entire PDF documents
    and images while preserving complex formatting, such as LaTeX formulas and table
    structures, for export to Markdown or Word formats.


    https://t.co/1xrB17CqnH https://t.co/pEFnFwLWgU'
source_url: https://x.com/tom_doerr/status/2083702166439477606
summary: Một ứng dụng web do cộng đồng phát triển có thể đọc toàn bộ PDF và hình ảnh,
  rồi xuất thành Markdown, trang web, Word hoặc dữ liệu có cấu trúc. Công cụ còn cố
  gắng giữ lại bảng biểu, hình ảnh, công thức và bố cục tài liệu.
tags:
- deepseek-ocr
- document conversion
- pdf processing
- optical character recognition
- structured documents
- open source
title: Ứng dụng DeepSeek OCR biến PDF scan thành tài liệu có thể chỉnh sửa
topics:
- ai
- ai/multimodal
---

## Chuyện gì đã xảy ra

Lập trình viên rdumasia303 đã công khai một ứng dụng web mã nguồn mở xây dựng trên DeepSeek-OCR. Công cụ nhận hình ảnh hoặc cả tệp PDF, đọc nội dung trên từng trang rồi biến kết quả thành tài liệu có thể chỉnh sửa và tái sử dụng. Nói đơn giản, đây là một máy quét tài liệu hiểu được bố cục tốt hơn.

Phiên bản mới nhất được mô tả trên trang dự án có thể xử lý PDF tối đa 100 MB, hiển thị tiến độ theo từng trang, tách hình ảnh và xuất sang Markdown, HTML, Word hoặc JSON. Ứng dụng cũng cố giữ lại bảng, tiêu đề và công thức toán viết bằng LaTeX. Đây là dự án của cộng đồng, không phải sản phẩm chính thức từ DeepSeek.

> Bước tiến hữu ích không chỉ là đọc được một trang, mà là dựng lại trang đó thành tài liệu có thể chỉnh sửa.

{{< source-post >}}

## Vì sao đáng chú ý

Công cụ nhận dạng chữ truyền thống thường chỉ trả về một mớ văn bản lộn xộn. Điều đó đặc biệt phiền khi bản gốc là hóa đơn, bài nghiên cứu, hồ sơ pháp lý hay báo cáo — nơi bảng biểu và bố cục cũng mang thông tin. Ứng dụng này muốn giữ lại nhiều cấu trúc hơn, qua đó rút ngắn quãng đường từ tài liệu scan đến ghi chú có thể tìm kiếm, tệp Word để chỉnh sửa, trang web hoặc quy trình xử lý dữ liệu.

Đổi lại, chạy công cụ trên máy cá nhân không hề nhẹ. Dự án khuyến nghị dùng card đồ họa NVIDIA, cho biết mô hình cần khoảng 8–12 GB bộ nhớ đồ họa và lần cài đầu phải tải khoảng 5–10 GB. Với người không chuyên kỹ thuật, đây có lẽ phù hợp hơn với một hệ thống do tổ chức cài đặt cho cả nhóm, thay vì một ứng dụng tải về là dùng ngay. Dù vậy, khả năng chạy trên hạ tầng tự quản lý có thể hấp dẫn những nơi xử lý tài liệu nhạy cảm, vì dữ liệu được xử lý trên phần cứng họ kiểm soát.

## Góc nhìn của tôi

Theo tôi, giá trị mới nằm ở cách đóng gói sản phẩm chứ không phải một đột phá mới về khả năng đọc tài liệu. DeepSeek-OCR cung cấp năng lực cốt lõi; dự án này bổ sung những thứ cần cho công việc hằng ngày: xử lý trọn tệp PDF, báo tiến độ, tách hình và xuất ra các định dạng thực sự hữu dụng.

Điểm đáng giá nhất là nỗ lực giữ nguyên cấu trúc. Đây là yếu tố quyết định một công cụ tài liệu sẽ tiết kiệm hàng giờ hay âm thầm tạo thêm lỗi. Câu hỏi chưa có lời đáp là độ chính xác trên tài liệu xấu ngoài đời: trang scan bị nghiêng, chữ viết tay, hợp đồng dày đặc, ô bảng bị gộp và công thức lạ. Trang dự án liệt kê nhiều khả năng, nhưng tài liệu nguồn không có so sánh độc lập hay số đo độ chính xác. Tôi sẽ dùng công cụ để tạo bản nháp nhanh, sau đó đối chiếu mọi con số, điều khoản và phương trình quan trọng với bản gốc.

Điều đáng theo dõi tiếp theo không hào nhoáng bằng một danh sách tính năng mới: các bài kiểm tra có thể lặp lại trên tài liệu khó, cảnh báo rõ khi mô hình không chắc chắn và cách cài đặt dễ hơn cho người không có card đồ họa mạnh. Những cải tiến đó mới có thể biến một bản trình diễn hứa hẹn thành hạ tầng văn phòng đáng tin cậy.

## Thuật ngữ

- **DeepSeek-OCR** — Một hệ thống AI được thiết kế để đọc chữ và cấu trúc từ hình ảnh tài liệu.
- **OCR (nhận dạng ký tự quang học)** — Phần mềm biến chữ trong ảnh hoặc bản scan thành văn bản có thể chọn và tìm kiếm.
- **mã nguồn mở** — Phần mềm có mã lập trình được công khai để mọi người xem, sửa và chia sẻ theo giấy phép.
- **PDF** — Định dạng tệp phổ biến giúp tài liệu hiển thị nhất quán trên nhiều thiết bị.
- **Markdown** — Cách đơn giản để tạo tiêu đề, danh sách và liên kết bằng ký hiệu trong văn bản thuần.
- **HTML** — Bộ chỉ dẫn tiêu chuẩn dùng để tạo cấu trúc cho trang web.
- **JSON** — Định dạng văn bản sắp xếp thông tin thành các trường có nhãn để phần mềm khác đọc.
- **LaTeX** — Hệ thống soạn thảo thường được dùng để biểu diễn công thức toán học.
- **card đồ họa NVIDIA** — Linh kiện máy tính có thể thực hiện các phép tính nặng mà nhiều công cụ AI cần.
- **bộ nhớ đồ họa** — Bộ nhớ tốc độ cao trên card đồ họa, được dùng khi xử lý hình ảnh và mô hình AI.

## Liên kết

- [Trang dự án và thông báo](https://github.com/rdumasia303/deepseek_ocr_app)
- [Kho mã nguồn GitHub](https://github.com/rdumasia303/deepseek_ocr_app)
- [Bài đăng gốc trên X](https://x.com/tom_doerr/status/2083702166439477606)