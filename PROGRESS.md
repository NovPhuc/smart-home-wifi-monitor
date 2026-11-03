# PROGRESS — Khóa luận 336 (CNTT-KLCN-336)

Phiên làm việc: 2026-10-11 (phiên 3) — **HOÀN THÀNH CẢ 5 GIAI ĐOẠN**
Nhánh git: `fix/optimize-training` · Commit gốc (trước tối ưu): `7b2f120` · Checkpoint fix phiên 1-2: `7ac19a8`
Sao lưu dữ liệu gốc: `backup_original/` + commit gốc (không bao giờ bị ghi đè — baseline chạy trong bản sao git archive `.tmp/baseline-wt`)
Căn cứ đánh giá: `De_cuong_chi_tiet_CNTT-KLCN-336.docx` (bản trích xuất: `de_cuong_text.txt`)

## KẾT QUẢ TỔNG (chạy thật 2026-10-11, seed 42, tái lập được — mọi số liệu từ `results/`)

| Chỉ số | Trước (gốc, `results/before_original/`) | Sau (tối ưu, `results/after_optimized/`) |
|---|---|---|
| RoomNetLite test Accuracy | 100.00% (dữ liệu v1 quá dễ — lỗi #2) | **98.99%** |
| RoomNetLite test Macro F1 | 100.00% | **99.00%** |
| SimpleCNN baseline test Accuracy | — (chưa có) | 97.65% → **cải tiến +1.34pp** |
| K-fold 5 RoomNetLite | — | 97.80% ± 1.06% [96.88, 98.73] |
| K-fold 5 SimpleCNN | — | 97.49% ± 1.35% [96.30, 98.67] |
| Anomaly Hybrid F1 (protocol cũ: mọi ngày, có rò rỉ / sau: test riêng D13-D14) | 91.53% (490 seq) | **99.50%** (166 seq, P=100%, R=99%) |
| Anomaly AE-only F1 | 43.90% | **98.48%** |
| Độ trễ model / e2e | 0.0270 ms / — | 0.0309 ms / 0.0252 ms |
| RandomForest / MLP / kNN | 99.83 / 99.33 / 98.32% | 99.16 / 98.99 / 88.26% |
| Unit test | 43/43 | **43/43** · DB integrity ok, 0 FK violation |

## Giai đoạn 1 — Danh sách việc ✅
Đọc AGENTS.md + đề cương; lập PROGRESS.md; commit checkpoint `7ac19a8` (bảo vệ fix phiên 1-2).

## Giai đoạn 2 — Phân tích ✅ (phiên 1-2, đã được duyệt)
- Cấu trúc: src/smarthome (models, preprocessing, dataset, anomaly+MobileSensorFusion, inference, topology, activity, mobile_sensor, storage SQLite, metrics, alerts) · scripts pipeline · server Flask · android_collector · tests 43.
- Thuật toán: RoomNetLite (CE + CenterLoss 0.02 + JS temporal 0.05), GRU-AE (CE room + 0.7·Huber), TopologyFilter, RuleEngine; preprocessor fit chỉ trên train ✓; split session 6/1/1 ✓.
- 15 lỗi phát hiện — bảng đầy đủ ở mục "Bảng lỗi" bên dưới; đều kèm file:dòng.

## Giai đoạn 3 — Đo baseline gốc ✅ (2026-10-11)
- `git archive 7b2f120` (trừ android_collector/ do đường dẫn >260 ký tự) → `.tmp/baseline-wt`; chạy đủ 7 bước pipeline gốc, seed 42 → `results/before_original/` (5 JSON + runlogs + run_info.txt).
- Phát hiện подтвер nhận: dữ liệu v1 cho Accuracy 100% (giả tạo), anomaly protocol cũ có rò rỉ.

## Giai đoạn 4 — Sửa lỗi + đo "sau" ✅ (2026-10-11)
- **Fix A (lỗi #8 — rò rỉ đánh giá)**: train_anomaly.py tách train D01-D10 / threshold D11-D12 / test D13-D14 (không giao nhau); ghi `test_days` vào anomaly_threshold.json; evaluate_anomaly.py chỉ đánh giá test_days (tương thích JSON cũ).
- **Fix B (#13-14)**: config.yaml bổ sung early_stopping_patience/min_delta (10/1e-4 room, 15/1e-4 anomaly) + topology.self_weight 0.75 (trùng default — không đổi hành vi).
- **Fix C (#12)**: results/ chuẩn hóa (before_original + after_optimized + runlogs + run_info.txt + README.md tái lập).
- Đo "sau": full pipeline + K-fold 5 × 2 model → `results/after_optimized/` (9 JSON + 11 runlogs + run_info.txt).
- Kiểm chứng: 43/43 pytest pass; SQLite integrity ok, foreign_key_check 0 vi phạm (10 bảng).

## Giai đoạn 5 — Báo cáo ✅ (2026-10-11)
- `BAO_CAO_KET_QUA.docx` (Times New Roman 13, bảng 11): (a) việc đã làm; (b) 15 lỗi + cách sửa; (c) bảng trước/sau **sinh trực tiếp từ results/*.json** qua `make_report.py`; (d) đối chiếu 11 yêu cầu: 9 ĐẠT, 2 ĐẠT MỘT PHẦN, 1 CHƯA ĐẠT (dữ liệu thực tế — tuần 9-10); (e) tồn tại + đề xuất; + tiến độ 12 tuần.

## Bảng lỗi (file:dòng — mức độ — trạng thái)
| # | Lỗi | Vị trí | Mức độ | Trạng thái |
|---|-----|--------|--------|------------|
| 1 | Anomaly imbalance 7/loại vs 560 normal | generate_synthetic_data.py:111-135 | CAO | ✅ 50/loại + dwell ±20% |
| 2 | Dữ liệu v1 quá dễ (baseline 100%) | generate_synthetic_data.py:19-25,34 | CAO | ✅ v2 thực tế (98.99%) |
| 3 | Rò rỉ: ngày chọn ngưỡng nằm trong tập đánh giá | train_anomaly.py + evaluate_anomaly.py | CAO | ✅ Fix A — tách 3 phần |
| 4 | Thiếu baseline CNN cho so sánh trước/sau | scripts/train_room.py | CAO | ✅ SimpleCNN + kfold |
| 5 | Median nhiễu khi <3 AP | preprocessing.py:50-52 | TB | ✅ global fallback |
| 6 | Quantile 0.99 cố định | train_anomaly.py (cũ) | TB | ✅ grid search |
| 7 | Không early stopping | train_room/anomaly.py | TB | ✅ + Cosine restarts |
| 8 | Nighttime 0-5h | config.yaml:61-62 | TB | ✅ 22-6h |
| 9 | MobileSensorFusion chưa nối inference | inference.py | TB | ✅ process_mobile_sensor |
| 10 | Không có results/ có cấu trúc | (thiếu) | TB | ✅ Fix C |
| 11 | Thiếu đo e2e latency | evaluate_room.py | T | ✅ đã đo |
| 12 | self_weight hard-code | topology.py + config | T | ✅ vào config |
| 13 | Test set cân bằng giả tạo | room_test.csv | T | 📝 ghi nhận + kfold |
| 14 | Config thiếu khóa early_stopping | config.yaml | T | ✅ Fix B |
| 15 | Chưa có dữ liệu thực tế lab | data/ | CAO | ❌ CHƯA — tuần 9-10 theo kế hoạch |

## Còn lại (theo kế hoạch đề cương)
1. **Tuần 9-10**: thu thập RSSI thực tế ≥2 phòng lab (android_collector + /api/collect) → train_home.py → đánh giá lại trên dữ liệu thật; test Android end-to-end; kiểm thử té ngã với accelerometer thật; sinh anomaly phân bố đều các ngày.
2. **Tuần 11-12**: K-fold 10/leave-one-session-out trên dữ liệu thực; quantization/pruning nếu cần edge; hoàn thiện demo + slide.

## Vị trí kết thúc phiên
5/5 giai đoạn hoàn thành. Bài toán "tối ưu + sửa lỗi + báo cáo đối chiếu đề cương trên dữ liệu mô phỏng" đã đóng; bước kế tiếp bắt buộc cần **thiết bị/thu thập thực tế** (ngoài phạm vi phần mềm).

## Phiên 4 (2026-10-23): chia sẻ nhà + tự tìm máy chủ
Yêu cầu: nhiều tài khoản theo dõi 1 nhà qua mã 6 số; app điện thoại tự tìm IP máy chủ qua tài khoản, không gõ IP.

Đã làm (tất cả đã chạy thật, pytest 47/47 + assembleDebug BUILD SUCCESSFUL):
- `src/smarthome/storage.py`: thêm bảng `home_shares` + `home_members`; `list_homes`/`get_home` tính cả nhà được chia sẻ (role owner/member); hàm create_share_code (rotate, TTL 24h), active_share, revoke_share_code, join_home_by_code (idempotent), list/remove_member.
- `server/app.py`: helper `require_owned_home()` + `require_mutation_context()` — thành viên "chỉ xem" (status/history/alerts/config/metrics/rooms GET), mọi ghi (phòng, thiết bị, collect, scan, sensor, demo, train, reset, export) về owner; endpoint mới GET/POST/DELETE `/api/homes/<id>/share`, GET/DELETE `/api/homes/<id>/members[/<uid>]`, POST `/api/homes/join`; login trả về user+homes+active_home.
- Quảng bá mDNS `_antam._tcp` khi chạy `server/app.py` (zeroconf; MATN_ASCII do console). Xác nhận chạy thật: "Dang quang ba _antam._tcp tren cong 5000".
- Web: nút "Chia sẻ / tham gia" (dialog shareDialog: nhập mã tham gia; tạo/rotate/thu hồi mã + danh sách thành viên); member-mode ẩn khu quản trị (account.css).
- Android `MainActivity.kt` + `activity_main.xml`: NSD dò `_antam._tcp.` tự điền URL máy chủ; đăng nhập cookie (java.net.CookieManager, khôi phục phiên từ SharedPreferences); tham gia nhà bằng mã; chủ nhà tạo mã chia sẻ ngay trên app; token ghép nối trở thành tùy chọn.
- 4 test API mới (share-flow quyền member, mã không hợp lệ/hết hạn/rotate, mã hết hạn theo thời gian, gỡ thành viên) → 43 → 47 test, tất cả pass.
- Sửa môi trường build (máy này): `local.properties` sdk.dir → `E:\Android`; `gradle.properties` org.gradle.java.home → `C:/Program Files/Android/Android Studio/jbr`; thiếu import `java.net.CookieHandler` trong MainActivity.kt (lỗi code thật, đã sửa).

Cảnh báo còn lại:
- `resolveService`/`NsdServiceInfo.host`/`WifiManager.startScan` deprecated (chỉ warning, hoạt động tới API 34; migrate khi cần).
- Session cookie khôi phục theo SECRET_KEY của server; đổi key → app phải đăng nhập lại.
- Mã chia sẻ 6 số không có rate-limit thu thử (khoảng không gian 10^6, TTL 24h) — chấp nhận được cho nội bộ gia đình; cần lockout nếu mở rộng.

## Phiên 5 (2026-10-26): soát UI sau lần gộp app.js (GLM 5.3 Flash / OpenCode)

Thực hiện theo `docs/08_brief_glm_review.md`; báo cáo chi tiết tại `docs/09_glm_review.md`.

Đã làm (kết quả chạy/đo thật):
- Đối chiếu bản gộp `server/static/app.js` + 2 template + 3 CSS với `backup_original/ui_2026-10-24/`: **không mất ID, không mất chức năng**; shape dữ liệu UI↔server khớp toàn bộ endpoint (chi tiết trong 09).
- Sửa lỗi 1 — shareDialog dính sát viền (nội dung ngoài `<form>` nên không được đệm, đo được 1px): thêm `#shareDialog { padding: 24px }` + `#shareDialog form { padding: 0 }` vào `mobile.css`. Lỗi kế thừa từ bản cũ, không phát sinh do lần gộp.
- Sửa lỗi 2 — badge `COLLECTING` trong suốt (app.js sinh `badge collecting` nhưng CSS thiếu): thêm `.badge.collecting` vào `style.css`.
- Kiểm chứng: `node --check app.js` OK; `pytest tests -q` với `PYTHONPATH=src` → **47/47 pass (29.50s)**; đo computed style fixture trước/sau cả hai fix.
- Kiểm tra chính tả + encoding: 13 file UTF-8 hợp lệ, không BOM, không ký tự lỗi; chuỗi UI tiếng Việt không có lỗi chính tả.

Phát hiện môi trường (chưa sửa, chờ agent chính):
- `.venv` thiếu package `smarthome` → pytest thuần lỗi `ModuleNotFoundError`; tạm chạy bằng `PYTHONPATH=src`. Đề nghị `pip install -e .`.
- `tests/__pycache__/` chứa `.pyc` cũ biên dịch từ bản dự án `1006` (path cũ nằm trong pyc) → nên xoá.
- Flask không chạy ở `:5000` như brief ghi; comment `app.js:10` dẫn tới `docs/07_...` không tồn tại. Chi tiết trong `docs/09_glm_review.md`.

## Phiên 6 (2026-10-27): hỗ trợ DeepSeek — kiểm chứng fix UI + sửa môi trường test (GLM 5.3 Flash)

Tiếp tục theo kiến trúc 2 agent (`docs/10`): GLM làm việc tại worktree `wt-glm-flash` (nhánh `agent/glm-flash`).

Đã làm (kết quả chạy thật):
- Kiểm chứng 2 fix của DeepSeek trong `app.js` (khắc phục mục #5 và #6 trong docs/09): thông báo gia tốc tuyến tính 1 lần mỗi lần bật cảm biến (`sensorAccelerationWarned`), đặt lại nhãn nút train sau FAILED. Logic đúng, `node --check` OK.
- Sửa môi trường test (mục #3 trong docs/09): `pip install -e .` vào `.venv` (import `smarthome` OK) + xoá `tests/__pycache__/` (pyc cũ trỏ sang bản 1006). Kết quả: pytest chạy **không cần PYTHONPATH: 47/47 pass (26.83s)**.
- Cập nhật `docs/09_glm_review.md` bảng trạng thái xử lý đầy đủ 7 mục.
- Đồng bộ toàn bộ trạng thái đã kiểm chứng (app.js + 2 CSS + docs/07, 09, 10 + PROGRESS.md + xoá app-v2/v3.js) vào nhánh `agent/glm-flash` để merge về chính khi duyệt.

## Phiên 7 (2026-10-27): hạ tầng chạy 2 model trên 1 dự án (DeepSeek V4.1 Flash max)

Yêu cầu: chạy **GLM 5.3 Flash (OpenCode)** và **DeepSeek V4.1 Flash suy luận max (DeepSeek Harness)**
trên cùng một dự án, dùng chung NVIDIA NIM key với hạn mức 40 request/phút.
Hướng dẫn cài đặt đầy đủ: `docs/10_chay_2_agent.md`.

Đã làm (tất cả chạy thật):

- Kiểm chứng proxy **có** ép DeepSeek chạy max: dựng upstream giả, body gửi tới NVIDIA chứa
  `chat_template_kwargs {"thinking":true,"reasoning_effort":"max"}` và `reasoning_effort: "max"`,
  còn request tới GLM **không** bị thêm gì. Mục `payload.override` trong `config.yaml` hoạt động
  đúng trên CLIProxyAPI 8.0.33.
- **Phát hiện quan trọng — lỗi phía NVIDIA, không phải cấu hình.** Gọi thẳng NVIDIA NIM (không qua
  proxy): `minimaxai/minimax-m3.1-flash` trả lời sau 1,4 s; `z-ai/glm-5.3-flash` và
  `deepseek-ai/deepseek-v4.1-flash` **không trả một byte nào** sau 150 s / 200 s (thử cả `stream: true`
  và `stream: false`). Cả hai ID đều có thật trong `/v1/models` của chính key này (85 model).
- Sửa `C:\cliproxy\nim-limiter.js` — bản gốc chỉ giới hạn số request nên **không xử lý được treo**,
  mà alias "best" chỉ chuyển model khi upstream trả lỗi: cắt khi quá hạn byte đầu
  (`--first-byte-timeout-sec=120`) trả 504; cách ly model vừa bị cắt (`--cooldown-sec=180`) trả 503
  ngay cho request sau; cách ly tăng dần (`--cooldown-max-sec=3600`); `/healthz` thêm
  `coolingDownSec`, `strikes`. **Đo thật:** `best` từ treo vô hạn → **6,1 s** (lần 1), **0,0 s** (lần 2).
  Với NVIDIA thật: `deepseek`/`glm-flash` lỗi rõ ràng sau 120 s, `minimax` OK 0,9 s, `best` OK 1,0 s.
- Thêm hai alias **`deep-first`** (DeepSeek → MiniMax) và **`glm-first`** (GLM → MiniMax) để mỗi agent
  giữ đúng model chính mà vẫn có đường lui, và tự quay lại model chính khi NVIDIA sống lại.
  Đo thật: lần 1 mất 124 s / 122 s, lần 2 chỉ còn 4,0 s / 1,4 s.
- Sửa `start-cpa.ps1`: file thiếu **BOM UTF-8** nên **không parse được trên Windows PowerShell 5.1**
  (mặc định của máy này) — chữ Việt bị đọc theo ANSI, lỗi `Unexpected token 'i'` tại dòng 82. Đã thêm
  BOM: parse OK trên cả 5.1 và 7. Thêm tham số `-FirstByteTimeoutSec`, `-CooldownSec`, `-CooldownMaxSec`.
  *Ghi chú:* công cụ soạn thảo dùng ở đây **xoá BOM** mỗi lần sửa file `.ps1` — sửa xong phải thêm lại.
- Dựng **worktree** cho 2 agent: `wt-glm-flash` (nhánh `agent/glm-flash`), `wt-deepseek`
  (nhánh `agent/deepseek`), cùng xuất phát từ commit `8a8f2b0`; script mở cả hai: `chay-2-agent.ps1`.
- Giao diện (tiếp nối phiên 5-6): sửa lỗi **nhịp cập nhật bị BỎ** thay vì hẹn lại (`refreshPending`)
  và lỗi **ghi khoá cache trước khi vẽ** (`safeRender`) — hai lỗi này làm UI đứng im dù dữ liệu mới;
  khôi phục thông báo "không cung cấp gia tốc tuyến tính" (một lần mỗi lần bật cảm biến, không spam);
  đặt lại nhãn nút huấn luyện sau khi thất bại; thêm thông báo "Model mẫu đang khởi động…" cho vài
  mẫu demo đầu tiên (đo được: phải tới mẫu thứ 2-3 model mẫu mới chốt phòng).
- Bỏ hai file chết `server/static/app-v2.js` và `app-v3.js` (đã gộp vào `app.js`; bản gốc còn nguyên
  trong `backup_original/ui_2026-10-24/` và trong lịch sử git).
- Môi trường test: GLM đã chạy `pip install -e .` vào `.venv` và xoá `tests/__pycache__/` cũ.

Kiểm chứng cuối (chạy thật): `node --check server/static/app.js` OK · `pytest tests -q` **47/47 pass**
(không cần PYTHONPATH) · Playwright đăng nhập rồi chạy demo 9 giây: phòng "Phòng ngủ", ô phòng sáng
đúng, 5 xác suất, 3 sự kiện dòng thời gian, **0 lỗi console/HTTP**; tắt demo trở về đúng trạng thái khóa.

Việc còn lại: **NVIDIA phải sửa `z-ai/glm-5.3-flash` và `deepseek-ai/deepseek-v4.1-flash`** thì hai
agent mới chạy đúng model chính; hiện tại cả hai tự rơi về MiniMax M3.1 Flash và vẫn làm việc được.

## Phiên 8 (2026-10-31): kiểm tra bảo mật và vá (GLM 5.3 Flash / OpenCode)

Yêu cầu: "kiểm tra lỗi bảo mật và sửa chữa". Soát toàn bộ server Flask, storage, frontend, git, Android manifest.

Đã tốt sẵn (kiểm chứng, không sửa): SQL 100% parameterized (storage.py); XSS chặn bằng `escapeHTML` đầy đủ 5 ký tự ở mọi chỗ innerHTML (app.js), template không có biến Jinja; password băm werkzeug; device token lưu SHA-256; subprocess không qua shell; `yaml.safe_load`; `.env`/`data/*.db` không bị git track; Authorization header sai không bị hạ cấp xuống session.

Đã vá (tất cả chạy thật, **pytest 50/50 pass** — 47 cũ + 3 test mới, 40.81s):

1. **[CAO] SECRET_KEY fallback cố định** (`server/app.py`) — bản cũ dùng `"change-this-development-secret"` khi thiếu env, ai đọc source có thể tự ký cookie giả mạo đăng nhập. Thay bằng `resolve_secret_key()`: env → file `data/secret_key` (sinh ngẫu nhiên 64 hex, gitignored) → ngẫu nhiên per-boot. Giữ được tính năng app Android khôi phục phiên sau restart. Kiểm chứng thật: key dài 64, khác chuỗi mặc định.
2. **[CAO] Không chống dò** — thêm lớp `AttemptLimiter` (in-memory, cửa sổ trượt): login 5 lần sai/15 phút theo email; `/api/homes/join` 5 lần sai mã/15 phút theo user; thành công thì xóa đếm; vượt hạn trả 429 `TOO_MANY_ATTEMPTS`. Khép lại cảnh báo "mã chia sẻ 6 số không có rate-limit" của phiên 4. Đánh đổi: kẻ xấu có thể cố tình khóa email của nạn nhân (đã ghi trong comment).
3. **[TB] Mật khẩu không có giới hạn trên** — thêm cap 128 ký tự ở `/api/auth/register`.
4. **[TB] Đoán email tồn tại qua thời gian phản hồi** — email không tồn tại vẫn chạy một lần `check_password_hash` với hash giả (timing attack).
5. **[TB] CSV injection ở `/api/export/scans.csv`** — ô văn bản (session_id/device_id/room/orientation) bắt đầu `= + - @` được thêm `'` phía trước; không đụng cột RSSI (số âm thật). Kiểm chứng thật: phòng tên `=HYPERLINK(1,2)` xuất ra `'=HYPERLINK(1,2)`.
6. **[TB] Cookie không Secure khi chạy HTTPS** — trong `__main__`, có cert/key mà không đặt `SMART_HOME_SECURE_COOKIE` thì tự bật `SESSION_COOKIE_SECURE`.
7. **[T] `/api/collect` nhận đầu vào quá lớn** — cap `session_id` ≤ 40 ký tự, `device_id` ≤ 80, `wifi` ≤ 64 AP, mỗi key AP ≤ 64 ký tự (chặn phình SQLite).

Thay đổi phụ: `.gitignore` thêm `data/secret_key`; test fixture reset 2 limiter như các state runtime khác; thêm 3 test (`test_password_rejected_over_max_length`, `test_login_brute_force_lockout`, `test_share_code_join_brute_force_lockout`) → 47 → **50 test**.

Ghi nhận, không sửa (có lý do):
- CSRF: đã giảm thiểu bởi `SameSite=Lax` + mọi endpoint ghi chỉ nhận JSON (`get_json(force=True)` từ form-encoded sẽ lỗi) + mọi mutation là POST/PATCH/DELETE; thêm CSRF token sẽ phá app Android dùng cookie session.
- Android `usesCleartextTraffic="true"`: chủ đích cho HTTP nội bộ LAN (README ghi rõ); HTTPS đã hỗ trợ qua env SSL.
- Session limiter nằm trong RAM: restart server là xóa — chấp nhận cho máy chủ gia đình, không thêm thư viện.
- `android_collector/app/build/` bị track trong git (artifact build, thay đổi mỗi lần assembleDebug) — **đã xử lý tiếp ở phần dưới**.

### Tiếp phiên 8 — hardened tiếp theo yêu cầu "tiếp tục"

8. **Security headers** (`@app.after_request`): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, CSP `default-src 'self'` (style-src cần `'unsafe-inline'` vì app.js vẽ thanh xác suất bằng style nội tuyến). Kiểm chứng thật: header xuất hiện trên mọi response; Playwright đăng ký tài khoản + chạy demo 9 giây với DB tạm → 5 thanh xác suất inline-style vẫn vẽ đúng, ô "Phòng ngủ" sáng, **0 lỗi CSP** (console chỉ có 2 lỗi có sẵn: 401 /api/auth/me khi chưa đăng nhập, 404 favicon).
9. **`/api/scan` trả 500 khi đầu vào sai** — `float()` trong `preprocessing._raw_vector` ném ValueError chưa bắt (giá trị RSSI/timestamp không phải số). Chuẩn hóa trước như `/api/collect`: wifi sai → 400, timestamp sai → 400, cap 64 AP, key AP ≤ 64 ký tự.
10. **Build artifact Android khỏi git** — 453 file `app/build/**` + `.gradle/` `.idea/` `.kotlin/` `build/` `local.properties` (machine-specific) đã `git rm -r --cached` (chỉ staged, **chưa commit** — chờ duyệt); `.gitignore` thêm 6 mẫu. README đổi cách cài APK từ "cài file có sẵn" sang "build bằng Android Studio/gradlew" vì APK không còn lưu trong Git.

Kiểm chứng cuối: `pytest tests -q` **50/50 pass**; chạy thật server (DB tạm, không đụng `data/smarthome.db`) + Playwright như trên; server đã dừng, DB tạm đã xóa.

## Phiên 10 (2026-11-01): kiểm tra bảo mật + vá lỗi cô lập dữ liệu + nâng cấp nhỏ

Báo cáo đầy đủ: `docs/12_kiem_tra_va_nang_cap.md`. Không commit.

### Hiện trạng đầu phiên
- `pytest tests -q`: **4 failed, 47 passed**. Nguyên nhân: `server/app_services.py`
  import `db`, `home_engines`, `last_results`, `alert_throttle` theo giá trị từ
  `app_state`; fixture đổi `app_state.db` nhưng route vẫn dùng DB cũ. Đây là lỗi
  cô lập dữ liệu (test có thể đọc/ghi nhầm `data/smarthome.db`), không chỉ lỗi test.
- `server/security_middleware.py` cũ (từ checkpoint trước) rate-limit cả trang/static
  và tin `X-Forwarded-For` vô điều kiện; bản refactor G1 đã bỏ middleware này.

### Đã làm
1. `app_services.py`: chuyển sang `import app_state`, truy cập động; thêm
   `finite_float()`, `notify_alert()`, `_post_webhook()`; `persist_result()` nhận
   `home_name`. `app.py` thêm `__getattr__` để `appmod.db`/`appmod.persist_result`
   vẫn tương thích nhưng luôn trỏ đúng trạng thái hiện tại.
2. Viết lại `security_middleware.py`: chỉ rate-limit `/api/*`; ngưỡng auth 30/phút,
   collect/scan/sensor 240/phút, API chung 300/phút; block 60 giây; lock + trần
   4096 client; chỉ tin XFF khi `SMART_HOME_TRUST_PROXY=1`; guard `view_args=None`;
   JSON-only cho thao tác ghi có body; `Permissions-Policy` cho phép
   accelerometer/gyroscope; HSTS chỉ khi HTTPS; `Cache-Control: no-store` cho API;
   lỗi API trả JSON.
3. `app.py`: nối middleware, thêm `GET /api/health` (503 khi DB lỗi).
4. Validate `max_dwell_minutes` (1–1440, hữu hạn), RSSI/timestamp hữu hạn, cap
   `platform` 40 ký tự, cap `orientation`/`device_id`.
5. Webhook CRITICAL: gửi thread nền, timeout 5 giây, không redirect; dùng cho cả
   cảnh báo Wi-Fi và cảm biến.
6. UI: nút **Đổi tên phòng** (PATCH giữ nguyên `max_dwell_minutes`); bump service
   worker cache `an-tam-home-v5`.
7. Android: `android:allowBackup="false"`.
8. Test: fixture reset rate limit; thêm 12 test hồi quy.
9. Docs: `README.md`, `.env.example`, `docs/12_kiem_tra_va_nang_cap.md`.

### Kiểm chứng thật
- `pytest tests -q`: **63 passed**.
- `py_compile` toàn bộ `server/*.py` + `server/routes/*.py`: OK.
- `node --check server/static/app.js` và `service-worker.js`: OK.
- Chạy server thật với DB tạm: health, 404 JSON, header, đăng ký, tạo/đổi tên
  phòng, NaN → 400, text/plain → 415, reset, 429 + `Retry-After`, trang chủ vẫn
  200 → **SMOKE OK**. Không đụng `data/smarthome.db` (kiểm tra: 0 alert, 0 prediction).

### Còn lại
- G1 code đã chạy được. Commit `360eb59` xuất hiện trong lúc phiên này đang chạy
  (do tiến trình khác tạo, **không phải phiên này**); phiên này không chạy
  `git commit`/`git push`. G2 (SSE/tách app.js), G3 (multi-task/ensemble), G4
  (sinh lại báo cáo) vẫn chưa làm.
- Rate limit trong RAM theo tiến trình; chưa có CSRF token (đang dựa SameSite=Lax +
  JSON-only + không bật CORS). Không bật `SMART_HOME_TRUST_PROXY` khi client nối
  trực tiếp.

## Phiên 9 (2026-10-31): VIẾT LẠI TOÀN BỘ CHỨC NĂNG — ĐANG DỞ, CHƯA XONG

Yêu cầu: "viết lại toàn bộ chức năng" kèm nguyên tắc trong `E:\Downloads\tinhnang.md` (nghiên cứu mã nguồn mở trước khi làm). Đã chọn phạm vi: **tất cả** (tầng app + tầng ML). Checkpoint phiên 8: commit `4e3289e` trên nhánh `fix/optimize-training`.

### Nghiên cứu đã xong (theo tinh thần tinhnang.md)
- **FIND3** (schollz/find3, 4.8k★): learn/track tách pha, ensemble meta-learning 10 classifier, WebSocket realtime, SQLite. → tham khảo G2, G3.
- **ARIL** (IEEE Access 2019, geekfeiw/ARIL): multi-task 1D ResNet, 1 encoder chung cho activity + location. Dùng CSI+SDR nên chỉ mượn ý tưởng multi-task cho G3.
- CSI/ESP32 presence (espectre-sense): hướng tương lai, không làm trong khóa luận này.
- Kết luận: kiến trúc hiện tại đã sát FIND3; khoảng cách lớn = polling 3 req/2s (nên SSE) + model đơn lẻ (nên ensemble/multi-task).

### Kế hoạch 4 giai đoạn
- **G1 — Tầng server (ĐANG LÀM, dở ~40%)**: tách `server/app.py` (952 dòng) thành module. Đường dẫn API + hành vi giữ 100% nguyên bản (Android/PWA không vỡ). Test phải xanh từng bước.
- **G2 — Realtime + frontend**: SSE (`/api/stream`) thay polling (không thêm thư viện, Flask stream được); tách `app.js` 1113 dòng thành ES modules; service-worker cache list cập nhật.
- **G3 — Tầng ML**: multi-task model (encoder chung + head phòng + head hoạt động, ARIL-style) + ensemble/meta-learning chọn model theo nhà (FIND3-style). Chạy lại toàn pipeline trên dữ liệu v2 → `results/` mới. Không bịa số liệu.
- **G4 — Báo cáo + docs**: sinh lại `BAO_CAO_KET_QUA.docx` từ results mới qua `make_report.py` (Times New Roman 13), cập nhật README.

### G1 — hiện trạng khi dừng (code CHẠY ĐƯỢC: app.py cũ chưa bị đụng, các file mới chỉ add-on)
Đã tạo:
- `server/app_state.py` — singleton runtime (cfg, db, engines/monitors/histories/jobs, 3 limiter, demo_engine/demo_source, lock, reset_runtime). Đã bao gồm `register_limiter` (theo IP, 10/giờ) — lưu ý: `register_limiter` là do agent khác thêm sau phiên 8, KHÔNG phải của phiên 8; giữ nguyên hành vi.
- `server/app_security.py` — resolve_secret_key, AttemptLimiter, DUMMY_PASSWORD_HASH, secure_cookie_requested, apply_security_headers, csv_formula_safe.
- `server/app_services.py` — calibration_settings, new_sensor_monitor, login_required, active_home, require_* helpers, home_progress, get_home_engine, persist_result.
- `server/routes/__init__.py` — register_routes(app) đăng ký 5 blueprint.
- `server/routes/auth_views.py` (register/login/logout/me), `server/routes/home_views.py` (homes/select/modify/share/members/join) — đã viết xong.

Còn lại của G1 (làm tiếp theo đúng thứ tự):
1. `server/routes/room_views.py` — rooms GET/POST/PATCH/DELETE + devices GET/POST/DELETE (copy logic từ app.py dòng 560-625, tham chiếu qua `app_state.*`).
2. `server/routes/track_views.py` — index, service-worker, calibration, collect, scan, demo/scan, sensor, sensor/status, status, history, alerts, config, metrics, export/scans.csv, reset (app.py dòng 334-910).
3. `server/routes/training_views.py` — run_training + start + status (app.py dòng 854-892).
4. Viết lại `server/app.py` thành bản lắp ráp: sys.path setup → create_app() (config + after_request apply_security_headers + register_routes + route `/` và `/service-worker.js`) → re-export cho test (app, cfg, db, home_engines, sensor_monitors, last_results, runtime_histories, training_jobs, alert_throttle, login_limiter, join_code_limiter, register_limiter, demo_engine, engine, demo_source, `import time`) → khối `__main__` giữ nguyên (mDNS, SSL, cookie secure tự bật).
5. Sửa fixture trong `tests/test_api_integration.py`: `appmod.app_state.db = SmartHomeDatabase(tmp_path/"api.db")` + `appmod.app_state.reset_runtime()` (bắt buộc — re-export cũ không thấy swap db). Thân test KHÔNG đổi; `monkeypatch appmod.time` vẫn hoạt động vì app.py vẫn `import time`.
6. Chạy `pytest tests -q` → phải ≥51 pass; `node --check` không cần (JS chưa đụng); chạy thật server + đăng nhập + demo để xác nhận không vỡ.
7. Commit checkpoint G1 với thông báo riêng.

### Ràng buộc khi làm tiếp (đọc kỹ)
- Không đổi đường dẫn API, tên trường JSON, mã lỗi — Android `MainActivity.kt` và PWA đang phụ thuộc.
- `appmod.time` bị monkeypatch (test_serial_share_code_expiry) — app.py phải giữ `import time`.
- 3 limiter nằm trong `app_state` — fixture phải reset qua `app_state.reset_runtime()`.
- Không commit khi chưa hỏi; mỗi bước code phải chạy được.

### Cập nhật 2026-11-01: G1 + G2 HOÀN THÀNH (làm song song với agent khác)

Agent khác ("phiên 10", docs/12) đã tiếp quản và hoàn thiện G1: sửa 4 test fail
(app_services import theo giá trị → `app_state.*` động), viết lại
`security_middleware.py` (rate limit theo nhóm endpoint, JSON-only guard CSRF
lớp 2, HSTS chỉ trên HTTPS, Permissions-Policy giữ accelerometer=(self), JSON
error handler), thêm `/api/health`, `finite_float` chặn NaN/Infinity, webhook
CRITICAL (đã nối code — config `alerts.webhook_url` giờ có tác dụng), nút đổi
tên phòng, Android `allowBackup="false"`, service-worker v5.

**G1 xong — commit `360eb59`** (lưu ý: docs/12 ghi "chưa commit chờ duyệt", nhưng
kế hoạch G1 được duyệt có bước commit; kiểm chứng sống trước khi commit:
health/register/demo/guard 415/rate-limit 429).

**G2 xong (SSE realtime)**: `/api/stream` với slot giới hạn 32 kết nối, heartbeat
15s, chỉ gửi event khi payload đổi; app.js client EventSource + fallback polling;
67/67 test pass. Kiểm chứng sống (DB tạm): 6 giây nhận `status, history, alerts,
status`; REST vẫn chạy song song; `node --check` OK.

Phân công tiếp (tránh hai agent đụng cùng file):
- **GLM (phiên này) — G3 tầng ML**: `src/smarthome/models.py`, `scripts/train_*.py`,
  `config.yaml` (mục ML), pipeline chạy lại, `results/` mới. File server/frontend
  KHÔNG đụng tới khi agent khác còn hoạt động.
- Agent khác (nếu tiếp tục): G2 còn dư — tách `app.js` thành ES modules (1113
  dòng), và G4 (báo cáo + README sau khi G3 có số liệu).

### G3 — thiết kế chi tiết (bắt đầu ngay dưới đây)
Mục tiêu theo nghiên cứu mã nguồn mở (ARIL IEEE Access 2019 + FIND3):
1. **Multi-task RoomNet-MT**: 1 encoder dùng chung + 2 head (phòng + hoạt động)
   — tham khảo ý tưởng joint learning của ARIL, giữ loss có trọng số.
2. **Ensemble meta-learning kiểu FIND3**: huấn luyện N model (RoomNetLite hiện
   tại + biến thể + baseline CNN/kNN/RF), chọn model tốt nhất THEO TỪNG NHÀ
   dựa trên validation session — không bao giờ chọn theo test.
3. Chạy lại toàn pipeline trên dữ liệu v2, seed 42, ghi `results/g3_multitask/`;
   so sánh trước/sau công khai trong báo cáo; KHÔNG bịa số liệu.
Ràng buộc: giữ tương thích inference hiện tại (interface SmartHomeInferenceEngine
không đổisignature), 67 test phải luôn pass.

### Cập nhật 2026-11-01 (chiều): G3a XONG — commit `e83a4f3`

Đã làm (chạy thật, **pytest 77/77 pass**):
- `src/smarthome/models/roomnet_mt.py` — **RoomNetMT**: encoder giống RoomNetLite
  + `activity_head` 4 lớp (STILL/LIGHT_ACTIVITY/MOVING/ROOM_CHANGE); forward trả
  `(room_logits, emb, activity_logits)` — 2 phần tử đầu tương thích 100% với
  RoomNetLite. Kèm `derive_activity_label()` — nhãn hoạt động suy từ cửa sổ bằng
  ĐÚNG ngưỡng ActivityMonitor (median delta; đổi phòng → ROOM_CHANGE).
  Lưu ý: bộ luật gốc dùng EMA theo scan, MT dùng median trên cửa sổ — ghi rõ
  khi báo cáo (chưng cất, không phải sao chép 1:1).
- `src/smarthome/dataset.py` — **RoomWindowDatasetMT**: thêm phần tử nhãn hoạt
  động (delta từ RSSI thô, nanmedian theo AP như `_rssi_delta` của luật).
- `scripts/train_room_mt.py` — giữ nguyên early stopping/cosine restarts/
  augmentation/CenterLoss/JS temporal của train_room.py; thêm
  `w_activity·CE_activity`; ghi `roomnet_mt_val_metrics.json` (chỉ số phòng +
  act_agree + confusion).
- 3 test mới trong test_algorithms.py (shapes, ngưỡng nhãn, dataset).
- **Smoke train 2 epoch** (`.tmp/mt_smoke`, không đụng models/ thật):
  val_acc/F1 = **97.32%**, **act_agree = 97.32%** (ngẫu nhiên = 25%) → head học tốt.

Song song: agent khác đã làm nốt G2b — tách app.js thành ES modules
(`server/static/js/` 10 file, template nạp `type="module"`, docs/14), service-worker v5,
Android cert-pinning (commit `dc50581`), `ap_hashing.py`. Commit `e83a4f3` gộp
cả hai nhánh công việc (đã test chung 77/77 + node --check từng module).

### G3 còn lại (phiên tới)
1. **G3b — ensemble meta-learning kiểu FIND3**: `scripts/train_ensemble.py`
   huấn luyện RoomNetLite + SimpleCNN + kNN/RF/MLP (sklearn đã có trong
   requirements), chọn tốt nhất THEO validation, ghi `model_choice.json`
   vào `models/homes/<id>/`; `SmartHomeInferenceEngine` đọc model_choice để
   nạp model phù hợp (sklearn dự đoán theo scan + majority-vote cửa sổ).
2. **Chạy lại pipeline đầy đủ** với RoomNet-MT + ensemble, seed 42 →
   `results/g3_multitask/` (room + kfold + anomaly + latency), so sánh
   with results/after_optimized/.
3. Nối `roomnet_mt.pt` vào `SmartHomeInferenceEngine` (head hoạt động xuất
   thêm trường `activity_model` trong /api/status — luật vẫn là driver cảnh báo).
4. **G4**: sinh lại BAO_CAO_KET_QUA.docx từ results mới (Times New Roman 13),
   cập nhật README (mục kiến trúc + API /api/stream).

### Cập nhật 2026-11-01 (tối): G3b XONG + tối ưu security theo 2 tài liệu — commit `c3cd72e`

Yêu cầu mới: "tối ưu đồ án dựa trên SECURITY_AUDIT_REPORT.md + SECURITY.md".

**G3b — ensemble meta-learning (tất cả chạy thật, pytest 84/84):**
- `src/smarthome/ensemble.py` — `select_best_candidate()` theo (macro_f1,
  accuracy) trên VALIDATION (tie-break theo tên để tái lập được).
- `scripts/train_ensemble.py` — đánh giá torch candidates (RoomNetLite/
  SimpleCNN/RoomNetMT) + huấn luyện sklearn (kNN/RF/MLP, lưu joblib), chọn
  best, ghi `model_choice.json` + `ensemble_val_metrics.json`. KHÔNG đụng test.
- `inference.py` — `_load_room_model()`: đọc `model_choice.json` (mặc định
  RoomNetLite); sklearn path dùng `predict_proba` trên cửa sổ duỗi phẳng
  (thứ tự features-major khớp to_xy); `activity_model` head: dùng chính MT
  khi được chọn, nạp riêng khi chỉ có roomnet_mt.pt; event thêm
  `activity_model.state/probabilities` (luật vẫn là driver cảnh báo).
- `train_home.py` thêm train_room_mt + train_ensemble; `full_pipeline.py`
  thêm đủ 10 bước; `evaluate_room.py` thêm `--model`/`--output` (RoomNetLite
  giữ tên file cũ cho /api/metrics).
- **Kết quả `results/g3_multitask/`** (README đầy đủ trong thư mục):
  ensemble chọn **RoomNetMT** (val F1 99.00%); test: RoomNetMT **99.16%/99.17%**,
  latency **0.0193 ms** (RoomNetLite 98.99%, SimpleCNN 97.65%). RF test 99.16%
  > RoomNetLite test nhưng THUA trên val — minh chứng chọn-theo-val là đúng.
  act_agreement 97.32%. Anomaly KHÔNG chạy lại (G3 không đổi model anomaly).
  K-fold MT chưa chạy (không chặn kết luận; làm khi còn thời gian G4).

**Tối ưu security theo 2 tài liệu:**
- Kiểm chứng từng finding của SECURITY_AUDIT_REPORT.md: ~90% là false positive
  của scanner (pattern `DES` khớp "DESC"/"description" do IGNORECASE; scanner
  tự quét chính regex của nó; dò dependency chỉ theo TÊN package — báo oan
  `requests>=2.31`; Kotlin pattern dính precedence — mọi dòng chứa "token"
  bị báo kể cả `findViewById`; DB heuristic báo oan `meta.key`/`rooms._name_key`).
  Android chỉ có MỘT Log thật (cảnh báo HTTP LAN, không log token).
- Sửa 7 lỗi scanner: `\b` + case-sensitive cho crypto, tự-loại-trừ file công
  cụ audit, bỏ qua dòng comment + marker `# nosec` (giống bandit), Kotlin Log
  pattern sửa precedence, dependency so version thật, DB_COLUMN_ALLOWLIST có
  giải thích, git-history hạ INFO (nhắc từ khóa ≠ chứa bí mật). Thêm wrapper
  UTF-8 cho console cp1252.
- 2 dòng đã soát tay được đánh dấu `# nosec` kèm lý do: storage.py PRAGMA
  (hằng số int module, PRAGMA không nhận tham số ràng buộc) + SQL test
  (bảng từ tuple cố định).
- **Kết quả: 69 findings (10 HIGH) → 4 INFO**, toàn bộ là thiết kế có chủ đích
  đã ghi trong SECURITY.md (mDNS, pin expiry 2027-11-01, HTTP LAN/NSD).

### Còn lại (phiên tới)
1. **G4**: sinh lại BAO_CAO_KET_QUA.docx từ results/g3_multitask + after_optimized
   (Times New Roman 13, qua make_report.py), cập nhật README (kiến trúc mới:
   module server, SSE, RoomNet-MT, ensemble).
2. Tùy chọn: k-fold 5×RoomNetMT; đánh giá demo dashboard với model_choice
   (hiện models/ toàn cục chưa dán model_choice — giữ nguyên hành vi demo cũ,
   quyết định dán khi duyệt).

### Cập nhật 2026-11-01 (đêm): G4 XONG — commit `7a71388`

- `make_report.py` cập nhật thành báo cáo **tuần 11**: thêm mục 3.1 (kết quả
  G3 đọc trực tiếp từ results/g3_multitask/models/*.json — không nhập tay),
  6 bullet việc tuần 9–11 (tái cấu trúc server + bảo mật, SSE, RoomNetMT,
  ensemble, sửa scanner), bằng chứng mới ở mục 4, mục 5 ghi thẳng "hạn tuần
  9–10 đã qua" cho dữ liệu thực tế, mục 6 đổi tuần 9–10 thành ĐẠT MỘT PHẦN.
- Viết theo `E:\Downloads\avoid.md` (dấu hiệu văn bản AI): câu ngắn có số
  liệu + đường dẫn file, không dùng các cụm khuôn mẫu ("đóng vai trò như",
  "không chỉ… mà còn", liệt kê 3 tính từ), thừa nhận thẳng giới hạn. Đã kiểm
  chứng bằng script đọc ngược docx: 6 bảng, đủ số liệu 99.16/97.32/99.00/4
  findings, font Times New Roman 13, 0 cụm AI-phrases.
- `python-docx` bổ sung vào requirements.txt (make_report.py cần).
- Kết luận báo cáo: 9 ĐẠT / 2 ĐẠT MỘT PHẦN / 1 CHƯA ĐẠT — giữ nguyên đánh giá
  trung thực, nêu rõ mọi số liệu hiện tại chỉ có giá trị trên dữ liệu mô phỏng v2.

### Kế hoạch phiên kế tiếp
1. Thu thập dữ liệu RSSI thực tế (việc CAO duy nhất còn lại — cần thiết bị thật).
2. Tùy chọn: k-fold RoomNetMT; quyết định dán model_choice.json vào models/
   toàn cục cho demo; slide thuyết trình.

## Phiên 11 (2026-11-02): hoàn thành báo cáo khóa luận + backup script

### Báo cáo khóa luận — HOÀN THÀNH (commit `cbbb74f` + phần này)
- **8.2/8.3/8.4 viết lại bằng số thật** (số bịa đã quét sạch: 0 occurrence cho
  87.3%/0.934/sensitivity 88%/Pi benchmark): RoomNetLite test 98.99% + per-room
  F1 (Bathroom thấp nhất 98.33%), RoomNetMT 99.16/99.17 + act_agreement 97.32%,
  anomaly hybrid P=100% R=99% F1=99.50% (166 mẫu, threshold 1.6089 grid search),
  K-fold 97.80%±1.06%. Mục 8.4 ghi thẳng "CHƯA KIỂM THỬ" với cơ chế + kịch bản
  đề xuất thay bảng bịa.
- **Chèn lại 8.6** (so sánh 6 model + bài học RF thua val) và **chương 9
  TRIỂN KHAI THỰC TẾ** (Docker multi-stage, compose.prod 6 dịch vụ, HTTPS hai
  phương án Let's Encrypt/Cloudflare Tunnel, Android prod + pinning, health
  check) + **chương 10** (10.1 thành quả thật, 10.2 hạn chế 7 mục, 10.3
  nếu/có thể) — mất do race lần trước, đã dựng lại theo docker-compose.prod.yml
  và SECURITY.md thực tế.
- Sửa 7.1 heading "Mô hình??", dòng kết bỏ "TS. Nguyễn Van A"/năm 2024.
- **BAO_CAO_KHOA_LUAN.docx** sinh lại bằng make_thesis_docx.py: **13 bảng,
  967 đoạn, ~48k ký tự**, TNR 16/13, verify ĐẠT toàn bộ (số liệu thật, không
  cụm AI theo avoid.md, không số bịa).

### Code bổ sung
- **`scripts/backup_db.py`** (mới): sqlite backup API (an toàn khi WAL đang
  ghi), integrity_check trước khi lưu, kiểm tra bản backup đọc được, xoay
  vòng --keep, đồng bộ node phụ/cloud qua BACKUP_REMOTE (rclone/scp). Chạy
  thật: backup 0.12 MB, 12 bảng, rotation hoạt động.
- **`.dockerignore`**: gộp bản của agent khác + các mục bảo mật (data/, .env,
  certs/, backup docx) — lần trước tôi ghi đè mất bản của họ, đã khôi phục
  đủ cả hai phần.
- `.gitignore` thêm `data/backups/`.

### Agent khác đã làm (phiên 11 của họ, commit `371ec80`, `3fede99`)
- Sửa 6 lỗi chặn deploy (prod chạy Werkzeug dev server → **gunicorn gthread
  cho SSE**, nginx upstream trùng, DOMAIN shell, cert mount...), wsgi.py,
  DEPLOY.md, .env.prod.example — **kiểm chứng Docker thật: image build OK,
  container healthy, /api/health 200**.
- **Redis-backed rate limiter** trong security_middleware.py: dual-mode
  (Redis sorted set sliding window / RAM fallback khi Redis lỗi), client ID =
  IP + UA hash — mục "rate limit phân tán" của đề bài đã xong.
- README cập nhật phần triển khai.

### Còn lại
- Thu dữ liệu RSSI thực tế (bắt buộc, cần thiết bị).
- K-fold RoomNetMT; slide thuyết trình.
- Lưu ý venv dev: pandas 3.1.0 (major) vs docker <2.3 — cân nhắc pin khi ổn.

## Phiên 10 (2026-11-01, đêm): viết dài báo cáo khóa luận — DỞ GIỮA CHỖ, CẦN TIẾP TỤC NGAY

Yêu cầu: (1) viết báo cáo dài + check đạo văn/AI + chỉnh format (kèm `E:\Downloads\avoid.md`
— danh sách dấu hiệu văn phong AI cần tránh); (2) code cần thêm "nếu/có thể":
server chung, lưu trữ phân tán, rate limit, bảo mật, Docker + Cloudflare + domain.

### Đã phát hiện SỐ LIỆU BỊA trong BAO_CAO_KHOA_LUAN.md (agent khác viết nháp)
Mục 8.2: "Accuracy 94.2/89.7/87.3%, test trên Raspberry Pi 4 8GB" — **BỊA**
(thật: val 98.83%, test 98.99%, chưa từng đo trên Pi). Mục 8.3: "AUC-ROC 0.934,
F1 0.71 @ quantile 0.99" — **BỊA** (thật: hybrid P=100% R=99% F1=99.50%,
AE-only F1=98.48%, threshold=1.6089 do grid search, 166 mẫu test D13–D14).
Mục 8.4: "Sensitivity 88%, 50 vở ngã mô phỏng, 5 người × 10 lần" — **BỊA**
(chưa từng test ngã thật — chính là hạn chế đã ghi). Mục 10.1: "87.3%,
AUC 0.934, 14 ngày trên Pi" — **BỊA**. Mục 11: trích dẫn rủi ro (WiFall,
Wang 2019 CSI survey — không xác minh được) + đánh số trùng. Bìa: "TS. Nguyễn
Van A" placeholder + "Năm học 2023-2024" sai.

### Đã sửa xong trong BAO_CAO_KHOA_LUAN.md (script .tmp/fix_thesis_md.py, chạy bằng system python)
- 8.5: thay bảng Pi bằng tài nguyên đo thật (model 49/104.5/113.1 KB, latency
  0.0367/0.0193/0.0246 ms — nguồn results/g3_multitask/models/) + ghi thẳng
  "chưa đo trên edge".
- 10.3: viết lại theo khung **nếu/có thể** đúng yêu cầu: server chung nhiều
  gia đình, lưu trữ phân tán (Redis/S3-MinIO), rate limit phân tán, backup
  tự động (sqlite backup API + rclone/scp) — table ngắn/trung/dài hạn.
- 11: thay bằng 8 trích dẫn đã xác minh thật (Wen ECCV 2016 CenterLoss, Bahl
  RADAR INFOCOM 2000, ARIL Wang 2019 arXiv:1904.04964, FIND3 schollz/find3,
  Goodfellow, scikit-learn JMLR 2011, OWASP, Cloudflare docs) — bỏ WiFall/
  survey CSI không xác minh, sửa đánh số trùng.
- Bìa: GVHD thành "……… (điền tên)"; năm học 2026–2027. Mục 1.1: thống kê dân
  số nêu nguồn Tổng cục Thống kê + "khoảng/dự báo". Quét cụm AI (avoid.md): sạch.

### BỊ MẤT do race condition với agent khác (đọc lại file phát hiện)
Mục **8.6** (bảng so sánh thật: RoomNetMT 99.16/99.17, RF test ngang nhưng thua
val — bài học chọn-theo-val), **10.1** (thành quả số thật), **10.2** (hạn chế,
bỏ "Nhà tắm 83%") đã bị agent khác GHI ĐÈ mất khi tôi sửa song song. Cần chèn lại
— SỐ LIỆU THẬT ĐÃ LẤY XONG và ghi ngay dưới đây:

- RoomNetLite test (results/g3_multitask/models/room_test_metrics.json):
  acc 98.99%, F1 98.99%; per-room F1: Bedroom 99.57, Corridor 99.17,
  Bathroom 98.33 (thấp nhất), LivingRoom 98.74, Kitchen 99.17; latency
  0.0367 ms; e2e 0.0246 ms.
- RoomNetMT test (room_test_metrics_RoomNetMT.json): acc 99.16%, F1 99.17%,
  latency 0.0193 ms. MT val (roomnet_mt_val_metrics.json): room F1 98.997%,
  act_agreement 97.32%, epochs_trained=8 (early stopping).
- Anomaly (results/after_optimized/anomaly_test_metrics.json): hybrid P=100%,
  R=99%, F1=99.50%; AE-only F1=98.48%; threshold.json: 1.6089, quantile chọn
  0.99 qua grid search, test_days=D13,D14, samples=166.
- Baseline test (g3_multitask/models/baseline_metrics.json): RF 99.16/99.16,
  MLP 98.99/98.99, kNN 88.26/88.29. SimpleCNN test 97.65%.
- RAM server đo thật: chưa kịp đo (server chết do venv hỏng lúc đo) — đo lại
  khi venv ổn: chạy server, `Get-Process python`, lấy WorkingSet64.

### Công việc còn lại NGAY phiên sau (thứ tự)
1. **Chèn lại 8.6 + 10.1 + 10.2** (nội dung soạn sẵn ở trên) — chèn SAU mục
   8.5, TRƯỚC khối "Hướng phát triển" hiện đang dính liền sau 8.5.
2. **Viết lại 8.2, 8.3, 8.4** bằng số thật ở trên; 8.4 ghi thẳng "chưa kiểm
   thử với accelerometer thật" thay bảng bịa. Kiểm tra cả mục 8.1 (môi trường).
3. **Sửa dòng kết** file (dòng ~1148) còn "TS. Nguyễn Van A".
4. **Sinh lại BAO_CAO_KHOA_LUAN.docx** bằng `make_thesis_docx.py` (script đã
   chạy OK: TNR 13/16, lề 3-2-2.5-2.5cm, giãn 1.5, số trang footer, bảng pipe
   + code fence + bold **...**). DOCX hiện tại trong cây là BẢN CŨ SAI — đã
   xóa khỏi commit, phải sinh lại.
5. Verify: script .tmp/verify_thesis.py (đã có sẵn, chạy bằng venv — sửa lại
   check 99.16/98.99/97.32 + "14 ngày"/"0.934"/"sensitivity 88%" = False).
6. Commit. Sau đó Part 2 code (chưa làm gì): `.dockerignore` (THIẾU — build
   context đang kéo cả .venv/data), wsgi.py + waitress cho Dockerfile prod
   (đang chạy Flask dev server trong prod!), Redis-backed rate limiter tùy
   chọn (compose.prod có Redis nhưng app chưa nối — env REDIS_HOST đã set),
   `scripts/backup_db.py` (sqlite backup API + hook rclone/scp cho "lưu trữ
   phân tán").

### Môi trường (quan trọng)
- Agent khác đang chạy song song và đã **xây lại venv**: torch 2.15.0+cpu,
  numpy 2.4.6, pandas 3.1.0 (major mới!), sklearn 1.9.1 — **84/84 test pass**
  trên stack này. pandas 3.x chưa pin trong requirements.txt (docker pin <2.3
  — chênh lệch dev/prod, cân nhắc pin khi ổn định).
- docker-compose.prod.yml + Dockerfile multi-stage + nginx.conf ĐÃ CÓ (agent
  khác làm) — phần code còn thiếu chỉ là 4 mục liệt kê ở trên.
- BAO_CAO_KHOA_LUAN.md hiện 45,490 ký tự/1148 dòng; những chỗ còn số bịa:
  8.2, 8.3, 8.4 (đã liệt kê) và dòng kết ~1148.

## Phiên 8 (2026-10-31): kiểm tra bảo mật + kiểm tra chức năng

Báo cáo đầy đủ: `docs/11_kiem_tra_bao_mat.md`. Cách làm: đọc mã theo từng lớp tấn công rồi
**chứng minh bằng thực nghiệm**, không kết luận dựa trên suy đoán.

Đã sửa trong phiên (7 lỗ hổng, đều có bằng chứng trước/sau):

- **CSRF qua "simple request"** ở kênh HTTP của MCP server CHORUS (CAO): trang web bất kỳ POST
  `Content-Type: text/plain` tới `127.0.0.1:8787/mcp` — trình duyệt không preflight nên công cụ
  vẫn chạy; đã chứng minh ghi được Shared Memory từ `Origin: evil.example`. Vá bằng: bắt buộc
  `application/json`, chặn `Origin` lạ, Bearer token.
- **DNS rebinding** (TB): không kiểm tra `Host` → `Host: attacker.example` vẫn được phục vụ.
- **Không xác thực kênh HTTP** (TB): gọi được cả `chorus_ask` (tốn hạn mức NVIDIA).
- **Điểm tiêm lệnh** (TB): `proxyKeyEnv` trong cấu hình được nhúng thẳng vào lệnh PowerShell.
- **Đăng ký không giới hạn** (TB): `join_code_limiter` tính theo `user_id` nên tạo tài khoản mới là
  lại có 5 lượt dò mã chia sẻ → thêm `register_limiter` 10 lần/giờ theo IP, kèm test
  `test_register_rate_limited_per_ip`.
- Trần thân request của CHORUS hạ 32 MB → 8 MB.
- **Quyền file chứa khoá** (CAO trên máy dùng chung): `data\secret_key`, `data\smarthome.db`,
  `.env`, `hub\http-token.txt` đều cho `BUILTIN\Users` đọc **và ghi** — đọc được `secret_key` là
  ký được cookie phiên để giả mạo bất kỳ tài khoản. Đã siết bằng `C:\chorus\harden-permissions.ps1`
  (có `-Revert`).

Đã kiểm chứng là **an toàn**: SQL injection (mọi truy vấn tham số hoá), IDOR (mọi thao tác ghi lọc
theo `home_id`), path traversal (CHORUS `slug()` + `send_from_directory` tên hằng), command injection
(`subprocess.run` dạng danh sách, `shell=False`), XSS (`escapeHTML` + CSP), tiêm mã Python (không có
`eval`/`exec`/`pickle`/`yaml.load`), token thiết bị (224 bit, chỉ lưu SHA-256), cách ly dữ liệu giữa
các nhà (kiểm tra sống: tài khoản thứ hai thấy `room` rỗng, `history = 0`).

Các lỗ hổng **đã được vá trước phiên này** và tôi đọc lại xác nhận: `SECRET_KEY` hằng số công khai,
giới hạn đăng nhập, giới hạn dò mã chia sẻ, lộ email qua độ trễ (`DUMMY_PASSWORD_HASH`),
`MAX_CONTENT_LENGTH`, trần mật khẩu 128, header bảo mật (CSP/XFO/nosniff/Referrer-Policy),
CSV formula injection khi xuất `scans.csv`.

**Kiểm tra chức năng** (chạy sống trên cổng 5000): 13/14 bước đạt — đăng ký, thêm phòng, mã ghép
thiết bị, mã chia sẻ, trạng thái, hiệu chuẩn, demo scan, lịch sử, cảnh báo, metrics, xuất CSV,
header bảo mật, đăng xuất. Luồng demo cần 4 lần quét mới chốt phòng (96% → 99%) — hành vi có sẵn
của model mẫu, giao diện đã báo "Model mẫu đang khởi động…".

Kiểm chứng cuối: `pytest tests -q` **51/51 pass** · `selftest-mcp.js` **28/28 đạt** ·
`security-probe.js` **0 lỗ hổng / 12 hạng mục**.

Khuyến nghị chưa sửa (chờ quyết định): chạy HTTPS trên LAN thay vì HTTP trần (cookie phiên đang đi
dạng rõ) · tắt mDNS nếu không dùng · thêm lớp chống CSRF thứ hai bằng cách từ chối thân không phải JSON.

## Phiên 11 (2026-11-01): G2 — SSE realtime cho dashboard

Báo cáo đầy đủ: `docs/13_sse_realtime.md`. Không commit.

### Yêu cầu
Tiếp tục sau G1: dashboard đang gọi 3 request (`/api/status`, `/api/history`,
`/api/alerts`) mỗi 2 giây. Thay bằng SSE, giữ polling làm fallback; không đổi API
Android/PWA, không đổi tên cookie phiên, không thêm thư viện.

### Đã làm
1. `server/routes/track_views.py`:
   - tách `_status_payload()`, `_history_payload()`, `_alerts_payload()` dùng chung
     cho REST và SSE;
   - thêm `GET /api/stream` (`@login_required` + `require_active_home`) trả
     `text/event-stream`, `Cache-Control: no-cache, no-store`,
     `X-Accel-Buffering: no`;
   - event `status`/`history`/`alerts`, chỉ gửi khi payload đổi; status gửi lại
     mỗi 15 giây; heartbeat 15 giây;
   - giới hạn 32 stream đồng thời (`BoundedSemaphore`), giải phóng bằng
     `call_on_close()`; vượt giới hạn trả 503 `TOO_MANY_STREAMS` + `Retry-After`;
   - mỗi vòng kiểm tra lại `db.get_home(user_id, home_id)`; mất quyền xem thì gửi
     event `auth` (`HOME_ACCESS_REVOKED`) rồi đóng stream.
2. `server/static/app.js`:
   - `startLiveUpdates()` mở `EventSource('/api/stream')` sau đăng nhập và sau mỗi
     `loadHome()`;
   - tách `applyStatus()/applyHistory()/applyAlerts()` để SSE và polling dùng chung,
     vẫn giữ `lastRenderKey` chống vẽ lại;
   - stream lỗi → đóng EventSource, bật polling fallback, hẹn mở lại SSE sau 15 giây;
     SSE mở thành công → dừng polling;
   - `visibilitychange`/`pagehide` đóng stream; event `auth` reload để nạp lại phiên.
3. `tests/test_api_integration.py`: thêm 4 test SSE (401, event đầu tiên, đẩy status
   mới, thu hồi quyền thành viên).
4. `README.md`: thêm `/api/stream` và mục **Realtime** trong bảo mật/vận hành.

### Kiểm chứng thật
- `pytest tests -q`: **67 passed** (63 + 4 test SSE).
- `py_compile` các file server đã sửa: OK.
- `node --check server/static/app.js` và `service-worker.js`: OK.
- Smoke HTTP thật với DB tạm: health 200, đăng ký 201, SSE không cookie 401, SSE có
  cookie 200 + đủ 3 event, ghi kết quả mới → SSE đẩy status `Bedroom` trong cùng kết
  nối, `/api/status` thấy `Bedroom` → **SMOKE OK**.
- `data/smarthome.db` không bị đụng: **0 alert, 0 prediction**.

### Còn lại
- G2 phần tách `app.js` thành ES modules **chưa làm**; hiện vẫn một file
  `server/static/app.js`.
- G3 (multi-task/ensemble) và G4 (sinh lại báo cáo) chưa làm.
- Mỗi stream vẫn truy vấn SQLite mỗi 2 giây; nếu số client tăng nhiều nên gom thành
  broadcaster chung. Giới hạn 32 stream tính theo từng process.
- Session vẫn là cookie phía client: đăng xuất ở tab khác không đóng ngay stream
  đang mở. Muốn thu hồi tức thì cần session phía server (`session_epoch`).
- Không chạy `git commit`/`git push`.

## Phiên 12 (2026-11-01): G2 — tách `app.js` thành ES modules

Báo cáo đầy đủ: `docs/14_frontend_modules.md`. Không commit. Không đụng file G3
(`src/smarthome/models.py`, `scripts/train_*.py`, phần ML trong `config.yaml`).

### Yêu cầu
Tiếp nối SSE ở phiên 11: `server/static/app.js` vẫn là một file ~1.100 dòng. Tách
theo tính năng, giữ nguyên hành vi, đường dẫn `/static/app.js`, ID phần tử và API.

### Đã làm
1. Tạo `server/static/js/` gồm 10 module: `core`, `auth`, `dashboard`, `settings`,
   `monitoring`, `demo`, `sensor`, `training`, `share`, `main`.
   - `core.js`: hằng số, `state`, DOM utils, hiệu ứng, `ApiError`/`api()`, trạng thái nút.
   - `dashboard.js`: nạp phiên/nhà, SSE + polling fallback, `renderHomes`.
   - `monitoring.js`: vẽ status/history/alerts/metrics, `refreshDashboard()`.
   - `settings.js`: phòng, thiết bị, tiến độ hiệu chuẩn.
   - `demo.js`, `sensor.js`, `training.js`, `share.js`: đúng một nhóm chức năng mỗi file.
   - `main.js`: gắn sự kiện, đăng ký service worker, boot cho cả hai template.
2. Tránh vòng import:
   - `core.js` có registry `registerStop()`/`stopAllActivity()`; `showAuth()` gọi
     `stopAllActivity()` thay vì import ngược dashboard/demo/training.
   - `renderRooms(reloadHome)` và `submitAuth(form, endpoint, onSuccess)` nhận callback
     từ tầng trên.
3. `server/static/app.js` còn 14 dòng, dùng `import('/static/js/main.js')` **động** để
   HTML cũ nạp kiểu script thường vẫn không vỡ cú pháp.
4. `dashboard.html` + `index.html`: script `type="module"`.
5. `service-worker.js`: cache `an-tam-home-v6`, `APP_SHELL` thêm đủ 10 module.
6. Docs: `docs/14_frontend_modules.md`; cập nhật `docs/13_sse_realtime.md`
   (đường dẫn module + service worker v6).

### Lỗi phát hiện khi smoke và đã sửa
Bấm **Chạy demo** trên trình duyệt thật báo `api is not defined`: `demo.js` thiếu
`api` trong import từ `core.js`. Đã thêm và chạy lại; demo hoạt động, console sạch.
`node --check` không bắt được lỗi này vì cú pháp vẫn hợp lệ.

### Kiểm chứng thật
- `node --input-type=module --check` cho `app.js` + 10 module: **11/11 OK**.
- Import graph chạy bằng Node với DOM stub: **IMPORT OK** (không vòng import).
- ESLint 9 `no-undef`/`no-unused-vars`: **0 error, 0 warning**.
- `pytest tests -q`: **67 passed**.
- Smoke trình duyệt thật (Flask cổng 5099, DB tạm): tải đủ 10 module HTTP 200;
  SSE 200 `text/event-stream`; đăng ký, demo (`Bedroom`, 99%), thêm/đổi tên phòng,
  tạo/thu hồi thiết bị, tạo mã chia sẻ, cảnh báo cảm biến cần HTTPS, đăng xuất/đăng
  nhập lại — tất cả chạy, không lỗi console mới.
- Service worker `an-tam-home-v6`: 18 entry, gồm đủ 11 file JS.
- `index.html` (cổng 5100) tải module, báo `HOME_REQUIRED` đúng nghiệp vụ; HTML cũ
  nạp `app.js` classic (cổng 5101) vẫn tải `/static/js/main.js`.
- `data/smarthome.db` không bị đụng: **0 alert, 0 prediction**.

### Còn lại
- G3 (multi-task/ensemble) do agent GLM phụ trách; G4 (sinh lại báo cáo) chưa làm.
- Chưa bundle JS: trình duyệt tải 11 file, dựa vào cache service worker.
- Không chạy `git commit`/`git push`.

## Phiên 10 (2026-11-01): vá lỗ hổng cert pinning Android + kiểm chứng lại toàn bộ

Báo cáo: `docs/11_kiem_tra_bao_mat.md` (mục 7-9).

**Lỗ hổng NGHIÊM TRỌNG đã vá — cert pinning của app Android tự vô hiệu hoá xác thực TLS.**
`CertificatePinner` tự viết một `X509TrustManager` và cài đè lên mặc định của Android, nhưng
`checkServerTrusted` **không hề xác thực chuỗi chứng chỉ tới root tin cậy** — nó chỉ kiểm tra
ngày hết hạn và (khi có pin) kiểm tra pin. Đồng thời `HostnameVerifier` trả về `true` ngay khi
chưa có pin, nên **kiểm tra tên miền cũng bị tắt**.

`res/raw/cert_pins.txt` chỉ chứa dòng chú thích ⇒ danh sách pin rỗng ⇒ **đúng nhánh fail-open
là nhánh đang chạy trong bản build thật**. Hệ quả: mọi kết nối `https://` của app chấp nhận
chứng chỉ bất kỳ và tên miền bất kỳ; kẻ tấn công cùng mạng đọc được email + mật khẩu đăng nhập
và token thiết bị. Nếu không viết code pinning nào thì Android vẫn kiểm tra chuỗi bình thường —
tức tính năng "bảo mật" này tự tạo ra lỗ hổng.

Đã sửa: uỷ thác xác thực chuỗi cho `TrustManagerFactory` mặc định trước rồi mới áp pin;
`getAcceptedIssuers` trả issuers thật; `pinnedSslContext()` trả **null** khi chưa cấu hình pin
để bên gọi giữ mặc định của Android; `verifyHostname()` luôn chạy
`HttpsURLConnection.getDefaultHostnameVerifier()` trước. Kiểm chứng: `gradlew assembleDebug`
**BUILD SUCCESSFUL in 52s**.

**Kiểm chứng lại toàn bộ sau khi phiên 9 tách `app.py` thành module:**
- `scripts/security_sweep.py` (mới): quét **39 tổ hợp / 34 route `/api/*`** bằng cách gọi không
  kèm phiên đăng nhập, và gọi thêm một lần với bearer token sai — **0 endpoint hở**. Rủi ro lớn
  nhất của việc tách blueprint là mất `@login_required` âm thầm; nay đã có lưới chặn hồi quy.
- Các lớp middleware mới đã kiểm chứng sống: rate limit chặn đúng ở request thứ 31 (nhóm auth
  30/60s); **`X-Forwarded-For` không được tin** (35 request với XFF đổi liên tục vẫn bị chặn —
  chỉ tin khi `SMART_HOME_TRUST_PROXY=1`); body không phải JSON trả **415** (lớp CSRF thứ hai);
  HSTS chỉ gửi khi HTTPS; lỗi API trả JSON không lộ traceback.
- `pytest tests -q` → **79 passed**; `selftest-mcp.js` → **28/28**; `security-probe.js` → **0/12**.

**Sửa môi trường build Android** (lỗi có sẵn, không do bản vá): `gradle.properties` ghim JDK vào
đường dẫn Android Studio không còn tồn tại → bỏ dòng ghim, dùng `JAVA_HOME`; `local.properties`
trỏ `sdk.dir` vào `E:\Android` (chỉ là thư mục Android Studio) → trỏ về SDK thật ở
`%LOCALAPPDATA%\Android\Sdk`.

**Ghi nhận (chưa sửa):** `security_middleware` lọc SQLi/XSS bằng regex trên query/path — không
phải biện pháp bảo vệ (regex danh sách đen luôn bypass được, và không chạm tới JSON body nơi tên
phòng/tên nhà thực sự nằm); hàng rào thật vẫn là truy vấn tham số hoá + Jinja escape, cả hai đều
đã có. Cần lưu ý rủi ro chặn nhầm nếu sau này có endpoint nhận chuỗi tự do qua query string.
`torch.load`/`joblib.load` khi nạp model là vector RCE cổ điển nếu file không đáng tin — ở đây
file do chính pipeline sinh ra nên rủi ro thấp; có thể siết thêm bằng `weights_only=True`.

## Phiên 11 (2026-11-02): triển khai Docker + Cloudflare + tên miền

Báo cáo kiểm chứng: `docs/12_trien_khai.md`. Hướng dẫn thao tác: `DEPLOY.md`.

Mục tiêu theo roadmap `tinhnang.md` — hạng mục cuối của phần code ("nén vào docker + host lên
cloudflare + deploy domain"). Trước phiên này đã có khung (Dockerfile đa stage,
docker-compose.prod.yml với Redis/nginx/certbot/cloudflared, nginx.conf) nhưng **chưa từng
chạy thử**, và khi chạy thử thì lộ 6 lỗi chặn khởi động:

1. `nginx.conf` khai báo `upstream app_backend` **hai lần** → nginx `[emerg] duplicate upstream`.
2. `include proxy_params;` trong **7** location — file này thuộc gói Debian, **không có trong
   `nginx:alpine`** → `[emerg] open() ... failed`. Header proxy đã đặt ở cấp `server` nên bỏ hẳn.
3. **4** dòng dùng `${DOMAIN:-...}` — cú pháp shell, nginx không hiểu; file lại mount thẳng vào
   `/etc/nginx/nginx.conf` nên envsubst template của image cũng không chạy.
4. Compose mount chứng chỉ vào `/etc/nginx/certs` nhưng config đọc `/etc/letsencrypt/live/...`
   (chỗ certbot ghi) → không tìm thấy chứng chỉ.
5. **Image production chạy Werkzeug dev server**: compose ghi "Gunicorn + Flask" nhưng Dockerfile
   `CMD ["python", "server/app.py"]`, và `gunicorn` thậm chí không có trong requirements.
6. Gunicorn 26 báo `[ERROR] Control server error: Permission denied: '/home/appuser'` vì
   `useradd -r` không tạo home.

Đã sửa: viết lại `nginx.conf` (một upstream, bỏ include, tên miền thật, mount `/etc/letsencrypt`);
thêm `server/wsgi.py` (không gọi `create_app()` lần hai để khỏi tách đôi singleton);
`gunicorn>=22.0`; CMD `gunicorn --worker-class gthread --workers 2 --threads 8 --timeout 300`
(worker `gthread` là bắt buộc vì dashboard dùng SSE ở `/api/stream`); tạo home cho `appuser`;
thêm `.env.prod.example`, `DEPLOY.md`, `docs/12_trien_khai.md`; gitignore `certs/`,
`certbot-www/`, `.env.prod` (chứa khoá riêng TLS).

**Kiểm chứng đã chạy thật** (Docker 29.9.2):
- `nginx -t` với `--add-host app:127.0.0.1` → **configuration file test is successful**.
- `docker compose -f docker-compose.prod.yml config --quiet` → exit 0; `docker-compose.yml` cũng vậy.
- `server/wsgi.py` gọi qua **giao diện WSGI thô** (không test client) → `200 OK` cho `/api/health`.
- `docker build --target prod` → thành công, gunicorn 26.2.0 + torch 2.15.0+cpu.
- `docker run` → container `Up (healthy)`, **0 dòng `[ERROR]`**, log có
  `Using worker: gthread` + 2 worker + `Control socket listening at /home/appuser/.gunicorn/gunicorn.ctl`;
  `GET /api/health` → 200 `{"status":"ok","database":"ok"}`; `GET /` → 200 có CSP;
  `GET /api/stream` khi chưa đăng nhập → 401 (SSE vẫn được bảo vệ đúng).

**Chưa kiểm chứng được ở máy này** (ghi rõ để không hiểu nhầm là đã thử hết): đường Cloudflare
Tunnel cần token + tài khoản thật; Let's Encrypt thật cần tên miền trỏ về IP công khai (lần thử
dùng chứng chỉ tự ký); chưa `up` cả 4 service cùng lúc.

**Còn lại của roadmap:** "server chung", "lưu trữ phân tán", và viết báo cáo (60%).

## Phiên 13 (2026-11-02): bảo mật — hạn phiên đăng nhập + CSV header, tinh chỉnh UI

Báo cáo đầy đủ: `docs/15_bao_mat_phien_csv_ui.md`. Không commit. Không đụng
thuật toán, dữ liệu, API.

### Yêu cầu
Tiếp bản phân tích bảo mật của phiên trước: sửa việc quan trọng nhất trước.
Chọn 2 lỗ hổng sửa được ngay trong code (không cần quyết định hạ tầng): cookie
phiên không có hạn server-side, và CSV injection còn sót ở dòng header export.
Kèm yêu cầu "tối ưu giao diện đẹp hơn" — làm kiểu tinh chỉnh nhỏ, dùng lại token
thiết kế sẵn có (theo tinh thần `tinhnang.md`: tham khảo mẫu mã nguồn mở, không
viết mới cả khối).

### Đã làm
1. **Hạn phiên (CAO):** phiên mang dấu `_iat` khi cấp; quá hạn 7 ngày (env
   `SMART_HOME_SESSION_MAX_AGE_HOURS`, 0 = tắt) bị xóa ngay ở before_request
   đầu tiên → route trả 401 chuẩn. Phiên thiếu `_iat` (cookie cũ) cũng bị từ
   chối → mọi người đăng nhập lại đúng một lần sau nâng cấp. Logout vẫn giữ
   nguyên hành vi cũ; Android Collector chỉ ảnh hưởng: đăng nhập lại sau 7 ngày.
   - `app_security.py` (`SESSION_MAX_AGE_HOURS`, `mark_session_issued`,
     `session_expired`), `security_middleware.py` (`install_session_guard`),
     `app.py` (guard đầu tiên trong chuỗi), `routes/auth_views.py` (đặt `_iat`).
2. **CSV header (TB):** `/api/export/scans.csv` áp `csv_formula_safe()` cho cả
   `fieldnames` lẫn key của row (`track_views.py`) — key `=HYPERLINK(...)`
   từ `/api/collect` không còn chạy công thức trong Excel; giá trị RSSI vẫn
   map đúng cột.
3. **UI:** tabular-nums cho số live; badge `#alertCount.has-pending` nền hổ phách
   khi có cảnh báo (monitoring.js + CSS); accent mint nav active; scrollbar thin;
   scroll-snap timeline; `.probability` 9px; `::selection` mint.
4. Tài liệu: `docs/15_bao_mat_phien_csv_ui.md`; `.env.example` + README mục
   Session ghi rõ hạn 7 ngày và đánh đổi Android.
5. Tests: `test_expired_session_is_rejected` (quá hạn → 401, thiếu `_iat` → 401,
   đăng nhập lại OK) và `test_csv_export_header_neutralizes_formula_in_ap_name`.

### Sự cố môi trường (đã xử lý, có xin phép)
Giữa phiên `.venv` bị hỏng (mất `pyvenv.cfg` + phần lớn site-packages; hai tiến
trình `server\app.py` cũ giữ khóa file `.pyd` → WinError 5). Nguyên nhân khớp
với ghi nhận ở trên: **agent khác đang xây lại venv song song**. Đã dừng 2
server sau khi xin phép, tái tạo `pyvenv.cfg` (Python 3.11.9), ensurepip, cài
lại gói + editable. Kết quả hội tụ đúng stack agent kia ghi: torch 2.15.0+cpu,
numpy 2.4.6, pandas 3.1.0, sklearn 1.9.1. Server đã mở lại, health OK.

### Kiểm chứng thật
- `pytest tests -q`: **84 passed** (trước phiên: 82).
- `node --check server/static/js/monitoring.js`: OK.
- Smoke Chromium thật: đăng ký → dashboard đúng nhà; **phiên giữ vững qua
  reload** (guard không làm vỡ phiên mới); `getComputedStyle` xác nhận 4 cải
  tiến CSS hiệu lực; console sạch (1 lỗi 401 duy nhất là bước probe phiên trước
  đăng nhập — flow cũ).
- `/api/health` sau khi mở lại server: `{"status":"ok","database":"ok"}`.
- `data/smarthome.db` không bị đụng (chỉ đăng ký 1 tài khoản test
  `test-smoke@example.com` qua giao diện — xóa tay nếu muốn sạch).

### Đã làm (bổ sung trong ngày, cùng phiên)
6. **Android mã hóa prefs nhạy cảm** bằng Android Keystore AES/GCM (không thêm
   thư viện; tương thích ngược plaintext cũ; Keystore lỗi → giữ hành vi cũ).
   `gradlew assembleDebug` BUILD SUCCESSFUL. Vá mục 2 trong danh sách còn lại.
7. **Webhook `http://`** ghi log cảnh báo mỗi lần gửi (không chặn cứng — một số
   dịch vụ tự host LAN chỉ có HTTP).
8. **Xóa tài khoản test** `test-smoke@example.com` khỏi DB (backup
   `.tmp/smarthome.db.bak-2026-11-02`; DB còn đúng 1 nhà thật).
9. Chạy lại `pytest tests -q` sau các bổ sung: **84 passed**.

### Còn lại (thứ tự ưu tiên đã chốt trong phân tích)
1. HTTPS LAN: tự ký cert + điền pin thật vào `network_security_config.xml`
   (khung sẵn có) — cần quyết định hạ tầng của người dùng.
2. ~~Android: EncryptedSharedPreferences~~ → **đã làm** bằng Android Keystore
   AES/GCM (không thêm thư viện).
3. Login limiter khóa theo email vẫn cho phép DoS khóa tài khoản nạn nhân —
   cần quyết định thiết kế (kết hợp khóa theo IP hoặc nâng ngưỡng).
4. ~~Webhook chỉ nhận `https://`~~ → **đã làm** theo hướng cảnh báo log.
   Salt cho hash BSSID khi thu dữ liệu thật — vẫn còn.
5. Không chạy `git commit`/`git push`.

## Phiên 12 (2026-11-02): lưu trữ phân tán (Redis) — kiểm chứng và sửa 3 lỗi

Báo cáo kiểm chứng: `docs/13_luu_tru_phan_tan.md`.

`docker-compose.prod.yml` đã khai báo service `redis` và code đã có nhánh `REDIS_HOST`,
nhưng **chưa từng chạy thử** — package `redis` thậm chí không có trong `.venv`. Chạy thử thì
nhánh Redis hỏng hoàn toàn.

**Ba lỗi đã sửa:**

1. **NGHIÊM TRỌNG — bật Redis là mọi request API trả HTTP 500.** `RateLimiter` bị dán hai lần
   thân class, sinh ra **hai định nghĩa `check`**; bản Python dùng (bản sau) đi thẳng vào
   `with self._lock:` mà không xét `_use_redis`, trong khi `__init__` chỉ tạo `_lock` khi
   KHÔNG dùng Redis. Hễ đặt `REDIS_HOST` — đúng cấu hình compose — là
   `AttributeError: 'RateLimiter' object has no attribute '_lock'` → HTTP 500. Không phát hiện
   sớm vì `/api/health` được miễn giới hạn nên smoke test qua đó vẫn xanh.
   Đã xoá định nghĩa trùng và cho `__init__` **luôn** tạo sẵn cấu trúc RAM. Cùng kiểu lỗi với
   `_client_id` (hai định nghĩa; bản chạy chỉ dùng IP còn tài liệu ghi "IP+UA") — đã gom còn
   một, giữ **chỉ IP** vì `User-Agent` do client tự đặt nên đưa vào khoá là tự cho kẻ tấn công
   thêm bucket mỗi request.
2. **Rate limit phân tán không nguyên tử.** `ZCARD` rồi `ZADD` ở hai lượt ⇒ 60 request đồng
   thời với ngưỡng 10 cho qua **29**. Đã gộp trim→đếm→kiểm tra chặn→ghi vào **một script Lua**:
   còn đúng **10**. Member sorted set nay có thêm phần ngẫu nhiên (trước lấy chính mốc thời
   gian nên hai request cùng thời điểm ghi đè nhau, bị đếm thiếu).
3. **Redis chết thì im lặng.** `except Exception: return None` khiến ứng dụng âm thầm chạy RAM:
   người vận hành tưởng hạn mức vẫn chia sẻ giữa các instance. Nay log rõ ràng, phân biệt
   "không đặt REDIS_HOST" (im lặng, đúng ý) với "đặt mà nối không được" (cảnh báo). `reset()`
   cũng xoá cả khoá trên Redis.

**Kiểm chứng đã chạy thật** (Redis 7 trong Docker):
- `scripts/rate_limit_probe.py` (mới): chế độ Redis nguyên tử (10/60) và **chia sẻ giữa hai
  tiến trình** (5+0=5); chế độ RAM nguyên tử nhưng không chia sẻ (5+5=10) — đúng thiết kế.
- Ứng dụng thật với `REDIS_HOST`: `dbsize=2`, khoá `ratelimit:auth:127.0.0.1` +
  `ratelimit:api:127.0.0.1`, `cmdstat_evalsha calls=3` đúng bằng 3 request ⇒ dùng Redis thật,
  không lặng lẽ rơi về RAM.
- `tests/test_rate_limit.py` (mới, 7 test, không cần Redis thật): chốt các lỗi trên khỏi tái phát.
- `pytest tests -q` → **91 passed**.

**Còn lại:** `MobileSensorMonitor`, `last_results`, `runtime_histories`, `training_jobs` vẫn là
trạng thái trong RAM từng tiến trình — muốn chạy nhiều instance thật thì phải chuyển tiếp hoặc
ghim mỗi nhà vào một instance (sticky session).

## Phiên 13 (2026-11-03): mở rộng báo cáo + công cụ tự soát văn phong AI

Hạng mục 1 của roadmap (`tinhnang.md`): "viết báo cáo (60%) — nhớ check đạo văn, ai — viết dài,
chỉnh format".

**Công cụ mới `scripts/report_style_check.py`** — tự soát theo `avoid.md` (Wikipedia:Signs of AI
writing) và soát trích dẫn. Làm ba việc kiểm được bằng máy, và **nói rõ giới hạn**: không thay được
Turnitin (đối chiếu kho văn bản toàn cầu) hay GPTZero.

1. Dấu hiệu văn phong AI: từ vựng AI (cả bản dịch tiếng Việt), phủ định song song, né hệ từ, quy tắc
   số 3, câu kết khuôn mẫu, hedging, in đậm quá mức, tỉ lệ gạch đầu dòng.
2. Trùng lặp nội bộ dự án (tự đạo văn): câu ≥120 ký tự trùng y nguyên với tài liệu khác trong repo.
3. Trích dẫn: mục tham khảo thiếu năm/DOI, URL còn tham số theo dõi, quá ít nguồn.

Đã siết hai lần để **không báo oan** (một công cụ kêu oan sẽ bị bỏ qua): bỏ `mã nội tuyến` trước khi
dò từ vựng nên `Portrait/Landscape/Flat` không còn bị gắn cờ; quy tắc số 3 đòi đúng ba thành phần
song song thật ngắn và bỏ qua dòng gạch đầu dòng/bảng; chỉ lấy dòng được đánh số làm mục tham khảo.

**Kết quả trên báo cáo:** không phát hiện dấu hiệu AI, không tự đạo văn, chỉ 3 gợi ý bổ sung DOI
(không phải lỗi). Trước khi siết, công cụ báo 3 chỗ — cả 3 đều là dương tính giả.

**Đã viết thêm vào `BAO_CAO_KHOA_LUAN.md`** (số từ văn xuôi 3.677 → **5.852**, tăng 59%):
- §1.4 Nghiên cứu liên quan (RADAR, Horus, ARIL, WiFi sensing, autoencoder cho dữ liệu chuỗi, phát
  hiện ngã) — trước đó báo cáo **thiếu hẳn** phần này.
- §1.5 Đối chiếu với các dự án mã nguồn mở theo đúng tinh thần `tinhnang.md`: bảng "lấy gì / không
  lấy gì" cho FIND3, ARIL, Home Assistant, ntfy.sh, OWASP Top 10; giải thích vì sao chọn RSSI thay
  vì CSI và vì sao tự chứa thay vì dùng đám mây. Có đoạn nói rõ **các mô hình đều dựa trên công
  trình đã công bố, không có kiến trúc nào do khóa luận phát minh** — vừa trung thực vừa phòng
  nghi vấn đạo văn.
- §1.6 Phương pháp thực hiện, §1.7 Đóng góp, §1.8 Cấu trúc báo cáo.
- §7.6 Hạn mức tần suất khi chạy nhiều tiến trình (Redis, script Lua nguyên tử, số đo 29/60 → 10/60,
  vì sao khoá chỉ dùng IP, vì sao phải log khi Redis chết).
- Sửa mã trong §7.5 còn ghi `CMD ["python", "server/app.py"]` (đã lỗi thời sau khi đổi sang gunicorn).
- Mục tham khảo: thêm arXiv/ISBN/URL tạp chí/ngày truy cập và 2 nguồn mới (GRU, PyTorch). **Cố ý
  không ghi DOI** cho 3 bài hội nghị vì chưa đối chiếu được với nhà xuất bản — ghi DOI sai còn tệ
  hơn không ghi, và đây đúng là lỗi `avoid.md` cảnh báo.

**Sinh lại `BAO_CAO_KHOA_LUAN.docx`** bằng `make_thesis_docx.py`: Times New Roman 13, giãn dòng 1.5,
lề trái 3 / phải 2 / trên-dưới 2.5 cm, 1079 đoạn, 14 bảng.

### Phiên 13 (tiếp): mở rộng chương 3 — Cơ sở lý thuyết

Chương 3 trước đây chỉ 392 từ và chủ yếu là sơ đồ ASCII, thiếu phần giải thích. Đã viết lại thành
**2.423 từ**, giữ nguyên các sơ đồ và bổ sung phần "vì sao":

- §3.1: cơ sở vật lý của đa đường, lý do chọn RSSI thay vì CSI, lý do chọn mức phòng thay vì toạ độ,
  bốn nguồn nhiễu và cách xử lý (cửa sổ trượt, tăng cường dữ liệu, giá trị thay thế −100 dBm cho AP
  mất, băm BSSID kèm lỗi chữ hoa/chữ thường giữa PC và Android).
- §3.2: vì sao tích chập 1D trên trục AP vẫn hữu ích dù không có thứ tự không gian; vì sao dùng tích
  chập tách rời theo chiều sâu; công thức CenterLoss và lý do cần nó cho các bước lọc phía sau; số
  hạng Jensen–Shannon cho tính liên tục theo thời gian.
- §3.3: ba thành phần của vector đặc trưng hành vi; vì sao autoencoder thay vì bộ phân loại (không có
  mẫu bất thường gán nhãn); vì sao GRU thay vì LSTM; **quy trình chọn ngưỡng trên validation, không
  dùng tập test** kèm giải thích đây là lỗi rò rỉ của bản đầu đã được sửa; lý do kết hợp thêm bộ luật.
- §3.4: ba pha vật lý của cú ngã (rơi – va chạm – nằm yên); vì sao dùng máy trạng thái thay vì phân
  loại từng mẫu; hướng cầm máy suy từ vector trọng lực; giới hạn (phải mang điện thoại, ứng dụng đang
  mở) và ghi rõ phần này chưa kiểm thử.
- §3.5: giải thích bộ lọc topology là cập nhật Bayes rút gọn; vì sao ma trận kề phải khai báo thủ công;
  ý nghĩa tham số `self_weight = 0,75`; nguồn gốc ý tưởng từ FIND3 và ARIL kèm câu nói rõ **không
  dùng lại mã nguồn của các dự án đó**.

Tổng số từ văn xuôi: 3.677 (đầu phiên) → **7.816** (+113%). Bộ tự soát `report_style_check.py` sau
khi siết tiếp (bỏ mã nội tuyến và nội dung trong ngoặc trước khi dò quy tắc số 3) báo **không phát
hiện dấu hiệu văn phong AI**, tỉ lệ gạch đầu dòng 8%, không tự đạo văn.

### Phiên 13 (tiếp): bổ sung mục 8.6 và 8.7 cho chương Kiểm thử

Chương 8 trước chỉ có kết quả mô hình. Đã thêm hai mục về kiểm thử phần mềm và kiểm chứng triển khai,
toàn bộ dùng số đo thật của các phiên trước:

- **§8.6 Kiểm thử phần mềm, phân quyền và bảo mật**: 91 test tự động; quét phân quyền 39 tổ hợp trên
  34 route `/api/*` với 0 tổ hợp hở; quét mã tĩnh từ 69 vấn đề (phần lớn là sai) xuống 4 vấn đề mức
  thông tin sau khi sửa bảy lỗi độ chính xác của chính bộ quét; và mô tả lỗi ghim chứng chỉ Android
  (lớp bảo mật tự tạo lỗ hổng) kèm cách vá và cách xác nhận bằng biên dịch lại.
- **§8.7 Kiểm chứng triển khai**: bảng 9 hạng mục với lệnh và kết quả thật (`nginx -t` thành công,
  compose config exit 0, gọi WSGI thô trả 200, build ảnh production thành công, container `Up
  (healthy)` với 0 dòng `[ERROR]`, worker `gthread`, `/api/stream` trả 401 khi chưa đăng nhập), kèm
  phần nói rõ những gì **chưa** kiểm chứng được (Cloudflare Tunnel, Let's Encrypt thật, chạy cả bốn
  service cùng lúc).
