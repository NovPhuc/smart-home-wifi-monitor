# 07 — Kiểm tra lỗi và tối ưu lớp giao diện

Phiên 2026‑10‑24/26. Phạm vi: `server/templates/*.html`, `server/static/*.js`, `server/static/*.css`.
Không sửa thuật toán, không sửa dữ liệu, không đụng `models/`, `results/`, `data/`.

Bản gốc của mọi file giao diện được giữ nguyên ở `backup_original/ui_2026-10-24/`.

## 1. Việc đã làm

Trước đây có **ba** file JS giao diện chồng chức năng:

| File | Dùng ở đâu | Nội dung |
|---|---|---|
| `app.js` | không template nào nạp | bản rút gọn chỉ có demo + giám sát |
| `app-v2.js` | `index.html` (trang demo tĩnh) | đầy đủ phần dịch lý do cảnh báo, bấm ô phòng để mô phỏng |
| `app-v3.js` | `dashboard.html` (**trang thật**, `/` trỏ vào đây) | tài khoản, nhiều nhà, chia sẻ, hiệu chuẩn, huấn luyện |

`index.html` không còn được `server/app.py` render ở đâu cả — chỉ `dashboard.html` là trang chạy thật.

Đã **gộp thành một** `server/static/app.js` duy nhất, giữ ưu điểm của cả hai bản và sửa lỗi.
Hai template cùng nạp file này; mọi phần tử không tồn tại trên trang hiện tại đều được bỏ qua
(`on(id, …)` thay cho `$('id').addEventListener(…)`) nên một file chạy được cho cả hai trang.

**Ưu điểm giữ lại từ `app-v2.js`:** dịch đủ 7 mẫu lý do cảnh báo · đổi tên phòng sang tiếng Việt
trong cảnh báo · badge cảm biến đặt lại khi tắt · bấm ô phòng để mô phỏng đúng phòng (trang demo).

**Ưu điểm giữ lại từ `app-v3.js`:** đăng nhập và phiên làm việc · nhiều căn nhà và chia sẻ ·
thiết lập/hiệu chuẩn/huấn luyện · chống XSS bằng `escapeHTML` · chỉ vẽ lại DOM khi dữ liệu đổi.

## 2. Bảng lỗi đã sửa

