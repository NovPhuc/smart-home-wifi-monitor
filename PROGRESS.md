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

## Kiểm định ngoài + dữ liệu thật (2026-10-11, chiều)
- **UCI WIL** (DOI 10.24432/C51880, 7 AP × 4 phòng × 2000 mẫu): RoomNetLite **98.99%** / SimpleCNN 98.23% / RF=kNN=MLP 99.24% → `results/external_uci_wil/` — ngang dải 96-99% đã công bố.
- **UJIIndoorLoc** (DOI 10.24432/C5MS59, toà 2/tầng 3, lưới 6 vùng × 2694 mẫu, 520 AP): RoomNetLite 81.12% / SimpleCNN 87.19% / **RF 92.36%** / kNN 76.63% → `results/external_ujiindoorloc/` — phát hiện: trên fingerprint siêu chiều, RF tốt nhất; RoomNetLite cần cải thiện (lọc WAP hiếm / tăng channels).
- Công cụ: `scripts/convert_external_dataset.py` + `config_external_*.yaml` (tái lập được; meta.json ghi nguồn/license/sơ đồ session).
- **Dữ liệu thật từ app Android trong DB**: 639 wifi_scans (thiết bị PEDM00) — Phòng ngủ 337 mẫu/5 session, Nhà Vệ Sinh 301 mẫu/8 session; 11/10 14:03 POST /api/collect HTTP 200 qua Cloudflare Tunnel → app end-to-end ✓.
- **Lỗi #5 mới phát hiện + sửa**: test API không cô lập DB → 11 home "Nhà Smoke Test" rác trong smarthome.db; đã sửa test (SMART_HOME_DATABASE → DB tạm trước khi import server). XÓA home rác: **CHỜ CHỦ PROJECT DUYỆT** (giữ home 3 "Nhà A" chứa dữ liệu thật).
- `BAO_CAO_KET_QUA.docx` cập nhật lần 2: đối chiếu **9 ĐẠT / 2 ĐẠT MỘT PHẦN / 0 CHƯA ĐẠT** + bảng kiểm định ngoài 3.1.

## Database + Public (2026-10-11, tối)
- **Dọn DB (có sự đồng ý của chủ project)**: backup toàn bộ trước → `data/backup_db/smarthome_backup_2026-10-11.db` (639 scans, thư mục đã loại khỏi git); xóa 13 home rác (id 1 "my house", id 2 "Nha cua toi" — 1 scan cũ 6/10 được bảo toàn trong backup, id 4–14 "Nhà Smoke Test" — rác test). Còn lại: home 3 "Nhà A" (READY, 638 scans thật, 13 session, token app SgjENw còn hiệu lực — app không cần cấu hình lại). integrity ok, 0 vi phạm FK.
- **Hardening public**: cài python-dotenv; `server/app.py` nạp `.env` khi khởi động; tạo `SMART_HOME_SECRET_KEY` (random 64 hex) + `SMART_HOME_SECURE_COOKIE=1` trong `.env` (ngoài git); thêm python-dotenv vào requirements.txt. Lưu ý: secure cookie → đăng nhập web qua `http://localhost:5000` sẽ không giữ phiên — đăng nhập qua URL tunnel (HTTPS).
- **Trạng thái public**: dashboard công khai qua Quick Tunnel `https://necessary-thousands-etc-donated.trycloudflare.com` (đã xác minh HTTP 200 từ Internet sau restart Flask). URL cố định: cần Cloudflare account + `cloudflared tunnel login` (named tunnel). Nếu "public" = repo GitHub public: cần bạn tạo repo rỗng + gửi URL, push sẽ thực hiện sau khi bạn xác nhận lần cuối (ràng buộc: hỏi trước khi push).
- **Cloud DB (chưa chọn provider)**: chờ bạn tạo Supabase/Neon free → dán `DATABASE_URL=postgresql://...` vào `.env` → tôi sẽ chuyển storage.py sang chế độ kép (SQLite cho 43 test, Postgres khi có DATABASE_URL) + script migrate giữ nguyên 638 scans thật.
- Flask khởi động lại với cấu hình mới (shell `sh_129d636e1001nSBCBMd9A5oXWR`); đã xác minh LOCAL 200 + TUNNEL 200.

## Public dự án (2026-10-11, tối)
- Đã tạo nhánh **`public-release`** (orphan, root commit `bd7005b`, 218 file) — lịch sử sạch, không chứa: de_cuong_text.txt (tài liệu trường), BAO_CAO_KET_QUA.docx, train logs + runlogs (đường dẫn máy cá nhân), backup_original, android build intermediates, 2 script report cũ.
- `.gitignore` bản public bổ sung: .env, data/*.db, data/homes/, data/backup_db/, models/homes/, .tmp/, android build — dữ liệu thật của người dùng KHÔNG có trong repo public.
- Đã quay lại nhánh `fix/optimize-training` làm việc; file trên đĩa nguyên vẹn.
- **Chờ chủ project**: tạo repo trống trên GitHub (gợi ý tên: smart-home-wifi-monitor-336, visibility Public) → gửi URL → push nhánh public-release lên main sau khi xác nhận. Chưa push (ràng buộc). Cân nhắc thêm LICENSE (MIT) nếu muốn cho phép tái sử dụng.

## Vị trí kết thúc phiên
Các việc chính đã đóng (kể cả dọn DB). Còn lại: (1) bạn thu đủ protocol thật (S08 đang chạy — nhớ đủ 3 hướng cầm) → bấm TRAIN trên dashboard để có metrics chính thức trên dữ liệu thật; (2) nếu muốn DB cloud: tạo Supabase/Neon + dán DATABASE_URL vào .env; (3) nếu muốn repo public: tạo repo GitHub + gửi URL; (4) báo cáo cuối khóa + slide (tuần 11-12).

## Triển khai Cloudflare Tunnel (cập nhật 2026-10-11 sau khi server restart)
- Lịch sử URL (Quick Tunnel đổi URL mỗi lần khởi động): `worldwide-demand-associated-lakes.trycloudflare.com` (đã chết) → **URL hiện tại: https://necessary-thousands-etc-donated.trycloudflare.com** (đã xác minh HTTP 200 từ Internet, trang "An Tâm Home — WiFi Care").
- Flask dashboard (port 5000) chạy nền → `.tmp/flask.log` (shell `sh_129babe93001B0b8HzZSDlZD7y`); cloudflared 2026.10.0 → `.tmp/cloudflared.log` (shell `sh_129babe94001kbQeSzObb57168`).
- App Android: trường Backend PHẢI dán URL HTTPS tunnel (KHÔNG dùng `http://192.168.1.100:5000` — địa chỉ LAN không tới được qua 4G; IP LAN thật của máy là `192.168.1.236` nếu muốn dùng cùng WiFi). Device token + session lưu trong SQLite nên vẫn hợp lệ sau restart.
- Muốn URL cố định: cần Cloudflare account + `cloudflared tunnel login` (named tunnel).
- Kết nối LAN (thay thế): IP thật của laptop là `192.168.1.236` (KHÔNG phải 192.168.1.100 như app đang cấu hình — nguyên nhân báo "Failed to connect"); Firewall Windows bật ở cả 3 profile và lệnh `netsh advfirewall firewall add rule ... localport=5000` cần quyền Admin (chưa chạy được từ shell thường) → khuyến nghị dùng URL tunnel vì không cần đụng firewall; nếu dùng LAN phải chạy lệnh netsh với PowerShell Admin.
- Dừng dịch vụ: kết thúc 2 tiến trình nền (python server/app.py + .tmp/cloudflared.exe).
