# G2 — Tách `app.js` thành ES modules

Ngày: 2026-11-01. Phạm vi: tách `server/static/app.js` (một file ~1.100 dòng) thành
các module theo tính năng, giữ nguyên hành vi giao diện và đường dẫn `/static/app.js`.
Không đổi API REST, không đổi template ID, không thêm thư viện hay bước build.

## 1. Lý do

File gốc gộp xác thực, dashboard, SSE, phòng/thiết bị, biểu đồ, demo, cảm biến,
huấn luyện và chia sẻ. Mỗi lần sửa một tính năng đều phải đọc cả file, dễ đụng nhầm
phần khác. Tách module giúp:

- mỗi file chỉ còn một nhóm chức năng, đọc/sửa nhanh hơn;
- import tường minh cho biết module nào dùng hàm nào;
- service worker cache được từng file; sửa một module không phải tải lại toàn bộ
  giao diện.

## 2. Cấu trúc sau khi tách

```text
server/static/app.js          entry, 14 dòng, import('/static/js/main.js')
server/static/js/
  core.js          hằng số, state, DOM utils, hiệu ứng, api(), lỗi ApiError
  auth.js          đăng nhập/đăng ký, chuyển tab, hiện form khi hết phiên
  dashboard.js     nạp phiên, chọn nhà, SSE + polling, nối các module
  settings.js      phòng, thiết bị, tiến độ hiệu chuẩn
  monitoring.js    vẽ status/history/alerts/metrics, refreshDashboard()
  demo.js          phát fingerprint mẫu, bấm ô phòng ở trang demo
  sensor.js        gửi gia tốc kế từ điện thoại
  training.js      poll trạng thái huấn luyện, cập nhật calibration/metrics
  share.js         mã chia sẻ, danh sách thành viên, sao chép
  main.js          gắn sự kiện, đăng ký service worker, boot
```

`app.js` giữ nguyên đường dẫn cũ để template, bookmark và service worker không phải
đổi. Nội dung còn lại:

```js
import('/static/js/main.js').catch(error => {
  console.error('[An Tâm] không nạp được giao diện:', error);
});
```

Dùng **import động** thay vì `import ... from` để HTML cũ (nạp `app.js` như script
thường, chưa có `type="module"`) vẫn không vỡ cú pháp khi service worker cập nhật
`app.js` trước template.

## 3. Đồ thị import (không có vòng)

```text
main ──► dashboard ──► auth
  │          │  └───► settings
  │          │  └───► monitoring ──► auth
  │          │            │  └────► settings
  │          │            └───────► sensor
  │          ├──► demo ──► monitoring, settings
  │          ├──► sensor
  │          ├──► training ──► monitoring, settings
  │          └──► share
  └──► core (mọi module)
```

Quy ước: `core.js` không import module nào khác. Các module tính năng chỉ import
`core.js` và module thấp hơn; `dashboard.js` là tầng cao nhất trước `main.js`.

## 4. Hai chỗ cần callback để tránh vòng import

1. **`showAuth()` dừng mọi hoạt động.** `auth.js` không thể import
   `dashboard.js`/`demo.js`/`training.js` (những file này đã import `auth.js`).
   `core.js` giữ registry:
   - `registerStop(callback)` — module đăng ký hàm dừng của mình;
   - `stopAllActivity()` — `auth.js` gọi khi hiện form đăng nhập.
   `dashboard.js` đăng ký `stopLiveUpdates`, `demo.js` đăng ký `stopDemo`,
   `training.js` đăng ký `stopTrainingPolling`.
2. **Đổi phòng cần nạp lại nhà.** `settings.js` nhận `reloadHome` làm tham số
   (`renderRooms(reloadHome)`), `dashboard.js` truyền `loadHome`. Tương tự,
   `submitAuth(form, endpoint, onSuccess)` nhận `loadApplication` từ `main.js`.

## 5. Tương thích

- `dashboard.html` và `index.html`: `<script type="module" src="/static/app.js">`.
- `service-worker.js`: cache `an-tam-home-v6`, `APP_SHELL` gồm `app.js` và đủ 10
  module trong `js/`. `/api/*` vẫn bị bỏ qua hoàn toàn nên SSE không bị cache.
- Không đổi ID phần tử, endpoint hay payload; Android Collector và PWA không bị ảnh
  hưởng.