| # | Lỗi | Vị trí (bản cũ) | Mức | Cách sửa |
|---|-----|-----------------|-----|----------|
| 1 | **Chạy demo thì lưới phòng không bao giờ sáng.** Lưới dựng từ phòng của căn nhà, nhưng model demo trả về 5 phòng tổng hợp (`Bedroom`…). Không ô nào khớp ⇒ không ô nào `active`, còn bảng xác suất lại hiện 5 phòng lạ. | `app-v3.js` `renderRooms()` + `renderStatus()` | CAO | Lưới đổi theo chế độ: đang demo thì dựng từ bộ phòng mẫu, hết demo dựng lại từ phòng thật (`roomGridEntries()`). |
| 2 | **Nhịp cập nhật bị BỎ, không hẹn lại.** `refreshDashboard()` `return` khi đang có request bay. Demo gửi 900 ms/bước còn poll 2000 ms nên rất nhiều nhịp bị nuốt. | `app-v3.js` `refreshDashboard()` | CAO | Đánh dấu `refreshPending` rồi chạy lại một lần ngay khi request hiện tại xong. |
| 3 | **Khoá cache ghi trước khi vẽ.** `lastRenderKey.status = key` chạy trước `renderStatus()`. Nếu `renderStatus` ném lỗi thì lần sau khoá đã trùng ⇒ UI đứng im vĩnh viễn, mà lỗi lại bị `catch` hiểu thành mất mạng nên báo "Mất kết nối" sai. | `app-v3.js` `refreshDashboard()` | CAO | Ghi khoá **sau** khi vẽ thành công; mỗi hàm vẽ bọc trong `safeRender()` để một lỗi vẽ không kéo sập cả nhịp. |
| 4 | `localStorage` gọi trần. Safari riêng tư / chặn lưu trữ ⇒ ném lỗi ngay dòng 21 ⇒ **toàn bộ script chết**, trang trắng. | `app-v3.js` đầu file | CAO (iOS) | Bọc `try/catch` trong đối tượng `storage`. |
| 5 | Không có timeout request. Một request treo làm `Promise.all` treo theo và các nhịp 2 s xếp hàng. | `app-v3.js` `api()` | TB | `AbortController` 8 s, lỗi trả về là `ApiError` có `status`. |
| 6 | `crypto.randomUUID` không có trên HTTP LAN (đúng môi trường triển khai) ⇒ mã thiết bị rơi về `Date.now()`, hai máy mở cùng lúc có thể trùng. | `app-v3.js` dòng 21 | TB | Fallback có thêm phần ngẫu nhiên. |
| 7 | Nhãn nút bị cũ. `setButtonBusy` chỉ lưu nhãn nhàn rỗi **một lần**, nhưng `renderCalibration` đổi chữ nút Huấn luyện ⇒ sau khi xong, nút quay về chữ cũ. | `app-v3.js` `setButtonBusy` | TB | `setButtonLabel()` cập nhật lại nhãn nhàn rỗi mỗi lần đặt chữ. |
| 8 | Nút Huấn luyện có thể kẹt ở "Đang khởi động…" và `disabled` nếu trạng thái việc không phải `TRAINING`. | `app-v3.js` dòng 231 | TB | `renderTrainingJob()` gỡ `aria-busy` và mở lại nút. |
| 9 | **Ba mẫu dịch bị mất** so với `app-v2.js`: chuyển phòng không hợp lệ, lưu trú ban đêm bất thường, di chuyển ban đêm bất thường ⇒ tiếng Anh lọt ra giao diện tiếng Việt. | `app-v3.js` `translateReason()` | TB | Khôi phục đủ 7 mẫu. |
| 10 | Tên phòng trong danh sách cảnh báo không được đổi sang tiếng Việt (khác với mọi chỗ còn lại). | `app-v3.js` `renderAlerts()` | Thấp | Dùng `roomLabel()`. |
| 11 | `#calibrationRooms` bị dựng lại `innerHTML` **mỗi nhịp poll** ⇒ thanh tiến độ không bao giờ chạy được transition (nhảy thẳng tới giá trị mới), mất bôi đen văn bản. | `app-v3.js` `renderCalibration()` | TB | `renderCalibrationRooms()` chỉ dựng lại khi danh sách phòng đổi; các nhịp sau chỉ cập nhật số và `transform`. |
| 12 | Ô phòng là `<div>` nhưng CSS cho `cursor:pointer` mà không có handler ⇒ bấm không làm gì (affordance chết). Đồng thời `.room-tile.active::after` in chữ "Đang ở đây" **trùng** với `<small>` do JS đặt. | `app-v3.js` + `style.css` | Thấp | Ô phòng chỉ để xem: bỏ `pointer`, thêm `role="listitem"` + `aria-current`; thay chữ lặp bằng một chấm báo. |
| 13 | Tắt cảm biến không đặt lại badge (bản v2 có làm). | `app-v3.js` `toggleSensor()` | Thấp | Đặt lại badge và `sensorMeta`. |
| 14 | Nhiều promise không được bắt lỗi: nút Đặt lại, đổi căn nhà, `checkTrainingStatus` sau khi vào nhà, các bước demo ⇒ `unhandled rejection`. | `app-v3.js` nhiều chỗ | TB | Bọc `ignore()` / `try…catch` toàn bộ. |
| 15 | Đăng xuất không dừng vòng poll trạng thái huấn luyện ⇒ tiếp tục gọi API và nhận 401. | `app-v3.js` `showAuth()` | Thấp | `showAuth()` dừng cả poll thường lẫn poll huấn luyện. |
| 16 | Đang chạy demo mà đổi căn nhà thì `demoTimer` vẫn sống, chỉ lớp CSS bị gỡ. | `app-v3.js` `loadHome()` | Thấp | `loadHome()` đặt lại trạng thái demo qua `stopDemo()`. |
| 17 | **Service worker trả về HTML cho MỌI request lỗi**, kể cả CSS/JS. Mất mạng đúng lúc nạp `app.js` ⇒ trình duyệt nhận HTML thay cho script. | `service-worker.js` dòng 36 | TB | Chỉ trả trang chủ khi `request.mode === 'navigate'`. |
| 18 | Service worker ghi cache cả phản hồi 404/500. | `service-worker.js` dòng 33 | Thấp | Chỉ ghi khi `response.ok`. |
| 19 | `APP_SHELL` trỏ `/static/app-v3.js`; đổi tên file là `cache.addAll` ném 404 ⇒ service worker mới không cài được. | `service-worker.js` dòng 7 | TB | Trỏ `/static/app.js`, tăng `CACHE_NAME` lên `an-tam-home-v4`. |
| 20 | `@import` Google Fonts (Manrope) là **mã chết**: `mobile.css` ghi đè `font-family` ở `:root` nên Manrope chưa bao giờ được dùng — chỉ tốn một request chặn render, và hỏng khi máy chủ không có Internet. | `style.css` dòng 1 | TB | Bỏ import, dùng thống nhất font hệ thống. Hình thức hiển thị **không đổi**. |
| 21 | Thanh tiến độ chạy bằng `width` ⇒ mỗi khung hình đều gây layout. | `style.css`, `account.css`, `mobile.css` | Thấp | Chuyển sang `transform: scaleX()` với `transform-origin: left`. |
| 22 | `transition: .25s` trên `.room-tile` = `transition: all`. | `style.css` | Thấp | Nêu đúng thuộc tính. |
| 23 | `:hover` không được gác theo thiết bị ⇒ trên điện thoại, hover dính lại sau khi chạm. | `style.css` | Thấp | Bọc trong `@media (hover: hover) and (pointer: fine)`. |
| 24 | Khối giảm chuyển động đặt `animation-duration: .01ms` nhưng **không** đặt lại `animation-delay`, nên phần tử vẫn nằm ở trạng thái đầu (`opacity: 0`) suốt thời gian trễ. | `mobile.css` | TB (a11y) | Thêm `animation-delay: 0ms` và `transition-delay: 0ms`. |
| 25 | Ô phòng không có ngữ nghĩa, tiêu đề trạng thái an toàn không được thông báo cho trình đọc màn hình. | `dashboard.html` | Thấp (a11y) | `role="list"`/`listitem`, `aria-current`, `aria-live="polite"` cho `#safetyTitle`. |

