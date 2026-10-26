# Brief giao việc cho GLM 5.3 Flash (chạy qua opencode)

Bạn đang ở trong repo khóa luận **CNTT-KLCN-336 — Định vị trong nhà bằng WiFi Fingerprinting**
(`E:\Downloads\smart-home-wifi-monitor2310\smart-home-wifi-monitor`).

Hãy đọc `AGENTS.md` và `PROGRESS.md` trước khi làm gì.

## Bối cảnh

Một agent khác (DeepSeek) vừa **gộp ba file giao diện** `server/static/app.js`,
`app-v2.js`, `app-v3.js` thành **một** file `server/static/app.js` duy nhất, viết lại
`style.css` / `mobile.css` / `account.css`, sửa `service-worker.js`, và đổi
`server/templates/dashboard.html` + `index.html` sang nạp `/static/app.js`.

Bản gốc của tất cả các file đó nằm ở `backup_original/ui_2026-10-24/` (chỉ để đối chiếu,
**không sửa**).

## Việc của bạn — làm đúng thứ tự

### 1. Soát lại phần giao diện vừa gộp (ưu tiên cao nhất)

Đọc kỹ `server/static/app.js` (bản mới) và `server/templates/dashboard.html`,
`server/templates/index.html`, ba file CSS. Đối chiếu với bản gốc trong
`backup_original/ui_2026-10-24/static/`.

Tìm **lỗi thật**, ví dụ:

- ID phần tử mà JS gọi (`$('...')`, `on('...')`) nhưng không tồn tại trong template
  tương ứng → chức năng chết im lặng.
- Hàm bị gọi trước khi định nghĩa, hoặc dùng biến chưa khai báo.
- `await` thiếu chỗ, promise không được bắt lỗi.
- Chức năng có ở bản cũ mà bản mới làm mất.
- Chồng chéo CSS: luật ở file nạp sau ghi đè làm hỏng giao diện (thứ tự nạp là
  `style.css` → `mobile.css` → `account.css`).
- Selector CSS không còn khớp với HTML/JS sinh ra (ví dụ phần tử đổi từ `width` sang
  `transform`, hoặc class đổi tên).

### 2. Soát phần máy chủ

`server/app.py`, `src/smarthome/*.py`, `scripts/*.py`: lỗi thật (không phải đề xuất
kiến trúc). Đặc biệt kiểm tra các endpoint mà giao diện mới đang gọi:
`/api/auth/*`, `/api/homes*`, `/api/rooms`, `/api/devices`, `/api/calibration`,
`/api/status`, `/api/history`, `/api/alerts`, `/api/metrics`, `/api/training/*`,
`/api/demo/scan`, `/api/sensor`, `/api/reset` — xem kiểu dữ liệu trả về có khớp với
cách giao diện đọc hay không (ví dụ giao diện đọc `metrics.baselines[name].accuracy`,
`calibration.rooms[].required_orientations`, `status.smoothed_probabilities`...).

### 3. Sửa

Chỉ sửa những gì bạn **chứng minh được là lỗi** (kèm `file:dòng`). Sửa nhỏ, đúng chỗ.
Không refactor lớn, không đổi tên hàng loạt, không đổi giao diện tuỳ ý.

### 4. Ghi báo cáo

Ghi kết quả vào `docs/09_glm_review.md`, mỗi mục một dòng:

| # | Lỗi | Vị trí (file:dòng) | Mức độ | Đã sửa? | Cách sửa |
|---|-----|--------------------|--------|---------|----------|

Cuối file ghi rõ: danh sách file bạn đã đổi, và những gì bạn **nghi ngờ nhưng chưa
chắc** (để agent kia kiểm lại).

## Quy tắc bắt buộc (theo AGENTS.md của repo)

- **Không bịa số liệu.** Chỉ báo cáo kết quả chạy thật.
- **Không sửa** `data/`, `models/`, `results/`, `backup_original/`, `.venv/`, `.tmp/`,
  `android_collector/build/`.
- Không xóa file. Muốn bỏ file thì chỉ ghi đề xuất vào báo cáo.
- Không chỉnh thuật toán, không chỉnh tập test, không "làm đẹp" chỉ số.
- Kiểm tra cú pháp sau khi sửa: `node --check server/static/app.js`.
- Chạy `python -m pytest tests -q` (dùng `.venv\Scripts\python.exe`) và ghi lại đúng
  kết quả thật vào báo cáo. Nếu không chạy được thì ghi rõ là không chạy được.
- Máy chủ Flask đang chạy sẵn ở `http://127.0.0.1:5000` — có thể gọi thử API bằng
  `curl`/`Invoke-WebRequest` để kiểm chứng.

## Điều KHÔNG được làm

- Không sửa `server/static/app-v2.js` và `server/static/app-v3.js` (đã ngừng dùng).
- Không tạo thêm file JS/CSS mới cho giao diện.
- Không cài thêm thư viện.
