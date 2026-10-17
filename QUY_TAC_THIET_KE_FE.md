# Quy tắc thiết kế Frontend (Design Guidelines)

> Áp dụng cho toàn bộ frontend Angular của hệ thống ôn luyện thi vấn đáp. Mọi thành viên phải tuân theo; muốn thay đổi quy tắc thì đề xuất trong nhóm và cập nhật file này trước khi áp dụng.

---

## 1. Nguyên tắc chung

1. **Nhất quán hơn sáng tạo:** cùng loại thao tác phải có cùng giao diện và hành vi ở mọi màn hình.
2. **Không hard-code giá trị thiết kế:** màu, font, khoảng cách, bo góc, bóng đổ chỉ lấy từ **design token** (CSS variables) ở mục 2–5.
3. **Mọi thao tác bất đồng bộ phải có đủ 4 trạng thái:** `loading` → `success` / `empty` / `error`.
4. **Không dùng `alert()`, `confirm()`, `prompt()` của trình duyệt.** Dùng Toast và Dialog dùng chung (mục 7, 8).
5. **Mobile-first, hỗ trợ desktop:** mọi màn hình phải dùng được từ 360px trở lên.
6. **Ngôn ngữ giao diện:** tiếng Việt có dấu, giọng văn lịch sự, ngắn gọn.

---

## 2. Màu sắc

Khai báo trong `src/styles/_tokens.scss` dưới dạng CSS variables. **Component chỉ dùng biến, không dùng mã màu trực tiếp.**

### 2.1 Màu thương hiệu & trung tính

| Token | Giá trị | Dùng cho |
|---|---|---|
| `--color-primary` | `#2563EB` | Nút chính, link, trạng thái active |
| `--color-primary-hover` | `#1D4ED8` | Hover nút chính |
| `--color-primary-soft` | `#DBEAFE` | Nền nhẹ, badge, item được chọn |
| `--color-text` | `#111827` | Chữ chính |
| `--color-text-secondary` | `#4B5563` | Chữ phụ, mô tả |
| `--color-text-muted` | `#9CA3AF` | Placeholder, chú thích, disabled |
| `--color-border` | `#E5E7EB` | Viền input, card, divider |
| `--color-bg` | `#F9FAFB` | Nền trang |
| `--color-surface` | `#FFFFFF` | Nền card, dialog, input |
| `--color-skeleton` | `#E5E7EB` | Khối skeleton |

### 2.2 Màu ngữ nghĩa (semantic)

| Token | Chính | Nền nhẹ | Dùng cho |
|---|---|---|---|
| `success` | `#16A34A` | `#DCFCE7` | Thành công, điểm đạt |
| `warning` | `#D97706` | `#FEF3C7` | Cảnh báo, cần giảng viên xem lại |
| `danger` | `#DC2626` | `#FEE2E2` | Lỗi, xóa, đang ghi âm |
| `info` | `#0284C7` | `#E0F2FE` | Thông tin, đang xử lý |

Đặt tên: `--color-success`, `--color-success-soft`, …

### 2.3 Màu theo nghiệp vụ

| Trường hợp | Quy tắc |
|---|---|
| Điểm ≥ 80% điểm tối đa | `success` |
| Điểm 50% – < 80% | `warning` |
| Điểm < 50% | `danger` |
| Đang ghi âm | Nút/chấm tròn `danger`, có hiệu ứng nhấp nháy nhẹ |
| `transcribing`, `grading` | `info` + spinner |
| `transcription_failed`, `grading_failed` | `danger` |
| `needsHumanReview = true` | Banner `warning` |

### 2.4 Quy tắc

- Không truyền đạt thông tin **chỉ bằng màu**: luôn kèm icon hoặc chữ (ví dụ: "✓ Đạt", "⚠ Cần xem lại").
- Độ tương phản chữ/nền tối thiểu **4.5:1** (WCAG AA).
- Chưa làm dark mode trong MVP, nhưng vì dùng token nên sau này có thể thêm.

---

## 3. Typography (Font chữ)