Chưa sửa (ghi nhận): `/favicon.ico` trả 404 vì template không khai báo icon; có thể trỏ về
`/static/icons/app-icon.svg` nhưng không ảnh hưởng chức năng.

## 3. Chuyển động đã thêm

Nguyên tắc: **chỉ báo cho thứ vừa thật sự đổi**, chạy một lần, chỉ dùng `opacity`/`transform`,
không có vòng lặp vô hạn trên dữ liệu, và giảm chuyển động được xử lý ngay từ đầu.

| Hiệu ứng | Việc gì | Thông số |
|---|---|---|
| `fieldUpdate` | giá trị vừa đổi nhấp nháy nhẹ | 260 ms, `cubic-bezier(.23,1,.32,1)`, `opacity .35→1` + `translateY(3px→0)` |
| `attentionPulse` | vành chú ý một lần: trạng thái an toàn leo thang lên CẦN CHÚ Ý/KHẨN CẤP, bước thiết lập vừa hoàn thành | 900 ms, một lần |
| `tilePop` | ô phòng vừa trở thành vị trí hiện tại | 320 ms |
| `riseIn` | mục mới nhất của dòng thời gian / cảnh báo trượt vào; và nội dung dashboard hiện ra so le sau khi đăng nhập | 260 ms, so le 40 ms |
| `liveBreath` | vòng thở rất nhẹ quanh chấm "trực tuyến" — chỉ báo còn sống | 2,6 s, `ease-in-out` |
| Hộp thoại | mở/đóng đối xứng bằng `@starting-style` + `allow-discrete`: `opacity 0→1`, `scale(.97)→1` | 180 ms, `ease-out` |
| Thanh tiến độ | `transform: scaleX()` mượt khi số mẫu tăng | 320 ms |

**Chủ ý KHÔNG cho nhấp nháy:** thời gian lưu trú, độ tin cậy, điểm bất thường, giờ cập nhật,
số AP, số mẫu. Đây là dữ liệu người dùng đang đọc và chúng đổi theo từng mẫu — nhấp nháy mỗi
2 giây là làm chữ rung lên vô ích. Chỉ vị trí, trạng thái an toàn, mức hoạt động và chỉ số
thực nghiệm (đổi rất ít lần) mới được nhấp nháy.

Giảm chuyển động: `prefers-reduced-motion: reduce` gỡ toàn bộ hiệu ứng gây dịch chuyển, giữ
lại thay đổi màu để trạng thái vẫn đọc được; JS cũng kiểm tra cờ này trước khi thêm lớp hiệu ứng.

## 4. Kiểm chứng đã chạy thật

- `node --check` trên `app.js` và `service-worker.js`: đạt.
- Flask chạy thật (`server/app.py`, cổng 5000), tải `/`, `/static/app.js`, `style.css`,
  `mobile.css`, `account.css`, `service-worker.js`: đều HTTP 200.
- Trình duyệt thật (Playwright) đăng ký tài khoản kiểm thử, vào dashboard, bật/tắt demo:
  **0 lỗi console / 0 lỗi trang**. Lưới phòng đổi đúng thành 5 phòng mẫu khi bật demo và trở
  lại trạng thái khóa khi tắt.
- `/api/status` trả `room=Bedroom`, `status=NORMAL`, 5 xác suất; giao diện hiển thị
  "Phòng ngủ", "AN TOÀN" — khớp dữ liệu thật của máy chủ.

## 5. Ghi chú

- Tài khoản kiểm thử `ui-check-2026-10-24@example.com` được tạo trong `data/smarthome.db`
  (CSDL ứng dụng, không phải tập dữ liệu huấn luyện). Có thể xóa bằng cách xóa người dùng đó.
- `server/static/app-v2.js` và `server/static/app-v3.js` **vẫn còn trên đĩa** nhưng không
  template nào nạp nữa. Giữ lại một nhịp để bản service worker cũ trong máy người dùng còn
  tải được; xóa được khi mọi máy đã nhận bản mới.
