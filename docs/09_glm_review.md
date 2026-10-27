# Báo cáo soát lỗi UI + server — GLM 5.3 Flash (OpenCode)

Phiên làm việc: 2026-10-26. Thực hiện theo `docs/08_brief_glm_review.md`.
Phạm vi: đối chiếu bản gộp `server/static/app.js`, hai template, ba file CSS với bản gốc
trong `backup_original/ui_2026-10-24/`; đối chiếu shape dữ liệu giữa giao diện và
`server/app.py` + `src/smarthome/`. Không sửa thuật toán, không đụng `data/`, `models/`,
`results/`, `backup_original/`, `.venv/`, `.tmp/`, `android_collector/build/`.

## Bảng lỗi

| # | Lỗi | Vị trí (file:dòng) | Mức độ | Đã sửa? | Cách sửa |
|---|-----|--------------------|--------|---------|----------|
| 1 | Hộp thoại chia sẻ nhà dính sát viền: `dialog` đặt `padding: 0`, chỉ bù đệm qua `dialog form`, nhưng `shareDialog` có sẵn eyebrow, h2 và 2 `<section>` nằm **ngoài** form → nội dung cách mép đúng 1px (đo computed style), nút "Đóng" chật góc trên phải | `server/templates/dashboard.html:90-104` + `server/static/mobile.css:124,155` | TB | ✅ | Thêm `#shareDialog { padding: 24px; }` và `#shareDialog form { padding: 0; }` trong `mobile.css` (sau rule `dialog form`) để nội dung có đệm và form con thẳng hàng với h3. Đo lại: h2/form cách mép 24px, thẳng hàng nhau |
| 2 | Badge trạng thái `COLLECTING` trong suốt: app.js sinh class `badge collecting` nhưng CSS chỉ có `normal/warning/critical/neutral` → chữ trắng nổi trên nền card không có nền badge. Nhà mới ở giai đoạn thu mẫu luôn rơi vào trạng thái này | `server/static/app.js:595` + `server/static/style.css:174-184` | TB | ✅ | Thêm `.badge.collecting { background: #1d3a52; color: var(--blue); }` vào `style.css` (khớp tông xanh của thanh tiến độ hiệu chuẩn). Đo lại: nền `rgb(29,58,82)`, chữ `rgb(104,167,255)` |
| 3 | Môi trường test hỏng: `.venv` không có package `smarthome` (không có editable install, `pip list` không thấy), chạy `pytest tests` thuần báo `ModuleNotFoundError: No module named 'smarthome'`. Ngoài ra `tests/__pycache__/` chứa `.pyc` cũ biên dịch từ bản dự án trước (`E:\Downloads\smart-home-wifi-monitor1006\...`, có cả pyc của Python 3.11/3.12/3.14) khiến traceback hiện đường dẫn dự án cũ, dễ chẩn đoán nhầm | `.venv/` + `tests/__pycache__/` | CAO | ❌ (ngoài quyền) | Tôi chạy lại với `PYTHONPATH=src` → **47/47 pass (29.50s)**. Đề xuất agent chính: chạy `pip install -e .` một lần và xoá `tests/__pycache__/` |
| 4 | Comment đầu file dẫn tới tài liệu không tồn tại: `docs/07_kiem_tra_loi_ui_va_toi_uu.md` không có trong `docs/` (chỉ có 01–06, 08) | `server/static/app.js:10` | T | ❌ | Chỉ là chú thích code. Đề nghị: tạo file 07 hoặc sửa dòng comment |
| 5 | Mất một thông báo phản hồi so với app-v2: khi `devicemotion` không có `acceleration`, bản cũ ghi 'Thiết bị không cung cấp gia tốc tuyến tính.' vào `sensorMeta`, bản gộp im lặng return | `server/static/app.js:808-810` (bản cũ: `backup_original/.../app-v2.js:251-256`) | T | ❌ | Bản gộp khớp hành vi `app-v3.js:172` nên có vẻ chủ đích (tránh ghi đè `sensorMeta` liên tục). Cần agent chính xác nhận |
| 6 | Sau huấn luyện thất bại, nhãn nút train kẹt 'Đang huấn luyện…' cho tới nhịp `/api/status` kế tiếp (~2s) vì nhánh FAILED không đặt lại nhãn nhàn rỗi | `server/static/app.js:879-896` | T | ❌ | Tự hồi phục qua `renderCalibration` từ nhịp poll. Ghi nhận để agent chính cân nhắc đặt lại nhãn trong nhánh FAILED |