### 3.1 Font

- **Font chính:** `Be Vietnam Pro` (hỗ trợ tiếng Việt tốt), dự phòng: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.
- **Font monospace** (mã, thời lượng ghi âm `00:45`): `"JetBrains Mono", Consolas, monospace`.
- Chỉ dùng các độ đậm: **400** (thường), **500** (nhấn nhẹ), **600** (tiêu đề), **700** (số điểm lớn).

```scss
--font-family-base: 'Be Vietnam Pro', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
--font-family-mono: 'JetBrains Mono', Consolas, monospace;
```

### 3.2 Thang cỡ chữ

| Token | Cỡ / line-height | Weight | Dùng cho |
|---|---|---|---|
| `--text-display` | 36px / 44px | 700 | Tổng điểm trên trang kết quả |
| `--text-h1` | 28px / 36px | 600 | Tiêu đề trang (1 cái/trang) |
| `--text-h2` | 22px / 30px | 600 | Tiêu đề section |
| `--text-h3` | 18px / 26px | 600 | Tiêu đề card |
| `--text-body` | 16px / 24px | 400 | Nội dung chính, transcript |
| `--text-sm` | 14px / 20px | 400 | Mô tả, label, nội dung bảng |
| `--text-xs` | 12px / 16px | 500 | Badge, chú thích, timestamp |

### 3.3 Quy tắc

- Không dùng cỡ chữ ngoài thang trên.
- Chữ nội dung tối thiểu 14px; input tối thiểu **16px** (tránh iOS tự zoom).
- Không VIẾT HOA toàn bộ câu, trừ badge ngắn.
- Đoạn văn dài (transcript, câu hỏi) giới hạn độ rộng ~ `72ch` để dễ đọc.

---

## 4. Khoảng cách, bo góc, bóng đổ

### 4.1 Spacing (lưới 4px)

| Token | Giá trị |
|---|---|
| `--space-1` | 4px |
| `--space-2` | 8px |
| `--space-3` | 12px |
| `--space-4` | 16px |
| `--space-5` | 24px |
| `--space-6` | 32px |
| `--space-7` | 48px |

- Padding card: `--space-5` (desktop), `--space-4` (mobile).
- Khoảng cách giữa các field trong form: `--space-4`.
- Khoảng cách giữa các section: `--space-6`.

### 4.2 Bo góc

| Token | Giá trị | Dùng cho |
|---|---|---|
| `--radius-sm` | 4px | Badge, checkbox |
| `--radius-md` | 8px | Nút, input |
| `--radius-lg` | 12px | Card, dialog |
| `--radius-full` | 9999px | Avatar, nút ghi âm tròn |

### 4.3 Bóng đổ

| Token | Dùng cho |
|---|---|
| `--shadow-sm` `0 1px 2px rgba(0,0,0,.05)` | Card |
| `--shadow-md` `0 4px 12px rgba(0,0,0,.08)` | Dropdown, toast |
| `--shadow-lg` `0 12px 32px rgba(0,0,0,.12)` | Dialog |

### 4.4 Breakpoint

| Tên | Độ rộng |
|---|---|
| `sm` | ≥ 640px |
| `md` | ≥ 768px |
| `lg` | ≥ 1024px |
| `xl` | ≥ 1280px |

Nội dung chính giới hạn `max-width: 1200px`, căn giữa.

---

## 5. Icon

- Dùng **một bộ icon duy nhất**: Material Symbols (Outlined).
- Kích thước: 16px (trong chữ), 20px (trong nút), 24px (độc lập).
- Nút chỉ có icon **bắt buộc** có `aria-label` và tooltip.

---

## 6. Trạng thái tải dữ liệu (Loading / Empty / Error)

### 6.1 Khi nào dùng loại loading nào