- Trang `index.html` (demo tĩnh) và `dashboard.html` dùng chung `main.js`; phần tử
  không tồn tại được bỏ qua như bản một file.

## 6. Lỗi phát hiện khi smoke và cách sửa

Smoke thật trên trình duyệt (Flask cổng 5099, DB tạm) bấm **Chạy demo** thì hiện:

```text
Không chạy được demo: api is not defined
```

Nguyên nhân: `demo.js` được tách ra nhưng thiếu `api` trong danh sách import từ
`core.js`. Đã thêm `api` và chạy lại: demo phát fingerprint, phòng `Bedroom` sáng,
`TIN CẬY 99%`, lịch sử và trạng thái cập nhật, console không còn lỗi mới.

Đây là lỗi chỉ smoke trình duyệt mới thấy; `node --check` không phát hiện vì cú
pháp hợp lệ, còn import thiếu chỉ lỗi khi gọi hàm.

## 7. Kiểm chứng thật

### Kiểm tra tĩnh

```powershell
# Cú pháp từng file như ES module
$files = @('app.js','js/core.js','js/auth.js','js/dashboard.js','js/settings.js',
  'js/monitoring.js','js/demo.js','js/sensor.js','js/training.js','js/share.js','js/main.js')
foreach ($f in $files) { Get-Content -Raw "server/static/$f" | node --input-type=module --check }
```

Kết quả: **11/11 OK**.

Import graph chạy bằng Node với DOM stub (sao chép sang thư mục tạm có
`package.json` `"type":"module"`): **IMPORT OK**.

ESLint 9 với `no-undef` + `no-unused-vars` trên `app.js` và `js/`: **0 error,
0 warning**.

### Test Python

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -m pytest tests -q
```

Kết quả: **67 passed** (không đổi so với trước khi tách; phần này không sửa Python).

### Smoke trình duyệt thật

Flask cổng 5099, DB tạm `%TEMP%\opencode\smoke-modules.db`, không dùng
`data/smarthome.db`:

1. Trang chủ tải đủ 10 module, tất cả HTTP 200; `/api/stream` trả 200
   `text/event-stream`.
2. Đăng ký tài khoản → dashboard hiện; console chỉ có 401 `/api/auth/me` đúng như
   trước khi đăng nhập.
3. Chạy demo → phòng `Bedroom` sáng, `TIN CẬY 99%`, history/status cập nhật.
4. Thêm phòng, đổi tên phòng → `reloadHome` chạy, danh sách phòng và ô phòng cùng đổi.
5. Tạo rồi thu hồi thiết bị → danh sách và bước tiến độ cập nhật.
6. Mở dialog chia sẻ, tạo mã mới → mã 6 ký tự, thông báo 24 giờ.
7. Bật cảm biến trên HTTP → hiện "Cần Safari qua HTTPS." như cũ.
8. Đăng xuất rồi đăng nhập lại → `submitAuth` + `loadApplication` chạy, dashboard trở lại.
9. Service worker `an-tam-home-v6`: 18 entry, gồm đủ 11 file JS (`app.js` + 10 module).
10. Trang `index.html` (route tạm `/demo`, cổng 5100) tải module và báo lỗi demo
    `HOME_REQUIRED` đúng nghiệp vụ, không lỗi import.
11. HTML cũ nạp `app.js` kiểu classic (cổng 5101) vẫn tải `/static/js/main.js` qua
    dynamic import.

Sau smoke, `data/smarthome.db` vẫn **0 alert, 0 prediction**.

## 8. Giới hạn còn lại

- Chưa có bước build/bundle: trình duyệt tải 11 file JS. Với LAN và HTTP/2 hoặc
  cache service worker thì không đáng kể; nếu cần giảm request có thể thêm bundler
  sau, nhưng sẽ phải đổi quy trình triển khai.
- Service worker dùng network-first cho tài nguyên tĩnh, nên lần tải đầu vẫn cần
  mạng; cache chỉ giúp lần sau và khi offline.
- `app.js` dùng import động nên lỗi nạp module chỉ hiện trong console, không chặn
  trang. Đây là chủ đích để HTML cũ không bị trắng trang.
- Chưa tách CSS; ba file `style.css`, `mobile.css`, `account.css` giữ nguyên.