## Đối chiếu endpoint — shape dữ liệu khớp

So sánh từng field giao diện đọc với code server trả về, **không thấy lệch**:

- `/api/auth/me`, `/api/auth/login` — `user.display_name/email`, `homes[].id/name/role`, `active_home` (`server/app.py:269-303`; `role` tính trong `storage.list_homes`)
- `/api/homes/<id>/share` GET/POST/DELETE — `{share: {code, expires_at}, ttl_hours}` (`app.py:354-382`, `storage.py:317-328`)
- `/api/homes/<id>/members` — `user_id, display_name, email, joined_at` (`storage.py:363-373`)
- `/api/rooms`, `/api/devices` — `id, name, platform, token_hint, last_seen_at` (`storage.py:455-461`)
- `/api/calibration` — `rooms[].{name, ready, samples, target_samples, orientations, required_orientations, sessions, required_sessions}`, `data_ready`, `model_status`, `localization_ready` (`storage.py:539-581`)
- `/api/status` — đủ `room, demo, confidence, dwell_minutes, anomaly_score, anomaly_threshold, activity.state, transitions_last_hour, reasons[], smoothed_probabilities, signal.quality/visible_access_points, timestamp, calibration, mobile_sensor` (`app.py:608-619`); nhánh rỗng `NO_DATA` được app.js xử lý an toàn (`status.signal || {}` v.v.)
- `/api/history`, `/api/alerts` — `timestamp, room, dwell_minutes, activity.state`; alert `id, status, room, reasons[]` (`storage.py:629-639`)
- `/api/metrics` — `room_model.{accuracy, macro_f1, mean_inference_ms}` (từ `mean_inference_ms_per_sample`, `metrics.py:44`), `anomaly_model.recall`, `baselines{name: {accuracy}}`
- `/api/training/*`, `/api/demo/scan`, `/api/sensor`, `/api/reset`, `/api/export/scans.csv` — đều có route, quyền khớp (member chỉ xem, ghi về owner/token)

## ID và chức năng sau khi gộp

- Đối chiếu từng ID bằng script: `dashboard.html` và `index.html` **không mất ID nào** so với bản gốc; mọi ID app.js gọi đều tồn tại ở template tương ứng (phần tử không có sẽ được `on()`/`$()` bỏ qua an toàn).
- Không phát hiện chức năng của app-v2/app-v3 bị mất. Các khác biệt đều là cải thiện có chủ đích, có chú thích trong code: `api()` thêm timeout 8s + `ApiError`, nhãn nút nhàn rỗi được lưu (`data-idleLabel`), `lastRenderKey` alerts thêm `status` (trước chỉ `id`), `renderCalibrationRooms` chỉ dựng lại DOM khi danh sách phòng đổi, guard `refreshInFlight`, `copyToClipboard` tự trả nhãn sau 1.5s, thêm `try/catch` cho `homeForm`/`deviceForm` (bản cũ để promise chết im lặng).
- CSS cascade: thứ tự nạp `style.css → mobile.css → account.css` hợp lý; các class app.js sinh ra (`is-updated`, `is-alerting`, `is-entering`, `is-new`, `room-tile.active`, `body.member-mode`, `body.demo-mode`, `body.calibration-required`, `progress-track i`, `probability i`, `baseline-list i`) đều có rule tương ứng.

## Kiểm tra chính tả và font/encoding (theo yêu cầu chủ nhà)

- **Encoding**: 13 file liên quan (JS, CSS, template, `app.py`, `storage.py`, `PROGRESS.md`, `docs/08`) đều **UTF-8 hợp lệ, không BOM, không ký tự lỗi U+FFFD**, tiếng Việt có dấu đầy đủ. (Mojibake khi xem qua console PowerShell là do code page của console, không phải file hỏng.)
- **Chính tả**: soát thủ công toàn bộ chuỗi hiển thị (nhãn phòng, trạng thái hoạt động, trạng thái an toàn, thông báo lỗi, câu confirm, tiêu đề mục, hướng dẫn thu dữ liệu) — **không phát hiện lỗi chính tả**. Bản dịch lý do cảnh báo đủ 7 mẫu (bản app-v3 cũ bị rơi 3 mẫu — bản gộp đã khôi phục đúng như ghi chú đầu file).
- **Font**: UI dùng system font stack; việc bỏ `@import` Google Fonts (Manrope) được giải thích trong `style.css:6-10` và cho kết quả hiển thị như cũ — chấp nhận được, không phải lỗi.