| Tình huống | Dùng | Không dùng |
|---|---|---|
| Tải lần đầu danh sách, card, trang chi tiết | **Skeleton** | Spinner toàn trang |
| Nút đang gửi (lưu, gửi bài) | Spinner nhỏ **trong nút** + disable nút | Khóa toàn màn hình |
| Upload audio | **Progress bar** có % | Spinner không có tiến độ |
| Chờ STT / chấm điểm (lâu, bất đồng bộ) | Màn hình trạng thái: icon + mô tả bước + spinner (vd: "Đang chuyển giọng nói thành văn bản…") | Skeleton |
| Tải lại/làm mới dữ liệu đã có | Giữ dữ liệu cũ + chỉ báo nhỏ (thanh progress mảnh ở trên) | Xóa trắng rồi hiện skeleton |

### 6.2 Quy tắc Skeleton

- Skeleton phải **giống bố cục thật** (cùng số dòng, cùng kích thước card) để tránh nhảy layout.
- Dùng component chung `<app-skeleton>` với các biến thể: `text`, `title`, `avatar`, `card`, `table-row`.
- Màu `--color-skeleton`, hiệu ứng shimmer nhẹ 1.5s; tắt hiệu ứng khi người dùng bật `prefers-reduced-motion`.
- Danh sách: hiển thị 3–6 item skeleton.
- Nếu dữ liệu về dưới **300ms** thì không cần nháy skeleton (có thể delay hiển thị skeleton 200–300ms).

### 6.3 Trạng thái rỗng (Empty state)

Dùng component chung `<app-empty-state>` gồm: icon/hình minh họa, tiêu đề, mô tả ngắn, và **hành động tiếp theo** (nếu có).

> Ví dụ: "Chưa có phiên luyện tập nào" — "Hãy chọn một câu hỏi để bắt đầu luyện tập." — [Chọn câu hỏi]

### 6.4 Trạng thái lỗi (Error state)

- Lỗi tải cả khu vực: `<app-error-state>` với thông điệp thân thiện + nút **"Thử lại"**.
- Không hiển thị lỗi kỹ thuật thô (stack trace, `HttpErrorResponse`, mã 500) cho người dùng; ghi log ở console/dev.
- Lỗi của một thao tác (lưu, gửi) → **Toast lỗi** (mục 7), giữ nguyên dữ liệu người dùng đã nhập.

---

## 7. Toast (thay cho `alert()`)

Dùng service chung `ToastService`; component **không** tự tạo thông báo riêng.

```ts
this.toast.success('Đã lưu câu hỏi');
this.toast.error('Không thể tải lên file ghi âm. Vui lòng thử lại.');
this.toast.warning('Bản ghi âm dài hơn 3 phút sẽ bị cắt.');
this.toast.info('Đang xử lý bài làm của bạn…');
```

| Quy tắc | Giá trị |
|---|---|
| Vị trí | Desktop: góc **trên bên phải**; mobile: **trên cùng giữa** |
| Thời gian tự đóng | success/info: **3s**; warning: **5s**; error: **không tự đóng** hoặc 7s, có nút đóng |
| Số toast hiển thị cùng lúc | Tối đa **3**, mới nhất ở trên |
| Nội dung | 1 câu ngắn, ≤ 80 ký tự; có thể kèm 1 hành động (vd: "Thử lại", "Hoàn tác") |
| Icon | Bắt buộc theo loại (✓, ⚠, ✕, ℹ) |
| Trùng lặp | Không hiện lại toast giống hệt đang hiển thị |

**Khi nào dùng Toast:** phản hồi kết quả thao tác (đã lưu, đã gửi, lỗi mạng).
**Không dùng Toast cho:** lỗi validate form (hiện ngay dưới field), thông tin quan trọng người dùng phải đọc (dùng banner hoặc dialog).

---

## 8. Dialog xác nhận (thay cho `confirm()`)

Dùng service chung `ConfirmDialogService`, trả về `Observable<boolean>`.

- Bắt buộc với thao tác **không hoàn tác được**: xóa câu hỏi/rubric, ghi âm lại (mất bản cũ), rời trang khi đang ghi âm, hủy phiên.
- Tiêu đề là câu hỏi rõ ràng: "Xóa câu hỏi này?"
- Nút hành động ghi **động từ cụ thể** ("Xóa", "Ghi lại"), không ghi "OK"/"Có".
- Thao tác nguy hiểm: nút màu `danger`, đặt bên phải; nút "Hủy" bên trái, focus mặc định vào "Hủy".
- Đóng được bằng phím `Esc` và click ra ngoài (trừ khi đang xử lý).

---

## 9. Nút (Button)

| Loại | Dùng cho | Quy định |
|---|---|---|
| **Primary** | Hành động chính của màn hình | **Tối đa 1** nút primary trong một khu vực |
| **Secondary** (viền) | Hành động phụ | |
| **Ghost / Text** | Hủy, hành động ít quan trọng | |
| **Danger** | Xóa, hủy phiên | Luôn kèm Confirm Dialog |

- Chiều cao: 40px (mặc định), 32px (nhỏ, trong bảng), 48px (lớn, mobile/CTA).
- Vùng chạm tối thiểu **44×44px** trên mobile.
- Đang xử lý: disable + spinner trong nút, giữ nguyên độ rộng; **chặn double-click/gửi trùng**.
- Nhãn nút: động từ + đối tượng ("Gửi bài", "Lưu rubric"), không quá 3 từ nếu có thể.

---

## 10. Form & Validation

- Dùng **Reactive Forms**.
- Label luôn hiển thị phía trên input (không chỉ dùng placeholder thay label).
- Field bắt buộc đánh dấu `*` màu `danger`.
- Hiện lỗi **khi rời field (blur)** hoặc khi bấm gửi, không hiện lỗi ngay khi vừa gõ ký tự đầu.
- Thông báo lỗi nằm **ngay dưới field**, màu `danger`, cỡ `--text-sm`, nói rõ cách sửa: "Điểm tối đa phải từ 1 đến 100".
- Khi gửi form lỗi: cuộn và focus vào field lỗi đầu tiên.
- Form có thay đổi chưa lưu mà người dùng rời trang → Confirm Dialog.
- Rubric editor: hiển thị **tổng điểm realtime**, cảnh báo nếu tổng ≠ điểm tối đa của câu hỏi.

---

## 11. Quy tắc riêng cho màn hình nghiệp vụ

### 11.1 Ghi âm

- Nút ghi âm tròn, lớn (≥ 64px), ở vị trí dễ bấm; trạng thái rõ ràng: *Sẵn sàng* → *Đang ghi (đỏ, nhấp nháy, đồng hồ đếm)* → *Đã ghi (nghe lại / ghi lại / gửi)*.
- Luôn hiển thị thời lượng `mm:ss` (font mono) và giới hạn tối đa.
- Quyền micro bị từ chối / không có micro → hiển thị **hướng dẫn** cách cấp quyền, không chỉ báo lỗi.

### 11.2 Transcript

- Hiển thị trong vùng soạn thảo rộng, font `--text-body`, có nhãn "Bản ghi do AI tạo — vui lòng kiểm tra và chỉnh sửa trước khi chấm".
- Nút "Xác nhận & chấm điểm" là primary duy nhất.

### 11.3 Kết quả

- Tổng điểm dùng `--text-display`, màu theo mục 2.3.
- Mỗi tiêu chí là một card: tên, điểm/điểm tối đa (progress bar), bằng chứng, thiếu/sai, gợi ý.
- Luôn có dòng chú thích: "Kết quả do AI đánh giá, chỉ mang tính tham khảo."

---

## 12. Văn bản giao diện (UX writing)

- Xưng hô: dùng "bạn"; không dùng "mày/tôi", không dùng giọng ra lệnh.
- Thông báo lỗi: **chuyện gì xảy ra + làm gì tiếp theo**. ✅ "Không kết nối được máy chủ. Vui lòng kiểm tra mạng và thử lại." ❌ "Error 500".
- Ngày giờ: `dd/MM/yyyy HH:mm` (vd: `15/10/2026 13:49`); thời gian tương đối cho mục gần đây ("5 phút trước").
- Số điểm: tối đa 1 chữ số thập phân, dấu phẩy thập phân theo tiếng Việt (`7,5/10`).
- Thống nhất thuật ngữ: *học phần*, *câu hỏi*, *rubric (tiêu chí chấm)*, *phiên luyện tập*, *bản ghi (transcript)*.