## Kiểm chứng đã chạy thật

- `node --check server/static/app.js` → **OK**.
- `.venv\Scripts\python.exe -m pytest tests -q` với `PYTHONPATH=src` → **47 passed in 29.50s**.
- Đo computed style trên fixture tĩnh (chứa đúng 3 file CSS của dự án, dựng lại đúng markup `shareDialog`):
  - Trước fix: `dialog` padding `0px`, h2/form cách mép `1px`, badge collecting nền `rgba(0,0,0,0)`.
  - Sau fix: padding `24px`, h2/form cách mép `24px` (thẳng hàng), badge nền `rgb(29,58,82)` chữ `rgb(104,167,255)`.
- Flask **không** đang chạy ở `:5000` (trái với giả định trong brief) nên không gọi API sống được; phần đối chiếu endpoint trên dựa vào đọc code + bộ test integration 47/47.

## File đã đổi

- `server/static/mobile.css` — thêm 4 dòng (đệm cho `#shareDialog`, hủy đệm kép form con).
- `server/static/style.css` — thêm 3 dòng (rule `.badge.collecting`).
- `docs/09_glm_review.md` — file này.
- `PROGRESS.md` — bổ sung mục phiên 2026-10-26.

## Nghi ngờ nhưng chưa chắc (agent chính kiểm lại)

1. `docs/07_kiem_tra_loi_ui_va_toi_uu.md` được trích dẫn nhưng không tồn tại (bảng lỗi #4).
2. Bỏ thông báo "Thiết bị không cung cấp gia tốc tuyến tính." trong `onDeviceMotion` (bảng lỗi #5) — chủ đích hay làm rơi?
3. Nhãn nút train kẹt ~2s sau FAILED (bảng lỗi #6).
4. Nên xoá `tests/__pycache__/` (pyc cũ trỏ sang bản 1006) và `pip install -e .` vào `.venv` để pytest chạy không cần PYTHONPATH (bảng lỗi #3).
5. `app-v2.js`/`app-v3.js` còn nằm trong `server/static/` nhưng đã không còn template nào nạp — chỉ còn vào lượt cache cũ của service worker; đề nghị để agent chính quyết định xoá hay giữ (tôi không xoá theo quy tắc).

## Cập nhật 2026-10-27 — trạng thái xử lý các mục

| Mục | Trạng thái | Ai xử lý | Ghi chú kiểm chứng |
|---|---|---|---|
| #1 shareDialog padding | ✅ Giữ nguyên fix của GLM | GLM (26/10) | Đã đo computed style trước/sau |
| #2 badge `collecting` | ✅ Giữ nguyên fix của GLM | GLM (26/10) | Đã đo computed style trước/sau |
| #3 env pytest + `__pycache__` | ✅ **Đã sửa** | GLM (27/10) | `pip install -e .` vào `.venv` (import `smarthome` OK) + xoá `tests/__pycache__/`; pytest chạy **không cần PYTHONPATH: 47/47 pass (26.83s)** |
| #4 comment trỏ docs/07 | ✅ **Đã xử lý** | DeepSeek | `docs/07_kiem_tra_loi_ui_va_toi_uu.md` đã tồn tại (82 dòng) |
| #5 mất thông báo gia tốc tuyến tính | ✅ **Đã sửa** | DeepSeek | `app.js`: thêm cờ `sensorAccelerationWarned` — thông báo 1 lần mỗi lần bật cảm biến, không spam `#sensorMeta`; reset cờ trong `toggleSensor` khi bật lại. Đã soát logic: đúng |
| #6 nhãn nút train kẹt sau FAILED | ✅ **Đã sửa** | DeepSeek | `app.js`: nhánh FAILED đặt lại nhãn bằng `setButtonLabel` theo `model_status`, khớp `renderCalibration`. Đã soát logic: đúng |
| #5-phụ app-v2/app-v3.js thừa | ✅ **Đã xoá** | DeepSeek | Hai file đã xoá khỏi working tree; service worker không còn trỏ tới (cache v4 chỉ nạp `app.js`) |

Kiểm chứng ngày 27/10: `node --check server/static/app.js` OK; `pytest tests -q` 47/47 pass.