---

## 13. Khả năng truy cập (Accessibility) tối thiểu

- Toàn bộ thao tác dùng được bằng bàn phím; có viền focus rõ (`outline` 2px `--color-primary`), **không** `outline: none`.
- Ảnh/icon có ý nghĩa phải có `alt`/`aria-label`.
- Toast dùng `aria-live="polite"` (lỗi dùng `assertive`).
- Tôn trọng `prefers-reduced-motion`.

---

## 14. Animation

- Thời lượng: 150ms (hover, focus), 200–250ms (mở dialog, toast, dropdown).
- Easing: `ease-out` khi xuất hiện, `ease-in` khi biến mất.
- Không dùng animation trang trí gây mất tập trung.

---

## 15. Component dùng chung (bắt buộc dùng, không tự viết lại)

| Component / Service | Vị trí | Mục đích |
|---|---|---|
| `ToastService` | `core/services/` | Thông báo |
| `ConfirmDialogService` | `core/services/` | Xác nhận thao tác |
| `<app-skeleton>` | `shared/components/` | Skeleton loading |
| `<app-empty-state>` | `shared/components/` | Trạng thái rỗng |
| `<app-error-state>` | `shared/components/` | Trạng thái lỗi + thử lại |
| `<app-page-header>` | `shared/components/` | Tiêu đề trang + breadcrumb + hành động |
| `<app-status-badge>` | `shared/components/` | Badge trạng thái phiên (`PracticeStatus`) |
| `<app-score-display>` | `shared/components/` | Hiển thị điểm + màu theo ngưỡng |
| `HttpErrorInterceptor` | `core/interceptors/` | Chuẩn hóa lỗi API, gọi toast cho lỗi chung (mất mạng, 401, 500) |

Cần component mới dùng chung → thêm vào `shared/` và cập nhật bảng này.

---

## 16. Quy ước code giao diện & Cấu trúc Component

- **Cấu trúc 3 file bắt buộc cho mỗi Component:** Mỗi component nằm trong một thư mục riêng gồm 3 file tách biệt, không dùng inline template/style:
  - `[name].component.ts` (Logic TypeScript)
  - `[name].component.html` (Template giao diện)
  - `[name].component.scss` (Style riêng)
  - `[name].component.spec.ts` (Unit test, tùy chọn)
- **Tự động hóa CLI:** Đã cấu hình `angular.json` để lệnh `ng g c [tên]` luôn tự động sinh ra 3 file rời (`.html`, `.scss`, `.ts`).
- **Style:** SCSS; token trong `src/styles/_tokens.scss`, style chung trong `src/styles.scss`.
- **Không dùng `!important`** (trừ ghi đè thư viện bên thứ ba, phải có comment lý do).
- **Không viết inline style** trong file HTML template.
- **Class đặt theo BEM:** `.question-card__title--active`.
- **Đơn vị:** `rem` cho font/khoảng cách (token đã quy đổi), `px` chỉ cho border/shadow.

---

## 17. Checklist trước khi tạo Pull Request

- [ ] Không có `alert()`, `confirm()`, `prompt()`.
- [ ] Không có mã màu / cỡ chữ / khoảng cách hard-code; chỉ dùng token.
- [ ] Có đủ trạng thái loading (skeleton), empty, error + thử lại.
- [ ] Nút gửi có disable + spinner, không gửi trùng.
- [ ] Thông báo kết quả dùng `ToastService`; thao tác nguy hiểm dùng `ConfirmDialogService`.
- [ ] Form có validate và thông báo lỗi dưới field.
- [ ] Kiểm tra ở 360px (mobile) và 1280px (desktop).
- [ ] Dùng được bằng bàn phím, có focus rõ.
- [ ] Văn bản tiếng Việt có dấu, đúng thuật ngữ mục 12.

